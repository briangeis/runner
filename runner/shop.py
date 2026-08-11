"""The shop portal and its purchase menu.

Ports Shop_To_Center and Go_Shopping from the original.

Two fixes over the original: the menu advances on key-down events rather than
held key state (the original raced through the list on a held arrow), and the
selector is positioned from the same formula that lays out the text, instead
of the mismatched ``(loc-1)*15+12`` that left it a row off.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from . import config, controls, hud
from .assets import load_sprite
from .display import Display
from .font import TechFont, tech_font
from .starfield import Starfield
from .state import GameState

PORTAL_SPEED = config.PORTAL_DESCENT_SPEED  # shop.y += 2 per tick
#: The portal only opens if the player flies well inside it.
PORTAL_ENTRY_INSET = 20

LINE_HEIGHT = 13

#: The single spacing the panel is built from: border to orb, and orb to the
#: text it points at.  One constant for both, so the two cannot drift apart.
#:
#: Measured to the orb rather than the text, since the orb is wider at the
#: sides and taller than a glyph and would otherwise sit nearest the border.
PANEL_PAD = 9

#: The selector orb is the money sprite, a spinning dollar sign, and its cell
#: is mostly empty: across all eight frames the ink spans 7 of the 14 columns
#: and all 13 rows.  Aligning the cell would sit the visible sign 12px from one
#: border and 14 from the other, so the ink is aligned instead and these
#: margins are subtracted back out.
ORB_CELL_WIDTH = 14
ORB_CELL_HEIGHT = 13
ORB_INK_LEFT = 3
ORB_INK_RIGHT = 4
ORB_INK_WIDTH = ORB_CELL_WIDTH - ORB_INK_LEFT - ORB_INK_RIGHT

#: Room reserved either side of the text for the orbs: the sign's visible
#: width, plus the same air between sign and text as between sign and border.
ORB_GUTTER = ORB_INK_WIDTH + PANEL_PAD


@dataclass(frozen=True)
class MenuItem:
    """One shelf in the shop.

    ``track`` and ``tier`` mark the upgrade tracks, which run 1 to 3 and can
    be *skipped*: a player may bank money for tier 3 rather than settle for
    tier 2, which is the choice the shop exists to pose.  ``None`` marks the
    one-off purchases that sit outside that system.

    Names say what they buy, tier included, and the shield shelf names the
    capacity it grants rather than the step it is.
    """

    label: str
    price: int
    track: str | None = None
    tier: int = 0
    #: Set for shelves whose label depends on the ship's current state.
    dynamic: str | None = None

    def label_for(self, state: GameState) -> str:
        if self.dynamic == "shield_capacity":
            capacity = min(state.max_shields + 1, config.SHIELD_UPGRADE_CAP)
            return f"SHIELD CAPACITY {capacity}"
        return self.label

    def owned_by(self, state: GameState) -> bool:
        """True once this shelf has nothing left to sell."""
        if self.track is None:
            return False
        return _tier_of(state, self.track) >= self.tier

    def available_to(self, state: GameState) -> bool:
        if self.track is not None:
            return not self.owned_by(state)
        if self.label.startswith("REPLENISH"):
            return state.shields < state.max_shields
        if self.dynamic == "shield_capacity":
            return state.max_shields < config.SHIELD_UPGRADE_CAP
        return True


def panel_rect() -> pygame.Rect:
    """The menu panel, sized to roughly the screen's own proportions.

    Height follows from the number of shelves and width from height, so the
    panel echoes the 8:5 viewport rather than being an arbitrary box, and the
    padding places everything else without hand-tuned coordinates.

    The height counts the gaps between rows rather than a full row each, since
    the last row only inks a glyph's worth, plus the orb's overhang above the
    first row and below the last.
    """
    height = (
        (len(MENU_ITEMS) - 1) * LINE_HEIGHT
        + tech_font().glyph_height
        + _orb_rise() * 2
        + PANEL_PAD * 2
    )
    aspect = config.SCREEN_WIDTH / config.SCREEN_HEIGHT
    width = min(config.SCREEN_WIDTH - 8, round(height * aspect))
    return pygame.Rect(
        (config.SCREEN_WIDTH - width) // 2,
        (config.SCREEN_HEIGHT + config.HUD_HEIGHT - height) // 2,
        width,
        height,
    )


def _orb_rise() -> int:
    """How far the orb's ink stands above and below a row of text."""
    return (ORB_CELL_HEIGHT - tech_font().glyph_height) // 2


def _row_y(index: int) -> int:
    return panel_rect().top + PANEL_PAD + _orb_rise() + index * LINE_HEIGHT


