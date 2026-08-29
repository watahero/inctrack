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

Three assertions were recorded as expected failures with Result.xfail, one per
confirmed defect this milestone exists to fix. An expected failure asserts the
behaviour the addon is *supposed* to have; the defect was why it was false.
All three are fixed and are ordinary checks now:

  * a bonus objective payout counted as a cleared phase   (suite 4, FIX-01)
  * the run clock not aged by the time spent unloaded     (suite 4, FIX-02)
  * the close button the window asks for and then ignores (suite 9, FIX-03)

Every one of them went green with its condition and its message byte-identical
to what Phase 1 wrote: each was deliberately shaped as a delta, a tolerance
window or a disjunction over both legitimate fixes, so that a *correct* fix
satisfies it untouched.

Result.xfail and the two report markers stay. main() guards both the total
against EXPECTED_XFAILS and the set of names against EXPECTED_DEFECTS, and
both are now empty -- so any new expected failure, and any regression that
re-reddens a fixed line, fails the run.
"""

import os
import re
import sys
import glob
import importlib
import traceback

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

# --- reference shapes for the over-reach guard ----------------------------
#
# The guard recomputes each split from the raw line here in Python and compares
# it with what the parser returned. That is the point of it: a reference
# derived from the parser would drift with the parser and agree with it while
# both were wrong. These are derived from the raw text instead.
#
# The three ' at ' bodies: everything between the fixed wording and the fixed
# tail, which is the text the parser must account for in full.
BOSS_OBJ_BODY = re.compile(r"^New Objective: Defeat (.+)!$")
BOSS_HINT_BODY = re.compile(r"^\(Boss: (.+)\)$")
NM_BONUS_BODY = re.compile(
    r"^Bonus Objective: Defeat (.+)! \(Expires in \d+ Minutes?\)$")

# The mob list body. The separator is comma-space; see split_mobs.
KILLS_BODY = re.compile(r"^New Objective: Defeat \d+ enemies \((.+)\)$")

# Mirrors the tightened Lua boon pattern deliberately, piece for piece. Two of
# its pieces are the tightening and are the reason it is written out here
# rather than reused from anywhere: the glyph group is `[^)]+`, a *non-empty*
# run, where the shipped form allowed an empty one; and the name, once
# trimmed, must be non-blank, which the pattern cannot say and the caller
# checks. Everything else is the 1.1.0 shape unchanged.
BOON_REF = re.compile(r"^(\S+) gains the effect of (.*?) \(([^)]+)\): (.+)$")
BOON_PHRASE = " gains the effect of "


# Which Lua sits behind lupa is not the addon's choice and is not stable
# across installs: lupa 2.8 ships lua51..lua55, luajit20 and luajit21, and
# plain LuaRuntime() resolves to whichever was built in. Ashita embeds LuaJIT
# 2.1. Nothing in this harness may depend on that resolution -- the ui suite's
# window snapshots once did, and were green on Lua 5.5 while six of them
# failed on LuaJIT, blaming ui.lua for a formatting choice in the recorder.
# The resolved implementation is printed in the run header so a mismatch is
# visible rather than inferred, and INCTRACK_LUA pins it for anyone checking a
# change against the dialect the addon actually ships against:
#
#     INCTRACK_LUA=luajit21 python test/run_tests.py
def lua_runtime():
    """A fresh Lua runtime: the backend named by INCTRACK_LUA, else lupa's."""
    name = os.environ.get("INCTRACK_LUA")
    if not name:
        return lupa.LuaRuntime()
    try:
        backend = importlib.import_module("lupa." + name)
    except ImportError:
        raise SystemExit(
            "INCTRACK_LUA=%s: this lupa build has no such Lua (it ships "
            "lua51..lua55, luajit20 and luajit21)" % name)
    return backend.LuaRuntime()


def make_lua():
    lua = lua_runtime()
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
        lua = lua_runtime()
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

# The confirmed defects still under test -- and nothing else. None are left.
# All three the milestone was opened to fix are fixed, and their lines are
# ordinary checks now:
#
#   * FIX-01, a bonus objective payout counted as a cleared phase (state)
#   * FIX-02, the run clock not aged by the time spent unloaded   (state)
#   * FIX-03, the close button the window asks for and ignores    (ui)
#
# Zero is the answer from here on, and it is guarded as strictly as three was.
# Any expected failure at all means either a new defect was recorded without
# this number being raised to admit it, or a fixed line went red again.
# main() fails the run either way.
EXPECTED_XFAILS = 0

# The identities behind that count. A count alone cannot tell three defects
# from three *different* defects: one fix landing early plus one regression
# arriving leaves the total at three and the run green, with the whole point
# of the mechanism -- that a green line here is as significant as a red one --
# quietly lost. Each xfail names which defect it stands for and main() compares
# the set, so a swap cannot pass. Empty now, and an empty set is not a slack
# one: main() compares the sorted lists, so any name at all mismatches [].
EXPECTED_DEFECTS = set()


