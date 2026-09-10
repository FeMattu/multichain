#!/usr/bin/env python3
"""Phase 2 - deterministic derivations. Reads <out>/<run>/<area>/phase1/, writes .../phase2/.

No hypothesis test lives here. Everything is an exact recomputation from the
raw rows of phase 1 and the sealed parameters: in-force weights per round,
effective weights g(w*Psi), W_tot, theoretical shares, E_i and u_i from the
logged score, the recomputed delay and its mismatch with the logged one,
rankings, the observed-vs-theoretical winner, margins, time-bar check, forks,
streaks, per-epoch counts, and the Chapter-6 weight-engine fold.

Tables: candidates_long, round_level, epoch_level_wpoa, epoch_level_weight_engine,
        weight_engine_verification, balance_by_height, malus_epoch, manifest.json

    python3 tools/pipeline/phase2_aggregate.py --out risultati
"""

import argparse
import json
import logging
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

from . import common as C

LOG = logging.getLogger("pipeline.phase2")

DELAY_TOL_S = 0.0015          # logged delay has 3 decimals: half a unit plus float noise


def _base(man):
    return OrderedDict([
        ("experiment_id", man["experiment_id"]), ("replication_id", man["replication_id"]),
        ("area", man["area"]), ("target_block_time", man["target_block_time"]),
        ("dumpfunction", man["dump_function"] or "none"), ("malus_enabled", man["malus_enabled"]),
        ("weight_epoch_length", man["weight_epoch_length"]),
    ])


def load_phase1(p1):
    man = json.loads((p1 / "manifest.json").read_text(encoding="utf-8"))
    t = {name: C.read_csv_dicts(p1 / (name + ".csv")) for name in (
        "blocks", "sortition_scores", "phi", "verify_lines", "sortition_ok_blocks", "rejects",
        "weight_engine_log", "weights_stream", "esg_stream", "membership_stream", "malus_stream",
        "traffic", "reconciliation", "gas_balances", "hosts")}
    return man, t


def meta_from_manifest(man):
    """The subset of legacy `meta` needed by weight_engine_params / fold."""
    meta = dict(man["params"])
    meta["epoch_len"] = int(man["weight_epoch_length"])
    meta["setup_blocks"] = int(man["setup_blocks"])
    meta["tbt"] = float(man["target_block_time"])
    return meta


