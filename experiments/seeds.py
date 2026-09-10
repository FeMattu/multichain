"""Deterministic seed derivation from one master seed.

    derived(purpose) = (master ^ fnv1a32(purpose)) & 0x7FFFFFFF

Pure, dependency-free and stable across Python versions — ``hash()`` is not,
which is why it is not used. Every seed that reaches a role script, a workload
generator or a manifest comes from here, so a descriptor plus its master seed
is a complete description of the randomness the harness controls.

What it does *not* control is stated in configs/seeds.yaml and in
docs/reproducibility.md: MultiChain's own RNG, and netem's kernel-side
generators.
"""

from __future__ import annotations

FNV_OFFSET = 0x811C9DC5
FNV_PRIME = 0x01000193
MASK32 = 0xFFFFFFFF


def fnv1a32(text: str) -> int:
    """32-bit FNV-1a of a UTF-8 string."""
    digest = FNV_OFFSET
    for byte in text.encode("utf-8"):
        digest = ((digest ^ byte) * FNV_PRIME) & MASK32
    return digest


def derive(master: int, purpose: str) -> int:
    """A stable non-negative 31-bit seed for one purpose."""
    return (int(master) ^ fnv1a32(purpose)) & 0x7FFFFFFF


def derive_node(master: int, purpose: str, node_id: str) -> int:
    """Per-node variant, so two nodes never share a workload seed."""
    return derive(master, "%s/%s" % (purpose, node_id))