class Result:
    def __init__(self, title):
        self.title = title
        self.checks = 0
        self.failures = []
        self.notes = []
        self.xfails = []
        self.fixed = []
        # The defect ids behind the two lists above, in the same order, for
        # the identity guard in main().
        self.xfail_ids = []
        self.fixed_ids = []

    def check(self, cond, msg):
        self.checks += 1
        if not cond:
            self.failures.append(msg)

    def xfail(self, cond, msg, defect):
        """Assert behaviour the addon is *supposed* to have, knowing a defect
        makes it false today.

        Counts as a check like any other. A false condition is the expected
        failure and lands in `xfails`; a condition that unexpectedly holds
        means the defect is gone and lands in `fixed`, which is loud and, via
        the guard in main(), red -- a defect that stopped reproducing before
        its own fix landed means the red line never got to prove anything.
        The message names the defect in the user's terms, not the code's;
        `defect` is the id main() checks the failure list against, and is
        required so a new expected failure cannot slip in anonymously.
        """
        self.checks += 1
        if cond:
            self.fixed.append(msg)
            self.fixed_ids.append(defect)
        else:
            self.xfails.append(msg)
            self.xfail_ids.append(defect)

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
    # The over-reach guard. The three tightened patterns each narrow what they
    # accept, and the failure mode of a narrowing is silent: a dropped line
    # looks exactly like a quiet stretch of chat. Coverage above catches a line
    # that stopped parsing outright. This catches the subtler half -- a line
    # that still parses but comes back with a name truncated, a location
    # carrying part of a name, a mob list holding names the server never sent,
    # or a boon claimed off an ordinary buff.
    #
    # Every comparison is recomputed from the raw text in Python, never from
    # the parser, so a parser and a harness that drift the same way cannot both
    # be wrong quietly. Suite 2's idiom: one failing check per violation, and a
    # single passing check plus the tallies when there are none.
    #
    # Every message here goes through ascii(): a boon line carries the glyph's
    # raw high bytes, and a report that dies encoding its own failure text on a
    # cp1252 console is a traceback where a readable red line was owed.
    whole = Result("parser: tightened patterns keep every line whole")

    kinds = set()
    generics = {}
    broken = 0
    # Per-family tallies, so a clean run is distinguishable from a run whose
    # corpus simply held none of the shape. A silent zero is what this counts.
    seen = {"at-split": 0, "at-anchor": 0, "mob-list": 0, "boon": 0}

    for path, lineno, line in lines:
        ev = parser.parse(line)

        if MUST_PARSE.match(line):
            coverage.check(ev is not None,
                           "unparsed %s:%d  %r" % (path, lineno, line))

        # Family 4 is the only one that must look at lines the parser
        # declined -- a boon claimed when the tail is absent and a boon missed
        # when it is present are both violations, so the check runs on every
        # line carrying the phrase. The substring test is what keeps the
        # regex off the other three million lines.
        if BOON_PHRASE in line:
            m = BOON_REF.match(line)
            if m and m.group(2).strip() == "":
                m = None                      # a blank name is not a boon
            claimed = ev is not None and ev["t"] == "boon"
            if m is not None:
                seen["boon"] += 1
            if claimed != (m is not None):
                broken += 1
                whole.check(False,
                            "the window would %s a boon here -- %s:%d  %s"
                            % ("invent" if claimed else "miss",
                               path, lineno, ascii(line)))
            elif claimed and (ev["name"] != m.group(2).strip()
                              or ev["stats"] != m.group(4).strip()):
                broken += 1
                whole.check(False,
                            "the boon row would read %s / %s where the line "
                            "says %s / %s -- %s:%d"
                            % (ascii(ev["name"]), ascii(ev["stats"]),
                               ascii(m.group(2).strip()),
                               ascii(m.group(4).strip()), path, lineno))

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
            continue

        kind = ev["t"]

        # Families 1 and 2: the ' at ' split, at each of its three sites.
        # Judged only where the parser actually returned that kind, so a bonus
        # the count form legitimately claimed is never held to the named-NM
        # rule and reported as a fault that is not one.
        body_re = None
        if kind == "objective_boss":
            body_re = BOSS_OBJ_BODY
        elif kind == "boss_hint":
            body_re = BOSS_HINT_BODY
        elif kind == "bonus_new" and ev["kind"] == "nm":
            body_re = NM_BONUS_BODY

        if body_re is not None:
            m = body_re.match(line)
            if m is not None:
                body = m.group(1)
                name = ev["label"] if kind == "bonus_new" else ev["name"]
                loc = ev["loc"]
                seen["at-split"] += 1

                # 1. No text was lost. True under the old split and the new
                #    one alike -- a pure statement about text survival.
                if name is None or loc is None or body != "%s at %s" % (name, loc):
                    broken += 1
                    whole.check(False,
                                "the name and location do not add back up to "
                                "the line: %s + %s vs %s -- %s:%d"
                                % (ascii(name), ascii(loc), ascii(body),
                                   path, lineno))

                # 2. The anchor is the last one. Claimed only where the body
                #    holds a parenthesised group, so new server wording
                #    without coordinates raises no false alarm.
                elif " at (" in body:
                    seen["at-anchor"] += 1
                    if not loc.startswith("("):
                        broken += 1
                        whole.check(False,
                                    "the coordinates the window draws start "
                                    "mid-name: %s -- %s:%d"
                                    % (ascii(loc), path, lineno))
                    elif " at (" in name:
                        broken += 1
                        whole.check(False,
                                    "the split fell before the coordinate "
                                    "group, so the name keeps a location: %s "
                                    "-- %s:%d" % (ascii(name), path, lineno))

        # Family 3: the list is the list, recomputed from the raw body.
        elif kind == "objective_kills":
            m = KILLS_BODY.match(line)
            if m is not None:
                seen["mob-list"] += 1
                want = [p.strip() for p in m.group(1).split(", ") if p.strip()]
                got = list(ev["mobs"].values())
                if got != want:
                    broken += 1
                    whole.check(False,
                                "the window would list mobs the line does not "
                                "name: %s vs %s -- %s:%d"
                                % (ascii(got), ascii(want), path, lineno))

    coverage.note("event kinds: %s" % ", ".join(sorted(kinds)))
    if not generics:
        dormant.check(True, "")
        dormant.note("all real lines handled by a specific pattern")

    if not broken:
        whole.check(True, "")
    whole.note("re-derived from the raw text: %d boss/hint/named-NM splits "
               "(%d of them with a parenthesised group), %d mob lists, "
               "%d boon tails"
               % (seen["at-split"], seen["at-anchor"], seen["mob-list"],
                  seen["boon"]))
    for family, n in sorted(seen.items()):
        if n == 0:
            whole.note("no %s line in this corpus -- that family is unguarded "
                       "by this run, not proven by it" % family)
    return coverage, dormant, whole


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
    # Re-derived from the raw text, never from anything the state machine
    # produced: reaching 'Phase #N' means N-1 phases were cleared, and the
    # completion closes the Nth, so the highest phase number the log shows is
    # the count. A completed run whose log carries no phase line at all is the
    # degenerate case -- the completion is then the only phase boundary, so
    # exactly one phase was cleared.
    want_cleared = max(active["phases"]) if active["phases"] else 1
    res.check(int(run["phases_cleared"]) == want_cleared,
              "%s: phases %d != %d"
              % (tag, int(run["phases_cleared"]), want_cleared))
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
    res.check(int(run["phases_cleared"]) == 0,
              "a points award moved the count of cleared phases on its own")

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

    # --- FIX-01, as an expected failure -----------------------------------

    # Intended behaviour, not current behaviour: only a phase boss dying
    # advances the count of cleared phases. Measured as deltas rather than as
    # one absolute number, so any single-author scheme Phase 2 chooses
    # satisfies it without this assertion being edited.

    def phases_cleared(state, when, absent):
        """The count the window would show, with a vanished run reported
        rather than raised.

        Result.check accumulates rather than aborting -- that is its contract.
        But `int(state.snapshot(state)["phases_cleared"])` raises if the
        snapshot is nil, and a raise here takes the whole run down before any
        suite reports or the known-defect guard runs: a named state regression
        would surface as an unhandled traceback instead of a named failure.
        `absent` is chosen at each call site so the assertion that follows
        still fails rather than accidentally passing on a sentinel.
        """
        snap = state.snapshot(state)
        res.check(snap is not None,
                  "the run had vanished from the window %s" % when)
        return int(snap["phases_cleared"]) if snap is not None else absent

    f1 = new_state(lua, State)
    feed(f1, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Fodder)",
        # Phase #1 deliberately: reaching phase N means N-1 were cleared, so a
        # Phase #2 fixture here would legitimately read 1 and turn the opening
        # check red against a correct implementation.
        "Incursion [Fort Ghelsba] Phase #1 7/20",
    ])
    at_start = phases_cleared(f1, "on its first phase message", absent=-1)
    res.check(at_start == 0,
              "the first phase of a run was reported as one already cleared: "
              "%d" % at_start)

    feed(f1, parser, [
        "Godwen gains 84 incursion points.",
        "Incursion [Fort Ghelsba] Phase #2 0/20",
    ])
    after_boss = phases_cleared(f1, "once the phase boss had died",
                                absent=at_start)
    res.check(after_boss - at_start == 1,
              "killing the phase boss did not move the count of cleared "
              "phases by exactly one (%d -> %d)" % (at_start, after_boss))

    # A bonus objective pays out too, and no phase message follows it.
    feed(f1, parser, [
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
        "Incursion [Fort Ghelsba] Bonus Objective Complete!",
        "Godwen gains 30 incursion points.",
    ])
    after_bonus = phases_cleared(f1, "once the bonus objective had paid out",
                                 absent=after_boss + 1)

    res.check(after_bonus - after_boss == 0,
              "counted a bonus objective payout as a cleared phase -- the "
              "window went from %d cleared to %d without a phase boss dying"
              % (after_boss, after_bonus))

    # Both awards must still add up, so a fix that simply drops the second one
    # is caught rather than mistaken for the real thing.
    snap = f1.snapshot(f1)
    points = int(snap["points"]) if snap is not None else -1
    res.check(points == 84 + 30,
              "a points award went missing: %d instead of %d"
              % (points, 84 + 30))

    # The same rule read three more ways, on shapes the log replay cannot
    # produce on demand: a run watched from Begins! to Complete!, a payout
    # with no phase behind it at all, and a run joined after three phases had
    # already gone by.

    f1a = new_state(lua, State)
    feed(f1a, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Incursion [Fort Ghelsba] Phase #1 0/20",
        "Godwen gains 84 incursion points.",
        "Incursion [Fort Ghelsba] Phase #2 0/20",
        "Godwen gains 91 incursion points.",
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 12m 30s",
    ])
    run = f1a.snapshot(f1a)
    res.check(int(run["phases_cleared"]) == 2,
              "a two-phase run watched from Begins! to Complete! ended on %s "
              "cleared phases -- the completion closes the final phase, whose "
              "boss kill never produces a phase line of its own"
              % run["phases_cleared"])
    res.check(not run["points_partial"],
              "a run watched from end to end was flagged as having missed "
              "points awards")

    f1b = new_state(lua, State)
    feed(f1b, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Godwen gains 30 incursion points.",
    ])
    res.check(int(f1b.snapshot(f1b)["phases_cleared"]) == 0,
              "a payout with no phase boundary behind it was counted as a "
              "cleared phase: %s" % f1b.snapshot(f1b)["phases_cleared"])

    f1c = new_state(lua, State)
    feed(f1c, parser, [
        "Incursion [Fort Ghelsba] Phase #4 3/15",
    ])
    run = f1c.snapshot(f1c)
    res.check(int(run["phases_cleared"]) == 3,
              "joining on phase 4 did not infer the three phases already "
              "cleared: %s" % run["phases_cleared"])
    res.check(bool(run["points_partial"]),
              "joining on phase 4 having watched no award left the points "
              "total unmarked, though three bosses paid out unseen")

    # WR-01: the addon is loaded during the final phase of a run and the very
    # first line it sees is the completion, which bootstraps the run itself.
    # There is no phase behind that we ever saw, so there is no cleared count
    # to state -- and unlike every other lower-bound case, nothing marks it:
    # ui.lua drops the 'reconnected - awaiting update' banner once the run is
    # finished. A fabricated 'Phases cleared 1' on a five-phase run would be
    # read as fact.
    f1d = new_state(lua, State)
    feed(f1d, parser, [
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s",
    ])
    run = f1d.snapshot(f1d)
    res.check(int(run["phases_cleared"]) == 0,
              "a run joined at its completion, with no phase line ever seen, "
              "claimed %s cleared phases -- a number the addon has no "
              "evidence for and no banner left to qualify it with"
              % run["phases_cleared"])
    res.check(bool(run["recovered"]),
              "a run bootstrapped by its own completion was not marked as "
              "recovered, so the count above reads as a watched total")

    # The counterpart, so the fix above is not just 'never count anything':
    # a run watched from Begins! has cleared its first phase by the time it
    # completes, whether or not a phase line ever reached us.
    f1e = new_state(lua, State)
    feed(f1e, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 9m 02s",
    ])
    res.check(int(f1e.snapshot(f1e)["phases_cleared"]) == 1,
              "a run watched from Begins! to Complete! reported %s cleared "
              "phases -- the phase it was in when it finished is cleared"
              % f1e.snapshot(f1e)["phases_cleared"])

    # Idempotence, now that the count is assigned rather than incremented: the
    # server can repeat a completion inside the 30-second linger window, and
    # the second one must not move the count.
    f1f = new_state(lua, State)
    feed(f1f, parser, [
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Incursion [Fort Ghelsba] Phase #1 0/20",
        "Incursion [Fort Ghelsba] Phase #2 0/20",
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 12m 30s",
        "Incursion [Fort Ghelsba] Complete! (Normal) Time: 12m 30s",
    ])
    res.check(int(f1f.snapshot(f1f)["phases_cleared"]) == 2,
              "a repeated completion inside the linger window counted the "
              "final phase twice: %s"
              % f1f.snapshot(f1f)["phases_cleared"])

    # --- FIX-02, as an expected failure -----------------------------------

    # Intended behaviour: time that passed while the addon was unloaded is
    # time the run does not get back. The wall-clock stamp needed to work that
    # out is already written into every save; the restore path never applies
    # it, so a reconnect resumes with a clock that is exactly the reload gap
    # too generous and a bonus objective that has really already lapsed.
    #
    # The injected clock is shared across suites, so it is set explicitly here
    # and returned to zero at the end, the way the timer suites already do.
    lua.globals()["__clock"] = 0
    f2 = new_state(lua, State)
    feed(f2, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Fodder)",
        "Incursion [Fort Ghelsba] Phase #1 5/20",
    ])
    lua.globals()["__clock"] = 120
    feed(f2, parser, [
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 5 Minutes)",
    ])

    saved_left = float(f2.time_left(f2))
    saved_elapsed = float(f2.elapsed(f2))
    blob = f2.serialise(f2)

    # Ten minutes offline, expressed the only way the addon can ever notice
    # it: by moving the wall-clock stamp the save already carries.
    GAP = 600
    blob["saved_at"] = blob["saved_at"] - GAP

    f3 = new_state(lua, State)
    restored = bool(f3.restore(f3, blob))
    res.check(restored,
              "a run saved ten minutes ago was thrown away as too old")

    # Guarded for the same reason as the snapshot reads above: a refusal to
    # restore makes every accessor below return nil, and float(None) raises
    # before this suite can report anything. The stand-ins are chosen so the
    # expected failure below still records a failure -- a state regression is
    # not a fix.
    back_left = float(f3.time_left(f3)) if restored else 0.0
    back_elapsed = float(f3.elapsed(f3)) if restored else 0.0
    back_bonus = f3.bonus(f3) if restored else False

    # Two seconds of tolerance on the clock comparisons: the stamp is real
    # wall time and a second can tick between the save and the restore.
    res.check(abs(back_left - (saved_left - GAP)) <= 2
              and abs(back_elapsed - (saved_elapsed + GAP)) <= 2
              and back_bonus is None,
              "clock was optimistic by the reload gap after a reconnect -- "
              "ten minutes away and the window came back claiming %d seconds "
              "left instead of %d, %d seconds elapsed instead of %d, and a "
              "bonus objective that had already run out"
              % (round(back_left), round(saved_left - GAP),
                 round(back_elapsed), round(saved_elapsed + GAP)))

    # A bonus with time to spare survives the same gap, with its countdown
    # moved down by it -- neither reset to what it was nor dropped.
    lua.globals()["__clock"] = 0
    f4 = new_state(lua, State)
    feed(f4, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 20 Minutes)",
    ])
    blob4 = f4.serialise(f4)
    blob4["saved_at"] = blob4["saved_at"] - GAP

    f5 = new_state(lua, State)
    res.check(bool(f5.restore(f5, blob4)),
              "a run with a live bonus was thrown away as too old")
    kept = f5.bonus(f5)
    res.check(kept is not None,
              "a bonus with ten minutes still to run was dropped on restore")
    kept_left = float(f5.bonus_remaining(f5)) if kept is not None else -1.0
    res.check(abs(kept_left - (20 * 60 - GAP)) <= 2,
              "a surviving bonus countdown was not moved down by the reload "
              "gap: %d seconds left, expected %d"
              % (round(kept_left), 20 * 60 - GAP))
    res.check(bool(f5.snapshot(f5)["desynced"]),
              "ageing the clock cleared the out-of-sync marking -- correcting "
              "the clock restores no knowledge of what the party did while "
              "the addon was gone")

    # A stamp from the future is clock skew or a hand-edited settings file,
    # and it must never be able to add time to the run (T-02-01).
    f6 = new_state(lua, State)
    feed(f6, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
    ])
    lua.globals()["__clock"] = 120
    fwd_left = float(f6.time_left(f6))
    fwd_elapsed = float(f6.elapsed(f6))
    blob6 = f6.serialise(f6)
    blob6["saved_at"] = blob6["saved_at"] + GAP

    f7 = new_state(lua, State)
    res.check(bool(f7.restore(f7, blob6)),
              "a run stamped in the future was thrown away")
    fwd_back_left = float(f7.time_left(f7)) if f7.snapshot(f7) else -1.0
    fwd_back_elapsed = float(f7.elapsed(f7)) if f7.snapshot(f7) else -1.0
    res.check(abs(fwd_back_left - fwd_left) <= 2
              and abs(fwd_back_elapsed - fwd_elapsed) <= 2,
              "a save stamped ten minutes in the future moved the clock: %d "
              "seconds left and %d elapsed, expected %d and %d"
              % (round(fwd_back_left), round(fwd_back_elapsed),
                 round(fwd_left), round(fwd_elapsed)))

    # --- HARD-05: a session of the wrong shape is discarded whole ----------

    # restore() checks the version, the instance, whether the run finished and
    # how old it is -- and then trusts the rest structurally. Well-formed JSON
    # of the wrong shape therefore reaches arithmetic: in ui.lua one frame
    # later, and since Phase 2 inside restore() itself, which runs outside any
    # protected call at both of its call sites (review finding IN-01).
    #
    # Every case below is a real serialise() output with exactly *one* field
    # broken, so a rejection can never be attributed to the wrong cause. Every
    # case asserts the same three things together: the call returned falsy, no
    # run was left behind, and nothing was raised.

    lua.globals()["__clock"] = 0

    SHAPE_FIXTURE = [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
        "New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Mesmerizer, Orcish Fodder)",
        "(Boss: Orcish Martial at (G-6))",
        "Godwen gains 84 incursion points.",
        "Incursion [Fort Ghelsba] Phase #2 13/20",
        "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)",
        "Incursion [Fort Ghelsba] Bonus Objective: Sentry Lizard 2/5",
        "Incursion [Fort Ghelsba] Seals Broken 2/6",
        "Godwen gains the effect of Ronin's Revenge (X): WS Accuracy+15",
        "Godwen gains the effect of Second Wind (X): Regen+3",
    ]

    def shape_blob():
        """A fully populated, well-formed serialise() output.

        Rebuilt from a fresh state on every call: serialise() hands out the
        live run's own objective and next_boss tables, so breaking a field of
        one blob would otherwise break the fixture for every case after it --
        and this whole block rests on each case differing from a known-good
        blob in exactly one place.
        """
        src = new_state(lua, State)
        feed(src, parser, SHAPE_FIXTURE)
        return src.serialise(src)

    def broken(path, value):
        """That blob with one field, named by a dotted path, replaced."""
        blob = shape_blob()
        target = blob
        steps = path.split(".")
        for step in steps[:-1]:
            target = target[int(step) if step.isdigit() else step]
        leaf = steps[-1]
        target[int(leaf) if leaf.isdigit() else leaf] = value
        return blob

    def rejects(path, value, what):
        s = new_state(lua, State)
        blob = broken(path, value)
        raised = None
        accepted = True
        try:
            accepted = bool(s.restore(s, blob))
        except Exception as exc:                    # noqa: BLE001
            raised = exc
        left = s.snapshot(s)
        if raised is not None:
            why = ("restore() raised instead (%s) -- in game that escapes "
                   "into an Ashita event handler, which has no protected call "
                   "around it, and the settings save that would have cleared "
                   "the unusable blob never happens" % raised)
        elif accepted:
            why = "it was accepted and the window drew a run built from it"
        elif left is not None:
            why = "it was refused and a half-applied run was left behind"
        else:
            why = ""
        res.check(raised is None and not accepted and left is None,
                  "a saved session whose %s was not discarded: %s"
                  % (what, why))

    # The control first: a validator that rejects everything would pass every
    # case below and cost the player their in-progress run on every reload.
    control = new_state(lua, State)
    res.check(bool(control.restore(control, shape_blob())),
              "a session the addon had just written itself was refused, so a "
              "reload throws away an in-progress run the server will never "
              "re-announce")
    kept = control.snapshot(control)
    res.check(kept is not None
              and kept["objective"]["kind"] == "kills"
              and int(kept["objective"]["count"]) == 20
              and len(list(kept["objective"]["mobs"].values())) == 3
              and kept["next_boss"]["name"] == "Orcish Martial"
              and int(kept["bonus"]["max"]) == 5
              and len(list(kept["boons"].values())) == 2
              and int(kept["points"]) == 84
              and int(kept["phase"]) == 2,
              "a session the addon wrote itself came back with something "
              "missing, so the window would resume a run short of what it "
              "held when it was saved")

    # Every numeric field that reaches arithmetic, one case each.
    rejects("kills_max", "twenty",
            "kill cap is the word 'twenty' rather than a number")
    rejects("objective.count", "twenty",
            "objective count is a string, so the progress bar divides by it")
    rejects("bonus.max", "five",
            "bonus maximum is a string, so the bonus bar divides by it")
    rejects("bonus.remaining", "soon",
            "bonus countdown is a string, so the expiry is computed from it")
    rejects("time_left", "lots",
            "saved time left is a string, which restore() itself subtracts a "
            "wall-clock gap from")
    rejects("elapsed", "ages",
            "elapsed time is a string, which restore() itself subtracts from "
            "the clock")
    rejects("saved_at", "yesterday",
            "save stamp is a string, which restore() itself subtracts from "
            "os.time()")
    rejects("phase", "two", "phase number is a string")
    rejects("points", "84",
            "points total is the numeral 84 written as text -- Lua would "
            "coerce it silently, which is a number the server never sent "
            "displayed with the same confidence as one it did")

    # The two shapes table.concat and the window disagree about.
    rejects("objective.mobs.2", 5,
            "mob list holds a number where a mob's name belongs")
    rejects("objective.mobs.2", lua.table_from({"name": "Orcish Fodder"}),
            "mob list holds a nested table where a mob's name belongs")
    rejects("objective.mobs.tail", "Phantom Mob",
            "mob list is keyed by something other than its own positions, so "
            "a name would ride past a length-based loop unseen")

    # --- WR-01: a hole is not a shorter list -------------------------------
    #
    # Every one of these lists is read back with 'for i = 1, #t', and '#' on a
    # table with a hole is unspecified -- keys {1, 3} answer 1 here. So a list
    # that satisfies "positive integer keys, valid values" can still carry a
    # member the loop never reaches, which is the half-apply the whole-blob
    # rule was written to forbid, arriving by the one route the per-key check
    # cannot see: a hole is the *absence* of a key, so pairs() never visits
    # it.
    #
    # Reachable rather than contrived: '[{...}, null, {...}]' is well-formed
    # JSON, the settings file is one a player can edit by hand, and the
    # persistence suite drives that literal through Ashita's own decoder.
    rejects("objective.mobs.2", None,
            "mob list has a hole where its second mob was, so the window "
            "lists fewer mobs than the blob holds and says nothing about the "
            "ones it dropped")

    holed = shape_blob()
    holed["boons"][3] = lua.table_from({"name": "Third Wind",
                                        "stats": "Regain+1"})
    holed["boons"][2] = None
    s_holed = new_state(lua, State)
    holed_raised = None
    holed_took = True
    try:
        holed_took = bool(s_holed.restore(s_holed, holed))
    except Exception as exc:                        # noqa: BLE001
        holed_raised = exc
    res.check(holed_raised is None and not holed_took
              and s_holed.snapshot(s_holed) is None,
              "a boons list with a hole in it was taken, so the run resumed "
              "holding one of the three boons the player picked with nothing "
              "on screen saying the other two were dropped: %s"
              % (holed_raised if holed_raised is not None
                 else ("accepted" if holed_took
                       else "a run was left behind")))

    # The rule is contiguity, not length: an empty list and a one-entry list
    # are both contiguous and both ordinary. json.lua writes an absent boons
    # list as '[]', so a run one minute old is exactly this shape.
    for size, what in ((0, "no boons yet"), (1, "one boon")):
        thinned = shape_blob()
        for i in (2, 1):
            if i > size:
                thinned["boons"][i] = None
        s_thin = new_state(lua, State)
        res.check(bool(s_thin.restore(s_thin, thinned)),
                  "a saved run with %s was refused as though its boons list "
                  "were malformed" % what)
        kept_boons = s_thin.snapshot(s_thin)
        res.check(kept_boons is not None
                  and len(list(kept_boons["boons"].values())) == size,
                  "a saved run with %s came back with a different number of "
                  "boons" % what)
    # A non-table where a sub-table belongs.
    rejects("objective", "Defeat 20 enemies", "objective is a bare string")
    rejects("next_boss", 7, "boss preview is a number")
    rejects("bonus", "Sentry Lizard 2/5", "bonus is a bare string")
    rejects("boons", "Ronin's Revenge", "boons list is a bare string")
    rejects("extra", 6, "extras map is a number")

    # A malformed member of a list fails the whole blob rather than being
    # skipped. Skipping is a half-apply by definition: the player comes back
    # to a run showing one of the two boons they picked, with nothing on
    # screen saying the other was dropped.
    rejects("boons.2.name", None,
            "second boon carries no name, which used to be silently skipped "
            "so the run came back holding one of the two boons picked")
    rejects("boons.2", 5, "boons list holds a number where a boon belongs")
    rejects("boons.1.stats", 15, "boon's stats line is a number")

    # Shapes, not contents. The objective's kind is checked for being a
    # string and never against a list of known kinds: a kind the server adds
    # later must survive.
    rejects("objective.kind", 3, "objective kind is a number")
    rejects("extra.Seals Broken", "2/6",
            "extras entry is a string rather than a counter")
    rejects("difficulty", 5, "difficulty is a number")
    rejects("points_partial", "yes",
            "points lower-bound marking is a string rather than a flag")
    # --- CR-01: a blank string is the right shape carrying nothing ---------
    #
    # These three fields were once required to be *non-empty*, and failing
    # that failed the whole blob. The rule was the wrong size for the harm:
    # a blank draws nothing on screen, while the refusal costs the run's
    # boons, points, phase and elapsed, none of which the server ever sends
    # again. It was also self-inflicted -- the addon's own writers produce
    # every one of these -- so a single degenerate server line turned every
    # later reload of that run into total loss.

    def accepts_blank(path, value, what):
        """A blob differing from the known-good one only by a blank string.

        Asserts three things together: it was taken, a run was left behind,
        and that run still holds everything the fixture put in it. Accepting
        the blob but dropping what came with it would be the half-apply the
        whole-blob rule forbids, in the other direction.
        """
        s = new_state(lua, State)
        blob = broken(path, value)
        raised = None
        took = False
        try:
            took = bool(s.restore(s, blob))
        except Exception as exc:                    # noqa: BLE001
            raised = exc
        run = s.snapshot(s)
        res.check(raised is None and took and run is not None,
                  "a saved session %s was thrown away whole, so the reload "
                  "cost the player the boons, points and phase of a live run "
                  "over a field that draws nothing: %s"
                  % (what, raised if raised is not None
                     else ("refused" if not took else "no run was left")))
        res.check(run is not None
                  and int(run["points"]) == 84
                  and int(run["phase"]) == 2
                  and int(run["kills_max"]) == 20
                  and len(list(run["boons"].values())) == 2
                  and run["bonus"] is not None
                  and run["objective"] is not None,
                  "a saved session %s came back short of what it held when it "
                  "was written" % what)
        return run

    kept = accepts_blank(
        "next_boss.name", "",
        "whose boss preview had a blank name -- which is what the parser "
        "writes for '(Boss:  at (J-9))'")
    res.check(kept is not None and kept["next_boss"] is not None
              and kept["next_boss"]["name"] == ""
              and kept["next_boss"]["loc"] == "(G-6)",
              "the blank name took the boss preview's location with it, so "
              "the one thing that line did say was dropped too: %r"
              % (dict(kept["next_boss"]) if kept is not None
                 and kept["next_boss"] is not None else None,))

    kept = accepts_blank(
        "instance", "",
        "whose instance name was blank -- which is what the parser writes "
        "for 'Incursion [] Begins!'")
    res.check(kept is not None and kept["instance"] == "",
              "a blank instance name was coerced into something the server "
              "never sent: %r" % (kept["instance"] if kept is not None
                                  else None,))

    kept = accepts_blank(
        "objective.mobs.2", "",
        "whose mob list held a blank name -- which 1.1.0's list split wrote "
        "for any list carrying an empty piece")
    res.check(kept is not None and kept["objective"]["mobs"] is not None
              and len(list(kept["objective"]["mobs"].values())) == 3,
              "the blank entry took the other two mobs with it: %r"
              % (list(kept["objective"]["mobs"].values())
                 if kept is not None else None,))

    # The same thing end to end, driven by server text rather than by
    # reaching into a blob: the parser writes the blank, serialise() saves
    # it, and the reload must bring the run back.
    blanked = new_state(lua, State)
    feed(blanked, parser, SHAPE_FIXTURE + ["(Boss:  at (J-9))"])
    written = blanked.serialise(blanked)
    res.check(written["next_boss"]["name"] == "",
              "the fixture no longer writes a blank boss name, so the case "
              "below proves nothing: %r" % (written["next_boss"]["name"],))
    reloaded = new_state(lua, State)
    reload_raised = None
    reload_took = False
    try:
        reload_took = bool(reloaded.restore(reloaded, written))
    except Exception as exc:                        # noqa: BLE001
        reload_raised = exc
    back = reloaded.snapshot(reloaded)
    res.check(reload_raised is None and reload_took and back is not None,
              "a run the addon had just written itself was refused on reload "
              "because one server line named no boss: %s"
              % (reload_raised if reload_raised is not None else "refused"))
    res.check(back is not None
              and int(back["points"]) == 84
              and len(list(back["boons"].values())) == 2
              and int(back["phase"]) == 2,
              "the run came back without the boons and points a blank boss "
              "name had nothing to do with")

    # And with a blank instance, which is the other line the parser writes.
    nameless_inst = new_state(lua, State)
    feed(nameless_inst, parser, [
        "Incursion [] Begins! (Normal)",
        "Godwen gains 84 incursion points.",
        "Godwen gains the effect of Ronin's Revenge (X): WS Accuracy+15",
    ])
    inst_blob = nameless_inst.serialise(nameless_inst)
    res.check(inst_blob["instance"] == "",
              "the fixture no longer writes a blank instance, so the case "
              "below proves nothing: %r" % (inst_blob["instance"],))
    inst_back = new_state(lua, State)
    res.check(bool(inst_back.restore(inst_back, inst_blob))
              and inst_back.snapshot(inst_back) is not None
              and int(inst_back.snapshot(inst_back)["points"]) == 84,
              "a run whose 'Begins!' line named no instance was thrown away "
              "on reload, taking its points and boons with it")


    # A rejection leaves the run the player is actually in alone. It is
    # neither replaced by a half-built one nor cleared.
    live = new_state(lua, State)
    feed(live, parser, SHAPE_FIXTURE)
    live_phase = int(live.snapshot(live)["phase"])
    live_points = int(live.snapshot(live)["points"])
    live_raised = None
    live_took = True
    try:
        live_took = bool(live.restore(live, broken("kills_max", "twenty")))
    except Exception as exc:                        # noqa: BLE001
        live_raised = exc
    res.check(live_raised is None and not live_took,
              "a malformed session was applied over a run in progress: %s"
              % (live_raised if live_raised is not None else "accepted",))
    after = live.snapshot(live)
    res.check(after is not None
              and int(after["phase"]) == live_phase
              and int(after["points"]) == live_points
              and after["next_boss"] is not None,
              "a rejected session took the run the player was standing in "
              "with it -- the window went blank on a live Incursion")

    # The objective and the boss preview are copies, not references into the
    # decoded blob. A table the addon does not own can be changed under it.
    src = new_state(lua, State)
    feed(src, parser, SHAPE_FIXTURE)
    shared = src.serialise(src)
    copyist = new_state(lua, State)
    res.check(bool(copyist.restore(copyist, shared)),
              "the copy fixture was refused, so nothing below is exercised")
    shared["objective"]["count"] = 999
    shared["objective"]["mobs"][1] = "Not A Mob"
    shared["next_boss"]["name"] = "Not The Boss"
    copied = copyist.snapshot(copyist)
    res.check(copied is not None and int(copied["objective"]["count"]) == 20,
              "the restored objective is the decoded blob's own table: a "
              "change to the blob moved the count on screen to %s"
              % (copied["objective"]["count"] if copied else "nothing",))
    res.check(copied is not None
              and copied["objective"]["mobs"][1] == "Orcish Grappler",
              "the restored mob list is the decoded blob's own table: a "
              "change to the blob renamed a mob on screen")
    res.check(copied is not None
              and copied["next_boss"]["name"] == "Orcish Martial",
              "the restored boss preview is the decoded blob's own table: a "
              "change to the blob renamed the boss on screen")

    lua.globals()["__clock"] = 0

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

    # ---- the tightened patterns: what they must get right, and what they
    # ---- must now decline ------------------------------------------------
    #
    # Three patterns admit or mangle shapes the server has not yet sent. None
    # has been observed to fail; each is a place where the window would show
    # something the server did not say. The fixtures below are invented
    # content in the server's established wording, as the rest of this suite
    # is. The failure messages say what the player would see, because that is
    # what is at stake -- a truncated boss name with its tail folded into the
    # coordinates, mobs that do not exist, a buff row masquerading as a boon.
    #
    # The corresponding "and nothing real stopped parsing" guarantee is not
    # here: it is the parser suites over the 127-log corpus, which pin the
    # structural parse count and keep the generic tier silent.

    def ev(line):
        return parser.parse(line)

    # -- HARD-02: the split anchors on the last ' at ' before the coordinate
    # -- group, so a name carrying that substring survives whole.

    AT_NAME = "Warden at the Ninth Gate"
    AT_LOC = "(K-7) (Map #4)"

    e = ev("New Objective: Defeat %s at %s!" % (AT_NAME, AT_LOC))
    res.check(e is not None and e["t"] == "objective_boss"
              and e["name"] == AT_NAME,
              "a boss whose own name contains ' at ' was shown truncated: %r"
              % (e and e["name"]))
    res.check(e is not None and e["loc"] == AT_LOC,
              "part of the boss's name was folded into its coordinates: %r"
              % (e and e["loc"]))

    e = ev("(Boss: %s at %s)" % (AT_NAME, AT_LOC))
    res.check(e is not None and e["t"] == "boss_hint" and e["name"] == AT_NAME,
              "the boss waiting at the end of the phase was named wrong: %r"
              % (e and e["name"]))
    res.check(e is not None and e["loc"] == AT_LOC,
              "the boss hint's coordinates carried part of its name: %r"
              % (e and e["loc"]))

    e = ev("Bonus Objective: Defeat %s at %s! (Expires in 10 Minutes)"
           % (AT_NAME, AT_LOC))
    res.check(e is not None and e["t"] == "bonus_new" and e["kind"] == "nm"
              and e["label"] == AT_NAME,
              "the bonus NM was shown under a truncated name: %r"
              % (e and e["label"]))
    res.check(e is not None and e["loc"] == AT_LOC,
              "the bonus NM's coordinates carried part of its name: %r"
              % (e and e["loc"]))

    # The fallback still answers: trailing text that is not a parenthesised
    # coordinate group parses exactly as it does today. Nothing that reaches
    # the window now stops reaching it.
    e = ev("New Objective: Defeat Gate Sentry at the northern span!")
    res.check(e is not None and e["t"] == "objective_boss"
              and e["name"] == "Gate Sentry",
              "a boss objective with no coordinates vanished from the window "
              "entirely: %r" % (e and e["t"]))
    res.check(e is not None and e["loc"] == "the northern span",
              "a boss objective with no coordinates lost its location: %r"
              % (e and e["loc"]))

    # The ordering contract still holds: the count form claims a bonus whose
    # label happens to carry the substring, and a kill objective is still a
    # kill objective.
    e = ev("Bonus Objective: Defeat 6 Wardens at Rest! (Expires in 10 Minutes)")
    res.check(e is not None and e["t"] == "bonus_new" and e["kind"] == "kills"
              and e["label"] == "Wardens at Rest" and int(e["max"]) == 6,
              "a counted bonus objective was drawn as a single named NM, so "
              "its progress bar would never move: %r"
              % ((e and (e["kind"], e["label"])),))
    e = ev("New Objective: Defeat 12 enemies (Cave Bat, Cave Worm)")
    res.check(e is not None and e["t"] == "objective_kills"
              and int(e["count"]) == 12,
              "a kill objective was read as a boss, losing the kill count: %r"
              % (e and e["t"]))

    # -- HARD-03: the list separator is comma-space, so a name carrying its
    # -- own comma is one mob and not two.

    def mobs(line):
        e = ev(line)
        return None if e is None else list(e["mobs"].values())

    got = mobs("New Objective: Defeat 9 enemies (Kalamainu,Prime, Cave Bat)")
    res.check(got == ["Kalamainu,Prime", "Cave Bat"],
              "a mob whose name contains a comma was split into two mobs "
              "that do not exist: %r" % (got,))
    res.check(got is not None and len(got) == 2,
              "the mob list shows the wrong number of mobs: %r" % (got,))

    got = mobs("New Objective: Defeat 20 enemies (Alpha, Beta, Gamma)")
    res.check(got == ["Alpha", "Beta", "Gamma"],
              "an ordinary comma-space list no longer splits the way it "
              "does today: %r" % (got,))
    got = mobs("New Objective: Defeat 20 enemies (Alpha,  Beta,Gamma, )")
    res.check(got == ["Alpha", "Beta,Gamma"],
              "the mob list picked up an empty or untrimmed entry, which the "
              "window would draw as a blank name: %r" % (got,))

    # -- HARD-04: a boon is a full '(<glyph>): <stats>' tail with a non-empty
    # -- glyph group and a non-blank name. An ordinary buff is not a boon.

    # The same raw high-byte run the state suite's boon fixture uses,
    # written as escapes here so an editor cannot quietly normalise it.
    GLYPH = "\u0081\u0098\u0081\u0098"

    res.check(ev("Godwen gains the effect of Protect.") is None,
              "an ordinary buff was listed among the boons picked this run")
    res.check(ev("Godwen gains the effect of Warding Aura (Signet) Attack+5")
              is None,
              "a parenthesised aside with no ': ' after it was listed as a "
              "boon")
    res.check(ev("Godwen gains the effect of Warding Aura (): Attack+5")
              is None,
              "a line with an empty glyph group was listed as a boon")
    res.check(ev("Godwen gains the effect of  (%s): Attack+5" % GLYPH) is None,
              "a boon with no name was listed, so the window would draw a "
              "blank row")

    e = ev("Godwen gains the effect of Warding Aura (%s): Attack+15 / "
           "Defense+8" % GLYPH)
    res.check(e is not None and e["t"] == "boon"
              and e["name"] == "Warding Aura",
              "a real boon stopped reaching the window: %r" % (e,))
    res.check(e is not None and e["stats"] == "Attack+15 / Defense+8",
              "a real boon's stats were mangled: %r" % (e and e["stats"]))
    e = ev("Godwen gains the effect of Vanguard's Ward (%s): VIT+10 / "
           "Damage taken-15%%" % GLYPH)
    res.check(e is not None and e["t"] == "boon"
              and e["stats"] == "VIT+10 / Damage taken-15%",
              "a boon whose stats carry a percent sign was lost or mangled: "
              "%r" % ((e and (e["name"], e["stats"])),))

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
    res.check(int(run["phases_cleared"]) == 2,
              "a points award moved the count of cleared phases -- only the "
              "next phase line does that")

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

    # WR-04. The staleness window is three hours; an Incursion is ninety
    # minutes. So a gap well inside the staleness rule can still be longer
    # than the run had left, and after FIX-02 restore() holds both numbers.
    # Ten minutes remaining, gone for two hours: the run ended without us
    # whether or not we ever saw the completion, and resuming it would put a
    # dead run on screen as a live one -- ~0:00 in red, an elapsed counter
    # past the instance duration, a phase count that will never move -- until
    # the player typed /incursion reset.
    tick(0)
    s3b = new_state(lua, State)
    feed(s3b, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Davoi] Begins! (Normal)",
    ])
    tick(80 * 60)                      # eighty minutes in: ten left
    expired = s3b.serialise(s3b)
    res.check(abs(int(expired["time_left"]) - 10 * 60) <= 1,
              "the fixture did not reach ten minutes remaining: %s"
              % expired["time_left"])
    expired["saved_at"] = expired["saved_at"] - (2 * 60 * 60)
    s3c = new_state(lua, State)
    res.check(not s3c.restore(s3c, expired),
              "restore resumed a run the instance clock proves ended during "
              "the gap -- two hours away with ten minutes left")
    res.check(s3c.snapshot(s3c) is None,
              "a refused restore left a half-applied run behind")

    # The other side of the rule: a gap the run could have survived is still
    # resumed, so this is a proof about the timer and not a second staleness
    # window. Ninety seconds away with ten minutes left, plus the minute of
    # slack the whole-minute server reports need.
    tick(0)
    s3d = new_state(lua, State)
    feed(s3d, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Davoi] Begins! (Normal)",
    ])
    tick(80 * 60)
    survives = s3d.serialise(s3d)
    survives["saved_at"] = survives["saved_at"] - 90
    s3e = new_state(lua, State)
    res.check(bool(s3e.restore(s3e, survives)),
              "restore threw away a run with minutes left on its clock after "
              "a ninety-second gap")

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

    # --- HARD-06: a held timer sync does not survive a reset ---------------

    # The hold exists to bridge the few seconds between the server's
    # remaining-minutes line and the 'Begins!' that follows it. A reset is the
    # player declaring the run over, and a sync captured before that moment
    # describes an instance they are no longer in. The two cases below are
    # written adjacent on purpose: they are one statement, not two, and the
    # fix is only right if both hold.

    tick(0)
    s7 = new_state(lua, State)
    feed(s7, parser, ["You have 90 minutes remaining inside this Incursion."])
    s7.reset(s7)
    res.check(s7["pending_time"] is None,
              "a reset left the last remaining-minutes line held, so it is "
              "still waiting to seed a run the player has not entered yet")

    feed(s7, parser, ["Incursion [Fort Ghelsba] Begins! (Normal)"])
    res.check(s7.time_left(s7) is None,
              "a run begun straight after a reset came up showing a clock "
              "left over from the run the player had just cleared: %r"
              % (s7.time_left(s7),))
    res.check(s7.snapshot(s7)["time_sync"] is None,
              "a run begun straight after a reset carried the old run's sync "
              "time, so its clock will start counting down from a number the "
              "server never gave it")

    # The pin in the other direction. Without the reset the very same
    # sequence must still adopt the sync -- that is what the hold is for, and
    # a fix that took it away would leave every run's clock blank for the
    # first ten minutes.
    tick(0)
    s8 = new_state(lua, State)
    feed(s8, parser, [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [Fort Ghelsba] Begins! (Normal)",
    ])
    kept_sync = s8.time_left(s8)
    res.check(kept_sync is not None and int(kept_sync) == 90 * 60,
              "the entry sync stopped seeding a new run's clock, so the "
              "window says nothing about time left until the first phase "
              "boundary ten minutes in: %r" % (kept_sync,))

    # The thirty-second staleness guard at 'begin' is a different rule -- how
    # old a sync may be, not whether the player threw the run away -- and it
    # is untouched, with and without a reset.
    tick(0)
    s9 = new_state(lua, State)
    feed(s9, parser, ["You have 90 minutes remaining inside this Incursion."])
    tick(31)
    feed(s9, parser, ["Incursion [Fort Ghelsba] Begins! (Normal)"])
    res.check(s9.time_left(s9) is None,
              "a remaining-minutes line from over thirty seconds ago seeded a "
              "new run's clock")

    tick(0)
    s10 = new_state(lua, State)
    feed(s10, parser, ["You have 90 minutes remaining inside this Incursion."])
    tick(31)
    s10.reset(s10)
    feed(s10, parser, ["Incursion [Fort Ghelsba] Begins! (Normal)"])
    res.check(s10.time_left(s10) is None,
              "a stale remaining-minutes line seeded a new run's clock after "
              "a reset")

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
    # awards_seen is the sole input to the points lower-bound marking after
    # FIX-01. If it silently fails to round-trip, a resumed run stops flagging
    # awards it never saw and nothing else in the suite notices.
    res.check(int(b["awards_seen"]) == 1, "awards_seen lost")
    res.check(b["objective"]["kind"] == "kills", "objective lost")
    res.check(len(list(b["objective"]["mobs"].values())) == 3, "mob list lost")
    res.check(b["next_boss"]["name"] == "Orcish Martial", "boss hint lost")
    res.check(b["bonus"]["label"] == "Sentry Lizard"
              and int(b["bonus"]["cur"]) == 2 and int(b["bonus"]["max"]) == 5,
              "bonus lost")
    # One second of tolerance on both: restore subtracts a real wall-clock gap
    # now, and the os.time() second can tick over between the encode and the
    # decode. A one-second move here is the ageing working, not a value lost.
    res.check(abs(int(s2.bonus_remaining(s2)) - int(s.bonus_remaining(s))) <= 1,
              "bonus expiry lost")
    res.check(abs(int(s2.time_left(s2)) - int(s.time_left(s))) <= 1,
              "time left lost")
    res.check(extra_of(s2).get("Seals Broken") == (2, 6, False),
              "unknown counter lost: %r" % extra_of(s2))
    boons = list(b["boons"].values())
    res.check(len(boons) == 1 and boons[0]["name"] == "Ronin's Revenge"
              and boons[0]["stats"] == "WS Accuracy+15 / Store TP+8",
              "boons lost in round trip: %r" % [(x["name"], x["stats"]) for x in boons])

    # --- the stubbed json and the real one must agree ---------------------

    # The addon-shell suite round-trips a saved run through the *stubbed* json
    # in stubs.py, so it is only ever as true as that stub -- and the stub is
    # both more permissive and more opinionated than json.lua: it sorts object
    # keys, emits bytes >= 0x80 raw rather than escaped, encodes an empty
    # table as {} and never [], and accepts a leading '+' on a number. Nothing
    # compared the two. If they disagree, the shell suite is green against a
    # fiction while the shipped addon loses the player's in-progress run on
    # the next reload -- the one failure the persistence code exists to
    # prevent.
    #
    # Compared through the text rather than the table: a Lua table proxy
    # belongs to the runtime that built it, and a JSON string is the only
    # thing that actually travels between the addon and a settings file.
    stub = stubs.AshitaHost(lua_runtime()).json

    stub_read = stub.decode(encoded)
    res.check(stub_read is not None
              and stub_read["instance"] == "Fort Ghelsba"
              and int(stub_read["phase"]) == 2
              and stub_read["bonus"]["label"] == "Sentry Lizard",
              "the harness's json cannot read what Ashita's json writes, so "
              "the addon-shell suite proves nothing about a real save: %r"
              % (encoded,))

    s6 = new_state(lua, State)
    crossed = js.decode(stub.encode(stub_read)) if stub_read is not None else None
    res.check(crossed is not None and bool(s6.restore(s6, crossed)),
              "the harness's json writes a run Ashita's json cannot read back")

    c = s6.snapshot(s6)
    res.check(c is not None
              and c["instance"] == a["instance"]
              and int(c["phase"]) == 2
              and int(c["kills_cur"]) == 13
              and c["next_boss"]["name"] == "Orcish Martial"
              and c["bonus"]["label"] == "Sentry Lizard"
              and int(c["bonus"]["cur"]) == 2,
              "a run written by one json and read by the other came back "
              "different, so the two suites are testing different formats")
    res.check(c is not None
              and extra_of(s6).get("Seals Broken") == (2, 6, False),
              "an unknown counter did not survive the two encoders: %r"
              % (extra_of(s6),))
    crossed_boons = list(c["boons"].values()) if c is not None else []
    res.check(len(crossed_boons) == 1
              and crossed_boons[0]["name"] == boons[0]["name"]
              and crossed_boons[0]["stats"] == boons[0]["stats"],
              "a boon name carrying the server's raw high bytes did not "
              "survive the two encoders: %r"
              % ([(x["name"], x["stats"]) for x in crossed_boons],))

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

    # --- the upgrade path: a session written by shipped 1.1.0 -------------

    # WR-02. FIX-01 split one counter in two: 'phases_cleared' kept its name
    # but changed meaning, and 'awards_seen' took over what it used to hold.
    # A 1.1.0 blob's phases_cleared was incremented by every points award --
    # bonus payouts and chests as well as bosses -- so importing it whole puts
    # the defect straight back on the HUD, and the completion then adds one
    # more. This is a real path: the addon is deployed live, and a player
    # reloading it mid-run has exactly such a blob in their settings.
    #
    # Both branches of the version test are exercised: the legacy migration
    # here, the current schema by the round trip above.
    legacy = js.decode(js.encode(s.serialise(s)))
    legacy["version"] = 1
    legacy["awards_seen"] = None
    legacy["phase"] = 3
    legacy["phases_cleared"] = 5      # authored by five payouts, two phases

    s7 = new_state(lua, State)
    res.check(bool(s7.restore(s7, legacy)),
              "a session written by 1.1.0 was rejected outright, losing an "
              "in-progress run on upgrade")
    g = s7.snapshot(s7)
    res.check(int(g["phases_cleared"]) == 2,
              "a 1.1.0 blob's award-authored count was imported as a cleared "
              "count: the window says %s cleared phases on a run the server "
              "only ever put at phase 3" % g["phases_cleared"])
    res.check(int(g["awards_seen"]) == 0,
              "a 1.1.0 blob's award count was carried over as though it were "
              "trustworthy (%s) -- it is max(awards, phase - 1), so an "
              "over-statement, and over-stating it silences the points "
              "lower-bound marking for the rest of the run" % g["awards_seen"])

    # And the completion must not compound it, which is what took a restored
    # 5 to 6 before WR-01 and WR-02.
    feed(s7, parser, ["Incursion [Fort Ghelsba] Complete! (Normal) Time: 40m 0s"])
    res.check(int(s7.snapshot(s7)["phases_cleared"]) == 3,
              "the completion compounded a restored count instead of closing "
              "the phase the run was on: %s"
              % s7.snapshot(s7)["phases_cleared"])

    # A future schema is refused rather than read with today's field meanings.
    s8 = new_state(lua, State)
    future = js.decode(js.encode(s.serialise(s)))
    future["version"] = 3
    res.check(not s8.restore(s8, future),
              "restore read a blob from a schema it does not know")

    # Garbage is rejected rather than half-applied.
    s5 = new_state(lua, State)
    res.check(not s5.restore(s5, lua.table_from({"version": 99})),
              "restore accepted a bad snapshot")
    res.check(s5.snapshot(s5) is None, "rejected restore left state behind")
    res.check(s5.serialise(s5) is None, "serialise of an empty state is not nil")

    # --- HARD-05, through Ashita's own decoder ----------------------------

    # The structural validator's rules are derived from what serialise()
    # writes, and the only evidence that it accepts everything serialise()
    # writes is a round trip through the decoder the game actually uses. The
    # harness's stub is more permissive; a green run against it alone would
    # not settle this.

    # The thinnest possible run: begun and nothing else. Every optional field
    # -- objective, next boss, bonus, boons, extras, phase, kill cap, clock --
    # is absent, and json.lua's own choices about empty tables are whatever
    # they are. If the validator's absent-or-X arms are wrong anywhere, this
    # is where a real player loses a run they had only just entered.
    thin = new_state(lua, State)
    feed(thin, parser, ["Incursion [Davoi] Begins! (Hard)"])
    thin_back = new_state(lua, State)
    res.check(bool(thin_back.restore(thin_back, js.decode(js.encode(thin.serialise(thin))))),
              "a run the player had only just entered -- no objective, no "
              "boss, no bonus, no boons -- was thrown away on reload")
    thin_run = thin_back.snapshot(thin_back)
    res.check(thin_run is not None
              and thin_run["instance"] == "Davoi"
              and thin_run["difficulty"] == "Hard",
              "a freshly entered run came back without its instance or "
              "difficulty: %r"
              % ((thin_run["instance"], thin_run["difficulty"])
                 if thin_run is not None else None,))

    # And the rejection, through the same decoder: a hand-edited settings
    # file is well-formed JSON of the wrong shape, which is the exact shape
    # the harness's own stub cannot prove anything about.
    bent = js.decode(js.encode(s.serialise(s)))
    bent["objective"]["count"] = "twenty"
    s9 = new_state(lua, State)
    bent_raised = None
    bent_took = True
    try:
        bent_took = bool(s9.restore(s9, bent))
    except Exception as exc:                        # noqa: BLE001
        bent_raised = exc
    res.check(bent_raised is None and not bent_took
              and s9.snapshot(s9) is None,
              "a hand-edited session whose objective count is a string was "
              "not discarded whole: %s"
              % (bent_raised if bent_raised is not None
                 else ("accepted" if bent_took else "a run was left behind")))

    # A malformed member of a list, through the same decoder: whole blob
    # gone, not one boon quietly dropped.
    nameless = js.decode(js.encode(s.serialise(s)))
    nameless["boons"][1]["name"] = None
    s10 = new_state(lua, State)
    nameless_raised = None
    nameless_took = True
    try:
        nameless_took = bool(s10.restore(s10, nameless))
    except Exception as exc:                        # noqa: BLE001
        nameless_raised = exc
    res.check(nameless_raised is None and not nameless_took
              and s10.snapshot(s10) is None,
              "a session holding a boon with no name was half-applied: the "
              "run came back with the nameless boon quietly skipped rather "
              "than the session discarded (%s)"
              % (nameless_raised if nameless_raised is not None
                 else ("accepted" if nameless_took
                       else "a run was left behind")))

    # --- WR-01, through Ashita's own decoder ------------------------------
    #
    # The hole is the one shape the harness's stub cannot settle, because it
    # is json.lua's own answer to a JSON null inside an array that produces
    # it. The literal below is what a hand-edited settings file looks like,
    # and it is what a truncated or patched blob decodes to.
    holed = js.decode('{"version":2,"instance":"Davoi","kills_cur":0,'
                      '"boons":[{"name":"A","stats":"x"},null,'
                      '{"name":"C","stats":"z"}],"extra":{}}')
    holed_keys = sorted(int(k) for k in holed["boons"].keys())
    holed_len = lua.eval("function (t) return #t end")(holed["boons"])
    res.check(holed_keys == [1, 3],
              "json.lua no longer drops a null array element, so the case "
              "below no longer stands for the shape it was written for: %r"
              % (holed_keys,))
    res.check(int(holed_len) < 3,
              "'#' on a table with a hole answered %s here, so this decoder "
              "would not have half-applied the list and the check below "
              "proves less than it claims" % (holed_len,))
    s11 = new_state(lua, State)
    holed_raised = None
    holed_took = True
    try:
        holed_took = bool(s11.restore(s11, holed))
    except Exception as exc:                        # noqa: BLE001
        holed_raised = exc
    res.check(holed_raised is None and not holed_took
              and s11.snapshot(s11) is None,
              "a session whose boons list came back from the decoder with a "
              "hole in it was taken, so the run resumed holding %s of the 3 "
              "boons it names, with nothing on screen saying so (%s)"
              % (holed_len,
                 holed_raised if holed_raised is not None
                 else ("accepted" if holed_took else "a run was left")))

    # The other half of the same rule, and the reason it is contiguity and
    # not length: serialise() always writes 'boons' and 'extra', json.lua
    # encodes an empty table as '[]', and a run one minute old has both. If
    # the rule could not tell an empty list from a holed one, every player
    # who reloaded before picking a boon would lose the run.
    fresh_encoded = js.encode(thin.serialise(thin))
    res.check('"boons":[]' in fresh_encoded and '"extra":[]' in fresh_encoded,
              "json.lua no longer writes an empty table as '[]', so what the "
              "validator is being asked to accept here is not what the addon "
              "actually saves: %r" % (fresh_encoded,))
    fresh_back = new_state(lua, State)
    res.check(bool(fresh_back.restore(fresh_back, js.decode(fresh_encoded))),
              "a run with no boons and no extras yet was refused, so a "
              "player reloading in the first minute of an Incursion loses it")

    return res


