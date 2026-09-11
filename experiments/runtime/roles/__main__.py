"""Entry point of one node controller.

Started by the scheduler inside the node's own namespace:

    python3 -m experiments.runtime.roles

Everything comes from the POESIA_* environment, because that is the only
channel into a namespace. The exit code matters: the scheduler restarts a
controller that exits non-zero, and records the restart.
"""

from __future__ import annotations

import sys

from . import controller_for
from .base import context_from_env


def main() -> int:
    context = context_from_env()
    return controller_for(context.role, context).run()


if __name__ == "__main__":
    sys.exit(main())