def _tier_of(state: GameState, track: str) -> int:
    return {
        "WEAPON": state.curr_weapon,
        "SHOT": state.shot_tier,
        "FIRE RATE": state.fire_tier,
    }[track]


MENU_ITEMS = [
    MenuItem("REPLENISH SHIELDS", config.PRICE_REPLENISH_SHIELDS),
    MenuItem("FIRE RATE 2", config.PRICE_FIRE_RATE_2, "FIRE RATE", 2),
    MenuItem("FIRE RATE 3", config.PRICE_FIRE_RATE_3, "FIRE RATE", 3),
    MenuItem("DOUBLE SHOT", config.PRICE_DOUBLE_SHOT, "SHOT", 2),
    MenuItem("TRIPLE SHOT", config.PRICE_TRIPLE_SHOT, "SHOT", 3),
    MenuItem("WEAPON UPGRADE 2", config.PRICE_WEAPON_2, "WEAPON", 2),
    MenuItem("WEAPON UPGRADE 3", config.PRICE_WEAPON_3, "WEAPON", 3),
    MenuItem(
        "SHIELD CAPACITY",
        config.PRICE_SHIELD_UPGRADE,
        dynamic="shield_capacity",
    ),
    MenuItem("EXTRA SHIP", config.PRICE_EXTRA_SHIP),
    MenuItem("EXIT SHOP", 0),
]
EXIT_INDEX = len(MENU_ITEMS) - 1


def tier_label(track: str, tier: int) -> str:
    """The shop's own name for a track's tier.

    Drops announce what they granted using this, so a power-up and the shelf
    that sells the same thing never call it two different names.
    """
    for item in MENU_ITEMS:
        if item.track == track and item.tier == tier:
            return item.label
    return f"{track} {tier}"


class Portal:
    """The shop entrance that drifts down to screen center after a boss."""

    def __init__(self) -> None:
        self.sheet = load_sprite("shop")
        self.x = float((config.SCREEN_WIDTH - 1 - self.sheet.width) // 2)
        self.y = float(1 - self.sheet.height)
        self.frame = 0
        self._timer = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x), int(self.y), self.sheet.width, self.sheet.height
        )

    @property
    def resting_y(self) -> float:
        return float((config.SCREEN_HEIGHT - self.sheet.height) // 2)

    def update(self, delta: float) -> None:
        if self.y < self.resting_y:
            self.y = min(self.resting_y, self.y + PORTAL_SPEED * delta)

        self._timer += delta
        while self._timer >= config.ANIMATION_FRAME_SECONDS:
            self._timer -= config.ANIMATION_FRAME_SECONDS
            self.frame = (self.frame + 1) % len(self.sheet)

    def accepts(self, player_rect: pygame.Rect) -> bool:
        """True once the player has flown far enough into a settled portal."""
        if self.y < self.resting_y:
            return False
        inset = self.rect.inflate(-PORTAL_ENTRY_INSET * 2, -PORTAL_ENTRY_INSET * 2)
        return inset.colliderect(player_rect)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.sheet.frame(self.frame), (int(self.x), int(self.y)))


def _purchase(state: GameState, index: int) -> bool:
    """Attempt a purchase. Returns True if money changed hands."""
    item = MENU_ITEMS[index]
    if index == EXIT_INDEX:
        return False
    if state.money < item.price or not item.available_to(state):
        return False

    if item.track == "WEAPON":
        # Tiers may be skipped, so the purchase sets the tier outright rather
        # than stepping toward it.
        state.curr_weapon = item.tier
    elif item.track == "SHOT":
        state.shot_tier = item.tier
    elif item.track == "FIRE RATE":
        state.fire_tier = item.tier
    elif item.label.startswith("REPLENISH"):
        state.refill_shields()
    elif item.label.startswith("SHIELD"):
        state.max_shields += 1
        # The original raised the ceiling without filling it, so paying for
        # this appeared to do nothing at all until the next refill.
        state.refill_shields()
    elif item.label.startswith("EXTRA SHIP"):
        state.lives += 1
    else:
        return False

    state.money -= item.price
    return True


#: How opaque the panel is. Enough to keep dimmed entries legible without
#: hiding the stars behind it.
PANEL_ALPHA = 185


def _draw_panel(surface: pygame.Surface) -> None:
    """Darken the area behind the menu so dimmed shelves stay readable."""
    rect = panel_rect()
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((6, 10, 22, PANEL_ALPHA))
    surface.blit(panel, rect.topleft)
    pygame.draw.rect(surface, (40, 70, 110), rect, 1)


#: Color for a shelf with nothing left to sell.
OWNED_TINT = (70, 90, 70)
#: Color for a shelf the player cannot currently afford.
UNAFFORDABLE_TINT = (95, 95, 95)


