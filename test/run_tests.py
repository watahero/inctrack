"""
inctrack test suite.

Loads the addon's real Lua modules (parser.lua, state.lua) into an embedded Lua
runtime and exercises them -- so a pass here means the shipped code, not a
reimplementation, behaves.

    pip install lupa
    python test/run_tests.py                 # unit suites only
    python test/run_tests.py <chatlog_dir>   # + replay of real chatlogs

The unit suites need nothing but Python and lupa. The replay suites need a
directory of Ashita chatlogs (<Ashita>\\chatlogs\\<Name>_YYYY.MM.DD.log); pass
it as the first argument or set INCURSION_CHATLOGS. The player name is taken
from the log filenames. Without logs those suites are skipped, not failed.

The persistence suite round-trips the save format through Ashita's own
json.lua. It is found next to the chatlogs (<Ashita>\\addons\\libs) or via
INCURSION_ASHITA_LIBS; without it that suite is skipped.

Suites:
  1. parser coverage    -- every structural Incursion line must parse      [logs]
  2. generic tier       -- the catch-alls must match nothing that exists   [logs]
  3. run reconstruction -- instance, phase, points, completion per run     [logs]
  4. state unit tests   -- objectives, bonus, recovery
  5. adaptability       -- invented future content is still tracked
  6. disconnect         -- stale progress is never presented as current
  7. timers             -- countdown, linger, staleness
  8. persistence        -- json round trip                                  [libs]
  9. ui                 -- pure helpers, and whole-window render snapshots
 10. addon shell        -- registration, text_in, settings, commands

ui.lua and inctrack.lua are reached through stubbed hosts (test/stubs.py);
make_host() builds an isolated runtime with both installed.

A few assertions are recorded as expected failures with Result.xfail. An
expected failure asserts the behaviour the addon is *supposed* to have; a
known defect is why it is false today. They are counted like any other check,
they print on their own XFAIL lines, and they never make the run exit
non-zero. Phase 2 is where they go green.
"""

import os
import re
import sys
import glob

import lupa

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(os.path.dirname(HERE), "inctrack")

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import stubs

# Name used in the synthetic unit-test fixtures below. Unrelated to any real
# character; the replay suites read the real name off the log filenames.
PLAYER = "Godwen"


def find_logs():
    """Chatlog directory from argv, then the environment, else None."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return os.environ.get("INCURSION_CHATLOGS") or None


def find_ashita_libs(logdir):
    """Ashita's addons/libs, from the environment or relative to the logs."""
    explicit = os.environ.get("INCURSION_ASHITA_LIBS")
    if explicit:
        return explicit
    if logdir:
        return os.path.join(os.path.dirname(os.path.abspath(logdir)), "addons", "libs")
    return None


def player_from_logs(lines):
    """Chatlogs are named <Character>_YYYY.MM.DD.log; take the character."""
    for path, _, _ in lines:
        name = os.path.basename(path).split("_", 1)[0]
        if name:
            return name
    return PLAYER

# Log lines carry one or two "[HH:MM:SS] " prefixes that the game never sends.
TS = re.compile(r"^(?:\[\d{2}:\d{2}:\d{2}\]\s*)+")

# If the parser returns nil for one of these, the addon silently misses an
# event in game.
MUST_PARSE = re.compile(
    r"^(?:"
    r"Incursion \[.+?\] (?:Begins!|Complete!|Phase #|Bonus Objective|Recovering session)"
    r"|New Objective: Defeat "
    r"|\(Boss: .+ at .+\)$"
    r"|Bonus Objective: (?:Defeat |Find the hidden chest!)"
    r"|You have \d+ minutes? remaining inside this Incursion\.$"
    r"|\S+ gains \d+ incursion points\.$"
    r"|\S+ gains the effect of .+ \(.*\): .+"
    r")"
)

BEGIN = re.compile(r"^Incursion \[(.+?)\] Begins!")
COMPLETE = re.compile(r"^Incursion \[(.+?)\] Complete!")
POINTS = re.compile(r"^(\S+) gains (\d+) incursion points\.$")
PHASE = re.compile(r"^Incursion \[(.+?)\] Phase #(\d+) (\d+)/(\d+)$")


def make_lua():
    lua = lupa.LuaRuntime()
    lua.execute(
        "package.path = [[%s\\?.lua;]] .. package.path" % ADDON.replace("\\", "\\\\")
    )
    lua.execute("__clock = 0")
    lua.execute("function __clockfn() return __clock end")
    lua.execute("__parser = require('parser')")
    lua.execute("__State  = require('state')")
    g = lua.globals()
    return lua, g.__parser, g.__State


def new_state(lua, State, player=PLAYER):
    return State.new(
        lua.table_from({"clock": lua.eval("__clockfn"), "player": player})
    )


# --------------------------------------------------------------------------
# The stubbed host: ui.lua and inctrack.lua, outside the game
# --------------------------------------------------------------------------

# Walk upvalues transitively, following function-valued ones and remembering
# what has been visited so a cycle cannot loop. _ENV is skipped: it is the
# globals table, and returning it would let a caller mistake a global for one
# of the file-scope locals this exists to reach.
UPVALUE_CHUNK = """
function __gsd_upvalues(fn)
    local out, seen, queue = {}, {}, { fn };
    local i = 1;
    while i <= #queue do
        local f = queue[i];
        i = i + 1;
        if not seen[f] then
            seen[f] = true;
            local n = 1;
            while true do
                local name, value = debug.getupvalue(f, n);
                if name == nil then
                    break;
                end
                if name ~= '_ENV' then
                    out[name] = value;
                    if type(value) == 'function' and not seen[value] then
                        queue[#queue + 1] = value;
                    end
                end
                n = n + 1;
            end
        end
    end
    return out;
end
"""


