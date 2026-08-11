"""Input: keyboard and game controller.

The original read raw scancodes out of a custom keyboard ISR and bound
movement to the arrow keys plus HOME / PGUP / END / PGDN for diagonals, with
ALT to fire.  Modern window managers on both Linux and Windows intercept ALT,
so the port rebinds and gets diagonals from held direction keys instead.

Controller support goes through SDL's GameController layer rather than the
raw joystick API, so one set of bindings covers every pad in SDL's database.

Every screen routes its key handling through :func:`intent_of`, so a binding is
declared once here rather than being matched inline in five event loops.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

import pygame

try:  # pragma: no cover - absent only on very old pygame builds
    from pygame._sdl2 import controller as _sdl_controller
except ImportError:  # pragma: no cover
    _sdl_controller = None

# --------------------------------------------------------------------------
# Keyboard
# --------------------------------------------------------------------------

MOVE_UP = (pygame.K_UP, pygame.K_w)
MOVE_DOWN = (pygame.K_DOWN, pygame.K_s)
MOVE_LEFT = (pygame.K_LEFT, pygame.K_a)
MOVE_RIGHT = (pygame.K_RIGHT, pygame.K_d)
FIRE = (pygame.K_SPACE, pygame.K_LCTRL, pygame.K_RCTRL)
#: Selecting a shop shelf: the fire keys and nothing else, so the key you
#: shoot with is the key you choose with.
CONFIRM = (pygame.K_SPACE, pygame.K_LCTRL, pygame.K_RCTRL)
QUIT = (pygame.K_ESCAPE,)
FULLSCREEN = (pygame.K_F11,)
DEBUG_CHEAT = (pygame.K_p,)

#: Keys that never count as "press any key", because they already mean
#: something or are easy to hit by accident.
NON_DISMISSING = set(QUIT) | set(FULLSCREEN) | set(DEBUG_CHEAT) | {
    pygame.K_LSHIFT,
    pygame.K_RSHIFT,
    pygame.K_LCTRL,
    pygame.K_RCTRL,
    pygame.K_LALT,
    pygame.K_RALT,
    pygame.K_LSUPER,
    pygame.K_RSUPER,
    pygame.K_CAPSLOCK,
    pygame.K_NUMLOCK,
    pygame.K_SCROLLLOCK,
}

# --------------------------------------------------------------------------
# Controller
# --------------------------------------------------------------------------

#: Firing is bound to the four face buttons and both shoulders; the triggers
#: fire too, but they are analog axes and are read separately below.  With no
#: reason to reserve any of them, binding them all means the player never has
#: to learn which is which.
PAD_FIRE_BUTTONS = (
    pygame.CONTROLLER_BUTTON_A,
    pygame.CONTROLLER_BUTTON_B,
    pygame.CONTROLLER_BUTTON_X,
    pygame.CONTROLLER_BUTTON_Y,
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
)
#: The lower triggers are analog axes rather than buttons, so they are read
#: against a threshold.
PAD_TRIGGER_AXES = (
    pygame.CONTROLLER_AXIS_TRIGGERLEFT,
    pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
)
PAD_DPAD = {
    "up": pygame.CONTROLLER_BUTTON_DPAD_UP,
    "down": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
    "left": pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    "right": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
}
#: The two buttons either side of the pad's center take the two jobs that sit
#: outside the game: Start toggles fullscreen and Back/Share quits, pairing
#: them with F11 and Esc.
PAD_START = pygame.CONTROLLER_BUTTON_START
PAD_BACK = pygame.CONTROLLER_BUTTON_BACK

#: How far the stick must move before it counts as a direction.  The ship has
#: one speed, so the stick is treated as a second D-pad rather than driving
#: variable-speed movement, since analog motion would change how the game
#: handles, not just how it is controlled.
STICK_DEADZONE = 0.5
#: How far a trigger must be pulled to count as a press.
TRIGGER_THRESHOLD = 0.5

#: Raw axis range reported by SDL.
_AXIS_MAX = 32767.0

#: The open controller, or None.  Typed loosely because pygame._sdl2 has no
#: stubs and may be absent entirely on an old build.
_pad = None


def init() -> None:
    """Open the first attached controller, if there is one.

    Safe to call when none is present, and safe to call twice.
    """
    if _sdl_controller is None:
        return
    _sdl_controller.init()
    _open_first()


def _open_first() -> None:
    global _pad
    if _sdl_controller is None:
        return
    if _pad is not None:
        return
    for index in range(_sdl_controller.get_count()):
        if _sdl_controller.is_controller(index):
            _pad = _sdl_controller.Controller(index)
            return


def handle_device_event(event: pygame.event.Event) -> None:
    """Track controllers being plugged in or pulled out mid-game."""
    global _pad
    if _sdl_controller is None:
        return
    if event.type == pygame.CONTROLLERDEVICEADDED:
        _open_first()
    elif event.type == pygame.CONTROLLERDEVICEREMOVED:
        _pad = None
        _open_first()


def _axis(axis: int) -> float:
    """One axis, normalized to -1..1. Zero when no pad is attached."""
    if _pad is None:
        return 0.0
    try:
        return _pad.get_axis(axis) / _AXIS_MAX
    except Exception:  # pragma: no cover - pad yanked mid-read
        return 0.0


def _button(button: int) -> bool:
    if _pad is None:
        return False
    try:
        return bool(_pad.get_button(button))
    except Exception:  # pragma: no cover - pad yanked mid-read
        return False


# --------------------------------------------------------------------------
# Held state, sampled every frame
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class InputState:
    """A snapshot of what the player is holding this frame."""

    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False
    fire: bool = False

    @property
    def move_x(self) -> int:
        """-1, 0 or 1. Opposing directions cancel."""
        return int(self.right) - int(self.left)

    @property
    def move_y(self) -> int:
        return int(self.down) - int(self.up)


def _any_pressed(pressed: Sequence[bool], keys: tuple[int, ...]) -> bool:
    return any(pressed[key] for key in keys)


def read(pressed: Sequence[bool] | None = None) -> InputState:
    """Sample keyboard and controller together into an :class:`InputState`.

    The two are simply OR-ed, so a player can use either at any moment without
    switching modes.
    """
    if pressed is None:
        pressed = pygame.key.get_pressed()

    stick_x, stick_y = _axis(pygame.CONTROLLER_AXIS_LEFTX), _axis(
        pygame.CONTROLLER_AXIS_LEFTY
    )
    triggers = any(
        _axis(axis) > TRIGGER_THRESHOLD for axis in PAD_TRIGGER_AXES
    )

    return InputState(
        up=_any_pressed(pressed, MOVE_UP)
        or _button(PAD_DPAD["up"])
        or stick_y < -STICK_DEADZONE,
        down=_any_pressed(pressed, MOVE_DOWN)
        or _button(PAD_DPAD["down"])
        or stick_y > STICK_DEADZONE,
        left=_any_pressed(pressed, MOVE_LEFT)
        or _button(PAD_DPAD["left"])
        or stick_x < -STICK_DEADZONE,
        right=_any_pressed(pressed, MOVE_RIGHT)
        or _button(PAD_DPAD["right"])
        or stick_x > STICK_DEADZONE,
        fire=_any_pressed(pressed, FIRE)
        or any(_button(button) for button in PAD_FIRE_BUTTONS)
        or triggers,
    )


# --------------------------------------------------------------------------
# Discrete actions, for menus and screens
# --------------------------------------------------------------------------


class Intent(Enum):
    """What a single press means, whatever device produced it."""

    NONE = auto()
    QUIT = auto()
    FULLSCREEN = auto()
    CHEAT = auto()
    UP = auto()
    DOWN = auto()
    CONFIRM = auto()
    #: A press with no specific meaning, which still dismisses a "press any
    #: key" screen.
    OTHER = auto()


def intent_of(event: pygame.event.Event) -> Intent:
    """Translate one event into an :class:`Intent`.

    Returns NONE for events that are not a press at all, so callers can treat
    anything else as deliberate input.
    """
    if event.type == pygame.KEYDOWN:
        key = event.key
        if key in QUIT:
            return Intent.QUIT
        if key in FULLSCREEN:
            return Intent.FULLSCREEN
        if key in DEBUG_CHEAT:
            return Intent.CHEAT
        if key in MOVE_UP:
            return Intent.UP
        if key in MOVE_DOWN:
            return Intent.DOWN
        if key in CONFIRM:
            return Intent.CONFIRM
        if key in NON_DISMISSING:
            return Intent.NONE
        return Intent.OTHER

    if event.type == pygame.CONTROLLERBUTTONDOWN:
        button = event.button
        if button == PAD_BACK:
            return Intent.QUIT
        if button == PAD_START:
            return Intent.FULLSCREEN
        if button == PAD_DPAD["up"]:
            return Intent.UP
        if button == PAD_DPAD["down"]:
            return Intent.DOWN
        if button in PAD_FIRE_BUTTONS:
            return Intent.CONFIRM
        return Intent.OTHER

    return Intent.NONE


def dismisses(intent: Intent) -> bool:
    """Whether a press should advance a "press any key" screen.

    Everything counts except the presses that already do something else, so a
    player never has to hunt for the right key.
    """
    return intent in (Intent.UP, Intent.DOWN, Intent.CONFIRM, Intent.OTHER)


#: Shown on the controls screen.  Arrow keys and Ctrl work exactly as WASD and
#: Space do, and the controller needs no explanation, since directions sit where
#: they are expected and every thumb button fires, so only one binding per
#: action is listed.
HELP_ROWS = [
    ("WASD", "MOVE"),
    ("SPACE", "FIRE"),
    ("F11", "FULLSCREEN"),
    ("ESC", "QUIT"),
]
