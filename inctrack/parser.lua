--[[
* inctrack -- parser.lua
* Copyright (c) 2026 Godwen. MIT License; see LICENSE in the repository root.
* Written with Claude (Anthropic).
]]--

--[[
* parser.lua -- CatsEyeXI Incursion chat message parser.
*
* Pure Lua. No Ashita dependency, no state. One function:
*
*     parser.parse(line) -> event table, or nil if the line is not ours.
*
* Two tiers of pattern:
*
*   Specific -- the message shapes the server sends today, recognised precisely
*               so the window can draw progress bars, coordinates and timers.
*
*   Generic  -- catch-alls for anything Incursion-tagged that the specific
*               patterns do not know. A new instance, objective wording, or
*               counter added to the server later still reaches the window as
*               readable text instead of being silently dropped. The generic
*               patterns are tried last, so they never shadow a specific one.
*
* The test suite asserts that the generic tier matches *nothing* in the current
* chatlogs -- if a generic fires on a real line today, a specific pattern has
* regressed.
]]--

local parser = {};

local function trim(s)
    return (s:gsub('^%s+', ''):gsub('%s+$', ''));
end

-- 'Orcish Grappler, Orcish Mesmerizer, Orcish Fodder' -> { 'Orcish Grappler', ... }
--
-- The separator is comma-space, scanned as plain text, not any comma. A name
-- carrying its own comma would not have a space after it, so splitting on the
-- two characters together keeps such a name whole where splitting on the comma
-- alone would put two mobs in the window that the server never named. All 469
-- kill-objective lines across 127 logs split identically either way, so this
-- narrows the rule without changing one line the server has actually sent.
-- A piece that is empty once trimmed is dropped rather than drawn as a blank.
local function split_mobs(s)
    local out = {};
    local start = 1;
    while true do
        local i, j = s:find(', ', start, true);
        local piece = trim(i and s:sub(start, i - 1) or s:sub(start));
        if piece ~= '' then
            out[#out + 1] = piece;
        end
        if not i then
            break;
        end
        start = j + 1;
    end
    return out;
end

-- Pull a '(Expires in N Minutes)' suffix off a bonus line, returning the
-- remainder and the minutes. Shared by the specific and generic bonus forms.
local function split_expiry(s)
    local body, mins = s:match('^(.-)%s*%(Expires in (%d+) Minutes?%)$');
    if body then
        return body, tonumber(mins);
    end
    return s, nil;
end

--[[
* Specific matchers, in order. Where two could match the same line the more
* precise one comes first:
*
*   bonus_progress before phase   -- both are 'Incursion [X] ... N/M'
*   objective_kills before objective_boss
*   bonus chest / count / named   -- 'Defeat 5 Sentry Lizard!' must not be read
*                                    as a named NM
]]--
local specific = {
    -- Incursion [Fort Ghelsba] Begins! (Normal)
    function(s)
        local instance, difficulty = s:match('^Incursion %[(.-)%] Begins! %((.-)%)$');
        if instance then
            return { t = 'begin', instance = instance, difficulty = difficulty };
        end
    end,

    -- Incursion [Giddeus] Recovering session...
    function(s)
        local instance = s:match('^Incursion %[(.-)%] Recovering session');
        if instance then
            return { t = 'recover', instance = instance };
        end
    end,

    -- Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s
    function(s)
        local instance, difficulty, m, sec =
            s:match('^Incursion %[(.-)%] Complete! %((.-)%) Time: (%d+)m (%d+)s');
        if instance then
            return {
                t = 'complete', instance = instance, difficulty = difficulty,
                minutes = tonumber(m), seconds = tonumber(sec),
            };
        end
    end,

    -- Incursion [Fort Ghelsba] Bonus Objective Complete!
    function(s)
        local instance = s:match('^Incursion %[(.-)%] Bonus Objective Complete!');
        if instance then
            return { t = 'bonus_done', instance = instance };
        end
    end,

    -- Incursion [Fort Ghelsba] Bonus Objective: Sentry Lizard 2/5
    function(s)
        local instance, name, cur, max =
            s:match('^Incursion %[(.-)%] Bonus Objective: (.+) (%d+)/(%d+)$');
        if instance then
            return {
                t = 'bonus_progress', instance = instance, name = trim(name),
                cur = tonumber(cur), max = tonumber(max),
            };
        end
    end,

    -- Incursion [Fort Ghelsba] Phase #3 12/15
    function(s)
        local instance, phase, cur, max =
            s:match('^Incursion %[(.-)%] Phase #(%d+) (%d+)/(%d+)$');
        if instance then
            return {
                t = 'phase', instance = instance, phase = tonumber(phase),
                cur = tonumber(cur), max = tonumber(max),
            };
        end
    end,

    -- New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Mesmerizer, Orcish Fodder)
    function(s)
        local count, mobs = s:match('^New Objective: Defeat (%d+) enemies %((.+)%)$');
        if count then
            return {
                t = 'objective_kills', count = tonumber(count), mobs = split_mobs(mobs),
            };
        end
    end,

    -- New Objective: Defeat Yagudo Scout at (J-9) (Map #1)!
    --
    -- The location is the anchor, not the name. A parenthesised trailing group
    -- is structurally identifiable; the name is simply whatever precedes it. So
    -- the precise form below captures the name greedily and requires the
    -- location to be parenthesised, which puts the split on the *last* ' at '
    -- rather than the first -- and a name that carries that substring itself
    -- survives whole instead of being truncated with its tail folded into the
    -- coordinates. Recognising such a name any other way would mean holding a
    -- list of names, which is hardcoded content and forbidden outright.
    --
    -- If the precise form declines, the shape shipped in 1.1.0 answers
    -- unchanged, so nothing that reaches the window today can stop reaching it.
    function(s)
        local name, loc = s:match('^New Objective: Defeat (.*) at (%(.+%))!$');
        if not name then
            name, loc = s:match('^New Objective: Defeat (.-) at (.+)!$');
        end
        if name then
            return { t = 'objective_boss', name = trim(name), loc = trim(loc) };
        end
    end,

    -- (Boss: Yagudo Scout at (J-9) (Map #1))
    -- Same shape, same anchor, same fallback as the objective above.
    function(s)
        local name, loc = s:match('^%(Boss: (.*) at (%(.+%))%)$');
        if not name then
            name, loc = s:match('^%(Boss: (.-) at (.+)%)$');
        end
        if name then
            return { t = 'boss_hint', name = trim(name), loc = trim(loc) };
        end
    end,

    -- Bonus Objective: Find the hidden chest! (Expires in 10 Minutes)
    function(s)
        local mins = s:match('^Bonus Objective: Find the hidden chest! %(Expires in (%d+) Minutes?%)$');
        if mins then
            return {
                t = 'bonus_new', kind = 'chest', label = 'Find the hidden chest',
                minutes = tonumber(mins),
            };
        end
    end,

    -- Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)
    function(s)
        local count, name, mins =
            s:match('^Bonus Objective: Defeat (%d+) (.+)! %(Expires in (%d+) Minutes?%)$');
        if count then
            return {
                t = 'bonus_new', kind = 'kills', label = trim(name),
                max = tonumber(count), minutes = tonumber(mins),
            };
        end
    end,

    -- Bonus Objective: Defeat Dust Eater at (H-9) (Map #2)! (Expires in 10 Minutes)
    -- Same shape, same anchor, same fallback as the two boss forms above.
    function(s)
        local name, loc, mins =
            s:match('^Bonus Objective: Defeat (.*) at (%(.+%))! %(Expires in (%d+) Minutes?%)$');
        if not name then
            name, loc, mins =
                s:match('^Bonus Objective: Defeat (.-) at (.+)! %(Expires in (%d+) Minutes?%)$');
        end
        if name then
            return {
                t = 'bonus_new', kind = 'nm', label = trim(name), loc = trim(loc),
                max = 1, minutes = tonumber(mins),
            };
        end
    end,

    -- You have 90 minutes remaining inside this Incursion.
    function(s)
        local mins = s:match('^You have (%d+) minutes? remaining inside this Incursion%.$');
        if mins then
            return { t = 'time', minutes = tonumber(mins) };
        end
    end,

    -- Godwen gains 84 incursion points.
    function(s)
        local who, amount = s:match('^(%S+) gains (%d+) incursion points%.$');
        if who then
            return { t = 'points', who = who, amount = tonumber(amount) };
        end
    end,

    -- Godwen gains the effect of Ronin's Revenge (<glyph>): WS Accuracy+15 / Store TP+8
    -- A boon chosen between phases. What makes this unambiguous is the tail: a
    -- parenthesised group, immediately followed by a colon and a space, and
    -- then the stats -- plus a name that is not blank. Ordinary buffs ('gains
    -- the effect of Protect.') have no such tail at all. The glyph is a
    -- client-side icon code and is discarded.
    --
    -- '[^)]' rather than '.-' so the group cannot be a lazy match that steps
    -- over a ')' and takes a later one; that is the part that narrows against
    -- a real ambiguity. The group is allowed to be *empty*, which the '+' here
    -- once forbade: emptiness separates nothing, because the tail plus the
    -- non-blank name below already tell a boon from a buff, and this matcher
    -- has no fallback tier under it the way the ' at ' forms do. A server data
    -- table with an unset icon field renders '()' through the same
    -- '%s gains the effect of %s (%s): %s' template, and a boon dropped there
    -- is dropped for good: the server never announces a boon twice, which is
    -- why it is a MUST_SAVE event in the first place.
    --
    -- The name must be non-blank once trimmed. That guard is doing the real
    -- work: this is the loosest pattern in the file -- it has no 'Incursion
    -- [', 'New Objective:' or '(Boss:' anchor -- so a blank name here means
    -- the match probably found something that is not a boon at all. The
    -- anchored boss forms are the opposite case and keep their blanks: there
    -- a match is certainly a boss line, and what the server did say (the
    -- location) is worth more than nothing.
    function(s)
        local who, name, stats = s:match('^(%S+) gains the effect of (.-) %([^)]*%): (.+)$');
        if who then
            name = trim(name);
            if name ~= '' then
                return { t = 'boon', who = who, name = name, stats = trim(stats) };
            end
        end
    end,
};

--[[
* Generic matchers. Tried only after every specific one has declined, so they
* exist purely to keep future server content visible.
]]--
local generic = {
    -- Any future 'Incursion [X] <label> N/M' counter.
    function(s)
        local instance, labelText, cur, max =
            s:match('^Incursion %[(.-)%] (.+) (%d+)/(%d+)$');
        if instance then
            return {
                t = 'generic_counter', generic = true, instance = instance,
                label = trim(labelText), cur = tonumber(cur), max = tonumber(max),
            };
        end
    end,

    -- Any future 'Incursion [X] <label> Complete!'
    function(s)
        local instance, labelText = s:match('^Incursion %[(.-)%] (.+) Complete!$');
        if instance then
            return {
                t = 'generic_done', generic = true, instance = instance,
                label = trim(labelText),
            };
        end
    end,

    -- Any other Incursion-tagged line.
    function(s)
        local instance, text = s:match('^Incursion %[(.-)%] (.+)$');
        if instance then
            return {
                t = 'generic_note', generic = true, instance = instance,
                text = trim(text),
            };
        end
    end,

    -- Any future objective wording.
    function(s)
        local text = s:match('^New Objective: (.+)$');
        if text then
            return { t = 'objective_text', generic = true, text = trim(text) };
        end
    end,

    -- Any future bonus wording, with the expiry suffix understood.
    function(s)
        local text = s:match('^Bonus Objective: (.+)$');
        if text then
            local body, mins = split_expiry(text);
            return {
                t = 'bonus_new', generic = true, kind = 'text',
                label = trim(body), minutes = mins,
            };
        end
    end,
};

--[[
* Parse a single chat line.
*
* The caller strips colour codes first; this only trims whitespace.
]]--
function parser.parse(line)
    if type(line) ~= 'string' then
        return nil;
    end

    local s = trim(line);

    -- A timestamp plugin may have prepended '[HH:MM:SS] ' (the chatlogs show
    -- doubled stamps, so one is active in this setup). Every pattern here is
    -- ^-anchored, so strip any number of them or nothing else matches.
    while true do
        local rest, n = s:gsub('^%[%d%d:%d%d:%d%d%]%s+', '', 1);
        if n == 0 then
            break;
        end
        s = rest;
    end

    if s == '' then
        return nil;
    end

    -- Cheap rejection: every message we care about starts with one of these.
    -- Chat volume in a party is high and this runs on every line.
    if not (s:find('^Incursion %[')
        or s:find('^New Objective: ')
        or s:find('^Bonus Objective: ')
        or s:find('^%(Boss: ')
        or s:find('^You have %d')
        or s:find('incursion points%.$')
        or s:find('): ', 1, true)) then   -- the '(glyph): stats' tail of a boon
        return nil;
    end

    for i = 1, #specific do
        local event = specific[i](s);
        if event then
            return event;
        end
    end

    for i = 1, #generic do
        local event = generic[i](s);
        if event then
            return event;
        end
    end

    return nil;
end

return parser;
