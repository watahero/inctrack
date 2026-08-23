--[[
* IncursionTracker -- state.lua
* Copyright (c) 2026 Godwen. MIT License; see LICENSE in the repository root.
* Written with Claude (Anthropic).
]]--

--[[
* state.lua -- Incursion run state machine.
*
* Pure Lua. Takes parser events, maintains a single run record, and answers
* timer questions. The clock is injected so tests are deterministic and so the
* addon can use whatever monotonic source Ashita provides.
*
*     local state = State.new({ clock = os.clock, player = 'Godwen' })
*     state:apply(event)
*     local run = state:snapshot()
*
* Nothing here knows the name of an instance, a boss, a mob or an objective.
* Everything displayed comes from the messages themselves, so content added to
* the server later needs no change in this file.
]]--

local State = {};
State.__index = State;

-- A restored run older than this is assumed stale and discarded.
local STALE_SECONDS = 3 * 60 * 60;

-- How long the window lingers after 'Complete!' so the result stays readable.
local LINGER_SECONDS = 30;

-- An unrecognised Incursion line is shown for this long, then drops off.
local NOTE_SECONDS = 30;

function State.new(opts)
    opts = opts or {};
    local self = setmetatable({}, State);
    self.clock  = opts.clock or os.clock;
    self.player = opts.player;
    self.run    = nil;
    self.dirty  = false;
    return self;
end

function State:now()
    return self.clock();
end

function State:set_player(name)
    self.player = name;
end

local function new_run(self, instance, difficulty)
    return {
        instance       = instance,
        difficulty     = difficulty,
        phase          = nil,
        kills_cur      = 0,
        kills_max      = nil,
        objective      = nil,
        next_boss      = nil,
        bonus          = nil,
        -- Counters from message shapes we do not specifically know, keyed by
        -- their label. Future content lands here instead of being lost.
        extra          = {},
        note           = nil,
        -- Boons chosen between phases, in pick order. They last the whole
        -- run and the server never re-announces them.
        boons          = {},
        time_left      = nil,   -- seconds remaining at time_sync
        time_sync      = nil,
        started        = self:now(),
        points         = 0,
        phases_cleared = 0,
        finished       = false,
        finish_time    = nil,
        elapsed_final  = nil,
        hide_at        = nil,
    };
end

function State:reset()
    self.run   = nil;
    self.dirty = true;
end

--[[
* Mark the run as out of sync with the server.
*
* Called after a reconnect or a reload. Everything we hold describes the run as
* it was before we dropped; the server replays none of it. Progress shown while
* desynced is a lower bound, not the truth, and the UI says so.
]]--
function State:desync()
    local run = self.run;
    if run and not run.finished then
        run.desynced = true;
    end
end

-- Fresh authoritative information has arrived: we are in step again.
local function resync(run)
    run.desynced = false;
    if run.objective then
        run.objective.stale = nil;
    end
end

