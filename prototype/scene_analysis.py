"""Auditable transaction scenarios, channel grouping and descriptive profiles."""
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import json
import re
from review_analysis import analyze_review

RULES=json.loads(Path(__file__).with_name('scene_rules.json').read_text())
SCENE_NAMES={'rental':'租赁','loan':'借款及还款往来','credit':'信用履约','recycling':'回收及二手平台'}

def words_in(text,words):
    return [w for w in words if w.lower() in text.lower()]

def event_for(r,scene):
    text=f"{r.get('merchant','')} {r.get('item','')} {r.get('kind','')} {r.get('note','')}"
    direction=r['direction']
    if r.get('refund') or r.get('refund_indicator') or r.get('item','').lstrip().startswith('退款') or text.strip().startswith('退款') or '退款' in r.get('kind',''):
        return '退款记录'
    if words_in(text,['解冻','取消','关单','计划有变','资质问题','误操作']):return '取消 / 解冻文字'
    if words_in(text,['冻结','授权']):return '授权 / 冻结文字'
    if scene in ('loan','credit'):
        if direction=='收入' and words_in(text,['红包','奖励','返现','优惠']):return '营销收入'
        if words_in(text,RULES['repayment_words']):
            return '还款文字线索' if direction=='支出' else '还款文字（原标非支出）'
        if direction=='收入' and words_in(text,RULES['disbursement_words']):return '放款文字线索'
        return '信用产品往来（性质待核）' if scene=='credit' else '机构往来（性质待核）'
    if scene=='rental':return '租赁付款线索' if direction=='支出' else ('收入记录' if direction=='收入' else '不计收支记录')
    return '平台收入' if direction=='收入' else ('平台支出' if direction=='支出' else '不计收支记录')

def classify_scene(r):
    merchant=r.get('merchant','');item=r.get('item','');text=f"{merchant} {item} {r.get('kind','')} {r.get('note','')}"
    rental=words_in(merchant,RULES['rental_merchants'])+words_in(item,RULES['rental_items'])
    loan=words_in(merchant,RULES['loan_merchants'])
    loan_product=words_in(text,RULES['loan_products'])
    credit=words_in(text,RULES['credit_products'])
    explicit=words_in(text,RULES['repayment_words']+RULES['disbursement_words'])
    recycle=words_in(merchant,RULES['recycling_merchants'])+words_in(item,RULES['recycling_items'])
    # Rent paid through a bank and rental early repayment remain rental events.
    if rental:scene='rental';evidence=rental
    elif loan_product:scene='loan';evidence=loan_product+explicit
    elif credit:scene='credit';evidence=credit+explicit
    elif (loan or explicit) and not words_in(item,['收钱服务费','收款服务费']):scene='loan';evidence=loan+explicit
    elif recycle:scene='recycling';evidence=recycle
    else:return None
    unresolved=merchant in ('','/','商家精选','未提供（PDF）')
    channel=(merchant+'（渠道待核）' if merchant and merchant!='/' else '渠道待核') if unresolved else merchant
    return dict(row=r['row'],scene=scene,channel=channel,event=event_for(r,scene),
                basis='商户 / 商品 / 类型文字命中：'+'、'.join(dict.fromkeys(evidence)),
                evidence=list(dict.fromkeys(evidence)),inferred=False)

def window_records(records,end,days=None):
    last=date.fromisoformat(end[:10]);first=last-timedelta(days=days-1) if days else date.min
    return [r for r in records if first<=date.fromisoformat(r['time'][:10])<=last]

def aggregate(rows):
    return dict(count=len(rows),income=sum(r['cents'] for r in rows if r['direction']=='收入'),
                expense=sum(r['cents'] for r in rows if r['direction']=='支出'),
                neutral=sum(r['cents'] for r in rows if r['direction']=='中性交易'))

def analyze(records,end):
    by_row={r['row']:r for r in records}
    matches=[hit for r in records if (hit:=classify_scene(r))]
    direct={m['row']:m for m in matches}
    # Link only an exact same-platform order to one unambiguous known rental channel.
    rental_orders=defaultdict(set)
    for m in matches:
        r=by_row[m['row']];order=r.get('merchant_id','')
        if m['scene']=='rental' and len(order)>=8 and '待核' not in m['channel']:
            rental_orders[(r.get('platform','微信'),order)].add(m['channel'])
    for r in records:
        channels=rental_orders.get((r.get('platform','微信'),r.get('merchant_id','')),set())
        if len(channels)==1 and (r['row'] not in direct or (direct[r['row']]['scene']=='rental' and '待核' in direct[r['row']]['channel'])):
            if r['row'] in direct:matches.remove(direct[r['row']])
            matches.append(dict(row=r['row'],scene='rental',channel=next(iter(channels)),event=event_for(r,'rental'),basis='同平台商户单号完全一致，关联唯一已识别租赁渠道',evidence=['同商户单号关联'],inferred=True))
    matches.sort(key=lambda m:m['row'])
    scenes={}
    for key in SCENE_NAMES:
        hits=[m for m in matches if m['scene']==key];rows=[by_row[m['row']] for m in hits]
        scenes[key]={**aggregate(rows),'channels':len({m['channel'] for m in hits}),'rows':[m['row'] for m in hits]}
    review=analyze_review(records,end)
    profiles=[]
    for rule in RULES['profiles']:
        rows=[r for r in records if (not rule.get('direction') or r['direction']==rule['direction']) and
              (r.get('kind') in rule.get('kinds',[]) or words_in(f"{r.get('merchant','')} {r.get('item','')} {r.get('kind','')}",rule['words']))]
        if rule['name']=='薪资文字':rows=[by_row[i] for i in review['salary']['rows']]
        profiles.append(dict(name=rule['name'],basis=rule['note'],rows=[r['row'] for r in rows],**aggregate(rows)))
    night=[r for r in records if r['direction'] in ('收入','支出') and (int(r['time'][11:13])>=22 or int(r['time'][11:13])<6)]
    profiles.append(dict(name='夜间收支',basis='交易发生于 22:00–次日 05:59；不推断作息或职业',rows=[r['row'] for r in night],**aggregate(night)))
    keywords=[]
    for word in RULES['counterparty_words']:
        rows=[r for r in records if word in r.get('merchant','')]
        if rows:keywords.append(dict(name=word,rows=[r['row'] for r in rows],**aggregate(rows)))
    periods={}
    for scene in ('loan','credit'):
        periods[scene]=[]
        for days in [7,15,30,90,180,None]:
            rows=window_records(records,end,days);ids={r['row'] for r in rows}
            hits=[m for m in matches if m['scene']==scene and m['row'] in ids]
            periods[scene].append(dict(days=days,**aggregate([by_row[m['row']] for m in hits]),channels=len({m['channel'] for m in hits}),
                                      repayment=sum(by_row[m['row']]['cents'] for m in hits if m['event']=='还款文字线索'),
                                      marketing=sum(by_row[m['row']]['cents'] for m in hits if m['event']=='营销收入')))
    return dict(version=RULES['version'],anchor=end[:10],matches=matches,scenes=scenes,profiles=profiles,keywords=keywords,
                loan_periods=periods['loan'],credit_periods=periods['credit'],review=review)
