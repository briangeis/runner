"""Gameplay balance.

Every value that affects how the game *feels* lives here, in one place, so it
can be tuned without hunting through the code.

Speeds are written in the original's units, pixels per 18.2 Hz tick, so
they stay comparable with the 1998 values.  The ``*_PX_S`` constants convert
to pixels per second for use against a delta time.

Where a value departs from the 1998 original, the comment records what the
original was and what was wrong with it.  Those numbers were measured, not
guessed, and the measurement sits beside each one.
"""

from __future__ import annotations

from .config import DOS_TICK_HZ, HUD_HEIGHT, ticks_to_seconds

# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------

#: Movement speed in pixels per original tick, per axis.
#:
#: The original's 3.0 crossed the screen in 5.9 seconds, 1.56 of the ship's
#: own widths per second, where arcade shooters of the era crossed in 1.5-2.5s.
#: Five brings that to 3.5s while staying short of twitchy.
PLAYER_SPEED = 5.0

# --------------------------------------------------------------------------
# Shots
# --------------------------------------------------------------------------

#: Original 5.0.  Kept at roughly 1.6x the ship's speed, as the original ratio
#: had it, so bolts still outrun the ship by the same margin.
SHOT_SPEED = 8.0

#: Gap between volleys, in original ticks, indexed by fire-rate tier.
#:
#: The original's "extra shots" upgrade doubled MAX_SHOTS, the cap on bolts in
#: flight.  Because that cap was binding in every mode, since 5 volleys are
#: airborne at once but the cap allowed 3, it acted as a hidden 40-65%
#: fire-rate increase the player could neither see nor reason about.  Fire rate
#: is now three explicit tiers, and tier 1 is deliberately slower than the
#: original's flat 5 ticks so that buying the next tier is felt.  Tier 3 lands
#: near where the old hidden bonus put you.
SHOT_COOLDOWN_TICKS = {1: 7.5, 2: 5.0, 3: 3.2}

#: Horizontal offset of the outer bolts from the ship's center.  The original
#: put them at the wingtips, 26px apart, so a triple shot was a dense column.
#: Wide enough here that the three lanes are meaningfully different, but still
#: narrow enough that hitting anything means being underneath it. The game's
#: central bargain is that you fire up and they fire down, so attacking has to
#: mean exposure.
VOLLEY_SPREAD = 20.0

#: The original reused SHOT_SPD for enemy fire, so speeding up the player's
#: bolts would have sped up incoming fire identically.  Split out, and nudged
#: up far less than the player's, since a faster ship already makes the
#: original incoming fire easier to dodge.  Original: 5.0.  The mothership's
#: ordinary paired bolts use this too; only the killshot has its own speed.
ENEMY_SHOT_SPEED = 6.0

#: The killshot, which is the mothership's alone.
#:
#: The charge is the warning, so the dodge is meant to happen while she is
#: lining up, not after the bolt leaves.  At the original 7.0 it was only
#: unavoidable from directly beneath her, and gave two thirds of a second to
#: react from the bottom of the screen against the 0.20s needed to step clear,
#: which made the charge something to watch rather than something to move for.
#: At 12.0 it cannot be dodged anywhere above the screen's midpoint, and even
#: at the very bottom it allows 0.38s, so reacting has to be immediate.
BOSS_SHOT_SPEED = 12.0

# --------------------------------------------------------------------------
# Enemies
# --------------------------------------------------------------------------

#: Per-type (min, max) speed in pixels per tick.  The original used one range,
#: (1.0, 2.0), for every type regardless of size, so a 16x10 asteroid drifted
#: exactly like a 52x26 gunship.  Size now means something.
ENEMY_SPEED = {
    0: (2.0, 3.0),  # 32x19 asteroid
    1: (1.5, 2.0),  # 52x26 red gunship
    2: (3.0, 4.5),  # 16x10 asteroid
    3: (2.0, 3.0),  # 31x24 nuisance ship
    4: (1.5, 2.5),  # 39x37 blue bomber
}

#: Hit points per enemy type.  The original killed every enemy with a single
#: bolt whatever the weapon tier, so weapon upgrades did nothing at all outside
#: the boss fight.  Size now buys durability as well as slowness; the two small
#: asteroids stay one-shot kills so the screen doesn't turn spongy.
ENEMY_HIT_POINTS = {0: 1, 1: 3, 2: 1, 3: 2, 4: 3}

