"""
Host stubs for the two Ashita-dependent addon files.

`inctrack/ui.lua` requires `imgui`; `inctrack/inctrack.lua` requires the whole
Ashita host (`addon`, `ashita.events`, `AshitaCore`, `common`, `chat`,
`settings`, `json`). Neither host exists outside the game, so until something
supplies them those 734 lines of shipped code cannot be executed by any test at
all. This module supplies them.

What is stubbed here is the *host*, never the addon. That is the whole point:
the suite keeps loading the shipped Lua, so a pass still means the shipped code
behaves rather than a reimplementation of it. Nothing in `inctrack/` is
modified, mocked, or wrapped.

This module is imported by `test/run_tests.py` and is never run directly --
`python test/run_tests.py` stays the single entry point. It has no CLI.

Contents:
  * install_imgui(lua)     -- a recording ImGui stub; returns an ImGuiRecorder
  * install_ashita(lua)    -- the in-memory Ashita fakes plus a pure-Lua json;
                              returns an AshitaHost
"""

import sys

import lupa


def lua_type(value):
    """`lupa.lua_type`, dispatched to the backend that built `value`.

    The module-level `lupa.lua_type` only recognises proxies from the one Lua
    that a plain `lupa.LuaRuntime()` resolves to. Hand it a table built by
    `lupa.luajit21` -- the dialect Ashita actually embeds -- and it answers
    None, so every "is this a Lua table?" test in the harness silently reads
    false: the p_open box in a recorded Begin stops being recognised, and the
    window snapshot the ui suite compares against is decided by which lupa the
    contributor happens to have. Dispatch on the proxy's own module so the
    answer is the same on every backend.
    """
    module = sys.modules.get(type(value).__module__)
    dispatch = getattr(module, "lua_type", None)
    if dispatch is None:
        return lupa.lua_type(value)
    return dispatch(value)


# --------------------------------------------------------------------------
# The recording ImGui stub
# --------------------------------------------------------------------------

# Window flag values, keyed by the short name the snapshot normaliser prints.
# These are the upstream Dear ImGui values; all that actually matters here is
# that each is a distinct power of two, so a summed flag argument (ui.lua adds
# its flags together) can be decomposed again.
WINDOW_FLAGS = {
    "NoTitleBar": 1,
    "NoMove": 4,
    "NoScrollbar": 8,
    "AlwaysAutoResize": 64,
    "NoFocusOnAppearing": 4096,
}

# Calls that measure rather than draw. They are always recorded; the snapshot
# normaliser can be asked to leave them out of the rendered text.
MEASUREMENT_CALLS = ("CalcTextSize", "GetCursorPosX")

