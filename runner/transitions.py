"""Screen transitions.

Ports of Screen_Transition from the original's graphics library.  Those
manipulated the VGA hardware directly; since every color in the palette is a
plain RGB triple, the same effects come out of ordinary surface operations.
"""

from __future__ import annotations

import pygame

from . import config, controls
from .display import Display
from .starfield import Starfield

#: The original added 4 to each 6-bit palette component per tick for 20 ticks.
#: Scaled to 8-bit that is ~16 per tick, saturating well before the end.
_WHITEN_STEP_PER_TICK = 16
WHITEN_DURATION = config.ticks_to_seconds(20)


def _pump(display: Display) -> bool:
    """Service the event queue during a blocking transition.

    Returns False if the player closed the window, so callers can bail out
    instead of trapping them inside an animation.
    """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.VIDEORESIZE:
            display.handle_resize(event.size)
        controls.handle_device_event(event)

        intent = controls.intent_of(event)
        if intent is controls.Intent.QUIT:
            return False
        if intent is controls.Intent.FULLSCREEN:
            display.toggle_fullscreen()
    return True


def whiten(display: Display, clock: pygame.time.Clock) -> bool:
    """Wash the screen out to white. Used on death."""
    frozen = display.buffer.copy()
    elapsed = 0.0

    while elapsed < WHITEN_DURATION:
        delta = clock.tick(config.TARGET_FPS) / 1000.0
        elapsed += delta
        if not _pump(display):
            return False

        amount = min(255, int(_WHITEN_STEP_PER_TICK * config.DOS_TICK_HZ * elapsed))
        display.buffer.blit(frozen, (0, 0))
        display.buffer.fill(
            (amount, amount, amount), special_flags=pygame.BLEND_RGB_ADD
        )
        display.present()
    return True


def fade_sprites(
    display: Display,
    clock: pygame.time.Clock,
    starfield: Starfield,
    seconds: float = 0.7,
) -> bool:
    """Fade the ships out while the starfield keeps running.

    Entering the shop should feel like the sky staying put while the ship and
    the portal dissolve away; it is the same sky the next level opens on.
    The original cut to a full-screen black dissolve instead, which threw the
    continuity away.
    """
    frozen = display.buffer.copy()
    elapsed = 0.0

    while elapsed < seconds:
        delta = clock.tick(config.TARGET_FPS) / 1000.0
        elapsed += delta
        if not _pump(display):
            return False

        starfield.update(delta)
        display.clear()
        starfield.draw(display.buffer)

        # The captured frame, including its own stars, fades over the live
        # ones so the field never appears to stop.
        remaining = max(0, int(255 * (1.0 - elapsed / seconds)))
        frozen.set_alpha(remaining)
        display.buffer.blit(frozen, (0, 0))
        display.present()

    frozen.set_alpha(255)
    return True
