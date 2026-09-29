"""Read WeChat proof tables locally, preserving page/table-row provenance."""
from pathlib import Path
from datetime import datetime
import hashlib
import re
import pdfplumber
from pypdf import PdfReader
from build_report import cents, classify, SCENARIOS, RULES, summarize

def clean(value):
    return str(value or '').replace('\n','').strip()

def parse_table_row(row,page,table_row,index):
    if len(row)!=8:
        raise ValueError(f'Page {page} table row {table_row}: expected 8 columns')
    tid,time,kind,direction,payment,amount,merchant,mid=[clean(v) for v in row]
    if not re.fullmatch(r'\d{20,64}',tid):
        raise ValueError(f'Page {page} table row {table_row}: invalid transaction ID')
    time=re.sub(r'^(\d{4}-\d\d-\d\d)\s*',r'\1 ',time)
    time=datetime.strptime(time,'%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
    if direction not in ['收入','支出','其他','/','中性交易']:
        raise ValueError(f'Page {page}: unknown direction {direction}')
    direction='中性交易' if direction in ['其他','/'] else direction
    category,rule=classify(kind,merchant,'',direction)
    return dict(row=index,source_page=page,source_table_row=table_row,source_ref=f'PDF 第 {page} 页，表格第 {table_row} 行',
                id=tid,time=time,kind=kind,direction=direction,payment=payment,cents=cents(amount),merchant=merchant,merchant_id=mid,
                item='未提供（PDF）',note='未提供（PDF）',status='未提供（PDF）',category=category,rule=rule,
                refund=direction=='收入' and '退款' in kind,
                scenes=[name for name,words in SCENARIOS if any(w in f'{merchant} {kind}' for w in words)])

def build_pdf(source):
    independent=PdfReader(source)
    first=independent.pages[0].extract_text()
    period=re.search(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) 至 (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',first)
    start,end=[datetime.strptime(v,'%Y-%m-%d %H:%M:%S') for v in period.groups()]
    records,checks=[],[]
    with pdfplumber.open(source) as pdf:
        for page_no,page in enumerate(pdf.pages,1):
            page_records=[]
            for table in page.extract_tables():
                for row_no,row in enumerate(table,1):
                    if not re.fullmatch(r'\d{20,64}',clean(row[0])):
                        if len(row)==8 and any(re.search(r'\d{4}-\d\d-\d\d',str(v)) for v in row[1:]) and clean(row[0])!='交易明细对应时间段':
                            raise ValueError(f'Unrecognized transaction row at page {page_no}, row {row_no}')
                        continue
                    r=parse_table_row(row,page_no,row_no,len(records)+len(page_records)+1)
                    if not start<=datetime.strptime(r['time'],'%Y-%m-%d %H:%M:%S')<=end:
                        raise ValueError('Transaction outside requested interval')
                    page_records.append(r)
            # Independent text extraction counts date lines, excluding the cover period.
            independent_count=len(re.findall(r'^\d{4}-\d\d-\d\d\s*$',independent.pages[page_no-1].extract_text(),re.M))
            checks.append(dict(name=f'第 {page_no} 页笔数（独立文本核验）',source=independent_count,computed=len(page_records),unit='笔'))
            if len(page_records)!=independent_count:
                raise ValueError(f'Page {page_no}: row count {len(page_records)} != independent count {independent_count}')
            independent_amounts=[cents(v) for v in re.findall(r'^([\d,]+\.\d{2})\s*$',independent.pages[page_no-1].extract_text(),re.M)]
            if independent_amounts != [r['cents'] for r in page_records]:
                raise ValueError(f'Page {page_no}: monetary cells differ between text and table extraction')
            checks.append(dict(name=f'第 {page_no} 页金额（独立文本逐笔核验）',source=sum(independent_amounts),computed=sum(r['cents'] for r in page_records),unit='分'))
            records.extend(page_records)
            if page_no%20==0: print(f'PDF extraction: {page_no}/{len(pdf.pages)} pages',flush=True)
    ids=[r['id'] for r in records]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate PDF transaction IDs require review')
    meta=dict(file=source.name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sheet='PDF',header_row=None,
              start=start.strftime('%Y-%m-%d'),end=end.strftime('%Y-%m-%d'),start_time=str(start),end_time=str(end),
              nickname=re.search(r'兹证明：(.*?)（',first)[1],generated=datetime.now().isoformat(timespec='seconds'),
              format='PDF',pages=len(independent.pages),rule_version=RULES['version'],
              missing_fields=['商品','备注','当前状态'],source_totals_available=False)
    return summarize(records,start,end,meta,checks)