IMGUI_CHUNK = """
--[[
* Recording ImGui stub. Every entry point ui.lua touches appends a
* (name, args) record to an ordered log; nothing is drawn and nothing is
* laid out.
]]--

-- Pixels per character. This stands in for font metrics we deliberately do
-- not model: the stub measures string length, not glyphs.
local PX_PER_CHAR = 7.0

-- The x a drawing call starts a fresh line at (ImGui's window padding).
--
-- Deliberately not 8: ui.lua's file default for origin_x is 8 (ui.lua:67) and
-- it is overwritten with GetCursorPosX() inside Begin (ui.lua:408). A stub
-- padding of 8 makes that assignment a no-op, so every right-aligned value
-- and wrap position in every window is identical whether or not the line
-- runs -- one of render's statements invisible to a suite that claims to
-- cover the whole window.
local PADDING = 11.0

-- Nominal width of a fill-width (-1) item, for cursor bookkeeping only.
local FULL_W = 300.0

-- The enum names ui.lua reads are globals, not fields on the imgui table.
ImGuiCol_PlotHistogram    = 40;
ImGuiStyleVar_ItemSpacing = 13;

ImGuiWindowFlags_NoTitleBar         = 1;
ImGuiWindowFlags_NoMove             = 4;
ImGuiWindowFlags_NoScrollbar        = 8;
ImGuiWindowFlags_AlwaysAutoResize   = 64;
ImGuiWindowFlags_NoFocusOnAppearing = 4096;

local S = {
    log     = {},
    counts  = {},
    cursor  = PADDING,
    last_end = PADDING,
    armed   = false,
};
__imgui_stub = S;

local function record(name, ...)
    S.log[#S.log + 1] = { name = name, n = select('#', ...), args = { ... } };
    S.counts[name] = (S.counts[name] or 0) + 1;
end

--[[
* Cursor bookkeeping: one number, so right_text's overflow branch at
* ui.lua:98 is reachable. This is arithmetic, not a layout engine --
* wrapping, real font metrics and window sizing are explicitly not simulated.
*
* A drawing call is placed at the cursor, remembers where it ended, and
* returns the cursor to the padding (ImGui moves to the next line). SameLine
* puts the cursor back at the previous item's end; SetCursorPosX overwrites
* it outright.
]]--
local function drew(width)
    S.last_end = S.cursor + width;
    S.cursor = PADDING;
end

local function text_w(text)
    return PX_PER_CHAR * #tostring(text or '');
end

-- Flags arrive summed, so decompose arithmetically rather than with bitwise
-- operators the addon's own Lua 5.1 dialect does not have.
local function has_flag(value, bit)
    if type(value) ~= 'number' then
        return false;
    end
    return math.floor(value / bit) % 2 == 1;
end

local imgui = {};

function imgui.CalcTextSize(text)
    record('CalcTextSize', text);
    return text_w(text);
end

function imgui.GetCursorPosX()
    record('GetCursorPosX');
    return S.cursor;
end

function imgui.SetCursorPosX(x)
    record('SetCursorPosX', x);
    S.cursor = x;
end

function imgui.SameLine(...)
    record('SameLine', ...);
    S.cursor = S.last_end;
end

function imgui.TextColored(color, text)
    record('TextColored', color, text);
    drew(text_w(text));
end

function imgui.PushTextWrapPos(x)
    record('PushTextWrapPos', x);
end

function imgui.PopTextWrapPos()
    record('PopTextWrapPos');
end

function imgui.PushStyleColor(idx, color)
    record('PushStyleColor', idx, color);
end

function imgui.PopStyleColor(count)
    record('PopStyleColor', count);
end

function imgui.PushStyleVar(idx, value)
    record('PushStyleVar', idx, value);
end

function imgui.PopStyleVar(count)
    record('PopStyleVar', count);
end

function imgui.ProgressBar(fraction, size, overlay)
    record('ProgressBar', fraction, size, overlay);
    local w = FULL_W;
    if type(size) == 'table' and type(size[1]) == 'number' and size[1] >= 0 then
        w = size[1];
    end
    drew(w);
end

function imgui.Dummy(size)
    record('Dummy', size);
    local w = 0;
    if type(size) == 'table' and type(size[1]) == 'number' and size[1] >= 0 then
        w = size[1];
    end
    drew(w);
end

--[[
* Begin is strictly positional, because the host's is. Ashita declares it
* exactly once --
*
*     virtual bool Begin(const char* name, bool* p_open = nullptr,
*                        ImGuiWindowFlags flags = 0) = 0;
*     (Ashita/plugins/sdk/imgui.h:305)
*
* -- with no overload, and addons/libs/imgui.lua adds no Lua wrapper that
* could reshape the call: it is a constants table whose __index is
* AshitaCore:GetGuiManager(), so an addon's imgui.Begin lands on that
* signature unmediated. Slot 2 is p_open and slot 3 is flags, always.
*
* Nothing here type-sniffs a numeric slot 2 into flags. An earlier version of
* this stub did, which made the suite bless a call shape no addon in the
* install uses and the host never promised: flags handed to slot 2 are a
* p_open in game, so the window would silently lose NoTitleBar and
* AlwaysAutoResize -- or the binding would raise, once per frame, inside
* d3d_present. A stub that accepts what the host rejects is worse than no
* stub, so this one accepts only what the header declares and the arguments
* are recorded exactly as they arrived, positions included.
*
* The close button is modelled honestly. When the click switch is armed,
* Begin writes false into the p_open box only if the recorded flags do not
* include NoTitleBar -- ImGui draws no close button on a window that has no
* title bar, so on such a window an armed click cannot reach one.
]]--
function imgui.Begin(...)
    local _, p_open, flags = ...;

    record('Begin', ...);

    S.cursor = PADDING;
    S.last_end = PADDING;

    if S.armed then
        S.armed = false;
        if type(p_open) == 'table'
                and not has_flag(flags, ImGuiWindowFlags_NoTitleBar) then
            p_open[1] = false;
        end
    end

    return true;
end

function imgui.End()
    record('End');
end

function S.reset()
    S.log = {};
    S.counts = {};
    S.cursor = PADDING;
    S.last_end = PADDING;
    S.armed = false;
end

function S.arm()
    S.armed = true;
end

S.api = imgui;
S.px_per_char = PX_PER_CHAR;
S.padding = PADDING;

package.loaded['imgui'] = imgui;
"""


