"""Alipay proof PDF adapter. Preserve the issuer's income/expense conventions."""
from datetime import datetime
import hashlib
import re
import pdfplumber
from pypdf import PdfReader
from build_report import cents, classify, SCENARIOS, RULES, summarize
from pdf_parser import clean


def parse_alipay_row(row, page, table_row, index):
    if len(row) != 8:
        raise ValueError(f'Alipay page {page}: expected 8 columns')
    raw_direction, merchant, item, payment, amount, tid, mid, time = map(clean, row)
    if raw_direction not in ('收入', '支出', '不计收支'):
        raise ValueError(f'Alipay page {page}: unknown direction {raw_direction}')
    if not re.fullmatch(r'\d{16,}(?:_[A-Za-z0-9_]+)?', tid):
        raise ValueError(f'Alipay page {page}: invalid order ID')
    time = re.sub(r'^(\d{4}-\d\d-\d\d)\s*', r'\1 ', time)
    time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S').isoformat(sep=' ')
    direction = '中性交易' if raw_direction == '不计收支' else raw_direction
    refund_indicator = item.startswith('退款')
    kind = '退款' if refund_indicator else ('转账' if item == '转账' else '未提供（PDF）')
    category, rule = classify(kind, merchant, item, direction)
    return dict(row=index, source_page=page, source_table_row=table_row,
                source_ref=f'PDF 第 {page} 页，表格第 {table_row} 行',
                platform='支付宝', raw_direction=raw_direction, direction=direction,
                id=tid, merchant_id=mid, time=time, merchant=merchant, item=item,
                payment=payment, cents=cents(amount), kind=kind,
                kind_basis='根据商品说明标记，原 PDF 无交易类型列',
                status='未提供（PDF）', note='未提供（PDF）', category=category, rule=rule,
                refund=refund_indicator and direction=='收入', refund_indicator=refund_indicator,
                scenes=[name for name, words in SCENARIOS if any(w in f'{merchant} {item}' for w in words)])


def build_alipay(source):
    independent = PdfReader(source)
    first = independent.pages[0].extract_text()
    period = re.search(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) 至 (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', first)
    if not period:
        raise ValueError('Missing Alipay export interval')
    start, end = [datetime.fromisoformat(v) for v in period.groups()]
    records, checks = [], []
    with pdfplumber.open(source) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            extracted=[]
            for table in page.extract_tables():
                for row_no, row in enumerate(table, 1):
                    if clean(row[0]) in ('收入','支出','不计收支'):
                        extracted.append(parse_alipay_row(row, page_no, row_no, len(records)+len(extracted)+1))
                    elif len(row)==8 and re.search(r'\d{4}-\d\d-\d\d',clean(row[-1])):
                        raise ValueError(f'Unrecognized Alipay row at page {page_no}, row {row_no}')
            # Independent engine, fixed columns from this documented proof layout.
            # Also compare direction and timestamp sequences; blank final notice page checks as zero.
            amounts, directions, times = [], [], []
            def visit(text, cm, tm, font, size):
                x = tm[4]*cm[0]+tm[5]*cm[2]+cm[4]
                value = clean(text)
                if 256 <= x < 297 and re.fullmatch(r'[\d,]+\.\d{2}',value): amounts.append(cents(value))
                if 49 <= x < 76:
                    if value in ('收入','支出','不计'): directions.append('不计收支' if value=='不计' else value)
                if 490 <= x < 546:
                    times.extend(re.findall(r'\d{4}-\d\d-\d\d|\d\d:\d\d:\d\d',text))
            independent.pages[page_no-1].extract_text(visitor_text=visit)
            expected_times=[part for r in extracted for part in r['time'].split(' ')]
            for label, expected, actual in [
                ('金额',amounts,[r['cents'] for r in extracted]),
                ('收支',directions,[r['raw_direction'] for r in extracted]),
                ('时间',times,expected_times)]:
                if expected != actual: raise ValueError(f'Alipay page {page_no}: independent {label} differs ({len(expected)} vs {len(actual)})')
            checks.extend([dict(name=f'第 {page_no} 页笔数、方向及时间（独立文本核验）',source=len(directions),computed=len(extracted),unit='笔'),
                           dict(name=f'第 {page_no} 页金额（独立文本逐笔核验）',source=sum(amounts),computed=sum(r['cents'] for r in extracted),unit='分')])
            if any(not start<=datetime.fromisoformat(r['time'])<=end for r in extracted): raise ValueError('Alipay record outside export interval')
            records.extend(extracted)
    # Alipay can reuse an order ID for payment and refund events; retain both source rows.
    meta=dict(file=source.name, sha256=hashlib.sha256(source.read_bytes()).hexdigest(), sheet='PDF',header_row=None,
              start=str(start.date()),end=str(end.date()),start_time=str(start),end_time=str(end),
              nickname=re.search(r'兹证明[:：]\s*(.*?)\(',first)[1], generated=datetime.now().isoformat(timespec='seconds'),
              format='PDF',platform='支付宝',pages=len(independent.pages),rule_version=RULES['version'],
              missing_fields=['交易类型（部分由商品说明标记）','备注','当前状态'],source_totals_available=False)
    return summarize(records,start,end,meta,checks)