# --------------------------------------------------------------------------
# 7. ui: the pure helpers and the layout contracts they hold up
# --------------------------------------------------------------------------

def rgba(color):
    """A Lua colour table as a comparable tuple.

    Every read of a Lua table hands back a fresh proxy, so two handles on the
    same COLOR entry never compare equal with `==`. Compare components.
    """
    return tuple(round(float(color[i]), 4) for i in range(1, 5))


def render_case(lines, clock=0, opts=None):
    """One whole-window render of a hand-built run, as reviewable text.

    lines -- the chat the run is built from, exactly as the game would send it
    clock -- the monotonic clock at render time, so elapsed and the instance
             countdown are the same on every run of the suite
    opts  -- ui.render's options table; visible and unlocked by default

    A fresh host per case is deliberate: ui.lua keeps origin_x and short_cache
    at file scope, so a shared host would let one case's memo cache colour the
    next one's output.

    Returns (snapshot text, what render returned, the ImGui stack balance).
    """
    host = make_host()
    parser = host.require("parser")
    State = host.require("state")
    ui = host.require("ui")
    COLOR = lua_locals(host, ui.render)["COLOR"]

    host.tick(0)
    state = new_state(host.lua, State)
    feed(state, parser, lines)
    host.tick(clock)

    settings = host.lua.table_from(
        {"visible": True, "locked": False} if opts is None else dict(opts))
    host.imgui.reset()
    shown = ui.render(state, settings)
    return (host.imgui.snapshot(colors=COLOR, measurements=False),
            shown, host.imgui.balance())


