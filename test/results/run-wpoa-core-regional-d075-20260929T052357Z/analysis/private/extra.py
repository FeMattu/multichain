import csv, json, math, sys, statistics as st, collections as C, re
import numpy as np
sys.path.insert(0,'test/analysis'); from pipeline.stat import longitudinal as lg
RUN=sys.argv[1]; A=RUN+'/analysis/'
rows=lambda p: list(csv.DictReader(open(A+p)))
addr=json.load(open(RUN+'/addresses.json')); nm={v:k for k,v in addr.items()}
fl=lambda x: float(x) if x not in ('',None) else float('nan')
# private E per miner
blocks={int(r['height']):r for r in rows('phase1/blocks.csv')}; h2={r['hash']:h for h,r in blocks.items()}
weff=C.defaultdict(dict)
for r in rows('phase1/round_final_weights.csv'): weff[int(r['round_height'])][nm[r['address']]]=fl(r['effective_weight_after_malus_and_dumping'])
RS=re.compile(r'wPoA-sortition height=(\d+) tip=(\w+) score=([0-9.eE+-]+)')
pr=C.defaultdict(dict)
for m in ['miner-%d'%i for i in range(5)]:
    for l in open(A+'private/%s.log'%m,errors='replace'):
        x=RS.search(l)
        if x and x[2] in h2: pr[h2[x[2]]+1][m]=float(x[3])
Em=C.defaultdict(list)
for h,d in pr.items():
    if h>220 and len(d)==5 and len(weff.get(h,{}))==5:
        for m,s in d.items(): Em[m].append(s*weff[h][m])
print('E per miner',{m:(round(st.mean(v),4),len(v),round(1.96/math.sqrt(len(v)),4)) for m,v in sorted(Em.items())})
# designated share by third for miner-4 and miner-2
H=sorted(h for h,d in pr.items() if h>220 and h in blocks and len(d)==5 and len(weff.get(h,{}))==5)
k=len(H)//3
for i,t in enumerate([H[:k],H[k:2*k],H[2*k:]]):
    des=C.Counter(min(pr[h],key=pr[h].get) for h in t); th=C.Counter()
    for h in t:
        W=sum(weff[h].values())
        for m,v in weff[h].items(): th[m]+=v/W
    print('third',i,{m:(round(des[m]/len(t),3),round(th[m]/len(t),3)) for m in ['miner-2','miner-4']})
# final-chain aggregate on wPoA only blocks
O=C.Counter(); P=C.Counter(); n=0
for h in H:
    O[nm[blocks[h]['miner_address']]]+=1; W=sum(weff[h].values()); n+=1
    for m,v in weff[h].items(): P[m]+=v/W
chi=sum((O[m]-P[m])**2/P[m] for m in P); print('wPoA-only agg n',n,'chi2',round(chi,3),{m:(round(O[m]/n,4),round(P[m]/n,4)) for m in sorted(P)}, 'TV',round(sum(abs(O[m]-P[m]) for m in P)/2/n,4))
# epoch 2 on wPoA-only
O2=C.Counter();P2=C.Counter();n2=0
for h in range(221,300):
    if h in weff and len(weff[h])==5:
        O2[nm[blocks[h]['miner_address']]]+=1; W=sum(weff[h].values()); n2+=1
        for m,v in weff[h].items(): P2[m]+=v/W
chi2=sum((O2[m]-P2[m])**2/P2[m] for m in P2); print('epoch2 wpoa-only n',n2,'chi2',round(chi2,2), {m:(O2[m],round(P2[m],1)) for m in sorted(P2)})
# GLM MC null
el=[r for r in rows('phase2/epoch_level.csv') if r['in_setup']=='False']
by=C.defaultdict(list)
for r in el: by[r['epoch']].append(r)
rng=np.random.default_rng(20260905); b1=[]
for _ in range(1000):
    S,T,X=[],[],[]
    for ep,rs in by.items():
        B=int(rs[0]['n_blocks_epoch']); p=np.array([fl(r['p_theoretical_blockweighted']) for r in rs]); p/=p.sum()
        o=rng.multinomial(B,p)
        for r,kk in zip(rs,o): S.append(int(kk)); T.append(B); X.append(math.log(fl(r['w_eff_end'])))
    g=lg.binomial_logit_glm(S,T,X)
    if g['converged']: b1.append(g['beta1'])
b1=np.array(b1); print('GLM null mean %.4f 95%% [%.4f, %.4f] n=%d P(<=1.048)=%.3f'%(b1.mean(),*np.percentile(b1,[2.5,97.5]),len(b1),(b1<=1.048).mean()))
# K2 residual correlations
res={(r['epoch'],r['validator_address']):fl(r['residual']) for r in rows('phase3/weight_election_residuals.csv')}
eg=rows('phase2/epoch_engine.csv')
def sp(a,b):
    a=np.array(a);b=np.array(b); ra=np.argsort(np.argsort(a)); rb=np.argsort(np.argsort(b)); r=np.corrcoef(ra,rb)[0,1]; n=len(a)
    t=r*math.sqrt((n-2)/(1-r*r)); from math import erf; p=2*(1-0.5*(1+erf(abs(t)/math.sqrt(2)))); return round(r,3),round(p,3),n
pairs=[(r,res[(r['epoch'],r['cluster_head_address'])]) for r in eg if (r['epoch'],r['cluster_head_address']) in res]
for c in ['earnings_g_k','income','miner_activity','companies_contribution_sum','R_k','return_rate_rho','W_k_raw','w_k_published']:
    print('K2',c,sp([fl(r[c]) for r,_ in pairs],[x for _,x in pairs]))
# concentration
ec=[r for r in rows('phase2/epoch_concentration.csv')]
print(ec[0].keys())
