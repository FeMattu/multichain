"""Private-score analysis (§3.5.1) for a regional run: python3 priv.py <run_dir> <log_dir> [setup]"""
import csv, json, math, re, sys, statistics as st, collections as C
import numpy as np

RUN, LOGS = sys.argv[1], sys.argv[2]
SETUP = int(sys.argv[3]) if len(sys.argv) > 3 else 220
rows = lambda p: list(csv.DictReader(open(p)))
addr = json.load(open(RUN + '/addresses.json'))
name = {v: k for k, v in addr.items()}
miners = sorted(k for k in addr if k.startswith('miner'))
blocks = {int(r['height']): r for r in rows(RUN + '/analysis/phase1/blocks.csv')}
hash2h = {r['hash']: h for h, r in blocks.items()}
man = json.load(open(RUN + '/manifest.json'))
T = float(man['chain_params']['target-block-time']); delta = float(man['wpoa_params']['wpoa-sortition-delta'])
Dmax = delta * T
weff = C.defaultdict(dict)
for r in rows(RUN + '/analysis/phase1/round_final_weights.csv'):
    weff[int(r['round_height'])][name.get(r['address'], r['address'])] = float(r['effective_weight_after_malus_and_dumping'])
Hmax = int(sys.argv[4]) if len(sys.argv) > 4 else max(blocks)

RS = re.compile(r'wPoA-sortition height=(\d+) tip=(\w+) score=([0-9.eE+-]+) delay=([0-9.]+)s -> start in (-?[0-9.]+)s \(anchor=(\w+), lag=(-?[0-9.]+)s')
PC = re.compile(r'cand height=(\d+) hash=(\w+) signer=(\w+) score=(\S+) score_norm=(\S+) seq=\d+ recv=(\S+)')
PR = re.compile(r'(\d\d:\d\d:\d\d) \[wpoa-fork\] round height=(\d+) candidates=(\d+) forkscore=\d selected=(\w+) legacy=(\w+) tip=(\w+) differs=(\d)')
PD = re.compile(r'(\d\d:\d\d:\d\d) \[wpoa-fork\] displace height=(\d+) from=(\w+) score=(\S+) seq=\d+ to=(\w+) score=(\S+)')
PF = re.compile(r'defer height=(\d+) hash=(\w+) score=(\S+) own=(\S+)')
PU = re.compile(r'(\d\d:\d\d:\d\d) UpdateTip: +new best=(\w+) +height=(\d+)')

priv = C.defaultdict(dict)   # h -> miner -> (score, delay, lag)
anchors = C.Counter(); nsched = 0; nsched_final = 0
cand = C.defaultdict(dict)   # h -> hash -> (signer, score, first recv over nodes)
cand_node = C.defaultdict(dict)  # (node,h) -> hash -> recv
rounds = []; displ = []; defer = []; defrel = 0; retarget = 0; reorg = {}
def sec(t): a, b, c = map(int, t.split(':')); return a * 3600 + b * 60 + c
for n in miners:
    prev = None; drops = C.Counter()
    for line in open(f'{LOGS}/{n}.log', errors='replace'):
        m = RS.search(line)
        if m:
            nsched += 1; anchors[m[6]] += 1
            if m[2] in hash2h:
                nsched_final += 1
                priv[hash2h[m[2]] + 1][n] = (float(m[3]), float(m[4]), float(m[7]))
            continue
        m = PC.search(line)
        if m:
            h = int(m[1]); s = float(m[4])
            if math.isfinite(s):
                rv = float(m[6])
                old = cand[h].get(m[2])
                cand[h][m[2]] = (m[3], s, min(rv, old[2]) if old else rv)
                cand_node[(n, h)][m[2]] = rv
            continue
        m = PR.search(line)
        if m: rounds.append((n, int(m[2]), int(m[3]), m[4], m[5], m[7])); continue
        m = PD.search(line)
        if m: displ.append((n, int(m[2]), m[3], float(m[4]), m[5], float(m[6]), m[1])); continue
        m = PF.search(line)
        if m: defer.append((n, int(m[1]), float(m[3]), float(m[4]))); continue
        if 'defer-release' in line:
            mh = re.search(r'height=(\d+)', line)
            if mh and SETUP < int(mh[1]) <= Hmax: defrel += 1
            continue
        if 'retarget-abort' in line: retarget += 1; continue
        m = PU.search(line)
        if m:
            h = int(m[3])
            if prev is not None and h <= prev and h > SETUP: drops[prev - h + 1] += 1
            prev = h
    reorg[n] = dict(drops)