def expected_window(text):
    """An inline expected window, written at column 0 for reviewability.

    Only the leading and trailing newlines of the literal are dropped -- the
    two-space indent between Begin and End is part of the snapshot.
    """
    return text.strip("\n")


def first_diff(got, want):
    """Where two windows first disagree, as one readable line.

    Compared unstripped: the indentation in a snapshot is the Begin/End
    nesting depth, so a change that alters only the depth -- an extra Begin, a
    missing End, a section drawn one level in -- is a real difference and not
    whitespace. Stripping first reported 'identical' for exactly the failure
    the snapshots most want to catch.
    """
    g, w = got.splitlines(), want.splitlines()
    for i in range(max(len(g), len(w))):
        a = g[i] if i < len(g) else "<end of window>"
        b = w[i] if i < len(w) else "<end of window>"
        if a != b:
            return "line %d drew %r, expected %r" % (i + 1, a, b)
    return "identical apart from trailing whitespace"


# The six expected windows. Inline rather than golden files on disk, so a
# change to any draw function shows up as a readable diff in review. Every
# line of all six was read against the layout mockup in ui.lua's header
# comment (ui.lua:15-26) before being pasted in.

# 1. Mid-phase. The phase bar with its overlay label, the mob line, and the
#    'Next:' line with a right-aligned location.
WINDOW_MID_PHASE = expected_window("""
PushStyleVar 13 [4, 2]
Begin 'inctrack###incursion_window' p_open=nil flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
  Dummy [300, 1]
  TextColored instance 'Crawlers' Nest Depths'
  SameLine
  TextColored dim '. Normal'
  SameLine
  SetCursorPosX 255
  TextColored text '~1:26:00'
  PushStyleColor 40 bar_kills
  ProgressBar 0.80 [-1, 16] 'Phase #3  12/15'
  PopStyleColor 1
  PushTextWrapPos 311
  TextColored dim 'Nest Weevil, Nest Hornet, Nest Beetle'
  PopTextWrapPos
  TextColored dim 'Next: '
  SameLine
  TextColored text 'Nest Matriarch'
  SameLine
  SetCursorPosX 269
  TextColored dim '(H-11)'
  TextColored dim 'Phases cleared '
  SameLine
  TextColored text '2'
  SameLine
  SetCursorPosX 227
  TextColored dim 'Elapsed 4:00'
End
PopStyleVar 1
""")

