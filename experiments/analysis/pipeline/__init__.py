"""Shadow experimental pipeline for wPoA + Weight Engine (three separated phases).

phase1_collect   raw extraction from esperimenti/<run>/<area>/run/ (no derivations, no statistics)
phase2_aggregate deterministic derivations (rankings, in-force weights, weight-engine fold)
phase3_analyze   statistical sheets (hypothesis tests, intervals, Monte Carlo)
common           shared pure helpers, also re-imported by the legacy tools/analizza_esperimenti.py
"""