class Host(stubs.AshitaHost):
    """An isolated Ashita + ImGui host: one call, one whole addon.

    A fresh lupa runtime per host, so each scenario gets clean module state --
    ui.lua keeps short_cache and origin_x at file scope and inctrack.lua keeps
    one incursion table, so a scenario that needs a pristine addon builds a new
    host rather than juggling package.loaded. make_lua()'s shared runtime and
    the eight suites that depend on it are left exactly as they are.

    Adds to AshitaHost:
      imgui  -- the ImGuiRecorder
      addon  -- inctrack.lua's file-scope locals, by upvalue reflection
    """

    def __init__(self, player=PLAYER, profile=None):
        lua = lupa.LuaRuntime()
        lua.execute(
            "package.path = [[%s\\?.lua;]] .. package.path" % ADDON.replace("\\", "\\\\")
        )
        lua.execute("__clock = 0")
        lua.execute("function __clockfn() return __clock end")
        self.imgui = stubs.install_imgui(lua)
        stubs.AshitaHost.__init__(self, lua, player=player, profile=profile)

    @property
    def addon(self):
        """The addon shell's file-scope locals: incursion, visible, reset,
        persist, printf, now, MUST_SAVE and the rest.

        Resolved lazily over every registered handler plus the profile-switch
        callback, since between them they close over the whole shell.
        """
        names = {}
        functions = list(self.events.values())
        callback = self.profile_callback
        if callback is not None:
            functions.append(callback)
        for fn in functions:
            names.update(lua_locals(self, fn))
        return names


def make_host(player=PLAYER, profile=None):
    """Build an isolated host with ui.lua's and inctrack.lua's hosts stubbed.

    player  -- what AshitaCore reports as party member 0 ('' defers the fetch)
    profile -- overrides merged over the addon's default settings on load
    """
    return Host(player=player, profile=profile)


def lua_locals(host, fn):
    """Every file-scope local reachable from `fn`, as a name -> value dict.

    ui.lua and inctrack.lua declare their helpers as file-scope locals, so
    nothing but ui.render and the registered handlers is reachable by name --
    and the addon may not be edited to export them. Upvalue reflection is the
    only way to unit-test them without changing the shipped code.

    From ui.render this reaches the draw functions and, through them,
    clock_str, right_text, wrapped, bar, urgency, replace_plain, shorten,
    STAT_SHORT, COLOR, CONTENT_W and origin_x.
    """
    lua = host.lua
    if lua.globals()["__gsd_upvalues"] is None:
        available = lua.eval(
            "type(debug) == 'table' and type(debug.getupvalue) == 'function'")
        if not available:
            raise RuntimeError(
                "debug.getupvalue is unavailable in this lupa build; "
                "ui.lua's and inctrack.lua's file-scope locals cannot be "
                "reached without it")
        lua.execute(UPVALUE_CHUNK)
    found = lua.globals()["__gsd_upvalues"](fn)
    return {k: v for k, v in found.items()}


def clean(line):
    return TS.sub("", line.rstrip("\n").rstrip("\r")).strip()


def load_lines(logdir):
    files = sorted(glob.glob(os.path.join(logdir, "*.log")))
    if not files:
        raise SystemExit("no *.log files found in %s" % logdir)
    out = []
    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for lineno, raw in enumerate(fh, 1):
                out.append((os.path.basename(path), lineno, clean(raw)))
    return out


def feed(state, parser, lines):
    for line in lines:
        ev = parser.parse(line)
        if ev is not None:
            state.apply(state, ev)


def extra_of(state):
    out = {}
    for entry in state.extra_sorted(state).values():
        out[entry["label"]] = (
            int(entry["cur"]) if entry["cur"] is not None else None,
            int(entry["max"]) if entry["max"] is not None else None,
            bool(entry["done"]),
        )
    return out


# Report markers. Both literals are a contract, not a style choice: the phase
# criteria and the defect suites count these lines in the run's output, so
# nothing else the harness prints may contain either substring.
XFAIL_MARK = "XFAIL "
FIXED_MARK = "NOW PASSING "


class Result:
    def __init__(self, title):
        self.title = title
        self.checks = 0
        self.failures = []
        self.notes = []
        self.xfails = []
        self.fixed = []

    def check(self, cond, msg):
        self.checks += 1
        if not cond:
            self.failures.append(msg)

    def xfail(self, cond, msg):
        """Assert behaviour the addon is *supposed* to have, knowing a defect
        makes it false today.

        Counts as a check like any other. A false condition is the expected
        failure and lands in `xfails`; a condition that unexpectedly holds
        means the defect is gone and lands in `fixed`, which is loud but does
        not turn the run red either way. The message names the defect in the
        user's terms, not the code's.
        """
        self.checks += 1
        if cond:
            self.fixed.append(msg)
        else:
            self.xfails.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    def status(self):
        if self.failures:
            return "FAILED (%d)" % len(self.failures)
        if self.xfails:
            return "ok (%d known defects)" % len(self.xfails)
        return "ok"

    def report(self):
        print("  %-44s %6d checks  %s"
              % (self.title, self.checks, self.status()))
        for n in self.notes:
            print("      %s" % n)
        for x in self.xfails:
            print("      %s%s" % (XFAIL_MARK, x))
        for f in self.fixed:
            print("      %s%s" % (FIXED_MARK, f))
        for f in self.failures[:10]:
            print("      FAIL %s" % f)
        if len(self.failures) > 10:
            print("      ... %d more" % (len(self.failures) - 10))
        # An expected failure is not a failure: the process still exits 0.
        return not self.failures