out = {}
out['sched_lines'] = nsched; out['sched_on_final_parent'] = nsched_final; out['anchors'] = dict(anchors)
H = [h for h in range(SETUP + 1, Hmax + 1) if h in blocks and len(priv[h]) == len(miners) and len(weff.get(h, {})) == len(miners)]
out['rounds_full'] = len(H); out['rounds_measured'] = len([h for h in range(SETUP + 1, Hmax + 1) if h in blocks])
# (a) E_i and argmin score_norm
E = []; SN = []; des = {}
for h in H:
    w = weff.get(h)
    if not w or len(w) < len(miners): continue
    W = sum(w.values())
    for mm, (s, d, l) in priv[h].items(): E.append(s * w[mm])
    smin = min(v[0] for v in priv[h].values())
    SN.append(1 - math.exp(-W * smin))
for h in H: des[h] = min(priv[h], key=lambda k: priv[h][k][0])
def ks(xs, F):
    xs = sorted(xs); n = len(xs)
    return math.sqrt(n) * max(max((i + 1) / n - F(x), F(x) - i / n) for i, x in enumerate(xs))
out['E_n'] = len(E); out['E_mean'] = st.mean(E); out['E_band'] = 1.96 / math.sqrt(len(E)); out['E_sqrtnD'] = ks(E, lambda x: 1 - math.exp(-x))
out['SN_n'] = len(SN); out['SN_mean'] = st.mean(SN); out['SN_sqrtnD'] = ks(SN, lambda x: x)
# designated shares vs theoretical
dc = C.Counter(des.values()); pt = C.Counter()
for h in H:
    w = weff[h]; W = sum(w.values())
    for k, v in w.items(): pt[k] += v / W
out['designated_share'] = {k: round(dc[k] / len(H), 4) for k in miners}
out['theoretical_share'] = {k: round(pt[k] / len(H), 4) for k in miners}
chi = sum((dc[k] - pt[k]) ** 2 / pt[k] for k in miners); out['designated_chi2_df4'] = chi
inc = {h: name.get(blocks[h - 1]['miner_address']) for h in H}
out['designated_eq_incumbent'] = sum(des[h] == inc[h] for h in H) / len(H)
out['designated_eq_incumbent_expected'] = sum(weff[h].get(inc[h], 0) / sum(weff[h].values()) for h in H) / len(H)
# (b) real inversions
fin = {h: name.get(blocks[h]['miner_address']) for h in H}
inv = [h for h in H if des[h] != fin[h]]
out['inv_n'] = len(inv); out['inv_rate'] = len(inv) / len(H)
k3 = len(H) // 3; thirds = [H[:k3], H[k3:2 * k3], H[2 * k3:]]
out['inv_by_third'] = [(sum(1 for h in t if h in set(inv)), len(t)) for t in thirds]
out['inv_to_incumbent'] = sum(fin[h] == inc[h] for h in inv)
elig = [h for h in inv if des[h] != inc[h]]
out['inv_eligible'] = len(elig); out['inv_eligible_to_incumbent'] = sum(fin[h] == inc[h] for h in elig)
from math import comb
kk, nn = out['inv_eligible_to_incumbent'], len(elig)
out['inv_incumbent_binom_p_vs_025'] = sum(comb(nn, i) * .25 ** i * .75 ** (nn - i) for i in range(kk, nn + 1)) if nn else None
mg = [sorted(v[1] for v in priv[h].values()) for h in inv]
mgi = [(priv[h][fin[h]][1] - priv[h][des[h]][1]) for h in inv if fin[h] in priv[h]]
out['inv_margin_mean'] = st.mean(mgi) if mgi else None; out['inv_margin_max'] = max(mgi) if mgi else None
out['inv_winner'] = dict(C.Counter(fin[h] for h in inv)); out['inv_designated'] = dict(C.Counter(des[h] for h in inv))
G = [sorted(v[1] for v in priv[h].values()) for h in H]; G = [g[1] - g[0] for g in G]
out['G_private_mean'] = st.mean(G); out['G_private_median'] = st.median(G)
out['P_G_lt'] = {t: sum(g < t for g in G) / len(G) for t in (0.1, 0.25, 0.5, 1.0)}
# lag
li = [priv[h][inc[h]][2] for h in H if inc[h] in priv[h]]
lo = [v[2] for h in H for k, v in priv[h].items() if k != inc[h]]
out['lag_incumbent'] = st.mean(li); out['lag_others'] = st.mean(lo)
out['lag_by_third'] = [(st.mean(priv[h][inc[h]][2] for h in t if inc[h] in priv[h]), st.mean(v[2] for h in t for k, v in priv[h].items() if k != inc[h])) for t in thirds]
# (c) forks
HB = [h for h in range(SETUP + 1, Hmax + 1) if h in blocks]
fork = [h for h in HB if len(cand[h]) > 1]
out['fork_rounds'] = len(fork); out['fork_rate'] = len(fork) / len(HB); out['max_blocks_per_height'] = max(len(cand[h]) for h in HB)
out['orphans'] = sum(len(cand[h]) - 1 for h in fork if blocks[h]['hash'] in cand[h])
out['fork_final_is_min'] = sum(1 for h in fork if min(cand[h], key=lambda x: cand[h][x][1]) == blocks[h]['hash'])
out['fork_by_third'] = [sum(1 for h in fork if t[0] <= h <= t[-1]) / sum(1 for h in HB if t[0] <= h <= t[-1]) for t in thirds]
# first arrival
fa_wrong_final = 0; fa_wrong_des = 0; fa_n = 0; fa_inc = 0; fa_inc_elig = 0; fa_elig = 0
fa_by_third = [0, 0, 0]
for h in H:
    if not cand[h]: continue
    fa_n += 1
    fs = min(cand[h], key=lambda x: cand[h][x][2])
    sig = name.get(cand[h][fs][0])
    if fs != blocks[h]['hash']: fa_wrong_final += 1
    if sig != des[h]:
        fa_wrong_des += 1
        fa_inc += sig == inc[h]
        if des[h] != inc[h]: fa_elig += 1; fa_inc_elig += sig == inc[h]
        for i, t in enumerate(thirds):
            if t[0] <= h <= t[-1]: fa_by_third[i] += 1
