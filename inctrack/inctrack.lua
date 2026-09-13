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
addon.version = '1.2.2';
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
    -- Set when the run has changed and is owed a disk write; cleared by the
    -- frame handler, which performs it. The chat thread decides *whether* a
    -- write is owed -- that arithmetic is unchanged -- and the frame handler
    -- does the writing, because persist() serialises the run, encodes it as
    -- JSON and calls settings.save(), and text_in runs on the game thread on
    -- every chat line the client receives. Ashita exposes no asynchronous
    -- write, so the flush rides the frame handler beside this one: it
    -- already exists and already runs every frame, which makes this a moved
    -- call rather than a new mechanism.
    save_due = false,
    -- The earliest clock reading at which an owed write may be attempted.
    -- Zero except after a failed one: see the frame handler. It is only ever
    -- read when save_due is set, so the frames that owe nothing -- which is
    -- almost all of them -- do not pay for it.
    save_retry_at = 0,
    -- Set the first time a write raised out of persist(). Ashita's
    -- settings.save() is a synchronous disk write and can fail for reasons
    -- that have nothing to do with this addon -- a read-only settings file, a
    -- full disk, a file another process has open -- and such a fault is
    -- persistent, so an unrated complaint is the same sentence once per owed
    -- write for the rest of the session. Same rule, and deliberately the same
    -- shape, as render_off and parse_told: one way of saying a thing once.
    save_told = false,
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

-- How long an owed write that raised waits before the frame handler tries it
-- again. The same five seconds the chat thread throttles ordinary writes
-- with, deliberately: a retry that is bounded by a number already in the file
-- is one fewer number to reason about.
local SAVE_RETRY_SECONDS = 5.0;

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
* React to a settings write that raised: keep what is owed, bound the retry,
* and say so once.
*
* Three callers want exactly these three things -- the frame handler's flush,
* reset()'s clear, and the load handler's discard of an unusable blob -- and
* the shell already carries a comment saying that the profile-switch callback
* duplicating reset()'s latch clearing is a thing to be remembered rather
* than a thing that is shared. One copy of this, then, rather than three.
*
* Re-arming rather than dropping is the whole of it. A write that is owed and
* never made is a run that is not on disk, and on the reset path it is worse
* than that: the clear is owed to a write that no later frame would make, so
* the run the player threw away is the one that comes back.
*
* Bounded, because a persistent fault -- a read-only settings file, a full
* disk, a file another process holds -- would otherwise serialise, encode and
* fail sixty times a second on the game thread, which is the cost deferring
* the write exists to avoid.
*
* The report is protected as a whole statement, and the error text is an
* argument and never part of the format string: tostring(err) runs on a value
* this code did not author, and a percent sign in a path or a host message is
* one of the things that gets us here.
]]--
local function save_failed(err)
    incursion.save_due = true;
    incursion.save_retry_at = now() + SAVE_RETRY_SECONDS;

    if not incursion.save_told then
        incursion.save_told = true;
        pcall(function ()
            printf('Could not write the run down: %s -- it will be '
                   .. 'retried, and further failures this session '
                   .. 'will not be reported; /incursion reset to '
                   .. 'hear them again.', tostring(err));
        end);
    end
end

--[[
* Persist the current run so a reload, crash, or zone-out mid-Incursion does
* not lose it. The server never re-announces the objective on recovery, so
* without this the window would come back blank for the rest of the phase.
*
* Three outcomes, and each of them is a different thing to write down:
*
*   * There is no run. The empty string is the right answer and the only
*     thing that may produce it -- an empty session means 'nothing to
*     resume', so a cleared or finished run has to say so or it comes back
*     from the dead on the next load.
*   * There is a run and it encoded. Write it.
*   * There is a run and the encode raised. Write *nothing*, and let the
*     raise out to the caller.
*
* That last one used to be folded into the first by a single ternary, and it
* is the one case where they are opposites: an unencodable run is not an
* absent one, and storing '' for it wrote an empty session over a perfectly
* good previously-saved run and said nothing. Silent and destructive on the
* one path whose whole purpose is not losing the run -- while the disk fault
* two lines further on latches, retries and reports.
*
* So the failure is raised rather than swallowed, because every caller
* already contains the disk write's raise and treats it the same way: the
* frame handler re-arms what it owes behind the retry window and says so
* once, and reset() and the load handler do likewise. From the player's side
* the two faults are the same event -- the run could not be written down --
* and there is nothing useful they could do differently about either.
]]--
local function persist()
    local blob = incursion.state:serialise();
    if blob == nil then
        incursion.settings.session = '';
        settings.save();
        return;
    end

    local ok, encoded = pcall(json.encode, blob);
    if not ok then
        -- Re-raised at level 0 and with the encoder's own error value, so
        -- what reaches the player is what the host said rather than a line
        -- number in this file.
        error(encoded, 0);
    end

    incursion.settings.session = encoded;
    settings.save();