# --------------------------------------------------------------------------
# 1 + 2. parser coverage, and the generic tier staying dormant
# --------------------------------------------------------------------------

def test_parser(lines, parser):
    coverage = Result("parser: structural lines all parse")
    dormant = Result("parser: generic tier matches nothing today")

    kinds = set()
    generics = {}

    for path, lineno, line in lines:
        ev = parser.parse(line)

        if MUST_PARSE.match(line):
            coverage.check(ev is not None,
                           "unparsed %s:%d  %r" % (path, lineno, line))

        if ev is None:
            continue
        kinds.add(ev["t"])

        # The generic patterns exist for content the server does not send yet.
        # If one fires on a real line, a specific pattern has regressed and the
        # window would lose a progress bar or a coordinate.
        if ev["generic"]:
            dormant.check(False, "generic %s on %s:%d  %r"
                          % (ev["t"], path, lineno, line))
            generics[ev["t"]] = generics.get(ev["t"], 0) + 1

    coverage.note("event kinds: %s" % ", ".join(sorted(kinds)))
    if not generics:
        dormant.check(True, "")
        dormant.note("all real lines handled by a specific pattern")
    return coverage, dormant


# --------------------------------------------------------------------------
# 3. replay every run
# --------------------------------------------------------------------------

def test_replay(lines, lua, parser, State, player):
    """
    Walk the logs once, driving the real state machine, and compare its view of
    each run against facts recomputed straight from the raw text.
    """
    res = Result("state: run reconstruction")

    state = new_state(lua, State, player)
    active = None

    for path, lineno, line in lines:
        ev = parser.parse(line)

        m = BEGIN.match(line)
        if m:
            active = {"instance": m.group(1), "points": 0,
                      "point_events": 0, "phases": {}}

        if ev is not None:
            state.apply(state, ev)

        if active is None:
            continue

        m = PHASE.match(line)
        if m and m.group(1) == active["instance"]:
            active["phases"][int(m.group(2))] = (int(m.group(3)), int(m.group(4)))

        m = POINTS.match(line)
        if m:
            active["points"] += int(m.group(2))
            active["point_events"] += 1

        m = COMPLETE.match(line)
        if m and m.group(1) == active["instance"]:
            verify_run(active, state, res, path)
            active = None

    return res


def verify_run(active, state, res, path):
    run = state.snapshot(state)
    tag = "%s %s" % (path, active["instance"])

    res.check(run["instance"] == active["instance"],
              "%s: instance %r" % (tag, run["instance"]))
    res.check(int(run["points"]) == active["points"],
              "%s: points %d != %d" % (tag, int(run["points"]), active["points"]))
    res.check(int(run["phases_cleared"]) == active["point_events"],
              "%s: phases %d != %d"
              % (tag, int(run["phases_cleared"]), active["point_events"]))
    res.check(bool(run["finished"]), "%s: not marked finished" % tag)
    res.check(run["finish_time"] is not None, "%s: no finish time" % tag)

    # The missed-phase inference must stay silent on a run we watched from end
    # to end, or every normal run would show its points as a lower bound.
    res.check(not run["points_partial"],
              "%s: clean run flagged as having missed points" % tag)
    res.check(not run["desynced"], "%s: clean run left out of sync" % tag)

    if active["phases"]:
        last = max(active["phases"])
        res.check(int(run["phase"] or 0) == last,
                  "%s: phase %s != %d" % (tag, run["phase"], last))


# --------------------------------------------------------------------------
# 4. state unit tests
# --------------------------------------------------------------------------

