"""Window management and the virtual screen.

All drawing happens on a 320x200 surface, exactly as the original wrote to its
double buffer.  This module scales that surface up to the window with
nearest-neighbor sampling, letterboxed to preserve its aspect.

The one departure from the original is that the scale is *uniform*: the aspect
comes from the buffer itself, so pixels stay square and sprites appear with the
proportions they were drawn in.  Mode 13h instead stretched the same buffer
to 4:3, which rendered every sprite 1.2x too tall.  See config.SCREEN_HEIGHT.
"""

from __future__ import annotations

import pygame

from . import config


def _window_position() -> tuple[int, int] | None:
    """Where the window currently sits, or None if the driver has no idea."""
    try:
        return pygame.display.get_window_position()
    except (AttributeError, pygame.error):  # pragma: no cover - driver specific
        return None


def _move_window(position: tuple[int, int]) -> None:
    try:
        pygame.display.set_window_position(position)
    except (AttributeError, pygame.error):  # pragma: no cover - driver specific
        pass


def best_window_size() -> tuple[int, int]:
    """Largest whole-number scale of the viewport that fits this desktop.

    Scaling by whole numbers keeps every game pixel the same size, so the art
    stays crisp.  The largest that fits within DESKTOP_MARGIN happens to be 4x
    (1280x800) on a 1080p display, and grows from there: a 4K monitor gets
    9x rather than a window taking up a third of its width.
    """
    try:
        desktops = pygame.display.get_desktop_sizes()
    except pygame.error:  # display not initialized yet
        desktops = []

    if not desktops:
        scale = config.MIN_WINDOW_SCALE
    else:
        desktop_width, desktop_height = desktops[0]
        usable_width = desktop_width * config.DESKTOP_MARGIN
        usable_height = desktop_height * config.DESKTOP_MARGIN
        scale = config.MIN_WINDOW_SCALE
        for candidate in range(config.MIN_WINDOW_SCALE, config.MAX_WINDOW_SCALE + 1):
            if (
                config.SCREEN_WIDTH * candidate <= usable_width
                and config.SCREEN_HEIGHT * candidate <= usable_height
            ):
                scale = candidate
            else:
                break

    return config.SCREEN_WIDTH * scale, config.SCREEN_HEIGHT * scale


class Display:
    """Owns the window and the 320x200 buffer everything draws into."""

    def __init__(
        self,
        size: tuple[int, int] | None = None,
        *,
        fullscreen: bool = False,
    ) -> None:
        if size is None:
            size = best_window_size()
        self._fullscreen = fullscreen
        self._windowed_size = size
        #: Where the window sat before it went fullscreen.
        self._windowed_pos: tuple[int, int] | None = None
        # The window has to exist before any surface can be convert()ed.
        self._set_mode(size, fullscreen)
        if not fullscreen:
            self._center()
        self.buffer = pygame.Surface(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        ).convert()

    def _center(self) -> None:
        """Put the window in the middle of the primary desktop.

        SDL leaves placement to the window manager otherwise, and managers do
        not agree on where a new window belongs.  Done as one explicit move
        after the window exists rather than through SDL_VIDEO_CENTERED, which
        would apply to every later set_mode as well and add a reposition to
        each one.
        """
        try:
            desktops = pygame.display.get_desktop_sizes()
        except pygame.error:  # pragma: no cover - display not ready
            return
        if not desktops:
            return
        width, height = self.window.get_size()
        desktop_width, desktop_height = desktops[0]
        _move_window(
            ((desktop_width - width) // 2, (desktop_height - height) // 2)
        )

    def _set_mode(self, size: tuple[int, int], fullscreen: bool) -> None:
        flags = pygame.RESIZABLE
        if fullscreen:
            flags = pygame.FULLSCREEN
            size = (0, 0)
        self.window = pygame.display.set_mode(size, flags)
        self._recompute_target()

    def _recompute_target(self) -> None:
        """Fit the play field's aspect inside the window and center it."""
        window_width, window_height = self.window.get_size()
        target_aspect = config.SCREEN_WIDTH / config.SCREEN_HEIGHT

        if window_width / window_height > target_aspect:
            height = window_height
            width = round(height * target_aspect)
        else:
            width = window_width
            height = round(width / target_aspect)

        self.target_rect = pygame.Rect(
            (window_width - width) // 2,
            (window_height - height) // 2,
            width,
            height,
        )

    def toggle_fullscreen(self) -> None:
        """Switch between fullscreen and windowed.

        Fullscreen is asked for at (0, 0), meaning the desktop's own
        resolution, and that detail carries the aspect ratio: nothing about
        the video mode changes, so the monitor is never handed a signal to
        rescale, and _recompute_target() letterboxes the 320x200 viewport
        inside whatever the desktop is.  pygame.display.toggle_fullscreen()
        would instead make the *window's* size the mode, and 1280x800 sent to
        a 16:9 panel arrives stretched.

        Leaving fullscreen lets SDL and the window manager reposition the
        window, which walked it down the screen a title bar at a time, so the
        windowed position is read on the way out and reapplied on the way
        back.
        """
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self._windowed_pos = _window_position()
            self._set_mode((0, 0), True)
            return

        self._set_mode(self._windowed_size, False)
        if self._windowed_pos is not None:
            _move_window(self._windowed_pos)

    def handle_resize(self, size: tuple[int, int]) -> None:
        if not self._fullscreen:
            self._windowed_size = size
        self._recompute_target()

    def clear(self, color: tuple[int, int, int] = (0, 0, 0)) -> None:
        """Clear the virtual screen, as Fill_Double_Buffer(0) did."""
        self.buffer.fill(color)

    def draw_backdrop(self, image: pygame.Surface) -> None:
        """Draw a full-screen background image.

        The art is 320x200 and the viewport is 320x200, so it fills the screen
        exactly: no scaling, no bars.
        """
        self.buffer.blit(image, (0, 0))

    def present(self) -> None:
        """Scale the virtual screen into the window and flip."""
        self.window.fill((0, 0, 0))
        pygame.transform.scale(
            self.buffer, self.target_rect.size, self.window.subsurface(self.target_rect)
        )
        pygame.display.flip()
