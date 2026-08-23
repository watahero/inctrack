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
*
* Layout is deliberately dense -- this sits on screen for an hour at a time:
*
*     Fort Ghelsba . Normal                      ~64:00
*     [=========== Phase #3  12/15 ============      ]
*     Orcish Grunt, Orcish Neckchopper, Orcish Stonechucker
*     Next: Orcish Sieger                          (I-9)
*     BONUS Sentry Lizard 2/5                       6:00
*     [=====--------------------------------------------]
*     Pts 233  Ph 2                         Elapsed 4:00
*     Ronin's Revenge, Stallwart's Sentinel   (hover: stats)
]]--

local imgui = require('imgui');

local ui = {};

local COLOR = {
    dim      = { 0.62, 0.62, 0.66, 1.00 },
    text     = { 0.90, 0.90, 0.92, 1.00 },
    instance = { 1.00, 0.86, 0.45, 1.00 },
    boss     = { 1.00, 0.55, 0.35, 1.00 },
    bonus    = { 0.60, 0.80, 1.00, 1.00 },
    boon     = { 0.78, 0.70, 0.95, 1.00 },
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

-- The phase bar carries its own label as overlay text; secondary bars are
-- thin strips under a text line.
local BAR_MAIN = 16;
local BAR_THIN = 5;

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
local ARG_SPACER    = { CONTENT_W, 1 };
local ARG_BAR_MAIN  = { -1, BAR_MAIN };
local ARG_BAR_THIN  = { -1, BAR_THIN };
local ARG_OPEN      = { true };
local ARG_PAD_TIGHT = { 4, 2 };   -- ItemSpacing while the window is open

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

local function bar(fraction, color, size, overlay)
    if fraction < 0 then fraction = 0 end
    if fraction > 1 then fraction = 1 end
    imgui.PushStyleColor(ImGuiCol_PlotHistogram, color);
    imgui.ProgressBar(fraction, size, overlay or '');
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

-- Instance, difficulty, and the instance clock on one line.
local function draw_header(state, run)
    imgui.TextColored(COLOR.instance, run.instance or 'Incursion');
    if run.difficulty then
        imgui.SameLine();
        imgui.TextColored(COLOR.dim, '. ' .. run.difficulty);
    end

    if run.finished then
        right_text('Complete ' .. (run.finish_time or ''), COLOR.good);
        return;
    end

    -- The server only ever reports whole minutes, so this is an estimate
    -- between syncs. The tilde says so rather than implying second accuracy.
    local left = state:time_left();
    right_text(left and ('~' .. clock_str(left)) or '--:--', urgency(left, 300, 60));
end

local function draw_objective(run)
    if run.finished then
        return;
    end

    local obj = run.objective;

    if not obj then
        -- Recovered mid-run: the server does not re-announce the objective,
        -- so say so rather than showing a stale or empty line.
        imgui.TextColored(COLOR.dim, 'Waiting for next objective...');
        return;
    end

    if obj.kind == 'boss' then
        -- One full orange bar carrying the whole message.
        local label = 'BOSS  ' .. (obj.name or '?');
        if obj.loc then
            label = label .. '  ' .. obj.loc;
        end
        bar(1.0, COLOR.bar_boss, ARG_BAR_MAIN, label);
        return;
    end

    -- An objective wording the parser did not recognise. Show it verbatim
    -- rather than an empty panel -- this is what lets new content still read.
    if obj.kind == 'text' then
        wrapped(obj.text or '?', COLOR.text);
        return;
    end

    -- Kill phase: the bar is the line, with phase and count as its label.
    local cur = run.kills_cur or 0;
    local max = run.kills_max or obj.count or 0;
    local label = string.format('%s  %d/%d',
        run.phase and ('Phase #' .. run.phase) or 'Phase', cur, max);
    if run.desynced then
        -- While out of sync the count is the last one we saw, not the truth.
        label = label .. ' ?';
    end
    bar(max > 0 and (cur / max) or 0,
        run.desynced and COLOR.bar_stale or COLOR.bar_kills,
        ARG_BAR_MAIN, label);

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
        imgui.TextColored(COLOR.dim, 'Next: ');
        imgui.SameLine();
        imgui.TextColored(COLOR.text, run.next_boss.name);
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

    if bonus.done then
        imgui.TextColored(COLOR.good, 'BONUS  Complete!');
        return;
    end

    local label = bonus.label or '?';
    if bonus.max and bonus.max > 1 then
        label = string.format('%s  %d/%d', label, bonus.cur or 0, bonus.max);
    elseif bonus.loc then
        label = label .. '  ' .. bonus.loc;
    end

    imgui.TextColored(COLOR.bonus, 'BONUS ');
    imgui.SameLine();
    imgui.TextColored(COLOR.text, label);

    local remaining = state:bonus_remaining();
    if remaining then
        right_text(clock_str(remaining), urgency(remaining, 120, 30));
    end

    if bonus.max and bonus.max > 1 then
        bar((bonus.cur or 0) / bonus.max, COLOR.bar_bonus, ARG_BAR_THIN);
    end
end

-- Counters from message shapes we do not specifically know.
local function draw_extra(state, run)
    if run.finished then
        return;
    end

    local list = state:extra_sorted();
    for i = 1, #list do
        local entry = list[i];
        local done = entry.done or (entry.max and entry.cur and entry.cur >= entry.max);

        imgui.TextColored(done and COLOR.good or COLOR.dim, entry.label);

        if entry.max and entry.max > 0 then
            right_text(string.format('%d/%d', entry.cur or 0, entry.max),
                       done and COLOR.good or COLOR.text);
            bar((entry.cur or 0) / entry.max,
                done and COLOR.bar_done or COLOR.bar_extra, ARG_BAR_THIN);
        elseif done then
            right_text('done', COLOR.good);
        end
    end
end

-- Points, phases cleared, elapsed -- one line.
local function draw_stats(state, run)
    -- '+' marks a total we know is short: boss kills that happened while we
    -- were disconnected awarded points the client never saw.
    local points = tostring(run.points or 0);
    if run.points_partial then
        points = points .. '+';
    end

    imgui.TextColored(COLOR.dim, 'Pts ');
    imgui.SameLine();
    imgui.TextColored(run.points_partial and COLOR.warn or COLOR.instance, points);
    imgui.SameLine();
    imgui.TextColored(COLOR.dim, '  Ph ');
    imgui.SameLine();
    imgui.TextColored(COLOR.text, tostring(run.phases_cleared or 0));

    right_text('Elapsed ' .. clock_str(state:elapsed()), COLOR.dim);
end

-- The boons chosen this run: names on one wrapped line, stats on hover so a
-- run with seven picks does not turn the window into a spreadsheet.
local function draw_boons(run)
    local boons = run.boons;
    if not boons or #boons == 0 then
        return;
    end

    local names = {};
    for i = 1, #boons do
        names[i] = boons[i].name;
    end
    wrapped(table.concat(names, ', '), COLOR.boon);

    if imgui.IsItemHovered() then
        imgui.BeginTooltip();
        for i = 1, #boons do
            imgui.TextColored(COLOR.boon, boons[i].name);
            if boons[i].stats then
                imgui.SameLine();
                imgui.TextColored(COLOR.dim, '  ' .. boons[i].stats);
            end
        end
        imgui.EndTooltip();
    end
end

-- The most recent Incursion line we could not interpret, while it is fresh.
local function draw_note(state)
    local note = state:note();
    if note then
        wrapped(note);
    end
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
    -- frame (bonus, extras and boons come and go). The width is held constant
    -- by the spacer below, so the auto-resize never oscillates.
    local flags = ImGuiWindowFlags_NoFocusOnAppearing
        + ImGuiWindowFlags_AlwaysAutoResize
        + ImGuiWindowFlags_NoScrollbar
        + ImGuiWindowFlags_NoTitleBar;
    if opts.locked then
        flags = flags + ImGuiWindowFlags_NoMove;
    end

    imgui.PushStyleVar(ImGuiStyleVar_ItemSpacing, ARG_PAD_TIGHT);

    ARG_OPEN[1] = true;
    if imgui.Begin('IncursionTracker###incursion_window', ARG_OPEN, flags) then
        origin_x = imgui.GetCursorPosX();
        imgui.Dummy(ARG_SPACER);   -- pins the content width to CONTENT_W

        draw_header(state, run);
        if run.desynced and not run.finished then
            imgui.TextColored(COLOR.warn, 'reconnected - awaiting update');
        end
        draw_objective(run);
        draw_bonus(state, run);
        draw_extra(state, run);
        draw_stats(state, run);
        draw_boons(run);
        draw_note(state);
    end
    imgui.End();

    imgui.PopStyleVar(1);

    -- The close button was clicked.
    if not ARG_OPEN[1] then
        return false;
    end
    return opts.visible;
end

return ui;
