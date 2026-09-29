"""Local feasibility prototype: WeChat XLSX -> auditable standalone HTML."""
from pathlib import Path
from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
from collections import Counter, defaultdict
import calendar
import hashlib
import json
import re
import argparse
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
RULES = json.loads((ROOT/'prototype'/'category_rules.json').read_text())

def cents(value):
    try:
        value = Decimal(str(value).replace('¥', '').replace('￥', '').replace(',', '').strip())
    except InvalidOperation as exc:
        raise ValueError(f'Invalid monetary value: {value}') from exc
    if not value.is_finite() or value < 0 or value != value.quantize(Decimal('.01')):
        raise ValueError(f'Invalid monetary value: {value}')
    return int(value * 100)

def classify(kind, merchant, item, direction):
    if direction == '收入' and '退款' in kind:
        return '退款入账', '交易类型包含“退款”且收支为收入'
    if kind.startswith('亲属卡'):
        return '亲属卡交易', '原始交易类型为亲属卡交易'
    if '红包' in kind:
        return '红包往来', '原始交易类型包含“红包”'
    if kind == '转账' or kind == '二维码收款':
        return '转账往来', '原始交易类型为转账或二维码收款'
    text = f'{merchant} {item}'.lower()
    if merchant in RULES['exact_merchants']:
        category, evidence = RULES['exact_merchants'][merchant]
        return category, f'{RULES["version"]}；{evidence}（规则线索，待核实）'
    for rule in RULES['rules']:
        category, keywords = rule['category'], rule['keywords']
        for word in keywords:
            if word.lower() in text:
                return category, f'{RULES["version"]}；交易对方或商品包含“{word}”（关键词归类，待核实）'
    if merchant in RULES['generic_platforms']:
        return '综合平台（用途待核）', '仅识别到平台名称，未识别出明确消费用途'
    return '未分类', '无明确规则命中，保留原文供核对'

SCENARIOS = [
    ('借贷机构线索', ['马上消费金融','微粒贷','借呗','度小满','招联消费金融','安逸花']),
    ('信用还款线索', ['信用卡还款','花呗还款','花呗主动还款','白条还款','抖音月付']),
    ('租赁线索', ['人人租','爱租机','机蜜','租机']),
    ('回收交易线索', ['转转回收','爱回收','回收宝']),
    ('薪资文字线索', ['工资','薪资','薪酬','代发工资']),
]

def build(source):
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.values)
    hi = next(i for i,r in enumerate(rows) if r[0] == '交易时间' and '交易单号' in r)
    headers = list(rows[hi])
    expected = ['交易时间','交易类型','交易对方','商品','收/支','金额(元)','支付方式','当前状态','交易单号','商户单号','备注']
    if headers != expected:
        raise ValueError(f'Unexpected header: {headers}')
    preamble = '\n'.join(str(r[0] or '') for r in rows[:hi])
    period = re.search(r'起始时间：\[(.*?)\] 终止时间：\[(.*?)\]', preamble)
    start, end = [datetime.strptime(v, '%Y-%m-%d %H:%M:%S') for v in period.groups()]
    records, seen, duplicates = [], {}, []
    raw_records = []
    for row_number, row in enumerate(rows[hi+1:], hi+2):
        if all(v is None for v in row):
            continue
        raw_records.append(row)
        time, kind, merchant, item, direction, amount, payment, status, tid, mid, note = row
        if not isinstance(time, datetime):
            time = datetime.strptime(str(time).strip(), '%Y-%m-%d %H:%M:%S')
        if not start <= time <= end:
            raise ValueError(f'Row {row_number}: outside export interval')
        if direction not in ('收入','支出','中性交易','/'):
            raise ValueError(f'Row {row_number}: unknown direction {direction}')
        if not isinstance(tid, str) or not tid.strip():
            raise ValueError(f'Row {row_number}: transaction ID must be nonempty text')
        if tid in seen:
            if row != seen[tid]:
                raise ValueError(f'Row {row_number}: conflicting duplicate transaction ID')
            duplicates.append(row_number)
            continue
        seen[tid] = row
        category, rule = classify(kind, str(merchant or ''), str(item or ''), direction)
        r = dict(row=row_number, time=time.strftime('%Y-%m-%d %H:%M:%S'), kind=kind,
                 merchant=str(merchant or ''), item=str(item or ''), direction=direction,
                 cents=cents(amount), payment=str(payment or ''), status=str(status or ''),
                 id=tid, merchant_id=str(mid or ''), note=str(note or ''), category=category, rule=rule)
        r['refund'] = direction == '收入' and '退款' in kind
        r['scenes'] = [name for name, keywords in SCENARIOS if any(k in f'{merchant} {item} {kind}' for k in keywords)]
        records.append(r)
    source_count = int(re.search(r'共(\d+)笔记录', preamble)[1])
    checks = [dict(name='原始交易笔数', source=source_count, computed=len(raw_records), unit='笔')]
    for d in ['收入','支出','中性交易']:
        match = re.search(d+r'：(\d+)笔 ([\d.]+)元', preamble)
        raw = [r for r in raw_records if r[4] == d or (d == '中性交易' and r[4] == '/')]
        checks += [dict(name=d+'笔数', source=int(match[1]), computed=len(raw), unit='笔'),
                   dict(name=d+'金额', source=cents(match[2]), computed=sum(cents(r[5]) for r in raw), unit='分')]
    if not all(c['source']==c['computed'] for c in checks):
        raise ValueError('Source reconciliation failed: '+repr(checks))
    meta=dict(file=source.name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sheet=sheet.title,
              header_row=hi+1,start=start.strftime('%Y-%m-%d'),end=end.strftime('%Y-%m-%d'),
              nickname=re.search(r'微信昵称：\[(.*?)\]',preamble)[1],generated=datetime.now().isoformat(timespec='seconds'),
              format='Excel',rule_version=RULES['version'])
    return summarize(records,start,end,meta,checks,len(duplicates))

