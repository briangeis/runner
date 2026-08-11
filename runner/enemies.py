"""Enemies, their projectiles and the power-ups they leave behind.

Ports Get_Enemy_Dir and Update_Enemy from the original, plus its handling
of the projectiles enemies fire.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto

import pygame

from . import balance, config
from .assets import load_sprite
from .shots import EnemyShot
from .state import GameState

COLLISION_INSET = 4

#: Tint added to a sprite that has been hit but not destroyed.  Shared with
#: the player's damage flash so the cue reads the same in both directions.
HIT_FLASH_TINT = (160, 0, 0)


class EnemyState(Enum):
    LIVE = auto()
    DYING = auto()  # playing the explosion animation
    POWER = auto()  # became a collectable power-up
    DEAD = auto()  # slot free for respawn


class PowerUp(Enum):
    """The PWR_* constants from the original, plus one addition."""

    SHIELD = 0
    WEAPON = 1
    SHOT = 2
    INVINCIBLE = 3
    POINTS = 4
    MONEY = 5
    FIRE_RATE = 6
    #: Not in the original. A single weighted slot that resolves on pickup to
    #: something the player can actually use, so a scarce drop is never wasted
    #: on something already maxed out.
    BENEFIT = 7
    #: Also new: the shop sells a spare ship, so drops can offer one too.
    EXTRA_SHIP = 8


def benefit_options(state: GameState) -> list[tuple[PowerUp, int]]:
    """What a BENEFIT drop could usefully be, with each one's shop price.

    Drop odds are derived from those prices, so the cheap things the shop
    sells are the common drops and the expensive ones are rare.  A shield
    refill is always on the list, including at full health, so it stays the
    most likely outcome rather than silently dropping out of the pool.
    """
    options: list[tuple[PowerUp, int]] = [
        (PowerUp.SHIELD, config.PRICE_REPLENISH_SHIELDS),
        (PowerUp.INVINCIBLE, config.VALUE_INVINCIBILITY),
        (PowerUp.EXTRA_SHIP, config.PRICE_EXTRA_SHIP),
    ]
    # An upgrade is offered at the price of the tier the player would buy
    # next, so late tiers are correspondingly rarer than early ones.
    if state.curr_weapon < 3:
        options.append((PowerUp.WEAPON,
                        config.PRICE_WEAPON_2 if state.curr_weapon < 2
                        else config.PRICE_WEAPON_3))
    if state.shot_tier < 3:
        options.append((PowerUp.SHOT,
                        config.PRICE_DOUBLE_SHOT if state.shot_tier < 2
                        else config.PRICE_TRIPLE_SHOT))
    if state.fire_tier < 3:
        options.append((PowerUp.FIRE_RATE,
                        config.PRICE_FIRE_RATE_2 if state.fire_tier < 2
                        else config.PRICE_FIRE_RATE_3))
    return options


def resolve_benefit(state: GameState) -> PowerUp:
    """Pick a BENEFIT, weighting cheap things as more likely than dear ones."""
    options = benefit_options(state)
    weights = [1.0 / price for _, price in options]
    return random.choices([power for power, _ in options], weights=weights)[0]


@dataclass(frozen=True)
class EnemyType:
    """Per-type characteristics, from the original's enm_size table."""

    index: int
    frame_count: int
    shoots: bool
    #: Types 0 and 2 are the "drifters" that enter from any screen edge.
    drifter: bool

    @property
    def sprite_name(self) -> str:
        return f"enemy_{self.index}"


ENEMY_TYPES = {
    0: EnemyType(0, frame_count=3, shoots=False, drifter=True),
    1: EnemyType(1, frame_count=4, shoots=False, drifter=False),
    2: EnemyType(2, frame_count=3, shoots=False, drifter=True),
    3: EnemyType(3, frame_count=4, shoots=True, drifter=False),
    4: EnemyType(4, frame_count=4, shoots=True, drifter=False),
}

#: Spawn weighting from the rand() % 100 ladder in Get_Enemy_Dir.
_SPAWN_TABLE = [(30, 0), (55, 2), (70, 1), (85, 3), (100, 4)]


