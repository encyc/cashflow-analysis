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
    review=a['review']
    for group in list(a['scenes'].values())+a['profiles']+a['keywords']+[review[k] for k in ('salary','large','night')]+review['salary']['monthly']+review['salary']['sources']+review['flows']:
        assert len(group['rows'])==group['count']
        assert set(group['rows'])<=set(by)
        for field,direction in [('income','收入'),('expense','支出'),('neutral','中性交易')]:
            assert sum(by[i]['cents'] for i in group['rows'] if by[i]['direction']==direction)==group[field]
    for scene in ('loan','credit'):
        for period in a[scene+'_periods']:
            end=date.fromisoformat(a['anchor']);start=end-timedelta(days=period['days']-1) if period['days'] else date.min
            hits=[h for h in a['matches'] if h['scene']==scene and start<=date.fromisoformat(by[h['row']]['time'][:10])<=end]
            rows=[by[h['row']] for h in hits]
            assert len(rows)==period['count']
            for field,direction in [('income','收入'),('expense','支出'),('neutral','中性交易')]:
                assert sum(r['cents'] for r in rows if r['direction']==direction)==period[field]
            assert period['repayment']==sum(by[h['row']]['cents'] for h in hits if h['event']=='还款文字线索')
            assert period['marketing']==sum(by[h['row']]['cents'] for h in hits if h['event']=='营销收入')
    actual=[r for r in by.values() if r['direction'] in ('收入','支出')]
    assert review['large']['rows']==[r['row'] for r in actual if r['cents']>=1_000_000]
    assert review['night']['rows']==[r['row'] for r in actual if int(r['time'][11:13])>=22 or int(r['time'][11:13])<6]
    flow_ids=[i for g in review['flows'] for i in g['rows']]
    assert len(flow_ids)==len(set(flow_ids))==len(actual)
    assert set(flow_ids)=={r['row'] for r in actual}
    for groups in (review['salary']['monthly'],review['salary']['sources']):
        ids=[i for g in groups for i in g['rows']]
        assert len(ids)==len(set(ids))==review['salary']['count']
        assert set(ids)==set(review['salary']['rows'])
    print('PASS',filename,{k:(v['count'],v['channels']) for k,v in a['scenes'].items()})
