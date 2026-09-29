"""Cross-check scene and profile subsets against immutable statement amounts."""
import json
from pathlib import Path
from datetime import date,timedelta
from scene_analysis import analyze
OUT=Path(__file__).resolve().parents[1]/'outputs'/'wechat-prototype'
for filename in ['analysis.json','pdf-analysis.json','person-1-combined.json','person-2-combined.json']:
    d=json.loads((OUT/filename).read_text());a=d['insights'];by={r['row']:r for r in d['records']}
    assert a==analyze(d['records'],d['meta']['end'])
    ids=[h['row'] for h in a['matches']]
    assert len(ids)==len(set(ids)) and set(ids)<=set(by)
    for group in list(a['scenes'].values())+a['profiles']+a['keywords']:
        assert len(group['rows'])==group['count']
        assert set(group['rows'])<=set(by)
        for field,direction in [('income','收入'),('expense','支出'),('neutral','中性交易')]:
            assert sum(by[i]['cents'] for i in group['rows'] if by[i]['direction']==direction)==group[field]
    for period in a['loan_periods']:
        end=date.fromisoformat(a['anchor']);start=end-timedelta(days=period['days']-1) if period['days'] else date.min
        rows=[by[h['row']] for h in a['matches'] if h['scene']=='loan' and start<=date.fromisoformat(by[h['row']]['time'][:10])<=end]
        assert len(rows)==period['count']
        assert sum(r['cents'] for r in rows if r['direction']=='支出')==period['expense']
    print('PASS',filename,{k:(v['count'],v['channels']) for k,v in a['scenes'].items()})