end

local function reset(quiet)
    incursion.state:reset();
    incursion.override = nil;
    -- Clearing the run is also a way back from a window that switched itself
    -- off, from a chat handler that has stopped complaining, and from a disk
    -- that has stopped being complained about, so /incursion reset recovers
    -- all three as well as the run.
    incursion.render_off = false;
    incursion.parse_told = false;
    incursion.save_told = false;
    -- The session string is emptied two lines below, so a write still owed
    -- from before the clear would put the run straight back over it on the
    -- next frame.
    incursion.save_due = false;
    -- And a retry window armed by a write that failed belongs to that write.
    -- Left standing it would hold the *next* run's first write back by up to
    -- five seconds for no reason the player could see.
    incursion.save_retry_at = 0;
    -- The boon shorthand memoised for the run belongs to a run that is gone.
    -- The window cannot notice this for itself: after a reset there is no run
    -- and it stops being drawn at all.
    ui.forget();
    incursion.settings.session = '';
    -- Protected, and re-armed on failure, because of the two lines above:
    -- save_due was just cleared so that a write owed from *before* the clear
    -- could not put the run straight back, which leaves this write the only
    -- one that will ever carry the clear. A raise here used to leave the
    -- command handler for Ashita's dispatch and leave 'session = ""' owed to
    -- a write no frame would make -- so the previous run stayed on disk and
    -- was resumed on the next load, handing the player back the run they had
    -- just thrown away. Catching the raise alone does not fix that; re-arming
    -- is what makes the ordering safe in both directions.
    local ok, err = pcall(settings.save);
    if not ok then
        save_failed(err);
    end
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
            -- Protected and re-armed, same as reset()'s clear and for the
            -- same reason: this write is the only thing that stops an
            -- unusable string being met again on every load, and a raise
            -- here escapes into Ashita's event dispatch while the addon is
            -- still loading. Frames follow a load, so there is somewhere for
            -- the retry to happen.
            local ok, err = pcall(settings.save);
            if not ok then
                save_failed(err);
            end
        end
    end
end);

