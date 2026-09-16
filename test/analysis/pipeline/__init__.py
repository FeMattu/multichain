"""The three-phase analysis pipeline.

Phase 1 collects, phase 2 aggregates, phase 3 tests — and each phase may only read the
output of the one before it. The separation is what keeps a conclusion traceable: a
surprising number in a phase-3 report can be followed back to a phase-2 row, then to a
phase-1 row, then to a single line of a node's ``events.jsonl`` and the RPC call that
produced it.

This is a package rather than a directory of loose scripts for one concrete reason: the
statistics live in a subpackage called ``stat``, which is also the name of a standard
library module. Reached as ``pipeline.stat`` it is unambiguous; put on ``sys.path`` as a
top-level ``stat`` it would shadow the real one for every module in the process,
including ``os.path`` and ``shutil``.
"""
