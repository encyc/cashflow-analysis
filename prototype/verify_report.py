"""Independent source-to-output acceptance checks for this feasibility sample."""
from pathlib import Path
from decimal import Decimal
import json
import re
import subprocess
import tempfile
import openpyxl

root=Path(__file__).resolve().parents[1]
out=root/'outputs'/'wechat-prototype'
data=json.loads((out/'analysis.json').read_text())
source=next((root/'template').glob('*.xlsx'))
rows=list(openpyxl.load_workbook(source,read_only=True,data_only=True).active.values)[18:]
s=data['summary']
assert len(rows)==s['count']==1854
for direction,key in [('收入','income'),('支出','expense')]:
    value=sum(Decimal(str(row[5])) for row in rows if row[4]==direction)*100
    assert value==s[key],(direction,value,s[key])
    assert sum(m[key] for m in data['monthly'])==value
    assert sum(m[key] for m in data['parties'])==value
    assert sum(m[key] for m in data['payments'])==value
assert sum(c['cents'] for c in data['categories'])==s['expense']
refund_rows=[row for row in rows if row[4]=='收入' and '退款' in row[1]]
assert len(refund_rows)==s['refund_count']==60
assert sum(Decimal(str(row[5])) for row in refund_rows)*100==s['refund']==1474181
assert s['non_refund_income']+s['refund']==s['income']
assert s['net']==-21045829
assert len(data['monthly'])==13 and s['complete_months']==12
assert data['monthly'][-1]['month']=='2026-09' and not data['monthly'][-1]['complete']
assert s['days']==366
assert s['active_days']==len({row[0].date() for row in rows})==361
assert sum(data['hours'])==1854
assert all(isinstance(r['id'],str) for r in data['records'])
assert len({r['id'] for r in data['records']})==1854
for record in data['records']:
    original=rows[record['row']-19]
    assert record['id']==original[8]
    assert record['cents']==Decimal(str(original[5]))*100
    assert record['merchant']==original[2]
    assert record['status']==original[7]
assert any(r['direction']=='支出' and '已全额退款'==r['status'] for r in data['records'])
assert all(c['source']==c['computed'] for c in data['checks'])
html=(out/'report.html').read_text()
embedded=re.search(r'<script id="report-data" type="application/json">(.*?)</script>',html,re.S)[1]
assert json.loads(embedded)==data
assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://',html)
script=re.findall(r'<script>(.*?)</script>',html,re.S)[0]
node='/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
with tempfile.NamedTemporaryFile(suffix='.js',mode='w') as f:
    f.write(script); f.flush()
    subprocess.run([node,'--check',f.name],check=True)
print('PASS: 1,854 source rows preserved; totals, refunds, months, parties, payments, categories, dates, IDs and embedded report data verified; JavaScript syntax valid.')

pdf=json.loads((out/'pdf-analysis.json').read_text())
assert pdf['summary']['count']==1889
assert len(pdf['checks'])==156 and all(c['source']==c['computed'] for c in pdf['checks'])
assert pdf['summary']['income']==3330416 and pdf['summary']['expense']==23549226
assert pdf['summary']['refund_count']==55 and pdf['summary']['refund']==1464168
assert all(r['status']=='未提供（PDF）' and r['item']=='未提供（PDF）' and r['note']=='未提供（PDF）' for r in pdf['records'])
assert len({r['id'] for r in pdf['records']})==1889
assert set(r['source_page'] for r in pdf['records'])==set(range(1,79))
pdf_html=(out/'pdf-report.html').read_text()
assert json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',pdf_html,re.S)[1])==pdf
with tempfile.NamedTemporaryFile(suffix='.js',mode='w') as f:
    f.write(re.findall(r'<script>(.*?)</script>',pdf_html,re.S)[0]);f.flush()
    subprocess.run([node,'--check',f.name],check=True)
c=json.loads((out/'reconciliation.json').read_text())
assert c['matched']==1702 and not c['excel_only'] and not c['pdf_only']
assert all(c['field_differences'][k]==0 for k in ['time','cents','direction','payment','merchant_id'])
assert c['excel_overlap']==c['pdf_overlap']
assert c['excel_outside']['count']==152 and c['pdf_outside']['count']==187
for d in (data,pdf):
    assert sum(m['income'] for m in d['monthly'])==d['summary']['income']
    assert sum(m['expense'] for m in d['monthly'])==d['summary']['expense']
    assert sum(m['cents'] for m in d['categories'])==d['summary']['expense']
print('PASS: 78 PDF pages, 1,889 rows, 156 page checks, preserved missing fields, 1,702 matching IDs and cross-format core fields verified.')