def test_state_units(lua, parser, State):
    res = Result("state: objectives, bonus, recovery")

    s = new_state(lua, State)
    feed(s, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Mesmerizer, Orcish Fodder)",
        "(Boss: Orcish Martial at (G-6))",
        "Incursion [Fort Ghelsba] Phase #1 7/20",
    ])
    run = s.snapshot(s)
    res.check(run["instance"] == "Fort Ghelsba", "instance not set")
    res.check(run["difficulty"] == "Normal", "difficulty not set")
    res.check(int(run["phase"]) == 1 and int(run["kills_cur"]) == 7
              and int(run["kills_max"]) == 20, "phase progress wrong")
    res.check(run["objective"]["kind"] == "kills", "objective kind wrong")
    res.check(len(list(run["objective"]["mobs"].values())) == 3, "mobs not split")
    res.check(run["next_boss"]["name"] == "Orcish Martial", "boss hint missed")
    res.check(run["next_boss"]["loc"] == "(G-6)", "boss loc wrong")

    feed(s, parser, ["New Objective: Defeat Orcish Martial at (G-6)!"])
    run = s.snapshot(s)
    res.check(run["objective"]["kind"] == "boss", "did not switch to boss")
    res.check(int(run["kills_cur"]) == 20, "kills not completed on boss spawn")

    # Boss loc with a map suffix survives intact.
    s2 = new_state(lua, State)
    feed(s2, parser, [
        "Incursion [Giddeus] Begins! (Normal)",
        "New Objective: Defeat Yagudo Scout at (J-9) (Map #1)!",
    ])
    res.check(s2.snapshot(s2)["objective"]["loc"] == "(J-9) (Map #1)",
              "map suffix lost from boss location")

    # Bonus objective, all three announcement forms.
    for line, kind, label, mx in [
        ("Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
         "kills", "Sentry Lizard", 5),
        ("Bonus Objective: Defeat Sentinel Lizard at (I-8)! (Expires in 10 Minutes)",
         "nm", "Sentinel Lizard", 1),
        ("Bonus Objective: Find the hidden chest! (Expires in 10 Minutes)",
         "chest", "Find the hidden chest", None),
    ]:
        s3 = new_state(lua, State)
        feed(s3, parser, ["Incursion [Fort Ghelsba] Begins! (Normal)", line])
        b = s3.snapshot(s3)["bonus"]
        res.check(b is not None and b["kind"] == kind and b["label"] == label,
                  "bonus form not parsed: %r" % line)
        if mx is not None:
            res.check(int(b["max"]) == mx, "bonus max wrong for %r" % line)

    s4 = new_state(lua, State)
    feed(s4, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
        "Incursion [Fort Ghelsba] Bonus Objective: Sentry Lizard 3/5",
    ])
    b = s4.snapshot(s4)["bonus"]
    res.check(int(b["cur"]) == 3 and int(b["max"]) == 5, "bonus progress wrong")
    feed(s4, parser, ["Incursion [Fort Ghelsba] Bonus Objective Complete!"])
    b = s4.snapshot(s4)["bonus"]
    res.check(bool(b["done"]) and int(b["cur"]) == 5, "bonus completion wrong")

    # Points are ours only.
    s5 = new_state(lua, State)
    feed(s5, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Godwen gains 84 incursion points.",
        "Vidikh gains 999 incursion points.",
    ])
    run = s5.snapshot(s5)
    res.check(int(run["points"]) == 84, "counted another player's points")
    res.check(int(run["phases_cleared"]) == 1, "phases_cleared wrong")

    # Recovery keeps a live run of the same instance rather than wiping it.
    s6 = new_state(lua, State)
    feed(s6, parser, [
        "Incursion [Giddeus] Begins! (Normal)",
        "Godwen gains 92 incursion points.",
        "Incursion [Giddeus] Recovering session...",
        "You have 81 minutes remaining inside this Incursion.",
    ])
    res.check(int(s6.snapshot(s6)["points"]) == 92,
              "recovery discarded a live run")

    # Any instance-tagged message naming a different instance resets the run.
    s7 = new_state(lua, State)
    feed(s7, parser, [
        "Incursion [Giddeus] Begins! (Normal)",
        "Godwen gains 92 incursion points.",
        "Incursion [Davoi] Phase #1 3/20",
    ])
    run = s7.snapshot(s7)
    res.check(run["instance"] == "Davoi" and int(run["points"]) == 0,
              "stale run not reset by a foreign phase message")

    s8 = new_state(lua, State)
    feed(s8, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s",
    ])
    run = s8.snapshot(s8)
    res.check(bool(run["finished"]), "not finished")
    res.check(run["finish_time"] == "48m 44s",
              "finish time wrong: %r" % run["finish_time"])
    res.check(int(s8.elapsed(s8)) == 48 * 60 + 44,
              "elapsed not frozen to server time")
    res.check(bool(s8.should_show(s8)), "window hidden immediately on completion")

    # Boons: the buffs picked between phases. The glyph inside the parens is a
    # client icon code -- real logs carry raw high bytes there -- and must be
    # discarded; the two bytes below are what the log actually contains.
    glyph = "()"
    s9 = new_state(lua, State)
    feed(s9, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Godwen gains the effect of Ronin's Revenge %s: WS Accuracy+15 / Store TP+8" % glyph,
        "Godwen gains the effect of Protect.",                 # ordinary buff
        "Godwen gains the effect of Stoneskin.",
        "Vidikh gains the effect of Fighter's Fury %s: STR+8 / Attack+15" % glyph,
        "Godwen gains the effect of Stallwart's Sentinel %s: VIT+10 / Damage taken-15%%" % glyph,
    ])
    boons = list(s9.snapshot(s9)["boons"].values())
    res.check([b["name"] for b in boons] == ["Ronin's Revenge", "Stallwart's Sentinel"],
              "boons wrong: %r" % [b["name"] for b in boons])
    res.check(boons[0]["stats"] == "WS Accuracy+15 / Store TP+8",
              "boon stats wrong: %r" % boons[0]["stats"])

    # A repeated pick updates in place rather than listing twice.
    feed(s9, parser, [
        "Godwen gains the effect of Ronin's Revenge %s: WS Accuracy+20 / Store TP+10" % glyph,
    ])
    boons = list(s9.snapshot(s9)["boons"].values())
    res.check(len(boons) == 2 and boons[0]["stats"].endswith("TP+10"),
              "repeat boon not deduped: %r" % [(b["name"], b["stats"]) for b in boons])

    # Cleared by a new run.
    feed(s9, parser, ["Incursion [Giddeus] Begins! (Normal)"])
    res.check(len(list(s9.snapshot(s9)["boons"].values())) == 0,
              "boons carried into a new run")

    return res


