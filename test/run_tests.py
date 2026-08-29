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

Eleven suite functions, printing thirteen result lines: test_parser returns
three Results (coverage, the dormant generic tier, the over-reach guard) and
every other suite returns one. Both numbers are checked by the record suite
against this file and against docs/design.md, because the arithmetic here has
been stated wrongly more than once.

  1. parser coverage    -- every structural Incursion line must parse      [logs]
     generic tier       -- the catch-alls must match nothing that exists   [logs]
     tightened patterns -- each split re-derived from the raw text         [logs]
  2. run reconstruction -- instance, phase, points, completion per run     [logs]
  3. state unit tests   -- objectives, bonus, recovery
  4. adaptability       -- invented future content is still tracked
  5. disconnect         -- stale progress is never presented as current
  6. timers             -- countdown, linger, staleness
  7. persistence        -- json round trip                                  [libs]
  8. ui                 -- pure helpers, and whole-window render snapshots
  9. addon shell        -- registration, text_in, settings, commands
 10. record             -- the counted claims the source and docs make
 11. reject cost        -- what a line the addon ignores costs, before/after

ui.lua and inctrack.lua are reached through stubbed hosts (test/stubs.py);
make_host() builds an isolated runtime with both installed.

The write policy suite 10 asserts, since the addon stopped writing to disk
on the chat thread: text_in decides whether a write is owed -- immediately
for an event the server never repeats, otherwise once every five seconds --
and marks it; d3d_present performs it, above both of its early returns, so a
hidden or latched-off window still writes the run down; and the unload
handler writes unconditionally, without consulting the mark, because it is
the one path that cannot wait for a frame. So every save is asserted twice:
nothing on the line that delivered it, then written on the next frame.

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
import time
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
# rather than reused from anywhere: the glyph group is `[^)]*`, which cannot
# step over a `)` the way the shipped `.-` could; and the name, once trimmed,
# must be non-blank, which the pattern cannot say and the caller checks.
# Everything else is the 1.1.0 shape unchanged.
#
# The group is `*` and not `+`. Requiring it to be non-empty narrowed only
# against the server -- the tail plus a non-blank name already separate a boon
# from an ordinary buff -- on a matcher with no fallback tier under it, so a
# `()` glyph group dropped a boon permanently.
BOON_REF = re.compile(r"^(\S+) gains the effect of (.*?) \(([^)]*)\): (.+)$")
BOON_PHRASE = " gains the effect of "


# --------------------------------------------------------------------------
# PERF-04: the reject-path corpus, and the head-of-phase baseline
# --------------------------------------------------------------------------

# Chat lines the addon does not care about, written out here rather than read
# from a log, so the figure prints on a machine with no chatlogs and no Ashita
# install (COVR-04). Invented names only, in the server's established wording,
# exactly as the rest of the harness does -- the addon must know none of them.
#
# Three groups, reported separately, because they cost different things:
#
#   plain    -- ordinary combat, party and system chat with no colour codes.
#               This is the group PERF-01 makes free.
#   coloured -- the same shapes carrying Ashita's colour-code marker bytes.
#               The gate declines to judge a line with a code in it, so these
#               keep costing exactly what they cost today, and never more.
#   stamped  -- carrying the '[HH:MM:SS] ' prefix a timestamp plugin adds. The
#               chatlogs show one active in this setup, so the reject path
#               meets this shape in life.
#
# Every line here is asserted to return nil from the shipped parser, so the
# benchmark can never be won by measuring a path that skipped real work.
#
# All three of Ashita's marker bytes are represented, because two of them were
# not until Phase 4's review: `strip_colors` strips 0x1E, 0x1F *and* 0x7F
# (addons/libs/sugar/string.lua), and a corpus carrying only the first two
# models a host that does not strip the third. Every check below that turns on
# "a code inside a needle" is only as wide as this tuple is.
CC_A = "\x1e\x51"      # a colour-code marker byte plus its one payload byte
CC_B = "\x1f\x02"
CC_C = "\x7f\x31"
CC_ALL = (CC_A, CC_B, CC_C)

REJECT_PLAIN = (
    "Godwen hits the Nest Skitterer for 42 points of damage.",
    "The Nest Skitterer misses Godwen.",
    "Godwen uses Fast Blade.",
    "Godwen defeats the Nest Drone.",
    "Rialla casts Cure III on Godwen.",
    "Godwen obtains 137 gil.",
    "Godwen recovers 24 MP.",
    "Rialla >> pulling the next group, hold here a moment",
    "Tomabi : anyone free for a run in an hour or so",
    "The Nest Broodguard readies Cocoon.",
    "Godwen's Fast Blade hits the Nest Skitterer for 118 points of damage.",
    "You cannot use that command at this time.",
)

# A code at the head and a second one dropped inside the line -- which is
# exactly where a code defeats an anchored test on raw text, and is the reason
# the gate declines to judge a coloured line at all.
#
# The pair rotates through all three markers, so each one appears both at the
# head and inside the line across the six. Six lines, two codes apiece, as
# before: the per-line strip and gsub counts the cost suite asserts on are
# unchanged by widening the byte set.
REJECT_COLOURED = tuple(
    CC_ALL[i % 3] + line[:5] + CC_ALL[(i + 1) % 3] + line[5:]
    for i, line in enumerate(REJECT_PLAIN[:6]))

REJECT_STAMPED = tuple(
    "[21:47:0%d] %s" % (i, line) for i, line in enumerate(REJECT_PLAIN[6:]))

# The colour-free half: the lines PERF-01 is entitled to reject outright.
REJECT_FREE = REJECT_PLAIN + REJECT_STAMPED
REJECT_CORPUS = REJECT_PLAIN + REJECT_COLOURED + REJECT_STAMPED

# Chosen so the slower shape takes upwards of 0.2s a pass while the whole
# benchmark -- two shapes, best of three, plus four counting hosts -- stays
# well under the five seconds it is allowed to add to a run.
REJECT_ITERATIONS = 3000

# The head-of-Phase-4 baseline: the old shape below, which is the reject path
# as Phase 3 shipped it.
#
# Provenance, never a threshold. A rate is a fact about one machine on one
# afternoon, so nothing here is ever asserted against it and nothing may
# compare it with a figure from another machine. The suite's actual checks are
# the deterministic counters, plus one same-run ratio between two shapes
# measured side by side on the same corpus.
#
# Re-recorded after Phase 4's review. The first figure taken here -- 285,562
# lines/s, 3.502 us/line -- was measured against a harness whose
# `strip_colors` stub did two gsubs where Ashita's does one, so the old shape
# was carrying an allocation per line that the real Phase-3 path never paid.
# The stub is now the host's single character-class gsub, the old shape is
# correspondingly cheaper, and the improvement PERF-01 bought is a smaller
# number than it was reported as. Honest and smaller beats flattering: the
# figure below is what the old shape actually cost.
#
# `commit` names where the old shape was transcribed from and does not move
# when the figure is re-taken -- the transcription is unchanged; only the host
# stub it runs against was corrected.
REJECT_BASELINE = {
    "date": "2026-08-29",
    "commit": "a6a3577",           # the parser exactly as Phase 3 left it
    "backend": "Lua 5.5",          # lupa's default build on this machine
    "python": "3.14.5",
    "lines_per_second": 288437,
    "us_per_line": 3.467,
}


def coloured(line):
    """True when the line carries an Ashita colour-code marker byte."""
    return "\x1e" in line or "\x1f" in line


# The two shapes, driven from inside Lua: a Python-to-Lua call per line would
# swamp what is being measured, which is a handful of string allocations. Both
# reuse one event table with only the message rewritten, so neither pays for a
# table the other does not, and both take the same corpus and iteration count.
BENCH_CHUNK = """
--[[
* The old shape -- the reject path as Phase 3 left it, copied rather than
* called so the baseline survives the change PERF-01 makes to the real one.
*
* This is the head of parser.parse: trim, the timestamp loop, the empty check
* and the anchored cheap rejection, transcribed from inctrack/parser.lua at
* commit a6a3577, the head of Phase 4. That transcription is what makes the
* recorded figure a baseline of the parser as Phase 3 shipped it rather than a
* coincidence.
*
* The corpus is entirely rejects, so the two matcher arrays are never reached
* and this head is the whole of the cost. Nothing below the rejection is
* copied, and nothing here is ever called by the addon.
]]--
local function __bench_parse_head(line)
    if type(line) ~= 'string' then
        return nil;
    end

    local s = (line:gsub('^%s+', ''):gsub('%s+$', ''));

    while true do
        local rest, n = s:gsub('^%[%d%d:%d%d:%d%d%]%s+', '', 1);
        if n == 0 then
            break;
        end
        s = rest;
    end

    if s == '' then
        return nil;
    end

    if not (s:find('^Incursion %[')
        or s:find('^New Objective: ')
        or s:find('^Bonus Objective: ')
        or s:find('^%(Boss: ')
        or s:find('^You have %d')
        or s:find('incursion points%.$')
        or s:find('): ', 1, true)) then
        return nil;
    end

    return nil;
end

-- The text_in handler as Phase 3 left it, wrapped around that head. The pcall
-- and the closure it allocates are part of what a line costs, so they stay.
local function __bench_old_line(e)
    return pcall(function ()
        local line = e.message;
        if line == nil or line == '' then
            return;
        end
        line = line:strip_colors();
        local event = __bench_parse_head(line);
        if event == nil then
            return;
        end
    end);
end

local function __bench_event()
    return { mode = 0, indent = 0, message = '', injected = false };
end

function __bench_old(corpus, iterations)
    local e = __bench_event();
    local n = #corpus;
    for _ = 1, iterations do
        for i = 1, n do
            e.message = corpus[i];
            __bench_old_line(e);
        end
    end
end

-- The new shape -- the addon's own registered handler, so what is timed is
-- the shipped path including its pcall, not a second copy of it.
function __bench_new(corpus, iterations)
    local handler = __host_events['text_in'];
    local e = __bench_event();
    local n = #corpus;
    for _ = 1, iterations do
        for i = 1, n do
            e.message = corpus[i];
            handler(e);
        end
    end
end
"""


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


def table_entries(host, table):
    """How many keys a Lua table actually holds, counted over pairs.

    Counted from the table itself rather than read off a bookkeeping counter,
    so a counter that has drifted from the thing it claims to describe is
    caught rather than believed.
    """
    counter = getattr(host, "_gsd_entry_counter", None)
    if counter is None:
        counter = host.lua.eval(
            "function (t) local n = 0; for _ in pairs(t) do n = n + 1 end; "
            "return n end")
        host._gsd_entry_counter = counter
    return int(counter(table))


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


def at(path, text, lineno=None):
    """A log location and the text found there, safe for any console.

    Every failure message in the log-driven suites embeds text the server
    sent, and a boon line carries the glyph's raw high bytes, which decode to
    U+FFFD. Printing that on a cp1252 console raises *inside* Result.report(),
    turning the readable red line the run owed into a traceback -- and the
    machines that have chatlogs are exactly the machines with that console.

    So the text always goes through ascii(). Phase 3 did this to its own six
    new messages one at a time and left the pre-existing ones under its scope
    fence; this is the one helper all of them share, so a message added later
    is escaped by using it rather than by remembering to.
    """
    if lineno is None:
        return "%s %s" % (path, ascii(text))
    return "%s:%d  %s" % (path, lineno, ascii(text))


# Every path in a decoded or restored table holding a number that is not a
# value. Written in Lua rather than walked from Python because the crossing
# back into Python is what a test like this must not depend on -- and because
# the three idioms below are the ones state.lua's own finite() uses, so a
# dialect that disagreed with them would fail the addon and the check together.
# tostring() is deliberately absent: Lua 5.5 on Windows prints '-nan(ind)'
# where LuaJIT prints 'nan'.
NONFINITE_CHUNK = """
function __gsd_nonfinite(t, prefix, out, seen)
    out = out or {}; seen = seen or {}; prefix = prefix or '';
    if seen[t] then return out end
    seen[t] = true;
    for k, v in pairs(t) do
        local path = prefix .. tostring(k);
        if type(v) == 'number' then
            if v ~= v or v == math.huge or v == -math.huge then
                out[#out + 1] = path;
            end
        elseif type(v) == 'table' then
            __gsd_nonfinite(v, path .. '.', out, seen);
        end
    end
    return out;
end
function __gsd_nonfinite_list(t)
    local out = __gsd_nonfinite(t);
    table.sort(out);
    return table.concat(out, ', ');
end
"""


