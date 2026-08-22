--[[
* IncursionTracker -- ui.lua
* Copyright (c) 2026 Godwen. MIT License; see LICENSE in the repository root.
* Written with Claude (Anthropic).
]]--

--[[
* ui.lua -- Incursion tracker window.
*
* Read-only: renders a run record from state.lua and never mutates it.
*
* No instance, boss, mob or objective name appears in this file. Everything
* drawn comes from the run record, which comes from the server's own messages.
]]--

local imgui = require('imgui');

local ui = {};

local COLOR = {
    dim      = { 0.62, 0.62, 0.66, 1.00 },
    text     = { 0.90, 0.90, 0.92, 1.00 },
    instance = { 1.00, 0.86, 0.45, 1.00 },
    boss     = { 1.00, 0.55, 0.35, 1.00 },
    bonus    = { 0.60, 0.80, 1.00, 1.00 },
    good     = { 0.45, 0.88, 0.50, 1.00 },
    warn     = { 1.00, 0.75, 0.30, 1.00 },
    bad      = { 1.00, 0.42, 0.42, 1.00 },

    bar_kills = { 0.30, 0.62, 0.90, 1.00 },
    bar_boss  = { 0.90, 0.45, 0.28, 1.00 },
    bar_bonus = { 0.42, 0.70, 0.95, 1.00 },
    bar_extra = { 0.55, 0.55, 0.72, 1.00 },
    bar_stale = { 0.72, 0.60, 0.30, 1.00 },
    bar_done  = { 0.35, 0.72, 0.40, 1.00 },
};

local BAR_HEIGHT = 14;

--[[
* The window auto-fits its height, but the content width is pinned to a
* constant by an invisible spacer drawn each frame. Right-aligned values are
* positioned against that constant rather than the live window width --
* aligning against the live width of an auto-resizing window feeds the
* alignment back into the computed size and it never settles.
]]--
local CONTENT_W = 300;

-- Window-local x of the content's left edge, captured once per frame after
-- Begin() so right alignment does not depend on the padding style.
local origin_x = 8;

-- Hoisted per-frame arguments; ImGui reads them, never keeps them, and
-- rebuilding them every frame at 60fps is pure GC churn.
local ARG_SPACER   = { CONTENT_W, 1 };
local ARG_BAR_SIZE = { -1, BAR_HEIGHT };
local ARG_OPEN     = { true };

-- mm:ss, or h:mm:ss past an hour.
local function clock_str(seconds)
    if not seconds then
        return '--:--';
    end
    seconds = math.floor(seconds);
    local h = math.floor(seconds / 3600);
    local m = math.floor((seconds % 3600) / 60);
    local s = seconds % 60;
    if h > 0 then
        return string.format('%d:%02d:%02d', h, m, s);
    end
    return string.format('%d:%02d', m, s);
end

-- Right-align a value on the current line, against the fixed content width.
local function right_text(text, color)
    imgui.SameLine();
    local target = origin_x + CONTENT_W - imgui.CalcTextSize(text);
    -- If the left side of the line already reaches the target, let the value
    -- sit after it rather than overprinting.
    if target > imgui.GetCursorPosX() then
        imgui.SetCursorPosX(target);
    end
    imgui.TextColored(color or COLOR.text, text);
end

local function wrapped(text, color)
    -- Wrap at the pinned content width, not at 0 (= the live window edge):
    -- inside an auto-resizing window the live edge is derived from the very
    -- text being wrapped, which is circular.
    imgui.PushTextWrapPos(origin_x + CONTENT_W);
    imgui.TextColored(color or COLOR.dim, text);
    imgui.PopTextWrapPos();
end

local function bar(fraction, color, overlay)
    if fraction < 0 then fraction = 0 end
    if fraction > 1 then fraction = 1 end
    imgui.PushStyleColor(ImGuiCol_PlotHistogram, color);
    imgui.ProgressBar(fraction, ARG_BAR_SIZE, overlay or '');
    imgui.PopStyleColor(1);
