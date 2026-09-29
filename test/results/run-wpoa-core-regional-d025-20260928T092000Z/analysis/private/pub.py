"""Public-pipeline statistics for ANALISI.md: python3 pub.py <run_dir>"""
import csv, json, math, sys, statistics as st, collections as C
import numpy as np
RUN = sys.argv[1]; A = RUN + '/analysis/'
rows = lambda p: list(csv.DictReader(open(A + p)))
addr = json.load(open(RUN + '/addresses.json')); nm = {v: k for k, v in addr.items()}
fl = lambda x: float(x) if x not in ('', None, 'nan') else float('nan')
out = {}
def ks(xs, F):
    xs = sorted(xs); n = len(xs)
    return math.sqrt(n) * max(max((i + 1) / n - F(x), F(x) - i / n) for i, x in enumerate(xs))
cl = [r for r in rows('phase2/candidate_long.csv') if r.get('in_setup', 'False') == 'False']
E = [fl(r['score_public']) * fl(r['weight_effective']) for r in cl]
out['A1_n'] = len(E); out['A1_mean'] = st.mean(E); out['A1_band'] = 1.96 / math.sqrt(len(E)); out['A1_sqrtnD'] = ks(E, lambda x: 1 - math.exp(-x))
byh = C.defaultdict(list)
for r in cl: byh[r['height']].append(r)
mn = [min(fl(r['score_norm_public']) for r in v) for v in byh.values()]
out['A2_n'] = len(mn); out['A2_mean'] = st.mean(mn); out['A2_sqrtnD'] = ks(mn, lambda x: x)
out['A2_winner_rows_mean'] = st.mean(fl(r['score_norm_public']) for r in cl if r['is_winner'] == 'True')
mm = [abs(fl(r['score_norm_mismatch_public'])) for r in cl]; out['A3_max'] = max(mm); out['A3_nonzero'] = sum(x > 1e-9 for x in mm)
dm = [abs(fl(r['delay_mismatch_public_s'])) for r in cl]; out['B_max'] = max(dm); out['B_n'] = len(dm); out['B_over'] = sum(x > 0.0015 for x in dm)
out['weff_eq_raw'] = sum(abs(fl(r['weight_effective']) - fl(r['weight_raw'])) < 1e-9 for r in cl)
# round level
rl = [r for r in rows('phase2/round_level.csv') if r['in_setup'] == 'False']
dt = [fl(r['dt_prev_s']) for r in rl if r['dt_prev_s']]
out['dt_n'] = len(dt); out['dt_mean'] = st.mean(dt); out['dt_sd'] = st.stdev(dt); out['dt_min'] = min(dt); out['dt_max'] = max(dt); out['dt_median'] = st.median(dt)
k = len(dt) // 3; out['dt_thirds'] = [st.mean(dt[:k]), st.mean(dt[k:2 * k]), st.mean(dt[2 * k:])]
ep = C.defaultdict(list)
for r in rl:
    if r['dt_prev_s']: ep[int(r['epoch'])].append(fl(r['dt_prev_s']))
em = {e: st.mean(v) for e, v in ep.items()}; out['dt_epoch_range'] = (min(em.values()), max(em.values()))
out['dt_epoch_first_last'] = (em[min(em)], em[max(em)])
phi = [fl(r['phi_s']) for r in rl]
out['phi_mean'] = st.mean(phi); out['phi_sd'] = st.stdev(phi); out['phi_min'] = min(phi); out['phi_max'] = max(phi)
out['phi_distinct'] = len(set(phi)); out['phi_sat'] = sum(abs(p) >= 4 - 1e-9 for p in phi)
out['phi_abs_lt05'] = sum(abs(p) < 0.5 for p in phi) / len(phi); out['phi_abs_gt1'] = sum(abs(p) > 1 for p in phi)
sg = [1 for a, b in zip(phi, phi[1:]) if a * b < 0]; out['phi_sign_change'] = len(sg) / (len(phi) - 1)
x = np.array(phi); out['phi_ac1'] = float(np.corrcoef(x[:-1], x[1:])[0, 1])
rt = [fl(r['residual_true_s']) for r in rl if r['residual_true_s']]
k = len(rt) // 3; out['res_true_mean'] = st.mean(rt); out['res_true_sd'] = st.stdev(rt)
out['res_true_sd_thirds'] = [st.stdev(rt[:k]), st.stdev(rt[k:2 * k]), st.stdev(rt[2 * k:])]
dtr = [fl(r['delay_true_s']) for r in rl if r['delay_true_s']]; out['delay_true_mean'] = st.mean(dtr)
out['true_winner_mismatch'] = sum(r['true_winner_mismatch'] == 'True' for r in rl); out['verdict_true'] = dict(C.Counter(r['verdict_true'] for r in rl))
out['txcount_mean'] = st.mean(fl(r['txcount']) for r in rl)
# first-10-blocks-of-epoch slowdown
first = [fl(r['dt_prev_s']) for r in rl if r['dt_prev_s'] and (int(r['height']) % 100) < 10]
rest = [fl(r['dt_prev_s']) for r in rl if r['dt_prev_s'] and (int(r['height']) % 100) >= 10]
out['dt_first10'] = st.mean(first); out['dt_rest'] = st.mean(rest); out['dt_first10_max'] = max(first)
# aggregate shares
ev = rows('phase3/wpoa_epoch_validators.csv')
wt = [r for r in rows('phase3/wpoa_epoch_tests.csv')]
out['epoch_tests_all'] = [r for r in wt if r['epoch'] == 'all'][0]
ew = [r for r in wt if r['epoch'] != 'all']
out['gof_rej'] = [(r['epoch'], r['gof_p_value'], r['gof_mc_round_by_round_p']) for r in ew if r['gof_reject_alpha05'] == 'True']
out['gof_mc_rej'] = sum(fl(r['gof_mc_round_by_round_p']) < 0.05 for r in ew)
out['share_changes'] = sum(r['share_changes_within_epoch'] == 'True' for r in ew)
out['L_rej'] = sum(fl(r['L_max_mc_p_value']) < 0.05 for r in ew); out['rep_rej'] = sum(fl(r['repeat_prob_mc_p_value']) < 0.05 for r in ew) if 'repeat_prob_mc_p_value' in ew[0] else None
ec = [r for r in ev if r['epoch'] != 'all']
out['wilson_n'] = len(ec); out['wilson_viol'] = sum(r['p_theoretical_inside_wilson95'] == 'False' for r in ec)
out['wilson_viol_by'] = dict(C.Counter(nm[r['validator_address']] for r in ec if r['p_theoretical_inside_wilson95'] == 'False'))
out['wilson_viol_epochs'] = sorted(set(int(r['epoch']) for r in ec if r['p_theoretical_inside_wilson95'] == 'False'))
out['wilson_width'] = st.mean(fl(r['wilson95_width']) for r in ec)
n = len(ec); kk = out['wilson_viol']
out['wilson_binom_p_upper'] = sum(math.comb(n, i) * .05 ** i * .95 ** (n - i) for i in range(kk, n + 1))
# standardized residuals
z = []; zb = C.defaultdict(list)
for r in ec:
    if int(r['epoch']) == max(int(x['epoch']) for x in ec): continue
    p = fl(r['p_theoretical']); B = fl(r['n_blocks']); O = fl(r['O_i'])
    zz = (O - B * p) / math.sqrt(B * p * (1 - p)); z.append(zz); zb[nm[r['validator_address']]].append(zz)