def nonfinite_fields(lua, table):
    """Where a table holds NaN or +/-infinity, as one comma-separated string.

    Empty when it holds neither, so a check reads as `not nonfinite_fields(...)`
    and its failure message names the field without a second walk.
    """
    if table is None:
        return ""
    if lua.globals()["__gsd_nonfinite_list"] is None:
        lua.execute(NONFINITE_CHUNK)
    return lua.globals().__gsd_nonfinite_list(table)


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
                           "unparsed %s" % at(path, line, lineno))

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
            dormant.check(False, "generic %s on %s"
                          % (ev["t"], at(path, line, lineno)))
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
    # The instance name came off a log line, so it goes through the same
    # console-safe formatting as the parser suites' locations do.
    tag = at(path, active["instance"])

    res.check(run["instance"] == active["instance"],
              "%s: instance %s" % (tag, ascii(run["instance"])))
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


    # --- IN-05 / audit G-1: a number that is not a value -------------------
    #
    # opt_number answers 'is this the right shape', and NaN and +/-infinity
    # are: type(v) == 'number' is true of all three, and every other rule in
    # the validator passes them. Nothing they could be said to *be* is,
    # though -- no minute, no kill count, no save stamp -- and arithmetic
    # spreads them rather than stopping on them, so one anywhere in the blob
    # reaches the window. Driven against the shipped modules, a restored run
    # drew
    #
    #     ~-9223372036854775808:-9223372036854775808:-9223372036854775808
    #
    # where the instance clock belongs, under LuaJIT, which is the dialect
    # Ashita embeds; under Lua 5.3 and later the same value raises out of
    # string.format instead, so the window goes dark.
    #
    # The rule is that a non-finite number reads exactly as a missing key
    # would: that one field is unknown, everything else comes back. Not the
    # whole run refused -- that is the harm CR-01 above exists to prevent, and
    # it costs boons, points, phase and elapsed the server never sends again.
    # Not the number kept either -- that is the core value inverted.
    #
    # Reachable rather than contrived: '1e999' is well-formed JSON and the
    # settings file is one a player can hand-edit. The persistence suite
    # drives that literal through Ashita's own decoder.

    # The three values are made in Python and cross into Lua through lupa. If
    # that crossing stopped preserving them -- a NaN arriving as a string, an
    # infinity clamped to a float maximum -- every case below would pass for
    # the wrong reason, so it is checked first, in Lua, with the same idioms
    # state.lua uses, on whichever backend this run is against. Those idioms
    # mean the same thing in both dialects; tostring() does not, which is why
    # nothing here reads one (Lua 5.5 on Windows prints '-nan(ind)' where
    # LuaJIT prints 'nan'), and neither does any integer test, since LuaJIT
    # has no integer subtype.
    lua.execute(
        "function __gsd_nf(v) return type(v) == 'number', v ~= v, "
        "v == math.huge, v == -math.huge end")
    nf = lua.globals().__gsd_nf

    NONFINITE = [
        ("NaN",       float("nan"),  (True, True,  False, False)),
        ("+infinity", float("inf"),  (True, False, True,  False)),
        ("-infinity", float("-inf"), (True, False, False, True)),
    ]
    for what, value, want in NONFINITE:
        got = tuple(bool(x) for x in nf(value))
        res.check(got == want,
                  "%s does not reach Lua as itself on this backend, so every "
                  "case below proves nothing: (number, v~=v, v==huge, "
                  "v==-huge) read %r, expected %r" % (what, got, want))

    # nonfinite_fields sweeps the whole restored record, so a value that
    # slipped past the field the case names is still caught. Nothing in the
    # run may be non-finite once restore() has returned, and that assertion --
    # unlike the per-field expectations below -- does not have to be kept in
    # step with any list.

    def restore_with(path, value):
        """A known-good blob with one field replaced, restored.

        Returns (raised, took, state, run).
        """
        s = new_state(lua, State)
        raised = None
        took = False
        try:
            took = bool(s.restore(s, broken(path, value)))
        except Exception as exc:                    # noqa: BLE001
            raised = exc
        return raised, took, s, s.snapshot(s)

    # What the fixture holds, so 'the rest came back intact' is stated once
    # rather than per case. The entry for the field a case is breaking is
    # skipped -- that field has its own expectation below.
    def rest_intact(run, skip):
        def read(*keys):
            v = run
            for k in keys:
                if v is None:
                    return None
                v = v[k]
            return v

        def count(*keys):
            t = read(*keys)
            return None if t is None else len(list(t.values()))

        checks = (
            ("instance",              lambda: read("instance") == "Fort Ghelsba"),
            ("difficulty",            lambda: read("difficulty") == "Normal"),
            ("phase",                 lambda: int(read("phase")) == 2),
            ("kills_cur",             lambda: int(read("kills_cur")) == 13),
            ("kills_max",             lambda: int(read("kills_max")) == 20),
            ("points",                lambda: int(read("points")) == 84),
            ("awards_seen",           lambda: int(read("awards_seen")) == 1),
            ("phases_cleared",        lambda: int(read("phases_cleared")) == 1),
            ("objective.count",       lambda: int(read("objective", "count")) == 20),
            ("objective.mobs",        lambda: count("objective", "mobs") == 3),
            ("next_boss",             lambda: read("next_boss", "name") == "Orcish Martial"),
            ("bonus.cur",             lambda: int(read("bonus", "cur")) == 2),
            ("bonus.max",             lambda: int(read("bonus", "max")) == 5),
            ("extra.Seals Broken.cur",
             lambda: int(read("extra", "Seals Broken", "cur")) == 2),
            ("extra.Seals Broken.max",
             lambda: int(read("extra", "Seals Broken", "max")) == 6),
            ("boons",                 lambda: count("boons") == 2),
        )
        lost = []
        for name, test in checks:
            if name == skip or run is None:
                continue
            try:
                ok = bool(test())
            except Exception:                       # noqa: BLE001
                ok = False
            if not ok:
                lost.append(name)
        return lost

    def same_number(got, want):
        if want is None:
            return got is None
        return got is not None and float(got) == float(want)

    def field(*keys):
        def read(s, run):
            v = run
            for k in keys:
                if v is None:
                    return None
                v = v[k]
            return v
        return read

    # Every field opt_number guards, and what the run holds for it once the
    # value is read as absent. Each of these is also what an absent key gives,
    # which is the whole of the rule.
    ABSENT_CASES = [
        ("phase", "the phase number", field("phase"), None),
        ("kills_cur", "the kill count", field("kills_cur"), 0),
        ("kills_max", "the kill cap", field("kills_max"), None),
        ("points", "the points total", field("points"), 0),
        ("awards_seen", "the award count", field("awards_seen"), 0),
        ("phases_cleared", "the cleared-phase count", field("phases_cleared"), 0),
        ("objective.count", "the objective's own count",
         field("objective", "count"), None),
        ("bonus.cur", "the bonus progress", field("bonus", "cur"), 0),
        ("bonus.max", "the bonus target", field("bonus", "max"), None),
        ("bonus.remaining", "the bonus countdown",
         lambda s, run: s.bonus_remaining(s), None),
        ("extra.Seals Broken.cur", "an extra counter's progress",
         field("extra", "Seals Broken", "cur"), None),
        ("extra.Seals Broken.max", "an extra counter's target",
         field("extra", "Seals Broken", "max"), None),
        ("time_left", "the instance clock",
         lambda s, run: s.time_left(s), None),
    ]

    for path, what, reader, absent in ABSENT_CASES:
        for name, value, _ in NONFINITE:
            raised, took, s_nf, run_nf = restore_with(path, value)
            leftover = nonfinite_fields(lua, run_nf)
            lost = rest_intact(run_nf, path)
            if raised is not None:
                why = ("restore() raised (%s) -- in game that escapes into an "
                       "Ashita event handler with no protected call around it"
                       % raised)
            elif not took:
                why = ("the whole run was thrown away over one field, costing "
                       "the boons, points, phase and elapsed the server never "
                       "sends again")
            elif run_nf is None:
                why = "it was taken and no run was left behind"
            elif leftover:
                why = ("%s came back holding %s, which the window formats into "
                       "a number the server never sent" % (name, leftover))
            elif lost:
                why = ("the run came back short of %s, which %s had nothing to "
                       "do with" % (", ".join(lost), what))
            else:
                why = ""
            res.check(raised is None and took and run_nf is not None
                      and not leftover and not lost,
                      "a saved session whose %s was %s did not come back as a "
                      "run with that one field unknown and the rest intact: %s"
                      % (what, name, why))

            got = reader(s_nf, run_nf) if run_nf is not None else None
            res.check(same_number(got, absent),
                      "a %s of %s read back as %r rather than as unknown (%r) "
                      "-- a value that is not a number was kept and drawn"
                      % (what, name, got, absent))

    # The two fields the clock is built from are checked against a control
    # rather than a literal: both are derived from wall time, and a second can
    # tick between the two restores. Same rule, stated as 'the same run the
    # blob without that key gives'.
    for path, what in (("elapsed", "the elapsed counter"),
                       ("saved_at", "the save stamp")):
        _, ctl_took, ctl_state, ctl_run = restore_with(path, None)
        res.check(ctl_took and ctl_run is not None,
                  "a saved session with no %s was refused, so the cases below "
                  "have no control to be compared against" % path)
        ctl_elapsed = float(ctl_state.elapsed(ctl_state)) if ctl_took else None
        for name, value, _ in NONFINITE:
            raised, took, s_nf, run_nf = restore_with(path, value)
            leftover = nonfinite_fields(lua, run_nf)
            lost = rest_intact(run_nf, path)
            res.check(raised is None and took and run_nf is not None
                      and not leftover and not lost,
                      "a saved session whose %s was %s did not come back as a "
                      "run with that one field unknown and the rest intact: %s"
                      % (what, name,
                         raised if raised is not None
                         else ("refused" if not took
                               else (leftover or ", ".join(lost)
                                     or "no run was left"))))
            if not took or ctl_elapsed is None:
                continue
            got = float(s_nf.elapsed(s_nf))
            res.check(abs(got - ctl_elapsed) <= 1,
                      "a %s of %s put the elapsed counter at %r, where the "
                      "same blob without that key puts it at %r -- the window "
                      "is counting from a number the server never sent"
                      % (what, name, got, ctl_elapsed))

    # And the whole shape at once: every numeric field non-finite together.
    # This is the case where each field's fallback has to hold with no other
    # field left to lean on, and it is the one a hand-edited file most
    # plausibly produces -- an editor that wrote '1e999' once wrote it
    # everywhere.
    all_broken = shape_blob()
    for path in [c[0] for c in ABSENT_CASES] + ["elapsed", "saved_at"]:
        target = all_broken
        steps = path.split(".")
        for step in steps[:-1]:
            target = target[int(step) if step.isdigit() else step]
        target[steps[-1]] = float("inf")
    s_all = new_state(lua, State)
    all_raised = None
    all_took = False
    try:
        all_took = bool(s_all.restore(s_all, all_broken))
    except Exception as exc:                        # noqa: BLE001
        all_raised = exc
    all_run = s_all.snapshot(s_all)
    res.check(all_raised is None and all_took and all_run is not None,
              "a saved session whose every number was +infinity was not "
              "resumed at all, so the names, the mob list and the boons the "
              "server did send went with them: %s"
              % (all_raised if all_raised is not None else "refused"))
    res.check(not nonfinite_fields(lua, all_run),
              "a run restored from an all-infinity blob still holds %s"
              % (nonfinite_fields(lua, all_run) or "nothing",))
    res.check(all_run is not None
              and all_run["instance"] == "Fort Ghelsba"
              and all_run["next_boss"] is not None
              and all_run["next_boss"]["name"] == "Orcish Martial"
              and len(list(all_run["objective"]["mobs"].values())) == 3
              and len(list(all_run["boons"].values())) == 2,
              "an all-infinity blob came back without the instance, boss, "
              "mobs and boons it also held -- every one of them a string the "
              "numbers had nothing to do with")
    res.check(all_run is not None and s_all.time_left(s_all) is None
              and s_all.bonus_remaining(s_all) is None,
              "an all-infinity blob came back with a clock: time left %r, "
              "bonus countdown %r"
              % (s_all.time_left(s_all) if all_run is not None else None,
                 s_all.bonus_remaining(s_all) if all_run is not None else None))

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

    # Every invented line this suite drives through the parser is remembered,
    # so the cheap gate at the foot of the suite can be held to all of them
    # without a second copy of the list going stale beside the first.
    driven = []

    def drive(state, lines):
        driven.extend(lines)
        feed(state, parser, lines)

    def ev(line):
        driven.append(line)
        return parser.parse(line)

    # --- the failure message survives the console it is printed on --------
    #
    # at() is what the log-driven suites format their failure messages with,
    # and those suites only run on a machine that has chatlogs -- which is the
    # machine whose console is cp1252 and whose logs carry a boon glyph that
    # decodes to U+FFFD. So the helper is exercised here instead, in a suite
    # that runs everywhere, on the byte that would take Result.report() down.
    # A traceback in place of a readable red line is the failure being
    # prevented; the assertion is simply that encoding does not raise.
    try:
        at("Godwen_2026.08.29.log",
           "Godwen gains the effect of Ward (�): STR+5", 1234
           ).encode("cp1252")
        encodable = True
    except UnicodeEncodeError:
        encodable = False
    res.check(encodable,
              "a failure message carrying a boon glyph cannot be printed on a "
              "cp1252 console, so the run would die with a traceback where a "
              "readable red line was owed")

    # A brand new instance with a new difficulty tier, more phases than any
    # instance has today, and an unusually large kill cap.
    s = new_state(lua, State)
    drive(s, [
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
    drive(s2, [
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
    drive(s3, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Incursion [Castle Zvahl Baileys] Seals Broken 2/6",
    ])
    res.check(extra_of(s3).get("Seals Broken") == (2, 6, False),
              "unknown counter dropped: %r" % extra_of(s3))

    drive(s3, ["Incursion [Castle Zvahl Baileys] Seals Broken 6/6"])
    res.check(extra_of(s3).get("Seals Broken") == (6, 6, True),
              "unknown counter did not complete: %r" % extra_of(s3))

    # Several unknown counters coexist rather than overwriting each other.
    drive(s3, ["Incursion [Castle Zvahl Baileys] Braziers Lit 1/3"])
    got = extra_of(s3)
    res.check(got.get("Seals Broken") == (6, 6, True)
              and got.get("Braziers Lit") == (1, 3, False),
              "unknown counters collided: %r" % got)

    # An unknown completion line for a counter we have seen.
    drive(s3, ["Incursion [Castle Zvahl Baileys] Braziers Lit Complete!"])
    res.check(extra_of(s3).get("Braziers Lit") == (3, 3, True),
              "unknown completion not applied: %r" % extra_of(s3))

    # A bonus objective phrased in a new way, with its expiry still understood.
    s4 = new_state(lua, State)
    drive(s4, [
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
    drive(s5, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Bonus Objective: Survive without a KO!",
    ])
    b = s5.snapshot(s5)["bonus"]
    res.check(b is not None and b["label"] == "Survive without a KO!",
              "bonus without an expiry dropped")
    res.check(s5.bonus_remaining(s5) is None, "invented an expiry")

    # Any other instance-tagged line surfaces as a transient note.
    s6 = new_state(lua, State)
    drive(s6, [
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Incursion [Castle Zvahl Baileys] The gate grinds open.",
    ])
    res.check(s6.note(s6) == "The gate grinds open.",
              "unknown status line dropped: %r" % s6.note(s6))

    # An unknown line for a different instance still resets a stale run.
    s7 = new_state(lua, State)
    drive(s7, [
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
    drive(s_ts, [
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
    drive(s8, ["Incursion [Castle Zvahl Baileys] Begins! (Mythic)"])
    before = s8.snapshot(s8)["instance"]
    drive(s8, [
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

    # -- HARD-04: a boon is a full '(<glyph>): <stats>' tail plus a non-blank
    # -- name. An ordinary buff is not a boon.

    # The same raw high-byte run the state suite's boon fixture uses,
    # written as escapes here so an editor cannot quietly normalise it.
    GLYPH = "\u0081\u0098\u0081\u0098"

    res.check(ev("Godwen gains the effect of Protect.") is None,
              "an ordinary buff was listed among the boons picked this run")
    res.check(ev("Godwen gains the effect of Warding Aura (Signet) Attack+5")
              is None,
              "a parenthesised aside with no ': ' after it was listed as a "
              "boon")
    # WR-04. The glyph group may be empty. It is an icon code the parser
    # throws away, and requiring it to be non-empty narrowed only against the
    # server: what separates a boon from an ordinary buff is the tail and the
    # non-blank name, both still demanded below. This matcher has no fallback
    # tier under it the way the ' at ' forms do, so a boon refused here is
    # refused for good -- the server never announces one twice.
    e = ev("Godwen gains the effect of Warding Aura (): Attack+5")
    res.check(e is not None and e["t"] == "boon"
              and e["name"] == "Warding Aura"
              and e["stats"] == "Attack+5",
              "a boon whose glyph group was empty -- which is what the "
              "server's own '%%s gains the effect of %%s (%%s): %%s' template "
              "renders when the icon field is unset -- was dropped, and a "
              "boon dropped here is gone for the rest of the run: %r" % (e,))

    # The ')'-exclusion is the half of HARD-04 that is kept, and this is the
    # line that tells the two halves apart: with a lazy '.-' the glyph group
    # steps over the first ')' and swallows 'Signet) (X', leaving the name as
    # 'Aura' -- a name the server did not send. With '[^)]' it cannot, so the
    # split falls on the last group and the name keeps its own parentheses,
    # the same rule the ' at ' matchers use.
    e = ev("Godwen gains the effect of Aura (Signet) (%s): Attack+5" % GLYPH)
    res.check(e is not None and e["t"] == "boon"
              and e["name"] == "Aura (Signet)"
              and e["stats"] == "Attack+5",
              "the glyph group stepped over a ')' and took part of the boon's "
              "own name with it: %r"
              % ((e and (e["name"], e["stats"])),))
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

    # ---- PERF-01: the cheap gate is a superset of the matchers -----------
    #
    # parser.relevant runs before any allocation, on the raw line, and decides
    # whether a line is ever parsed at all. The two directions are not
    # symmetric and only one of them is a hazard:
    #
    #   a false positive costs one wasted strip_colors on a line that is then
    #   rejected by the anchored gate underneath, and nothing else;
    #
    #   a false negative loses a line the server did send, for good, and looks
    #   exactly like a quiet stretch of chat. Nothing is logged, nothing is
    #   drawn differently, and the window simply stops keeping up.
    #
    # So the rule below is an implication in one direction: everything any
    # matcher accepts, the gate accepts. It is written as an implication over
    # the fixtures rather than as a copied list of expected booleans, so a
    # matcher added later is covered by adding a fixture -- there is no list
    # of answers to forget to extend.
    #
    # The sampling rule is one fixture per distinct SHAPE a matcher can
    # accept, not one per matcher. A matcher carrying an optional group or one
    # of the two-attempt fallback alternations has more than one shape, and
    # each shape gets its own line. Two of them are named here rather than
    # left to sampling, because the whole difference between them is a single
    # optional 's' sitting inside the region a needle would otherwise cover:
    # at the one-minute warning the server sends 'You have 1 minute remaining
    # inside this Incursion.', and a needle carrying the plural would drop the
    # instance clock at the moment the player most needs it.
    SUPERSET = (
        # begin, recover, complete, bonus complete, bonus progress, phase --
        # one shape each, all carrying the Incursion tag.
        "Incursion [Castle Zvahl Baileys] Begins! (Mythic)",
        "Incursion [Castle Zvahl Baileys] Recovering session...",
        "Incursion [Castle Zvahl Baileys] Complete! (Mythic) Time: 48m 44s",
        "Incursion [Castle Zvahl Baileys] Bonus Objective Complete!",
        "Incursion [Castle Zvahl Baileys] Bonus Objective: Demon Pawn 2/5",
        "Incursion [Castle Zvahl Baileys] Phase #12 31/40",
        # objective_kills -- one shape.
        "New Objective: Defeat 40 enemies (Demon Pawn, Demon Knight)",
        # objective_boss -- two shapes: the precise form, whose location is a
        # parenthesised group, and the 1.1.0 fallback, whose location is not.
        "New Objective: Defeat Demon Overlord at (K-7) (Map #4)!",
        "New Objective: Defeat Demon Overlord at the sealed door!",
        # boss_hint -- the same two shapes.
        "(Boss: Demon Overlord at (K-7) (Map #4))",
        "(Boss: Demon Overlord at the sealed door)",
        # the chest bonus -- two shapes, plural and singular expiry.
        "Bonus Objective: Find the hidden chest! (Expires in 10 Minutes)",
        "Bonus Objective: Find the hidden chest! (Expires in 1 Minute)",
        # the count bonus -- the same two.
        "Bonus Objective: Defeat 5 Demon Pawn! (Expires in 10 Minutes)",
        "Bonus Objective: Defeat 5 Demon Pawn! (Expires in 1 Minute)",
        # the named-NM bonus -- four: precise and fallback, each plural and
        # singular.
        "Bonus Objective: Defeat Demon Marshal at (H-9) (Map #2)! "
        "(Expires in 10 Minutes)",
        "Bonus Objective: Defeat Demon Marshal at (H-9) (Map #2)! "
        "(Expires in 1 Minute)",
        "Bonus Objective: Defeat Demon Marshal at the sealed door! "
        "(Expires in 10 Minutes)",
        "Bonus Objective: Defeat Demon Marshal at the sealed door! "
        "(Expires in 1 Minute)",
        # the instance clock -- two shapes, and the singular is the reason
        # this table samples shapes rather than matchers.
        "You have 90 minutes remaining inside this Incursion.",
        "You have 1 minute remaining inside this Incursion.",
        # points -- one shape.
        "Godwen gains 84 incursion points.",
        # boon -- two shapes: a glyph group with something in it, and the
        # empty one WR-04 restored.
        "Godwen gains the effect of Ronin's Revenge (%s): Store TP+8" % GLYPH,
        "Godwen gains the effect of Ronin's Revenge (): Store TP+8",
        # the generic tier: a counter, a completion, a bare note, an unknown
        # objective wording and an unknown bonus wording -- one shape each,
        # and none of them anything the server sends today.
        "Incursion [Castle Zvahl Baileys] Seals Broken 2/6",
        "Incursion [Castle Zvahl Baileys] Braziers Lit Complete!",
        "Incursion [Castle Zvahl Baileys] The gate grinds open.",
        "New Objective: Escort the Cardian to the sealed door at (H-8)!",
        "Bonus Objective: Light all four braziers! (Expires in 7 Minutes)",
        # and the timestamp plugin's prefix, singly and doubled, since the
        # gate runs before any of it is stripped.
        "[22:07:45] You have 90 minutes remaining inside this Incursion.",
        "[22:07:45] [22:07:45] Incursion [Fort Ghelsba] Begins! (Normal)",
    )

    # The antecedent, pinned once: a fixture no matcher accepts would make its
    # implication below vacuously true and prove nothing at all.
    unmatched = [line for line in SUPERSET if parser.parse(line) is None]
    res.check(not unmatched,
              "the superset table holds %d line(s) no matcher accepts, so the "
              "gate checks below prove nothing about them: %s"
              % (len(unmatched), unmatched))

    for line in SUPERSET:
        res.check(bool(parser.relevant(line)),
                  "the server sends this and the parser understands it, but "
                  "the cheap gate drops it before anything is ever parsed, so "
                  "the window would simply stop keeping up: %r" % line)

    # And every invented line this suite drove through the parser above, held
    # to the same implication. A fixture written for some other reason is
    # covered here for free, which is what keeps this honest as the suite
    # grows.
    for line in sorted(set(driven)):
        if parser.parse(line) is None:
            continue
        res.check(bool(parser.relevant(line)),
                  "an invented future line this suite already tracks is "
                  "dropped by the cheap gate before it can be parsed: %r"
                  % line)

    # ---- and the gate says no to ordinary chat --------------------------
    #
    # Not a correctness requirement -- a false positive is free -- but the
    # counter-pin that says the gate is not simply answering yes to
    # everything, which would satisfy every check above and buy nothing.
    ORDINARY = (
        "Godwen hits the Nest Skitterer for 42 points of damage.",
        "The Nest Skitterer misses Godwen.",
        "Godwen uses Fast Blade.",
        "Rialla casts Cure III on Godwen.",
        "Godwen obtains a square of Yagudo cloth.",
        "Rialla >> pulling the next group, hold here a moment",
        "Zsoleara : !incursions",
        "You cannot use that command at this time.",
        "Godwen defeats the Nest Drone.",
        # The two that say the needle is 'Incursion [' and not 'Incursion':
        # chat that names the content, and a currency line that carries it in
        # passing. Both are lines the suite above already drives past the
        # parser; here they have to get past the gate as well.
        "[2]<Larios> LFM Palborough Mines Incursion 5@",
        "You store Orcish Steel x38 (Total: 292) Incursion >> Currencies",
    )
    accepted = [line for line in ORDINARY if parser.parse(line) is not None]
    res.check(not accepted,
              "the rejection table holds %d line(s) the parser does accept, "
              "so the gate is being asked to decline something real: %s"
              % (len(accepted), accepted))
    for line in ORDINARY:
        res.check(not parser.relevant(line),
                  "the cheap gate answers yes to ordinary chat, so it saves "
                  "nothing on the traffic it exists for: %r" % line)

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

    # --- IN-05 / audit G-1, through Ashita's own decoder -------------------
    #
    # '1e999' is a well-formed JSON number that no double can hold, and
    # json.lua answers it with +infinity -- on both dialects, checked below
    # rather than assumed. That is the whole of the reachability argument: the
    # settings file is one a player can hand-edit, and the harness's own stub
    # cannot settle what the real decoder does with an overflowing literal.
    #
    # An infinity is the right *shape* and no value at all, so it reads as a
    # missing key: that field is unknown and the rest of the run survives.
    # Refusing the blob instead would cost the boons, points, phase and
    # elapsed the server never re-announces, which is the harm CR-01 above
    # exists to prevent; keeping the number would put
    # '~-9223372036854775808:...' where the instance clock belongs.
    over = js.decode('{"version":2,"instance":"Davoi","difficulty":"Hard",'
                     '"phase":3,"kills_cur":4,"kills_max":1e999,'
                     '"time_left":1e999,"elapsed":-1e999,'
                     '"boons":[{"name":"A","stats":"x"}],"extra":{}}')
    res.check(nonfinite_fields(lua, over) != "",
              "json.lua no longer decodes '1e999' to an infinity, so this "
              "case no longer stands for the shape it was written for")
    res.check(sorted(nonfinite_fields(lua, over).split(", "))
              == ["elapsed", "kills_max", "time_left"],
              "the decoder put an infinity somewhere other than the three "
              "fields this case writes one into: %r"
              % (nonfinite_fields(lua, over),))

    s12 = new_state(lua, State)
    over_raised = None
    over_took = False
    try:
        over_took = bool(s12.restore(s12, over))
    except Exception as exc:                        # noqa: BLE001
        over_raised = exc
    over_run = s12.snapshot(s12)
    res.check(over_raised is None and over_took and over_run is not None,
              "a hand-edited session carrying '1e999' was not resumed, so "
              "three unreadable numbers cost the player the instance, the "
              "phase, the kills and the boon the same file also named: %s"
              % (over_raised if over_raised is not None
                 else ("refused" if not over_took else "no run was left")))
    res.check(not nonfinite_fields(lua, over_run),
              "a run restored from a '1e999' file still holds %s, which the "
              "window formats into a number the server never sent"
              % (nonfinite_fields(lua, over_run) or "nothing",))
    res.check(over_run is not None
              and over_run["instance"] == "Davoi"
              and over_run["difficulty"] == "Hard"
              and int(over_run["phase"]) == 3
              and int(over_run["kills_cur"]) == 4
              and len(list(over_run["boons"].values())) == 1,
              "a run restored from a '1e999' file came back without the "
              "instance, phase, kill count and boon the unreadable numbers "
              "had nothing to do with")
    res.check(over_run is not None and over_run["kills_max"] is None
              and s12.time_left(s12) is None,
              "an unreadable kill cap or clock was kept rather than read as "
              "unknown: cap %r, clock %r"
              % (over_run["kills_max"] if over_run is not None else None,
                 s12.time_left(s12) if over_run is not None else None))

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
# comment -- ui.lua (`Layout is deliberately dense`) -- before being pasted in.

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
#    do-not-overprint branch, ui.lua (`if target > imgui.GetCursorPosX()`).
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
    # default of 8 -- ui.lua (`local origin_x = 8`) -- and it is only
    # rewritten inside Begin, ui.lua (`origin_x = imgui.GetCursorPosX()`).
    # That is correct for the direct-call tests in this section,
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

    # --- and the memoisation stops growing (PERF-03) ---
    #
    # The cache above is keyed by server text, and the addon lives as long as
    # the client does: nothing about a stat string is bounded by anything the
    # addon controls. Past a stated cap the whole cache is dropped rather than
    # one entry evicted -- boon stat strings are few and repeat every frame,
    # so an LRU would be more code, on the render path, for no gain on real
    # traffic.
    cap_value = L.get("SHORT_CACHE_MAX")
    short_cache = L.get("short_cache")
    forget = ui["forget"]

    res.check(cap_value is not None,
              "shorten()'s memo cache has no stated bound, so it grows for as "
              "long as the client is running")
    res.check(forget is not None,
              "ui.lua exports nothing the shell can call when the run the "
              "cache was built for is gone, so a character's boon text stays "
              "in memory until the client is closed")
    if forget is None:
        def forget():                                        # noqa: F811
            return None

    cap = int(cap_value) if cap_value is not None else 0

    # Measured on the table, never on a counter: a bookkeeping number that has
    # drifted from the cache would otherwise report a bound that is not there.
    forget()
    res.check(table_entries(host, short_cache) == 0,
              "the cache did not start this case empty, so nothing counted "
              "below is this case's doing")

    evicted = "Accuracy+0 / Store TP+0"
    peak, dropped, previous = 0, False, 0
    for i in range(512):
        shorten("Accuracy+%d / Store TP+%d" % (i, i))
        held = table_entries(host, short_cache)
        peak = max(peak, held)
        if held < previous:
            dropped = True
        previous = held

    res.check(cap > 0 and peak <= cap,
              "the memo cache reached %d entries against a stated bound of "
              "%d: keyed by server text, in a process that stays up for a "
              "whole play session" % (peak, cap))
    res.check(dropped,
              "512 distinct stat strings never made the cache drop anything, "
              "so the bound above passed on a cache that simply never filled")

    # A drop costs memoisation. It may never cost correctness.
    res.check(shorten(evicted) == "Acc+0 STP+0",
              "a stat string the drop had evicted came back shortened "
              "wrongly, so the bound is being paid for in what the window "
              "shows: %r" % shorten(evicted))

    # --- and it is cleared in place, not replaced ---
    #
    # ui.lua's file-scope locals are reachable only by upvalue reflection, so
    # a helper that assigned a fresh table would leave the harness holding an
    # orphan and measuring a cache the addon no longer uses. The handle is
    # taken before the call and read after it, which is what makes the two
    # checks below statements about the live cache.
    handle = L["short_cache"]
    shorten("Evasion+10 / Enmity-5")
    res.check(table_entries(host, handle) > 0,
              "nothing reached the cache, so emptying it below would prove "
              "nothing")
    forget()
    res.check(table_entries(host, handle) == 0,
              "the clearing helper replaced the cache table instead of "
              "emptying it, so the handle the harness holds is an orphan and "
              "what it measures is not the cache the addon is using")
    shorten("Fast Cast+5")
    res.check(table_entries(host, handle) == 1,
              "the table the addon memoises into is not the one the harness "
              "reads, so nothing above is a statement about the shipped cache")
    forget()

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
    # it must sit after the text rather than printing on top of it --
    # ui.lua (`if target > imgui.GetCursorPosX()`).
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

    # --- STAT_SHORT's ordering contract, ui.lua (`local STAT_SHORT`) ---

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
        # -- state.lua (`run.objective.stale = true`). The second reconnect
        # is what puts the window
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

    # ui.lua declares origin_x = 8 at file scope -- ui.lua (`local origin_x
    # = 8`) -- and overwrites it inside Begin, ui.lua (`origin_x =
    # imgui.GetCursorPosX()`). The stub's padding is
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

    # --- IN-05 / audit G-1: what a restored non-finite number draws --------
    #
    # The state suite settles what restore() keeps. This settles the half that
    # matters on screen, because the harm was never the value in the record --
    # it was the window drawing it with the same confidence as a real one. The
    # audit drove exactly this path and watched the header row draw
    #
    #     TextColored '~-9223372036854775808:-9223372036854775808:...'
    #
    # under LuaJIT, with right_text silently skipping its SetCursorPosX so the
    # rest of the line lost its alignment too. Under Lua 5.3 and later the
    # same value raises out of string.format, which HARD-01 contains by
    # disabling the window -- so on the shipped dialect the player reads a
    # fabricated clock, and on this harness's default they lose the window.
    #
    # Both dialects are covered by one assertion here: the frame must not
    # raise, and the clock must read as unknown.
    #
    # The two cases differ in what 'unknown' looks like, and deliberately so.
    # An unreadable time_left leaves the addon with no clock at all, which the
    # window already has a mark for. An unreadable saved_at leaves it with a
    # clock and no idea how long it was away -- which is exactly what a blob
    # with no stamp at all leaves it with, and restore() has always read that
    # as no gap. The saved minutes are then still the server's own number,
    # drawn under the '~' that says they are an estimate and beside the
    # 'reconnected - awaiting update' line that says the run is a lower bound.
    for label, field, value, want_clock in (
            ("infinite", "time_left", float("inf"),
             "TextColored dim '--:--'"),
            ("NaN", "saved_at", float("nan"),
             "TextColored text '~1:30:00'")):
        nf_host = make_host()
        nf_parser = nf_host.require("parser")
        NfState = nf_host.require("state")
        nf_ui = nf_host.require("ui")
        nf_color = lua_locals(nf_host, nf_ui.render)["COLOR"]

        nf_host.tick(0)
        source = new_state(nf_host.lua, NfState)
        feed(source, nf_parser, mid_phase)
        blob = source.serialise(source)
        blob[field] = value

        target = new_state(nf_host.lua, NfState)
        res.check(bool(target.restore(target, blob)),
                  "a saved run whose %s was %s was refused outright, so the "
                  "window has nothing to draw and the player has lost the "
                  "run" % (field, label))

        nf_host.imgui.reset()
        nf_raised = None
        try:
            nf_ui.render(target,
                         nf_host.lua.table_from({"visible": True,
                                                 "locked": False}))
        except Exception as exc:                    # noqa: BLE001
            nf_raised = exc
        res.check(nf_raised is None,
                  "drawing a run restored from a %s %s raised inside "
                  "d3d_present (%s) -- the window is disabled for the rest of "
                  "the session and the player is told to type /incursion"
                  % (label, field, nf_raised))
        if nf_raised is not None:
            continue

        nf_balance = nf_host.imgui.balance()
        res.check(all(v == 0 for v in nf_balance.values()),
                  "the frame that drew a %s %s left the ImGui stack "
                  "unbalanced: %r" % (label, field, nf_balance))

        drawn = nf_host.imgui.snapshot(colors=nf_color, measurements=False)
        # Checked case-insensitively and against the value LuaJIT's %d prints
        # for a non-finite double, because the two dialects spell these
        # differently -- '-nan(ind)' against 'nan' -- and neither spelling is
        # a thing the player should ever read.
        garbage = [token for token in ("nan", "inf", "9223372036854775808")
                   if token in drawn.lower()]
        res.check(not garbage,
                  "the window drew %s on a run restored from a %s %s -- a "
                  "number the server never sent, beside numbers it did"
                  % (", ".join(garbage), label, field))
        res.check(want_clock in drawn,
                  "the instance clock did not read %r on a run restored from "
                  "a %s %s; the header drew: %s"
                  % (want_clock, label, field,
                     "; ".join(line.strip() for line in drawn.splitlines()[3:9])))
        res.check("TextColored warn 'reconnected - awaiting update'" in drawn,
                  "a run restored from a %s %s dropped the desync warning, so "
                  "the window presents what it kept as confirmed"
                  % (label, field))

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


# The timestamp loop's own pattern, written as parser.lua writes it. Matched
# as a substring of what is handed to gsub, so the loop is identified by what
# it looks for rather than by how many gsubs happened to run.
TIMESTAMP_PATTERN = "%[%d%d:%d%d:%d%d%]"


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

    # --- and the changelog agrees with the number it reports --------------
    #
    # The version string is a claim made to players on every load, and the
    # changelog is the only thing that says what the claim means. The two
    # drifting apart is exactly the class of quiet wrongness this milestone
    # exists to remove, and this is the cheapest guard against it recurring:
    # the newest heading in CHANGELOG.md must name the version addon.version
    # holds.
    #
    # Noted and skipped rather than failed when the file is absent. The addon
    # folder is installable on its own -- that is how it is distributed -- so a
    # CHANGELOG.md that is not beside it says nothing about the addon. Same
    # rule the persistence suite follows for Ashita's json.lua.
    changelog = os.path.join(os.path.dirname(HERE), "CHANGELOG.md")
    if not os.path.isfile(changelog):
        res.note("skipped: CHANGELOG.md not found beside the addon folder")
    else:
        with open(changelog, "r", encoding="utf-8") as fh:
            headings = re.findall(r"^## +(\S+)", fh.read(), re.M)
        newest = headings[0] if headings else None
        res.check(newest == version,
                  "the addon reports version %r and the newest changelog "
                  "heading names %r, so the build and the record of what is "
                  "in it disagree" % (version, newest))

    # --- the chat handler's pcall boundary ---------------------------------
    #
    # inctrack.lua (`local ok, err = pcall(function ()`).

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

    # --- and it says it once ----------------------------------------------
    #
    # A line the addon cannot read is rarely a one-off: a systematically
    # malformed shape arrives on every chat line the client receives, so an
    # unrated complaint is the same sentence sixty times in a burst, on top of
    # the chat the player was trying to read. Same latch as the render path
    # got in 03-01, and the same recovery: /incursion reset, or a character
    # change.
    #
    # The check above is the counter-pin and stays exactly as it is: the first
    # report is still made, and still exactly once. A guard that swallowed it
    # would be a worse bug than the flood it prevents.
    res.check(any("/incursion reset" in line for line in bad.chat[before:]),
              "the addon went quiet about a line it could not read without "
              "telling the player how to hear about it again: %r"
              % (bad.chat[before:],))

    quiet_from = len(bad.chat)
    bad.fire_text_in(bad.lua.table_from({"also": "not a string"}))
    bad.fire_text_in(bad.lua.table_from({"nor": "this"}))
    res.check(len(bad.chat) == quiet_from,
              "a second unreadable line complained again, so a malformed "
              "shape arriving on every line would bury the player's chat: %r"
              % (bad.chat[quiet_from:],))

    # The way back, both of them. The addon does not export reset(), so this
    # goes through the command handler exactly as the player does.
    bad.fire("command", command="/incursion reset")
    after_reset = len(bad.chat)
    bad.fire_text_in(bad.lua.table_from({"still": "not a string"}))
    res.check(len([line for line in bad.chat[after_reset:]
                   if "parse error" in line]) == 1,
              "/incursion reset is offered as the way back but does not "
              "actually restore the report: %r" % (bad.chat[after_reset:],))

    bad.switch_profile({"session": ""})
    after_switch = len(bad.chat)
    bad.fire_text_in(bad.lua.table_from({"new": "character"}))
    res.check(len([line for line in bad.chat[after_switch:]
                   if "parse error" in line]) == 1,
              "a new character inherited the old one's silence about lines "
              "the addon cannot read: %r" % (bad.chat[after_switch:],))

    # And the failure path still only prints. Not the render latch: a parse
    # error costs one line, not the frame, so nothing is disabled and the next
    # line is still read.
    res.check(shell_run(bad) is None,
              "the report-once guard started resetting or disabling things on "
              "the failure path")
    bad.fire_text_in(begins())
    res.check(shell_run(bad) is not None,
              "an unreadable line stopped the handler reading the next one")

    # Read-only on the ordinary path too. This is the guarantee the comment
    # inctrack.lua (`Read-only. The message is never modified`) makes, and
    # that nothing had tested until this phase.
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

    # --- PERF-01: and 'nothing' now means no allocation either ------------
    #
    # 'Costs nothing' above meant no run, no save and no chat. This is the
    # other half, and it is the half that is paid on every chat line the
    # client receives, forever: the line must be turned away before a string
    # is allocated for it. strip_colors is the shell's own call, so only the
    # shell can decline to make it -- no reordering inside parser.lua reaches
    # this. The gsub counter catches trim and the timestamp loop underneath.
    free = loaded_host()
    free.count_gsub()
    strip_before, gsub_before = free.strip_colors_calls, free.gsub_calls
    free.fire_text_in("Godwen hits the Nest Weevil for 42 points of damage.")
    e_free = free.fire_text_in("Rialla casts Cure III on Godwen.")
    res.check(free.strip_colors_calls == strip_before,
              "a chat line that is none of the addon's business still paid "
              "for a colour strip -- two gsubs and two allocations, on the "
              "game thread, on every line in a crowded zone")
    res.check(free.gsub_calls == gsub_before,
              "a chat line that is none of the addon's business still ran "
              "%d gsub(s): the trim and the timestamp loop are still being "
              "paid for on traffic the addon ignores"
              % (free.gsub_calls - gsub_before))
    res.check(e_free["message"] == "Rialla casts Cure III on Godwen."
              and e_free["message_modified"] is None
              and e_free["blocked"] is None,
              "the early return rewrote or swallowed the line it declined")

    # The counter-pin. Every check above is satisfied by a gate that says no
    # to everything, and a gate that says no to everything is the silent-drop
    # failure this whole design exists to prevent.
    busy = loaded_host()
    busy.count_gsub()
    strip_before, gsub_before = busy.strip_colors_calls, busy.gsub_calls
    busy.fire_text_in(begins())
    res.check(busy.strip_colors_calls > strip_before
              and busy.gsub_calls > gsub_before,
              "a line the addon does care about was turned away by the gate "
              "as cheaply as one it does not, which means it was not parsed")
    res.check(shell_run(busy) is not None,
              "the line that starts a run no longer starts one")

    # --- a colour code makes the gate decline to judge --------------------
    #
    # The gate runs on the raw message, before strip_colors, and Ashita's
    # colour codes are a marker byte plus one payload byte that can land
    # anywhere -- including between two characters of one of the gate's own
    # needles. So a coloured line is one the gate is not entitled to judge and
    # declines to: it costs exactly what it cost before this change, and never
    # more. That is what makes a false negative impossible rather than
    # unlikely.
    tinted = loaded_host()
    tinted.count_gsub()
    strip_before = tinted.strip_colors_calls
    chat_before = len(tinted.chat)
    tinted.fire_text_in(CC_A + "Godwen hits the Nest Weevil for 42 points "
                               "of damage.")
    res.check(tinted.strip_colors_calls > strip_before,
              "a coloured line was judged on its raw bytes instead of being "
              "let through, which is how a real line gets dropped for a code "
              "sitting inside a needle")
    res.check(shell_run(tinted) is None and len(tinted.chat) == chat_before,
              "a coloured combat line invented a run or reached the player's "
              "chat -- the anchored rejection underneath stopped working")

    # The safety pin for the whole design: a code inside a needle. Stripped,
    # this is an ordinary 'Begins!' line; raw, the marker sits in the middle
    # of 'Incursion [' and every plain search for it answers no.
    #
    # Once per marker byte, and that is the point rather than thoroughness for
    # its own sake. This pin ran on 0x1F alone for the whole of Phase 4 while
    # the gate read only 0x1E and 0x1F -- so it could not see that 0x7F, which
    # `strip_colors` also removes, was missing from the gate. A pin that
    # exercises a subset of the host's markers proves the gate is a superset
    # of that subset and nothing more. The corpus cannot help: Ashita's log
    # writer strips codes on the way to disk, so all 2.9M recorded lines carry
    # none of the three.
    for marker, label in ((CC_A, "0x1E"), (CC_B, "0x1F"), (CC_C, "0x7F")):
        hidden = begins()
        split = hidden.index("Incursion ") + 5
        hidden = hidden[:split] + marker + hidden[split:]
        res.check(all(needle not in hidden
                      for needle in ("Incursion [", "New Objective: ",
                                     "Bonus Objective: ", "(Boss: ")),
                  "the %s fixture does not actually hide the needle, so the "
                  "check below would pass with the colour fall-through "
                  "removed: %r" % (label, hidden))
        coded = loaded_host()
        coded.fire_text_in(hidden)
        res.check(shell_run(coded) is not None,
                  "a %s colour code landing inside one of the gate's needles "
                  "lost the line that starts a run -- silently, with the "
                  "window simply never appearing" % label)

    # --- the timestamp loop only runs for a line that carries a stamp -----
    #
    # A gsub apiece, on every line, for a prefix that almost never appears.
    # Two fresh hosts doing identical work but for the stamp, so the
    # difference between their counters is the loop and nothing else.
    plainly, stamped = loaded_host(), loaded_host()
    plainly.count_gsub()
    stamped.count_gsub()
    plain_before, stamp_before = plainly.gsub_calls, stamped.gsub_calls
    plainly.fire_text_in(begins())
    stamped.fire_text_in("[22:07:45] " + begins())
    plain_cost = plainly.gsub_calls - plain_before
    stamp_cost = stamped.gsub_calls - stamp_before
    res.check(shell_run(plainly) is not None and shell_run(stamped) is not None
              and shell_run(plainly)["instance"] == shell_run(stamped)["instance"],
              "a timestamp plugin's prefix changed what the window shows")
    res.check(stamp_cost > plain_cost,
              "the stamped line cost no more than the unstamped one (%d vs "
              "%d gsubs), so either the loop runs for both or it runs for "
              "neither" % (stamp_cost, plain_cost))

    # And the half a difference in totals cannot see. ROADMAP Phase 4
    # criterion 2 asks for three things; this is its third clause, and it is
    # the one the two totals above are blind to. The loop's guard --
    # parser.lua (`if s:byte(1) == LBRACKET then`) -- is behaviour-neutral to
    # remove: the pattern it runs is ^-anchored, so on a line that carries no
    # stamp the ungated loop finds nothing, breaks immediately and returns the
    # same event. Every check in this file stays green, and every line the
    # client receives pays one more gsub forever. The difference above stays
    # positive too, merely narrowing from two to one.
    #
    # So the claim is asserted directly instead: on a line the addon does
    # parse, and which does not start with '[', the timestamp pattern is not
    # handed to gsub at all. Counted by the pattern rather than by the total,
    # which is what makes zero mean "did not run" instead of "ran and found
    # nothing".
    plain_loop = plainly.gsub_calls_matching(TIMESTAMP_PATTERN)
    stamp_loop = stamped.gsub_calls_matching(TIMESTAMP_PATTERN)
    res.check(plain_loop == 0,
              "a line with no timestamp ran the timestamp loop %d time(s) "
              "anyway: the gate on the leading '[' is gone, so every chat "
              "line the client receives now pays a gsub to strip a prefix it "
              "does not carry" % plain_loop)
    res.check(stamp_loop > 0,
              "the stamped line did not run the timestamp loop either, so "
              "the check above is passing because nothing is being measured "
              "rather than because the gate works")

    # --- the write policy: decided here, written from the frame (PERF-02) --
    #
    # persist() serialises the run, encodes it as JSON and calls
    # settings.save() -- disk I/O -- and until this phase all of that ran
    # inside text_in, on the game thread, on the line that triggered it: every
    # boon, every objective, every boss hint, every phase boundary, in the
    # middle of combat chat.
    #
    # The *decision* has not moved and is unchanged: an event the server never
    # repeats is owed a write the moment it lands, a kill count rides the
    # five-second throttle. Only the write moved, onto the frame handler that
    # already runs sixty times a second. So every site below is asserted
    # twice -- nothing written yet, then written after one frame -- because
    # 'fewer writes on the chat thread' is not the claim. Zero is.
    saver = loaded_host()
    res.check(saver.saves == 0,
              "loading with nothing saved still wrote to disk")

    saver.fire_text_in(begins())
    res.check(saver.saves == 0,
              "the start of a run went to disk on the chat thread, on the "
              "line that delivered it -- a synchronous write in the middle of "
              "combat chat (%d writes)" % saver.saves)
    saver.fire("d3d_present")
    res.check(saver.saves == 1,
              "the start of a run was never written down at all, so a reload "
              "a moment later comes back blank (%d writes)" % saver.saves)

    # The flag is consumed, not sampled.
    saver.fire("d3d_present")
    res.check(saver.saves == 1,
              "an idle frame with nothing new wrote the run again, so the "
              "addon touches the disk sixty times a second (%d writes)"
              % saver.saves)

    # The policy the player experiences, measured across frames rather than on
    # the line, so what is asserted is the policy and not the disk.
    saver.fire_text_in(phase_line(1, 3))
    saver.fire("d3d_present")
    res.check(saver.saves == 1,
              "a kill count arriving a moment after a saved event still "
              "earned its own disk write (%d writes)" % saver.saves)

    saver.tick(6.0)
    saver.fire_text_in(phase_line(1, 3))
    res.check(saver.saves == 1,
              "a kill count past the throttle window was written on the chat "
              "thread instead of on the next frame (%d writes)" % saver.saves)
    saver.fire("d3d_present")
    res.check(saver.saves == 2,
              "a kill count past the throttle window was never written down "
              "(%d writes)" % saver.saves)

    saver.fire_text_in(SHELL_BOON)
    res.check(saver.saves == 2,
              "a boon went to disk on the chat thread, on the line that "
              "delivered it (%d writes)" % saver.saves)
    saver.fire("d3d_present")
    res.check(saver.saves == 3,
              "a boon -- which the server never announces again -- was left "
              "unwritten because a kill count had just been saved (%d writes)"
              % saver.saves)

    res.check(saver.sessions[-1] != "",
              "the run was 'saved' as an empty string, so a reload would come "
              "back blank")
    blob = saver.json.decode(saver.sessions[-1])
    res.check(blob is not None and blob["instance"] == SHELL_INSTANCE,
              "what the frame wrote does not name the instance the player is "
              "standing in: %r" % (saver.sessions[-1],))

    # --- the flush runs on frames that draw nothing (PERF-02) -------------
    #
    # d3d_present returns early twice: once when the window latched itself off
    # after a render error, and again when it is simply not on screen. A
    # player running with automatic show/hide off is still playing the run,
    # and so is one whose window latched off -- so a flush below either return
    # would mean their run is never written down at all. That is the single
    # easiest way to get this deferral wrong, so both returns are pinned.
    hidden_run = loaded_host()
    hidden_run.settings["auto"] = False
    hidden_run.fire_text_in(begins())
    hidden_run.fire_text_in(SHELL_MOBS)
    res.check(hidden_run.addon["visible"]() is False,
              "the fixture is not actually hiding the window, so the check "
              "below would pass with the flush sitting under the visibility "
              "return and would prove nothing")
    saves_before = hidden_run.saves
    hidden_run.fire("d3d_present")
    res.check(hidden_run.saves == saves_before + 1,
              "a player with automatic show/hide off never has their run "
              "written down: the window is off screen, the frame returned "
              "before the flush, and the whole Incursion is lost on a reload")
    # Guarded rather than indexed straight: when the flush is misplaced there
    # is no written session at all, and this check has to be able to go red
    # about it rather than raise and take the rest of the suite with it.
    res.check(bool(hidden_run.sessions) and hidden_run.sessions[-1] != "",
              "the frame that drew no window wrote nothing, or wrote an empty "
              "run over the Incursion in progress: %r"
              % (hidden_run.sessions[-1:],))

    latched = loaded_host()
    latched.fire_text_in(begins())
    latched.fire("d3d_present")
    latched.addon["incursion"]["render_off"] = True
    latched.fire_text_in(SHELL_MOBS)
    saves_before = latched.saves
    latched.fire("d3d_present")
    res.check(latched.saves == saves_before + 1,
              "a window that switched itself off after a render error stopped "
              "writing the run down too, so one render fault quietly became a "
              "lost Incursion")

    # --- a disk that refuses the write (CR-02) ----------------------------
    #
    # persist() serialises the run, encodes it -- and that encode was the only
    # part ever protected -- and then calls settings.save(), Ashita's
    # synchronous disk write. When PERF-02 moved the call out of text_in's
    # pcall it landed at the top of d3d_present with nothing around it, above
    # the pcall that contains the render. A read-only settings file or a file
    # another process has open therefore raised straight out of the frame
    # handler, onto the game thread every addon in the process shares: the
    # exact failure the render latch and the whole stack-repair apparatus
    # exist to prevent, and it skipped the render for that frame, told the
    # player nothing, dropped the write with the flag already consumed, and
    # did it again on every subsequent owed write.
    #
    # Nothing here could be provoked before: the stub's save could not fail.
    def frame_escape(host):
        """Drive one d3d_present; return the error text if it got out."""
        try:
            host.fire("d3d_present")
        except Exception as exc:                          # noqa: BLE001
            return str(exc).splitlines()[0]
        return None

    faulty = loaded_host()
    faulty.fire_text_in(begins())
    faulty.fail_saves()
    res.check(faulty.addon["incursion"]["save_due"] is True,
              "the fixture owes no write, so the frame below would take the "
              "flush branch not at all and prove nothing")
    attempts_before = faulty.save_attempts
    wrote_before = faulty.saves
    chat_before = len(faulty.chat)
    faulty.imgui.reset()

    escaped = frame_escape(faulty)
    res.check(escaped is None,
              "a refused disk write threw out of d3d_present and into the "
              "game thread every addon shares: %s" % escaped)
    res.check(faulty.save_attempts > attempts_before,
              "the frame never even tried the write it was owed, so the "
              "check above passed for the wrong reason")
    res.check(faulty.saves == wrote_before,
              "the fixture's disk did not actually refuse the write, so "
              "nothing below is measuring a failure")
    res.check("Begin" in [name for name, _ in faulty.imgui.calls],
              "a refused disk write cost the frame its window: the flush "
              "sits above the render, so a raise there blanks a window that "
              "has nothing wrong with it")

    said = faulty.chat[chat_before:]
    res.check(len(said) == 1,
              "a refused disk write produced %d chat lines; every other "
              "failure path in this addon says its piece exactly once"
              % len(said))
    res.check(any("read-only" in line for line in said),
              "the player was told a write failed but not what the host "
              "said about it: %r" % (said,))
    res.check(any("100%" in line for line in said),
              "the host's error text lost its percent sign on the way to "
              "chat, which means it was pasted into the format string "
              "instead of passed as an argument: %r" % (said,))
    res.check(any("/incursion reset" in line for line in said),
              "the player was told a write failed and not how to hear about "
              "it again: %r" % (said,))

    # Bounded, in both directions. Not dropped -- the flag goes back, because
    # a run that is owed a write and never gets one comes back blank on the
    # next reload. Not retried every frame either: a persistent fault would
    # otherwise serialise, encode and fail sixty times a second on the game
    # thread, which is the cost deferring the write existed to avoid.
    res.check(faulty.addon["incursion"]["save_due"] is True,
              "a refused write was dropped with the flag already consumed, "
              "so nothing retries it and the run stays unwritten until some "
              "later chat event happens to owe another one")
    attempts_before = faulty.save_attempts
    chat_before = len(faulty.chat)
    for _ in range(4):
        res.check(frame_escape(faulty) is None,
                  "a second frame with a refused write escaped the handler")
    res.check(faulty.save_attempts == attempts_before,
              "a persistent disk fault was retried on every frame: %d "
              "attempts across four frames, on the game thread"
              % (faulty.save_attempts - attempts_before))
    res.check(len(faulty.chat) == chat_before,
              "the report-once latch did not hold: a persistent fault said "
              "its piece %d more times" % (len(faulty.chat) - chat_before))

    # Past the retry window it tries again, and when the disk comes back the
    # run is written down -- the write was deferred, not discarded.
    faulty.tick(6.0)
    attempts_before = faulty.save_attempts
    res.check(frame_escape(faulty) is None,
              "the retry frame escaped the handler")
    res.check(faulty.save_attempts > attempts_before,
              "the write was never retried at all past its window, so it was "
              "dropped after all -- only more slowly")

    faulty.heal_saves()
    faulty.tick(12.0)
    faulty.fire("d3d_present")
    res.check(faulty.saves > wrote_before,
              "the run was never written down once the disk came back, so a "
              "transient fault cost the whole Incursion")
    res.check(faulty.addon["incursion"]["save_due"] is False,
              "the flag stayed set after a write that landed, so the addon "
              "now writes on every frame")
    # Guarded rather than indexed straight, for the same reason the hidden-run
    # check above is: when the containment is missing there is no written
    # session at all, and these two have to be able to go red about it rather
    # than raise and take every check in this suite down with them.
    written = faulty.sessions[-1] if faulty.sessions else ""
    res.check(written != "",
              "what finally reached disk was empty, or nothing reached it: %r"
              % (faulty.sessions[-1:],))
    blob = faulty.json.decode(written) if written else None
    res.check(blob is not None and blob["instance"] == SHELL_INSTANCE,
              "what finally reached disk does not name the instance the "
              "player is standing in: %r" % (written,))

    # And the latch has the same way back as the other two. Healed first:
    # reset() writes as well, and this is about hearing the complaint again,
    # not about a second failure path.
    res.check(faulty.addon["incursion"]["save_told"] is True,
              "the report-once latch was never set, so the single chat line "
              "above was a coincidence")
    faulty.fire("command", command="/incursion reset")
    res.check(faulty.addon["incursion"]["save_told"] is False,
              "/incursion reset clears the render and parse latches and not "
              "this one, so a player who has heard about a disk fault once "
              "has no way to hear about it again")

    # --- an unload straight after a burst loses nothing -------------------
    #
    # The unload path is the one that cannot wait for a frame, and its
    # unconditional write is what makes deferring every other write safe at
    # all. No frame runs between the burst and the unload here, deliberately.
    leaving = loaded_host()
    leaving.fire_text_in(begins())
    leaving.fire_text_in(phase_line(2, 4))
    leaving.fire_text_in(SHELL_MOBS)
    leaving.fire_text_in(SHELL_BOON)
    res.check(leaving.saves == 0,
              "the burst wrote to disk on the chat thread after all "
              "(%d writes)" % leaving.saves)
    leaving.fire("unload")
    res.check(leaving.saves == 1,
              "unloading straight after a burst, with no frame in between, "
              "wrote nothing at all: the whole run is gone (%d writes)"
              % leaving.saves)
    res.check(leaving.settings["session"] != "",
              "unloading mid-run left nothing to come back to")

    came_back = loaded_host(profile={"session": leaving.settings["session"]})
    back = shell_run(came_back)
    res.check(back is not None and back["instance"] == SHELL_INSTANCE,
              "a run unloaded straight after a burst did not come back at all")
    res.check(back is not None and int(back["phase"]) == 2,
              "the run came back on the wrong phase: %r"
              % (back["phase"] if back is not None else None,))
    first_boon = back["boons"][1] if back is not None else None
    res.check(first_boon is not None and first_boon["stats"] is not None,
              "the boon picked a heartbeat before the unload was lost, which "
              "is exactly the event the server never announces again")

    # And an unload with nothing owed still writes. The throttle means the
    # copy on disk can be up to five seconds behind the run the player is
    # watching, and the unload is the last chance to catch up -- which is why
    # it does not consult the flag. A kill count inside the throttle window
    # is precisely that case, and it is the one that tells an unconditional
    # write from a conditional one.
    settling = loaded_host()
    settling.fire_text_in(begins())
    settling.fire_text_in(phase_line(3, 7))
    settling.fire("d3d_present")
    written = settling.json.decode(settling.sessions[-1])
    res.check(written is not None and int(written["kills_cur"]) == 7,
              "the frame wrote the run without the kill count it was holding "
              "at the time: %r" % (settling.sessions[-1],))

    settling.fire_text_in(phase_line(3, 11))
    saves_before = settling.saves
    settling.fire("unload")
    res.check(settling.saves == saves_before + 1,
              "unloading with a throttled kill count outstanding wrote "
              "nothing at all (%d writes)" % (settling.saves - saves_before))
    final = settling.json.decode(settling.sessions[-1])
    res.check(final is not None and int(final["kills_cur"]) == 11,
              "the run came back to the kill count it had five seconds "
              "earlier: the unload wrote only what a frame had already "
              "written, so everything the throttle was holding is gone: %r"
              % (settling.sessions[-1],))

    # --- a cleared run leaves nothing owed --------------------------------
    #
    # A write marked before the clear must not land after it: reset() has just
    # emptied the session string itself, so a pending flush would put the run
    # straight back over it.
    cleared = loaded_host()
    cleared.fire_text_in(begins())
    cleared.fire("command", command="/incursion reset")
    saves_before = cleared.saves
    cleared.fire("d3d_present")
    res.check(cleared.saves == saves_before,
              "a frame after /incursion reset wrote a run back over the "
              "session the player had just cleared (%d writes)"
              % (cleared.saves - saves_before))
    res.check(cleared.settings["session"] == "",
              "the run the player cleared came back on the next frame: %r"
              % (cleared.settings["session"],))

    # And a character change, which does its own clearing rather than calling
    # reset(). A write owed by the old character must not land in the new
    # character's settings.
    swapped = loaded_host()
    swapped.fire_text_in(begins())
    swapped.switch_profile({"session": ""})
    saves_before = swapped.saves
    swapped.fire("d3d_present")
    res.check(swapped.saves == saves_before,
              "a frame after a character change wrote the previous "
              "character's run into the new character's settings (%d writes)"
              % (swapped.saves - saves_before))
    res.check(swapped.settings["session"] == "",
              "the new character's settings came back holding the previous "
              "character's Incursion: %r" % (swapped.settings["session"],))

    # --- the frame handler allocates nothing (PERF-02) --------------------
    #
    # ui.render reads two fields off its options table and keeps no handle on
    # it -- passed, read, dropped -- so building a fresh one sixty times a
    # second is pure GC churn, which is why ui.lua already hoists its own
    # per-frame argument tables. One hoisted table, one field rewritten per
    # frame; the other is fixed because the handler has already returned above
    # when the window is not on screen.
    frames = loaded_host()
    frames.fire_text_in(begins())
    frames.fire_text_in(phase_line(1, 3))
    opts = frames.addon.get("FRAME_OPTS")
    res.check(opts is not None,
              "the frame handler still builds a fresh options table every "
              "frame, sixty times a second, for a function that reads two "
              "fields off it and drops it")
    res.check(opts is not None and opts["visible"] is True,
              "the hoisted options table does not ask for a visible window, "
              "so the frame that reached render drew nothing: %r"
              % (opts["visible"] if opts is not None else None,))

    frames.fire("command", command="/incursion lock")
    frames.imgui.reset()
    frames.fire("d3d_present")
    locked_begins = [args for n, args in frames.imgui.calls if n == "Begin"]
    res.check(len(locked_begins) == 1,
              "the locked frame opened %d windows, so nothing below is a "
              "statement about the one window this addon draws"
              % len(locked_begins))
    locked_flags = (stubs.window_flags(locked_begins[0][2])
                    if locked_begins else [])
    res.check("NoMove" in locked_flags,
              "/incursion lock no longer reaches the window: the one field "
              "the hoisted table rewrites each frame stopped being written, "
              "so the drag lock is dead. Flags that reached Begin: %s"
              % ("|".join(locked_flags) or "none"))

    frames.fire("command", command="/incursion lock")
    frames.imgui.reset()
    frames.fire("d3d_present")
    free_begins = [args for n, args in frames.imgui.calls if n == "Begin"]
    free_flags = (stubs.window_flags(free_begins[0][2])
                  if free_begins else [])
    res.check(bool(free_begins) and "NoMove" not in free_flags,
              "unlocking the window left it locked, so the hoisted table was "
              "written once and never again. Flags that reached Begin: %s"
              % ("|".join(free_flags) or "none"))

    # --- the boon memo goes when the run does (PERF-03) -------------------
    #
    # Through the real command and the real profile callback, with a frame
    # drawn first so there is something in the cache to lose. The cache is a
    # file-scope local in ui.lua, reached the only way it can be reached.
    caching = loaded_host()
    cache_ui = caching.require("ui")
    boon_cache = lua_locals(caching, cache_ui.render).get("short_cache")
    res.check(boon_cache is not None,
              "the boon shorthand cache is no longer reachable, so nothing "
              "below is a statement about what the addon holds in memory")
    caching.fire_text_in(begins())
    caching.fire_text_in(SHELL_BOON)
    caching.fire("d3d_present")
    res.check(boon_cache is not None and table_entries(caching, boon_cache) > 0,
              "the frame drew the boon row without memoising anything, so "
              "the clearing checks below would pass on an empty cache")
    caching.fire("command", command="/incursion reset")
    res.check(boon_cache is not None
              and table_entries(caching, boon_cache) == 0,
              "the boon text of a run the player cleared is still held in "
              "memory, and stays there for as long as the client is running")

    swapping = loaded_host()
    swap_ui = swapping.require("ui")
    swap_cache = lua_locals(swapping, swap_ui.render).get("short_cache")
    swapping.fire_text_in(begins())
    swapping.fire_text_in(SHELL_BOON)
    swapping.fire("d3d_present")
    res.check(swap_cache is not None
              and table_entries(swapping, swap_cache) > 0,
              "the frame drew the boon row without memoising anything, so "
              "the character-change check below would prove nothing")
    swapping.switch_profile({"session": ""})
    res.check(swap_cache is not None
              and table_entries(swapping, swap_cache) == 0,
              "one character's boon text was still in memory after they "
              "logged out and another character logged in")

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
    # A discard is reported, and reported as a discard: not as a fault, not
    # as a resume. The player is the only one who can tell "your run is gone"
    # from "the HUD has not caught up yet", and the difference is a whole
    # Incursion's boons and points.
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

    # WR-05. Silence here is not neutral. The HUD comes back with nothing,
    # and the next Incursion-tagged line bootstraps a fresh run: phase nil,
    # phases_cleared 0, elapsed counting from zero, and no 'reconnected --
    # awaiting update' marking on any of it, because a bootstrapped run is
    # not a desynced one. That is a window full of numbers the server never
    # sent, unmarked.
    bent_told = ([line for line in bent.chat if "could not be resumed" in line]
                 if bent is not None else [])
    res.check(len(bent_told) == 1,
              "a saved run was thrown away on load and the player was told "
              "%d times, not once -- what they see instead is a HUD that "
              "came back empty for no stated reason: %r"
              % (len(bent_told), bent.chat if bent is not None else None))

    # And the one refusal that is not a loss stays quiet. restore() turns a
    # finished run away on purpose -- there is nothing left to resume -- and
    # every completed Incursion leaves exactly such a blob behind, so
    # complaining here would put a false alarm on every login after a run.
    done = loaded_host()
    done.fire_text_in(begins())
    done.fire_text_in(phase_line(1, 3))
    done.fire_text_in("Incursion [%s] Complete! (Normal) Time: 48m 44s"
                      % SHELL_INSTANCE)
    done.fire("unload")
    res.check(done.settings["session"] != "",
              "the finished run was never written down, so the case below is "
              "not the case it was written for")
    after_done = loaded_host(profile={"session": done.settings["session"]})
    res.check(not [line for line in after_done.chat
                   if "could not be resumed" in line],
              "logging in after finishing an Incursion complained that a run "
              "could not be resumed, when nothing was lost: %r"
              % (after_done.chat,))
    res.check(shell_run(after_done) is None,
              "a finished run was resumed on the next load")
    res.check(after_done.settings["session"] == "",
              "the finished run was kept and will be retried on every load")

    # The profile-switch path answers the same way: it is the same loss, on a
    # path a player reaches by logging in on a character mid-run.
    told = loaded_host()
    told.fire_text_in(begins())
    chat_before = len(told.chat)
    told.switch_profile({"session": WRONG_SHAPE})
    said = [line for line in told.chat[chat_before:]
            if "could not be resumed" in line]
    res.check(len(said) == 1,
              "a character change whose saved run could not be read said "
              "nothing about it: the new character's HUD came up empty with "
              "no reason given (%r)" % (told.chat[chat_before:],))
    res.check(told.settings["session"] == "",
              "the unusable run carried over to the new profile and will be "
              "retried on every load: %r" % (told.settings["session"],))

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
    # the window's manual show/hide path -- inctrack.lua
    # (`incursion.override = not visible()`). That belongs to the command
    # section below and to the ui suite, and a second entry for it here would
    # say nothing either of them does not already.

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

    # --- WR-03: the repair's own lookups run inside their pcalls -----------
    #
    # `pcall(imgui.End)` evaluates imgui.End *before* pcall is entered. In
    # Ashita imgui is a constants table whose __index is
    # AshitaCore:GetGuiManager(), so that read is a live call into the GUI
    # manager and can raise on its own -- and a raise from it is outside the
    # pcall that was written to contain it, so it escapes d3d_present into
    # the game thread every addon shares. That is the second error of the
    # frame the block comment says can never happen.
    #
    # The recorder is an ordinary table and cannot produce this on its own,
    # so the stub models it: arm_lookup_fault lifts the entry point out of
    # the table and raises from the read. It asserts nothing about how
    # Ashita's binding behaves; it puts the raise where the language puts it.

    for entry in ("End", "PopStyleVar"):
        lookup = loaded_host()
        lookup.fire_text_in(begins())
        lookup.fire_text_in(phase_line(1, 3))
        lookup.fire_text_in(SHELL_MOBS)

        # A clean frame first, which is what earns the repair at all: with
        # render_ok unset the shell repairs nothing and the lookup is never
        # reached.
        lookup.imgui.reset()
        one_frame(lookup)
        res.check("Begin" in drawn_names(lookup),
                  "no clean frame was drawn before the %s case, so the "
                  "repair below is never attempted and the case proves "
                  "nothing" % entry)

        shell_run(lookup)["objective"]["mobs"][1] = True
        lookup.imgui.reset()
        lookup.imgui.arm_lookup_fault(entry)
        chat_before = len(lookup.chat)
        escaped = one_frame(lookup)

        res.check(escaped is None,
                  "the stack repair's own lookup of imgui.%s raised outside "
                  "its pcall and threw out of d3d_present, into the game "
                  "thread every addon shares -- the second error of the "
                  "frame the handler exists to prevent: %s" % (entry, escaped))
        res.check(entry not in drawn_names(lookup),
                  "imgui.%s was called, so the lookup never raised and this "
                  "case is green without having been asked anything: %r"
                  % (entry, drawn_names(lookup)))
        res.check(lookup.addon["incursion"]["render_off"] is True,
                  "a lookup that raised during the repair left the window "
                  "switched on, so the same failure repeats every frame")
        said = lookup.chat[chat_before:]
        res.check(len(said) == 1 and "/incursion" in said[0],
                  "a repair whose lookup raised swallowed the one line that "
                  "tells the player what happened and how to get the window "
                  "back: %r" % (said,))

    # --- WR-02: the recovery path the error message advertises -------------
    #
    # The error line names /incursion as the way back, so what /incursion
    # does next is the last thing standing between a render failure and a
    # player with no HUD. A player running with automatic show/hide off has
    # override = true -- that is the only reason they can see the window at
    # all -- and dropping it back to automatic visibility on the way out of
    # the failure puts the window straight back off screen while the chat
    # line says it is back.

    manual = loaded_host()
    manual.fire_text_in(begins())
    manual.fire_text_in(phase_line(1, 3))
    manual.settings["auto"] = False                   # automatic show/hide off
    manual.addon["incursion"]["override"] = True      # shown by hand

    manual.imgui.reset()
    one_frame(manual)
    res.check("Begin" in drawn_names(manual),
              "the fixture never had a window on screen, so the recovery "
              "below is not being asked the question it was written for")

    manual.imgui.arm_fault("PushStyleVar")
    one_frame(manual)
    res.check(manual.addon["incursion"]["render_off"] is True,
              "the render failure was not latched, so the recovery path "
              "below is never reached")

    chat_before = len(manual.chat)
    manual.fire("command", command="/incursion")
    said = manual.chat[chat_before:]
    manual.imgui.reset()
    escaped = one_frame(manual)
    drew = "Begin" in drawn_names(manual)

    res.check(escaped is None and drew,
              "/incursion after a render error left the window off screen "
              "for a player running with automatic show/hide off, on the one "
              "recovery path the error message itself names")
    res.check(len(said) == 1,
              "re-enabling the window said %d things instead of one: %r"
              % (len(said), said))
    res.check(bool(said) and ("hidden" not in said[0]) == drew,
              "the chat line and the screen disagree: chat said %r and the "
              "next frame drew %s -- a line that states something untrue "
              "about what is on screen is the core value inverted"
              % (said, "a window" if drew else "nothing"))

    # The other side of the same rule. Here there is nothing to bring the
    # window back -- no manual show, and automatic show/hide off -- so the
    # line must not claim there is.
    stayed = loaded_host()
    stayed.fire_text_in(begins())
    stayed.fire_text_in(phase_line(1, 3))
    stayed.addon["incursion"]["render_off"] = True
    stayed.settings["auto"] = False
    chat_before = len(stayed.chat)
    stayed.fire("command", command="/incursion")
    said = stayed.chat[chat_before:]
    stayed.imgui.reset()
    one_frame(stayed)
    drew = "Begin" in drawn_names(stayed)
    res.check(not drew,
              "the fixture drew a window it had no reason to, so the line "
              "below is not being held to anything")
    res.check(bool(said) and "hidden" in said[0]
              and "/incursion" in said[0],
              "the window stayed hidden and the player was told it was back, "
              "with no word on what to do next: %r" % (said,))

    return res


# --------------------------------------------------------------------------
# 11. the record: what the source and the docs say about themselves
# --------------------------------------------------------------------------

REPO = os.path.dirname(HERE)

# English number words, up to as far as anything here counts. Written out
# rather than digits because that is how the prose in these files reads, and
# the point of this suite is to check the prose.
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}


def repo_text(*parts):
    """One repository file, as text."""
    with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_record(parser):
    """The claims the source and the docs make about themselves.

    Every check here is of the form "the file says N and the file is M": a
    counted fact stated in prose, checked against the thing it counts. This
    suite exists because Phase 4's review found three provably wrong
    statements in documentation the phase claimed as a deliverable, and one of
    them had already been "fixed" once -- verified by grepping for the old
    wording and finding none, a check that cannot tell a right answer from a
    differently wrong one.

    Nothing here greps for a phrase that must be absent. Every check derives
    the true number and compares.
    """
    res = Result("record: what the source and the docs say about themselves")

    parser_src = repo_text("inctrack", "parser.lua")

    # --- the module header names every function the module exports --------
    #
    # parser.relevant is called directly from the shell's chat handler, not
    # only through parse, so a header that names one entry point sends a
    # reader looking for the coupling in the wrong place -- which is exactly
    # where CR-01 lived.
    exported = sorted(k for k in parser.keys())
    header = parser_src.split("]]--", 2)[1] if "]]--" in parser_src else ""
    missing = [name for name in exported
               if ("parser." + name) not in header]
    res.check(not missing,
              "parser.lua's module header does not name %s, which the module "
              "exports: a reader who trusts the header does not know every "
              "way into this file" % ", ".join("parser." + n for n in missing))

    stated = re.search(r"No Ashita dependency, no state\. (\w+) functions?:",
                       parser_src)
    res.check(stated is not None
              and NUMBER_WORDS.get(stated.group(1).lower()) == len(exported),
              "parser.lua's header says it has %r functions and it exports "
              "%d (%s)"
              % (stated.group(1) if stated else None,
                 len(exported), ", ".join(exported)))

    # --- what a 'no' from the gate costs ----------------------------------
    #
    # A cost claim, in a phase whose subject is cost, in the one function
    # whose budget is the argument for its existence. It said seven while the
    # marker searches in front of the needles brought it to nine, and CR-01's
    # third marker brings it to ten. Counted from the function body rather
    # than believed, and the split is counted too: a marker search is the one
    # whose literal is an escape.
    body = parser_src.split("function parser.relevant(line)", 1)[-1]
    body = body.split("\nend", 1)[0]
    searches = len(re.findall(r"line:find\(", body))
    markers = len(re.findall(r"line:find\('\\", body))
    needles = searches - markers
    res.check(searches and markers and needles,
              "parser.relevant's body no longer looks like plain searches "
              "(%d searches, %d markers, %d needles), so the counts below "
              "would be checking nothing" % (searches, markers, needles))

    for label, source, pattern in (
        ("parser.lua", parser_src,
         r"costs (\w+) searches.{0,120}?(\w+) for the marker bytes"
         r".{0,60}?then the (\w+) needles"),
        ("docs/design.md", repo_text("docs", "design.md"),
         r"It is (\w+) `string\.find` searches.{0,120}?(\w+) for the "
         r"colour-code markers, then the (\w+) needles"),
    ):
        found = re.search(pattern, source, re.S)
        got = (None if found is None else
               tuple(NUMBER_WORDS.get(g.lower()) for g in found.groups()))
        res.check(got == (searches, markers, needles),
                  "%s states the gate's cost as %r and it is %d searches -- "
                  "%d for the colour markers, then %d needles"
                  % (label, None if found is None else found.groups(),
                     searches, markers, needles))

    # --- the residual on the deferred write, in all three places ----------
    #
    # It was stated in three files as "roughly one frame", which is not the
    # bound: the addon does not drive Present, so a minimised or throttled
    # client stretches the window as far as it likes. And a crash was given
    # as the only way to lose the write, when a raise inside persist() loses
    # one too, with no crash and nothing on fire.
    #
    # Loose alternations rather than an exact phrase, so this pins the two
    # facts and not one wording of them -- and positively, so it cannot pass
    # by finding a differently wrong sentence the way an absent-phrase grep
    # can.
    # \s+ between words rather than a literal space: these passages are
    # hard-wrapped prose, so the phrase being looked for is split across a
    # newline in two of the three files.
    bound = re.compile(
        r"next\s+(frame\s+that\s+actually\s+runs|`?d3d_present`?)")
    other = re.compile(
        r"raise\s+inside|write\s+itself\s+fails|could\s+not\s+write", re.I)
    for parts in (("inctrack", "inctrack.lua"), ("docs", "design.md"),
                  ("README.md",)):
        text = repo_text(*parts)
        name = "/".join(parts)
        res.check(bound.search(text) is not None,
                  "%s states the deferred write's residual as a length of "
                  "time or a number of frames; the bound is the next frame "
                  "that actually runs, which the addon does not control"
                  % name)
        res.check(other.search(text) is not None,
                  "%s gives a crash as the only way to lose the deferred "
                  "write; a raise inside persist() loses one with nothing on "
                  "fire at all" % name)

    # --- the error-handling list counts its own entries -------------------
    #
    # It said "three protected boundaries, and one validator" over four
    # entries, and described the frame handler's boundary as the render pcall
    # alone -- while an unprotected disk write ran above it (CR-02). Counted
    # against the list rather than trusted.
    design = repo_text("docs", "design.md")
    stated = re.search(r"(\w+) protected boundaries, and (\w+) validator",
                       design)
    listed = 0
    if stated is not None:
        for n in re.findall(r"^(\d+)\. \*\*", design[stated.end():], re.M):
            if int(n) != listed + 1:
                break
            listed = int(n)
    claimed = (None if stated is None else
               sum(NUMBER_WORDS.get(g.lower(), -99) for g in stated.groups()))
    res.check(claimed == listed and listed > 0,
              "docs/design.md's error-handling section claims %r and then "
              "lists %d entries"
              % (None if stated is None else stated.groups(), listed))

    # --- how many suites there are, and how many lines they print ---------
    #
    # docs/design.md said "Eleven suites, reported as twelve result lines"
    # over a twelve-row table, against a harness that calls run_suite() ten
    # times -- a sentence that contradicted the table under it and matched
    # neither number. It had already been corrected once, verified by
    # grepping for the previous wrong wording and finding none.
    #
    # So: counted, from the harness and from the table, and compared with
    # both numbers in the sentence. This file is read as text rather than
    # introspected, because what is being checked is a claim about the source.
    harness = repo_text("test", "run_tests.py")
    functions = len(re.findall(r"run_suite\(\"", harness))
    # The parser suite is the only one that returns more than one Result.
    parser_lines = len(
        re.search(r"return coverage[^\n]*", harness).group(0).split(","))
    said = re.search(
        r"(\w+) suite functions, reported as (\w+) result lines", design)
    counts = (None if said is None else
              tuple(NUMBER_WORDS.get(g.lower()) for g in said.groups()))

    # Rows of the table immediately under that sentence, not of every table
    # in the file: from its header rule to the first line that is not a row.
    rows, in_table = 0, False
    for line in (design[said.end():] if said else "").splitlines():
        if line.startswith("|---"):
            in_table = True
        elif in_table:
            if not line.startswith("|"):
                break
            rows += 1

    res.check(functions > 0 and parser_lines > 1,
              "the harness no longer looks like run_suite(\"name\", fn) with "
              "one multi-Result suite (%d calls, parser returns %d), so the "
              "counts below would be checking nothing"
              % (functions, parser_lines))
    res.check(counts == (functions, functions - 1 + parser_lines),
              "docs/design.md says %r; the harness calls run_suite() %d "
              "times and the parser suite returns %d Results, which is %d "
              "result lines"
              % (None if said is None else said.groups(), functions,
                 parser_lines, functions - 1 + parser_lines))
    res.check(rows == functions - 1 + parser_lines,
              "docs/design.md's table has %d rows and the harness prints %d "
              "result lines, so the sentence above it can be right and the "
              "table still wrong"
              % (rows, functions - 1 + parser_lines))

    # --- no field of State is written and never read ----------------------
    #
    # state.lua is roughly 60% prose and its comments are load-bearing, so a
    # field that every mutating branch assigns reads, to anyone arriving in
    # this file first, as the thing that drives the behaviour it sits beside.
    # `dirty` was exactly that: assigned by twenty branches and by reset(),
    # read by nothing -- not by inctrack.lua, not by ui.lua, not by this
    # harness -- and never cleared, so even a reader who wired it up would
    # find it latched true after the first event. What actually decides the
    # disk write is MUST_SAVE plus the five-second throttle in inctrack.lua,
    # two files away.
    #
    # Derived rather than grepped for by name, so this outlives the one field
    # it was written for: every `self.X` state.lua assigns must be read
    # somewhere -- in state.lua itself, or through the handle the shell and
    # the UI hold.
    state_src = repo_text("inctrack", "state.lua")
    read_src = state_src + repo_text("inctrack", "inctrack.lua") \
        + repo_text("inctrack", "ui.lua")
    assigned = sorted(set(re.findall(r"self\.(\w+)\s*=[^=]", state_src)))
    res.check(len(assigned) >= 4,
              "state.lua assigns %d fields on self, so the check below is "
              "not walking the fields that exist" % len(assigned))
    write_only = []
    for field in assigned:
        # A read is any mention that is not an assignment target: self.X in
        # state.lua, and .X through the state handle in the other two files.
        reads = len(re.findall(r"(?:self|state)\.%s\b(?!\s*=[^=])" % field,
                               read_src))
        if not reads:
            writes = len(re.findall(r"self\.%s\s*=[^=]" % field, state_src))
            write_only.append("%s (%d writes, 0 reads)" % (field, writes))
    res.check(not write_only,
              "state.lua carries a field nothing reads: %s. A vestigial field "
              "in a file whose comments are this load-bearing is a navigation "
              "hazard -- it tells a reader the state machine works in a way "
              "it does not" % ", ".join(write_only))

    # --- every citation in the harness points at something that exists ----
    #
    # The harness pins each stub and each fixture to the shipped statement it
    # models. Good discipline, and the reason the phase's own ledger caught
    # four drifted citations in a plan -- but the citations were line numbers,
    # and by the end of the phase thirteen of them had drifted by 40 to 280
    # lines and pointed at unrelated code. A citation that resolves to the
    # wrong statement is worse than none: it sends a reader somewhere else
    # with the confidence of a reference.
    #
    # So they are searchable tokens now, in one form -- file (`token`) -- and
    # this walks every one of them. Moving the cited code is fine; renaming it
    # without re-anchoring the citation is what fails, which is the drift that
    # was accumulating silently.
    # file (`token`), tolerating the hard wrap that puts the file at the end
    # of one comment line and the token at the start of the next.
    cite = re.compile(
        r"(\w+\.(?:lua|py))[ \t]*(?:\n[ \t]*(?:#|\*|--)[ \t]*)?\(`([^`]+)`\)")
    cited = broken = 0
    for parts in (("test", "run_tests.py"), ("test", "stubs.py")):
        source = repo_text(*parts)
        for target, token in cite.findall(source):
            cited += 1
            where = ("inctrack", target) if target.endswith(".lua") \
                else ("test", target)
            # These citations sit in hard-wrapped comments, so a token can be
            # split across lines with a comment marker in the middle of it.
            # Drop the marker from every continuation line, then match
            # whitespace-insensitively, because the code being cited may be
            # wrapped too.
            words = []
            for i, line in enumerate(token.splitlines()):
                if i:
                    line = re.sub(r"^\s*(#|\*|--)\s*", "", line)
                words.extend(line.split())
            loose = r"\s+".join(re.escape(w) for w in words)
            if re.search(loose, repo_text(*where)) is None:
                broken += 1
                res.check(False,
                          "%s cites %s (`%s`) and %s contains no such text"
                          % ("/".join(parts), target, " ".join(words),
                             target))
    res.check(cited >= 20,
              "only %d citations were found in the harness, so this check is "
              "not walking the ones that exist" % cited)
    res.check(broken == 0,
              "%d harness citations point at text that is not in the file "
              "they name" % broken)

    return res


# --------------------------------------------------------------------------
# 12. what a line the addon ignores costs, before and after
# --------------------------------------------------------------------------

def bench_host(count=False):
    """A loaded host with the two benchmark shapes installed.

    `count` installs the opt-in gsub counter. Counters and stopwatch never
    share a host: the counter is a Lua function standing in front of a C one,
    so a counted host is a slower host and a timed one must be unwrapped.
    """
    host = loaded_host()
    host.lua.execute(BENCH_CHUNK)
    if count:
        host.count_gsub()
    return host


def bench_time(host, name, corpus, iterations, passes=3):
    """Seconds for the best of `passes` runs of one shape over the corpus.

    Timed from Python: os.clock and os.time are both stubbed inside the host
    (they have to be, for the run timers to be deterministic), so the only
    honest stopwatch is out here.
    """
    fn = host.lua.globals()[name]
    table = host.lua.table_from(list(corpus))
    best = None
    for _ in range(passes):
        started = time.perf_counter()
        fn(table, iterations)
        elapsed = time.perf_counter() - started
        if best is None or elapsed < best:
            best = elapsed
    return best


def bench_count(name, corpus):
    """(strip_colors calls, gsub calls) for one pass of one shape."""
    host = bench_host(count=True)
    strip_before = host.strip_colors_calls
    gsub_before = host.gsub_calls
    host.lua.globals()[name](host.lua.table_from(list(corpus)), 1)
    return (host.strip_colors_calls - strip_before,
            host.gsub_calls - gsub_before)


def test_reject_cost(parser, backend):
    """PERF-04: what a chat line the addon ignores costs, before and after.

    Two shapes over one fixed corpus, in one run, on the same machine:

      old -- the reject path as Phase 3 left it, copied into the harness at
             commit a6a3577: strip_colors on every line, then trim, then the
             timestamp loop, then the anchored rejection.
      new -- the addon's own registered text_in handler, whatever it does now.

    Before PERF-01 lands these are the same code and the two figures agree;
    afterwards they do not, and the gap is what the phase bought.

    No rate is ever an acceptance threshold -- a rate is a fact about a
    machine, and the recorded baseline is provenance, not a bar to clear. The
    checks here are the deterministic counters plus, once there is a
    difference to measure, one same-run ratio between the two shapes.

    Nor is the ratio a fact about the player. It is a weighted average over
    this corpus's colour mix, and a coloured line is one the gate declines to
    judge on purpose, so it costs exactly what it always did. Weight the mix
    the other way and the same code reports a smaller number. What the mix
    really is in a live chat window cannot be settled from the recorded logs
    -- Ashita strips the marker bytes before a line reaches disk, so every one
    of the 2.9M recorded lines reads as colour-free whatever it was on screen.
    That is why the assertions below are the per-class counters, which hold
    whatever the mix is, and why the ratio is qualified in the report where it
    is printed.
    """
    res = Result("cost: the non-Incursion reject path")

    # The pin that keeps every figure below honest. A corpus line the parser
    # actually recognises would be measured doing real work in one shape and
    # skipping it in the other, and the ratio would be meaningless.
    parsed = [line for line in REJECT_CORPUS if parser.parse(line) is not None]
    res.check(not parsed,
              "the benchmark corpus is not all rejects, so these figures "
              "compare a path that skipped real work with one that did it: %s"
              % ", ".join(ascii(line) for line in parsed))

    lines_per_pass = len(REJECT_CORPUS) * REJECT_ITERATIONS
    timing = {}
    for name in ("__bench_old", "__bench_new"):
        timing[name] = bench_time(bench_host(), name,
                                  REJECT_CORPUS, REJECT_ITERATIONS)

    rate = {k: lines_per_pass / v for k, v in timing.items()}
    micros = {k: v * 1e6 / lines_per_pass for k, v in timing.items()}
    ratio = rate["__bench_new"] / rate["__bench_old"]

    counts = {}
    for name in ("__bench_old", "__bench_new"):
        counts[(name, "free")] = bench_count(name, REJECT_FREE)
        counts[(name, "colour")] = bench_count(name, REJECT_COLOURED)

    res.note("corpus: %d lines (%d colour-free, %d coloured), %d iterations a "
             "pass, best of 3"
             % (len(REJECT_CORPUS), len(REJECT_FREE), len(REJECT_COLOURED),
                REJECT_ITERATIONS))
    # The backend is named because the rates depend on it entirely: the same
    # corpus through luajit21 and through Lua 5.5 gives two different numbers
    # for the same code, which is the whole reason no rate is a threshold.
    res.note("backend: %s%s"
             % (backend,
                " (INCTRACK_LUA)" if os.environ.get("INCTRACK_LUA") else ""))
    res.note("old shape (Phase 3): %s lines/s, %.3f us/line"
             % (thousands(rate["__bench_old"]), micros["__bench_old"]))
    res.note("new shape (shipped):  %s lines/s, %.3f us/line"
             % (thousands(rate["__bench_new"]), micros["__bench_new"]))
    res.note("new/old: %.2fx" % ratio)
    # The one qualification the headline figure needs, printed beside it
    # rather than left to a reader to work out from the corpus line above.
    res.note("that ratio is a property of this corpus's colour mix (%d of %d "
             "lines colour-free), not a measurement of the player's: a "
             "coloured line is one the gate declines to judge and it costs "
             "what it always did, so a more heavily coloured mix moves the "
             "figure toward 1.00x. The real mix is not measurable here -- "
             "Ashita's log writer strips the marker bytes on the way to "
             "disk, so every recorded line reads as colour-free whatever it "
             "was on screen. The per-class counters below are the part of "
             "this that does not depend on the mix"
             % (len(REJECT_FREE), len(REJECT_CORPUS)))
    for group, label in (("free", "colour-free"), ("colour", "coloured")):
        n = len(REJECT_FREE if group == "free" else REJECT_COLOURED)
        old_s, old_g = counts[("__bench_old", group)]
        new_s, new_g = counts[("__bench_new", group)]
        res.note("per %s rejected line -- old: %.2f strip_colors, %.2f gsub; "
                 "new: %.2f strip_colors, %.2f gsub"
                 % (label, old_s / n, old_g / n, new_s / n, new_g / n))
    res.note("recorded baseline (%s, commit %s, %s, Python %s): %s lines/s, "
             "%.3f us/line -- provenance, not a threshold"
             % (REJECT_BASELINE["date"], REJECT_BASELINE["commit"],
                REJECT_BASELINE["backend"], REJECT_BASELINE["python"],
                thousands(REJECT_BASELINE["lines_per_second"]),
                REJECT_BASELINE["us_per_line"]))

    # --- what the figures above have to say ------------------------------

    free_n = len(REJECT_FREE)
    old_strip, old_gsub = counts[("__bench_old", "free")]
    new_strip, new_gsub = counts[("__bench_new", "free")]

    res.check(new_strip == 0,
              "a colour-free line the addon ignores still paid for %.2f "
              "colour strips apiece -- a gsub and an allocation, on the game "
              "thread, on every line the client receives"
              % (new_strip / free_n))
    res.check(new_gsub == 0,
              "a colour-free line the addon ignores still ran %.2f gsubs "
              "apiece: the trim and the timestamp loop are still being paid "
              "for on traffic that is turned away" % (new_gsub / free_n))
    res.check(old_strip == free_n,
              "the Phase-3 copy did not strip colours once per line (%d over "
              "%d lines), so it is not the shape it claims to be"
              % (old_strip, free_n))
    res.check(old_gsub > 0,
              "the Phase-3 copy allocated nothing either, so the comparison "
              "above is between two identical shapes and says nothing")

    # The one wall-clock assertion in the whole suite, and it is safe because
    # it never leaves this run: a ratio between two shapes measured on the
    # same corpus on the same machine within the same second. Hard rule 10 is
    # about figures that travel between machines, and this one does not.
    #
    # 1.2 is a noise margin, not a target. The real gap is a constant factor
    # -- five allocations against none -- and lands far above it; a bare '>'
    # on a single best-of-three pair would carry no margin at all and would be
    # the one thing in the suite able to flake on a busy machine.
    res.check(ratio >= 1.2,
              "the reject path is only %.2fx the shape Phase 3 shipped over "
              "the same corpus in the same run, which is inside the noise: "
              "whatever PERF-01 changed, it did not change what a line the "
              "addon ignores costs" % ratio)

    return res


def thousands(n):
    """A rate a human can read at a glance, without a locale."""
    return "{:,}".format(int(round(n)))


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

    Returns a list, because test_parser returns three Results rather than one
    -- coverage, the dormant generic tier and the over-reach guard. Every
    other suite returns a single Result and is wrapped here.
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
    backend = getattr(lua, "lua_implementation", "unknown")
    print("  lua: %s%s" % (backend,
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
    suites.extend(run_suite("record", test_record, parser))
    # Last, because it is the only suite that reads a stopwatch and every
    # suite before it has finished competing for the machine by the time it
    # runs.
    suites.extend(run_suite("reject cost", test_reject_cost, parser, backend))

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