# 2. Boss up. One full-width orange bar carries the whole message, and the
#    kill line and its mob list are gone.
WINDOW_BOSS_UP = expected_window("""
PushStyleVar 13 [4, 2]
Begin 'inctrack###incursion_window' p_open=nil flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
  Dummy [300, 1]
  TextColored instance 'Crawlers' Nest Depths'
  SameLine
  TextColored dim '. Normal'
  SameLine
  SetCursorPosX 255
  TextColored text '~1:20:00'
  PushStyleColor 40 bar_boss
  ProgressBar 1 [-1, 16] 'BOSS  Nest Matriarch  (H-11)'
  PopStyleColor 1
  TextColored dim 'Phases cleared '
  SameLine
  TextColored text '2'
  SameLine
  SetCursorPosX 220
  TextColored dim 'Elapsed 10:00'
End
PopStyleVar 1
""")

# 3. An active bonus and a counter the parser does not specifically know.
#    The BONUS row with its right-aligned countdown and thin progress strip,
#    the generic counter row, and the boon rows with shortened stats. No
#    objective has been announced, so the objective section says so.
WINDOW_BONUS = expected_window("""
PushStyleVar 13 [4, 2]
Begin 'inctrack###incursion_window' p_open=nil flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
  Dummy [300, 1]
  TextColored instance 'Crawlers' Nest Depths'
  SameLine
  TextColored dim '. Normal'
  SameLine
  SetCursorPosX 276
  TextColored dim '--:--'
  TextColored dim 'Waiting for next objective...'
  TextColored bonus 'BONUS '
  SameLine
  TextColored text 'Gilded Crawler  2/5'
  SameLine
  SetCursorPosX 283
  TextColored text '6:00'
  PushStyleColor 40 bar_bonus
  ProgressBar 0.40 [-1, 5] ''
  PopStyleColor 1
  TextColored dim 'Hives Smoked'
  SameLine
  SetCursorPosX 290
  TextColored text '1/3'
  PushStyleColor 40 bar_extra
  ProgressBar 0.33 [-1, 5] ''
  PopStyleColor 1
  TextColored dim 'Phases cleared '
  SameLine
  TextColored text '0'
  SameLine
  SetCursorPosX 227
  TextColored dim 'Elapsed 4:00'
  TextColored boon 'Warden's Vigil'
  SameLine
  SetCursorPosX 206
  TextColored dim 'WS Acc+15 STP+8'
  TextColored boon 'Hivewarden's Guard'
  SameLine
  SetCursorPosX 220
  TextColored dim 'VIT+10 DT-15%'
End
PopStyleVar 1
""")

# 4. Reconnected, on a phase we did not watch begin. The warning line, the
#    '?' suffix on the phase label, the stale bar colour, the '(?)' on a mob
#    list the server never confirmed for this phase, and no boss preview --
#    the old phase's boss would be a lie.
WINDOW_RECONNECTED = expected_window("""
PushStyleVar 13 [4, 2]
Begin 'inctrack###incursion_window' p_open=nil flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
  Dummy [300, 1]
  TextColored instance 'Crawlers' Nest Depths'
  SameLine
  TextColored dim '. Normal'
  SameLine
  SetCursorPosX 269
  TextColored text '~36:00'
  TextColored warn 'reconnected - awaiting update'
  PushStyleColor 40 bar_stale
  ProgressBar 0.07 [-1, 16] 'Phase #5  1/15 ?'
  PopStyleColor 1
  PushTextWrapPos 311
  TextColored warn 'Nest Weevil, Nest Hornet, Nest Beetle  (?)'
  PopTextWrapPos
  TextColored dim 'Phases cleared '
  SameLine
  TextColored text '4'
  SameLine
  SetCursorPosX 227
  TextColored dim 'Elapsed 5:00'
End
PopStyleVar 1
""")

# 5. Finished, still inside the linger window. 'Complete' and the server's own
#    run time replace the instance clock, and the objective, bonus and extras
#    sections are gone. There is no SetCursorPosX before the value because the
#    instance and difficulty already run past where it would start -- the
#    do-not-overprint branch at ui.lua:96-100.
WINDOW_FINISHED = expected_window("""
PushStyleVar 13 [4, 2]
Begin 'inctrack###incursion_window' p_open=nil flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
  Dummy [300, 1]
  TextColored instance 'Crawlers' Nest Depths'
  SameLine
  TextColored dim '. Normal'
  SameLine
  TextColored good 'Complete 48m 44s'
  TextColored dim 'Phases cleared '
  SameLine
  TextColored text '1'
  SameLine
  SetCursorPosX 220
  TextColored dim 'Elapsed 48:44'
End
PopStyleVar 1
""")

# 6. A percent sign in server-supplied text, in an instance name and in a boon
#    stat string. This asserts the harness records displayed text verbatim and
#    never treats it as a format string (T-01-03). It is a statement about the
#    recorder, not a claim that the real ImGui binding is safe -- that is
#    HARD-01 in Phase 3 and is deliberately not attempted here.
WINDOW_PERCENT = expected_window("""
PushStyleVar 13 [4, 2]
Begin 'inctrack###incursion_window' p_open=nil flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
  Dummy [300, 1]
  TextColored instance 'Vault 50% Sealed'
  SameLine
  TextColored dim '. Normal'
  SameLine
  SetCursorPosX 276
  TextColored dim '--:--'
  TextColored dim 'Waiting for next objective...'
  TextColored dim 'Phases cleared '
  SameLine
  TextColored text '0'
  SameLine
  SetCursorPosX 227
  TextColored dim 'Elapsed 1:00'
  TextColored boon 'Sealbreaker's Gift'
  SameLine
  SetCursorPosX 206
  TextColored dim 'DT-15% Cure+10%'
End
PopStyleVar 1
""")


