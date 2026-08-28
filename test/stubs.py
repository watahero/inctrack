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
  * install_imgui(lua)  -- a recording ImGui stub; returns an ImGuiRecorder
"""

import lupa


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
local PADDING = 8.0

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
* Begin has two real call shapes: a table second argument is the p_open
* boolean-box, a number second argument is the flags. Both are recorded as
* they arrived, so a test can tell which was used.
*
* The close button is modelled honestly. When the click switch is armed,
* Begin writes false into the p_open box only if the recorded flags do not
* include NoTitleBar -- ImGui draws no close button on a window that has no
* title bar, so on such a window an armed click cannot reach one.
]]--
function imgui.Begin(...)
    local name, a, b = ...;
    local box, flags;
    if type(a) == 'table' then
        box = a;
        flags = b;
    elseif type(a) == 'number' then
        flags = a;
    end

    record('Begin', ...);

    S.cursor = PADDING;
    S.last_end = PADDING;

    if S.armed then
        S.armed = false;
        if box ~= nil and not has_flag(flags, ImGuiWindowFlags_NoTitleBar) then
            box[1] = false;
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
    if lupa.lua_type(value) == "table":
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
    """Integers plainly, fractions to two decimals -- diffable either way."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return "%d" % value
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
    if lupa.lua_type(value) == "table":
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
        parts = ["Begin"]
        if args:
            parts.append(_render(args[0], cmap))
        box = args[1] if len(args) > 1 else None
        if lupa.lua_type(box) == "table":
            parts.append("p_open=" + _render(box, cmap))
            flags = args[2] if len(args) > 2 else None
        else:
            flags = box
        names = window_flags(flags)
        parts.append("flags=" + ("|".join(names) if names else "none"))
        return " ".join(parts)


def install_imgui(lua):
    """Install the recording ImGui stub into `lua` and return its handle.

    Populates package.loaded['imgui'] so require('imgui') at ui.lua:28
    resolves to it, and sets the ImGui* enum globals ui.render reads.
    """
    return ImGuiRecorder(lua)