def window_flags(value):
    """A summed ImGuiWindowFlags value, decomposed into sorted flag names.

    An unrecognised remainder is reported as a trailing '?<n>' entry rather
    than silently dropped.
    """
    if not value:
        return []
    value = int(value)
    names = sorted(n for n, bit in WINDOW_FLAGS.items() if value & bit)
    rest = value
    for bit in WINDOW_FLAGS.values():
        rest &= ~bit
    if rest:
        names.append("?%d" % rest)
    return names


def _seq(value):
    """A Lua array (or any Python sequence) as a plain Python list."""
    if lua_type(value) == "table":
        return [value[i] for i in range(1, len(value) + 1)]
    return list(value)


def _color_key(values):
    """The hashable identity of a colour: its four components, rounded."""
    if len(values) != 4:
        return None
    try:
        return tuple(round(float(v), 4) for v in values)
    except (TypeError, ValueError):
        return None


def _color_map(colors):
    """name -> colour table, inverted into colour components -> name."""
    if colors is None:
        return None
    out = {}
    for name, value in colors.items():
        key = _color_key(_seq(value))
        if key is not None:
            out[key] = name
    return out


def _num(value):
    """Integers plainly, fractions to two decimals -- diffable either way.

    Normalised before formatting rather than branched on the Python type,
    because that type is decided by whichever Lua `lupa` resolved to and not
    by the addon: LuaJIT (the dialect Ashita embeds) hands an integral double
    back as a Python int, while Lua 5.4+ hands the same value back as a
    float. Branching on it made every inline window in the ui suite pass on
    one backend and fail on the other, blaming ui.lua for a defect in this
    recorder. 252 and 252.0 must render identically or the snapshots are
    pinned to one contributor's build of lupa.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    value = float(value)
    if value == int(value):
        return "%d" % int(value)
    return "%.2f" % value


def _render(value, cmap):
    """One recorded argument as reviewable text.

    Text is reproduced verbatim inside single quotes and is never used as a
    format string -- server-supplied text can contain a percent sign.
    """
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _num(value)
    if isinstance(value, bytes):
        return "'" + value.decode("latin-1") + "'"
    if isinstance(value, str):
        return "'" + value + "'"
    if lua_type(value) == "table":
        items = _seq(value)
        if cmap:
            name = cmap.get(_color_key(items))
            if name is not None:
                return name
        return "[" + ", ".join(_render(v, cmap) for v in items) + "]"
    return str(value)


class ImGuiRecorder:
    """Python-side handle on the recording ImGui stub.

    calls          -- the raw log: a list of (name, args) pairs, args a tuple
    reset()        -- clear the log and the cursor state
    arm_close()    -- arm a one-shot 'the user clicked close this frame'
    snapshot(...)  -- the log as reviewable multi-line text
    counts         -- per-entry-point call counts
    padding        -- the cursor x at the top of a window, i.e. what ui.lua
                      captures as origin_x
    balance()      -- push/pop balance of the three ImGui stacks
    api            -- the Lua imgui table itself
    """

    def __init__(self, lua):
        self.lua = lua
        lua.execute(IMGUI_CHUNK)
        self._s = lua.globals()["__imgui_stub"]
        self.api = self._s["api"]

    @property
    def calls(self):
        log = self._s["log"]
        out = []
        for i in range(1, len(log) + 1):
            entry = log[i]
            args = entry["args"]
            count = int(entry["n"])
            out.append((entry["name"],
                        tuple(args[j] for j in range(1, count + 1))))
        return out

    @property
    def counts(self):
        return {k: int(v) for k, v in self._s["counts"].items()}

    @property
    def padding(self):
        """Where the stub puts the cursor at the top of a window.

        This is what GetCursorPosX() reports inside Begin, and therefore what
        ui.lua:408 captures as origin_x -- a test can assert the window took
        its left edge from ImGui rather than from its own file default.
        """
        return float(self._s["padding"])

    def reset(self):
        self._s["reset"]()

    def arm_close(self):
        self._s["arm"]()

    def balance(self):
        """Unbalanced stacks are a frame-rate bug, so record them from the
        start -- Phase 3 asserts on these when ui.render errors mid-window."""
        window = style_var = style_color = 0
        for name, args in self.calls:
            count = 1
            if args and isinstance(args[0], (int, float)):
                count = int(args[0])
            if name == "Begin":
                window += 1
            elif name == "End":
                window -= 1
            elif name == "PushStyleVar":
                style_var += 1
            elif name == "PopStyleVar":
                style_var -= count
            elif name == "PushStyleColor":
                style_color += 1
            elif name == "PopStyleColor":
                style_color -= count
        return {"window": window, "style_var": style_var,
                "style_color": style_color}

    def snapshot(self, colors=None, measurements=True):
        """The call log as readable, diffable, multi-line text.

        One recorded call per line, indented between Begin and End. Pass the
        addon's COLOR table as `colors` to see colour names instead of RGBA
        components. Pass measurements=False to leave out CalcTextSize and
        GetCursorPosX, which measure rather than draw.
        """
        cmap = _color_map(colors)
        lines = []
        depth = 0
        for name, args in self.calls:
            if not measurements and name in MEASUREMENT_CALLS:
                continue
            if name == "End" and depth > 0:
                depth -= 1
            pad = "  " * depth
            if name == "Begin":
                lines.append(pad + self._begin_line(args, cmap))
                depth += 1
            else:
                rendered = " ".join(_render(a, cmap) for a in args)
                lines.append((pad + name + " " + rendered).rstrip())
        return "\n".join(lines)

    def _begin_line(self, args, cmap):
        """One recorded Begin, rendered by argument *position*.

        The host's Begin is a single positional signature -- Begin(name,
        p_open, flags) -- so slot 2 is reported as p_open and slot 3 as
        flags, whatever type happens to be sitting in them. The snapshot
        therefore records which slot each value arrived in rather than
        inferring the caller's intent from its type, and flags handed to
        slot 2 show up as a p_open with no flags at all -- a visible,
        diffable line rather than a shape the recorder quietly forgave.
        """
        parts = ["Begin"]
        if args:
            parts.append(_render(args[0], cmap))
        parts.append(
            "p_open=" + _render(args[1] if len(args) > 1 else None, cmap))
        names = window_flags(args[2] if len(args) > 2 else None)
        parts.append("flags=" + ("|".join(names) if names else "none"))
        return " ".join(parts)


def install_imgui(lua):
    """Install the recording ImGui stub into `lua` and return its handle.

    Populates package.loaded['imgui'] so require('imgui') at ui.lua:28
    resolves to it, and sets the ImGui* enum globals ui.render reads.
    """
    return ImGuiRecorder(lua)


# --------------------------------------------------------------------------
# The Ashita host fakes, and a pure-Lua json
# --------------------------------------------------------------------------

# Fixed wall-clock epoch (2026-01-01 00:00:00 UTC). Seeding os.time() at a
# constant is what makes a serialised blob reproducible from run to run.
EPOCH = 1767225600

ASHITA_CHUNK = """
--[[
* In-memory Ashita host fakes -- not strict mocks. Tests assert on the
* behaviour that results, so a refactor inside the addon does not produce a
* false failure.
]]--