def _roll_drop() -> PowerUp:
    """Pick what a power-up turns out to be, per the drop weights.

    The original hardcoded a rand() % 14 ladder; the weights live in
    balance.py so the mix can be tuned.
    """
    weights = balance.DROP_WEIGHTS
    names = list(weights)
    return PowerUp[random.choices(names, weights=[weights[n] for n in names])[0]]


#: Which sprite represents each outcome.  The original had only three orbs, so
#: everything that is not points or money shares the third.
_DROP_SPRITES = {
    PowerUp.POINTS: "powerup_points",
    PowerUp.MONEY: "powerup_money",
}
_DEFAULT_DROP_SPRITE = "powerup_other"

POWERUP_FALL_SPEED = config.POWERUP_FALL_SPEED


def _pick_type(mothership_active: bool) -> EnemyType:
    if mothership_active:
        # Only the small drifters appear during the boss fight.
        return ENEMY_TYPES[random.choice((0, 2))]
    roll = random.randrange(100)
    for threshold, index in _SPAWN_TABLE:
        if roll < threshold:
            return ENEMY_TYPES[index]
    return ENEMY_TYPES[4]


class Enemy:
    """One enemy slot, which may also be holding an explosion or a power-up."""

    def __init__(self) -> None:
        self.state = EnemyState.DEAD
        self.sheet = load_sprite("enemy_0")
        self.type = ENEMY_TYPES[0]
        self.x = 0.0
        self.y = 0.0
        self.dx = 0.0
        self.dy = 0.0
        self.frame = 0
        self.frame_count = 1
        self.power: PowerUp | None = None
        self.health = 1
        self.flash_timer = 0.0
        #: Seconds until this enemy's next bolt, if its type shoots at all.
        self._next_shot = 0.0
        #: Id of the last volley to damage this target, so a multi-bolt volley
        #: can only score once against it.
        self.last_volley = -1
        #: Level this enemy spawned on, which scales asteroid pressure.
        self.level = 1
        self._timer = 0.0

    @staticmethod
    def _roll_shot_gap(first: bool = False) -> float:
        """Seconds until this enemy fires again.

        The first gap after spawning starts from zero rather than from the
        range's floor, so a screen that has just refilled does not go quiet
        for the same minimum all at once.
        """
        low, high = balance.ENEMY_VOLLEY_INTERVAL
        return random.uniform(0.0 if first else low, high)

    def take_hit(self, damage: int) -> bool:
        """Absorb one bolt. Returns True if this destroyed the enemy.

        Damage is the player's weapon tier, so upgrading a weapon shortens
        every fight rather than only the boss's.
        """
        self.health -= damage
        if self.health <= 0:
            return True
        self.flash_timer = balance.ENEMY_HIT_FLASH_SECONDS
        return False

    # -- geometry ---------------------------------------------------------

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x), int(self.y), self.sheet.width, self.sheet.height
        )

    @property
    def hitbox(self) -> pygame.Rect:
        return self.rect.inflate(-COLLISION_INSET * 2, -COLLISION_INSET * 2)

    # -- spawning ---------------------------------------------------------

    def spawn(
        self,
        mothership_active: bool,
        others: "list[Enemy] | None" = None,
        level: int = 1,
    ) -> None:
        """Place a fresh enemy at a screen edge. Port of Get_Enemy_Dir.

        When ``others`` is supplied, the placement is attempted repeatedly
        until it lands clear of every live enemy.  The original never checked,
        so roughly one spawn in ten appeared on top of another ship.
        """
        self.level = level
        tries = balance.SPAWN_CLEARANCE_TRIES if others else 0
        for _ in range(max(1, tries + 1)):
            self._place(mothership_active)
            if not tries or self._is_clear(others or []):
                return

    @staticmethod
    def _bottom_entry_x(span_x: int, width: int) -> int:
        """Column for an asteroid rising from below.

        Play funnels the ship to the center-bottom, so a rock entering there
        is unreactable; it was the single largest cause of deaths. Keeping
        the outer margins live preserves what asteroids are actually for,
        which is making the screen edges uncomfortable.
        """
        safe = balance.ASTEROID_BOTTOM_SAFE_FRACTION
        if safe <= 0.0:
            return random.randrange(span_x)

        margin = int(config.SCREEN_WIDTH * (1.0 - safe) / 2)
        left_max = max(1, margin - width)
        right_min = min(span_x - 1, config.SCREEN_WIDTH - margin)
        if right_min <= left_max:
            return random.randrange(span_x)
        if random.random() < 0.5:
            return random.randrange(left_max)
        return random.randrange(right_min, span_x)

    def _is_clear(self, others: "list[Enemy]") -> bool:
        box = self.rect
        return not any(
            other is not self
            and other.state in (EnemyState.LIVE, EnemyState.POWER)
            and box.colliderect(other.rect)
            for other in others
        )

    def _place(self, mothership_active: bool) -> None:
        self.type = _pick_type(mothership_active)
        self.sheet = load_sprite(self.type.sprite_name)
        self.frame_count = self.type.frame_count
        self.frame = 0
        self._timer = 0.0
        self.power = None
        self.health = balance.enemy_health(self.type.index)
        self.flash_timer = 0.0
        self._next_shot = self._roll_shot_gap(first=True)
        self.state = EnemyState.LIVE

        width, height = self.sheet.width, self.sheet.height

        right_edge = config.SCREEN_WIDTH - 1
        bottom_edge = config.SCREEN_HEIGHT - 1

        # The original picked the sprite's top-left corner from the whole
        # 0-319 / 0-199 range, ignoring its size, so an enemy entering along
        # an edge could be almost entirely off screen, most visible on the
        # 52px-wide type 1 dropping in from the top.
        span_x = max(1, config.SCREEN_WIDTH - width)
        span_y = max(1, config.SCREEN_HEIGHT - height)

        # Speed range for this type.  The original used one range for every
        # type, so a 16x10 asteroid drifted exactly like a 52x26 gunship.
        low, high = balance.enemy_speed_range(self.type.index)
        if self.type.drifter:
            # Asteroids are the clock on a level: they get faster as the
            # levels climb, so a fight cannot be drawn out indefinitely.
            pressure = balance.level_pressure(self.level)
            low, high = low * pressure, high * pressure

        def fast() -> float:
            """A speed in this type's range, always non-zero."""
            return random.uniform(low, high)

        def drift() -> float:
            """A cross-axis component, which may be zero (as the original's
            rand() % 4 - 2 + 1 could be), giving straight-line travel."""
            return random.uniform(-low, high)

        if self.type.drifter:
            edge = random.randrange(4)
            if edge == 0:  # from the left
                self.x, self.y = 1 - width, random.randrange(span_y)
                dx, dy = fast(), drift()
            elif edge == 1:  # from the right
                self.x, self.y = right_edge, random.randrange(span_y)
                dx, dy = -fast(), drift()
            elif edge == 2:  # from the top
                self.x, self.y = random.randrange(span_x), 1 - height
                dx, dy = drift(), fast()
            else:  # from the bottom
                self.x = self._bottom_entry_x(span_x, width)
                self.y = bottom_edge
                dx, dy = drift(), -fast()
        elif self.type.index == 1:
            self.x, self.y = random.randrange(span_x), 1 - height
            dx, dy = 0.0, fast()
        elif self.type.index == 3:
            # Enters from the top and angles back toward screen center.
            self.x, self.y = random.randrange(span_x), 1 - height
            dy = fast()
            dx = dy if self.x < config.SCREEN_WIDTH // 2 else -dy
        else:  # type 4, the bomber running across enemy territory
            dx = fast()
            if random.random() < 0.5:
                self.x = float(1 - width)
            else:
                self.x, dx = float(right_edge), -dx
            # "Fire up, they fire down" makes the top of the screen enemy
            # territory and the bottom the player's. The original let the
            # bomber run to y=136 of 200, deep into the player's half; it now
            # stays below the HUD and clear of the midpoint.
            top = max(
                config.HUD_HEIGHT,
                int(config.SCREEN_HEIGHT * balance.BOMBER_BAND_TOP),
            )
            floor = int(config.SCREEN_HEIGHT * balance.BOMBER_BAND_BOTTOM) - height
            self.y = float(random.randrange(top, max(top + 1, floor)))
            dy = 0.0

        self.dx = config.per_tick(dx)
        self.dy = config.per_tick(dy)

    # -- update -----------------------------------------------------------

    def update(self, delta: float, state: GameState) -> list[EnemyShot]:
        """Advance one frame. Returns any bolts this enemy fired."""
        fired: list[EnemyShot] = []
        self.flash_timer = max(0.0, self.flash_timer - delta)

        if self.state in (EnemyState.LIVE, EnemyState.POWER):
            self.x += self.dx * delta
            self.y += self.dy * delta

            if self.state is EnemyState.LIVE and self.type.shoots:
                self._next_shot -= delta
                if self._next_shot <= 0.0:
                    self._next_shot = self._roll_shot_gap()
                    fired.append(
                        EnemyShot(
                            self.x + self.sheet.width / 2,
                            self.y + self.sheet.height - 3,
                            self.type.index - 2,
                        )
                    )

            if (
                self.x < 1 - self.sheet.width
                or self.x > config.SCREEN_WIDTH - 2
                or self.y < 1 - self.sheet.height
                or self.y > config.SCREEN_HEIGHT - 2
            ):
                self.state = EnemyState.DEAD

        self._advance_animation(delta, state)
        return fired

    def _advance_animation(self, delta: float, state: GameState) -> None:
        if self.state is EnemyState.DEAD:
            return

        self._timer += delta
        while self._timer >= config.ANIMATION_FRAME_SECONDS:
            self._timer -= config.ANIMATION_FRAME_SECONDS
            self.frame += 1

            if self.state is EnemyState.DYING:
                # The explosion plays once, then the slot frees up.
                if self.frame >= len(self.sheet):
                    self.state = EnemyState.DEAD
                    # Only spaceships lure the mothership out. Asteroids are
                    # ambient pressure, not progress; shooting rocks should
                    # not summon her.
                    if not self.type.drifter:
                        state.kills += 1
                    self._maybe_drop()
                    return
            else:
                # A live enemy cycles only the frames its type uses; a
                # power-up orb cycles its whole strip.
                limit = (
                    self.frame_count
                    if self.state is EnemyState.LIVE
                    else len(self.sheet)
                )
                self.frame %= limit

    def _maybe_drop(self) -> None:
        """Leave a power-up behind, as the tail of Update_Enemy does.

        Only the larger enemy types drop; the two drifters never do.
        """
        if self.type.drifter or random.random() >= balance.POWERUP_DROP_CHANCE:
            return

        power = _roll_drop()
        sheet_name = _DROP_SPRITES.get(power, _DEFAULT_DROP_SPRITE)

        previous = self.rect
        self.sheet = load_sprite(sheet_name)
        self.power = power
        self.state = EnemyState.POWER
        self.frame = 0
        self._timer = 0.0
        self.x = previous.centerx - self.sheet.width / 2
        self.y = previous.centery - self.sheet.height / 2
        self.dx = 0.0
        self.dy = POWERUP_FALL_SPEED

    def explode(self) -> None:
        """Replace this enemy with an explosion, centered on where it was."""
        previous = self.rect
        self.sheet = load_sprite("explosion")
        self.state = EnemyState.DYING
        self.frame = 0
        self._timer = 0.0
        self.flash_timer = 0.0
        self.x = previous.centerx - self.sheet.width / 2
        self.y = previous.centery - self.sheet.height / 2

    def draw(self, surface: pygame.Surface) -> None:
        if self.state is EnemyState.DEAD:
            return
        frame = self.sheet.frame(self.frame)
        if self.flash_timer > 0.0:
            # Same red flash the player gets, so a hit that didn't kill is
            # visibly distinct from one that missed.
            frame = frame.copy()
            frame.fill(HIT_FLASH_TINT, special_flags=pygame.BLEND_RGB_ADD)
        surface.blit(frame, (int(self.x), int(self.y)))