--[[
* event: unload
]]--
ashita.events.register('unload', 'incursion_unload', function ()
    -- Unconditional, and deliberately so: it does not consult save_due. This
    -- is the one path that cannot wait for a frame -- there will not be
    -- another one -- and its unconditional write is what makes deferring
    -- every other write safe at all. Nothing is owed afterwards.
    incursion.save_due = false;

    --[[
    * And contained, because a raise here reaches Ashita's event dispatch in
    * the middle of an addon unload or a client shutdown.
    *
    * This is the one failure in the file with no better answer available,
    * and the ceiling is worth stating rather than dressing up: there is
    * nowhere to retry to. save_failed() re-arms a write for a later frame
    * and says so; after this there is no later frame, so using it here would
    * promise the player a retry that cannot happen. What is actually owed is
    * the two things that are left -- the raise does not escape into the
    * host, and the loss is said out loud instead of swallowed.
    *
    * Said unconditionally, past save_told, for the same reason: everything
    * that latch suppresses is a fault that will be tried again. This one is
    * the last write of the session, so it is a different sentence and it can
    * only ever be said once anyway -- unload fires once.
    *
    * The report is protected as a whole statement and the error text is an
    * argument, never part of the format string. Same rule as everywhere
    * else, and unloading is a poor moment to discover an exception to it.
    ]]--
    local ok, err = pcall(persist);
    if not ok then
        pcall(function ()
            printf('Could not write the run down on the way out: %s -- '
                   .. 'anything since the last write is lost.', tostring(err));
        end);
    end
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
            --
            -- The decision is made here and the write is not: this is
            -- arithmetic on a number, and the disk write it used to make
            -- inline is now owed to the frame handler. The policy the player
            -- experiences is unchanged.
            local t = now();
            if MUST_SAVE[event.t] or (t - incursion.save_at) > 5.0 then
                incursion.save_at = t;
                incursion.save_due = true;
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
* Hoisted render arguments. ui.render reads two fields off this table and
* keeps no handle on it -- passed, read, dropped -- so building a fresh one
* sixty times a second is pure GC churn. Same reason, and the same shape, as
* ui.lua's own hoisted ARG_* tables.
*
* locked is rewritten each frame; visible is fixed true because the frame
* handler has already returned above when the window is not on screen.
]]--
local FRAME_OPTS = {
    visible = true,
    locked  = false,
};

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
    --[[
    * The deferred write, and it sits here on purpose: above both of the
    * early returns below.
    *
    * The handler returns when the window latched itself off after a render
    * error, and again when the window is simply not on screen. A player
    * running with automatic show/hide off is still playing the run, and so
    * is one whose window latched off -- so a flush placed under either
    * return means their Incursion is never written down at all, and a
    * mid-run reload comes back blank. Nothing about drawing the window has
    * anything to do with owing the disk a write.
    *
    * The flag is consumed *before* the write, not after, so a raise inside
    * persist() cannot leave it set and retry sixty times a second. Same rule
    * the render latch follows.
    *
    * And the write is contained, for the same reason the render below is:
    * this is the frame handler, and a raise here reaches the game thread
    * every addon in the process shares. persist() serialises the run and
    * encodes it -- that encode has always been protected -- and then calls
    * settings.save(), which is Ashita's synchronous disk write and can fail
    * for reasons that have nothing to do with this addon. Until the write
    * moved here it ran inside text_in's pcall, where a fault cost one line;
    * placed above the render pcall with nothing around it, it cost the
    * frame, every other addon's ImGui stacks, and the write itself.
    *
    * A failure re-arms the flag rather than dropping what it was owed, and
    * arms it behind the same five-second window the chat thread throttles
    * with. Consumed-then-restored rather than left set: a persistent fault
    * that retried on every frame would serialise, encode and fail sixty
    * times a second on the game thread, which is the cost this deferral
    * exists to avoid. Bounded retry is the middle: a transient fault costs
    * five seconds, a persistent one costs one attempt per window and says so
    * once.
    *
    * The residual, stated rather than hidden: the run is not on disk between
    * the chat line and the next frame that actually runs. That is normally
    * about one frame, but the bound is 'the next d3d_present', not '16 ms'
    * -- the addon does not drive Present, so a minimised, alt-tabbed or
    * background-throttled client stretches it as far as the client likes,
    * and a client killed there loses everything since the last frame that
    * ran rather than one event. The unload handler writes unconditionally,
    * so every orderly departure is covered; the profile-switch callback
    * discards what is owed on purpose, because it belongs to the character
    * that just left. The other way to lose a write needs no crash at all: a
    * raise inside persist(), which is why the raise below is caught,
    * retried, and reported rather than left silent.
    ]]--
    if incursion.save_due and now() >= incursion.save_retry_at then
        incursion.save_due = false;

        local ok, err = pcall(persist);
        if not ok then
            -- Keep what is owed, bound the retry, say so once: see
            -- save_failed above, which reset() and the load handler share.
            save_failed(err);
        end
    end

    -- Already failed once this session. Return before asking anything else,
    -- so the failure costs one branch a frame instead of repeating.
    if incursion.render_off then
        return;
    end

    if not visible() then
        return;
    end

    -- One field a frame, into the table hoisted above. visible is fixed
    -- because the handler has already returned when the window is not on
    -- screen -- a later reader would otherwise wonder why it is not read
    -- from visible().
    FRAME_OPTS.locked = incursion.settings.locked;

    local ok, err = pcall(ui.render, incursion.state, FRAME_OPTS);

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
    * One residual, stated rather than guarded, and it costs two repairs
    * rather than one: the flags arithmetic reads opts.locked, so a nil ImGui
    * constant reached only on the locked path could raise before Begin on a
    * host where an unlocked frame has already drawn clean. That arithmetic
    * runs before the PushStyleVar as well as before the Begin, so neither has
    * happened and both repairs below are owed nothing -- the End is an
    * unmatched close and the PopStyleVar an over-pop. The two are not equally
    * bad. Each repair call is individually pcall-wrapped, so an over-pop that
    * raises in Lua is caught here and goes no further; an unmatched ImGui
    * close is a C++ assert inside the host and no pcall reaches it. Nothing
    * data-driven reaches this path and no test provokes it.
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
        -- problem, neither is a line the old character's chat could not be
        -- read from, and neither is a disk fault already reported. This
        -- callback does its own clearing rather than calling reset(), so all
        -- three fields have to be cleared here too.
        incursion.render_off = false;
        incursion.parse_told = false;
        incursion.save_told = false;
        -- And a write owed by the old character must not land in the new
        -- character's settings, which is where the next frame would put it --
        -- nor may a retry window armed by the old character's failed write
        -- hold the new character's first write back.
        incursion.save_due = false;
        incursion.save_retry_at = 0;
        -- And the boon shorthand memoised for the old character's run, for
        -- the same reason as the reset path: it belongs to nobody now.
        ui.forget();
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
