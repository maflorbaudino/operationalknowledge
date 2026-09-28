# -*- coding: utf-8 -*-
import pandas as pd, re, collections
UP='/root/.claude/uploads/bc7375d9-8385-5523-8bb6-2b2f061d324b/'
def parse_ris(p):
    recs=[];cur=collections.defaultdict(list)
    for line in open(p,encoding='utf-8',errors='ignore'):
        line=line.rstrip('\n')
        m=re.match(r'^([A-Z][A-Z0-9])  - ?(.*)$',line)
        if m:
            k,v=m.groups()
            if k=='ER': recs.append(dict(cur)); cur=collections.defaultdict(list)
            else: cur[k].append(v.strip())
    return recs
def load():
    df=pd.read_csv(UP+'e7317b04-all_study_record_1.csv')
    ris=parse_ris(UP+'9df95a2b-all_study_record.ris')
    assert len(ris)==len(df),(len(ris),len(df))
    norm=lambda s:re.sub(r'\W+','',str(s).lower())
    # comprobar alineación por título
    mis=sum(norm(r['TI'][0])!=norm(t) for r,t in zip(ris,df.Title))
    df['year']=[int(r['PY'][0]) if r.get('PY') and r['PY'][0].isdigit() else None for r in ris]
    df['kw']=['; '.join(r.get('KW',[])) for r in ris]
    df['ris_url']=[r.get('UR',[''])[0] for r in ris]
    return df,mis
if __name__=='__main__':
    df,mis=load(); print('desalineados',mis); print(df.year.describe()); print(df.year.value_counts().sort_index().tail(15))
    print(df.ris_url.str.extract(r'/(\d+)$')[0].notna().sum())
