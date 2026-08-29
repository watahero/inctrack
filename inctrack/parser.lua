--[[
* inctrack -- parser.lua
* Copyright (c) 2026 Godwen. MIT License; see LICENSE in the repository root.
* Written with Claude (Anthropic).
]]--

--[[
* parser.lua -- CatsEyeXI Incursion chat message parser.
*
* Pure Lua. No Ashita dependency, no state. Two functions:
*
*     parser.relevant(line) -> boolean. Could this line possibly be ours?
*         Allocation-free, runs on the *raw* message, and a deliberate
*         superset: it may produce false positives but never false negatives.
*         The shell calls it before strip_colors -- the only place that
*         allocation is avoidable -- and parse calls it again on entry, so
*         the module is safe called standalone.
*
*     parser.parse(line) -> event table, or nil if the line is not ours.
*
* The second entry point matters to a reader more than its size suggests: it
* is called directly from the shell's chat handler, not only through parse,
* so a change to it is a change to what the addon can see at all.
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

-- The byte a timestamped line starts with, resolved once rather than written
-- as a number at the one place it is compared.
local LBRACKET = ('['):byte();

--[[
* Could this line possibly be ours?
*
* Asked before anything is allocated for the line -- before strip_colors in
* the shell and before trim below -- because the chat handler runs on every
* line the client receives, forever, and over 127 real logs 97.5% of them are
* not ours. string.find with plain = true returns indices and never builds a
* string, so a 'no' here costs seven searches over a short string and nothing
* else. The number of searches is fixed and does not depend on the input.
*
* Two rules, in this order.
*
* 1. A line carrying a colour-code marker byte gets an unconditional yes.
*    This runs on the *raw* message, and Ashita's colour codes are a marker
*    byte plus one arbitrary payload byte that can land anywhere -- including
*    between two characters of one of the needles below, which would make
*    every plain search for that needle answer no on a line the server really
*    did send. A line with a code in it is a line this function is not
*    entitled to judge, so it declines to. That line then costs exactly what
*    it cost before this function existed, and never more.
*
*    The marker set is the one Ashita's own strip_colors removes -- 0x1E,
*    0x1F and 0x7F, stripped in a single gsub with a character class
*    (addons/libs/sugar/string.lua, string_mt.strip_colors). The set here
*    must stay a superset of that one, and the coupling is the whole point:
*    a marker the shell strips but this gate does not decline to judge is a
*    line lost before strip_colors ever runs. The chatlogs cannot warn about
*    it either -- they carry no marker bytes at all, because Ashita's log
*    writer strips them on the way to disk -- so this set is checked against
*    the host's source rather than against a survey of real lines.
*
*    Three plain searches rather than one character class: this is the branch
*    every line pays, and a plain search is the one shape that visibly cannot
*    allocate or backtrack.
*
* 2. Otherwise, yes when the line holds any one of the literal substrings the
*    matchers require. Each needle is a literal the corresponding matcher's
*    own pattern cannot match without -- under *every* alternation and *every*
*    optional group in it, not merely under the shape of the example line
*    above that matcher. Two are worth naming:
*
*    - 'remaining inside this Incursion' begins after the optional plural in
*      'You have (%d+) minutes? remaining...', because at the one-minute
*      warning the server sends 'You have 1 minute remaining inside this
*      Incursion.' A needle carrying the plural would answer no, the shell
*      would return before strip_colors, and the instance clock would stop at
*      the moment the player most needs it -- silently, since a dropped line
*      looks exactly like a quiet stretch of chat. That is the only place in
*      this file where a covering needle would otherwise land inside an
*      optional region: the three Bonus Objective expiry forms carry a
*      'Minutes?' as well, but their needle is the 'Bonus Objective: ' prefix,
*      which sits at the head of the line, clear of it.
*
*    - 'gains the effect of ' is the loosest of the seven and admits every
*      ordinary buff line as well as every boon, because a boon carries no
*      'Incursion [', 'New Objective: ' or '(Boss: ' anchor to be told apart
*      by. Those lines pay one wasted colour strip and are then turned away by
*      the anchored rejection below, which is the right side to be wrong on.
*
* Deliberately looser than that anchored rejection, and deliberately in front
* of it rather than in place of it: this one runs on unnormalised text and may
* only ever produce false *positives*, which cost one wasted colour strip. The
* anchored rejection goes on doing the precise half of the job, on text that
* has been trimmed and destamped.
*
* No type guard, deliberately. The shell's pcall boundary has caught a
* non-string message since 1.0.0 by letting the handler's first string method
* call raise; a guard here would turn that into a silent early return.
* parser.parse keeps its own, unchanged.
]]--
function parser.relevant(line)
    if line:find('\30', 1, true)
        or line:find('\31', 1, true)
        or line:find('\127', 1, true) then
        return true;
    end

    return (line:find('Incursion [', 1, true)
        or line:find('New Objective: ', 1, true)
        or line:find('Bonus Objective: ', 1, true)
        or line:find('(Boss: ', 1, true)
        or line:find('remaining inside this Incursion', 1, true)
        or line:find('incursion points.', 1, true)
        or line:find('gains the effect of ', 1, true)) ~= nil;
end

--[[
* Parse a single chat line.
*
* The caller strips colour codes first; this only trims whitespace.
]]--
function parser.parse(line)
    if type(line) ~= 'string' then
        return nil;
    end

    -- The same question the shell asks before it allocates, asked again here
    -- so this module is safe called standalone -- by the test harness, and by
    -- anything that reaches parse without going through the chat handler.
    if not parser.relevant(line) then
        return nil;
    end

    local s = trim(line);

    -- A timestamp plugin may have prepended '[HH:MM:SS] ' (the chatlogs show
    -- doubled stamps, so one is active in this setup). Every pattern here is
    -- ^-anchored, so strip any number of them or nothing else matches.
    --
    -- Only for a line that starts with '[': the loop is a gsub, and an
    -- allocation, for a prefix almost no line carries. The pattern it runs is
    -- ^-anchored itself, so a line beginning with any other byte cannot match
    -- it and the loop's whole cost is the one gsub that finds nothing.
    if s:byte(1) == LBRACKET then
        while true do
            local rest, n = s:gsub('^%[%d%d:%d%d:%d%d%]%s+', '', 1);
            if n == 0 then
                break;
            end
            s = rest;
        end
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
