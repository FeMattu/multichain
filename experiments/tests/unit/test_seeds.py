"""Seed derivation must be pure, stable and independent per purpose."""

from __future__ import annotations

from experiments import seeds


def test_fnv1a_matches_the_reference_vectors():
    # Canonical FNV-1a 32-bit test vectors.
    assert seeds.fnv1a32("") == 0x811C9DC5
    assert seeds.fnv1a32("a") == 0xE40C292C
    assert seeds.fnv1a32("foobar") == 0xBF9CF968


def test_derivation_is_deterministic():
    assert seeds.derive(12345, "esg") == seeds.derive(12345, "esg")


def test_purposes_do_not_collide():
    purposes = ("esg", "workload", "netem", "node_seed", "placement")
    derived = {seeds.derive(20260910, p) for p in purposes}
    assert len(derived) == len(purposes)


def test_different_masters_give_different_seeds():
    assert seeds.derive(1, "esg") != seeds.derive(2, "esg")


def test_seeds_are_non_negative_and_fit_31_bits():
    for master in (0, 1, 20260910, 2 ** 31 - 1, 2 ** 63):
        for purpose in ("esg", "netem"):
            value = seeds.derive(master, purpose)
            assert 0 <= value < 2 ** 31


def test_per_node_seeds_differ():
    a = seeds.derive_node(20260910, "node_seed", "m1")
    b = seeds.derive_node(20260910, "node_seed", "m2")
    assert a != b
