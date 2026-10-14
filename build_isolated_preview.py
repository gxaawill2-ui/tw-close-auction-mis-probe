"""Build a self-contained, network-free preview from audited saved research JSON."""
import json
import re
from pathlib import Path


def build(payload_path, output):
    root=Path(__file__).parent;payload=json.loads(Path(payload_path).read_text())
    date=payload['trade_date']
    live=json.loads((root/'state/live'/f'{date}.json').read_text())
    # Isolated policy replay only: keep original outcome visible in the banner.
    original=live['capture_outcome'];live.update(status='partial',capture_outcome=payload['capture_outcome'])
    fixtures={f'state/candidates/{date}.json':payload,f'state/live/{date}.json':live,
              f'state/validation/{date}.json':{'trade_date':date,'status':'PENDING_SCHEDULED_POSTMARKET'},
              'state/calendars/2026.json':json.loads((root/'state/calendars/2026.json').read_text())}
    for name in ('events-index','fund-events','source-health'):
        p=root/'state/events'/f'{name}.json'
        if p.exists():fixtures[f'state/events/{name}.json']=json.loads(p.read_text())
    html=(root/'docs/index.html').read_text()
    html=re.sub(r'<link rel="stylesheet"[^>]+>',lambda m:'<style>'+(root/'docs/status.css').read_text()+'</style>',html)
    html=re.sub(r'  <script defer[^>]+></script>\n','',html)
    banner=f'<aside style="padding:12px;background:#423721;color:#ffe1a3;font-size:13px">隔離驗收重播｜{date}｜原始歷史結果 {original} 完整保留。此頁示範新版 PARTIAL 分類與研究名單，時鐘固定 14:10；所有股票均非正式交易訊號，無網路請求。</aside>'
    html=html.replace('<body>','<body>'+banner)
    bootstrap='''const fixed="'''+date+'''T14:10:00+08:00";const RealDate=Date;
window.Date=class extends RealDate{constructor(...a){super(...(a.length?a:[fixed]));}static now(){return new RealDate(fixed).getTime();}};
const fixtures='''+json.dumps(fixtures,ensure_ascii=False).replace('</','<\\/')+''';
window.fetch=async url=>{const path=String(url).split('/main/')[1]?.split('?')[0];const data=fixtures[path];return new Response(data?JSON.stringify(data):'Not found',{status:data?200:404,headers:{'Content-Type':'application/json'}});};'''
    scripts=[bootstrap,*[(root/'docs'/name).read_text() for name in ('status.js','events.js','market-closing.js')]]
    html=html.replace('</body>',''.join('<script>'+s.replace('</script','<\\/script')+'</script>' for s in scripts)+'</body>')
    Path(output).write_text(html)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('output');a=p.parse_args();build(a.payload,a.output)
