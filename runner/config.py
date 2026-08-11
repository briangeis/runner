"""Tunable constants for the port.

Values transcribed from the original live near the top.  The 1998 game ran
its logic once per iteration of a loop gated by ``Time_Delay(1)``, which waits
for the next tick of the PC's 18.2 Hz timer.  Every speed constant is
therefore "pixels per 18.2 Hz tick".

Rather than lock the port to that tick rate, speeds are converted to pixels
per second with :func:`per_tick` and applied against a delta time.  The game
then moves at exactly the original pace while rendering as smoothly as the
display allows.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------

#: The viewport is the original 320x200, but with *square* pixels.
#:
#: Mode 13h stretched its 320x200 buffer to fill a 4:3 CRT, making every pixel
#: 1.2x taller than wide.  The artwork was not drawn under those conditions:
#: the sprites were made on a square-pixel display, treating 320x200 as a
#: viewport rather than an aspect ratio.  In game they came out 1.2x too
#: tall: circles rendered as ovals and the ships looked too narrow for their
#: height.  That was a limitation of the book's library, not an intent.
#:
#: The fix is to stop stretching, not to change the play field.  Sprites are
#: rendered as though the hardware mode had square pixels (as a 320x240 mode
#: would have had), while the viewport stays the original 320x200.  So:
#:
#:   * gameplay geometry is exactly the original's: 200 rows, and every
#:     speed constant below keeps its 1998 value;
#:   * the 320x200 background art fills the screen exactly, with no bars;
#:   * sprites finally show the proportions they were drawn in.
#:
#: The window is consequently 8:5 rather than 4:3.  Square pixels over a
#: 320x200 viewport leave nothing to fill a 4:3 frame with except bars.
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 200

#: Pixels are square, so the window opens at a whole-number multiple of the
#: viewport.  display.best_window_size() picks the largest multiple that fits
#: within DESKTOP_MARGIN of the desktop, which lands on 4x (1280x800) at 1080p
#: and scales up from there: a 4K display gets 9x rather than a window
#: occupying a third of its width.
MIN_WINDOW_SCALE = 2
MAX_WINDOW_SCALE = 12

#: Fraction of the desktop the window may occupy, leaving room for panels and
#: title bars.
DESKTOP_MARGIN = 0.9

WINDOW_TITLE = "Runner"
TARGET_FPS = 60

# --------------------------------------------------------------------------
# Original timing
# --------------------------------------------------------------------------

#: The DOS timer interrupt frequency that gated the original game loop.
DOS_TICK_HZ = 18.2


def per_tick(pixels: float) -> float:
    """Convert an original per-tick speed into pixels per second."""
    return pixels * DOS_TICK_HZ


def ticks_to_seconds(ticks: float) -> float:
    """Convert a count of original timer ticks into seconds."""
    return ticks / DOS_TICK_HZ

# --------------------------------------------------------------------------
# Fixed gameplay constants, transcribed from the original
# --------------------------------------------------------------------------
#
# Values that affect how the game *feels*, such as speeds, spawn rates, drop
# rates and prices, have moved to runner/balance.py.  What remains here is
# either structural or has never been in question.

NUM_STARS = 250  # NUM_STARS
STAR_COLOR_INDEX = 255  # STAR_C, white in the shared palette

POWERUP_FALL_SPEED = per_tick(2)  # dir_y set on the ENM_POWER branch
PORTAL_DESCENT_SPEED = per_tick(2)  # the portal descended 2px per tick

#: Stars pick a speed of rand() % 20 + 10 pixels per tick in the original.
STAR_SPEED_MIN = per_tick(10)
STAR_SPEED_MAX = per_tick(29)

INVINCIBLE_SECONDS = ticks_to_seconds(400)  # INVC_TIME

STARTING_SHIELDS = 3
STARTING_MAX_SHIELDS = 3
SHIELD_UPGRADE_CAP = 6  # the ceiling the original's shop enforced

#: The original set lives=1 unconditionally, so its lives system
#: never actually did anything. The port gives the player real lives.
STARTING_LIVES = 3

#: Sprite animation advanced every 2 loop iterations in most of the original.
ANIMATION_FRAME_SECONDS = ticks_to_seconds(2)

#: Rows occupied by the status bar. The HUD draws over everything, so this is
#: also the strip the mothership should stay clear of.
HUD_HEIGHT = 10

# --------------------------------------------------------------------------
# Shop pricing, unchanged from the original
# --------------------------------------------------------------------------

# Each upgrade track runs 1 to 3, and a tier may be skipped: banking for
# tier 3 rather than settling for tier 2 is the choice the shop poses. Tier 3
# therefore costs more than both tier 2s combined, so skipping is a real gamble
# on surviving to the next shop.

PRICE_REPLENISH_SHIELDS = 100

PRICE_FIRE_RATE_2 = 300
PRICE_FIRE_RATE_3 = 700

PRICE_DOUBLE_SHOT = 400
PRICE_TRIPLE_SHOT = 800

PRICE_WEAPON_2 = 350
PRICE_WEAPON_3 = 750

PRICE_SHIELD_UPGRADE = 500

#: Not in the original, which sold no way to recover a lost ship.
PRICE_EXTRA_SHIP = 1000

#: Invincibility is not sold, but drop odds are derived from shop prices, so
#: it needs a notional worth to sit among them.
VALUE_INVINCIBILITY = 250

# --------------------------------------------------------------------------
# Debug
# --------------------------------------------------------------------------

#: The original bound an invincibility-plus-$1000 cheat to P.  Off in a
#: shipped game, and kept for testing: endless invincibility is the only
#: practical way to sit inside a boss fight and watch what she does.
ENABLE_DEBUG_CHEAT = False
DEBUG_CHEAT_MONEY = 1000
