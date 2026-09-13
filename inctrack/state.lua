--[[
* inctrack -- state.lua
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

--[[
* A Skirmish this long without a Skirmish line is over. The mode has no
* completion message -- it ends at the reward chest, which pays out through
* ordinary 'You obtain ...!' lines, or in a wipe that says nothing -- and the
* Skirmish Point fight after the last phase line was observed to run about
* four silent minutes, so ten covers a long one. The next run beginning
* replaces the window outright either way.
]]--
local SKIRMISH_IDLE_SECONDS = 10 * 60;

--[[
* Events that open a run when none exists, though they name no instance. Each
* is a line the server only ever sends inside an Incursion; the run they open
* is unnamed until the first instance-tagged line supplies the name.
]]--
local BOOTSTRAP_KINDS = {
    objective_kills = true,
    objective_boss  = true,
    objective_text  = true,
    boss_hint       = true,
    bonus_new       = true,
    -- The Skirmish setup lines, for a load that lands mid-listing; the
    -- instance-tagged Skirmish lines bootstrap the way every tagged line
    -- does. skirmish_begin has its own arm, like 'begin'.
    skirmish_target  = true,
    skirmish_quarter = true,
};

function State.new(opts)
    opts = opts or {};
    local self = setmetatable({}, State);
    self.clock  = opts.clock or os.clock;
    self.player = opts.player;
    self.run    = nil;
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
        -- Our own points awards actually witnessed. Never displayed: it is
        -- the yardstick for judging whether phases went by unseen.
        awards_seen    = 0,
        phases_cleared = 0,
        finished       = false,
        finish_time    = nil,
        elapsed_final  = nil,
        hide_at        = nil,
    };
end

function State:reset()
    self.run   = nil;
    -- A reset is the player declaring the run over, and a sync captured
    -- before that moment describes an instance they are no longer in. The
    -- hold below exists to bridge the few seconds between the server's
    -- remaining-minutes line and the 'Begins!' that follows it -- not to
    -- survive the player throwing the run away in between, which would seed
    -- the next run's clock with the old one's number.
    self.pending_time = nil;
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

-- Every Skirmish line marks the run as the Skirmish mode and restarts its
-- quiet-time clock; the idle rule in should_show reads both.
local function skirmish_touch(self, run)
    run.skirmish = true;
    run.difficulty = run.difficulty or 'Skirmish';
    run.last_skirmish_at = self:now();
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
        return true;
    end

    -- Allied Skirmish has begun! -- a mode start, so it replaces whatever
    -- run came before it, exactly as Begins! does. The line names no
    -- instance (the progress lines do), and the mode has no instance clock,
    -- so a held Incursion sync from moments before belongs to nothing now.
    if t == 'skirmish_begin' then
        self.run = new_run(self, nil, 'Skirmish');
        self.run.objective = { kind = 'text', text = 'Allied Skirmish' };
        skirmish_touch(self, self.run);
        self.pending_time = nil;
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
    -- without one (addon loaded mid-run), so bootstrap from it -- and so can
    -- the objective, boss and bonus announcements, which the server only
    -- ever sends inside an Incursion but which name no instance. Those open
    -- an *unnamed* run: dropping one costs the window its mob list for the
    -- whole phase (seen in the field, 2026-09-13), while holding it costs
    -- nothing but waiting for the next instance-tagged line to supply the
    -- name. A points award or a timer sync is deliberately not enough: both
    -- say an Incursion exists, neither says anything worth showing.
    if not self.run and (e.instance or BOOTSTRAP_KINDS[t]) then
        self.run = new_run(self, e.instance, nil);
        self.run.recovered = true;
        -- The same moment Begins! handles: a timer sync held seconds ago
        -- belongs to the run we just discovered we are inside.
        if self.pending_time and (self:now() - self.pending_time.at) <= 30 then
            self.run.time_left = self.pending_time.seconds;
            self.run.time_sync = self.pending_time.at;
            self.pending_time = nil;
        end
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

    -- A run opened by an unnamed announcement takes its name from the first
    -- instance-tagged line to arrive. Adoption, not the reset below: a reset
    -- here would throw away the very objective the bootstrap above was for.
    if e.instance and run.instance == nil then
        run.instance = e.instance;
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
        end

        -- More phases behind us than awards we watched land: the bosses that
        -- cleared the difference paid out to a window that was not listening,
        -- so the points total we hold is a lower bound. Measured against the
        -- awards witnessed rather than against the count above, which now
        -- moves on every ordinary phase transition.
        if e.phase and e.phase - 1 > run.awards_seen then
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
        return true;
    end

    if t == 'objective_kills' then
        run.objective = { kind = 'kills', count = e.count, mobs = e.mobs };
        run.kills_cur = 0;
        run.kills_max = e.count;
        run.note = nil;
        resync(run);
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
        return true;
    end

    -- An objective wording we do not recognise. Shown verbatim.
    if t == 'objective_text' then
        run.objective = { kind = 'text', text = e.text };
        run.kills_cur = 0;
        run.kills_max = nil;
        run.note = nil;
        resync(run);
        return true;
    end

    if t == 'boss_hint' then
        run.next_boss = { name = e.name, loc = e.loc };
        resync(run);
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
        return true;
    end

    -- A counter in a shape we do not specifically know. Tracked by its own
    -- label so several can coexist.
    if t == 'generic_counter' then
        run.extra[e.label] = {
            label = e.label, cur = e.cur, max = e.max,
            done = e.cur >= e.max, at = self:now(),
        };
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
        return true;
    end

    if t == 'generic_note' then
        run.note = { text = e.text, at = self:now() };
        return true;
    end

    if t == 'time' then
        run.time_left = e.minutes * 60;
        run.time_sync = self:now();
        return true;
    end

    if t == 'points' then
        -- Only our own gains. When the player name is unknown we accept any,
        -- since the server only ever addresses these to us.
        if self.player and e.who ~= self.player then
            return false;
        end
        run.points         = run.points + e.amount;
        run.awards_seen    = run.awards_seen + 1;

        -- A points award means a boss just died, so whatever phase progress we
        -- were showing is finished. While desynced that display is stale and
        -- would otherwise sit there until the next kill.
        if run.desynced then
            run.objective  = nil;
            run.next_boss  = nil;
            run.kills_cur  = 0;
            run.kills_max  = nil;
        end

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
                return true;
            end
        end
        run.boons[#run.boons + 1] = { name = e.name, stats = e.stats };
        return true;
    end

    -- The Skirmish mode's own lines. The mode borrows the machinery the
    -- window already has: the destination is the objective text, and the
    -- four quarters are labelled counters -- the same 'extra' shelf the
    -- generic tier fills -- keyed by the mob list, which is the only name a
    -- progress line ever gives its quarter. There is no completion message
    -- to handle: the mode ends in a loot burst, and the run is replaced by
    -- whatever begins next.
    if t == 'skirmish_target' then
        skirmish_touch(self, run);
        run.objective = {
            kind = 'text',
            text = 'Clear every quarter, then the Skirmish Point at ' .. e.loc,
        };
        run.note = nil;
        resync(run);
        return true;
    end

    if t == 'skirmish_quarter' then
        skirmish_touch(self, run);
        run.skirmish_groups = run.skirmish_groups or {};
        run.skirmish_groups[table.concat(e.mobs, ','):lower()] = e.label;
        local entry = run.extra[e.label];
        if not entry then
            entry = { label = e.label, cur = 0, at = self:now() };
            run.extra[e.label] = entry;
        end
        entry.max  = e.max;
        entry.done = (entry.cur or 0) >= e.max;
        return true;
    end

    if t == 'skirmish_progress' then
        skirmish_touch(self, run);
        local label = run.skirmish_groups
            and run.skirmish_groups[table.concat(e.mobs, ','):lower()]
            or e.mobs[1] or 'Skirmish';
        -- 'at' is kept from the first sighting: four quarters advance in
        -- parallel, and counters that reshuffle on every kill cannot be
        -- read at a glance.
        local prev = run.extra[label];
        run.extra[label] = {
            label = label, cur = e.cur, max = e.max,
            done = e.cur >= e.max,
            at = prev and prev.at or self:now(),
        };
        return true;
    end

    if t == 'skirmish_group_done' then
        skirmish_touch(self, run);
        run.note = { text = 'Group #' .. e.group .. ' completed!', at = self:now() };
        return true;
    end

    if t == 'skirmish_phase_done' then
        skirmish_touch(self, run);
        run.objective = { kind = 'text', text = 'Phase completed! ' .. e.text };
        run.note = nil;
        return true;
    end

    if t == 'complete' then
        -- The final phase's boss kill is never followed by a phase line -- the
        -- run simply ends -- so the completion is what closes the phase we are
        -- on: reaching 'Phase #N' and then finishing means N cleared.
        --
        -- Assigned rather than incremented, and only ever upwards. An
        -- increment invents a number when there is nothing to add to: a run
        -- joined at the final phase, where the completion itself bootstraps
        -- the run, has no phase behind it that we ever saw, and claiming one
        -- cleared phase for a five-phase run is a confident wrong answer with
        -- no uncertainty marking left to carry it -- the desync banner is
        -- suppressed once the run is finished. Assigning also makes a
        -- repeated 'Complete!' inside the linger window idempotent without a
        -- guard, and stops a restored count being compounded.
        --
        -- A run we watched begin has cleared at least its first phase even if
        -- no phase line reached us; a run we were dropped into has no floor at
        -- all, so it gets none.
        local closing = run.phase or (run.recovered and 0 or 1);
        if closing > run.phases_cleared then
            run.phases_cleared = closing;
        end
        run.finished      = true;
        run.finish_time   = string.format('%dm %ds', e.minutes, e.seconds);
        run.elapsed_final = e.minutes * 60 + e.seconds;
        run.bonus         = nil;
        run.objective     = nil;
        run.note          = nil;
        run.extra         = {};
        run.hide_at       = self:now() + LINGER_SECONDS;
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
    -- The Skirmish's quiet-time rule: the mode has no completion message,
    -- so ten minutes without a Skirmish line is taken as the end. A late
    -- line restarts the clock and the window comes back on its own.
    if run.skirmish and run.last_skirmish_at
        and (self:now() - run.last_skirmish_at) > SKIRMISH_IDLE_SECONDS then
        return false;
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

    -- A run still waiting for its name is display-only. Its blob could not
    -- pass restore's gates, so persisting one would greet the next load with
    -- 'Saved run could not be resumed' for a run that was never worth
    -- resuming; the name arrives seconds later and persistence starts then.
    if not run.instance then
        return nil;
    end

    -- Timers are stored as remaining durations rather than absolute clock
    -- values, because the clock resets when the addon reloads.
    local out = {
        -- Version 2: FIX-01 split the single 'phases_cleared' counter in two.
        -- The field kept its name but changed its meaning -- it now counts
        -- phases the server announced, not points awards -- and 'awards_seen'
        -- was added to carry what it used to hold. A version-1 blob therefore
        -- cannot be read field-for-field, and restore() migrates it rather
        -- than importing a count authored by the very defect FIX-01 removed.
        version        = 2,
        instance       = run.instance,
        difficulty     = run.difficulty,
        phase          = run.phase,
        kills_cur      = run.kills_cur,
        kills_max      = run.kills_max,
        objective      = run.objective,
        next_boss      = run.next_boss,
        points         = run.points,
        awards_seen    = run.awards_seen,
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

    if run.skirmish then
        out.skirmish = true;
        -- Stored as a duration, like the other clocks: the monotonic clock
        -- restarts with the addon, and the reload gap is added back on
        -- restore so time away counts as quiet time.
        out.skirmish_idle = self:now() - (run.last_skirmish_at or run.started);
    end

    for labelText, entry in pairs(run.extra) do
        out.extra[labelText] = {
            label = entry.label, cur = entry.cur,
            max = entry.max, done = entry.done,
        };
    end

    return out;
end

--[[
* Structural validation of a decoded session.
*
* json.decode is already protected; the decoded *shape* is not. Everything
* below is well-formed JSON that restore() would previously have trusted: a
* kill cap that is a string, an objective count the progress bar divides by, a
* mob list holding a number where table.concat wants a name. A field of the
* wrong type reaches arithmetic in ui.lua one frame later -- and, since the
* wall-clock ageing landed, inside restore() itself, which runs outside any
* protected call at both of its call sites.
*
* Two rules govern this, and both are the project's core value restated:
*
*   Reject, never coerce. A coerced field is a number the server never sent,
*   displayed with exactly the same confidence as one it did.
*
*   Discard whole, never half-apply. A malformed member fails the entire blob.
*   A run resumed with one of the two boons the player picked, and nothing on
*   screen saying the other was dropped, is quietly wrong.
*
* Shapes only. The objective's kind is checked for being a string and never
* against a list of known kinds: a kind the server adds later must survive,
* and a name of anything belongs in no Lua file here.
]]--

local function opt_number(v)  return v == nil or type(v) == 'number';  end
local function opt_string(v)  return v == nil or type(v) == 'string';  end
local function opt_boolean(v) return v == nil or type(v) == 'boolean'; end
local function opt_table(v)   return v == nil or type(v) == 'table';   end

--[[
* The right shape, carrying no value: NaN and +/-infinity.
*
* opt_number above answers 'is this the right shape', and these are: they are
* of type 'number', and every rule in this file passes them. But there is
* nothing either of them could be said to *be* -- no minute, no kill count, no
* save stamp -- and arithmetic spreads them instead of stopping on them. A
* save stamp of NaN makes both the instance clock and the elapsed counter NaN,
* and the window then draws
*
*     ~-9223372036854775808:-9223372036854775808:-9223372036854775808
*
* where the clock belongs under LuaJIT, which is the dialect Ashita embeds,
* and raises out of string.format under Lua 5.3 and later. A fabricated number
* drawn beside real ones is the worst outcome this addon recognises.
*
* So a non-finite number is read exactly as a missing key would be: that one
* field reads as unknown, and everything else in the run comes back intact.
*
* Absent rather than fatal, deliberately. Review finding CR-01 settled that
* this validator never judges whether a value is *informative*, because
* refusing a blob costs a live run's boons, points, phase and elapsed and the
* server re-announces none of it. Dropping one field is not that judgement:
* it is the narrower one that there is no number here to keep. The parallel
* with a blank string is exact except in what it draws -- a blank name is the
* right shape carrying nothing and draws nothing, while a NaN is the right
* shape carrying nothing and draws garbage -- so the field goes rather than
* the run.
*
* Reachable: '1e999' is well-formed JSON, the settings file is one a player
* can hand-edit, and Ashita's own json.lua decodes it to +infinity on both
* dialects. NaN is one subtraction away from that, and tonumber('nan') is a
* real NaN under LuaJIT.
*
* Written the long way because it is the one form that means the same thing in
* both dialects: 'v ~= v' is true of NaN alone, and each infinity is equal to
* math.huge or its negation. tostring() is not usable for this -- Lua 5.5 on
* Windows prints '-nan(ind)' where LuaJIT prints 'nan' -- and neither is any
* integer test, since LuaJIT has no integer subtype at all.
]]--
local function finite(v)
    if type(v) ~= 'number' or v ~= v or v == math.huge or v == -math.huge then
        return nil;
    end
    return v;
end

--[[
* Shape, never content.
*
* Every string field below is checked for *being* a string and never for
* saying anything. An earlier form of this validator demanded a *non-empty*
* string for the instance name, the boss preview's name, a boon's name and
* every mob in the list. A blank one there is not a wrong shape; it is the
* right shape carrying nothing, and every consumer already handles it --
* imgui.TextColored('') draws nothing at all.
*
* The two costs are not comparable. A blank field costs one empty row on
* screen. Refusing the blob costs the whole run -- boons, points, phase,
* elapsed -- and the server re-announces none of it, so nothing can put it
* back. Refusing is right where accepting would put a name or a number on
* screen that the server never sent. A blank puts nothing on screen at all,
* so it cannot be the thing that lies.
*
* Nor is a blank hypothetical here. The addon's own writers produce them:
*
*   'Incursion [] Begins! (Normal)'    -> instance = ''
*   '(Boss:  at (J-9))'                -> next_boss.name = ''
*   'New Objective: Defeat  at (J-9)!' -> objective.name = ''
*
* and a blob written by shipped 1.1.0 -- which restore() still accepts, by
* version -- can carry a blank boon name (its boon matcher had no name
* guard) or a blank mob (its list split kept empty pieces). Those blobs are
* on players' disks today. Demanding a non-blank string here turns one
* degenerate server line, or an upgrade, into total loss of a live run: the
* precise harm the persistence layer exists to prevent.
*
* What still fails a blob is a field of the wrong *type* -- nil where a name
* belongs, a number, a nested table -- because those are what reach
* arithmetic and table.concat, and those are what no writer here produces.
]]--
local function is_string(v)
    return type(v) == 'string';
end

-- A positive integer key, in the dialect-independent form: JSON decoders hand
-- back floats where tonumber gives integers, so the test is the value's own
-- arithmetic, not its subtype.
local function array_key(k)
    return type(k) == 'number' and k >= 1 and k % 1 == 0;
end

-- Every key as well as every value. A stray key or a hole is a shape the
-- addon's own writers cannot produce, and admitting one would let a decoded
-- blob smuggle a value past a length-based loop unseen.
local function array_of(t, ok)
    if t == nil then
        return true;
    end
    if type(t) ~= 'table' then
        return false;
    end
    local n = 0;
    for k, v in pairs(t) do
        if not array_key(k) or not ok(v) then
            return false;
        end
        n = n + 1;
    end
    -- Contiguous from 1, and not merely a set of positive integer keys.
    -- Every loop that reads one of these lists is driven by '#', and '#' on a
    -- table with a hole is unspecified: keys {1, 3} answered 1 here, so a
    -- three-boon list came back holding one boon with nothing on screen
    -- saying the other two were dropped. That is the half-apply this whole
    -- validator exists to forbid, and checking the keys one at a time cannot
    -- see it -- a hole is the absence of a key, so pairs() never visits it.
    -- Counting what pairs() did visit and then demanding 1..n does.
    --
    -- Reachable, not hypothetical: '"boons": [{...}, null, {...}]' is
    -- well-formed JSON, the settings file is one a player can hand-edit, and
    -- a decoder that drops null elements hands back exactly {1, 3}.
    for i = 1, n do
        if t[i] == nil then
            return false;
        end
    end
    return true;
end

local function map_of(t, ok)
    if t == nil then
        return true;
    end
    if type(t) ~= 'table' then
        return false;
    end
    for k, v in pairs(t) do
        if type(k) ~= 'string' or not ok(v) then
            return false;
        end
    end
    return true;
end

local function valid_objective(o)
    if o == nil then
        return true;
    end
    if type(o) ~= 'table' then
        return false;
    end
    return opt_string(o.kind) and opt_string(o.name) and opt_string(o.loc)
        and opt_string(o.text) and opt_number(o.count)
        and opt_boolean(o.stale)
        and array_of(o.mobs, is_string);
end

local function valid_next_boss(b)
    if b == nil then
        return true;
    end
    return type(b) == 'table' and is_string(b.name) and opt_string(b.loc);
end

local function valid_bonus(b)
    if b == nil then
        return true;
    end
    if type(b) ~= 'table' then
        return false;
    end
    return opt_string(b.kind) and opt_string(b.label) and opt_string(b.loc)
        and opt_number(b.cur) and opt_number(b.max) and opt_number(b.remaining)
        and opt_boolean(b.done);
end

local function valid_boon(b)
    return type(b) == 'table' and is_string(b.name) and opt_string(b.stats);
end

local function valid_extra(e)
    return type(e) == 'table' and opt_string(e.label)
        and opt_number(e.cur) and opt_number(e.max) and opt_boolean(e.done);
end

local function valid_session(data)
    if type(data) ~= 'table' then
        return false;
    end
    return is_string(data.instance)
        and opt_string(data.difficulty) and opt_string(data.finish_time)
        and opt_number(data.phase) and opt_number(data.kills_cur)
        and opt_number(data.kills_max) and opt_number(data.points)
        and opt_number(data.awards_seen) and opt_number(data.phases_cleared)
        and opt_number(data.elapsed) and opt_number(data.time_left)
        and opt_number(data.saved_at)
        and opt_boolean(data.finished) and opt_boolean(data.points_partial)
        and opt_boolean(data.skirmish) and opt_number(data.skirmish_idle)
        and valid_objective(data.objective)
        and valid_next_boss(data.next_boss)
        and valid_bonus(data.bonus)
        and array_of(data.boons, valid_boon)
        and map_of(data.extra, valid_extra);
end

function State:restore(data)
    if type(data) ~= 'table' or not data.instance then
        return false;
    end
    if data.version ~= 1 and data.version ~= 2 then
        return false;
    end

    -- After the version gate, before anything is read for its *value*: the
    -- wall-clock arithmetic below, the version-1 migration and the clock
    -- ageing all assume the shapes this answers for. A false answer discards
    -- the session whole and leaves the state exactly as it was found -- a run
    -- already in progress is not disturbed by a rejection.
    if not valid_session(data) then
        return false;
    end

    -- A finished run has nothing left to track. Resuming one would pop a stale
    -- 'Complete!' window on the next login for a run already over.
    if data.finished then
        return false;
    end

    -- Every number the blob carries is read through finite() from here down,
    -- so NaN and +/-infinity arrive as nil and are handled by the same arms
    -- that already handle an absent field. The four that reach arithmetic
    -- before the run is built are taken once, here, so the gap, the staleness
    -- rule and the clock all read the same value.
    local saved_at  = finite(data.saved_at);
    local time_left = finite(data.time_left);
    local elapsed   = finite(data.elapsed);
    local phase     = finite(data.phase);

    -- How long we were gone. Wall clock is the only source that survives
    -- process death: the injected monotonic clock restarts from zero with the
    -- addon, so the stamp written at save time is the only record of the gap.
    -- A negative gap is a stamp from the future -- clock skew, or a settings
    -- file edited by hand -- and is clamped to zero, because time spent away
    -- can only ever be taken off the run, never added to it. An absent stamp
    -- reads as no gap, which is also what exempts such a blob from the
    -- staleness rule below, exactly as before.
    local gap = 0;
    if saved_at then
        gap = os.time() - saved_at;
        if gap < 0 then
            gap = 0;
        end
    end

    if saved_at and gap > STALE_SECONDS then
        return false;
    end

    -- STALE_SECONDS is three hours; an Incursion is ninety minutes. So the
    -- staleness rule alone lets a run come back that the instance clock
    -- already proves is over -- the window would show ~0:00 in red beside an
    -- elapsed counter past the instance duration, 'Waiting for next
    -- objective...', and a phase count that will never move again, and it
    -- would sit there until the player typed /incursion reset. Presenting a
    -- finished run as live is exactly the failure this addon exists to avoid,
    -- and the two facts needed to catch it -- the gap and the saved time_left
    -- -- are both to hand here.
    --
    -- One minute of slack: the server reports whole minutes, and our own
    -- countdown floors at zero, so the saved value can be up to a minute
    -- short of the truth. Erring towards resuming keeps a run that might
    -- still be live rather than discarding one that is.
    if time_left and gap > time_left + 60 then
        return false;
    end

    local now = self:now();
    local run = new_run(self, data.instance, data.difficulty);

    run.phase          = phase;
    run.kills_cur      = finite(data.kills_cur) or 0;
    run.kills_max      = finite(data.kills_max);
    -- Copied field by field rather than adopted whole. The decoded blob is a
    -- table the addon does not own -- the caller keeps a handle on it and can
    -- change it afterwards -- and adopting it by reference is what review
    -- finding IN-01 recorded. The bonus, the boons and the extras below were
    -- already built this way; these two are now the same.
    if data.objective then
        local o = data.objective;
        run.objective = {
            kind  = o.kind,
            name  = o.name,
            loc   = o.loc,
            text  = o.text,
            count = finite(o.count),
            stale = o.stale,
        };
        if o.mobs then
            local mobs = {};
            for i = 1, #o.mobs do
                mobs[i] = o.mobs[i];
            end
            run.objective.mobs = mobs;
        end
    end

    if data.next_boss then
        run.next_boss = { name = data.next_boss.name, loc = data.next_boss.loc };
    end

    run.points         = finite(data.points) or 0;
    if data.version == 1 then
        -- A blob written by 1.1.0. Its 'phases_cleared' was authored by every
        -- points award -- bonus payouts and chests included -- and then raised
        -- to phase-1 by the reconnect inference, so it is max(awards, phase-1)
        -- and importing it whole would put the defect FIX-01 removed straight
        -- back on the HUD, one higher than before once the completion lands.
        --
        -- The phase number is the one field in that blob the server authored
        -- outright, so the cleared count is re-derived from it, exactly as a
        -- live phase line would.
        --
        -- The award count is not recoverable at all: max(awards, phase-1)
        -- over-states it, and an over-stated awards_seen would suppress the
        -- points lower-bound marking for the rest of the run. Starting at
        -- zero marks rather than hides, which is the only safe direction.
        run.awards_seen    = 0;
        run.phases_cleared = phase and (phase - 1) or 0;
    else
        run.awards_seen    = finite(data.awards_seen) or 0;
        run.phases_cleared = finite(data.phases_cleared) or 0;
    end
    run.points_partial = data.points_partial or false;
    -- The gap counts as run time: the instance kept going without us.
    run.started        = now - (elapsed or 0) - gap;
    run.recovered      = true;

    -- We were not listening between the save and now, so treat everything
    -- restored as a lower bound until the server tells us otherwise.
    run.desynced       = true;

    if time_left then
        run.time_left = time_left - gap;
        if run.time_left < 0 then
            run.time_left = 0;
        end
        run.time_sync = now;
    end

    if data.bonus then
        local remaining = finite(data.bonus.remaining);
        run.bonus = {
            kind  = data.bonus.kind,
            label = data.bonus.label,
            loc   = data.bonus.loc,
            cur   = finite(data.bonus.cur) or 0,
            max   = finite(data.bonus.max),
            done  = data.bonus.done or false,
            -- No special case for a bonus that ran out while we were gone: a
            -- negative result puts the expiry in the past, and State:bonus()
            -- already drops a not-done bonus past its expiry. That keeps the
            -- record in place, so a later progress line can still revive it.
            expires_at = remaining and (now + remaining - gap) or nil,
        };
    end

    -- Copied unconditionally. The loop used to skip a malformed entry, which
    -- is a half-apply by definition: the run came back holding one of the two
    -- boons the player picked, with nothing on screen saying the other was
    -- dropped. A malformed entry has already failed the whole blob above.
    if data.skirmish then
        run.skirmish = true;
        local idle = finite(data.skirmish_idle) or 0;
        if idle < 0 then
            idle = 0;
        end
        -- The reload gap counts as quiet time: nothing the mode said while
        -- we were away was heard, which is exactly what the idle rule asks.
        run.last_skirmish_at = now - idle - gap;
    end

    if data.boons then
        for i = 1, #data.boons do
            local b = data.boons[i];
            run.boons[i] = { name = b.name, stats = b.stats };
        end
    end

    if data.extra then
        for labelText, entry in pairs(data.extra) do
            run.extra[labelText] = {
                label = entry.label or labelText, cur = finite(entry.cur),
                max = finite(entry.max), done = entry.done or false, at = now,
            };
        end
    end

    self.run = run;
    return true;
end

return State;