#: How long a damaged enemy flashes, matching the player's hit feedback.  The
#: original had no damage feedback anywhere.
ENEMY_HIT_FLASH_SECONDS = 0.12

#: Chance per tick that a free enemy slot refills.  The original's 1/3 refilled
#: a slot in 0.16s, holding 7.8 of 8 alive 83% of the time: a permanently
#: saturated screen with no rhythm.  Measured to leave roughly 5 of 8 alive,
#: which opens gaps to fly through.
RESPAWN_CHANCE = 1 / 40

#: Seconds between one enemy's bolts, drawn uniformly from this range.
#:
#: The original rolled a per-tick coin flip for every shooting enemy, which
#: gives exponentially distributed gaps.  Measured over three minutes: 18% of
#: an enemy's consecutive shots came within half a second and the closest pair
#: was 0.02s apart, while the ninetieth percentile gap was 28s.  Two bolts
#: leaving one ship at once claim two of the six shared slots, and the rest of
#: the screen falls silent for it.  A bounded interval keeps the same overall
#: rate and spreads it across the enemies that are actually on screen.
#:
#: The gap after spawning is drawn from zero instead, so ships that have only
#: just arrived are not all mute for the same minimum first.
ENEMY_VOLLEY_INTERVAL = (1.8, 3.8)

MAX_ENEMIES = 8
MAX_ENEMY_SHOTS = 6

#: Attempts to find a spawn position clear of other enemies.  The original
#: never checked, and stacked them on roughly 12% of spawns.
SPAWN_CLEARANCE_TRIES = 12

#: Vertical band the blue bomber may occupy, as fractions of the screen.
#: "Fire up, they fire down" makes the top enemy territory and the bottom the
#: player's; the original let the bomber run to y=136 of 200, deep into the
#: player's half.  It now stays below the HUD and clear of the midpoint.
BOMBER_BAND_TOP = 0.05
BOMBER_BAND_BOTTOM = 0.5

#: Fraction of the bottom edge, centered, where asteroids never enter.  Play
#: funnels the ship to the center-bottom, and a rock rising into it from off
#: screen is unreactable; it was the single largest cause of deaths.  Keeping
#: the outer margins live preserves what asteroids are actually for, which is
#: making the screen edges uncomfortable.  The original had no such exclusion.
ASTEROID_BOTTOM_SAFE_FRACTION = 0.5

# --------------------------------------------------------------------------
# Mothership
# --------------------------------------------------------------------------

#: The original ran both axes at 3.0.  She bounced vertically 1.1 times a
#: second inside a 25px band while being 46px tall, which read as a vibration
#: rather than a patrol; a slower vertical sweep fixes that.
BOSS_SPEED_X = 3.5
BOSS_SPEED_Y = 1.0

#: Vertical patrol band, in pixels from the top of the screen.
#:
#: The original's top of 0 let her slide under the status bar, which draws over
#: everything.  Its bottom of 25 put her *bottom edge* at y=71; a later
#: widening to 60 pushed that to y=106, past the screen's own midpoint, leaving
#: under 0.8s to read a falling bolt.  Holding her between 10 and 32 keeps her
#: bottom edge at 56-78 and gives the player a full second.
BOSS_PATROL_TOP = float(HUD_HEIGHT)
BOSS_PATROL_BOTTOM = 32.0

#: Hit points for the first mothership of a game, and the amount added for each
#: one already beaten.
#:
#: The original used a flat 18 forever, so once the player had upgrades the
#: fight was over in about half a second.  A game with no levels and no ending
#: otherwise has no difficulty curve for upgrades to keep up with.  The step
#: has to match that curve, which multiplies damage roughly sevenfold across
#: the three tracks; at 25 a fully-kitted player still needs long enough with
#: her for her behavior to show.
BOSS_POWER = 15
BOSS_POWER_STEP = 25

#: Spaceship kills needed to lure her out.  Unchanged from the original, except
#: that asteroids no longer count toward it.
KILLS_FOR_BOSS = 25

#: Seconds between her ordinary bolts, drawn uniformly from this range.
#:
#: The original shared the regular enemy rate, giving a volley every 2.7s,
#: far too sparse for something meant to be intimidating.  A per-tick coin flip
#: also gives exponentially distributed gaps: a tenth under 0.08s and a tenth
#: over 1.75s, so bolts arrive in clusters and then not at all.  A bounded
#: interval keeps steady pressure without being metronomic.
BOSS_VOLLEY_INTERVAL = (0.55, 1.05)