def summarize(records,start,end,meta,checks,duplicates=0):
    def aggregate(items):
        return {d: dict(count=sum(r['direction']==d for r in items), cents=sum(r['cents'] for r in items if r['direction']==d)) for d in ['收入','支出','中性交易']}
    totals = aggregate(records)
    monthly = []
    cursor = start.date().replace(day=1)
    while cursor <= end.date():
        month_end = cursor.replace(day=calendar.monthrange(cursor.year,cursor.month)[1])
        key = cursor.strftime('%Y-%m')
        items = [r for r in records if r['time'].startswith(key)]
        a = aggregate(items)
        monthly.append(dict(month=key, income=a['收入']['cents'], expense=a['支出']['cents'], count=len(items),
                            refund=sum(r['cents'] for r in items if r['refund']), complete=start.date()<=cursor and month_end<=end.date()))
        cursor = month_end + timedelta(days=1)
    full = [m for m in monthly if m['complete']]
    active_days = set(r['time'][:10] for r in records if r['direction'] in ('收入','支出'))
    days = (end.date()-start.date()).days+1
    longest, run, run_start, longest_start = 0, 0, None, None
    for offset in range(days):
        day = start.date()+timedelta(days=offset)
        if day.isoformat() not in active_days:
            if not run: run_start = day
            run += 1
            if run > longest: longest, longest_start = run, run_start
        else: run=0
    by_party, by_payment, by_category = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in records:
        by_party[r['merchant']].append(r)
        by_payment[r['payment']].append(r)
        if r['direction']=='支出': by_category[r['category']].append(r)
    parties = [dict(name=k, count=len(v), income=sum(r['cents'] for r in v if r['direction']=='收入'), expense=sum(r['cents'] for r in v if r['direction']=='支出')) for k,v in by_party.items()]
    payments = [dict(name=k, count=len(v), income=sum(r['cents'] for r in v if r['direction']=='收入'), expense=sum(r['cents'] for r in v if r['direction']=='支出')) for k,v in by_payment.items()]
    categories = sorted([dict(name=k,count=len(v),cents=sum(r['cents'] for r in v)) for k,v in by_category.items()],key=lambda x:-x['cents'])
    same = defaultdict(lambda: {'收入': [], '支出': []})
    for r in records:
        if r['direction'] in ('收入','支出') and not r['refund'] and '退款' not in r['status'] and '退还' not in r['status']:
            same[(r['time'][:10],r['cents'])][r['direction']].append(r['row'])
    pairs = []
    for (day, amount), bucket in same.items():
        for incoming, outgoing in zip(bucket['收入'],bucket['支出']):
            pairs.append(dict(date=day,cents=amount,income_row=incoming,expense_row=outgoing))
    refund = sum(r['cents'] for r in records if r['refund'])
    summary = dict(income=totals['收入']['cents'], expense=totals['支出']['cents'], neutral=totals['中性交易']['cents'],
                   count=len(records), refund=refund, refund_count=sum(r['refund'] for r in records),
                   net=totals['收入']['cents']-totals['支出']['cents'], non_refund_income=totals['收入']['cents']-refund,
                   days=days, active_days=len(active_days), active_rate=round(len(active_days)/days*100,2),
                   longest_inactive=longest, longest_start=str(longest_start) if longest_start else None,
                   complete_months=len(full), avg_income=round(sum(m['income'] for m in full)/len(full)) if full else None,
                   avg_expense=round(sum(m['expense'] for m in full)/len(full)) if full else None,
                   credit_expense=sum(r['cents'] for r in records if r['direction']=='支出' and '信用卡' in r['payment']),
                   duplicates=duplicates)
    summary['unknown_expense']=sum(c['cents'] for c in categories if c['name']=='未分类')
    summary['platform_unresolved_expense']=sum(c['cents'] for c in categories if c['name']=='综合平台（用途待核）')
    summary['income_count']=totals['收入']['count']
    summary['expense_count']=totals['支出']['count']
    return dict(meta=meta,
                summary=summary, checks=checks, records=records, monthly=monthly,parties=parties,payments=payments,categories=categories,
                hours=[sum(int(r['time'][11:13])==h for r in records) for h in range(24)], pairs=pairs,
                scenes=[dict(name=n,keywords=k,count=sum(n in r['scenes'] for r in records),cents=sum(r['cents'] for r in records if n in r['scenes'])) for n,k in SCENARIOS])

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',nargs='?',type=Path)
    args=parser.parse_args()
    source=args.source or next((ROOT/'template').glob('*.xlsx'))
    if source.suffix.lower()=='.pdf':
        from pdf_parser import build_pdf
        data=build_pdf(source)
    else:
        data=build(source)
    out=ROOT/'outputs'/'wechat-prototype'
    out.mkdir(parents=True,exist_ok=True)
    from render_report import render
    html=render(data)
    text=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    stem='pdf-report' if source.suffix.lower()=='.pdf' else 'report'
    (out/('pdf-analysis.json' if stem=='pdf-report' else 'analysis.json')).write_text(text,encoding='utf-8')
    template=(ROOT/'prototype'/'report.html').read_text(encoding='utf-8')
    (out/(stem+'.html')).write_text(html,encoding='utf-8')
    print(json.dumps({'summary':data['summary'],'checks':data['checks'],'report':str(out/(stem+'.html'))},ensure_ascii=False,indent=2))
