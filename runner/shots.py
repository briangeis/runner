"""Projectiles.

Ports the original's shot spawning, ``Update_Shots`` and ``Update_Enm_Shots``.

The original preallocated fixed arrays, 18 player bolts and 6 enemy bolts,
and hunted for a free slot with a loop that tested its bound *after* indexing,
which let it write past the end of the enemy shot array.  Python lists remove
the whole class of problem; the caps that mattered for gameplay are enforced
explicitly instead.
"""

from __future__ import annotations

import pygame

from . import balance, config
from .assets import load_sprite
from .state import GameState


class Projectile:
    """Shared movement and animation for every kind of bolt."""

    sprite_name = ""

    def __init__(self, x: float, y: float, speed: float, frames: list[int]) -> None:
        self.sheet = load_sprite(self.sprite_name)
        self.x = x
        self.y = y
        self.speed = speed
        self._frames = frames
        self._phase = 0
        self._timer = 0.0
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x), int(self.y), self.sheet.width, self.sheet.height
        )

    def update(self, delta: float) -> None:
        self.y += self.speed * delta
        if self.y + self.sheet.height < 0 or self.y > config.SCREEN_HEIGHT:
            self.alive = False

        self._timer += delta
        while self._timer >= config.ANIMATION_FRAME_SECONDS:
            self._timer -= config.ANIMATION_FRAME_SECONDS
            self._phase = (self._phase + 1) % len(self._frames)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(
            self.sheet.frame(self._frames[self._phase]), (int(self.x), int(self.y))
        )


class PlayerShot(Projectile):
    """A bolt fired by the runner, traveling up the screen.

    Weapon tier selects a pair of alternating frames, exactly as the original's
    ``curr_frame = (curr_weapon - 1) * 2``.
    """

    sprite_name = "shot"

    def __init__(self, x: float, y: float, weapon: int, volley_id: int = 0) -> None:
        sheet = load_sprite(self.sprite_name)
        frames = sheet.group(f"weapon_{weapon}")
        super().__init__(
            x - sheet.width / 2,
            y - sheet.height,
            -balance.SHOT_SPEED_PX_S,
            frames,
        )
        self.weapon = weapon
        #: Bolts fired together share an id, so a target can be limited to one
        #: hit per volley however many of them land on it.
        self.volley_id = volley_id


class EnemyShot(Projectile):
    """A bolt fired by an enemy or the mothership, traveling down."""

    sprite_name = "enemy_shot"

    def __init__(self, x: float, y: float, frame: int) -> None:
        sheet = load_sprite(self.sprite_name)
        super().__init__(
            x - sheet.width / 2, y, balance.ENEMY_SHOT_SPEED_PX_S, [frame]
        )


class MothershipShot(Projectile):
    """The boss's killshot. Kills outright, regardless of shields.

    It falls straight, like everything else the enemies fire. The aiming
    happens beforehand: she breaks off patrol, slows, and chases the player to
    line it up. That chase is the threat, and the charge animation is the
    warning; the bolt itself is honest.
    """

    sprite_name = "mothership_shot"

    def __init__(self, x: float, y: float) -> None:
        sheet = load_sprite(self.sprite_name)
        super().__init__(
            x - sheet.width / 2,
            y,
            balance.BOSS_SHOT_SPEED_PX_S,
            [0, 1, 2],
        )


_volley_counter = 0


def volley(
    state: GameState, x: float, y: float, width: float
) -> list[PlayerShot]:
    """Build the bolts for one trigger pull.

    A single shot leaves the nose; a double leaves the wingtips; a triple adds
    one from the nose, slightly ahead.  Mirrors the original's spawn
    positions, but the wing bolts are pushed out by the tuned spread so the
    three lanes are meaningfully different.

    Bolts all travel straight up.  Angling them outward would let the player
    attack the mothership from beside her, outside the downward fire that is
    supposed to be the price of attacking at all.
    """
    global _volley_counter
    _volley_counter += 1

    weapon = state.curr_weapon
    count = state.bolts_per_volley

    if count == 1:
        return [PlayerShot(x, y, weapon, _volley_counter)]

    offset = max(width / 2, balance.VOLLEY_SPREAD)
    shots = [
        PlayerShot(x - offset, y, weapon, _volley_counter),
        PlayerShot(x + offset, y, weapon, _volley_counter),
    ]
    if count == 3:
        shots.append(PlayerShot(x, y - 4, weapon, _volley_counter))
    return shots