# --------------------------------------------------------------------------
# 4b. adaptability: message shapes the server does not send yet
# --------------------------------------------------------------------------

def test_future_content(lua, parser, State):
    """
    Nothing in the addon hardcodes an instance, boss, mob or objective name.
    These are invented messages in shapes the server does not currently use;
    they stand in for content added later, and must still reach the window.
    """
    res = Result("adaptability: unseen content still tracked")

    # A brand new instance with a new difficulty tier, more phases than any
    # instance has today, and an unusually large kill cap.
    s = new_state(lua, State)
    feed(s, parser, [
        "You have 120 minutes remaining inside this Incursion.",
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "New Objective: Defeat 40 enemies (Demon Pawn, Demon Knight)",
        "(Boss: Demon Overlord at (K-7) (Map #4))",
        "Incursion [Castle Zvahl Baileys] Phase #12 31/40",
    ])
    run = s.snapshot(s)
    res.check(run["instance"] == "Castle Zvahl Baileys", "new instance not tracked")
    res.check(run["difficulty"] == "Mythic", "new difficulty not tracked")
    res.check(int(run["phase"]) == 12, "phase beyond #8 not tracked")
    res.check(int(run["kills_cur"]) == 31 and int(run["kills_max"]) == 40,
              "new kill cap not tracked")
    res.check(run["next_boss"]["name"] == "Demon Overlord", "new boss not tracked")
    res.check(int(s.time_left(s)) == 120 * 60, "longer instance timer not tracked")

    # An objective phrased in a way no current message uses.
    s2 = new_state(lua, State)
    feed(s2, parser, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "New Objective: Escort the Cardian to the sealed door at (H-8)!",
    ])
    obj = s2.snapshot(s2)["objective"]
    res.check(obj is not None and obj["kind"] == "text",
              "unknown objective wording dropped")
    res.check(obj["text"] == "Escort the Cardian to the sealed door at (H-8)!",
              "unknown objective text mangled: %r" % (obj and obj["text"]))

    # A counter in a shape we do not specifically know.
    s3 = new_state(lua, State)
    feed(s3, parser, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Incursion [Castle Zvahl Baileys] Seals Broken 2/6",
    ])
    res.check(extra_of(s3).get("Seals Broken") == (2, 6, False),
              "unknown counter dropped: %r" % extra_of(s3))

    feed(s3, parser, ["Incursion [Castle Zvahl Baileys] Seals Broken 6/6"])
    res.check(extra_of(s3).get("Seals Broken") == (6, 6, True),
              "unknown counter did not complete: %r" % extra_of(s3))

    # Several unknown counters coexist rather than overwriting each other.
    feed(s3, parser, ["Incursion [Castle Zvahl Baileys] Braziers Lit 1/3"])
    got = extra_of(s3)
    res.check(got.get("Seals Broken") == (6, 6, True)
              and got.get("Braziers Lit") == (1, 3, False),
              "unknown counters collided: %r" % got)

    # An unknown completion line for a counter we have seen.
    feed(s3, parser, ["Incursion [Castle Zvahl Baileys] Braziers Lit Complete!"])
    res.check(extra_of(s3).get("Braziers Lit") == (3, 3, True),
              "unknown completion not applied: %r" % extra_of(s3))

    # A bonus objective phrased in a new way, with its expiry still understood.
    s4 = new_state(lua, State)
    feed(s4, parser, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Bonus Objective: Light all four braziers! (Expires in 7 Minutes)",
    ])
    b = s4.snapshot(s4)["bonus"]
    res.check(b is not None and b["label"] == "Light all four braziers!",
              "unknown bonus wording dropped: %r" % (b and b["label"]))
    res.check(int(s4.bonus_remaining(s4)) == 7 * 60,
              "expiry not read from an unknown bonus wording")

    # A bonus with no expiry at all still registers.
    s5 = new_state(lua, State)
    feed(s5, parser, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Bonus Objective: Survive without a KO!",
    ])
    b = s5.snapshot(s5)["bonus"]
    res.check(b is not None and b["label"] == "Survive without a KO!",
              "bonus without an expiry dropped")
    res.check(s5.bonus_remaining(s5) is None, "invented an expiry")

    # Any other instance-tagged line surfaces as a transient note.
    s6 = new_state(lua, State)
    feed(s6, parser, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Incursion [Castle Zvahl Baileys] The gate grinds open.",
    ])
    res.check(s6.note(s6) == "The gate grinds open.",
              "unknown status line dropped: %r" % s6.note(s6))

    # An unknown line for a different instance still resets a stale run.
    s7 = new_state(lua, State)
    feed(s7, parser, [
        "Incursion [Giddeus] Begins! (Normal)",
        "Godwen gains 92 incursion points.",
        "Incursion [Castle Zvahl Baileys] Seals Broken 1/6",
    ])
    run = s7.snapshot(s7)
    res.check(run["instance"] == "Castle Zvahl Baileys" and int(run["points"]) == 0,
              "unknown message for a new instance did not reset a stale run")

    # A timestamp plugin may prepend '[HH:MM:SS] ' (even twice) to the live
    # message; the ^-anchored patterns must still match.
    s_ts = new_state(lua, State)
    feed(s_ts, parser, [
        "[22:07:45] You have 90 minutes remaining inside this Incursion.",
        "[22:07:45] [22:07:45] Incursion [Fort Ghelsba] Begins! (Normal)",
        "[22:08:01] Incursion [Fort Ghelsba] Phase #1 3/20",
    ])
    run = s_ts.snapshot(s_ts)
    res.check(run is not None and run["instance"] == "Fort Ghelsba"
              and int(run["kills_cur"]) == 3,
              "timestamp-prefixed lines not parsed")

    # Chat that merely mentions Incursion must not be mistaken for content.
    s8 = new_state(lua, State)
    feed(s8, parser, ["Incursion [Castle Zvahl Baileys] Begins! (Mythic)"])
    before = s8.snapshot(s8)["instance"]
    feed(s8, parser, [
        "[2]<Larios> LFM Palborough Mines Incursion 5@",
        "Zsoleara : !incursions",
        "anyone know the best way to skillup from incursion parties?",
        "You store Orcish Steel x38 (Total: 292) Incursion >> Currencies",
        "Godwen obtains a square of Yagudo cloth.",
    ])
    res.check(s8.snapshot(s8)["instance"] == before and s8.note(s8) is None,
              "ordinary chat mentioning Incursion leaked into the window")

    return res


