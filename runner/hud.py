"""The status bar.

A port of Update_Stats in the original.  Score and money are zero-padded
to six digits and the shield meter is a six-frame sprite.

The original also built a ``str_lives`` string, but it contained the literal
text ``"     SHIELDS: "`` and lives were never displayed, because the game only
ever granted one.  Now that lives work, they get a readout.
"""

from __future__ import annotations

import pygame

from . import config
from .assets import load_sprite
from .font import tech_font
from .state import GameState

TEXT_Y = 1

#: Gutter kept clear at each edge.  The original ran the score hard against
#: the left edge while leaving a gap on the right, so the bar looked shunted.
MARGIN = 4


def draw(surface: pygame.Surface, state: GameState) -> None:
    """Lay the status bar out across the full width with even spacing.

    Rather than one long pre-padded string, each field is measured and the
    slack is distributed between them, so the bar stays balanced whatever the
    shield meter is showing.
    """
    font = tech_font()
    bar = load_sprite("shield_bar")

    score = f"SCORE {state.score:06d}"
    money = f"MONEY {state.money:06d}"
    ships = f"SHIPS {state.lives}"
    shields_label = "SHIELDS"

    # The invincibility readout replaces the meter, but the slot keeps the
    # meter's width either way so the bar doesn't re-flow when it triggers.
    shields_width = font.width_of(shields_label) + 3 + bar.width
    invincible_label = "INVINCIBLE"

    widths = [
        font.width_of(score),
        font.width_of(money),
        shields_width,
        font.width_of(ships),
    ]
    slack = config.SCREEN_WIDTH - 2 * MARGIN - sum(widths)
    gap = max(2, slack // (len(widths) - 1))

    x = MARGIN
    font.draw(surface, x, TEXT_Y, score)
    x += widths[0] + gap

    font.draw(surface, x, TEXT_Y, money)
    x += widths[1] + gap

    font.draw(surface, x, TEXT_Y, shields_label)
    meter_x = x + font.width_of(shields_label) + 3
    if state.invincible:
        # Centered in the meter's slot, so the word occupies the same space the
        # bar does rather than hanging off its left edge.
        offset = (bar.width - font.width_of(invincible_label)) // 2
        font.draw(surface, meter_x + offset, TEXT_Y, invincible_label)
    elif state.shields > 0:
        frame = min(state.shields, config.SHIELD_UPGRADE_CAP) - 1
        surface.blit(bar.frame(frame), (meter_x, TEXT_Y))

    # Right-align the last field so it mirrors the left gutter exactly.
    font.draw(
        surface, config.SCREEN_WIDTH - MARGIN - widths[3], TEXT_Y, ships
    )
