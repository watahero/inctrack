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
    incursion.settings.session = '';
    settings.save();
    if not quiet then
        printf('Run cleared.');
    end
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
    -- or stale blob is discarded rather than half-applied.
    local saved = incursion.settings.session;
    if type(saved) == 'string' and saved ~= '' then
        local ok, blob = pcall(json.decode, saved);
        if ok and type(blob) == 'table' and incursion.state:restore(blob) then
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

    if not ok then
        printf('parse error: %s', tostring(err));
    end
end);

--[[
* event: d3d_present
]]--
ashita.events.register('d3d_present', 'incursion_present', function ()
    if not visible() then
        return;
    end

    ui.render(incursion.state, {
        visible = true,
        locked  = incursion.settings.locked,
    });
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
        -- nil makes the text_in handler re-fetch the name on the next event,
        -- once the new character actually exists in memory.
        incursion.state:set_player(nil);

        -- The new profile may hold that character's own in-progress run.
        local saved = s.session;
        if type(saved) == 'string' and saved ~= '' then
            local ok, blob = pcall(json.decode, saved);
            if not (ok and type(blob) == 'table' and incursion.state:restore(blob)) then
                s.session = '';
            end
        end
    end
    settings.save();
end);
