"""The 4x7 "tech" font.

A port of Font_Engine_1 in the original.  The font holds 64 glyphs starting
at ASCII 32 (space), so it covers punctuation, digits and uppercase letters
only; lowercase input is upper-cased rather than dropped.
"""

from __future__ import annotations

from functools import lru_cache

import pygame

from .assets import ASSETS_DIR, AssetError, load_manifest


class TechFont:
    """Blits strings from the original bitmap font."""

    def __init__(self) -> None:
        entry = load_manifest()["font"]
        path = ASSETS_DIR / entry["file"]
        if not path.is_file():
            raise AssetError(
                f"font asset missing: {path}\n"
                "The installation looks incomplete; try unpacking it again."
            )
        strip = pygame.image.load(str(path)).convert_alpha()

        self.glyph_width: int = entry["glyph_width"]
        self.glyph_height: int = entry["glyph_height"]
        self.advance: int = entry["advance"]
        self._first = ord(entry["first_char"])
        self._glyphs = [
            strip.subsurface(
                pygame.Rect(
                    i * self.glyph_width, 0, self.glyph_width, self.glyph_height
                )
            ).copy()
            for i in range(entry["glyph_count"])
        ]

    def width_of(self, text: str) -> int:
        """Pixel width of a string as it would be drawn."""
        return max(0, len(text) * self.advance - 1)

    def draw(
        self, surface: pygame.Surface, x: int, y: int, text: str
    ) -> None:
        """Draw ``text`` with its top-left corner at ``x, y``."""
        for character in text.upper():
            index = ord(character) - self._first
            if 0 <= index < len(self._glyphs):
                surface.blit(self._glyphs[index], (x, y))
            # Characters outside the font still advance, preserving alignment.
            x += self.advance

    def draw_centered(
        self, surface: pygame.Surface, y: int, text: str
    ) -> None:
        x = (surface.get_width() - self.width_of(text.upper())) // 2
        self.draw(surface, x, y, text)


@lru_cache(maxsize=1)
def tech_font() -> TechFont:
    """The shared font instance. Requires a display mode to be set."""
    return TechFont()