def test_ui():
    """ui.lua, against the recording ImGui stub.

    Reads no chatlogs and needs no Ashita install (COVR-04): every fixture
    below is written out here.
    """
    res = Result("ui: helpers, layout contract, render")

    host = make_host()
    ui = host.require("ui")
    rec = host.imgui

    # ui.lua exports ui.render and nothing else -- every helper below is a
    # file-scope local -- and this phase adds coverage without editing a byte
    # under inctrack/. Upvalue reflection is therefore the only way to reach
    # them; see lua_locals.
    L = lua_locals(host, ui.render)
    clock_str = L["clock_str"]
    right_text = L["right_text"]
    wrapped = L["wrapped"]
    bar = L["bar"]
    urgency = L["urgency"]
    replace_plain = L["replace_plain"]
    shorten = L["shorten"]
    STAT_SHORT = L["STAT_SHORT"]
    COLOR = L["COLOR"]

    # CONTENT_W and origin_x come from the same walk rather than being copied
    # into the test, because the right-alignment assertions below are stated
    # against origin_x + CONTENT_W and a copy would stop tracking the addon.
    # Read here, before any render call, origin_x is still ui.lua's file
    # default of 8 (ui.lua:67) -- it is only rewritten inside Begin
    # (ui.lua:408). That is correct for the direct-call tests in this section,
    # which never go through render; the snapshot cases further down do go
    # through Begin and see the stub's cursor instead.
    CONTENT_W = float(L["CONTENT_W"])
    origin_x = float(L["origin_x"])
    right_edge = origin_x + CONTENT_W

    def recorded(name):
        """Every recorded call of one entry point, as a list of arg tuples."""
        return [args for n, args in rec.calls if n == name]

    # --- clock_str: the only thing that formats a duration for the window ---

    res.check(clock_str(None) == "--:--",
              "a time the addon does not know yet drew as a real clock "
              "instead of a placeholder: %r" % clock_str(None))

    for seconds, want in [(0, "0:00"), (59, "0:59"), (60, "1:00"),
                          (599, "9:59")]:
        got = clock_str(seconds)
        res.check(got == want,
                  "a countdown of %d seconds read as %r on screen, not %r"
                  % (seconds, got, want))

    for seconds, want in [(3600, "1:00:00"), (3661, "1:01:01"),
                          (5400, "1:30:00")]:
        got = clock_str(seconds)
        res.check(got == want,
                  "an instance with over an hour left read as %r, losing the "
                  "hour" % got)

    res.check(clock_str(90.9) == "1:30",
              "the clock rounded up and showed a second that has not passed "
              "yet: %r" % clock_str(90.9))

    # --- urgency: the colour that makes a nearly-expired timer obvious ---

    for seconds, want, symptom in [
        (None, "dim", "a timer the addon has no value for was coloured as if "
                      "it were a live reading"),
        (301, "text", "a timer with five minutes left was already shouting"),
        (300, "warn", "a timer entering its last five minutes stayed in the "
                      "ordinary colour"),
        (61, "warn", "a timer about to enter its last minute stayed in the "
                     "ordinary colour"),
        (60, "bad", "a timer down to its last minute was not drawn in the "
                    "alarm colour"),
        (0, "bad", "an expired timer was not drawn in the alarm colour"),
    ]:
        res.check(rgba(urgency(seconds, 300, 60)) == rgba(COLOR[want]),
                  "%s (%s seconds)" % (symptom, seconds))

    # --- replace_plain: literal text, not a Lua pattern ---

    res.check(replace_plain("a.b acb", ".", "!") == "a!b acb",
              "a stat phrase containing a dot matched text that merely sits "
              "in the same position: %r"
              % replace_plain("a.b acb", ".", "!"))
    res.check(replace_plain("aXbXc", "X", "-") == "a-b-c",
              "only the first occurrence of a stat phrase was shortened: %r"
              % replace_plain("aXbXc", "X", "-"))

    # --- shorten: boon stats in the shorthand the layout is sized for ---

    res.check(shorten("WS Accuracy+15 / Store TP+8") == "WS Acc+15 STP+8",
              "a boon's stats did not shorten to the abbreviations the boon "
              "row is sized for: %r" % shorten("WS Accuracy+15 / Store TP+8"))
    res.check(shorten("R.Accuracy+10 / Accuracy+20") == "RAcc+10 Acc+20",
              "ranged accuracy was shortened as if it were melee accuracy: %r"
              % shorten("R.Accuracy+10 / Accuracy+20"))
    res.check(shorten("Regen +2 / Refresh +1") == "Regen+2 Refresh+1",
              "a boon stat the shorthand table has never seen was mangled "
              "instead of shown as the server wrote it: %r"
              % shorten("Regen +2 / Refresh +1"))
    once = shorten("Cure Potency+10 / Fast Cast+5")
    res.check(shorten("Cure Potency+10 / Fast Cast+5") == once,
              "the same boon read differently on the second frame it was "
              "drawn: %r then %r"
              % (once, shorten("Cure Potency+10 / Fast Cast+5")))

    # --- bar, right_text and wrapped draw, so read the recorded calls ---

    rec.reset()
    bar(-0.5, COLOR["bar_kills"], L["ARG_BAR_MAIN"], "under")
    under = recorded("ProgressBar")
    res.check(len(under) == 1 and float(under[0][0]) == 0.0,
              "a progress bar drew backwards past its left end: %r"
              % (under and under[0][0],))

    rec.reset()
    bar(1.7, COLOR["bar_kills"], L["ARG_BAR_MAIN"], "over")
    over = recorded("ProgressBar")
    res.check(len(over) == 1 and float(over[0][0]) == 1.0,
              "a progress bar drew past its right end: %r"
              % (over and over[0][0],))
    res.check(len(recorded("PushStyleColor"))
              == sum(int(a[0]) for a in recorded("PopStyleColor")),
              "a bar left a colour pushed on the stack, so everything drawn "
              "after it takes that bar's colour")

    label = "9:59"
    rec.reset()
    width = float(rec.api.CalcTextSize(label))   # the stub's own metric
    rec.reset()
    right_text(label, COLOR["text"])
    moved = recorded("SetCursorPosX")
    res.check(len(moved) == 1
              and abs(float(moved[0][0]) - (right_edge - width)) < 0.001,
              "a right-aligned value did not finish flush with the right edge "
              "of the window: %r, wanted %r"
              % (moved and moved[0][0], right_edge - width))

    # The left side of the line already runs past where the value would start:
    # it must sit after the text rather than printing on top of it
    # (ui.lua:96-100).
    rec.reset()
    rec.api.TextColored(COLOR["text"], "x" * 60)
    right_text(label, COLOR["text"])
    res.check(not recorded("SetCursorPosX"),
              "a long line and its right-aligned value printed on top of one "
              "another")
    res.check(len(recorded("TextColored")) == 2,
              "a right-aligned value was dropped when the line ran long")

    rec.reset()
    wrapped("some overlong mob list", COLOR["dim"])
    wraps = recorded("PushTextWrapPos")
    res.check(len(wraps) == 1
              and abs(float(wraps[0][0]) - right_edge) < 0.001,
              "wrapped text wrapped somewhere other than the window's pinned "
              "content width: %r, wanted %r"
              % (wraps and wraps[0][0], right_edge))
    res.check(len(wraps) == len(recorded("PopTextWrapPos")),
              "wrapped text left the wrap position pushed, so every later "
              "line wrapped too")

    # --- STAT_SHORT's ordering contract (ui.lua:286-292) ---

    # Longer phrases must be listed before their own substrings, or the
    # substring replaces first and the longer phrase can never match whole.
    # This is exactly the table a later edit re-sorts alphabetically.
    phrases = [STAT_SHORT[i][1] for i in range(1, len(STAT_SHORT) + 1)]
    offenders = [(phrases[a], phrases[b])
                 for a in range(len(phrases))
                 for b in range(a + 1, len(phrases))
                 if phrases[a] in phrases[b]]
    res.check(not offenders,
              "boon stats would shorten to the wrong abbreviation: %r is "
              "listed before %r, which contains it, so the longer phrase can "
              "never match whole"
              % (offenders[0] if offenders else ("", "")))

    # --- whole-window snapshots -------------------------------------------

    # Invented content in the server's established wording, so nothing here
    # depends on a chatlog (D-12).
    INSTANCE = "Crawlers' Nest Depths"
    mid_phase = [
        "You have 90 minutes remaining inside this Incursion.",
        "Incursion [%s] Begins! (Normal)" % INSTANCE,
        "Godwen gains 84 incursion points.",
        "Godwen gains 149 incursion points.",
        "New Objective: Defeat 15 enemies "
        "(Nest Weevil, Nest Hornet, Nest Beetle)",
        "(Boss: Nest Matriarch at (H-11))",
        "Incursion [%s] Phase #3 12/15" % INSTANCE,
    ]

    cases = [
        ("mid-phase", mid_phase, 240, WINDOW_MID_PHASE),

        ("boss-up",
         mid_phase + ["New Objective: Defeat Nest Matriarch at (H-11)!"],
         600, WINDOW_BOSS_UP),

        ("active-bonus", [
            "Incursion [%s] Begins! (Normal)" % INSTANCE,
            "Bonus Objective: Defeat 5 Gilded Crawler! (Expires in 10 Minutes)",
            "Incursion [%s] Bonus Objective: Gilded Crawler 2/5" % INSTANCE,
            "Incursion [%s] Hives Smoked 1/3" % INSTANCE,
            "Godwen gains the effect of Warden's Vigil (X): "
            "WS Accuracy+15 / Store TP+8",
            "Godwen gains the effect of Hivewarden's Guard (X): "
            "VIT+10 / Damage taken-15%",
        ], 240, WINDOW_BONUS),

        # Two drops, because one is not enough to show all four staleness
        # markers at once: a phase message flags the old mob list but also
        # clears the desync, since a kill count is live information
        # (state.lua:206-224). The second reconnect is what puts the window
        # into 'these mobs are only probable *and* this count is a lower
        # bound' -- exactly the state the player must not mistake for truth.
        ("reconnected", mid_phase + [
            "Incursion [%s] Recovering session..." % INSTANCE,
            "You have 41 minutes remaining inside this Incursion.",
            "Incursion [%s] Phase #5 1/15" % INSTANCE,
            "Incursion [%s] Recovering session..." % INSTANCE,
        ], 300, WINDOW_RECONNECTED),

        ("finished", [
            "Incursion [%s] Begins! (Normal)" % INSTANCE,
            "Incursion [%s] Complete! (Normal) Time: 48m 44s" % INSTANCE,
        ], 10, WINDOW_FINISHED),

        ("percent-in-server-text", [
            "Incursion [Vault 50% Sealed] Begins! (Normal)",
            "Godwen gains the effect of Sealbreaker's Gift (X): "
            "Damage taken-15% / Cure Potency+10%",
        ], 60, WINDOW_PERCENT),
    ]

    for name, lines, clock, want in cases:
        got, shown, bal = render_case(lines, clock=clock)
        res.check(got == want,
                  "the %s window is not the one the layout contract "
                  "describes: %s" % (name, first_diff(got, want)))
        # Holds whatever the window contains, and Phase 3 leans on it: an
        # unbalanced stack corrupts every frame drawn after this one.
        res.check(bal["window"] == 0 and bal["style_var"] == 0
                  and bal["style_color"] == 0,
                  "the %s window left the ImGui stacks unbalanced: %r"
                  % (name, bal))
        res.check(shown is True,
                  "the %s window hid itself although nobody asked it to"
                  % name)

    # --- the left edge every right-aligned value is measured from ---------

    # ui.lua declares origin_x = 8 at file scope and overwrites it with
    # GetCursorPosX() inside Begin (ui.lua:67 and :408). The stub's padding is
    # deliberately not 8 (stubs.py), so dropping that line is observable:
    # without this check every window above would be byte-identical whether or
    # not the addon ever asks ImGui where the content starts, and a real
    # window whose padding is not 8 would draw every right-aligned value and
    # every wrap position in the wrong place.
    edge_host = make_host()
    edge_parser = edge_host.require("parser")
    EdgeState = edge_host.require("state")
    edge_ui = edge_host.require("ui")
    edge = new_state(edge_host.lua, EdgeState)
    feed(edge, edge_parser, ["Incursion [%s] Begins! (Normal)" % INSTANCE])
    edge_host.imgui.reset()
    edge_ui.render(
        edge, edge_host.lua.table_from({"visible": True, "locked": False}))
    after = float(lua_locals(edge_host, edge_ui.render)["origin_x"])
    res.check(after == edge_host.imgui.padding,
              "the window did not take its left edge from ImGui, so every "
              "right-aligned value and every wrapped line is measured from a "
              "guess: %r, not %r" % (after, edge_host.imgui.padding))

    # Nothing to draw yet: not an empty window, no window at all.
    blank_host = make_host()
    BlankState = blank_host.require("state")
    blank_ui = blank_host.require("ui")
    blank = new_state(blank_host.lua, BlankState)

    for visible in (True, False):
        blank_host.imgui.reset()
        kept = blank_ui.render(
            blank,
            blank_host.lua.table_from({"visible": visible, "locked": False}))
        res.check(not blank_host.imgui.calls,
                  "an empty window appeared with no Incursion in progress")
        res.check(kept is visible,
                  "the window changed its own visibility with no run to show")

    # --- FIX-03, fixed ----------------------------------------------------

    # If the window offers a close control, clicking it closes the window.
    # Written in Phase 1 as a disjunction over what the recorded Begin call
    # shows, so either legitimate fix would turn it green without the
    # assertion being edited -- one where the window stops asking for a close
    # control at all, and one where it starts drawing the bar that would carry
    # it. Phase 2 took the first: the assertion below is unchanged from the
    # day it was written red.
    close_host = make_host()
    close_parser = close_host.require("parser")
    CloseState = close_host.require("state")
    close_ui = close_host.require("ui")

    close_host.tick(0)
    closable = new_state(close_host.lua, CloseState)
    feed(closable, close_parser, [
        "Incursion [%s] Begins! (Normal)" % INSTANCE,
        "Incursion [%s] Phase #1 4/15" % INSTANCE,
    ])

    close_host.imgui.reset()
    close_host.imgui.arm_close()      # the player clicks close, this frame
    still_shown = close_ui.render(
        closable,
        close_host.lua.table_from({"visible": True, "locked": False}))

    begins = [args for name, args in close_host.imgui.calls if name == "Begin"]
    offered_close = any(len(args) > 1 and stubs.lua_type(args[1]) == "table"
                        for args in begins)

    # The disjunction below holds whenever no Begin was recorded at all, so a
    # frame that drew nothing would report the defect as fixed. Assert the
    # precondition separately: the disjunction is only reached once a window
    # is known to exist.
    res.check(bool(begins),
              "the close-button case drew no window at all, so nothing was "
              "proved about the close button either way")

    res.check((not offered_close) or still_shown is False,
              "the window asks for a close button and then ignores it -- "
              "clicking close leaves the window on screen")

    # Pins which branch of that disjunction the fix took. Without this, a
    # later change that reinstated the close box and then hid the window on
    # the click would satisfy the check above through its other term, and the
    # player would be back to a control they can never reach: the window is
    # drawn with no title bar, so there is nowhere for a close box to appear.
    res.check(not offered_close,
              "the window asks for a close control it can never show -- it "
              "is drawn without a title bar, so the player has nothing to "
              "click")

    # --- CR-01: which slot each Begin argument arrived in ------------------

    # Ashita declares Begin exactly once, and positionally:
    #
    #     virtual bool Begin(const char* name, bool* p_open = nullptr,
    #                        ImGuiWindowFlags flags = 0) = 0;
    #     (Ashita/plugins/sdk/imgui.h:305)
    #
    # There is no overload, and addons/libs/imgui.lua adds no Lua wrapper that
    # could reshape the call -- it is a constants table whose __index is
    # AshitaCore:GetGuiManager(), so the call lands on that signature
    # unmediated. Flags handed to slot 2 are therefore not flags: they are a
    # p_open. In game the window would come back with a title bar, resizable,
    # collapsible, stealing focus, no longer fitting its own height and no
    # longer honouring /incursion lock -- or the binding would raise
    # 'bad argument #2' sixty times a second inside d3d_present.
    #
    # A layout snapshot cannot catch that on its own: it compares what was
    # drawn, and this is a fault in how the drawing was *requested*. So the
    # argument positions are pinned here by name, each with the symptom it
    # produces, and the recorder no longer forgives a numeric slot 2.
    shape_host = make_host()
    shape_parser = shape_host.require("parser")
    ShapeState = shape_host.require("state")
    shape_ui = shape_host.require("ui")

    shape = new_state(shape_host.lua, ShapeState)
    feed(shape, shape_parser, mid_phase)
    shape_host.imgui.reset()
    shape_ui.render(
        shape, shape_host.lua.table_from({"visible": True, "locked": True}))

    shape_begins = [args for n, args in shape_host.imgui.calls
                    if n == "Begin"]
    res.check(len(shape_begins) == 1,
              "the frame opened %d windows, so nothing below is a statement "
              "about the one window this addon draws" % len(shape_begins))

    for args in shape_begins:
        res.check(len(args) == 3,
                  "Begin was called with %d arguments -- the host's signature "
                  "is Begin(name, p_open, flags), so a shorter call leaves "
                  "the flags behind entirely" % len(args))

        p_open = args[1] if len(args) > 1 else None
        res.check(not isinstance(p_open, (int, float)),
                  "a number reached Begin's slot 2, which is p_open and not "
                  "flags -- in game every flag ui.render computed would be "
                  "dropped (title bar back, no auto-resize, /incursion lock "
                  "dead) or the binding would raise once per frame")
        res.check(p_open is None,
                  "Begin's slot 2 is %r, not nil -- this window is drawn "
                  "without a title bar, so it must ask for no close control "
                  "at all rather than one it can never show" % (p_open,))

        flags = args[2] if len(args) > 2 else None
        res.check(isinstance(flags, (int, float))
                  and not isinstance(flags, bool),
                  "Begin's slot 3 holds %r rather than a flags number, so the "
                  "window asked for none of the flags ui.render computed"
                  % (flags,))
        got_flags = stubs.window_flags(flags)
        for flag in ("NoTitleBar", "AlwaysAutoResize", "NoFocusOnAppearing",
                     "NoMove"):
            res.check(flag in got_flags,
                      "%s never reached the host: the flags Begin actually "
                      "received are %s" % (flag, "|".join(got_flags) or "none"))

    # No clock to reset at the end of this suite: every case above builds and
    # discards its own host, so nothing it advanced is shared with any other
    # suite -- which is why the eight existing report lines are unaffected.

    return res


# --------------------------------------------------------------------------
# 10. the addon shell: registration, text_in, persistence, profiles
# --------------------------------------------------------------------------

# Invented content in the server's established wording. This suite reads no
# chatlogs and needs no Ashita install (COVR-04): every fixture below is a
# chat line written out here, and nothing in it opens a file.
SHELL_INSTANCE = "Crawlers' Nest Depths"
SHELL_OTHER = "Hivewarden Vaults"
SHELL_BOON = ("%s gains the effect of Warden's Vigil (X): "
              "WS Accuracy+15 / Store TP+8" % PLAYER)

# An instance name holding a percent sign. Server text is quoted through to
# the window verbatim, so a name like this reaches a draw call unescaped --
# the second of the two triggers the phase brief names.
SHELL_PERCENT = "Vault of 100% Ruin"

# A kill objective, so a mob list exists to poison. Invented names in the
# server's established wording, as everything else in this suite is.
SHELL_MOBS = ("New Objective: Defeat 12 enemies "
              "(Nest Skitterer, Nest Broodguard, Nest Drone)")
SHELL_FIRST_MOB = "Nest Skitterer"


def begins(instance=SHELL_INSTANCE):
    return "Incursion [%s] Begins! (Normal)" % instance


def phase_line(n, cur, mx=15, instance=SHELL_INSTANCE):
    return "Incursion [%s] Phase #%d %d/%d" % (instance, n, cur, mx)


def loaded_host(player=PLAYER, profile=None):
    """A host with inctrack.lua required and its load handler fired.

    The addon registers its handlers at require time and does everything else
    -- the banner, the player name, resuming a saved run -- inside the load
    handler, which is exactly how Ashita drives it.
    """
    host = make_host(player=player, profile=profile)
    host.require("inctrack")
    host.tick(0)
    host.fire("load")
    return host


def shell_state(host):
    """The State instance the shell holds. lupa does not bind self, so the
    caller passes the receiver explicitly: state.snapshot(state)."""
    return host.addon["incursion"]["state"]


def shell_run(host):
    state = shell_state(host)
    return state.snapshot(state)