--[[
* Apply one parser event. Returns true when the event changed the run, so the
* caller knows whether to persist.
]]--
function State:apply(e)
    if type(e) ~= 'table' or not e.t then
        return false;
    end

    local t = e.t;

    if t == 'begin' then
        self.run = new_run(self, e.instance, e.difficulty);
        -- The entry timer sync is announced just *before* 'Begins!', so it
        -- arrives with no run to attach to. Pick it up here, otherwise the
        -- clock stays blank until the first phase boundary ten minutes in.
        if self.pending_time and (self:now() - self.pending_time.at) <= 30 then
            self.run.time_left = self.pending_time.seconds;
            self.run.time_sync = self.pending_time.at;
        end
        self.pending_time = nil;
        self.dirty = true;
        return true;
    end

    if t == 'recover' then
        -- A recover only re-syncs the timer; it carries no objective or phase.
        -- Keep the existing run when it is the same instance and still fresh,
        -- otherwise start a partial one that fills in on the next message.
        local run = self.run;
        local reusable = run
            and run.instance == e.instance
            and not run.finished
            and (self:now() - run.started) < STALE_SECONDS;
        if not reusable then
            self.run = new_run(self, e.instance, nil);
            self.run.recovered = true;
        end
        -- Whatever we kept describes the run as it was before we dropped. The
        -- party may have finished the phase, killed the boss, or moved on
        -- entirely while we were gone, and none of that is replayed to us.
        self:desync();
        self.dirty = true;
        return true;
    end

    -- Always hold the latest timer sync for the 'begin' above, which follows
    -- it. This must happen even when a run exists: between back-to-back runs
    -- the previous (finished) run still occupies state when the next run's
    -- entry sync arrives, and without the hold the new run's clock would stay
    -- blank until its first phase boundary, ten minutes in.
    if t == 'time' then
        self.pending_time = { seconds = e.minutes * 60, at = self:now() };
        if not self.run then
            return false;
        end
    end

    -- Everything below needs a run. Any instance-tagged message can arrive
    -- without one (addon loaded mid-run), so bootstrap from it.
    if not self.run and e.instance then
        self.run = new_run(self, e.instance, nil);
        self.run.recovered = true;
    end

    local run = self.run;
    if not run then
        return false;
    end

    -- A finished run stays around only for as long as the window lingers.
    -- After that it must stop absorbing events rather than mixing later
    -- activity into a result that is already settled.
    if run.finished and run.hide_at and self:now() > run.hide_at then
        return false;
    end

    -- An instance-tagged message naming a different instance means our run is
    -- stale. This is deliberately generic: it guards new message shapes too.
    if e.instance and run.instance ~= e.instance then
        self.run = new_run(self, e.instance, nil);
        self.run.recovered = true;
        run = self.run;
    end

    if t == 'phase' then
        -- Reaching phase N means N-1 phases were cleared, whether or not we
        -- were connected to watch them. This is the only way to notice boss
        -- kills that happened while we were gone.
        if e.phase and e.phase - 1 > run.phases_cleared then
            run.phases_cleared = e.phase - 1;
            -- Those bosses awarded points we never saw, so the total we hold
            -- is now a lower bound.
            run.points_partial = true;
        end

        -- Coming back on a different phase than we left on: the objective's
        -- mob list may belong to the old phase, and the boss preview certainly
        -- does. Keep the mobs but flag them, drop the boss outright.
        if run.desynced and run.phase and e.phase ~= run.phase then
            if run.objective then
                run.objective.stale = true;
            end
            run.next_boss = nil;
        end

        run.phase     = e.phase;
        run.kills_cur = e.cur;
        run.kills_max = e.max;
        if run.objective and run.objective.kind == 'kills' then
            run.objective.count = e.max;
        end

        -- A kill count is live information, so we are in step on progress even
        -- if the mob list is still only probable.
        run.desynced = false;
        self.dirty = true;
        return true;
    end

    if t == 'objective_kills' then
        run.objective = { kind = 'kills', count = e.count, mobs = e.mobs };
        run.kills_cur = 0;
        run.kills_max = e.count;
        run.note = nil;
        resync(run);
        self.dirty = true;
        return true;
    end

    if t == 'objective_boss' then
        run.objective = { kind = 'boss', name = e.name, loc = e.loc };
        -- Kills are done by definition once the boss objective appears.
        if run.kills_max then
            run.kills_cur = run.kills_max;
        end
        run.note = nil;
        resync(run);
        self.dirty = true;
        return true;
    end

    -- An objective wording we do not recognise. Shown verbatim.
    if t == 'objective_text' then
        run.objective = { kind = 'text', text = e.text };
        run.kills_cur = 0;
        run.kills_max = nil;
        run.note = nil;
        resync(run);
        self.dirty = true;
        return true;
    end

    if t == 'boss_hint' then
        run.next_boss = { name = e.name, loc = e.loc };
        resync(run);
        self.dirty = true;
        return true;
    end

    if t == 'bonus_new' then
        run.bonus = {
            kind       = e.kind,
            label      = e.label,
            loc        = e.loc,
            cur        = 0,
            max        = e.max,
            expires_at = e.minutes and (self:now() + e.minutes * 60) or nil,
            done       = false,
        };
        self.dirty = true;
        return true;
    end

    if t == 'bonus_progress' then
        -- Progress can arrive for a bonus we never saw announced (addon loaded
        -- mid-phase), so synthesise one rather than dropping the update.
        if not run.bonus or run.bonus.done then
            run.bonus = { kind = 'kills', label = e.name, cur = 0, done = false };
        end
        run.bonus.label = e.name;
        run.bonus.cur   = e.cur;
        run.bonus.max   = e.max;

        -- A progress message proves the bonus is still live. Our expiry runs
        -- from when we received the announcement, so it can lag the server's
        -- by a little; if ours has already lapsed, drop the countdown rather
        -- than hide an objective the server says is still counting.
        if run.bonus.expires_at and self:now() >= run.bonus.expires_at then
            run.bonus.expires_at = nil;
        end

        self.dirty = true;
        return true;
    end

    if t == 'bonus_done' then
        if not run.bonus then
            run.bonus = { kind = 'kills', label = 'Bonus objective', cur = 0 };
        end
        run.bonus.done = true;
        if run.bonus.max then
            run.bonus.cur = run.bonus.max;
        end
        run.bonus.expires_at = nil;
        self.dirty = true;
        return true;
    end

    -- A counter in a shape we do not specifically know. Tracked by its own
    -- label so several can coexist.
    if t == 'generic_counter' then
        run.extra[e.label] = {
            label = e.label, cur = e.cur, max = e.max,
            done = e.cur >= e.max, at = self:now(),
        };
        self.dirty = true;
        return true;
    end

    if t == 'generic_done' then
        local entry = run.extra[e.label];
        if entry then
            entry.done = true;
            if entry.max then
                entry.cur = entry.max;
            end
        else
            run.extra[e.label] = {
                label = e.label, done = true, at = self:now(),
            };
        end
        self.dirty = true;
        return true;
    end

    if t == 'generic_note' then
        run.note = { text = e.text, at = self:now() };
        self.dirty = true;
        return true;
    end

    if t == 'time' then
        run.time_left = e.minutes * 60;
        run.time_sync = self:now();
        self.dirty = true;
        return true;
    end

    if t == 'points' then
        -- Only our own gains. When the player name is unknown we accept any,
        -- since the server only ever addresses these to us.
        if self.player and e.who ~= self.player then
            return false;
        end
        run.points         = run.points + e.amount;
        run.phases_cleared = run.phases_cleared + 1;

        -- A points award means a boss just died, so whatever phase progress we
        -- were showing is finished. While desynced that display is stale and
        -- would otherwise sit there until the next kill.
        if run.desynced then
            run.objective  = nil;
            run.next_boss  = nil;
            run.kills_cur  = 0;
            run.kills_max  = nil;
        end

        self.dirty = true;
        return true;
    end

    if t == 'boon' then
        -- Ours only, same rule as points.
        if self.player and e.who ~= self.player then
            return false;
        end
        -- Dedupe by name: a repeat pick (or a replayed line) updates the
        -- stats in place rather than listing the boon twice.
        for i = 1, #run.boons do
            if run.boons[i].name == e.name then
                run.boons[i].stats = e.stats;
                self.dirty = true;
                return true;
            end
        end
        run.boons[#run.boons + 1] = { name = e.name, stats = e.stats };
        self.dirty = true;
        return true;
    end

    if t == 'complete' then
        run.finished      = true;
        run.finish_time   = string.format('%dm %ds', e.minutes, e.seconds);
        run.elapsed_final = e.minutes * 60 + e.seconds;
        run.bonus         = nil;
        run.objective     = nil;
        run.note          = nil;
        run.extra         = {};
        run.hide_at       = self:now() + LINGER_SECONDS;
        self.dirty = true;
        return true;
    end

    return false;
end

-- Seconds of instance time left, or nil. Approximate: the server reports whole
-- minutes, so this counts down from the last sync and snaps when a new one lands.
function State:time_left()
    local run = self.run;
    if not run or not run.time_left or not run.time_sync then
        return nil;
    end
    local left = run.time_left - (self:now() - run.time_sync);
    if left < 0 then
        return 0;
    end
    return left;
end

-- Seconds since the run started, frozen once the run completes.
function State:elapsed()
    local run = self.run;
    if not run then
        return nil;
    end
    if run.elapsed_final then
        return run.elapsed_final;
    end
    return self:now() - run.started;
end

--[[
* The bonus objective worth displaying, or nil.
*
* A bonus whose timer ran out without completing is dropped rather than left on
* screen at 0:00 -- which is what a bonus that lapsed during a disconnect looks
* like, since the server does not announce the expiry.
]]--
function State:bonus()
    local run = self.run;
    if not run or not run.bonus or run.finished then
        return nil;
    end
    local bonus = run.bonus;
    if not bonus.done and bonus.expires_at and self:now() >= bonus.expires_at then
        return nil;
    end
    return bonus;
end

-- Seconds until the active bonus objective expires, or nil.
function State:bonus_remaining()
    local run = self.run;
    if not run or not run.bonus or not run.bonus.expires_at then
        return nil;
    end
    local left = run.bonus.expires_at - self:now();
    if left <= 0 then
        return 0;
    end
    return left;
end

-- Unrecognised status line, while it is still fresh.
function State:note()
    local run = self.run;
    if not run or not run.note then
        return nil;
    end
    if (self:now() - run.note.at) > NOTE_SECONDS then
        return nil;
    end
    return run.note.text;
end

-- Shared empty result for the common no-extras case; callers only read it,
-- and it saves a table allocation on every rendered frame.
local NO_EXTRAS = {};

-- Generic counters, most recently updated first.
function State:extra_sorted()
    local run = self.run;
    if not run or next(run.extra) == nil then
        return NO_EXTRAS;
    end

    local list = {};
    for _, entry in pairs(run.extra) do
        list[#list + 1] = entry;
    end

    table.sort(list, function(a, b)
        if a.at ~= b.at then return a.at > b.at; end
        return a.label < b.label;
    end);

    return list;
end

-- True while the window should be on screen under automatic visibility.
function State:should_show()
    local run = self.run;
    if not run then
        return false;
    end
    if run.finished then
        return run.hide_at ~= nil and self:now() < run.hide_at;
    end
    return true;
end

function State:snapshot()
    return self.run;
end

--[[
* Serialisation. Kept here rather than in the addon shell so the round trip can
* be tested without Ashita. Returns a plain table any encoder can take.
]]--
function State:serialise()
    local run = self.run;
    if not run then
        return nil;
    end

    -- Timers are stored as remaining durations rather than absolute clock
    -- values, because the clock resets when the addon reloads.
    local out = {
        version        = 1,
        instance       = run.instance,
        difficulty     = run.difficulty,
        phase          = run.phase,
        kills_cur      = run.kills_cur,
        kills_max      = run.kills_max,
        objective      = run.objective,
        next_boss      = run.next_boss,
        points         = run.points,
        phases_cleared = run.phases_cleared,
        finished       = run.finished,
        finish_time    = run.finish_time,
        points_partial = run.points_partial,
        elapsed        = self:elapsed(),
        time_left      = self:time_left(),
        saved_at       = os.time(),
        extra          = {},
        boons          = {},
    };

    for i = 1, #run.boons do
        out.boons[i] = { name = run.boons[i].name, stats = run.boons[i].stats };
    end

    if run.bonus then
        out.bonus = {
            kind      = run.bonus.kind,
            label     = run.bonus.label,
            loc       = run.bonus.loc,
            cur       = run.bonus.cur,
            max       = run.bonus.max,
            done      = run.bonus.done,
            remaining = self:bonus_remaining(),
        };
    end

    for labelText, entry in pairs(run.extra) do
        out.extra[labelText] = {
            label = entry.label, cur = entry.cur,
            max = entry.max, done = entry.done,
        };
    end

    return out;
end

function State:restore(data)
    if type(data) ~= 'table' or data.version ~= 1 or not data.instance then
        return false;
    end

    -- A finished run has nothing left to track. Resuming one would pop a stale
    -- 'Complete!' window on the next login for a run already over.
    if data.finished then
        return false;
    end

    -- Wall-clock age, not the injected clock: this survives an addon reload.
    if data.saved_at and (os.time() - data.saved_at) > STALE_SECONDS then
        return false;
    end

    local now = self:now();
    local run = new_run(self, data.instance, data.difficulty);

    run.phase          = data.phase;
    run.kills_cur      = data.kills_cur or 0;
    run.kills_max      = data.kills_max;
    run.objective      = data.objective;
    run.next_boss      = data.next_boss;
    run.points         = data.points or 0;
    run.phases_cleared = data.phases_cleared or 0;
    run.points_partial = data.points_partial or false;
    run.started        = now - (data.elapsed or 0);
    run.recovered      = true;

    -- We were not listening between the save and now, so treat everything
    -- restored as a lower bound until the server tells us otherwise.
    run.desynced       = true;

    if data.time_left then
        run.time_left = data.time_left;
        run.time_sync = now;
    end

    if data.bonus then
        run.bonus = {
            kind  = data.bonus.kind,
            label = data.bonus.label,
            loc   = data.bonus.loc,
            cur   = data.bonus.cur or 0,
            max   = data.bonus.max,
            done  = data.bonus.done or false,
            expires_at = data.bonus.remaining and (now + data.bonus.remaining) or nil,
        };
    end

    if type(data.boons) == 'table' then
        for i = 1, #data.boons do
            local b = data.boons[i];
            if type(b) == 'table' and b.name then
                run.boons[#run.boons + 1] = { name = b.name, stats = b.stats };
            end
        end
    end

    if type(data.extra) == 'table' then
        for labelText, entry in pairs(data.extra) do
            run.extra[labelText] = {
                label = entry.label or labelText, cur = entry.cur,
                max = entry.max, done = entry.done or false, at = now,
            };
        end
    end

    self.run = run;
    return true;
end

return State;