--[[
* Deterministic clocks. state.lua deliberately mixes two of them with
* different epochs: the monotonic clock drives every run timer through the
* now() at inctrack.lua:80 (os.clock resets on reload, so timers serialise as
* remaining durations), while the os.time() wall clock is what `saved_at` and
* the staleness check in State:restore compare. Both are stubbed, and
* separately, so a test can age one without the other.
*
* Both values are seeded from Python; see stubs.EPOCH.
]]--
__host_epoch = 0;
__host_mono  = 0;
__host_wall  = 0;

os.clock = function () return __host_mono; end
os.time  = function () return __host_wall; end

-- The five addon.* assignments at inctrack.lua:20-24 need somewhere to land.
addon = {};

-- Ashita's common.lua prelude table constructor; a passthrough is all the
-- addon asks of it, exactly as suite 8 already does at run_tests.py:842.
function T(t)
    return t or {};
end

__host_events  = {};
__host_aliases = {};

ashita = {
    events = {
        register = function (event, alias, fn)
            __host_events[event] = fn;
            __host_aliases[event] = alias;
        end,
    },
};

--[[
* AshitaCore:GetMemoryManager():GetParty():GetMemberName(0) -- inctrack.lua:127
* and :177. These are colon calls, so every method takes its receiver
* explicitly. The name starts empty so the deferred-fetch path at
* inctrack.lua:176-181 is exercisable; Python supplies one later.
]]--
__host_player = '';