out['first_arrival_n'] = fa_n; out['first_arrival_ne_final'] = fa_wrong_final; out['first_arrival_ne_designated'] = fa_wrong_des
out['first_arrival_inv_rate'] = fa_wrong_des / fa_n; out['first_arrival_to_incumbent'] = fa_inc / max(fa_wrong_des, 1)
out['first_arrival_to_incumbent_elig'] = (fa_inc_elig, fa_elig)
out['first_arrival_by_third'] = [fa_by_third[i] / len(t) for i, t in enumerate(thirds)]
# native vs score rule, last evaluation per node/height with >=2 candidates
last = {}
for r in rounds:
    if SETUP < r[1] <= Hmax and r[2] >= 2 and r[1] in blocks: last[(r[0], r[1])] = r
ev = list(last.values())
out['eval_contested'] = len(ev)
out['eval_selected_final'] = sum(r[3] == blocks[r[1]]['hash'] for r in ev) / len(ev)
out['eval_legacy_final'] = sum(r[4] == blocks[r[1]]['hash'] for r in ev) / len(ev)
dv = [r for r in ev if r[3] != r[4]]
out['eval_diverge'] = len(dv); out['eval_diverge_heights'] = len(set(r[1] for r in dv))
out['eval_diverge_sel_final'] = sum(r[3] == blocks[r[1]]['hash'] for r in dv) / max(len(dv), 1)
out['eval_diverge_leg_final'] = sum(r[4] == blocks[r[1]]['hash'] for r in dv) / max(len(dv), 1)
dd = [d for d in displ if SETUP < d[1] <= Hmax]
out['displace'] = len(dd); out['displace_heights'] = len(set(d[1] for d in dd)); out['displace_to_better'] = sum(d[5] < d[3] for d in dd) / max(len(dd), 1)
out['defer'] = len([d for d in defer if SETUP < d[1] <= Hmax]); out['defer_release'] = defrel; out['retarget_abort'] = retarget
import datetime
stale = []
for n, h, fr, _, to, _, t in dd:
    rv = cand_node.get((n, h), {}).get(fr)
    if rv is None: continue
    tt = datetime.datetime.utcfromtimestamp(rv); rs = tt.hour * 3600 + tt.minute * 60 + tt.second + tt.microsecond / 1e6
    x = sec(t) - rs
    if x < -43200: x += 86400
    stale.append(x)
out['stale_n'] = len(stale); out['stale_max'] = max(stale); out['stale_median'] = st.median(stale); out['stale_p95'] = float(np.percentile(stale, 95))
out['reorg_depth_hist'] = reorg
# (d) MC on private delays
rng = np.random.default_rng(20260905)
D = np.array([[priv[h][m][1] for m in miners] for h in H])
incidx = np.array([miners.index(inc[h]) if inc[h] in miners else -1 for h in H])
a0 = D.argmin(1)
def mc(sig, adv=0.0, reps=20):
    r = []; ri = []; rie = []
    for _ in range(reps):
        X = D + rng.normal(0, sig, D.shape)
        if adv:
            X[np.arange(len(H)), incidx] -= adv
        a = X.argmin(1); iv = a != a0
        r.append(iv.mean()); ri.append((a[iv] == incidx[iv]).mean())
        e = iv & (a0 != incidx); rie.append((a[e] == incidx[e]).mean())
    return float(np.mean(r)), float(np.mean(ri)), float(np.mean(rie))
out['mc_sym'] = {s: mc(s) for s in (0.2, 0.3, 0.35, 0.4, 0.5)}
out['mc_adv'] = {a: mc(0.35, a) for a in (0.1, 0.3)}
print(json.dumps(out, indent=1, default=str))
