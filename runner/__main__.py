"""Entry point:  python -m runner"""

from __future__ import annotations

import sys

from .assets import AssetError


def main() -> int:
    try:
        from .game import main as run
    except ImportError as error:  # pragma: no cover - import-time guard
        print(f"error: {error}", file=sys.stderr)
        print(
            "Is the virtual environment active, and pygame-ce installed?\n"
            "  python -m venv .venv\n"
            "  .venv/bin/pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    try:
        return run()
    except AssetError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
