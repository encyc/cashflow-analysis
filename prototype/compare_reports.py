"""Build reproducible cross-format reconciliation and procurement review."""
from pathlib import Path
import json
import re
import html
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'wechat-prototype'

def reconcile(excel,pdf):
    start=max(excel['meta']['start'],pdf['meta']['start'])
    end=min(excel['meta']['end'],pdf['meta']['end'])
    def selected(report):
        return {r['id']:r for r in report['records'] if start<=r['time'][:10]<=end}
    a,b=selected(excel),selected(pdf)
    common=sorted(a.keys()&b.keys())
    core=['time','cents','direction','payment','merchant_id']
    counts={key:sum(a[i][key]!=b[i][key] for i in common) for key in core+['merchant','kind','category']}
    differences=[]
    for i in common:
        fields=[k for k in core+['merchant','kind','category'] if a[i][k]!=b[i][k]]
        if fields:
            differences.append(dict(id=i,excel_row=a[i]['row'],pdf_page=b[i]['source_page'],pdf_row=b[i]['source_table_row'],
                                    fields=fields,excel={k:a[i][k] for k in fields},pdf={k:b[i][k] for k in fields}))
    def summary(records):
        return dict(count=len(records),income=sum(r['cents'] for r in records if r['direction']=='收入'),
                    expense=sum(r['cents'] for r in records if r['direction']=='支出'))
    return dict(start=start,end=end,matched=len(common),excel_only=sorted(a.keys()-b.keys()),pdf_only=sorted(b.keys()-a.keys()),
                field_differences=counts,differences=differences,excel_overlap=summary(list(a.values())),pdf_overlap=summary(list(b.values())),
                excel_outside=summary([r for r in excel['records'] if r['id'] not in a]),
                pdf_outside=summary([r for r in pdf['records'] if r['id'] not in b]))