local party = {};
function party.GetMemberName(self, index)
    return __host_player;
end

local memory = {};
function memory.GetParty(self)
    return party;
end

AshitaCore = {};
function AshitaCore.GetMemoryManager(self)
    return memory;
end

-- Console output is captured rather than written, so the host touches no
-- stdout state of the harness it is embedded in.
__host_chat = {};
print = function (...)
    local parts = {};
    for i = 1, select('#', ...) do
        parts[i] = tostring((select(i, ...)));
    end
    __host_chat[#__host_chat + 1] = table.concat(parts, '\\t');
end

-- require('common') at inctrack.lua:26 is for side effects only.
package.loaded['common'] = {};

package.loaded['chat'] = {
    header  = function (name) return '[' .. tostring(name) .. '] '; end,
    message = function (text) return tostring(text); end,
};

--[[
* settings. Nothing is written to disk: save() counts the write and records
* what would have been written, which is what a test needs to see.
]]--
__host_profile     = nil;   -- Python-supplied overrides for the next load()
__host_defaults    = nil;
__host_settings    = nil;
__host_saves       = 0;
__host_sessions    = {};
__host_settings_cb = nil;

local function merged(defaults, over)
    local out = {};
    if type(defaults) == 'table' then
        for k, v in pairs(defaults) do out[k] = v; end
    end
    if type(over) == 'table' then
        for k, v in pairs(over) do out[k] = v; end
    end
    return out;
end

package.loaded['settings'] = {
    load = function (defaults)
        __host_defaults = defaults;
        __host_settings = merged(defaults, __host_profile);
        return __host_settings;
    end,
    save = function ()
        __host_saves = __host_saves + 1;
        local session = __host_settings and __host_settings.session or '';
        __host_sessions[#__host_sessions + 1] = tostring(session);
    end,
    register = function (name, alias, fn)
        __host_settings_cb = fn;
    end,
};

-- Fire the profile-switch callback registered at inctrack.lua:281 with a new
-- settings table, as a character change does.
function __host_switch(over)
    __host_settings = merged(__host_defaults, over);
    if __host_settings_cb ~= nil then
        __host_settings_cb(__host_settings);
    end
    return __host_settings;
end

--[[
* string:strip_colors() -- inctrack.lua:167. Ashita's two colour-code escape
* forms are a marker byte followed by one payload byte. The call counter is
* free now and is what PERF-01 measures in Phase 4.
]]--
__host_strip_calls = 0;

function string.strip_colors(s)
    __host_strip_calls = __host_strip_calls + 1;
    local out = tostring(s):gsub('\\30.', '');
    out = out:gsub('\\31.', '');
    return out;
end

-- require() returns two values from Lua 5.4 on (the module and its loader
-- data). The harness wants the module and nothing else.
function __host_require(name)
    return (require(name));
end

-- string:args() -- inctrack.lua:229. '/inc reset' -> { '/inc', 'reset' },
-- 1-indexed, so args[1] and args[2] behave as they do in game.
function string.args(s)
    local out = {};
    for word in tostring(s):gmatch('%S+') do
        out[#out + 1] = word;
    end
    return out;
end
"""

JSON_CHUNK = """
--[[
* A stubbed pure-Lua json, so the new suites need no Ashita install (D-04).
* Suite 8 keeps round-tripping the save format through Ashita's own json.lua;
* that suite's whole purpose is the real thing, and this stub is never put
* anywhere the shared runtime from make_lua() can see it.
*
* The decoder scans its input character by character. It never hands the text
* to load(), loadstring() or dofile(): a decoder that evaluates its input is a
* code execution path in the harness (T-01-01), and it would also silently
* accept non-JSON such as {a=1}.
]]--

local json = {};

local ESCAPES = {
    ['"']  = '\\\\"',
    ['\\\\'] = '\\\\\\\\',
    ['\\b'] = '\\\\b',
    ['\\f'] = '\\\\f',
    ['\\n'] = '\\\\n',
    ['\\r'] = '\\\\r',
    ['\\t'] = '\\\\t',
};

--[[
* Bytes >= 0x80 are emitted raw rather than escaped. Real logs carry raw high
* bytes inside boon names, and \\u escaping them would decode back to a
* codepoint rather than the byte, breaking the round trip this stub exists to
* provide.
]]--
local function quote(s)
    local out = s:gsub('[%c"\\\\]', function (c)
        return ESCAPES[c] or string.format('\\\\u%04x', string.byte(c));
    end);
    return '"' .. out .. '"';
end

local function numstr(v)
    if v ~= v or v == math.huge or v == -math.huge then
        error('json.encode: cannot encode ' .. tostring(v));
    end
    if math.type ~= nil then
        if math.type(v) == 'integer' then
            return string.format('%d', v);
        end
    elseif v == math.floor(v) then
        return string.format('%d', v);
    end
    return string.format('%.14g', v);
end

local encode_value;

encode_value = function (v, depth)
    local kind = type(v);
    if v == nil then
        return 'null';
    end
    if kind == 'boolean' then
        return v and 'true' or 'false';
    end
    if kind == 'number' then
        return numstr(v);
    end
    if kind == 'string' then
        return quote(v);
    end
    if kind ~= 'table' then
        error('json.encode: cannot encode a ' .. kind);
    end
    if depth > 64 then
        error('json.encode: nesting too deep');
    end

    local parts = {};

    -- An array when its length is non-zero, an object otherwise. State's
    -- `boons` and `objective.mobs` are arrays; `extra` is string-keyed.
    if #v > 0 then
        for i = 1, #v do
            parts[i] = encode_value(v[i], depth + 1);
        end
        return '[' .. table.concat(parts, ',') .. ']';
    end

    local keys = {};
    for k in pairs(v) do
        keys[#keys + 1] = k;
    end
    -- Sorted so the output is reproducible; JSON object order carries no
    -- meaning either way.
    table.sort(keys, function (a, b) return tostring(a) < tostring(b); end);
    for i = 1, #keys do
        parts[i] = quote(tostring(keys[i])) .. ':'
            .. encode_value(v[keys[i]], depth + 1);
    end
    return '{' .. table.concat(parts, ',') .. '}';
end

function json.encode(v)
    return encode_value(v, 0);
end

function json.decode(text)
    if type(text) ~= 'string' then
        error('json.decode: expected a string, got ' .. type(text));
    end

    local pos = 1;
    local last = #text;

    local function fail(msg)
        error('json.decode: ' .. msg .. ' at offset ' .. tostring(pos));
    end

    local function skip()
        while pos <= last do
            local c = text:sub(pos, pos);
            if c == ' ' or c == '\\t' or c == '\\n' or c == '\\r' then
                pos = pos + 1;
            else
                break;
            end
        end
    end

    local function parse_string()
        pos = pos + 1;   -- the opening quote
        local buf = {};
        while true do
            if pos > last then
                fail('unterminated string');
            end
            local c = text:sub(pos, pos);
            if c == '"' then
                pos = pos + 1;
                return table.concat(buf);
            end
            if c == '\\\\' then
                local e = text:sub(pos + 1, pos + 1);
                pos = pos + 2;
                if e == 'n' then buf[#buf + 1] = '\\n';
                elseif e == 't' then buf[#buf + 1] = '\\t';
                elseif e == 'r' then buf[#buf + 1] = '\\r';
                elseif e == 'b' then buf[#buf + 1] = '\\b';
                elseif e == 'f' then buf[#buf + 1] = '\\f';
                elseif e == '/' then buf[#buf + 1] = '/';
                elseif e == '"' then buf[#buf + 1] = '"';
                elseif e == '\\\\' then buf[#buf + 1] = '\\\\';
                elseif e == 'u' then
                    local hex = text:sub(pos, pos + 3);
                    if #hex < 4 or hex:find('%X') ~= nil then
                        fail('bad \\\\u escape');
                    end
                    local code = tonumber(hex, 16);
                    pos = pos + 4;
                    if code < 256 then
                        buf[#buf + 1] = string.char(code);
                    else
                        -- The encoder never emits these; do not invent an
                        -- encoding for one that arrived from elsewhere.
                        buf[#buf + 1] = '?';
                    end
                else
                    fail('bad escape');
                end
            else
                buf[#buf + 1] = c;
                pos = pos + 1;
            end
        end
    end

    local function parse_number()
        local start = pos;
        while pos <= last do
            if text:sub(pos, pos):find('[%d%+%-%.eE]') ~= nil then
                pos = pos + 1;
            else
                break;
            end
        end
        local raw = text:sub(start, pos - 1);
        local v = tonumber(raw);
        if v == nil then
            pos = start;
            fail('bad number');
        end
        return v;
    end

    local parse_value;

    parse_value = function (depth)
        if depth > 64 then
            fail('nesting too deep');
        end
        skip();
        if pos > last then
            fail('unexpected end of input');
        end
        local c = text:sub(pos, pos);

        if c == '{' then
            pos = pos + 1;
            local out = {};
            skip();
            if text:sub(pos, pos) == '}' then
                pos = pos + 1;
                return out;
            end
            while true do
                skip();
                if text:sub(pos, pos) ~= '"' then
                    fail('expected a quoted key');
                end
                local key = parse_string();
                skip();
                if text:sub(pos, pos) ~= ':' then
                    fail('expected :');
                end
                pos = pos + 1;
                out[key] = parse_value(depth + 1);
                skip();
                local d = text:sub(pos, pos);
                if d == ',' then
                    pos = pos + 1;
                elseif d == '}' then
                    pos = pos + 1;
                    return out;
                else
                    fail('expected , or }');
                end
            end
        end

        if c == '[' then
            pos = pos + 1;
            local out = {};
            skip();
            if text:sub(pos, pos) == ']' then
                pos = pos + 1;
                return out;
            end
            local i = 1;
            while true do
                out[i] = parse_value(depth + 1);
                i = i + 1;
                skip();
                local d = text:sub(pos, pos);
                if d == ',' then
                    pos = pos + 1;
                elseif d == ']' then
                    pos = pos + 1;
                    return out;
                else
                    fail('expected , or ]');
                end
            end
        end

        if c == '"' then
            return parse_string();
        end
        if text:sub(pos, pos + 3) == 'true' then
            pos = pos + 4;
            return true;
        end
        if text:sub(pos, pos + 4) == 'false' then
            pos = pos + 5;
            return false;
        end
        if text:sub(pos, pos + 3) == 'null' then
            pos = pos + 4;
            return nil;
        end
        if c:find('[%d%-%+]') ~= nil then
            return parse_number();
        end
        fail('unexpected character ' .. c);
    end

    local value = parse_value(0);
    skip();
    if pos <= last then
        fail('trailing content');
    end
    return value;
end

package.loaded['json'] = json;
"""


# Ashita v4's text_in event table, as the real host supplies it -- and reads
# it back. An addon does not rewrite a chat line by assigning to `e.message`:
# the host looks at `message_modified` (and `mode_modified`, `indent_modified`)
# to decide what the player actually sees, and at `blocked` to decide whether
# they see it at all. An event table carrying only `message` therefore cannot
# prove the read-only guarantee at inctrack.lua:156 -- a handler that rewrote
# chat in game would leave every assertion about `message` untouched.
TEXT_IN_FIELDS = {
    "mode": 0,
    "indent": 0,
    "message": "",
    "mode_modified": None,
    "indent_modified": None,
    "message_modified": None,
    "blocked": None,
    "injected": False,
}


class AshitaHost:
    """Python-side handle on the in-memory Ashita host.

    lua                -- the runtime the fakes were installed into
    require(name)       -- require a module inside that runtime
    events              -- event name -> registered handler
    fire(event, **kw)   -- build the event table, call the handler, return it
    fire_text_in(msg)   -- fire text_in with the host's real event shape
    chat                -- the captured console lines
    settings            -- the live settings table the addon holds
    saves               -- how many settings.save() calls happened
    sessions            -- the session string recorded at each save
    switch_profile(d)   -- fire the settings profile-switch callback
    set_party_name(n)   -- what AshitaCore reports as party member 0
    tick(seconds)       -- set the monotonic clock
    wall(seconds)       -- set the wall clock, as an offset from EPOCH
    strip_colors_calls  -- how many times string:strip_colors() ran
    """

    def __init__(self, lua, player="", profile=None):
        self.lua = lua
        lua.execute(ASHITA_CHUNK)
        lua.execute(JSON_CHUNK)
        g = lua.globals()
        g["__host_epoch"] = EPOCH
        g["__host_wall"] = EPOCH
        g["__host_player"] = player or ""
        if profile is not None:
            g["__host_profile"] = lua.table_from(dict(profile))

    def _g(self, name):
        return self.lua.globals()[name]

    def require(self, name):
        return self.lua.globals()["__host_require"](name)

    @property
    def events(self):
        return {k: v for k, v in self._g("__host_events").items()}

    @property
    def aliases(self):
        return {k: v for k, v in self._g("__host_aliases").items()}

    def fire(self, event, **fields):
        """Invoke a registered handler with an event table built from kwargs.

        The table is returned, so a caller can read back what the handler
        wrote to it -- e.blocked, for instance.
        """
        handler = self.events.get(event)
        if handler is None:
            raise KeyError("no handler registered for %r" % event)
        e = self.lua.table_from(dict(fields))
        handler(e)
        return e

    def fire_text_in(self, message):
        """Fire text_in with the event table Ashita really hands a handler.

        Nil-valued fields are left out rather than set: in Lua an absent key
        and a nil value are the same thing, so this way a *_modified key
        existing at all means the handler wrote it, which is exactly the
        question the read-only guarantee turns on.
        """
        fields = dict(TEXT_IN_FIELDS)
        fields["message"] = message
        return self.fire("text_in", **{k: v for k, v in fields.items()
                                       if v is not None})

    @property
    def chat(self):
        return _seq(self._g("__host_chat"))

    @property
    def settings(self):
        return self._g("__host_settings")

    @property
    def saves(self):
        return int(self._g("__host_saves"))

    @property
    def sessions(self):
        return _seq(self._g("__host_sessions"))

    @property
    def strip_colors_calls(self):
        return int(self._g("__host_strip_calls"))

    @property
    def profile_callback(self):
        return self._g("__host_settings_cb")

    @property
    def json(self):
        return self.require("json")

    def set_party_name(self, name):
        self.lua.globals()["__host_player"] = name or ""

    def tick(self, seconds):
        """Set the monotonic clock -- the one every run timer reads."""
        g = self.lua.globals()
        g["__host_mono"] = seconds
        if g["__clock"] is not None:
            g["__clock"] = seconds

    def wall(self, seconds):
        """Set the wall clock, as an offset in seconds from EPOCH.

        This is the clock `saved_at` and State:restore's staleness check use;
        wall(4 * 60 * 60) ages a snapshot by four hours without touching any
        run timer.
        """
        self.lua.globals()["__host_wall"] = EPOCH + seconds

    def switch_profile(self, profile):
        """A character change: a new settings table reaches the callback."""
        return self.lua.globals()["__host_switch"](
            self.lua.table_from(dict(profile)))


def install_ashita(lua, player="", profile=None):
    """Install the Ashita host fakes and the json stub, and return the handle.

    Everything inctrack.lua reaches for at load is supplied: the `addon`
    table, T{}, ashita.events, AshitaCore, common, chat, settings, a captured
    print, the two string extensions, deterministic clocks, and json.
    """
    return AshitaHost(lua, player=player, profile=profile)
