"""Parse new proofs, group by certified identity, publish one report per person."""
from pathlib import Path
from datetime import datetime
import copy
import hashlib
from html import escape
import json
import re
from pypdf import PdfReader
from build_report import ROOT, summarize, RULES
from pdf_parser import build_pdf
from alipay_parser import build_alipay

OUT=ROOT/'outputs'/'wechat-prototype'

def identity(source):
    text=PdfReader(source).pages[0].extract_text()
    match=re.search(r'兹证明[:：]\s*(.*?)\s*[（(](?:居民身份证|证件号码)[:：]\s*([0-9Xx]+)[）)]',text)
    if not match:raise ValueError(f'Certified identity not found: {source.name}')
    # The document number is used only in memory; never included in the report or logs.
    return match[1].strip(),match[2].upper()

def validate_identity(a,b):
    if not a[0] or not a[1] or a!=b:raise ValueError('Certified identities do not match')

def merge_records(records):
    seen={};result=[];duplicates=0
    provenance={'row','source_row','source_page','source_table_row','source_ref','source_file','source_sha256'}
    for record in records:
        key=(record['platform'],record.get('source_sha256',record.get('source_file','')),record.get('source_page'),record.get('source_table_row'),record.get('source_ref'))
        if key in seen:
            old=seen[key]
            if {k:v for k,v in old.items() if k not in provenance}!={k:v for k,v in record.items() if k not in provenance}:
                raise ValueError('Conflicting record at the same source location')
            duplicates+=1;continue
        seen[key]=record;result.append(copy.deepcopy(record))
    result.sort(key=lambda r:(r['time'],r['platform'],r['id']),reverse=True)
    order_counts={}
    for r in result:
        key=(r['platform'],r['id']);order_counts[key]=order_counts.get(key,0)+1
    for i,r in enumerate(result,1):
        r['source_row']=r['row'];r['row']=i
        r['same_order_records']=order_counts[(r['platform'],r['id'])]
    return result,duplicates

def combine(reports,person):
    starts=[datetime.fromisoformat(d['meta']['start_time']) for d in reports]
    ends=[datetime.fromisoformat(d['meta']['end_time']) for d in reports]
    records,duplicates=merge_records([r for d in reports for r in d['records']])
    checks=[{**c,'name':d['meta']['platform']+' · '+c['name']} for d in reports for c in d['checks']]
    sources=[dict(meta=d['meta'],summary=d['summary']) for d in reports]
    meta=dict(format='合并 PDF',nickname=person,start=str(min(starts).date()),end=str(max(ends).date()),
              start_time=str(min(starts)),end_time=str(max(ends)),common_start=str(max(starts)),common_end=str(min(ends)),
              generated=datetime.now().isoformat(timespec='seconds'),rule_version=RULES['version'],
              pages=sum(d['meta']['pages'] for d in reports),sources=sources,identity_check='两份证明的姓名与证件号码一致（号码不输出）')
    data=summarize(records,min(starts),max(ends),meta,checks,duplicates)
    # Monthly averages require both sources to cover the full calendar month.
    for month in data['monthly']:
        month['complete']=all(next(m for m in d['monthly'] if m['month']==month['month'])['complete'] if any(m['month']==month['month'] for m in d['monthly']) else False for d in reports)
    full=[m for m in data['monthly'] if m['complete']]
    data['summary'].update(complete_months=len(full),avg_income=round(sum(m['income'] for m in full)/len(full)) if full else None,avg_expense=round(sum(m['expense'] for m in full)/len(full)) if full else None,
        neutral_count=sum(r['direction']=='中性交易' for r in records),
        repeated_order_groups=len({(r['platform'],r['id']) for r in records if r['same_order_records']>1}),
        neutral_refund_count=sum(r['direction']=='中性交易' and r['refund_indicator'] for r in records),
        neutral_refund=sum(r['cents'] for r in records if r['direction']=='中性交易' and r['refund_indicator']))
    if not duplicates:
        for field,unit in [('count','笔'),('income','分'),('expense','分'),('neutral','分')]:
            total=sum(d['summary'][field] for d in reports)
            checks.append(dict(name='两平台合并核验 · '+field,source=total,computed=data['summary'][field],unit=unit))
            if total!=data['summary'][field]:raise ValueError('Merged totals inconsistent')
    return data