# --------------------------------------------------------------------------
# 5. timers
# --------------------------------------------------------------------------

def test_disconnect(lua, parser, State):
    """
    Disconnect and reconnect, with the party making progress while we are gone.

    The server replays nothing on reconnect, so everything held is a lower
    bound until fresh information arrives. What must never happen is the window
    presenting stale numbers as if they were current.
    """
    res = Result("disconnect: stale progress is not trusted")

    # Partway through phase 3, having watched both earlier bosses die. The two
    # points awards matter: reaching phase 3 implies exactly two cleared
    # phases, so a realistic fixture must already account for them.
    def mid_phase():
        s = new_state(lua, State)
        feed(s, parser, [
            "You have 90 minutes remaining inside this Incursion.",
            "Incursion [Fort Ghelsba] Begins! (Normal)",
            "Godwen gains 84 incursion points.",
            "Godwen gains 149 incursion points.",
            "New Objective: Defeat 15 enemies (Orcish Grunt, Orcish Neckchopper, Orcish Stonechucker)",
            "(Boss: Orcish Sieger at (I-9))",
            "Incursion [Fort Ghelsba] Phase #3 12/15",
        ])
        return s

    # Baseline: in sync, nothing flagged.
    s = mid_phase()
    run = s.snapshot(s)
    res.check(not run["desynced"], "flagged desynced while connected")
    res.check(not run["points_partial"], "flagged partial points while connected")

    # --- Reconnect. The display is now unverified.
    s = mid_phase()
    feed(s, parser, [
        "Incursion [Fort Ghelsba] Recovering session...",
        "You have 41 minutes remaining inside this Incursion.",
    ])
    run = s.snapshot(s)
    res.check(bool(run["desynced"]), "reconnect did not mark the run out of sync")
    res.check(int(run["kills_cur"]) == 12,
              "reconnect discarded progress it could still show")
    res.check(int(s.time_left(s)) == 41 * 60, "reconnect did not resync the timer")

    # --- The party cleared our phase and its boss, then a phase beyond that,
    # while we were gone. First kill back is Phase #5.
    feed(s, parser, ["Incursion [Fort Ghelsba] Phase #5 1/15"])
    run = s.snapshot(s)
    res.check(not run["desynced"], "a live kill count did not clear the desync")
    res.check(int(run["phase"]) == 5 and int(run["kills_cur"]) == 1,
              "progress not corrected from the first kill back")
    res.check(int(run["phases_cleared"]) == 4,
              "phases cleared while disconnected not inferred: %s"
              % run["phases_cleared"])
    res.check(bool(run["points_partial"]),
              "points not flagged as a lower bound after missing boss kills")
    res.check(run["next_boss"] is None,
              "kept the old phase's boss after skipping phases")
    res.check(bool(run["objective"]["stale"]),
              "old phase's mob list not flagged as unconfirmed")

    # The next real objective announcement clears every doubt.
    feed(s, parser, [
        "New Objective: Defeat 15 enemies (Orcish Grunt, Orcish Neckchopper)",
        "(Boss: Orcish Ironlord at (I-8))",
    ])
    run = s.snapshot(s)
    res.check(not run["objective"]["stale"], "stale flag survived a fresh objective")
    res.check(run["next_boss"]["name"] == "Orcish Ironlord", "boss not refreshed")

    # --- Same phase on return: nothing is thrown away or falsely flagged.
    s = mid_phase()
    feed(s, parser, [
        "Incursion [Fort Ghelsba] Recovering session...",
        "Incursion [Fort Ghelsba] Phase #3 13/15",
    ])
    run = s.snapshot(s)
    res.check(not run["desynced"] and not run["points_partial"],
              "a brief drop inside one phase was treated as missed progress")
    res.check(run["next_boss"] is not None and not run["objective"]["stale"],
              "same-phase reconnect discarded good information")

    # --- Back while the boss is up: the kill count is finished, not 12/15.
    s = mid_phase()
    feed(s, parser, [
        "Incursion [Fort Ghelsba] Recovering session...",
        "Godwen gains 192 incursion points.",
    ])
    run = s.snapshot(s)
    res.check(run["objective"] is None,
              "kept showing kill progress after the phase's boss died")
    res.check(int(run["points"]) == 84 + 149 + 192,
              "missed a points award we did see")
    res.check(int(run["phases_cleared"]) == 3, "phases cleared wrong after a boss kill")

    # --- A bonus that lapsed while we were away is dropped, not left at 0:00.
    lua.execute("__clock = 0")
    s = new_state(lua, State)
    feed(s, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
    ])
    res.check(s.bonus(s) is not None, "bonus missing while it is still running")
    lua.execute("__clock = 700")
    res.check(s.bonus(s) is None, "expired bonus still displayed")

    # One that completed before expiring stays, so the result is visible.
    lua.execute("__clock = 0")
    s = new_state(lua, State)
    feed(s, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
        "Incursion [Fort Ghelsba] Bonus Objective Complete!",
    ])
    lua.execute("__clock = 700")
    res.check(s.bonus(s) is not None, "completed bonus dropped once its timer ran out")

    # --- Reload from disk is a disconnect too: time passed unobserved.
    lua.execute("__clock = 0")
    s = mid_phase()
    s2 = new_state(lua, State)
    res.check(bool(s2.restore(s2, s.serialise(s))), "restore rejected a live run")
    res.check(bool(s2.snapshot(s2)["desynced"]),
              "a restored run was presented as in sync")

    lua.execute("__clock = 0")
    return res


