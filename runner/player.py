"""The runner itself.

A port of Move_Runner in the original: movement, screen clamping, the
four-way banking animation and firing.
"""

from __future__ import annotations

import math

import pygame

from . import balance, config, controls
from .assets import load_sprite
from .enemies import HIT_FLASH_TINT
from .shots import PlayerShot, volley
from .state import GameState

#: Collision boxes are inset before testing.  The original's comparisons
#: carried a hardcoded +4/-4 fudge on every edge, which made contact forgiving.
COLLISION_INSET = 4

#: Scale applied to each axis when moving diagonally, so that the resulting
#: speed matches straight-line speed.
_DIAGONAL = math.sqrt(0.5)

#: Blink rate of the damage flash. Faster than the invincibility blink, so
#: the two read differently at a glance, and red rather than grey.
HIT_BLINK_PERIOD = 0.06

#: Blink rate while invincible, and the quicker one it changes to as the
#: timer runs down.  That change is the only warning in the play field that
#: invincibility is about to end; without it the status bar is the only tell.
INVINCIBLE_BLINK_PERIOD = 0.16
INVINCIBLE_WARNING_SECONDS = 3.0
INVINCIBLE_WARNING_PERIOD = 0.07


class Player:
    """The player's ship."""

    def __init__(self) -> None:
        self.sheet = load_sprite("runner")
        self.x = float((config.SCREEN_WIDTH - self.sheet.width) // 2)
        self.y = float((config.SCREEN_HEIGHT - self.sheet.height) // 2)
        self.frame = 0
        self._idle_step = 0
        self._bank_step = 0
        self._anim_timer = 0.0
        self._cooldown = 0.0

    # -- geometry ---------------------------------------------------------

    @property
    def width(self) -> int:
        return self.sheet.width

    @property
    def height(self) -> int:
        return self.sheet.height

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    @property
    def hitbox(self) -> pygame.Rect:
        return self.rect.inflate(-COLLISION_INSET * 2, -COLLISION_INSET * 2)

    @property
    def nose(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y

    # -- update -----------------------------------------------------------

    def update(
        self, state: GameState, input_state: controls.InputState, delta: float
    ) -> list[PlayerShot]:
        """Move, animate and fire. Returns any bolts launched this frame."""
        step_x, step_y = input_state.move_x, input_state.move_y

        if step_x and step_y:
            # The original summed both axes, so diagonal movement was 41%
            # faster than straight and 45 degrees was the quickest route
            # anywhere.  Scaling makes speed independent of direction.
            step_x *= _DIAGONAL
            step_y *= _DIAGONAL

        speed = balance.PLAYER_SPEED_PX_S
        self.x += step_x * speed * delta
        self.y += step_y * speed * delta
        self._clamp()
        self._animate(input_state, delta)

        self._cooldown = max(0.0, self._cooldown - delta)
        if input_state.fire and self._cooldown == 0.0:
            self._cooldown = balance.cooldown_for(state.fire_tier)
            return volley(state, *self.nose, self.width)
        return []

    def _clamp(self) -> None:
        self.x = max(0.0, min(self.x, config.SCREEN_WIDTH - self.width))
        self.y = max(0.0, min(self.y, config.SCREEN_HEIGHT - self.height))

    def _animate(self, input_state: controls.InputState, delta: float) -> None:
        self._anim_timer += delta
        while self._anim_timer >= config.ANIMATION_FRAME_SECONDS:
            self._anim_timer -= config.ANIMATION_FRAME_SECONDS
            self._idle_step = (self._idle_step + 1) % 8
            self._bank_step = (self._bank_step + 1) % 4

        if input_state.move_x < 0:
            group, step = self.sheet.group("bank_left"), self._bank_step
        elif input_state.move_x > 0:
            group, step = self.sheet.group("bank_right"), self._bank_step
        elif input_state.up:
            group, step = self.sheet.group("climb"), self._bank_step
        else:
            group, step = self.sheet.group("idle"), self._idle_step

        self.frame = group[step % len(group)]

    def animate_idle(self, delta: float) -> None:
        """Advance the idle cycle without reading input (used by cutscenes)."""
        self._animate(controls.InputState(), delta)

    # -- drawing ----------------------------------------------------------

    def draw(self, surface: pygame.Surface, state: GameState) -> None:
        frame = self.sheet.frame(self.frame)

        if state.flashing and _blink(state.hit_timer, HIT_BLINK_PERIOD):
            # The original gave no feedback for taking a hit at all; the
            # only cue was the shield meter ticking down, which is at the top
            # of the screen and easy to miss mid-fight.
            frame = frame.copy()
            frame.fill(HIT_FLASH_TINT, special_flags=pygame.BLEND_RGB_ADD)
        elif state.invincible and _invincible_blink(state.invincible_timer):
            # The original swapped to a dedicated frame while invincible;
            # a blink reads more clearly at modern frame rates.
            frame = frame.copy()
            frame.fill((90, 90, 90), special_flags=pygame.BLEND_RGB_ADD)

        surface.blit(frame, (int(self.x), int(self.y)))


def _blink(timer: float, period: float) -> bool:
    return int(timer / period) % 2 == 0


def _invincible_blink(timer: float) -> bool:
    """Whether the invincibility tint shows this frame.

    The blink quickens over the last few seconds, so the player can see it
    running out without reading the status bar.  Cheat-granted invincibility
    never runs out, so it holds steady instead, which also makes the two
    tell each other apart.
    """
    if not math.isfinite(timer):
        return True
    period = (
        INVINCIBLE_WARNING_PERIOD
        if timer <= INVINCIBLE_WARNING_SECONDS
        else INVINCIBLE_BLINK_PERIOD
    )
    return int(timer / period) % 2 == 0