out['z_sd'] = st.stdev(z); out['z_sd_by'] = {k: round(st.stdev(v), 3) for k, v in sorted(zb.items())}; out['z_mean_by'] = {k: round(st.mean(v), 3) for k, v in sorted(zb.items())}
agg = [r for r in ev if r['epoch'] == 'all']
out['agg'] = {nm[r['validator_address']]: (r['p_theoretical'], r['p_hat'], r['wilson95_low'], r['wilson95_high'], r['O_i'], r['n_blocks']) for r in agg}
# epoch 2 recount on wPoA-only blocks
bl = [r for r in rows('phase1/blocks.csv')]
e2 = [r for r in bl if r['epoch'] == '2']
out['epoch2_heights'] = (min(int(r['height']) for r in e2), max(int(r['height']) for r in e2), sum(r['in_setup'] == 'True' for r in e2))
# weight engine
eg = rows('phase2/epoch_engine.csv')
e1 = []; e2_ = []
for r in eg:
    W = fl(r['miner_esg_score']) * (fl(r['miner_activity']) + fl(r['companies_contribution_sum']))
    e1.append(abs(W - fl(r['W_k_raw'])) / fl(r['W_k_raw']))
    if r['rho_prev']:
        wf = fl(r['W_k_raw']) * (fl(r['rho_prev']) * fl(r['lambda_w']) + 1 - fl(r['lambda_w']))
        e2_.append(abs(wf - fl(r['w_k_final'])) / fl(r['w_k_final']))
out['id_W_err'] = max(e1); out['id_w_err'] = max(e2_)
rho = [fl(r['return_rate_rho']) for r in eg if int(r['epoch']) >= 2]
out['rho_mean'] = st.mean(rho); out['rho_sd'] = st.stdev(rho); out['rho_max'] = max(rho); out['rho_min'] = min(rho); out['rho_zero'] = sum(x == 0 for x in rho) / len(rho)
fac = [0.99 * x + 0.01 for x in rho]; out['fac_range'] = (min(fac), max(fac))
esg = C.defaultdict(set)
for r in eg: esg[nm[r['cluster_head_address']]].add(r['miner_esg_score'])
out['esg'] = {k: sorted(v) for k, v in sorted(esg.items())}
# weights max/min per epoch (measured)
we = C.defaultdict(list)
for r in eg:
    if int(r['epoch']) >= 2: we[int(r['epoch'])].append(fl(r['w_k_published']))
rat = [max(v) / min(v) for v in we.values()]; out['wratio_mean'] = st.mean(rat); out['wratio_range'] = (min(rat), max(rat))
wm = C.defaultdict(list)
for r in eg:
    if int(r['epoch']) >= 2: wm[nm[r['cluster_head_address']]].append(fl(r['w_k_published']))
out['w_mean_by'] = {k: round(st.mean(v)) for k, v in sorted(wm.items())}
def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); r = np.corrcoef(ra, rb)[0, 1]
    n = len(a); t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    return float(r), n
out['w_trend'] = {k: round(spearman(list(range(len(v))), v)[0], 3) for k, v in wm.items()}
# K correlations
e_rows = [r for r in eg if int(r['epoch']) >= 2]
for c in ['w_k_published', 'W_k_raw', 'earnings_g_k', 'companies_contribution_sum', 'income', 'miner_activity']:
    out['K1_' + c] = round(spearman([fl(r[c]) for r in e_rows], [fl(r['n_blocks_won_epoch']) for r in e_rows])[0], 3)
res = {(r['epoch'], r['validator_address']): fl(r['residual']) if 'residual' in r else None for r in rows('phase3/weight_election_residuals.csv')}
out['res_cols'] = list(rows('phase3/weight_election_residuals.csv')[0].keys())
print(json.dumps(out, indent=1, default=str))