def test_timers(lua, parser, State):
    res = Result("timers: countdown, linger, staleness")

    def tick(t):
        lua.execute("__clock = %d" % t)

    tick(0)
    s = new_state(lua, State)
    feed(s, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
    ])

    res.check(int(s.time_left(s)) == 90 * 60, "time_left not seeded from the sync")
    res.check(int(s.bonus_remaining(s)) == 600, "bonus expiry not seeded")

    tick(120)
    res.check(int(s.time_left(s)) == 90 * 60 - 120, "time_left did not count down")
    res.check(int(s.bonus_remaining(s)) == 480, "bonus expiry did not count down")
    res.check(int(s.elapsed(s)) == 120, "elapsed did not advance")

    feed(s, parser, ["You have 79 minutes remaining inside this Incursion."])
    res.check(int(s.time_left(s)) == 79 * 60, "time_left did not snap to a new sync")

    tick(2000)
    res.check(int(s.bonus_remaining(s)) == 0, "bonus expiry went negative")

    # An unrecognised status line ages out rather than sticking forever.
    feed(s, parser, ["Incursion [Fort Ghelsba] The gate grinds open."])
    res.check(s.note(s) == "The gate grinds open.", "note not recorded")
    tick(2000 + 31)
    res.check(s.note(s) is None, "note did not age out")

    tick(3000)
    feed(s, parser, ["Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s"])
    res.check(int(s.elapsed(s)) == 48 * 60 + 44, "elapsed not frozen on completion")
    res.check(bool(s.should_show(s)), "window hidden during the linger window")

    tick(3000 + 31)
    res.check(not s.should_show(s), "window still shown after the linger window")

    # Once the linger has passed, the finished run stops absorbing events.
    feed(s, parser, ["Godwen gains 500 incursion points."])
    res.check(int(s.snapshot(s)["points"]) == 0,
              "a stale finished run absorbed later points")

    feed(s, parser, ["Incursion [Giddeus] Begins! (Normal)"])
    res.check(s.snapshot(s)["instance"] == "Giddeus", "new run did not start")
    res.check(bool(s.should_show(s)), "new run not shown")

    # Restore refuses a snapshot older than the staleness window.
    tick(0)
    s2 = new_state(lua, State)
    feed(s2, parser, ["Incursion [Davoi] Begins! (Normal)"])
    blob = s2.serialise(s2)
    blob["saved_at"] = blob["saved_at"] - (4 * 60 * 60)
    s3 = new_state(lua, State)
    res.check(not s3.restore(s3, blob), "restore accepted a stale snapshot")

    # Back-to-back runs: the second run's entry sync arrives while the first
    # (finished) run still occupies state -- 22:07:45 in the real logs. The
    # new run's clock must still be seeded from it.
    tick(0)
    s4 = new_state(lua, State)
    feed(s4, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s",
    ])
    tick(400)  # past the linger window, like a real between-runs gap
    feed(s4, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Giddeus] Begins! (Normal)",
    ])
    res.check(s4.snapshot(s4)["instance"] == "Giddeus", "second run not started")
    tl = s4.time_left(s4)
    res.check(tl is not None and int(tl) == 90 * 60,
              "second run's clock not seeded from its entry sync: %r" % tl)

    # Same thing *inside* the linger window (instant re-queue).
    tick(0)
    s5 = new_state(lua, State)
    feed(s5, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s",
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Giddeus] Begins! (Normal)",
    ])
    tl = s5.time_left(s5)
    res.check(tl is not None and int(tl) == 90 * 60,
              "instant re-queue lost the entry sync: %r" % tl)

    # A progress message proves a bonus is live even if our locally-estimated
    # expiry has already lapsed (our clock starts at the announcement's
    # *receipt*, so it can lead the server's).
    tick(0)
    s6 = new_state(lua, State)
    feed(s6, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
    ])
    tick(605)
    res.check(s6.bonus(s6) is None, "expired bonus still displayed")
    feed(s6, parser, ["Incursion [Fort Ghelsba] Bonus Objective: Sentry Lizard 4/5"])
    b = s6.bonus(s6)
    res.check(b is not None and int(b["cur"]) == 4,
              "a live progress message did not revive the bonus")

    tick(0)
    return res


# --------------------------------------------------------------------------
# 6. persistence
# --------------------------------------------------------------------------

