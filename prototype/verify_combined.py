"""Validate source coverage, provenance, identities, integer sums and embedded report payloads."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from merge_reports import OUT, ROOT, identity

NODE='/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'

def verify():
    manifest=json.loads((OUT/'combined-manifest.json').read_text())
    assert len(manifest)==2
    all_files=[]
    for entry in manifest:
        stem=Path(entry['file']).stem
        data=json.loads((OUT/(stem+'.json')).read_text())
        records=data['records'];s=data['summary']
        assert len(records)==s['count']
        assert all(isinstance(r['cents'],int) for r in records)
        assert len({(r['platform'],r['source_sha256'],r['source_page'],r['source_table_row']) for r in records})==len(records)
        assert len({r['row'] for r in records})==len(records)
        source_records=[];identities=[]
        for source in data['meta']['sources']:
            meta=source['meta'];file=ROOT/'template'/meta['file'];all_files.append(file.name)
            identities.append(identity(file))
            assert meta['sha256']==hashlib.sha256(file.read_bytes()).hexdigest()
            suffix='wechat' if meta['platform']=='微信' else 'alipay'
            raw=json.loads((OUT/(stem.replace('-combined','')+'-'+suffix+'.json')).read_text())
            assert all(c['source']==c['computed'] for c in raw['checks'])
            assert len(raw['checks'])==meta['pages']*2
            source_records.extend(raw['records'])
        assert len(set(identities))==1 and identities[0][0]==entry['name']
        assert len(source_records)==len(records)
        by_id={(r['platform'],r['source_page'],r['source_table_row']):r for r in source_records}
        for r in records:
            original=by_id[(r['platform'],r['source_page'],r['source_table_row'])]
            assert r['source_row']==original['row']
            assert {k:v for k,v in r.items() if k not in ('row','source_row','same_order_records')}=={k:v for k,v in original.items() if k!='row'}
            assert 1<=r['source_page']<=next(v['meta']['pages'] for v in data['meta']['sources'] if v['meta']['file']==r['source_file'])
        for direction,field in [('收入','income'),('支出','expense'),('中性交易','neutral')]:
            assert sum(r['cents'] for r in records if r['direction']==direction)==s[field]
            assert sum(source['summary'][field] for source in data['meta']['sources'])==s[field]
        assert s['net']==s['income']-s['expense']
        assert sum(m['income'] for m in data['monthly'])==s['income']
        assert sum(m['expense'] for m in data['monthly'])==s['expense']
        assert sum(m['count'] for m in data['monthly'])==s['count']
        assert sum(c['cents'] for c in data['categories'])==s['expense']
        assert all(c['source']==c['computed'] for c in data['checks'])
        html=(OUT/entry['file']).read_text()
        assert json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',html,re.S)[1])==data
        # Identity matching must not leak certificate numbers into the reports.
        assert identities[0][1] not in html
        script=re.findall(r'<script>(.*?)</script>',html,re.S)[0]
        subprocess.run([NODE,'--check'],input=script,text=True,check=True,capture_output=True)
        assert 'src="http' not in html
        print(f"PASS {entry['name']}: {len(records)} rows, {data['meta']['pages']} pages, {len(data['checks'])} checks, source fields and embedded HTML preserved")
    assert len(all_files)==len(set(all_files))==4

if __name__=='__main__':verify()