#: Probability she commits to a killshot when an overlap begins and she is
#: recharged.
#:
#: The trigger is the two hulls sharing a column: the instant the player is
#: lined up to shoot her is the instant she is lined up to shoot back.  That
#: shared moment is the whole dilemma: going in for damage invites the chase,
#: and sitting still invites it too, because her patrol crosses the player
#: sooner or later and there is nowhere to hide from it.
#:
#: Rolled on a timer for as long as the player is in her column, not once on
#: the way in.  Rolling only on entry meant a player could park underneath her
#: and be safe there, which is the reverse of what sharing her column should
#: mean.  Kept below certainty so it is never something to count on.
#:
#: Measured over three minutes against three players: one holding still, one
#: parked in her column, one working to stay out of it.  This pair gives them
#: 9.3, 10.3 and 5.0 chases a minute, and she is charging for under a third of
#: the fight in the worst case.  Standing in her column is the dangerous
#: choice, holding still is nearly as bad, and moving out of it is the way to
#: be left alone.
BOSS_KILLSHOT_CHANCE = 0.85

#: How long she waits before considering a killshot again, whether the last
#: roll committed her or not.  It is both the recharge after firing and the
#: cadence of the rolls themselves, so it sets the ceiling on how often a
#: player standing in her column can be chased.
BOSS_KILLSHOT_INTERVAL = 3.5

#: Quiet on her *ordinary* fire after a killshot, a shorter breather than the
#: recharge above, so dodging her buys a moment to recover rather than dropping
#: the player straight back under the bombing.
BOSS_RECOVERY_SECONDS = 1.2

#: Quiet after she first arrives, before any killshot.  Separate from the
#: interval: starting on a full cooldown meant an upgraded player could kill
#: her before she ever attempted one.
BOSS_FIRST_KILLSHOT_DELAY = 1.0

#: While charging she stops firing normally and moves at this fraction of her
#: patrol speed, chasing the player to line the shot up.  It must stay below
#: the player's speed so breaking away is always possible, but not so far
#: below that the chase is invisible.  At 0.85 over 1.8s she covers 97px
#: against the player's 164px: escaping works, but has to be committed to.
BOSS_CHARGE_SPEED_SCALE = 0.85
BOSS_CHARGE_SECONDS = 1.8

# --------------------------------------------------------------------------
# Economy
# --------------------------------------------------------------------------

#: Chance a killed enemy leaves a power-up.  Asteroids never do.  Unchanged.
POWERUP_DROP_CHANCE = 1 / 4

#: The original paid 50 for a money drop against a $100 cheapest shelf, which
#: worked out at $29/min: the shop was mathematically unreachable, and the
#: first visit could buy nothing at all with $63 in hand.  The fix is mostly
#: frequency rather than size: money is now over half of all drops and the
#: mothership pays a bounty.  Measured at roughly $450 a boss cycle, about one
#: purchase, which puts a full loadout 5-6 bosses out and leaves the original
#: shop prices untouched.  Money drops less often now that points drop as
#: often as it does, so the amount rises to hold income where it was.
MONEY_VALUE = 85

#: Points for a points pickup.  Worth flying for: a bomber, the dearest kill
#: on the board, pays 40, so this is six of those for one collected orb.  The
#: original paid 50 against a flat 10 a kill, which made it barely worth the
#: detour, let alone the risk of taking one.
POINTS_VALUE = 250

#: Relative weights for what a power-up turns out to be.
#:
#: The original used a rand() % 14 ladder in which three of the fourteen slots
#: were permanent upgrades, so upgrades arrived every three minutes or so,
#: routine enough to fully kit out by drops alone, and progression was decided
#: by drop luck rather than by play.  Worse, a roll could land on something
#: already maxed and be silently wasted.
#:
#: "BENEFIT" is a single slot that resolves *on pickup*, choosing among the
#: things the player can actually still use with odds inversely proportional to
#: what the shop charges for them.  Only about a third of what it yields is a
#: permanent upgrade, since the rest is shield refills and the like, so this
#: weight keeps the true upgrade rate near 9%, against the original's 21%.
DROP_WEIGHTS = {"MONEY": 37, "POINTS": 37, "BENEFIT": 26}

