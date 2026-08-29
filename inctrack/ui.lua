--[[
* inctrack -- ui.lua
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
*     Phases cleared 2                      Elapsed 4:00
*     Ronin's Revenge                   WS Acc+15 STP+8
*     Stallwart's Sentinel                VIT+10 DT-15%
*
* The sample is one shape out of many, and it cannot show the rows that only
* appear when something has gone sideways. Below is every row the window can
* draw, in the order render() draws them, with the condition each appears
* under. A whole-window snapshot in the suite is reviewed against this list
* before it is pasted in, so a row missing here is a row nothing pins.
*
*   1. An invisible spacer, CONTENT_W wide. Every frame, unconditionally: it
*      is what holds the width of an auto-resizing window still.
*   2. Header. The instance name always, then '. <difficulty>' when one is
*      known. Right-aligned on the same line: 'Complete <the server's own run
*      time>' once the run has finished, otherwise the instance clock as
*      '~mm:ss' -- or '--:--' when no timer sync has landed yet.
*   3. 'reconnected - awaiting update', while the run is desynced and has not
*      finished.
*   4. The objective block. Nothing at all once the run is finished; otherwise
*      exactly one of:
*        - a full orange bar 'BOSS  <name>  <loc>', once the kills are done;
*        - the phase bar, labelled 'Phase #N  cur/max' -- amber and suffixed
*          ' ?' while desynced -- and under it the mob list, suffixed '  (?)'
*          when it belongs to a phase the server never confirmed for us, and
*          then 'Next: <name>' with the coordinates right-aligned, when a boss
*          preview is held;
*        - an objective wording the parser did not recognise, drawn verbatim
*          and wrapped;
*        - 'Waiting for next objective...', when there is no objective at all
*          -- a run picked up mid-phase, which the server does not re-announce.
*   5. The bonus row, while a bonus is held and has not lapsed:
*      'BONUS  Complete!' once done, otherwise 'BONUS <label>' with '  cur/max'
*      when it counts past one or its coordinates when it names a place, the
*      countdown right-aligned when one is known, and a thin progress strip
*      beneath when it counts.
*   6. One row per counter in a shape the parser does not specifically know:
*      the label, then 'cur/max' right-aligned above a thin strip when it has
*      a maximum, or 'done' right-aligned when it has none. Gone once the run
*      has finished.
*   7. 'Phases cleared N' with 'Elapsed m:ss' right-aligned. Always, and the
*      only stats row there is: points are tracked in state.lua and are
*      deliberately never displayed.
*   8. One row per boon picked this run, in pick order: the name, and the
*      stats right-aligned in the usual FFXI shorthand.
*   9. The most recent Incursion line the parser could not interpret, for the
*      thirty seconds it stays fresh.
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

-- Phases cleared and elapsed -- one line. Points are tracked in state (the
-- count of awards is how phases cleared is derived) but not displayed.
local function draw_stats(state, run)
    imgui.TextColored(COLOR.dim, 'Phases cleared ');
    imgui.SameLine();
    imgui.TextColored(COLOR.text, tostring(run.phases_cleared or 0));

    right_text('Elapsed ' .. clock_str(state:elapsed()), COLOR.dim);
end

--[[
* Boon stat text, shortened to the usual FFXI abbreviations for display.
*
* Display-only: the run record keeps the server's wording. Longer phrases are
* listed before their substrings ('R.Accuracy' before 'Accuracy', 'Physical
* dmg taken' before 'Damage taken') so each is replaced whole. Anything not in
* the table passes through untouched, so a boon added later still reads.
]]--
local STAT_SHORT = {
    { 'HP/MP Rec. while healing', 'Rest'  },
    { 'Physical dmg taken',       'PDT'   },
    { 'Phys. dmg taken',          'PDT'   },
    { 'Damage taken',             'DT'    },
    { 'Magic Atk. Bonus',         'MAB'   },
    { 'Magic Acc.',               'MAcc'  },
    { 'WS Accuracy',              'WS Acc'},
    { 'R.Accuracy',               'RAcc'  },
    { 'R.Attack',                 'RAtt'  },
    { 'Dbl. Attack',              'DA'    },
    { 'Accuracy',                 'Acc'   },
    { 'Attack',                   'Att'   },
    { 'Crit. Hit Rate',           'Crit'  },
    { 'Store TP',                 'STP'   },
    { 'Cure Potency',             'Cure'  },
    { 'Waltz Potency',            'Waltz' },
    { 'Fast Cast',                'FC'    },
    { 'Move. Speed',              'Speed' },
    { 'Combat Skills',            'Skills'},
    { 'Evasion',                  'Eva'   },
    { 'Enmity',                   'Enm'   },
};

-- Plain-text find/replace; the phrases contain '.' which Lua patterns would
-- otherwise treat as a wildcard.
local function replace_plain(s, from, to)
    local out, i = {}, 1;
    while true do
        local a, b = s:find(from, i, true);
        if not a then
            out[#out + 1] = s:sub(i);
            break;
        end
        out[#out + 1] = s:sub(i, a - 1);
        out[#out + 1] = to;
        i = b + 1;
    end
    return table.concat(out);
end

--[[
* Memoised: the same few strings are shortened every frame.
*
* Bounded, and three separate judgements went into how:
*
* Why a bound at all. The key is text the server chose, and this addon lives
* as long as the client does. Nothing about a stat string is bounded by
* anything the addon controls, so without a cap this table grows for a whole
* play session.
*
* Why the whole cache rather than an eviction policy. A run's boon stat
* strings are few and repeat every frame, so an LRU is more code -- code on
* the render path -- for no measurable gain on real traffic. Dropping the lot
* costs one re-shorten per live string on the next frame that draws it.
*
* Why 64. A run's boons are a handful, and 64 is far above any run the
* 127-log corpus holds, so the drop can only ever fire on input the server
* never sent. A bound that is reached in ordinary play would be trading a
* real cost for a hypothetical one.
*
* short_clear() empties this table in place and never assigns a fresh one.
* ui.lua's file-scope locals are reachable only by upvalue reflection, so a
* replaced table would leave any handle taken on it an orphan, measuring a
* cache the addon no longer uses.
]]--
local SHORT_CACHE_MAX = 64;
local short_cache = {};
local short_held = 0;

local function short_clear()
    for key in pairs(short_cache) do
        short_cache[key] = nil;
    end
    short_held = 0;
end

--[[
* Drop everything memoised for a run that is over.
*
* The second thing this file has ever exported, and it has to be: it cannot
* be inferred from inside render. After a reset there is no run, so the shell
* stops calling render at all and the draw function never gets a frame in
* which to notice that what it cached belongs to nobody. The shell knows; the
* window cannot.
]]--
function ui.forget()
    short_clear();
end

local function shorten(stats)
    local hit = short_cache[stats];
    if hit then
        return hit;
    end

    local s = stats;
    for i = 1, #STAT_SHORT do
        s = replace_plain(s, STAT_SHORT[i][1], STAT_SHORT[i][2]);
    end
    -- 'Skills +10' -> 'Skills+10'; ' / ' -> single space.
    s = s:gsub('%s+([%+%-])', '%1'):gsub('%s*/%s*', ' ');

    -- At the cap, drop the lot and start again, so the table never holds more
    -- than SHORT_CACHE_MAX entries on any call.
    if short_held >= SHORT_CACHE_MAX then
        short_clear();
    end
    short_cache[stats] = s;
    short_held = short_held + 1;
    return s;
end

-- The boons chosen this run, one per line: name, then shorthand stats.
local function draw_boons(run)
    local boons = run.boons;
    if not boons or #boons == 0 then
        return;
    end

    for i = 1, #boons do
        imgui.TextColored(COLOR.boon, boons[i].name);
        if boons[i].stats then
            right_text(shorten(boons[i].stats), COLOR.dim);
        end
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
* Returns the visibility it was given. The window carries no close control
* of its own -- it is drawn without a title bar, so there is nowhere to put
* one. /incursion is the manual dismiss, and the linger after a run ends is
* the automatic one.
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

    -- Explicit nil for p_open. Ashita's binding is declared once and
    -- positionally -- Begin(const char* name, bool* p_open, ImGuiWindowFlags
    -- flags), plugins/sdk/imgui.h:305 -- and addons/libs/imgui.lua adds no
    -- wrapper of its own: it is a constants table whose __index is
    -- AshitaCore:GetGuiManager(), so this call reaches that signature
    -- unmediated. Flags must therefore go in slot 3. Passing nil is not the
    -- same as passing a box and ignoring it: it asks for no close control at
    -- all, which is what this window wants -- it is drawn without a title
    -- bar, so there is nowhere for one to appear.
    if imgui.Begin('inctrack###incursion_window', nil, flags) then
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

    return opts.visible;
end

return ui;
