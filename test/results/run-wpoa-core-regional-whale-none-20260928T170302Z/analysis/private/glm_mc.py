import csv, math, sys, importlib.util, numpy as np
sys.path.insert(0,'test/analysis'); from pipeline.stat import longitudinal as lg
A='test/results/run-wpoa-core-regional-whale-none-20260928T170302Z/analysis/'
rows=[r for r in csv.DictReader(open(A+'phase2/epoch_level.csv')) if r['in_setup']=='False']
by={}
for r in rows: by.setdefault(r['epoch'],[]).append(r)
rng=np.random.default_rng(20260905); b1=[]
for _ in range(2000):
    S,T,X=[],[],[]
    for ep,rs in by.items():
        B=int(rs[0]['n_blocks_epoch']); p=np.array([float(r['p_theoretical_blockweighted']) for r in rs]); p/=p.sum()
        o=rng.multinomial(B,p)
        for r,k in zip(rs,o): S.append(int(k)); T.append(B); X.append(math.log(float(r['w_eff_end'])))
    g=lg.binomial_logit_glm(S,T,X)
    if g['converged']: b1.append(g['beta1'])
b1=np.array(b1); print('null beta1 mean %.4f  95%% [%.4f, %.4f]  n=%d  P(>=1.5359)=%.4f'%(b1.mean(),*np.percentile(b1,[2.5,97.5]),len(b1),(b1>=1.5359).mean()))