def derive_run(p1, p2):
    man, t = load_phase1(p1)
    meta = meta_from_manifest(man)
    L, setup = meta["epoch_len"], meta["setup_blocks"]
    tbt = meta["tbt"]
    delta = C.as_float(meta.get("wpoa_sortition_delta"), 0.5)
    lam = C.as_float(meta.get("wpoa_sortition_lambda"), 0.0)
    kappa, alpha, lam_w, mu, m_max, dump_fn = C.weight_engine_params(meta)
    final_height = C.inum(man.get("final_height"), 0) or 0
    base = _base(man)
    host_by_addr = {h["address"]: h["host"] for h in t["hosts"] if h["address"]}
    addr_by_host = {h["host"]: h["address"] for h in t["hosts"] if h["address"]}
    miners = [h["host"] for h in t["hosts"] if h["role"] == "miner"]
    buried = {e["epoch"]: e["buried"] for e in man.get("epochs", [])}
    warnings = []

    # ---- blocks -----------------------------------------------------------
    blocks = sorted(({"height": C.inum(b["height"]), "hash": b["hash"], "miner": b["miner_address"],
                      "miner_host": b["miner_host"], "time": C.inum(b["time"]),
                      "txcount": C.inum(b["txcount"], 0)} for b in t["blocks"]),
                    key=lambda b: b["height"])
    by_height = {b["height"]: b for b in blocks}

    # ---- weight records and the Chapter-6 fold (inputs from phase 1 only) --
    wrecs = []
    for r in t["weights_stream"]:
        wrecs.append({"address": r["node_address"], "epoca": C.inum(r["epoch_tag"]),
                      "peso": C.inum(r["weight"]), "height_payload": C.inum(r["height_payload"]),
                      "height_conferma": C.inum(r["confirm_height"]), "txid": r["txid"]})
    wrecs.sort(key=lambda r: (r["height_conferma"] if r["height_conferma"] is not None else 10 ** 9,
                              r["epoca"] or 0))
    memberships = [(r["node_address"], r["miner_address"], C.epoch_of(C.inum(r["confirm_height"]), L))
                   for r in t["membership_stream"]]
    esgs = [(r["node_address"], C.fnum(r["esg"]), C.epoch_of(C.inum(r["confirm_height"]), L),
             r["publisher_address"]) for r in t["esg_stream"]]
    traffic_ok = [(r["address"], C.epoch_of(C.inum(r["confirm_height"]), L))
                  for r in t["traffic"] if r["txid"] and r["confirm_height"] != ""]
    reconciliations = [(addr_by_host.get(r["miner_host"], ""),
                        C.epoch_of(C.inum(r["assumed_confirm_height"]), L), C.fnum(r["sent_gas"], 0.0))
                       for r in t["reconciliation"]]
    inputs = C.weight_engine_inputs_pure(memberships, esgs, traffic_ok, reconciliations, wrecs,
                                         L, n_malus_rec=len(t["malus_stream"]))
    max_epoch = max([e for _a, e in inputs["published"]] + [C.epoch_of(final_height, L) or 1] + [1])
    derived, psi_by_epoch, malus_by_epoch = C.weight_engine_fold(inputs, meta, max_epoch)
    fold_miners = inputs["miners"]

    # ---- per-height indexes of the log tables ------------------------------
    scores_at = defaultdict(list)
    n_dup = 0
    for r in t["sortition_scores"]:
        if C.inum(r["duplicate_index"], 0):
            n_dup += 1
            continue
        scores_at[C.inum(r["height"])].append(r)
    phi_at = {(r["host"], C.inum(r["tip_height"])): r for r in t["phi"]}
    verify_at = defaultdict(list)
    for r in t["verify_lines"]:
        verify_at[C.inum(r["height"])].append(r)
    sortok_at = defaultdict(list)
    for r in t["sortition_ok_blocks"]:
        sortok_at[C.inum(r["height"])].append(r)
    rejects_at = Counter(C.inum(r["height"]) for r in t["rejects"])
    samples = defaultdict(list)
    for r in t["gas_balances"]:
        samples[r["host"]].append((C.inum(r["sample_height"]), C.fnum(r["balance_gas"])))
    for h in samples:
        samples[h].sort()

    def last_sample(host, height):
        best = (None, None)
        for sh, bal in samples.get(host, []):
            if sh <= height:
                best = (sh, bal)
            else:
                break
        return best

    # ---- candidates_long and round_level -----------------------------------
    cand_rows, round_rows = [], []
    inforce = {}
    idx = 0
    streak = 0
    prev_miner = None
    obs_by_epoch = defaultdict(Counter)        # epoch -> miner_addr -> blocks
    exp_by_epoch = defaultdict(Counter)        # epoch -> addr -> sum of p
    blocks_by_epoch = Counter()
    p_first, p_last = {}, {}                   # (epoch, addr) -> p at first / last block
    w_first, w_last = {}, {}                   # (epoch, addr) -> (w_raw, w_eff)
    argmin_count = defaultdict(Counter)        # epoch -> addr -> rounds as argmin
    argmin_lost = defaultdict(Counter)
    won_not_argmin = defaultdict(Counter)
    delays_epoch = defaultdict(lambda: defaultdict(list))
    forks_epoch, competing_epoch, rejects_epoch = Counter(), Counter(), Counter()
    rounds_epoch = Counter()
    share_change_epoch = defaultdict(set)
    n_tb_viol = n_inv = n_rounds = n_full = 0
    n_delay_mismatch_rows = 0
    rounds_with_delay_mismatch = set()
    dmax_local = delta * tbt
    max_mismatch = 0.0
    phi_mismatch_rounds = 0
    n_argmin_disagree = 0

    for blk in blocks:
        h = blk["height"]
        while idx < len(wrecs) and wrecs[idx]["height_conferma"] is not None \
                and wrecs[idx]["height_conferma"] < h:
            inforce[wrecs[idx]["address"]] = wrecs[idx]
            idx += 1
        if h <= setup:
            continue
        e = C.epoch_of(h, L)
        eb = buried.get(e, C.epoch_buried(e, L, final_height))
        blocks_by_epoch[e] += 1
        obs_by_epoch[e][blk["miner"]] += 1
        prev = by_height.get(h - 1)
        parent_time = prev["time"] if prev else None
        dt_prev = (blk["time"] - parent_time) if parent_time is not None else None

        # effective weights in force for this round
        eff, raw = {}, {}
        for addr, rec in inforce.items():
            psi = psi_by_epoch.get((addr, e - 1), 1.0)
            raw[addr] = rec["peso"]
            eff[addr] = C.apply_dumping(C.effective_after_malus(rec["peso"], psi), dump_fn)
        w_tot = sum(eff.values())
        shares = {a: (v / w_tot if w_tot > 0 else None) for a, v in eff.items()}
        for a, p in shares.items():
            if p is not None:
                exp_by_epoch[e][a] += p
                p_first.setdefault((e, a), p)
                p_last[(e, a)] = p
                w_first.setdefault((e, a), (raw[a], eff[a]))
                w_last[(e, a)] = (raw[a], eff[a])
                if p_first[(e, a)] != p:
                    share_change_epoch[e].add(a)

        # streak on the canonical sequence
        streak = streak + 1 if blk["miner"] == prev_miner else 1
        repeats = int(blk["miner"] == prev_miner) if prev_miner is not None else ""
        prev_miner = blk["miner"]

        # competing blocks, rejects, verify line of the canonical block
        competing = sorted({r["block_hash"] for r in sortok_at.get(h, []) if r["block_hash"] != blk["hash"]})
        forks_epoch[e] += int(bool(competing))
        competing_epoch[e] += len(competing)
        rejects_epoch[e] += rejects_at.get(h, 0)
        vrow = None
        for r in verify_at.get(h, []):
            if r["signer_address"] == blk["miner"] and C.inum(r["ntime"]) == blk["time"]:
                vrow = r
                break
        if vrow is None and verify_at.get(h):
            vrow = verify_at[h][0]
        tb_ok, tb_slack, v_floor, v_parent_match = "", "", "", ""
        if vrow:
            v_floor = C.inum(vrow["delay_floor_s"])
            nt, pt = C.inum(vrow["ntime"]), C.inum(vrow["parent_ntime"])
            tb_slack = nt - pt - v_floor
            tb_ok = int(tb_slack >= 0)
            v_parent_match = int(pt == parent_time) if parent_time is not None else ""
            if not tb_ok:
                n_tb_viol += 1

        cands = scores_at.get(h, [])
        rounds_epoch[e] += int(bool(cands))
        # per-candidate derivations
        crows = []
        for r in cands:
            addr, host = r["address"], r["host"]
            score = C.fnum(r["score_raw"])
            d_log = C.fnum(r["delay_logged_s"])
            rec = inforce.get(addr)
            phi_row = phi_at.get((host, h - 1))
            phi = C.fnum(phi_row["phi_s"]) if phi_row else None
            w_eff = eff.get(addr)
            row = OrderedDict(base)
            row.update({
                "height": h, "epoch": e, "epoch_buried": int(bool(eb)),
                "candidate_host": host, "candidate_address": addr,
                "weight_raw_inforce": rec["peso"] if rec else "",
                "weight_record_epoch_tag": rec["epoca"] if rec else "",
                "weight_record_confirm_height": rec["height_conferma"] if rec else "",
                "psi": round(psi_by_epoch.get((addr, e - 1), 1.0), 6),
                "weight_effective": round(w_eff, 6) if w_eff is not None else "",
                "W_tot_effective": round(w_tot, 6) if w_tot else "",
                "p_theoretical": round(shares[addr], 6) if shares.get(addr) is not None else "",
                "score_raw": score,
                "E_i": round(score * w_eff, 8) if (score is not None and w_eff) else "",
                "u_i": round(math.exp(-score * w_eff), 8) if (score is not None and w_eff) else "",
                "score_norm": round(C.normalized_score(score, w_tot), 8) if (score is not None and w_tot) else "",
                "phi_s": phi if phi is not None else "",
                "phi_bound_s": phi_row["phi_bound_s"] if phi_row else "",
                "delay_logged_s": d_log,
            })
            d_rec = None
            if score is not None and w_tot and phi is not None:
                d_rec = C.sortition_delay(score, w_tot, tbt, delta, lam, phi)
                mism = d_rec - d_log
                max_mismatch = max(max_mismatch, abs(mism))
            row["delay_recomputed_s"] = round(d_rec, 4) if d_rec is not None else ""
            row["delay_mismatch_s"] = round(d_rec - d_log, 4) if d_rec is not None else ""
            ok = int(abs(d_rec - d_log) <= DELAY_TOL_S) if d_rec is not None else ""
            row["delay_recompute_ok"] = ok
            # W_tot that would reproduce the logged delay exactly: when it differs
            # from W_tot_effective the node computed with another weight map view
            w_impl = ""
            if ok == 0 and score and dmax_local:
                norm_impl = ((d_log - tbt - lam * phi) / dmax_local + 1.0) / 2.0
                if 0.0 < norm_impl < 1.0:
                    w_impl = round(-math.log(1.0 - norm_impl) / score, 1)
            row["W_tot_implied_by_logged_delay"] = w_impl
            if ok == 0:
                n_delay_mismatch_rows += 1
            row["is_winner"] = int(addr == blk["miner"])
            row["_d"] = d_log
            row["_s"] = score
            crows.append(row)
            if d_log is not None:
                delays_epoch[e][addr].append(d_log)

        # ranks and the theoretical winner
        by_d = sorted((c for c in crows if c["_d"] is not None), key=lambda c: (c["_d"], c["candidate_address"]))
        by_s = sorted((c for c in crows if c["_s"] is not None), key=lambda c: (c["_s"], c["candidate_address"]))
        for i, c in enumerate(by_d, 1):
            c["rank_by_delay"] = i
        for i, c in enumerate(by_s, 1):
            c["rank_by_score"] = i
        argmin_d = by_d[0] if by_d else None
        argmin_s = by_s[0] if by_s else None
        if argmin_d and argmin_s and argmin_d["candidate_address"] != argmin_s["candidate_address"]:
            n_argmin_disagree += 1
        miner_phis = {c["candidate_host"]: c["phi_s"] for c in crows if c["phi_s"] != ""}
        phi_identical = int(len(set(miner_phis.values())) <= 1) if miner_phis else ""
        if phi_identical == 0:
            phi_mismatch_rounds += 1
        winner_row = next((c for c in crows if c["is_winner"]), None)
        for c in crows:
            c["is_theoretical_argmin_delay"] = int(argmin_d is not None and c is argmin_d)
            c["is_theoretical_argmin_score"] = int(argmin_s is not None and c is argmin_s)
            c["actual_proposer_host"] = blk["miner_host"]
            c["actual_proposer_address"] = blk["miner"]
            c["block_hash"] = blk["hash"]
            c["block_time"] = blk["time"]
            c["parent_time"] = parent_time if parent_time is not None else ""
            c["verify_delay_floor_s"] = v_floor
            c["time_bar_ok"] = tb_ok
            c["fork_detected"] = int(bool(competing))
            c["n_competing_blocks"] = len(competing)
            sh_h, sh_b = last_sample(c["candidate_host"], h)
            c["balance_gas_sample"] = sh_b if sh_b is not None else ""
            c["balance_sample_height"] = sh_h if sh_h is not None else ""
            c["streak_position"] = streak if c["is_winner"] else ""
            c.pop("_d"), c.pop("_s")
            cand_rows.append(c)
        if argmin_d:
            a = argmin_d["candidate_address"]
            argmin_count[e][a] += 1
            if a != blk["miner"]:
                argmin_lost[e][a] += 1
                won_not_argmin[e][blk["miner"]] += 1

        if any(c["delay_recompute_ok"] == 0 for c in crows):
            rounds_with_delay_mismatch.add(h)
        n_rounds += int(bool(crows))
        expected_n = len([a for a in eff if eff[a] > 0])
        n_full += int(bool(crows) and len(crows) >= expected_n)
        inv = ""
        if argmin_d is not None:
            inv = int(argmin_d["candidate_address"] != blk["miner"])
            n_inv += inv
        rr = OrderedDict(base)
        rr.update({
            "height": h, "epoch": e, "epoch_buried": int(bool(eb)),
            "n_candidates_logged": len(crows), "n_candidates_with_weight": expected_n,
            "all_candidates_logged": int(bool(crows) and len(crows) >= expected_n),
            "winner_observed_host": blk["miner_host"], "winner_observed_address": blk["miner"],
            "winner_observed_logged_score": int(winner_row is not None),
            "winner_theoretical_argmin_delay_host": argmin_d["candidate_host"] if argmin_d else "",
            "winner_theoretical_argmin_score_host": argmin_s["candidate_host"] if argmin_s else "",
            "argmin_delay_equals_argmin_score": int(argmin_d["candidate_address"] == argmin_s["candidate_address"]) if (argmin_d and argmin_s) else "",
            "winner_matches_theoretical_argmin": (1 - inv) if inv != "" else "",
            "inversion": inv,
            "observed_winner_rank_by_delay": winner_row.get("rank_by_delay", "") if winner_row else "",
            "delay_min_s": by_d[0]["delay_logged_s"] if by_d else "",
            "delay_winner_s": winner_row["delay_logged_s"] if winner_row else "",
            "margin_G_logged_s": round(by_d[1]["delay_logged_s"] - by_d[0]["delay_logged_s"], 4) if len(by_d) >= 2 else "",
            "margin_G_recomputed_s": (round(sorted(c["delay_recomputed_s"] for c in crows if c["delay_recomputed_s"] != "")[1]
                                            - sorted(c["delay_recomputed_s"] for c in crows if c["delay_recomputed_s"] != "")[0], 4)
                                      if sum(1 for c in crows if c["delay_recomputed_s"] != "") >= 2 else ""),
            "inversion_gap_s": round(winner_row["delay_logged_s"] - by_d[0]["delay_logged_s"], 4) if (winner_row and by_d) else "",
            "score_min": by_s[0]["score_raw"] if by_s else "",
            "score_gap_2_1": (by_s[1]["score_raw"] - by_s[0]["score_raw"]) if len(by_s) >= 2 else "",
            "W_tot_effective": round(w_tot, 6) if w_tot else "",
            "W_tot_minus_argmin_weff": round(w_tot - eff.get(argmin_s["candidate_address"], 0.0), 6) if (argmin_s and w_tot) else "",
            "weff_argmin_score": round(eff.get(argmin_s["candidate_address"], 0.0), 6) if (argmin_s and w_tot) else "",
            "p_observed_winner": round(shares.get(blk["miner"], 0.0), 6) if (w_tot and shares.get(blk["miner"]) is not None) else "",
            "phi_s": miner_phis.get(blk["miner_host"], next(iter(miner_phis.values()), "")) if miner_phis else "",
            "phi_identical_across_nodes": phi_identical,
            "block_time": blk["time"], "parent_time": parent_time if parent_time is not None else "",
            "dt_prev_s": dt_prev if dt_prev is not None else "",
            "scheduler_residual_s": round(dt_prev - winner_row["delay_logged_s"], 4) if (dt_prev is not None and winner_row) else "",
            "verify_delay_floor_s": v_floor, "time_bar_slack_s": tb_slack, "time_bar_ok": tb_ok,
            "verify_parent_matches_chain": v_parent_match,
            "fork_detected": int(bool(competing)), "n_competing_blocks": len(competing),
            "competing_hashes": " ".join(competing), "n_rejects": rejects_at.get(h, 0),
            "txcount": blk["txcount"],
            "streak_length_so_far": streak, "winner_repeats_previous": repeats,
            "n_candidates_delay_recompute_mismatch": sum(1 for c in crows if c["delay_recompute_ok"] == 0),
        })
        round_rows.append(rr)

    # ---- epoch_level_wpoa ---------------------------------------------------
    epoch_rows = []
    dmax = delta * tbt
    validators = sorted({a for e in exp_by_epoch for a in exp_by_epoch[e]} | set(fold_miners))
    for e in sorted(blocks_by_epoch):
        lo, hi = C.epoch_bounds(e, L)
        B = blocks_by_epoch[e]
        for a in validators:
            dl = delays_epoch[e].get(a, [])
            mean_d = sum(dl) / len(dl) if dl else None
            wf, wl = w_first.get((e, a)), w_last.get((e, a))
            row = OrderedDict(base)
            row.update({
                "epoch": e, "epoch_buried": int(bool(buried.get(e, C.epoch_buried(e, L, final_height)))),
                "epoch_start_height": lo, "epoch_end_height": hi,
                "epoch_measured_start_height": max(lo, setup + 1),
                "n_blocks_epoch": B, "n_rounds_with_scores": rounds_epoch[e],
                "validator_host": host_by_addr.get(a, a[:10]), "validator_address": a,
                "O_i": obs_by_epoch[e].get(a, 0),
                "E_i_expected": round(exp_by_epoch[e].get(a, 0.0), 6),
                "p_theoretical_blockweighted": round(exp_by_epoch[e].get(a, 0.0) / B, 6) if B else "",
                "p_theoretical_start": round(p_first[(e, a)], 6) if (e, a) in p_first else "",
                "p_theoretical_end": round(p_last[(e, a)], 6) if (e, a) in p_last else "",
                "share_changed_within_epoch": int(a in share_change_epoch[e]),
                "p_observed": round(obs_by_epoch[e].get(a, 0) / B, 6) if B else "",
                "w_raw_start": wf[0] if wf else "", "w_raw_end": wl[0] if wl else "",
                "w_eff_start": round(wf[1], 6) if wf else "", "w_eff_end": round(wl[1], 6) if wl else "",
                "n_delays_logged": len(dl),
                "delay_mean_s": round(mean_d, 4) if dl else "",
                "delay_min_s": round(min(dl), 4) if dl else "", "delay_max_s": round(max(dl), 4) if dl else "",
                "delay_pos_in_band_mean": round((mean_d - (tbt - dmax)) / (2 * dmax), 4) if (dl and dmax) else "",
                "n_rounds_theoretical_argmin": argmin_count[e].get(a, 0),
                "n_rounds_theoretical_argmin_lost": argmin_lost[e].get(a, 0),
                "n_rounds_won_not_argmin": won_not_argmin[e].get(a, 0),
                "n_forks_epoch": forks_epoch[e], "n_competing_blocks_epoch": competing_epoch[e],
                "n_rejects_epoch": rejects_epoch[e],
            })
            epoch_rows.append(row)

    # ---- epoch_level_weight_engine -----------------------------------------
    theta_thesis = Counter()
    for b in blocks:
        theta_thesis[C.epoch_of(b["height"], L)] += max(b["txcount"] - 1, 0)
    published, pub_height = inputs["published"], inputs["pub_height"]
    we_rows, malus_rows = [], []
    ver_by_epoch = defaultdict(lambda: Counter())
    pubs_by_epoch = defaultdict(dict)
    for r in t["weight_engine_log"]:
        e = C.inum(r["epoch"])
        if r["kind"] == "publication":
            pubs_by_epoch[e][r["address"]] = (C.inum(r["weight"]), C.inum(r["height"]), r["host"])
        else:
            ver_by_epoch[e][r["kind"]] += 1
    n_recompute_mismatch = 0
    for e in range(1, max_epoch + 1):
        snapshot = {}
        for m in fold_miners:
            best = None
            for (a, ee), w in published.items():
                if a == m and ee <= e and (best is None or ee > best[0]):
                    best = (ee, w)
            if best:
                snapshot[m] = C.apply_dumping(C.effective_after_malus(best[1], psi_by_epoch.get((m, e - 1), 1.0)), dump_fn)
        w_tot_snap = sum(snapshot.values())
        for m in fold_miners:
            d = derived.get((m, e))
            if d is None:
                continue
            pubw = published.get((m, e))
            prevw = published.get((m, e - 1))
            psi = psi_by_epoch.get((m, e - 1), 1.0)
            match = (int(d["int_weight"] == pubw) if pubw is not None else "")
            if match == 0:
                n_recompute_mismatch += 1
            parts = sorted(d["contrib"], key=lambda p: host_by_addr.get(p[0], p[0]))
            logged = pubs_by_epoch.get(e, {}).get(m)
            row = OrderedDict(base)
            row.update({
                "epoch": e, "epoch_buried": int(bool(buried.get(e, C.epoch_buried(e, L, final_height)))),
                "epoch_start_height": C.epoch_bounds(e, L)[0], "epoch_end_height": C.epoch_bounds(e, L)[1],
                "cluster_head_host": host_by_addr.get(m, m[:10]), "cluster_head_address": m,
                "esg_miner": round(d["esg_miner"], 4), "tau_miner": d["tau_miner"],
                "n_companies": len(parts),
                "companies": " ".join("%s:esg=%.2f:tau=%d:c_i=%.4f" % (host_by_addr.get(p[0], p[0][:6]), p[1], p[2], p[3]) for p in parts),
                "tau_cluster_sum": sum(p[2] for p in parts),
                "c_i_sum": round(sum(p[3] for p in parts), 6),
                "theta_code": d["theta"],
                "theta_thesis": theta_thesis.get(e, 0),
                "W_k_raw": round(d["raw"], 6), "A_k_alloc": round(d["alloc"], 6),
                "R_k_reconciled": round(d["reconciled"], 4),
                "B_k_prev": round(d["balance_prev"], 6), "B_k": round(d["balance"], 6),
                "rho_k": round(d["rho"], 6),
                "rho_k_prev": round(d["rho_prev"], 6) if isinstance(d["rho_prev"], float) else "",
                "feedback_factor": round(d["rho_prev"] * lam_w + (1 - lam_w), 6) if isinstance(d["rho_prev"], float) else "",
                "w_k_recomputed": round(d["w"], 6), "w_k_int_recomputed": d["int_weight"],
                "w_k_published": pubw if pubw is not None else "",
                "w_k_published_prev": prevw if prevw is not None else "",
                "publish_confirm_height": pub_height.get((m, e), ""),
                "publish_logged_height": logged[1] if logged else "",
                "publish_logged_weight": logged[0] if logged else "",
                "recompute_match": match,
                "implied_W_k_raw_from_published": (round(pubw / kappa / (d["rho_prev"] * lam_w + (1 - lam_w)), 6)
                                                   if (pubw is not None and isinstance(d["rho_prev"], float))
                                                   else (round(pubw / kappa, 6) if pubw is not None else "")),
                "implied_raw_delta_over_esg_miner": (round((pubw / kappa / (d["rho_prev"] * lam_w + (1 - lam_w)) - d["raw"]) / d["esg_miner"], 4)
                                                     if (pubw is not None and isinstance(d["rho_prev"], float) and d["esg_miner"])
                                                     else (round((pubw / kappa - d["raw"]) / d["esg_miner"], 4)
                                                           if (pubw is not None and d["esg_miner"]) else "")),
                "malus_M": round(d["malus"], 6), "psi": round(psi, 6),
                "w_after_malus": C.effective_after_malus(pubw, psi) if pubw is not None else "",
                "w_effective_g": round(C.apply_dumping(C.effective_after_malus(pubw, psi), dump_fn), 6) if pubw is not None else "",
                "W_tot_snapshot": round(w_tot_snap, 6) if w_tot_snap else "",
                "share_snapshot": round(snapshot.get(m, 0.0) / w_tot_snap, 6) if w_tot_snap else "",
                "blocks_mined_epoch": obs_by_epoch[e].get(m, 0),
                "blocks_measured_epoch": blocks_by_epoch.get(e, 0),
            })
            we_rows.append(row)
            mrow = OrderedDict(base)
            mrow.update({"epoch": e, "cluster_head_host": host_by_addr.get(m, m[:10]),
                         "cluster_head_address": m, "malus_M": round(d["malus"], 6),
                         "psi": round(psi_by_epoch.get((m, e), 1.0), 6), "n_events": 0,
                         "events": "", "registry_records": len(t["malus_stream"])})
            malus_rows.append(mrow)

    ver_rows = []
    for e in sorted(set(ver_by_epoch) | set(pubs_by_epoch)):
        row = OrderedDict(base)
        row.update({"epoch": e, "n_publications_logged": len(pubs_by_epoch.get(e, {})),
                    "n_hosts_verification_ok": ver_by_epoch[e].get("verification_ok", 0),
                    "n_hosts_verification_failed": ver_by_epoch[e].get("verification_failed", 0),
                    "n_hosts_not_verified": ver_by_epoch[e].get("not_verified", 0)})
        ver_rows.append(row)

    # ---- balance_by_height --------------------------------------------------
    bal_rows = []
    for host in sorted(samples):
        for sh, bal in samples[host]:
            r = OrderedDict(base)
            r.update({"host": host, "height": sh, "kind": "sample", "balance_gas": bal,
                      "epoch": C.epoch_of(sh, L)})
            bal_rows.append(r)
    for r0 in t["reconciliation"]:
        hs = C.inum(r0["send_height"])
        for kind, val in (("reconcile_before", C.fnum(r0["balance_before_gas"])),
                          ("reconcile_after", (C.fnum(r0["balance_before_gas"], 0.0) - C.fnum(r0["sent_gas"], 0.0)))):
            r = OrderedDict(base)
            r.update({"host": r0["miner_host"], "height": hs, "kind": kind,
                      "balance_gas": round(val, 4) if val is not None else "", "epoch": C.epoch_of(hs, L),
                      "sent_gas": r0["sent_gas"]})
            bal_rows.append(r)
    bal_rows.sort(key=lambda r: (r["host"], r["height"] if r["height"] is not None else 0, r["kind"]))

    # ---- write --------------------------------------------------------------
    p2.mkdir(parents=True, exist_ok=True)
    counts = {
        "candidates_long": C.write_csv(p2 / "candidates_long.csv", cand_rows),
        "round_level": C.write_csv(p2 / "round_level.csv", round_rows),
        "epoch_level_wpoa": C.write_csv(p2 / "epoch_level_wpoa.csv", epoch_rows),
        "epoch_level_weight_engine": C.write_csv(p2 / "epoch_level_weight_engine.csv", we_rows),
        "weight_engine_verification": C.write_csv(p2 / "weight_engine_verification.csv", ver_rows),
        "balance_by_height": C.write_csv(p2 / "balance_by_height.csv", bal_rows),
        "malus_epoch": C.write_csv(p2 / "malus_epoch.csv", malus_rows),
    }
    if n_dup:
        warnings.append("%d duplicated score lines ignored (first occurrence kept)" % n_dup)
    if n_argmin_disagree:
        warnings.append("%d rounds where argmin by delay differs from argmin by score" % n_argmin_disagree)
    if phi_mismatch_rounds:
        warnings.append("%d rounds where Phi differs across miners" % phi_mismatch_rounds)
    summary = OrderedDict([
        ("n_measured_blocks", sum(blocks_by_epoch.values())),
        ("n_rounds_with_scores", n_rounds), ("n_rounds_all_candidates_logged", n_full),
        ("n_inversions", n_inv),
        ("inversion_rate", round(n_inv / n_rounds, 6) if n_rounds else ""),
        ("n_time_bar_violations", n_tb_viol),
        ("max_abs_delay_mismatch_s", round(max_mismatch, 6)),
        ("delay_recompute_tolerance_s", DELAY_TOL_S),
        ("n_candidate_rows_delay_mismatch", n_delay_mismatch_rows),
        ("n_rounds_delay_mismatch", len(rounds_with_delay_mismatch)),
        ("rounds_delay_mismatch", sorted(rounds_with_delay_mismatch)),
        ("n_rounds_phi_mismatch", phi_mismatch_rounds),
        ("n_rounds_argmin_delay_vs_score_disagree", n_argmin_disagree),
        ("n_forks", sum(forks_epoch.values())), ("n_competing_blocks", sum(competing_epoch.values())),
        ("n_rejects", sum(rejects_epoch.values())),
        ("n_weight_recompute_mismatches", n_recompute_mismatch),
        ("n_weight_rows", len(we_rows)), ("malus_registry_records", len(t["malus_stream"])),
        ("measured_epochs", sorted(blocks_by_epoch)), ("max_epoch", max_epoch),
    ])
    manifest = OrderedDict(list(base.items()) + [
        ("run_id", man["run_id"]), ("setup_blocks", setup), ("final_height", final_height),
        ("params", man["params"]), ("startup_params", man.get("startup_params", {})),
        ("shadow", man.get("shadow", {})), ("miners", miners), ("epochs", man.get("epochs", [])),
        ("summary", summary), ("row_counts", counts), ("warnings", warnings), ("phase", 2)])
    (p2 / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("%s: phase2 written | rounds %d | inversions %d (%.1f%%) | time-bar violations %d | "
             "max |D_rec-D_log| %.4f s | weight mismatches %d", man["run_id"], n_rounds, n_inv,
             100.0 * n_inv / n_rounds if n_rounds else 0.0, n_tb_viol, max_mismatch, n_recompute_mismatch)
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="risultati", help="pipeline root holding <run>/<area>/phase1")
    ap.add_argument("--only", default="", help="substring filter on <run>/<area>")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s")
    root = Path(args.out).expanduser().resolve()
    found = 0
    for p1 in sorted(root.glob("*/*/phase1")):
        rid = "%s/%s" % (p1.parent.parent.name, p1.parent.name)
        if args.only not in rid:
            continue
        found += 1
        try:
            derive_run(p1, p1.parent / "phase2")
        except Exception as exc:
            LOG.exception("%s: phase2 failed: %s", rid, exc)
    if not found:
        LOG.error("no phase1 directories under %s", root)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