def write_report(data,slug):
    from render_report import render
    html=render(data)
    (OUT/(slug+'.json')).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    (OUT/(slug+'.html')).write_text(html)


def write_index(manifest):
    template=(ROOT/'prototype'/'report.html').read_text()
    css=re.search(r'<style>(.*?)</style>',template,re.S)[1]
    cards=[]
    def money(value):return f'{value/100:,.2f}'
    for entry in manifest:
        s=entry['summary']
        cards.append(f'''<section class="section"><div class="section-title"><h2>{escape(entry['name'])}</h2><span class="tag">微信 + 支付宝</span></div><p class="muted">2025-10-01 至 2026-09-28 · {s['count']:,} 笔记录</p><div class="metric-row"><div><small>原始收入（元）</small><strong class="income">{money(s['income'])}</strong></div><div><small>原始支出（元）</small><strong class="expense">{money(s['expense'])}</strong></div></div><p class="note">不计收支 / 其他：{s['neutral_count']:,} 笔，{money(s['neutral'])} 元。</p><a class="button primary" href="{entry['file']}">查看流水报告 →</a></section>''')
    html='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>双平台流水 · 报告目录</title><style>'''+css+'''</style></head><body><header><div class="brand">流水分析</div><span class="header-note">个人流水 · 审核参考</span></header><main style="max-width:1080px;margin:auto;padding:28px 16px"><section class="hero"><span class="tag">审核报告目录</span><h1 style="margin-top:14px">个人流水分析报告</h1><p class="muted">选择审核对象，查看微信与支付宝的收支情况、交易场景及流水明细。</p><p class="note">收入包含账单列为收入的退款；收支差额不等同于净现金流或账户余额。</p></section>'''+''.join(cards)+'''<p class="foot">流水分析报告 · 供审核参考</p></main></body></html>'''
    (OUT/'combined.html').write_text(html)

def main():
    sources=sorted((ROOT/'template').glob('*20251001*.pdf'))
    groups={}
    for source in sources:
        who=identity(source)
        platform='支付宝' if source.name.startswith('支付宝') else '微信'
        print(f'Parsing {who[0]} / {platform}',flush=True)
        data=build_alipay(source) if platform=='支付宝' else build_pdf(source)
        data['meta']['platform']=platform
        for r in data['records']:
            r.update(platform=platform,source_file=source.name,source_sha256=data['meta']['sha256'],source_ref=source.name+' · '+r['source_ref'])
            r.setdefault('raw_direction','其他' if r['direction']=='中性交易' else r['direction'])
            r.setdefault('refund_indicator',r['refund'])
        groups.setdefault(who,[]).append(data)
    manifest=[]
    for i,(who,reports) in enumerate(sorted(groups.items()),1):
        if sorted(d['meta']['platform'] for d in reports)!=['微信','支付宝']:raise ValueError('Each person must have one WeChat and one Alipay proof')
        for d in reports:validate_identity(who,identity(ROOT/'template'/d['meta']['file']))
        data=combine(reports,who[0]);slug=f'person-{i}-combined'
        for d in reports:
            suffix='wechat' if d['meta']['platform']=='微信' else 'alipay'
            (OUT/f'person-{i}-{suffix}.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
        write_report(data,slug)
        manifest.append(dict(name=who[0],file=slug+'.html',summary=data['summary']))
        print(json.dumps(manifest[-1],ensure_ascii=False),flush=True)
    write_index(manifest)
    (OUT/'combined-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
