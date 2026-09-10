"""Network fabrics: the thing that turns a topology into interfaces and links.

Three backends behind one interface (:class:`~experiments.runtime.fabric.base.Fabric`):

``core``    CORE Network Emulator, driven through its gRPC API. The primary
            backend: CORE owns the session, the nodes and the links, and the
            harness asks it to build them.
``netns``   Plain Linux network namespaces, veth pairs, static routes and
            tc/netem. These are the same primitives CORE itself uses; the
            backend exists so the harness runs on a machine where CORE is not
            installed, and so the fabric can be unit-tested end to end.
``docker``  One container per node. Declared and dispatched, not yet built:
            see :mod:`experiments.runtime.fabric.docker_backend`.
"""

from .base import Fabric, FabricStatus, LinkEndpoint, RealizedLink, RealizedNode  # noqa: F401
from .factory import available_backends, make_fabric  # noqa: F401
