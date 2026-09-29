"""Shared standalone HTML renderer for original and combined reports."""
from pathlib import Path
import json
from scene_analysis import analyze
BASE=Path(__file__).parent

def render(data):
    data['insights']=analyze(data['records'],data['meta']['end'])
    template=(BASE/'report.html').read_text()
    template=template.replace('</style>',(BASE/'scene-ui.css').read_text()+'\n</style>')
    extra=(BASE/'combined-ui.js').read_text()+'\n'+(BASE/'scene-ui.js').read_text()
    template=template.replace('filter();\n</script>',extra+'\nfilter();\n</script>')
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    return template.replace('__REPORT_DATA__',payload.replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026'))
