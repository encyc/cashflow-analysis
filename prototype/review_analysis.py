"""Evidence-based summaries of payment statements, without credit scoring."""
from collections import defaultdict

SALARY_WORDS = ('工资', '薪资', '薪酬')
SALARY_EXCLUSIONS = ('退款', '退还', '退回', '冲正', '撤销', '取消', '失败',
                     '工资卡', '非工资', '非薪资', '借款', '贷款')
LARGE_THRESHOLD_CENTS = 1_000_000


def subset(rows):
    return dict(rows=[r['row'] for r in rows], count=len(rows),
                income=sum(r['cents'] for r in rows if r['direction'] == '收入'),
                expense=sum(r['cents'] for r in rows if r['direction'] == '支出'),
                neutral=sum(r['cents'] for r in rows if r['direction'] == '中性交易'))


def analyze_review(records, end):
    salary, evidence = [], []
    for r in records:
        text = ' '.join(str(r.get(k, '')) for k in ('merchant', 'item', 'kind', 'note', 'status'))
        words = [w for w in SALARY_WORDS if w in text]
        if (r['direction'] == '收入' and words and not r.get('refund')
                and not r.get('refund_indicator') and not any(w in text for w in SALARY_EXCLUSIONS)):
            salary.append(r)
            evidence.append(dict(row=r['row'], words=words))
    sources = defaultdict(list)
    flows = defaultdict(list)
    for r in salary:
        sources[(r.get('platform', '微信'), r.get('merchant', ''))].append(r)
    actual = [r for r in records if r['direction'] in ('收入', '支出')]
    for r in actual:
        flows[(r.get('platform', '微信'), r.get('merchant', ''))].append(r)
    months = []
    if records:
        year, month = map(int, min(r['time'][:7] for r in records).split('-'))
        while f'{year:04}-{month:02}' <= end[:7]:
            key = f'{year:04}-{month:02}'
            months.append(dict(month=key, **subset([r for r in salary if r['time'].startswith(key)])))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return dict(version='2026-09-30-review-v1',
                salary=dict(**subset(salary), evidence=evidence, monthly=months,
                            sources=[dict(platform=p, merchant=m, **subset(rows))
                                     for (p, m), rows in sorted(sources.items())]),
                large=dict(threshold_cents=LARGE_THRESHOLD_CENTS,
                           **subset([r for r in actual if r['cents'] >= LARGE_THRESHOLD_CENTS])),
                night=subset([r for r in actual if int(r['time'][11:13]) >= 22 or int(r['time'][11:13]) < 6]),
                flows=[dict(platform=p, merchant=m, **subset(rows))
                       for (p, m), rows in sorted(flows.items())])