end

-- Colour by urgency, so a nearly-expired timer is obvious at a glance.
local function urgency(seconds, warn_at, bad_at)
    if not seconds then
        return COLOR.dim;
    end
    if seconds <= bad_at then
        return COLOR.bad;
    end
    if seconds <= warn_at then
        return COLOR.warn;
    end
    return COLOR.text;
end

local function draw_header(run)
    imgui.TextColored(COLOR.instance, run.instance or 'Incursion');
    if run.difficulty then
        right_text(run.difficulty, COLOR.dim);
    end
end

local function draw_objective(run)
    local obj = run.objective;

    if run.finished then
        imgui.TextColored(COLOR.good, 'Complete!');
        if run.finish_time then
            right_text(run.finish_time, COLOR.dim);
        end
        return;
    end

    if not obj then
        -- Recovered mid-run: the server does not re-announce the objective,
        -- so say so rather than showing a stale or empty line.
        imgui.TextColored(COLOR.dim, 'Waiting for next objective...');
        return;
    end

    if obj.kind == 'boss' then
        imgui.TextColored(COLOR.boss, 'BOSS');
        imgui.SameLine();
        imgui.TextColored(COLOR.text, obj.name or '?');
        if obj.loc then
            right_text(obj.loc, COLOR.boss);
        end
        bar(1.0, COLOR.bar_boss);
        return;
    end

    -- An objective wording the parser did not recognise. Show it verbatim
    -- rather than an empty panel -- this is what lets new content still read.
    if obj.kind == 'text' then
        wrapped(obj.text or '?', COLOR.text);
        return;
    end

    -- Kill phase.
    local cur = run.kills_cur or 0;
    local max = run.kills_max or obj.count or 0;

    imgui.TextColored(COLOR.dim, run.phase and ('Phase #' .. run.phase) or 'Phase');

    -- While out of sync the count is the last one we saw, not the truth.
    right_text(string.format('%d/%d', cur, max),
               run.desynced and COLOR.warn or COLOR.text);

    bar(max > 0 and (cur / max) or 0,
        run.desynced and COLOR.bar_stale or COLOR.bar_kills);

    if obj.mobs and #obj.mobs > 0 then
        -- Flagged when we came back on a different phase: these are probably
        -- right, since consecutive phases often share a mob set, but the
        -- server never confirmed them for this phase.
        local mobs = table.concat(obj.mobs, ', ');
        if obj.stale then
            wrapped(mobs .. '  (?)', COLOR.warn);
        else
            wrapped(mobs);
        end
    end

    if run.next_boss then
        imgui.TextColored(COLOR.dim, 'Next: ' .. run.next_boss.name);
        if run.next_boss.loc then
            right_text(run.next_boss.loc, COLOR.dim);
        end
    end
end

local function draw_bonus(state, run)
    local bonus = state:bonus();
    if not bonus then
        return;
    end

    imgui.Separator();

    if bonus.done then
        imgui.TextColored(COLOR.good, 'BONUS');
        imgui.SameLine();
        imgui.TextColored(COLOR.good, 'Complete!');
        bar(1.0, COLOR.bar_done);
        return;
    end

    local remaining = state:bonus_remaining();

    imgui.TextColored(COLOR.bonus, 'BONUS');
    imgui.SameLine();
    imgui.TextColored(COLOR.text, bonus.label or '?');

    if remaining then
        right_text(clock_str(remaining), urgency(remaining, 120, 30));
    end

    if bonus.max and bonus.max > 1 then
        bar((bonus.cur or 0) / bonus.max,
            COLOR.bar_bonus,
            string.format('%d/%d', bonus.cur or 0, bonus.max));
    elseif bonus.loc then
        imgui.TextColored(COLOR.dim, bonus.loc);
    end
end

