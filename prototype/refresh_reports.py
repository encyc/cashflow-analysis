"""Refresh the four report UIs from verified parsed records, without rereading PDFs."""
import json
from pathlib import Path
from render_report import render
from merge_reports import OUT,write_index

for source,target in [('analysis.json','report.html'),('pdf-analysis.json','pdf-report.html'),('person-1-combined.json','person-1-combined.html'),('person-2-combined.json','person-2-combined.html')]:
    data=json.loads((OUT/source).read_text())
    html=render(data)
    (OUT/source).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    (OUT/target).write_text(html)
    print(data['meta']['nickname'],data['insights']['scenes'])
write_index(json.loads((OUT/'combined-manifest.json').read_text()))