#: Points for destroying each enemy type.
#:
#: The original paid a flat 10 for anything at all, the mothership included,
#: so the score recorded how long you had played rather than how well.  Points
#: now follow how hard the kill was: how much it takes to destroy, how small
#: and quick it is, and whether it shoots back.  Asteroids stay cheap, since
#: they are the clock rather than the objective.
ENEMY_SCORE = {
    0: 5,   # 32x19 asteroid: one hit, drifts, the easiest thing on screen
    2: 10,  # 16x10 asteroid: one hit, but the smallest and fastest target
    1: 20,  # 52x26 gunship: three hits, though big and predictable
    3: 30,  # 31x24 nuisance ship: two hits, shoots, cuts across the player
    4: 40,  # 39x37 bomber: three hits, shoots, and works the danger zone
}

#: Points for the mothership, plus the step for each already beaten, so her
#: score climbs with her health the way the bounty does.
BOSS_SCORE = 500
BOSS_SCORE_STEP = 200

#: Paid for destroying the mothership, plus the step for each already beaten.
#: The original paid nothing, so drops were the only income and money was
#: unrelated to progress.  A bounty ties income to the boss cycle rather than
#: to raw grinding.
BOSS_BOUNTY = 150
BOSS_BOUNTY_STEP = 40

# --------------------------------------------------------------------------
# Levels
# --------------------------------------------------------------------------

#: Extra asteroid pressure per level beyond the first, as a fraction applied to
#: both their spawn rate and their speed.  Asteroids are the clock that stops a
#: level being dragged out, so they are what intensifies; the spaceships stay
#: predictable, per the intended design.  The original had no levels at all.
ASTEROID_PRESSURE_STEP = 0.12

# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------

#: Starfield density and per-star speed range, in pixels per tick.  The
#: original's 250 stars at 10-29 crossed the screen in 0.4-1.1s, too fast to
#: read as depth; it looked like noise rather than travel.  These take
#: 0.8-2.7s.
STAR_COUNT = 150
STAR_SPEED_MIN = 4.0
STAR_SPEED_MAX = 14.0

#: How long the ship flashes after taking a hit.  The original gave no feedback
#: beyond the shield meter ticking down at the top of the screen, which is easy
#: to miss mid-fight.
HIT_FLASH_SECONDS = 0.3

# --------------------------------------------------------------------------
# Derived
# --------------------------------------------------------------------------

PLAYER_SPEED_PX_S = PLAYER_SPEED * DOS_TICK_HZ
SHOT_SPEED_PX_S = SHOT_SPEED * DOS_TICK_HZ
ENEMY_SHOT_SPEED_PX_S = ENEMY_SHOT_SPEED * DOS_TICK_HZ
BOSS_SHOT_SPEED_PX_S = BOSS_SHOT_SPEED * DOS_TICK_HZ
BOSS_SPEED_X_PX_S = BOSS_SPEED_X * DOS_TICK_HZ
BOSS_SPEED_Y_PX_S = BOSS_SPEED_Y * DOS_TICK_HZ


def cooldown_for(tier: int) -> float:
    """Seconds between volleys at a given fire-rate tier."""
    return ticks_to_seconds(SHOT_COOLDOWN_TICKS.get(tier, SHOT_COOLDOWN_TICKS[1]))


def enemy_speed_range(type_index: int) -> tuple[float, float]:
    return ENEMY_SPEED.get(type_index, (1.0, 2.0))


def enemy_health(type_index: int) -> int:
    return ENEMY_HIT_POINTS.get(type_index, 1)


def boss_health(bosses_beaten: int) -> int:
    """Hit points for the next mothership.

    ``bosses_beaten`` counts those already destroyed this game, so the first
    fight uses the base value.
    """
    return BOSS_POWER + BOSS_POWER_STEP * bosses_beaten


def boss_reward(bosses_beaten: int) -> int:
    return BOSS_BOUNTY + BOSS_BOUNTY_STEP * bosses_beaten


def enemy_score(type_index: int) -> int:
    return ENEMY_SCORE.get(type_index, 0)


def boss_score(bosses_beaten: int) -> int:
    return BOSS_SCORE + BOSS_SCORE_STEP * bosses_beaten


def level_pressure(level: int) -> float:
    """Multiplier applied to asteroid spawn rate and speed on a level."""
    return 1.0 + ASTEROID_PRESSURE_STEP * max(0, level - 1)