-- Counters from message shapes we do not specifically know.
local function draw_extra(state, run)
    if run.finished then
        return;
    end

    local list = state:extra_sorted();
    if #list == 0 then
        return;
    end

    imgui.Separator();

    for i = 1, #list do
        local entry = list[i];
        local done = entry.done or (entry.max and entry.cur and entry.cur >= entry.max);

        imgui.TextColored(done and COLOR.good or COLOR.dim, entry.label);

        if entry.max and entry.max > 0 then
            right_text(string.format('%d/%d', entry.cur or 0, entry.max), COLOR.text);
            bar((entry.cur or 0) / entry.max,
                done and COLOR.bar_done or COLOR.bar_extra);
        elseif done then
            right_text('done', COLOR.good);
        end
    end
end

-- Two label/value pairs on one line, split at the fixed content midpoint.
local function stat_row(l1, v1, c1, l2, v2, c2)
    imgui.TextColored(COLOR.dim, l1);
    imgui.SameLine();
    imgui.TextColored(c1 or COLOR.text, v1);

    imgui.SameLine();
    local mid = origin_x + CONTENT_W / 2;
    if mid > imgui.GetCursorPosX() then
        imgui.SetCursorPosX(mid);
    end
    imgui.TextColored(COLOR.dim, l2);
    imgui.SameLine();
    imgui.TextColored(c2 or COLOR.text, v2);
end

local function draw_stats(state, run)
    imgui.Separator();

    local left = state:time_left();
    -- The server only ever reports whole minutes, so this is an estimate
    -- between syncs. The tilde says so rather than implying second accuracy.
    local left_str = left and ('~' .. clock_str(left)) or '--:--';

    stat_row('Time left', left_str, urgency(left, 300, 60),
             'Elapsed', clock_str(state:elapsed()));

    -- '+' marks a total we know is short: boss kills that happened while we
    -- were disconnected awarded points the client never saw.
    local points = tostring(run.points or 0);
    if run.points_partial then
        points = points .. '+';
    end

    stat_row('Points', points,
             run.points_partial and COLOR.warn or COLOR.instance,
             'Phases', tostring(run.phases_cleared or 0));
end

-- The most recent Incursion line we could not interpret, while it is fresh.
local function draw_note(state)
    local note = state:note();
    if not note then
        return;
    end
    imgui.Separator();
    wrapped(note);
end

--[[
* Render the window.
*
* state -- the State instance
* opts  -- { visible = bool, locked = bool }
*
* Returns the (possibly updated) visibility, so a click on the title bar's
* close button propagates back to the caller.
]]--
function ui.render(state, opts)
    local run = state:snapshot();
    if not run then
        return opts.visible;
    end

    -- Auto-resize fits the height to whatever sections are visible this
    -- frame (bonus and extras come and go). The width is held constant by
    -- the spacer below, so the auto-resize never oscillates.
    local flags = ImGuiWindowFlags_NoFocusOnAppearing
        + ImGuiWindowFlags_AlwaysAutoResize
        + ImGuiWindowFlags_NoScrollbar;
    if opts.locked then
        flags = flags + ImGuiWindowFlags_NoMove;
    end

    ARG_OPEN[1] = true;
    if imgui.Begin('Incursion###incursion_window', ARG_OPEN, flags) then
        origin_x = imgui.GetCursorPosX();
        imgui.Dummy(ARG_SPACER);   -- pins the content width to CONTENT_W

        draw_header(run);
        imgui.Separator();
        if run.desynced and not run.finished then
            imgui.TextColored(COLOR.warn, 'reconnected - awaiting update');
        end
        draw_objective(run);
        draw_bonus(state, run);
        draw_extra(state, run);
        draw_stats(state, run);
        draw_note(state);
    end
    imgui.End();

    -- The close button was clicked.
    if not ARG_OPEN[1] then
        return false;
    end
    return opts.visible;
end

return ui;
