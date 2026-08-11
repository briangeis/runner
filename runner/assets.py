"""Loading of the artwork.

The sprites ship as PNG strips with a manifest describing how to cut them up.
This module reads that manifest and hands back ready-to-blit surfaces, so
nothing at runtime needs to know about palettes or sprite sheet geometry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
MANIFEST_PATH = ASSETS_DIR / "manifest.json"


class AssetError(RuntimeError):
    """Raised when the converted assets are missing or unusable."""


@dataclass(frozen=True)
class SpriteSheet:
    """An animation's frames, already split out of its PNG strip."""

    name: str
    frames: list[pygame.Surface]
    width: int
    height: int
    frame_groups: dict[str, list[int]]

    def frame(self, index: int) -> pygame.Surface:
        """Return a frame, wrapping so animation counters can't overrun."""
        return self.frames[index % len(self.frames)]

    def group(self, name: str) -> list[int]:
        return self.frame_groups[name]

    def __len__(self) -> int:
        return len(self.frames)


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        raise AssetError(
            f"asset manifest not found at {MANIFEST_PATH}.\n"
            "The installation looks incomplete; try unpacking it again."
        )
    return json.loads(MANIFEST_PATH.read_text())


def _load_png(relative_path: str) -> pygame.Surface:
    path = ASSETS_DIR / relative_path
    if not path.is_file():
        raise AssetError(
            f"asset file missing: {path}\n"
            "The installation looks incomplete; try unpacking it again."
        )
    return pygame.image.load(str(path)).convert_alpha()


@lru_cache(maxsize=None)
def load_sprite(name: str) -> SpriteSheet:
    """Load one sprite animation by its manifest name.

    Requires a display mode to be set, since frames are converted for fast
    blitting.
    """
    manifest = load_manifest()
    try:
        entry = manifest["sprites"][name]
    except KeyError:
        available = ", ".join(sorted(manifest["sprites"]))
        raise AssetError(f"unknown sprite {name!r}. Available: {available}") from None

    strip = _load_png(entry["file"])
    width, height = entry["width"], entry["height"]
    frames = [
        strip.subsurface(pygame.Rect(i * width, 0, width, height)).copy()
        for i in range(entry["frames"])
    ]
    return SpriteSheet(
        name=name,
        frames=frames,
        width=width,
        height=height,
        frame_groups=entry.get("frame_groups", {}),
    )


@lru_cache(maxsize=None)
def load_splash(name: str) -> pygame.Surface:
    """Load a full-screen 320x200 image, such as the title art."""
    manifest = load_manifest()
    try:
        entry = manifest["splash"][name]
    except KeyError:
        available = ", ".join(sorted(manifest["splash"]))
        raise AssetError(
            f"unknown splash image {name!r}. Available: {available}"
        ) from None
    return _load_png(entry["file"]).convert()


@lru_cache(maxsize=1)
def banner() -> str:
    """The ASCII banner the original printed to the console on exit."""
    entry = load_manifest().get("banner")
    if not entry:
        return ""
    path = ASSETS_DIR / entry["file"]
    return path.read_text() if path.is_file() else ""


@lru_cache(maxsize=1)
def palette() -> list[tuple[int, int, int]]:
    """The shared 256-color VGA palette from the original artwork."""
    return [tuple(color) for color in load_manifest()["palette"]]


def palette_color(index: int) -> tuple[int, int, int]:
    """Look up an original palette index, e.g. STAR_COLOR_INDEX."""
    return palette()[index]