def apply_powerup(state: GameState, power: PowerUp) -> PowerUp:
    """Grant a collected power-up. Port of the original's ENM_POWER branch.

    Returns what was actually granted, which differs from ``power`` only for
    the BENEFIT slot, which resolves here rather than at drop time so it can
    account for everything the player has picked up in the meantime.
    """

    if power is PowerUp.BENEFIT:
        # Worked out fresh on every pickup: what is the player eligible for
        # right now, and how do the shop's prices weight those options.
        power = resolve_benefit(state)

    if power is PowerUp.SHIELD:
        # A full refill, matching what the shop's cheapest shelf does.
        state.refill_shields()
    elif power is PowerUp.EXTRA_SHIP:
        state.lives += 1
    elif power is PowerUp.WEAPON:
        state.upgrade_weapon()
    elif power is PowerUp.SHOT:
        state.upgrade_shot()
    elif power is PowerUp.INVINCIBLE:
        state.grant_invincibility()
    elif power is PowerUp.POINTS:
        state.score += balance.POINTS_VALUE
    elif power is PowerUp.MONEY:
        state.money += balance.MONEY_VALUE
    elif power is PowerUp.FIRE_RATE:
        state.upgrade_fire_rate()

    return power


class Explosion:
    """A blast playing out at a fixed point, belonging to no enemy.

    An enemy becomes its own explosion when it dies, so most blasts live in
    an enemy slot and are handled there.  The mothership has no slot, and
    routing hers through the enemy pool meant suppressing the kill and the
    drop that finishing an enemy's explosion is supposed to award.  Owning
    the blast outright is easier than explaining that exception.
    """

    def __init__(self, over: pygame.Rect, sheet_name: str = "explosion") -> None:
        self.sheet = load_sprite(sheet_name)
        self.x = over.centerx - self.sheet.width / 2
        self.y = over.centery - self.sheet.height / 2
        self.frame = 0
        self.alive = True
        self._timer = 0.0

    def update(self, delta: float) -> None:
        self._timer += delta
        while self._timer >= config.ANIMATION_FRAME_SECONDS:
            self._timer -= config.ANIMATION_FRAME_SECONDS
            self.frame += 1
            if self.frame >= len(self.sheet):
                self.alive = False
                return

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.sheet.frame(self.frame), (int(self.x), int(self.y)))


