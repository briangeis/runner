"""The title screen and the controls screen.

``show`` is a port of Intro in the original: the RUNNER splash art with the
credits banner scrolling across the bottom.  The original polled raw key state
with no debounce; this waits on key-down events instead.

``show_controls`` has no counterpart in the original, which shipped with no
in-game explanation of its keys at all.
"""

from __future__ import annotations

import pygame

from . import config, controls
from .assets import load_splash, load_sprite
from .display import Display
from .font import tech_font

BANNER_SPEED = config.per_tick(5)  # the banner scrolled 5px per tick
BANNER_MARGIN = 5

#: The prompt sits in the empty band between the bottom of the explosion in
#: the splash art (y=140, measured) and the top of the scrolling marquee.
EXPLOSION_BOTTOM = 140

#: Gap between the key and action columns on the controls screen.
COLUMN_GAP = 12

#: Vertical rhythm on the controls screen.  A heading sits HEADING_GAP above
#: the block it introduces and SECTION_GAP separates one section from the
#: next; the second has to be clearly larger than the first, or the two
#: groups read as one long list.
CONTROLS_LINE_LEADING = 5
HEADING_GAP = 8
SECTION_GAP = 20

#: The prompt is anchored near the bottom, as it is on the title screen, with
#: this much kept clear above it.
PROMPT_BOTTOM_MARGIN = 24
PROMPT_CLEARANCE = 18

#: The three collectables, and what each stands for.
LEGEND = [
    ("powerup_points", "POINTS"),
    ("powerup_money", "MONEY"),
    ("powerup_other", "UPGRADE"),
]


def _prompt_y(banner_height: int) -> int:
    """Center the prompt between the explosion and the marquee."""
    marquee_top = config.SCREEN_HEIGHT - banner_height - BANNER_MARGIN
    return (EXPLOSION_BOTTOM + marquee_top) // 2 - tech_font().glyph_height // 2


def show(display: Display, clock: pygame.time.Clock) -> bool:
    """Run the title screen. Returns False if the player chose to quit."""
    background = load_splash("intro")
    banner = load_sprite("scroll").frame(0)
    banner_x = float(config.SCREEN_WIDTH - 1)
    banner_y = config.SCREEN_HEIGHT - banner.get_height() - BANNER_MARGIN
    prompt_y = _prompt_y(banner.get_height())
    font = tech_font()
    elapsed = 0.0

    while True:
        delta = clock.tick(config.TARGET_FPS) / 1000.0
        elapsed += delta

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
            elif controls.dismisses(intent):
                return True

        banner_x -= BANNER_SPEED * delta
        if banner_x < -banner.get_width():
            banner_x = float(config.SCREEN_WIDTH - 1)

        display.draw_backdrop(background)
        display.buffer.blit(banner, (int(banner_x), banner_y))

        # Blink the prompt so it reads as interactive rather than decorative.
        if int(elapsed * 2) % 2 == 0:
            font.draw_centered(display.buffer, prompt_y, "PRESS ANY KEY")

        display.present()


def _draw_controls(surface: pygame.Surface, top: int) -> None:
    """Draw the key/action table as two columns.

    The gutter straddles the screen's center line, with keys right-aligned
    against it and actions left-aligned from it, so the table stays balanced
    however long an individual label is.
    """
    font = tech_font()
    line_height = font.glyph_height + CONTROLS_LINE_LEADING
    half_gap = COLUMN_GAP // 2
    center = config.SCREEN_WIDTH // 2

    for row, (key, action) in enumerate(controls.HELP_ROWS):
        y = top + row * line_height
        font.draw(surface, center - half_gap - font.width_of(key), y, key)
        font.draw(surface, center + half_gap, y, action)


def _controls_layout() -> tuple[int, int, int, int, int]:
    """Vertical positions for the controls screen, centered as one block.

    Returns the y of the CONTROLS heading, the table, the COLLECT heading,
    the legend and the prompt.  Measuring the block and centering what is
    left keeps both heading gaps equal and the section break visibly wider,
    whatever the table happens to contain.
    """
    font = tech_font()
    glyph = font.glyph_height
    line_height = glyph + CONTROLS_LINE_LEADING
    table = (len(controls.HELP_ROWS) - 1) * line_height + glyph
    legend = max(load_sprite(name).height for name, _ in LEGEND)

    block = glyph + HEADING_GAP + table + SECTION_GAP + glyph + HEADING_GAP + legend

    prompt_y = config.SCREEN_HEIGHT - PROMPT_BOTTOM_MARGIN
    region_top = config.HUD_HEIGHT
    region_bottom = prompt_y - PROMPT_CLEARANCE
    heading_y = region_top + (region_bottom - region_top - block) // 2

    table_y = heading_y + glyph + HEADING_GAP
    collect_y = table_y + table + SECTION_GAP
    legend_y = collect_y + glyph + HEADING_GAP
    return heading_y, table_y, collect_y, legend_y, prompt_y


def _draw_legend(surface: pygame.Surface, top: int, frame: int) -> None:
    """Show the three collectables so the player knows what to fly into."""
    font = tech_font()
    sprites = [(load_sprite(name), label) for name, label in LEGEND]

    gap = 10
    widths = [
        sheet.width + 3 + font.width_of(label) for sheet, label in sprites
    ]
    total = sum(widths) + gap * (len(sprites) - 1)
    x = (config.SCREEN_WIDTH - total) // 2

    for (sheet, label), width in zip(sprites, widths):
        surface.blit(sheet.frame(frame), (x, top))
        text_y = top + (sheet.height - font.glyph_height) // 2
        font.draw(surface, x + sheet.width + 3, text_y, label)
        x += width + gap


def show_controls(display: Display, clock: pygame.time.Clock) -> bool:
    """Controls and collectables. Waits for a key. False means quit."""
    font = tech_font()
    heading_y, table_y, collect_y, legend_y, prompt_y = _controls_layout()
    elapsed = 0.0
    frame = 0
    frame_timer = 0.0

    while True:
        delta = clock.tick(config.TARGET_FPS) / 1000.0
        elapsed += delta

        frame_timer += delta
        while frame_timer >= config.ANIMATION_FRAME_SECONDS:
            frame_timer -= config.ANIMATION_FRAME_SECONDS
            frame += 1

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
            elif controls.dismisses(intent):
                return True

        display.clear()
        font.draw_centered(display.buffer, heading_y, "CONTROLS")
        _draw_controls(display.buffer, table_y)

        font.draw_centered(display.buffer, collect_y, "COLLECT")
        _draw_legend(display.buffer, legend_y, frame)

        if int(elapsed * 2) % 2 == 0:
            font.draw_centered(display.buffer, prompt_y, "PRESS ANY KEY")
        display.present()