def test_json_roundtrip(lua, parser, State, libs):
    """
    The addon stores the in-progress run as a JSON string in its settings.
    Round trip a fully populated run through Ashita's own json.lua: this is
    what makes recovery work, and the server never re-announces the objective,
    so a broken round trip would leave the window blank for a whole phase.
    """
    res = Result("persistence: json round trip")

    jsonlib = libs and os.path.join(libs, "json.lua")
    if not jsonlib or not os.path.isfile(jsonlib):
        res.note("skipped: Ashita json.lua not found (set INCURSION_ASHITA_LIBS)")
        return res

    # json.lua leans on T{} from Ashita's common.lua; a passthrough is all it
    # needs here, since we only exercise encode/decode.
    lua.execute("if T == nil then function T(t) return t or {} end end")
    lua.execute("__json = dofile([[%s]])" % jsonlib)
    js = lua.globals().__json

    s = new_state(lua, State)
    feed(s, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Mesmerizer, Orcish Fodder)",
        "(Boss: Orcish Martial at (G-6))",
        "Godwen gains 84 incursion points.",
        "Incursion [Fort Ghelsba] Phase #2 13/20",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
        "Incursion [Fort Ghelsba] Bonus Objective: Sentry Lizard 2/5",
        "Incursion [Fort Ghelsba] Seals Broken 2/6",
        "Godwen gains the effect of Ronin's Revenge (\x81\x98): WS Accuracy+15 / Store TP+8",
    ])

    try:
        encoded = js.encode(s.serialise(s))
    except Exception as exc:                      # noqa: BLE001
        res.check(False, "json.encode raised: %s" % exc)
        return res

    res.check(isinstance(encoded, str) and len(encoded) > 0,
              "encode produced nothing")

    s2 = new_state(lua, State)
    res.check(bool(s2.restore(s2, js.decode(encoded))),
              "restore rejected a round-tripped snapshot")

    a, b = s.snapshot(s), s2.snapshot(s2)
    res.check(b["instance"] == a["instance"], "instance lost")
    res.check(b["difficulty"] == a["difficulty"], "difficulty lost")
    res.check(int(b["phase"]) == 2, "phase lost")
    res.check(int(b["kills_cur"]) == 13 and int(b["kills_max"]) == 20,
              "kill progress lost")
    res.check(int(b["points"]) == 84, "points lost")
    res.check(int(b["phases_cleared"]) == 1, "phases_cleared lost")
    res.check(b["objective"]["kind"] == "kills", "objective lost")
    res.check(len(list(b["objective"]["mobs"].values())) == 3, "mob list lost")
    res.check(b["next_boss"]["name"] == "Orcish Martial", "boss hint lost")
    res.check(b["bonus"]["label"] == "Sentry Lizard"
              and int(b["bonus"]["cur"]) == 2 and int(b["bonus"]["max"]) == 5,
              "bonus lost")
    res.check(int(s2.bonus_remaining(s2)) == int(s.bonus_remaining(s)),
              "bonus expiry lost")
    res.check(int(s2.time_left(s2)) == int(s.time_left(s)), "time left lost")
    res.check(extra_of(s2).get("Seals Broken") == (2, 6, False),
              "unknown counter lost: %r" % extra_of(s2))
    boons = list(b["boons"].values())
    res.check(len(boons) == 1 and boons[0]["name"] == "Ronin's Revenge"
              and boons[0]["stats"] == "WS Accuracy+15 / Store TP+8",
              "boons lost in round trip: %r" % [(x["name"], x["stats"]) for x in boons])

    # A finished run is not resumed -- it would pop a stale 'Complete!' window
    # on the next login for a run that is already over.
    s3 = new_state(lua, State)
    feed(s3, parser, [
        "Incursion [Davoi] Begins! (Normal)",
        "Incursion [Davoi] Complete! (Normal) Time: 30m 0s",
    ])
    s4 = new_state(lua, State)
    res.check(not s4.restore(s4, s3.serialise(s3)),
              "restore resumed a finished run")

    # Garbage is rejected rather than half-applied.
    s5 = new_state(lua, State)
    res.check(not s5.restore(s5, lua.table_from({"version": 99})),
              "restore accepted a bad snapshot")
    res.check(s5.snapshot(s5) is None, "rejected restore left state behind")
    res.check(s5.serialise(s5) is None, "serialise of an empty state is not nil")

    return res


def main():
    logdir = find_logs()
    libs = find_ashita_libs(logdir)
    lua, parser, State = make_lua()

    print("inctrack tests")

    suites = []

    if logdir:
        lines = load_lines(logdir)
        player = player_from_logs(lines)
        print("  chatlogs: %s" % logdir)
        print("  %d chat lines from %d logs, character %s" % (
            len(lines), len(set(l[0] for l in lines)), player))
        suites.extend(test_parser(lines, parser))
        suites.append(test_replay(lines, lua, parser, State, player))
    else:
        print("  chatlogs: none (pass a directory or set INCURSION_CHATLOGS "
              "to replay real runs)")
    print()

    suites.append(test_state_units(lua, parser, State))
    suites.append(test_future_content(lua, parser, State))
    suites.append(test_disconnect(lua, parser, State))
    suites.append(test_timers(lua, parser, State))
    suites.append(test_json_roundtrip(lua, parser, State, libs))

    ok = True
    for s in suites:
        ok &= s.report()

    print()
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