class EnemyField:
    """The pool of enemy slots and the rules that refill it."""

    def __init__(self, size: int | None = None) -> None:
        if size is None:
            size = balance.MAX_ENEMIES
        self.enemies = [Enemy() for _ in range(size)]

    def __iter__(self) -> Iterator[Enemy]:
        return iter(self.enemies)

    @property
    def live_count(self) -> int:
        return sum(
            1 for enemy in self.enemies if enemy.state is not EnemyState.DEAD
        )

    def clear(self) -> None:
        for enemy in self.enemies:
            enemy.state = EnemyState.DEAD

    def explode_all(self, *, spaceships_only: bool = False) -> None:
        """Blow up what is on screen.

        A power-up is never taken.  It is already earned, and destroying one
        the player had not yet flown to was an unfixed bug from 1998; the
        original swept the whole array both when she arrived and when she
        died, so the fix has to cover both.

        ``spaceships_only`` is for her arrival, which asteroids are
        indifferent to.  Her death clears them as well, to hand the shop a
        quiet screen.
        """
        for enemy in self.enemies:
            if enemy.state in (EnemyState.DEAD, EnemyState.POWER):
                continue
            if spaceships_only and enemy.type.drifter:
                continue
            enemy.explode()

    def update(
        self, delta: float, state: GameState, *, live_cap: int | None = None
    ) -> list[EnemyShot]:
        """Update every slot, respawning dead ones. Returns bolts fired."""
        fired: list[EnemyShot] = []
        for enemy in self.enemies:
            fired.extend(enemy.update(delta, state))
        respawn_chance = (
            balance.RESPAWN_CHANCE
            * balance.level_pressure(state.level)
            * config.DOS_TICK_HZ
            * delta
        )
        for enemy in self.enemies:
            if enemy.state is not EnemyState.DEAD or state.shop_visible:
                continue
            if live_cap is not None and self.live_count >= live_cap:
                break
            if random.random() < respawn_chance:
                enemy.spawn(state.mothership_active, self.enemies, state.level)

        return fired

    def draw(self, surface: pygame.Surface) -> None:
        for enemy in self.enemies:
            enemy.draw(surface)
