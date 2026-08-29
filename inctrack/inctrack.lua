--[[
* inctrack -- live objective and progress HUD for CatsEyeXI Incursions.
*
* Copyright (c) 2026 Godwen
* Licensed under the MIT License. See LICENSE in the repository root.
*
* Written with Claude (Anthropic). This is an independent project and is not
* affiliated with the CatsEyeXI server team or with any other Incursion addon
* or plugin (including trove's Incursion browser).
*
* Reads the server's own chat messages; no packet or memory inspection.
*
* Usage:
*     /incursion          Toggle the window
*     /incursion reset    Clear the current run
*     /incursion lock     Toggle window drag lock
*     /incursion auto     Toggle automatic show/hide
]]--

addon.name    = 'inctrack';
addon.author  = 'Godwen';
addon.version = '1.1.0';
addon.link    = 'https://github.com/watahero/inctrack';
addon.desc    = 'Live Incursion objective, progress and timers. Independent project, not affiliated with other Incursion addons.';

require('common');

local chat     = require('chat');
local settings = require('settings');
local json     = require('json');
local parser   = require('parser');
local State    = require('state');
local ui       = require('ui');
-- ui.lua requires this too, so both handles are the same table through
-- package.loaded. The shell needs its own because the stack repair after a
-- caught render error is made from here, not from the draw function.
local imgui    = require('imgui');

local default_settings = T{
    -- Show and hide the window automatically around a run.
    auto    = true,
    -- Prevent the window from being dragged.
    locked  = false,
    -- The in-progress run, JSON encoded. A single string rather than a nested
    -- table so the settings merge cannot reshape it on the way back in.
    session = '',
};

local incursion = T{
    settings = settings.load(default_settings),
    state    = nil,
    -- nil follows automatic visibility; true/false is a manual override that
    -- lasts until the next run starts.
    override = nil,
    save_at  = 0,
    -- Set when ui.render raised inside d3d_present. The window takes itself
    -- off screen for the rest of the session rather than failing sixty times
    -- a second; /incursion and /incursion reset both clear it.
    render_off = false,
    -- Set the first time render returned cleanly with a run to draw. It says
    -- the render shape has run end to end on this host, which is what makes
    -- the stack repair below a repair rather than a guess. Deliberately not
    -- cleared by reset(): it is a fact about the host, not about the run.
    render_ok  = false,
    -- Set the first time the chat handler's pcall came back false. A line the
    -- addon cannot read is not a one-off: a systematically malformed shape
    -- arrives on every chat line the client receives, so an unrated complaint
    -- is the same sentence sixty times in a burst. /incursion reset and a
    -- character change both clear it, so the player has a stated way back
    -- rather than having to reload the addon. Same rule as render_off, and
    -- deliberately the same shape -- one way of saying a thing once.
    parse_told = false,
};

-- Events worth a disk write the moment they land, because the server never
-- sends them again. Everything else rides the throttle.
local MUST_SAVE = {
    begin          = true,
    recover        = true,
    complete       = true,
    objective_kills = true,
    objective_boss = true,
    objective_text = true,
    boss_hint      = true,
    bonus_new      = true,
    bonus_done     = true,
    generic_done   = true,
    boon           = true,
};

local function printf(fmt, ...)
    print(chat.header(addon.name) .. chat.message(fmt:format(...)));
end

--[[
* Ashita has no monotonic clock exposed to addons, so os.clock is used. It
* measures process CPU-ish time on some builds, but on Windows it is wall time
* since process start, which is exactly what the timers need and, unlike
* os.time, it has sub-second resolution.
]]--
local function now()
    return os.clock();
end

--[[
* Persist the current run so a reload, crash, or zone-out mid-Incursion does
* not lose it. The server never re-announces the objective on recovery, so
* without this the window would come back blank for the rest of the phase.
]]--
local function persist()
    local blob = incursion.state:serialise();
    local ok, encoded = pcall(json.encode, blob);
    incursion.settings.session = (ok and blob ~= nil) and encoded or '';
    settings.save();
end

local function reset(quiet)
    incursion.state:reset();
    incursion.override = nil;
    -- Clearing the run is also a way back from a window that switched itself
    -- off, and from a chat handler that has stopped complaining, so
    -- /incursion reset recovers both as well as the run.
    incursion.render_off = false;
    incursion.parse_told = false;
    incursion.settings.session = '';
    settings.save();
    if not quiet then
        printf('Run cleared.');
    end
end

--[[
* Take up a saved run, or say why it could not be taken up.
*
* Returns the decoded blob when the run was resumed and nil otherwise; the
* caller clears the stored string on nil, so an unusable blob is not retried
* on every load forever.
*
* The refusal used to be silent, which was defensible while the only ways to
* fail were unreadable JSON, a finished run and a three-hour-old blob. The
* structural validator widened it to every shape mismatch, and what the
* player sees on a rejection is a mid-run reload where the HUD comes back
* with nothing and then bootstraps a fresh run from the next Incursion line:
* phase nil, no boons, elapsed counting from zero, and no 'reconnected'
* marking on any of it, because a bootstrapped run is not a desynced one.
* That is a window showing numbers the server never sent, unmarked -- the one
* thing this addon exists not to do.
*
* Silence is still right for a run that had already finished. restore()
* refuses those deliberately, there is nothing left to resume, and saying a
* run 'could not be resumed' when the player watched it end would be the same
* fault pointed the other way.
]]--
local function resume(saved)
    local ok, blob = pcall(json.decode, saved);
    if ok and type(blob) == 'table' and incursion.state:restore(blob) then
        return blob;
    end
    if not (ok and type(blob) == 'table' and blob.finished) then
        printf('Saved run could not be resumed -- unreadable, too old, or '
               .. 'not a shape this build knows. Starting fresh.');
    end
    return nil;
end

-- Whether the window should be drawn right now.
local function visible()
    if incursion.override ~= nil then
        return incursion.override;
    end
    if not incursion.settings.auto then
        return false;
    end
    return incursion.state:should_show();
end

incursion.state = State.new({ clock = now });

--[[
* event: load
]]--
ashita.events.register('load', 'incursion_load', function ()
    -- Identify this build plainly so it is not mistaken for another Incursion
    -- addon or plugin.
    printf('v%s by %s (written with Claude). /incursion to toggle.', addon.version, addon.author);

    local name = AshitaCore:GetMemoryManager():GetParty():GetMemberName(0);
    if name ~= nil and name ~= '' then
        incursion.state:set_player(name);
    end

    -- Resume a run that was in progress when we were last unloaded. A corrupt
    -- or stale blob is discarded rather than half-applied, and the discard is
    -- said out loud: see resume().
    local saved = incursion.settings.session;
    if type(saved) == 'string' and saved ~= '' then
        local blob = resume(saved);
        if blob ~= nil then
            printf('Resumed run in %s.', tostring(blob.instance));
        else
            incursion.settings.session = '';
            settings.save();
        end
    end
end);

--[[
* event: unload
]]--
ashita.events.register('unload', 'incursion_unload', function ()
    persist();
end);

--[[
* event: text_in
*
* Read-only. The message is never modified or blocked, and a parse failure can
* never take the chat handler down with it.
]]--
ashita.events.register('text_in', 'incursion_text_in', function (e)
    local ok, err = pcall(function ()
        local line = e.message;
        if line == nil or line == '' then
            return;
        end

        -- Could this be ours at all? Asked here, on the raw message, because
        -- strip_colors is this handler's own call: no reordering inside
        -- parser.lua can decline to make it, so this is the only place the
        -- allocation is actually avoidable. A line carrying a colour code is
        -- never turned away here -- the gate declines to judge one, since a
        -- code can sit inside the very text it searches for.
        if not parser.relevant(line) then
            return;
        end

        -- Colour codes would defeat the anchored patterns.
        line = line:strip_colors();

        local event = parser.parse(line);
        if event == nil then
            return;
        end

        -- The player name is not always available at load time (logging in
        -- with the addon already active), so fill it in when we can.
        if incursion.state.player == nil then
            local name = AshitaCore:GetMemoryManager():GetParty():GetMemberName(0);
            if name ~= nil and name ~= '' then
                incursion.state:set_player(name);
            end
        end

        if incursion.state:apply(event) then
            -- A new run cancels any manual show/hide from the previous one.
            if event.t == 'begin' then
                incursion.override = nil;
            end

            -- Save immediately for anything the server will not repeat -- the
            -- objective and boss above all, since 'Recovering session...' does
            -- not re-announce them. Kill counts arrive constantly and are
            -- cheap to lose, so those only force a save every few seconds.
            local t = now();
            if MUST_SAVE[event.t] or (t - incursion.save_at) > 5.0 then
                incursion.save_at = t;
                persist();
            end
        end
    end);

    --[[
    * The failure path only prints. It does not reset state, does not disable
    * anything and does not stop the handler reading the next line -- this is
    * not the render latch, because a parse error costs one line, not the
    * frame. All the latch changes is how often the player hears about it.
    *
    * tostring(err) stays an argument and never becomes part of the format
    * string: a percent sign in server text is one of the things that gets us
    * here in the first place.
    ]]--
    if not ok and not incursion.parse_told then
        incursion.parse_told = true;
        printf('parse error: %s -- further ones this session will not be '
               .. 'reported; /incursion reset to hear them again.',
               tostring(err));
    end
end);

--[[
* event: d3d_present
*
* ui.render runs here, on the game thread, once per frame. It is handed
* strings that came off the wire and tables that came out of a JSON blob, so
* an error is reachable -- and an error here is not a log line: it leaves the
* ImGui window and style stacks unbalanced for every addon in the process,
* and then it happens again on the next frame, and the one after.
*
* So it is contained here rather than inside ui.lua, beside the pcall that
* has protected text_in since 1.0.0. One pattern, one place, and ui.lua stays
* a pure draw function.
]]--
ashita.events.register('d3d_present', 'incursion_present', function ()
    -- Already failed once this session. Return before asking anything else,
    -- so the failure costs one branch a frame instead of repeating.
    if incursion.render_off then
        return;
    end

    if not visible() then
        return;
    end

    local ok, err = pcall(ui.render, incursion.state, {
        visible = true,
        locked  = incursion.settings.locked,
    });

    if ok then
        -- A frame that took render's early return proves nothing about the
        -- window, so the latch wants a run to have been drawn as well. The
        -- guard short-circuits once it is set, so after the first drawn frame
        -- this costs nothing.
        if not incursion.render_ok and incursion.state:snapshot() ~= nil then
            incursion.render_ok = true;
        end
        return;
    end

    --[[
    * Repair what is owed, and only what is owed.
    *
    * render's shape is fixed and short -- state:snapshot() with its early
    * return, the flags arithmetic, one PushStyleVar, Begin, the draws, an
    * unconditional End, the pop -- and three of those statements run *before*
    * Begin. A raise from any of them leaves nothing open and nothing pushed,
    * so an End there is an unmatched close: on a real host that is an ImGui
    * assert, which would make this repair the second error of the frame --
    * the exact failure the guard above exists to prevent.
    *
    * render_ok is the one fact the shell can hold honestly. It says the
    * render shape has run end to end on this host at least once, so the
    * constants are good, the push is good and the Begin is good, and what
    * raised afterwards is inside the window. Every data-driven raise site
    * does sit between Begin and the End, so exactly one window and one style
    * var are owed -- but the shell cannot see inside render and must not
    * guess which. When render_ok is not set, repair nothing: a style var left
    * pushed is recovered when the frame ends; an unmatched close is not.
    *
    * The style *colour* stack is deliberately not repaired. Its only push and
    * pop in the whole file bracket a single ImGui call with no data-driven
    * raise site between them, so nothing can stop between them. The addon
    * suite asserts all three stacks anyway, so if that ever stops being true
    * the tests say so rather than a guess here quietly papering over it.
    *
    * One residual, stated rather than guarded: the flags arithmetic reads
    * opts.locked, so a nil ImGui constant reached only on the locked path
    * could raise before Begin on a host where an unlocked frame has already
    * drawn clean, and there this would over-close by one window. Nothing
    * data-driven reaches it and no test provokes it.
    *
    * Each repair call is protected on its own, for the same reason as above:
    * neither of them may become the second error of the frame either. The
    * *lookups* go inside the pcall too, and that is not a formality:
    * `pcall(imgui.End)` reads imgui.End before pcall is entered, and imgui
    * here is Ashita's constants table whose __index is
    * AshitaCore:GetGuiManager() (see the require at the top of this file), so
    * the read is a live call into the GUI manager. A raise from the read of
    * an unparenthesised `pcall(imgui.End)` escapes this handler exactly as
    * the failed render would have -- into d3d_present, on the game thread
    * every addon in the process shares. A closure moves the read inside.
    ]]--
    if incursion.render_ok then
        pcall(function () imgui.End(); end);
        pcall(function () imgui.PopStyleVar(1); end);
    end

    incursion.render_off = true;

    -- Protected for the same reason, and the whole statement rather than the
    -- call alone: tostring(err) runs on an error value this code did not
    -- author. The error text is an argument and never part of the format
    -- string -- a percent sign in server text is one of the things that gets
    -- us here.
    pcall(function ()
        printf('Render error, window disabled: %s -- /incursion to try again.',
               tostring(err));
    end);
end);

--[[
* event: command
]]--
ashita.events.register('command', 'incursion_command', function (e)
    local args = e.command:args();
    local cmd = args[1] and args[1]:lower() or '';
    if cmd ~= '/incursion' and cmd ~= '/inc' then
        return;
    end

    e.blocked = true;

    local sub = (args[2] or ''):lower();

    if sub == '' then
        -- A window switched off by a render error is re-enabled here, not
        -- toggled. Toggling against a window that is not being drawn would
        -- read as 'hide it', which is the opposite of what was asked.
        if incursion.render_off then
            incursion.render_off = false;
            -- Deliberately *not* clearing override. Whatever it held is what
            -- put the window on screen on the frame that failed -- nil under
            -- automatic visibility, true under a manual show, and it cannot
            -- have been false because visible() returns before render then --
            -- so it is also what brings the window back. Clearing it drops a
            -- manual show, and for a player running with automatic show/hide
            -- off that is the only thing keeping the window on screen: the
            -- window would go straight back off while this line said the
            -- opposite.
            --
            -- The line reports what is on screen rather than what was asked
            -- for. The player can have turned automatic show/hide off in
            -- between, and there is no wording that can be true of every
            -- state without looking.
            if visible() then
                printf('Window re-enabled.');
            else
                printf('Window re-enabled, but it is hidden: automatic '
                       .. 'show/hide is off. /incursion again to show it.');
            end
            return;
        end

        -- Toggle against what is currently on screen.
        incursion.override = not visible();
        if incursion.override and incursion.state:snapshot() == nil then
            printf('No active Incursion run to show; the window will appear when one starts.');
        end
        return;
    end

    if sub == 'reset' then
        reset(false);
        return;
    end

    if sub == 'lock' then
        incursion.settings.locked = not incursion.settings.locked;
        settings.save();
        printf('Window %s.', incursion.settings.locked and 'locked' or 'unlocked');
        return;
    end

    if sub == 'auto' then
        incursion.settings.auto = not incursion.settings.auto;
        incursion.override = nil;
        settings.save();
        printf('Automatic show/hide %s.', incursion.settings.auto and 'on' or 'off');
        return;
    end

    printf('Usage:');
    printf('  /incursion         Toggle the window');
    printf('  /incursion reset   Clear the current run');
    printf('  /incursion lock    Toggle window drag lock');
    printf('  /incursion auto    Toggle automatic show/hide');
end);

--[[
* Fires when the settings library switches character profiles (login, logout,
* character change). The run and the player name belong to the old character,
* so both must go: keeping the name would silently filter out the new
* character's own points messages.
]]--
settings.register('settings', 'incursion_settings_update', function (s)
    if s ~= nil then
        incursion.settings = s;

        incursion.state:reset();
        incursion.override = nil;
        -- A render failure on the old character is not the new character's
        -- problem, and neither is a line the old character's chat could not
        -- be read from. This callback does its own clearing rather than
        -- calling reset(), so both fields have to be cleared here too.
        incursion.render_off = false;
        incursion.parse_told = false;
        -- nil makes the text_in handler re-fetch the name on the next event,
        -- once the new character actually exists in memory.
        incursion.state:set_player(nil);

        -- The new profile may hold that character's own in-progress run.
        -- Same rule as the load path: an unusable blob is cleared rather than
        -- retried, and the player is told rather than left with a HUD that
        -- came back empty for no stated reason.
        local saved = s.session;
        if type(saved) == 'string' and saved ~= '' and resume(saved) == nil then
            s.session = '';
        end
    end
    settings.save();
end);
