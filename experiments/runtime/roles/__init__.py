"""Per-node controllers: what each node actually does during a run.

The Shadow suite drove every node with a bash script. These are those scripts
ported to Python, with a life cycle, a supervisor and configuration in place
of constants. See :mod:`experiments.runtime.roles.base`.
"""

from .admin import AdminController  # noqa: F401
from .base import RoleContext, RoleController, context_from_env  # noqa: F401
from .ca import CaController  # noqa: F401
from .company import CompanyController  # noqa: F401
from .miner import MinerController  # noqa: F401

CONTROLLERS = {
    "admin": AdminController,
    "miner": MinerController,
    "company": CompanyController,
    "ca": CaController,
}


def controller_for(role: str, context):
    """The controller class for a role, instantiated."""
    try:
        factory = CONTROLLERS[role]
    except KeyError:
        raise SystemExit("no controller for role %r; known: %s"
                         % (role, ", ".join(sorted(CONTROLLERS)))) from None
    return factory(context)