def test_addon_shell():
    """inctrack.lua, against the stubbed Ashita host.

    The shell exports nothing and may not be edited this phase, so its
    file-scope state -- the incursion table, visible(), reset(), persist() --
    is reached through host.addon by upvalue reflection. Assertions are on the
    behaviour that results (what the run holds, what reached chat, how many
    saves happened, what string was written), not on call sequences (D-03).
    """
    res = Result("addon: load, chat, settings, commands")

    # --- every handler the addon needs in game is actually registered ------

    host = make_host()
    host.require("inctrack")

    for event in ("load", "unload", "text_in", "d3d_present", "command"):
        res.check(event in host.events,
                  "the addon never asked the game for the %s event, so that "
                  "whole path is dead once installed" % event)
    res.check(host.profile_callback is not None,
              "nothing listens for a character change, so one character's run "
              "would follow the player onto another")

    # --- the load banner, which is how a player tells this addon apart ----

    version = host.lua.globals()["addon"]["version"]
    host.tick(0)
    host.fire("load")
    banner = [line for line in host.chat if version in line]
    res.check(len(banner) == 1,
              "the banner naming this build reached chat %d times, not once: "
              "%r" % (len(banner), host.chat))
    res.check(bool(banner) and banner[0].startswith("[inctrack] "),
              "the banner does not identify itself as inctrack, so it cannot "
              "be told from another Incursion addon: %r" % banner)

    # --- the pcall boundary at inctrack.lua:160 ---------------------------

    # Forced from outside rather than by editing the addon: a Lua table as the
    # message. The handler's first real act is a string method call on it,
    # which raises for a table. A number would not do -- numbers share the
    # string metatable, so (5):strip_colors() coerces and succeeds, the
    # handler runs to completion, and no parse-error line is ever produced.
    # Every text_in here is fired with the event table Ashita really supplies
    # (stubs.TEXT_IN_FIELDS), because the read-only guarantee is about the
    # fields the host reads back: the player sees `message_modified` if the
    # handler wrote one, not `message`. Asserting on `message` alone would
    # leave a handler that rewrote chat in game entirely undetected.
    bad = loaded_host()
    before = len(bad.chat)
    e = bad.fire_text_in(bad.lua.table_from({"not": "a string"}))
    errors = [line for line in bad.chat[before:] if "parse error" in line]
    res.check(len(errors) == 1,
              "a chat line the addon could not read produced %d complaints "
              "instead of one, or took the chat handler down with it: %r"
              % (len(errors), bad.chat[before:]))
    res.check(stubs.lua_type(e["message"]) == "table",
              "the chat handler rewrote the message it was handed")
    res.check(e["message_modified"] is None and e["mode_modified"] is None
              and e["indent_modified"] is None,
              "the chat handler rewrote the line the player sees, after "
              "failing to read it: %r" % (e["message_modified"],))
    res.check(e["blocked"] is None,
              "the chat handler swallowed a line the player was meant to see")
    res.check(shell_run(bad) is None,
              "a chat line that could not be read still started a run")

    # Read-only on the ordinary path too. This is the guarantee the comment at
    # inctrack.lua:156 makes and that nothing has tested until now.
    ordinary = begins()
    e = bad.fire_text_in(ordinary)
    res.check(e["message"] == ordinary,
              "the chat handler rewrote an ordinary line: %r" % (e["message"],))
    res.check(e["message_modified"] is None and e["mode_modified"] is None
              and e["indent_modified"] is None,
              "the chat handler rewrote the line the player sees: %r"
              % (e["message_modified"],))
    res.check(e["blocked"] is None,
              "the chat handler blocked an ordinary line")

    # --- a line that is none of the addon's business costs nothing --------

    idle = loaded_host()
    saves_before = idle.saves
    chat_before = len(idle.chat)
    idle.fire_text_in("Godwen hits the Nest Weevil for 42 points of damage.")
    res.check(idle.saves == saves_before,
              "an unrelated combat line wrote settings to disk")
    res.check(len(idle.chat) == chat_before,
              "an unrelated combat line put something in the player's chat")
    res.check(shell_run(idle) is None,
              "an unrelated combat line invented a run")

    # --- the MUST_SAVE policy, driven by the injected clock ---------------

    # The only thing standing between a mid-run reload and a blank window for
    # a whole phase. Events the server never repeats are written the moment
    # they land; kill counts arrive constantly and ride a five-second throttle.
    saver = loaded_host()
    res.check(saver.saves == 0,
              "loading with nothing saved still wrote to disk")

    saver.fire_text_in(begins())
    res.check(saver.saves == 1,
              "the start of a run was not written down immediately (%d writes)"
              % saver.saves)

    saver.fire_text_in(phase_line(1, 3))
    res.check(saver.saves == 1,
              "a kill count arriving a moment later forced a second disk "
              "write (%d writes)" % saver.saves)

    saver.tick(6.0)
    saver.fire_text_in(phase_line(1, 3))
    res.check(saver.saves == 2,
              "a kill count past the throttle window was not written down "
              "(%d writes)" % saver.saves)

    saver.fire_text_in(SHELL_BOON)
    res.check(saver.saves == 3,
              "a boon -- which the server never announces again -- was left "
              "unwritten because a kill count had just been saved (%d writes)"
              % saver.saves)

    res.check(saver.sessions[-1] != "",
              "the run was 'saved' as an empty string, so a reload would come "
              "back blank")
    blob = saver.json.decode(saver.sessions[-1])
    res.check(blob is not None and blob["instance"] == SHELL_INSTANCE,
              "what was written down does not name the instance the player is "
              "standing in: %r" % (saver.sessions[-1],))

    # --- unloading mid-run keeps the run ----------------------------------

    before = saver.saves
    saver.fire("unload")
    res.check(saver.saves == before + 1,
              "unloading mid-run did not write the run down")
    res.check(saver.settings["session"] != "",
              "unloading mid-run left nothing to come back to")

    # --- the resume round trip, through the stubbed json both ways --------

    resumed = loaded_host(profile={"session": saver.settings["session"]})
    run = shell_run(resumed)
    res.check(run is not None and run["instance"] == SHELL_INSTANCE,
              "a run in progress did not come back after a reload")
    res.check(run is not None and int(run["phase"]) == 1,
              "the resumed run lost the phase it was on")
    res.check(any(("Resumed run in %s" % SHELL_INSTANCE) in line
                  for line in resumed.chat),
              "the run came back but the player was never told: %r"
              % resumed.chat)

    # A saved run that is not readable is discarded whole rather than
    # half-applied, and the unusable string is cleared so it cannot be retried
    # on every load forever.
    corrupt = loaded_host(profile={"session": "not json at all"})
    res.check(corrupt.settings["session"] == "",
              "an unreadable saved run was kept and will be retried on every "
              "load: %r" % (corrupt.settings["session"],))
    res.check(corrupt.saves == 1,
              "clearing the unreadable saved run was never written to disk "
              "(%d writes)" % corrupt.saves)
    res.check(shell_run(corrupt) is None,
              "an unreadable saved run left a half-built run behind")

    # HARD-05 on the load path. Unreadable is the easy case -- json.decode
    # says no and the pcall around it catches anything it throws. This is the
    # hard one: perfectly well-formed JSON of the wrong shape, which is what a
    # settings file edited by hand or truncated mid-write looks like. Nothing
    # protects the restore() call itself at either of its two call sites, so
    # what the shape costs is decided entirely inside state.lua.
    #
    # A discarded session is an ordinary outcome, not a fault to report at the
    # player: the run is gone either way and there is nothing they can do.
    WRONG_SHAPE = ('{"version":2,"instance":"%s","phase":1,"kills_cur":3,'
                   '"kills_max":15,"time_left":"lots","elapsed":42,'
                   '"boons":[],"extra":{}}' % SHELL_INSTANCE)

    bent = None
    bent_raised = None
    try:
        bent = loaded_host(profile={"session": WRONG_SHAPE})
    except Exception as exc:                        # noqa: BLE001
        bent_raised = exc
    res.check(bent_raised is None,
              "a saved session of the wrong shape took the addon's load "
              "handler down with it -- in game that error escapes into "
              "Ashita, and the settings save that clears the unusable string "
              "never happens, so it fails again on every load: %s"
              % (bent_raised,))
    res.check(bent is not None and shell_run(bent) is None,
              "a saved session of the wrong shape was half-applied into a run")
    res.check(bent is not None and bent.settings["session"] == "",
              "an unusable saved session was kept and will be retried on "
              "every load: %r"
              % (bent.settings["session"] if bent is not None else None,))
    res.check(bent is not None and bent.saves == 1,
              "clearing the unusable saved session was never written to disk "
              "(%s writes)" % (bent.saves if bent is not None else "no",))
    bent_noise = ([line for line in bent.chat
                   if "error" in line.lower() or "Resumed run" in line]
                  if bent is not None else [])
    res.check(bent is not None and not bent_noise,
              "a discarded session was reported at the player as a fault, or "
              "reported as resumed when it was not: %r" % (bent_noise,))

    # --- the player's name, which may not exist yet at load ---------------

    late = loaded_host(player="")
    res.check(shell_state(late)["player"] is None,
              "the addon claimed to know who the player is before the game "
              "could tell it")
    late.set_party_name(PLAYER)
    late.fire_text_in(begins())
    res.check(shell_state(late)["player"] == PLAYER,
              "the player's name was never picked up once it became "
              "available, so their own points would be filtered out forever")

    # Nothing is asserted about the window before the name resolves: accepting
    # anyone's points while the player is unknown is a recorded risk with no
    # requirement behind it either way, and blessing it here would be a
    # promise this milestone has not made.
    late.fire_text_in("Vidikh gains 999 incursion points.")
    late.fire_text_in("%s gains 84 incursion points." % PLAYER)
    run = shell_run(late)
    res.check(run is not None and int(run["points"]) == 84,
              "another player's points were counted as the player's own: %r"
              % (run and int(run["points"]),))

    # --- a character change -----------------------------------------------

    # The run and the name belong to the old character. Keeping either would
    # show one character's Incursion to another, or filter out the new
    # character's own points.
    other = loaded_host(player="Vidikh")
    other.fire_text_in(begins(SHELL_OTHER))
    other.fire_text_in(phase_line(2, 5, 18, SHELL_OTHER))
    other.fire("unload")

    switched = loaded_host()
    switched.fire_text_in(begins())
    switched.addon["incursion"]["override"] = False   # a manual hide
    switched.addon["incursion"]["render_off"] = True  # and a render failure
    saves_before = switched.saves
    switched.switch_profile(
        {"session": other.settings["session"], "locked": True})

    inc = switched.addon["incursion"]
    run = shell_run(switched)
    res.check(run is not None and run["instance"] == SHELL_OTHER,
              "after a character change the window still showed the previous "
              "character's run: %r" % (run and run["instance"],))
    res.check(shell_state(switched)["player"] is None,
              "the previous character's name was kept, so the new character's "
              "own points would be discarded as somebody else's")
    res.check(inc["override"] is None,
              "a window hidden by hand on one character stayed hidden on the "
              "next")
    res.check(inc["render_off"] is False,
              "a window switched off by a render error on one character came "
              "up switched off on the next, who never saw the failure")
    res.check(inc["settings"]["locked"] is True,
              "the new character's own settings were not adopted")
    res.check(switched.saves == saves_before + 1,
              "the character change was never written to disk")

    # A profile switch that carries no settings table at all still saves and
    # leaves everything else alone.
    saves_before = switched.saves
    switched.profile_callback(None)
    inc = switched.addon["incursion"]
    run = shell_run(switched)
    res.check(switched.saves == saves_before + 1,
              "a settings event with nothing in it skipped the save")
    res.check(run is not None and run["instance"] == SHELL_OTHER,
              "a settings event with nothing in it threw the run away")
    res.check(inc["settings"]["locked"] is True,
              "a settings event with nothing in it changed the settings")

    # --- the command surface ----------------------------------------------

    # Commands arrive as a plain string; the harness's string:args() extension
    # makes args[1] and args[2] behave as they do in game. `blocked` is read
    # back off the event table the handler was given.
    cmd = loaded_host()
    inc = cmd.addon["incursion"]

    e = cmd.fire("command", command="/incursion")
    res.check(e["blocked"] is True,
              "the addon let its own command fall through to the game as an "
              "unknown command")
    res.check(inc["override"] is True,
              "asking for the window with nothing on screen did not ask for "
              "it to be shown")
    res.check(any("No active Incursion run" in line for line in cmd.chat),
              "the window was asked for with no run in progress and the "
              "player was told nothing: %r" % cmd.chat)

    cmd.fire("command", command="/incursion")
    res.check(inc["override"] is False,
              "the command does not toggle: asking twice did not put the "
              "window back where it started")

    e = cmd.fire("command", command="/inc")
    res.check(e["blocked"] is True,
              "the short form of the command was not recognised")
    res.check(inc["override"] is True,
              "the short form of the command did not toggle the window")

    chat_before = len(cmd.chat)
    e = cmd.fire("command", command="/heal")
    res.check(e["blocked"] is None,
              "the addon swallowed a command that was not its own")
    res.check(len(cmd.chat) == chat_before,
              "the addon answered a command that was not its own: %r"
              % cmd.chat[chat_before:])

    # --- reset ---------------------------------------------------------------

    clearing = loaded_host()
    clearing.fire_text_in(begins())
    clearing.addon["incursion"]["override"] = True
    saves_before = clearing.saves
    clearing.fire("command", command="/incursion reset")

    inc = clearing.addon["incursion"]
    res.check(shell_run(clearing) is None,
              "clearing the run left it on screen")
    res.check(clearing.settings["session"] == "",
              "the cleared run was still on disk and would come back on the "
              "next reload: %r" % (clearing.settings["session"],))
    res.check(clearing.saves == saves_before + 1,
              "clearing the run was never written to disk")
    res.check(any("Run cleared" in line for line in clearing.chat),
              "the run was cleared and the player was never told: %r"
              % clearing.chat)
    res.check(inc["override"] is None,
              "clearing the run left a manual show/hide from the old run in "
              "place")

    # HARD-06, through the path the phase's success criterion actually names:
    # the player types /incursion reset, not State:reset(). The server sends
    # the remaining-minutes line just before 'Begins!', so a reset in between
    # is exactly the window in which a held sync could leak into a run it
    # never belonged to.
    swept = loaded_host()
    swept.fire_text_in("You have 90 minutes remaining inside this Incursion.")
    swept.fire("command", command="/incursion reset")
    swept.fire_text_in(begins())
    swept_state = shell_state(swept)
    swept_left = swept_state.time_left(swept_state)
    res.check(swept_left is None,
              "/incursion reset then a new run: the window came up already "
              "counting down from the cleared run's clock (%r seconds left) "
              "instead of blank" % (swept_left,))
    swept_run = shell_run(swept)
    res.check(swept_run is not None and swept_run["time_sync"] is None,
              "a run begun after /incursion reset carried the cleared run's "
              "sync time")

    # --- lock and auto, both ways -------------------------------------------

    toggles = loaded_host()
    saves_before = toggles.saves

    toggles.fire("command", command="/incursion lock")
    res.check(toggles.settings["locked"] is True,
              "locking the window did not lock it")
    res.check(toggles.chat[-1].endswith("Window locked."),
              "locking the window reported the wrong state: %r"
              % toggles.chat[-1])
    toggles.fire("command", command="/incursion lock")
    res.check(toggles.settings["locked"] is False,
              "locking the window a second time did not unlock it")
    res.check(toggles.chat[-1].endswith("Window unlocked."),
              "unlocking the window reported the wrong state: %r"
              % toggles.chat[-1])
    res.check(toggles.saves == saves_before + 2,
              "the lock setting was changed without being written to disk")

    toggles.addon["incursion"]["override"] = True
    saves_before = toggles.saves
    toggles.fire("command", command="/incursion auto")
    res.check(toggles.settings["auto"] is False,
              "turning automatic show/hide off did not turn it off")
    res.check(toggles.addon["incursion"]["override"] is None,
              "turning automatic show/hide off left an old manual show/hide "
              "in charge of the window")
    res.check(toggles.chat[-1].endswith("Automatic show/hide off."),
              "turning automatic show/hide off reported the wrong state: %r"
              % toggles.chat[-1])
    toggles.fire("command", command="/incursion auto")
    res.check(toggles.settings["auto"] is True,
              "turning automatic show/hide on did not turn it back on")
    res.check(toggles.chat[-1].endswith("Automatic show/hide on."),
              "turning automatic show/hide on reported the wrong state: %r"
              % toggles.chat[-1])
    res.check(toggles.saves == saves_before + 2,
              "the automatic show/hide setting was changed without being "
              "written to disk")

    # --- an unrecognised subcommand explains itself and does nothing else ---

    usage = loaded_host()
    usage.fire_text_in(begins())
    saves_before = usage.saves
    auto_before = usage.settings["auto"]
    locked_before = usage.settings["locked"]
    chat_before = len(usage.chat)

    usage.fire("command", command="/incursion wibble")
    said = usage.chat[chat_before:]
    res.check(len(said) == 5,
              "an unrecognised subcommand printed %d lines instead of the "
              "usage header and its four commands: %r" % (len(said), said))
    res.check(bool(said) and said[0].endswith("Usage:"),
              "an unrecognised subcommand did not lead with usage: %r" % said)
    res.check(all("/incursion" in line for line in said[1:]),
              "the usage text does not list the commands: %r" % said[1:])
    res.check(usage.saves == saves_before,
              "an unrecognised subcommand wrote settings to disk")
    res.check(usage.settings["auto"] == auto_before
              and usage.settings["locked"] == locked_before,
              "an unrecognised subcommand changed a setting")
    res.check(shell_run(usage) is not None,
              "an unrecognised subcommand threw the run away")

    # --- visible(): the override-vs-auto interaction ------------------------

    # Three lines of code with five distinct outcomes, and the one place a
    # player can end up staring at a window that will not go away or waiting
    # for one that never arrives.
    look = loaded_host()
    visible = look.addon["visible"]

    res.check(visible() is False,
              "the window was on screen with no Incursion in progress")

    look.fire_text_in(begins())
    res.check(visible() is True,
              "the window stayed hidden through a run the player is standing "
              "in, with automatic show/hide on")

    look.settings["auto"] = False
    res.check(visible() is False,
              "the window showed itself although automatic show/hide is off")

    look.addon["incursion"]["override"] = True
    res.check(visible() is True,
              "the window was asked for by hand and still refused to appear")

    look.addon["incursion"]["override"] = False
    look.settings["auto"] = True
    res.check(visible() is False,
              "the window was dismissed by hand and came back anyway")

    # --- the render gate ----------------------------------------------------

    frame = loaded_host()
    frame.imgui.reset()
    frame.fire("d3d_present")
    res.check(not frame.imgui.calls,
              "a frame drew something with no Incursion in progress: %r"
              % (frame.imgui.calls[:4],))

    frame.fire_text_in(begins())
    frame.fire_text_in(phase_line(1, 3))
    override_before = frame.addon["incursion"]["override"]
    frame.imgui.reset()
    frame.fire("d3d_present")
    drawn = [name for name, _ in frame.imgui.calls]
    res.check("Begin" in drawn,
              "a frame during a live run drew no window: %r" % drawn)
    res.check(frame.addon["incursion"]["override"] is override_before,
              "an ordinary frame changed the window's show/hide state by "
              "itself")

    # Nothing here arms the recorder's close switch or asserts anything about
    # the manual-hide branch at inctrack.lua:219-222: that is the ui suite's
    # one expected failure, and a second entry for the same defect would break
    # the exactly-three guard in main().

    # --- an error inside ui.render (HARD-01) --------------------------------
    #
    # ui.render runs inside d3d_present, on the game thread, sixty times a
    # second, and it is handed strings that came off the wire and tables that
    # came out of a JSON blob. An error there is not a log line: it leaves the
    # ImGui window and style stacks unbalanced for every addon sharing the
    # process, and then it happens again on the next frame, and the one after.

    BALANCED = {"window": 0, "style_var": 0, "style_color": 0}

    def one_frame(host):
        """Drive a single d3d_present.

        Returns the error text if it escaped into the host, or None when the
        frame handler contained it. A raise that reaches here is a raise that
        would reach Ashita.
        """
        try:
            host.fire("d3d_present")
        except Exception as exc:                          # noqa: BLE001
            return str(exc).splitlines()[0]
        return None

    def drawn_names(host):
        return [name for name, _ in host.imgui.calls]

    res.check(frame.addon["incursion"]["render_off"] is False,
              "an ordinary frame took the window off screen for the rest of "
              "the session by itself")

    # Trigger A: a value table.concat refuses, reached through the mob list.
    # A boolean and not a number -- table.concat takes numbers happily, so a
    # number would prove nothing.
    concat = loaded_host()
    concat.fire_text_in(begins())
    concat.fire_text_in(phase_line(1, 3))
    concat.fire_text_in(SHELL_MOBS)

    # One clean frame first. That is realistic -- a run draws for a while and
    # then a bad value arrives -- and it is what earns the repair: the render
    # shape has been shown to work on this host, so what raises afterwards is
    # inside the window.
    concat.imgui.reset()
    one_frame(concat)
    res.check("Begin" in drawn_names(concat),
              "the window drew no clean frame before the run was poisoned, "
              "so nothing below can tell a repair from a guess")

    shell_run(concat)["objective"]["mobs"][1] = True
    chat_before = len(concat.chat)
    concat.imgui.reset()
    escaped = one_frame(concat)
    balance = concat.imgui.balance()

    res.check(escaped is None,
              "a bad value in the mob list threw out of d3d_present and into "
              "the game thread every addon shares: %s" % escaped)
    res.check(balance == BALANCED,
              "the ImGui stacks were left unbalanced after a render error, "
              "so this window and every other addon's is corrupt from the "
              "next frame on: %r" % (balance,))
    res.check("Begin" in drawn_names(concat),
              "the failing frame never opened the window, so the balance "
              "above is the balance of a frame that drew nothing")

    said = concat.chat[chat_before:]
    res.check(len(said) == 1,
              "one render failure produced %d chat lines" % len(said))
    res.check(any("/incursion" in line for line in said),
              "the window vanished and nothing said how to get it back: %r"
              % (said,))

    # Not sixty times a second.
    chat_before = len(concat.chat)
    concat.imgui.reset()
    for _ in range(60):
        one_frame(concat)
    res.check(not concat.imgui.calls,
              "a window that took itself off screen kept drawing anyway: %r"
              % (concat.imgui.calls[:4],))
    res.check(len(concat.chat) == chat_before,
              "the same failure was reported again on later frames -- at "
              "frame rate that is a chat log the player cannot read")

    # The addon is not dead, only the window.
    concat.fire_text_in(phase_line(2, 7))
    still = shell_run(concat)
    res.check(still is not None and still["phase"] == 2,
              "chat stopped driving the run once the window switched itself "
              "off: the whole addon went down with the HUD")

    # The way back.
    shell_run(concat)["objective"]["mobs"][1] = SHELL_FIRST_MOB
    concat.fire("command", command="/incursion")
    chat_before = len(concat.chat)
    concat.imgui.reset()
    escaped = one_frame(concat)
    res.check(escaped is None,
              "the frame after /incursion threw: %s" % escaped)
    res.check("Begin" in drawn_names(concat),
              "/incursion did not bring the window back: the player's only "
              "recovery short of /addon reload does nothing")
    res.check(len(concat.chat) == chat_before,
              "a recovered window complained again on the very frame it came "
              "back")

    # Trigger B: a percent sign in a server-supplied instance name, raising
    # from the call that draws it. The recorder models the consequence on
    # demand; it never claims Ashita's binding really treats drawn text as a
    # format string.
    pct = loaded_host()
    pct.fire_text_in(begins(SHELL_PERCENT))
    pct.fire_text_in(phase_line(1, 3, instance=SHELL_PERCENT))

    pct.imgui.reset()
    one_frame(pct)
    res.check("Begin" in drawn_names(pct),
              "the window drew no clean frame before the injector was armed, "
              "so nothing below can tell a repair from a guess")

    chat_before = len(pct.chat)
    pct.imgui.reset()
    pct.imgui.arm_fault("TextColored", contains=SHELL_PERCENT)
    escaped = one_frame(pct)
    balance = pct.imgui.balance()

    res.check(escaped is None,
              "a percent sign in a name the server sent threw out of "
              "d3d_present: %s" % escaped)
    res.check(balance == BALANCED,
              "the ImGui stacks were left unbalanced after a raise from a "
              "draw call: %r" % (balance,))
    res.check("Begin" in drawn_names(pct),
              "the failing frame never opened the window, so the balance "
              "above is the balance of a frame that drew nothing")

    said = pct.chat[chat_before:]
    res.check(len(said) == 1 and "/incursion" in said[0],
              "the player was not told once, in one line naming /incursion, "
              "what happened: %r" % (said,))

    # Trigger C: a raise that precedes the window's opening. Three statements
    # in render run before Begin, and a raise from any of them leaves nothing
    # open and nothing pushed. Closing a window that was never opened is an
    # unmatched close -- on a real host an ImGui assert, which would make the
    # repair the second error of the frame. So the right repair here is no
    # repair, and this is the case that forbids an unconditional one.
    early = loaded_host()
    early.fire_text_in(begins())
    early.fire_text_in(phase_line(1, 3))

    # Deliberately no clean frame: this host has never drawn.
    chat_before = len(early.chat)
    early.imgui.reset()
    early.imgui.arm_fault("PushStyleVar")
    escaped = one_frame(early)
    balance = early.imgui.balance()
    drawn = drawn_names(early)

    res.check(escaped is None,
              "a raise before the window opened threw out of d3d_present: %s"
              % escaped)
    res.check(balance == BALANCED,
              "the stacks did not come back level from a frame that opened "
              "nothing: %r" % (balance,))
    res.check("End" not in drawn,
              "the shell closed a window that was never opened -- on a real "
              "host that is an ImGui assert, so the repair became the second "
              "error of the frame: %r" % drawn)
    res.check("PopStyleVar" not in drawn,
              "the shell popped a style var that was never pushed: %r"
              % drawn)
    res.check(early.addon["incursion"]["render_off"] is True,
              "a failure before the window opened was not latched, so it "
              "will happen again on every frame from now on")

    said = early.chat[chat_before:]
    res.check(len(said) == 1 and "/incursion" in said[0],
              "the player was not told once, in one line naming /incursion, "
              "what happened: %r" % (said,))

    early.fire("command", command="/incursion")
    early.imgui.reset()
    escaped = one_frame(early)
    res.check(escaped is None and "Begin" in drawn_names(early),
              "/incursion did not bring back a window disabled by a failure "
              "that happened before it was ever opened")

    # /incursion reset is the other way back, and it clears the run with it.
    back = loaded_host()
    back.fire_text_in(begins())
    back.fire_text_in(phase_line(1, 3))
    back.imgui.arm_fault("PushStyleVar")
    one_frame(back)
    res.check(back.addon["incursion"]["render_off"] is True,
              "the failure was not latched, so it will repeat every frame")

    back.fire("command", command="/incursion reset")
    res.check(back.addon["incursion"]["render_off"] is False,
              "/incursion reset left the window switched off, so a player "
              "clearing the run still has no HUD")
    res.check(shell_run(back) is None,
              "/incursion reset kept the run it was asked to clear")

    return res