def _draw_menu(
    surface: pygame.Surface, state: GameState, font: TechFont
) -> None:
    """Draw the shelves by name, hiding the price of anything already spent.

    The original listed a fixed price against every line whether or not it
    could still be bought, so a maxed-out track looked purchasable.  Names
    alone are deliberate: a tier meter would imply a progression the player is
    meant to climb, when the point is that tiers can be skipped and the order
    is theirs to choose.
    """
    rect = panel_rect()
    left = rect.left + PANEL_PAD + ORB_GUTTER
    right = rect.right - PANEL_PAD - ORB_GUTTER

    for row, item in enumerate(MENU_ITEMS):
        y = _row_y(row)
        owned = item.owned_by(state)
        available = item.available_to(state)
        affordable = state.money >= item.price

        if owned or not available:
            color = OWNED_TINT
        elif not affordable:
            color = UNAFFORDABLE_TINT
        else:
            color = None  # the font's own color

        label = item.label_for(state)
        if not item.price:
            # The exit sits on its own, centered, rather than pretending to be
            # a shelf with an invisible price.
            center = left + (right - left - font.width_of(label)) // 2
            _draw_tinted(surface, font, center, y, label, color)
            continue

        _draw_tinted(surface, font, left, y, label, color)
        # A shelf with nothing left to sell shows no price at all.  OWNED is a
        # track the player has finished; MAX is a shelf with nothing to give
        # right now, meaning shields already full or capacity at its ceiling.
        if owned:
            text = "OWNED"
        elif not available:
            text = "MAX"
        else:
            text = str(item.price)
        _draw_tinted(surface, font, right - font.width_of(text), y, text, color)


def _draw_tinted(
    surface: pygame.Surface,
    font: TechFont,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int] | None,
) -> None:
    """Draw text, optionally recolored to mark it unavailable."""
    if color is None:
        font.draw(surface, x, y, text)
        return
    patch = pygame.Surface(
        (font.width_of(text) + 1, font.glyph_height), pygame.SRCALPHA
    )
    font.draw(patch, 0, 0, text)
    patch.fill(color, special_flags=pygame.BLEND_RGB_MULT)
    surface.blit(patch, (x, y))


def run(
    display: Display,
    clock: pygame.time.Clock,
    state: GameState,
    starfield: Starfield,
) -> bool:
    """Show the purchase menu. Returns False if the player quit the game.

    The menu sits on the moving starfield rather than on the placeholder
    backdrop the original used, whose palette matched nothing else in the
    game. The shop was always meant to appear over the stars, and keeping
    them running makes it the same sky the next level opens on.  A
    dark panel sits behind the text, since dimmed entries would otherwise be
    unreadable against black.
    """
    selector = load_sprite("powerup_money")
    font = tech_font()

    index = 0
    selector_frame = 0
    timer = 0.0

    while True:
        delta = clock.tick(config.TARGET_FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                state.quitting = True
                return False
            if event.type == pygame.VIDEORESIZE:
                display.handle_resize(event.size)
            controls.handle_device_event(event)

            intent = controls.intent_of(event)
            if intent is controls.Intent.QUIT:
                state.quitting = True
                return False
            if intent is controls.Intent.FULLSCREEN:
                display.toggle_fullscreen()
            elif intent is controls.Intent.DOWN:
                index = (index + 1) % len(MENU_ITEMS)
            elif intent is controls.Intent.UP:
                index = (index - 1) % len(MENU_ITEMS)
            elif intent is controls.Intent.CONFIRM:
                if index == EXIT_INDEX:
                    return True
                _purchase(state, index)

        timer += delta
        while timer >= config.ANIMATION_FRAME_SECONDS:
            timer -= config.ANIMATION_FRAME_SECONDS
            selector_frame = (selector_frame + 1) % len(selector)

        starfield.update(delta)
        display.clear()
        starfield.draw(display.buffer)
        _draw_panel(display.buffer)
        _draw_menu(display.buffer, state, font)

        # Selector orbs bracket the highlighted row.  Both are placed by their
        # ink rather than their cell, so the visible sign sits PANEL_PAD from
        # its border like everything else in the panel.
        rect = panel_rect()
        orb_y = _row_y(index) - _orb_rise()
        frame = selector.frame(selector_frame)
        display.buffer.blit(frame, (rect.left + PANEL_PAD - ORB_INK_LEFT, orb_y))
        display.buffer.blit(
            frame,
            (rect.right - PANEL_PAD - ORB_CELL_WIDTH + ORB_INK_RIGHT, orb_y),
        )

        hud.draw(display.buffer, state)
        display.present()