def render(x,p,c,review):
    e=html.escape
    money=lambda n:f'{n/100:,.2f}'
    pct=lambda a,b:f'{a/b*100:.2f}%'
    def table(headers,rows):
        return '<div class="tablewrap"><table><thead><tr>'+''.join('<th>'+e(str(h))+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    def section(id,title,body):return f'<section class="section" id="{id}"><div class="section-title"><h2>{title}</h2></div>{body}</section>'
    css=re.search(r'<style>(.*?)</style>',(ROOT/'prototype'/'report.html').read_text(),re.S)[1]
    nav='<nav class="toolbar"><a class="button" href="report.html">Excel 报告</a><a class="button" href="pdf-report.html">PDF 报告</a><a class="button" href="#procurement">采购验收</a></nav>'
    headline=f'<section class="hero">{nav}<h1 style="margin-top:24px">两份账单对账与采购验收</h1><p>共同区间 {c["start"]} 至 {c["end"]}，匹配 {c["matched"]:,} 笔。</p><p>金额、时间、方向、付款方式、商户单号差异：{sum(c["field_differences"][k] for k in ["cents","time","direction","payment","merchant_id"])} 项。</p><p class="note">两份文件各自生成报告，未将重叠交易叠加。PDF 独立解析，未用 Excel 回填缺失字段。</p></section>'
    rows=[]
    for label,report in [('Excel',x),('PDF',p)]:
        rows.append([label,report['meta']['start']+' 至 '+report['meta']['end'],report['summary']['count'],money(report['summary']['income']),money(report['summary']['expense']),report['summary']['complete_months']])
    period=table(['来源','时间范围','笔数','收入（元）','支出（元）','完整月数'],rows)
    period+=table(['分段','笔数','收入（元）','支出（元）'],[[name,c[key]['count'],money(c[key]['income']),money(c[key]['expense'])] for name,key in [('共同区间 Excel','excel_overlap'),('共同区间 PDF','pdf_overlap'),('Excel 独有时段','excel_outside'),('PDF 独有时段','pdf_outside')]])
    period+=f'<p class="note">共同区间仅 Excel 独有单号 {len(c["excel_only"])} 个，仅 PDF 独有单号 {len(c["pdf_only"])} 个。PDF 无官方总额控制值，采用逐页笔数和逐笔金额的两套提取结果交叉核验，再与 Excel 共同区间核对。</p>'
    mapping={'time':'时间','cents':'金额','direction':'收支方向','payment':'付款方式','merchant_id':'商户单号','merchant':'商户显示名称','kind':'交易类型文字','category':'规则分类'}
    diff=table(['核对字段','共同单号中的差异笔数'],[[mapping[k],v] for k,v in c['field_differences'].items()])
    diff+='<p>文本差异包括表情符号和换行空格。分类差异与 PDF 缺少商品描述有关；保留两端结果，不把名称不同自动判为不同交易，也不默默合并交易对手。</p>'
    diff+='<details><summary>展开全部差异与源行定位</summary>'+table(['单号尾号','Excel 行','PDF 页 / 表行','字段','Excel','PDF'],[[d['id'][-8:],d['excel_row'],str(d['pdf_page'])+' / '+str(d['pdf_row']),mapping[k],d['excel'][k],d['pdf'][k]] for d in c['differences'] for k in d['fields']])+'</details>'
    xs=x['summary'];ps=p['summary']
    classification=table(['范围','未分类金额','未分类占支出','综合平台用途待核','合计待核占支出'],[
        ['Excel 初版','68,787.20','28.21%','未单列','28.21%'],
        ['Excel 本版',money(xs['unknown_expense']),pct(xs['unknown_expense'],xs['expense']),money(xs['platform_unresolved_expense']),pct(xs['unknown_expense']+xs['platform_unresolved_expense'],xs['expense'])],
        ['PDF 本版',money(ps['unknown_expense']),pct(ps['unknown_expense'],ps['expense']),money(ps['platform_unresolved_expense']),pct(ps['unknown_expense']+ps['platform_unresolved_expense'],ps['expense'])]])
    classification+='<p>新增生活缴费、车辆养护、婚庆摄影、医疗药品、数字服务、商超便利等规则。只做交易用途分类，不推断健康状况、婚姻状况或信用能力。分类覆盖率不等于准确率，尚未有独立人工标注集。</p>'
    unknown=[r for r in x['records'] if r['direction']=='支出' and r['category'] in ['未分类','综合平台（用途待核）']]
    unknown.sort(key=lambda r:-r['cents'])
    classification+='<details><summary>展开 Excel 全部用途待核记录</summary>'+table(['Excel 行','日期','商户','商品','金额（元）','类别'],[[r['row'],r['time'][:10],r['merchant'],r['item'],money(r['cents']),r['category']] for r in unknown])+'</details>'
    source_url=review.get('source_url','')
    source_link=f'<a href="{e(source_url)}" rel="noreferrer" target="_blank">外部参考报告</a>' if source_url else '外部参考报告（访问链接不随源码保存）'
    vendor=f'<p>{e(review["scope"])}</p><p>{source_link}，观察日期 {review["observed_at"]}。未向供应商发送任何文件或消息。</p>'
    vendor+=table(['功能','参考报告可见情况','本地样稿','差距或验证事项'],review['matrix'])
    findings='<p>以下是需要供应商解释的现象，尚不能据此认定其算法错误。</p>'+table(['观察','页面证据','待确认问题'],review['observations'])
    procurement='<p>建议先用基础解析与明细回查作为验收基线，再分别验收分类、机构识别和评分。不能只凭页面完整或分数看起来合理就认定有预测能力。以下为拟定验收项，供应商尚未执行。</p>'+table(['编号','项目','测试材料','建议验收标准','当前状态'],review['acceptance'])
    procurement+='<p>采购判断：本地已验证单样本解析、统计和交互展示可实现。付费服务的增量价值，需要由机构库覆盖、独立样本识别效果、外部数据来源、评分验证及服务保障证明。由于没有报价与验证材料，本次不作价格或投资回报结论。</p>'
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>对账与采购验收</title><style>'+css+'main{max-width:1200px;margin:auto;padding:25px}td{vertical-align:top;min-width:100px;max-width:400px;overflow-wrap:anywhere}h1{margin-top:20px}</style></head><body><main>'+headline+section('reconcile','两份文件与时间范围',period)+section('differences','共同区间差异说明',diff)+section('classification','分类改进与剩余项',classification)+section('vendor','与外部服务的功能对照',vendor)+section('questions','四个优先问清的问题',findings)+section('procurement','采购验收清单',procurement)+'<p class="foot">本地核验材料 · 非同样本供应商性能测试</p></main></body></html>'

def main():
    x=json.loads((OUT/'analysis.json').read_text());p=json.loads((OUT/'pdf-analysis.json').read_text())
    c=reconcile(x,p);review=json.loads((ROOT/'prototype'/'vendor_review.json').read_text())
    (OUT/'reconciliation.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
    (OUT/'comparison.html').write_text(render(x,p,c,review))
    print(json.dumps({k:v for k,v in c.items() if k!='differences'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