def run_suite(label, fn, *args):
    """Run one suite, turning a crash into a reported failure.

    Result.check accumulates rather than aborting -- that is its contract --
    but a Lua accessor that returns nil after a state regression makes the
    *Python* dereference raise, and an uncaught raise takes every other
    suite's report and the known-defect guard down with it. A named regression
    would surface as a traceback with no report at all, which is the one
    outcome that makes the whole-suite guarantee unanswerable.

    A suite that dies is a red suite, not a missing one: the run still
    reports, the exit code is still non-zero, and the guard still notices that
    a named defect stopped being counted. The traceback goes to stderr so
    nothing is lost.

    Returns a list, because the parser suites come in pairs.
    """
    try:
        out = fn(*args)
    except Exception as exc:                              # noqa: BLE001
        traceback.print_exc()
        broken = Result("%s: the suite did not finish" % label)
        broken.check(False,
                     "the suite stopped early and proved nothing past that "
                     "point: %s: %s" % (type(exc).__name__, exc))
        return [broken]
    return [out] if isinstance(out, Result) else list(out)


def main():
    logdir = find_logs()
    libs = find_ashita_libs(logdir)
    lua, parser, State = make_lua()

    print("inctrack tests")
    print("  lua: %s%s" % (getattr(lua, "lua_implementation", "unknown"),
                           " (INCTRACK_LUA)" if os.environ.get("INCTRACK_LUA")
                           else ""))

    suites = []

    if logdir:
        lines = load_lines(logdir)
        player = player_from_logs(lines)
        print("  chatlogs: %s" % logdir)
        print("  %d chat lines from %d logs, character %s" % (
            len(lines), len(set(l[0] for l in lines)), player))
        suites.extend(run_suite("parser", test_parser, lines, parser))
        suites.extend(run_suite("run reconstruction", test_replay,
                                lines, lua, parser, State, player))
    else:
        print("  chatlogs: none (pass a directory or set INCURSION_CHATLOGS "
              "to replay real runs)")
    print()

    suites.extend(run_suite("state", test_state_units, lua, parser, State))
    suites.extend(run_suite("adaptability", test_future_content,
                            lua, parser, State))
    suites.extend(run_suite("disconnect", test_disconnect,
                            lua, parser, State))
    suites.extend(run_suite("timers", test_timers, lua, parser, State))
    suites.extend(run_suite("persistence", test_json_roundtrip,
                            lua, parser, State, libs))
    suites.extend(run_suite("ui", test_ui))
    suites.extend(run_suite("addon", test_addon_shell))

    ok = True
    for s in suites:
        ok &= s.report()

    # Not "some things fail" but "these, and nothing else, fail" -- and the
    # set is now empty. The count is summed across every suite, and the suites
    # that carried the three defects always run, so this holds identically
    # with and without chatlogs. Neither line printed here may contain either
    # report marker -- the phase criteria count those in this output.
    known = sum(len(s.xfails) for s in suites)
    still_red = [d for s in suites for d in s.xfail_ids]
    early = [d for s in suites for d in s.fixed_ids]
    print()
    print("  %d known defects" % known)
    if known != EXPECTED_XFAILS:
        print("  guard: this phase closes on exactly %d known defects; the "
              "run reported %d" % (EXPECTED_XFAILS, known))
        ok = False
    if sorted(still_red) != sorted(EXPECTED_DEFECTS):
        print("  guard: the failure list must be exactly %s; it is %s"
              % (", ".join(sorted(EXPECTED_DEFECTS)) or "empty",
                 ", ".join(sorted(still_red)) or "empty"))
        ok = False
    if early:
        print("  guard: %s stopped failing before its fix was written, so the "
              "red line that was meant to prove the fix never ran"
              % ", ".join(sorted(early)))
        ok = False

    print()
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
