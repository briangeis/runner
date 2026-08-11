"""Mutable game state.

The original kept all of this as file-scope globals, shared by every module
because the whole game compiled as a single translation unit.  Gathering it
into one object keeps the same convenience without the action-at-a-distance.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import balance, config

#: Base cap on bolts in flight.  The original tracked this as MAX_SHOTS,
#: stepping 3 -> 6 -> 9 with an optional doubling bought from the shop.
BASE_SHOTS = 3

#: Every upgrade track runs 1 to 3.
MAX_TIER = 3


@dataclass
class GameState:
    """Everything that survives a single frame of play."""

    score: int = 0
    money: int = 0
    lives: int = config.STARTING_LIVES
    shields: int = config.STARTING_SHIELDS
    max_shields: int = config.STARTING_MAX_SHIELDS
    kills: int = 0

    level: int = 1

    #: The three upgrade tracks, each running 1 to 3. Tiers can be skipped:
    #: a player may bank money for tier 3 rather than settle for tier 2, which
    #: is the choice the shop is meant to pose.
    curr_weapon: int = 1
    shot_tier: int = 1
    #: The original called this "extra shots" and implemented it as a doubled
    #: cap on bolts in flight. That cap was binding in every mode, so what it
    #: actually delivered was a faster effective rate of fire; now stated
    #: plainly as what it is, and split into tiers like the rest.
    fire_tier: int = 1

    invincible: bool = False
    invincible_timer: float = 0.0
    #: Counts down after taking a hit, driving the damage flash.
    hit_timer: float = 0.0

    mothership_active: bool = False
    shop_visible: bool = False
    #: Bosses destroyed this game. Each subsequent one is tougher, which is
    #: the only difficulty curve a game with no levels and no ending has.
    #: Survives losing a life; only a new game resets it.
    bosses_beaten: int = 0

    #: Set when the player asks to leave; unwinds every loop.
    quitting: bool = False

    @property
    def max_shots(self) -> int:
        """Cap on bolts in flight.

        The original used this as a hidden throttle: MAX_SHOTS was always
        below the number of bolts actually wanted airborne, so buying "extra
        shots" to double it was really buying a faster rate of fire.  Now that
        fire rate is its own upgrade, the cap is set generously so it never
        silently throttles anything.
        """
        return BASE_SHOTS * 4 * self.shot_tier

    @property
    def bolts_per_volley(self) -> int:
        return self.shot_tier

    def damage(self) -> None:
        """Take one hit.

        The original decremented ``shields`` unguarded and looped on
        ``while (shields != 0)``, so two hits in one frame could drive it to
        -1 and hang the game with an unkillable player.  Clamping at zero
        fixes that.
        """
        if not self.invincible:
            self.shields = max(0, self.shields - 1)
            self.hit_timer = balance.HIT_FLASH_SECONDS

    def kill(self) -> None:
        """Instant death, ignoring shields (the mothership's tracking shot)."""
        self.shields = 0

    @property
    def dead(self) -> bool:
        return self.shields <= 0

    def grant_invincibility(self, seconds: float | None = None) -> None:
        """Turn invincibility on, for a while or for good.

        ``math.inf`` never runs out, which is what the debug cheat wants from
        it.  The power-up passes nothing and gets the timed version.
        """
        self.invincible = True
        self.invincible_timer = (
            config.INVINCIBLE_SECONDS if seconds is None else seconds
        )

    def tick_timers(self, delta: float) -> None:
        """Advance the invincibility and damage-flash countdowns."""
        self.hit_timer = max(0.0, self.hit_timer - delta)
        if not self.invincible:
            return
        self.invincible_timer -= delta
        if self.invincible_timer <= 0.0:
            self.invincible = False
            self.invincible_timer = 0.0

    @property
    def flashing(self) -> bool:
        """True while the ship should render its damage flash."""
        return self.hit_timer > 0.0

    def upgrade_weapon(self) -> None:
        self.curr_weapon = min(MAX_TIER, self.curr_weapon + 1)

    def upgrade_shot(self) -> None:
        """Step single -> double -> triple, as PWR_SHOT did."""
        self.shot_tier = min(MAX_TIER, self.shot_tier + 1)

    def upgrade_fire_rate(self) -> None:
        self.fire_tier = min(MAX_TIER, self.fire_tier + 1)

    def refill_shields(self) -> None:
        self.shields = self.max_shields

    def reset_for_new_level(self) -> None:
        """Clear the encounter state a finished level leaves behind.

        Shields are deliberately untouched.  The shop's cheapest shelf sells a
        refill and it is also the most likely power-up drop; handing one out
        free at every level change would make both worthless.
        """
        self.kills = 0
        self.invincible = False
        self.invincible_timer = 0.0
        self.mothership_active = False
        self.shop_visible = False

    def reset_for_new_life(self) -> None:
        """Restore the loadout the player starts a life with.

        A new life is a new level plus full shields; losing a ship is what
        earns the refill that finishing a level does not.

        The original wiped score and money here too.  With a real lives
        system that would be punitive, so progress carries over and only the
        combat state resets.
        """
        self.reset_for_new_level()
        self.shields = self.max_shields

    def reset_for_new_game(self) -> None:
        self.score = 0
        self.money = 0
        self.lives = config.STARTING_LIVES
        self.max_shields = config.STARTING_MAX_SHIELDS
        self.level = 1
        self.curr_weapon = 1
        self.shot_tier = 1
        self.fire_tier = 1
        self.bosses_beaten = 0
        self.reset_for_new_life()
