"""The mothership boss.

A port of Mother_Ship in the original.  The boss enters from the top
right, bounces around the upper strip of the screen, fires paired bolts, and
periodically lines up an aimed shot that kills outright.

The original tested ``if (mpower == 0)`` after subtracting the weapon tier, so
collecting a weapon upgrade mid-fight could step the total straight past zero
and leave the boss permanently invulnerable.  This uses ``<= 0``.
"""

from __future__ import annotations

import random

import pygame

from . import balance, config
from .assets import load_sprite
from .enemies import COLLISION_INSET, HIT_FLASH_TINT
from .shots import EnemyShot, MothershipShot


class Mothership:
    """The boss ship."""

    def __init__(self, bosses_beaten: int = 0) -> None:
        self.sheet = load_sprite("mothership")
        self.x = float(config.SCREEN_WIDTH + self.sheet.width)
        self.y = float(-self.sheet.height)
        self.dx = -balance.BOSS_SPEED_X_PX_S
        self.dy = balance.BOSS_SPEED_Y_PX_S
        self.patrol_top = balance.BOSS_PATROL_TOP
        self.patrol_bottom = balance.BOSS_PATROL_BOTTOM
        self.max_power = balance.boss_health(bosses_beaten)
        self.power = self.max_power
        self.alive = True

        self.frame = 0
        self._timer = 0.0
        self._windup = 0.0
        self._quiet = balance.BOSS_FIRST_KILLSHOT_DELAY
        self._next_volley = self._roll_volley_gap()
        self.flash_timer = 0.0
        #: Id of the last volley to damage her; see Enemy.last_volley.
        self.last_volley = -1

    @staticmethod
    def _roll_volley_gap() -> float:
        return random.uniform(*balance.BOSS_VOLLEY_INTERVAL)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x), int(self.y), self.sheet.width, self.sheet.height
        )

    @property
    def hitbox(self) -> pygame.Rect:
        """Inset like every other ship, for the empty space around the hull.

        The original inset her 4px on three sides and 10 on the bottom, which
        is the side the player shoots from.  Measured against the artwork that
        is not empty space: her outer four rows carry 4 to 9 opaque pixels of
        47, but six rows up she is already 23 wide, so the deeper fudge was
        eating solid ship.
        """
        return self.rect.inflate(-COLLISION_INSET * 2, -COLLISION_INSET * 2)

    @property
    def winding_up(self) -> bool:
        return self._windup > 0.0

    def hit(self, weapon: int) -> bool:
        """Absorb one bolt. Returns True if this killed the boss."""
        self.power -= weapon
        if self.power <= 0:
            self.alive = False
            return True
        self.flash_timer = balance.ENEMY_HIT_FLASH_SECONDS
        return False

    def update(
        self, delta: float, player_rect: pygame.Rect
    ) -> tuple[list[EnemyShot], MothershipShot | None]:
        """Move and shoot. Returns paired bolts and any killshot released.

        She is the only thing in the game that knows about the bargain the
        rest of it runs on: she fires down, the player fires up. The moment
        the two ships overlap horizontally is the moment the player is lined
        up to shoot her, and equally the moment she is lined up to shoot back.
        She may take it: normal fire stops, she slows and chases to hold the
        line, the charge animation runs as a warning, and then she fires and
        returns to patrol needing to recharge.

        That shared instant is the whole dilemma. Going in for damage invites
        the chase; sitting still invites it too, because the patrol will cross
        the player eventually and there is nowhere to hide from it.
        """
        self.flash_timer = max(0.0, self.flash_timer - delta)
        self._quiet = max(0.0, self._quiet - delta)
        self._move(delta, player_rect if self.winding_up else None)

        bolts: list[EnemyShot] = []
        aimed: MothershipShot | None = None

        if self.winding_up:
            # Charging: no ordinary fire, just the tell.
            self._windup -= delta
            if self._windup <= 0.0:
                self._windup = 0.0
                self.frame = 0
                self._quiet = balance.BOSS_KILLSHOT_INTERVAL
                # Her ordinary bombing pauses too, for a shorter beat than the
                # killshot recharge. Dodging the killshot should buy a moment
                # to breathe, not drop the player straight back under fire.
                self._next_volley = max(
                    self._next_volley, balance.BOSS_RECOVERY_SECONDS
                )
                aimed = MothershipShot(
                    self.x + self.sheet.width / 2, self.y + self.sheet.height - 3
                )
            else:
                # Cycle the firing frames rather than stepping through them
                # once, so a long charge reads as building rather than stuck.
                self._animate(delta, "firing")
            return bolts, aimed

        self._animate(delta)
        bolts.extend(self._tick_ordinary_fire(delta))

        # The killshot is considered once when an overlap *begins*, not every
        # frame it lasts, so a player caught inside one is not rolled against
        # over and over.
        # Considered on a timer for as long as the player is in her column,
        # not once when they enter it. Rolling only on the way in let a player
        # park under her and be safe there, which is the opposite of what
        # sharing her column is supposed to mean.
        if self._provoked(player_rect) and self._quiet <= 0.0:
            if random.random() < balance.BOSS_KILLSHOT_CHANCE:
                self._windup = balance.BOSS_CHARGE_SECONDS
            else:
                self._quiet = balance.BOSS_KILLSHOT_INTERVAL

        return bolts, aimed

    def _tick_ordinary_fire(self, delta: float) -> list[EnemyShot]:
        """Her patrol bombing: a steady pace, neither clustered nor sparse.

        The original rolled a per-tick coin flip, which gives exponentially
        distributed gaps, a tenth under 0.08s and a tenth over 1.75s, so
        bolts arrived in bursts and then not at all.  Drawing the next gap from
        a bounded range keeps the pressure constant without being metronomic.
        """
        self._next_volley -= delta
        if self._next_volley > 0.0:
            return []
        self._next_volley = self._roll_volley_gap()
        return self._paired_bolts()

    def _move(self, delta: float, chasing: pygame.Rect | None = None) -> None:
        if chasing is None:
            self.x += self.dx * delta
            self.y += self.dy * delta
        else:
            # Slowed while charging, and closing on the player to line the
            # killshot up rather than firing wherever she happens to be.
            #
            # The step is capped at the distance left to cover, so she settles
            # onto the player rather than sliding past and correcting back.
            # Steering by flipping the sign of dx made her jitter in place
            # against a stationary target, and broke the patrol direction
            # she needs once the charge ends.
            scale = balance.BOSS_CHARGE_SPEED_SCALE
            reach = abs(self.dx) * scale * delta
            offset = chasing.centerx - (self.x + self.sheet.width / 2)
            self.x += max(-reach, min(reach, offset))
            self.y += self.dy * scale * delta

        if self.x < 0:
            self.x, self.dx = 0.0, -self.dx
        elif self.x > config.SCREEN_WIDTH - self.sheet.width:
            self.x = float(config.SCREEN_WIDTH - self.sheet.width)
            self.dx = -self.dx

        if self.y < self.patrol_top:
            self.y, self.dy = self.patrol_top, -self.dy
        elif self.y > self.patrol_bottom:
            self.y, self.dy = self.patrol_bottom, -self.dy

    def _animate(self, delta: float, group_name: str = "idle") -> None:
        """Advance within one frame group, wrapping inside it.

        Stepping within the group rather than across the whole strip is what
        keeps the charge cycling instead of running once and stopping. Entering
        from another group starts at that group's first frame.
        """
        group = self.sheet.group(group_name)
        self._timer += delta
        while self._timer >= config.ANIMATION_FRAME_SECONDS:
            self._timer -= config.ANIMATION_FRAME_SECONDS
            if self.frame in group:
                self.frame = group[(group.index(self.frame) + 1) % len(group)]
            else:
                self.frame = group[0]

    def _paired_bolts(self) -> list[EnemyShot]:
        center = self.x + self.sheet.width / 2
        base_y = self.y + self.sheet.height
        return [
            EnemyShot(center - 5, base_y, 2),
            EnemyShot(center + 5, base_y, 2),
        ]

    def _provoked(self, player_rect: pygame.Rect) -> bool:
        """Whether the player is lined up with her right now.

        Overlap, not proximity: the trigger is the two hulls sharing a column,
        which is exactly the position from which the player can hit her. For a
        47px boss and a 35px ship that happens within 41px.
        """
        box = self.rect
        return player_rect.right > box.left and player_rect.left < box.right

    def draw(self, surface: pygame.Surface) -> None:
        frame = self.sheet.frame(self.frame)
        if self.flash_timer > 0.0:
            frame = frame.copy()
            frame.fill(HIT_FLASH_TINT, special_flags=pygame.BLEND_RGB_ADD)
        surface.blit(frame, (int(self.x), int(self.y)))
