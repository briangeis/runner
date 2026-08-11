"""The scrolling starfield background.

A port of Update_Stars in the original.  Stars fall straight down at a
fixed per-star speed and are recycled at the top of the screen with a fresh
column and speed once they pass the bottom edge.

The original drew every star in the same white at 10-29 pixels per tick, so
they crossed the screen in well under a second and read as noise rather than
travel.  The port slows them and ties brightness to speed, which is what makes
a random-speed field read as depth: dim slow stars sit far away, bright fast
ones rush past close to the ship.
"""

from __future__ import annotations

import random

import pygame

from . import balance, config
from .assets import palette_color

#: Dimmest a distant star is drawn, as a fraction of the star color.
MIN_BRIGHTNESS = 0.35


class Starfield:
    """Single-pixel stars drifting down the screen."""

    def __init__(self, count: int | None = None) -> None:
        self.base_color = palette_color(config.STAR_COLOR_INDEX)
        self._min_speed = config.per_tick(balance.STAR_SPEED_MIN)
        self._max_speed = config.per_tick(balance.STAR_SPEED_MAX)

        if count is None:
            count = balance.STAR_COUNT
        self._x = [0.0] * count
        self._y = [0.0] * count
        self._speed = [0.0] * count
        self._color = [self.base_color] * count

        for index in range(count):
            self._x[index] = random.uniform(0, config.SCREEN_WIDTH)
            self._y[index] = random.uniform(0, config.SCREEN_HEIGHT)
            self._respeed(index)

    def _respeed(self, index: int) -> None:
        speed = random.uniform(self._min_speed, self._max_speed)
        self._speed[index] = speed
        self._color[index] = self._color_for(speed)

    def _color_for(self, speed: float) -> tuple[int, int, int]:
        """Faster stars are nearer, so they are drawn brighter.

        The original drew every star the same white, which is what stopped its
        random speeds reading as parallax at all.
        """
        span = self._max_speed - self._min_speed
        nearness = (speed - self._min_speed) / span if span else 1.0
        level = MIN_BRIGHTNESS + (1.0 - MIN_BRIGHTNESS) * nearness
        red, green, blue = self.base_color
        return int(red * level), int(green * level), int(blue * level)

    def _recycle(self, index: int) -> None:
        self._x[index] = random.uniform(0, config.SCREEN_WIDTH)
        self._y[index] = 0.0
        self._respeed(index)

    def update(self, delta: float) -> None:
        for index, speed in enumerate(self._speed):
            self._y[index] += speed * delta
            if self._y[index] > config.SCREEN_HEIGHT:
                self._recycle(index)

    def draw(self, surface: pygame.Surface) -> None:
        set_at = surface.set_at
        for x, y, color in zip(self._x, self._y, self._color):
            set_at((int(x), int(y)), color)
