"""Build only the isolated Worker UI; does not write docs/ or production Pages."""
import json
from pathlib import Path
from build_stage3_preview import build


def main():
    payload={'schema_version':'STAGE3_SELECTION_V1','trade_date':'2026-10-16','mode':'LIVE',
        'is_synthetic':False,'version':0,'generated_at':None,'public_written_at':None,
        'rows':[],'verified_count':0,'research_count':0,'unknown_candidate_count':0,
        'universe_count':0,'screening_calculable_count':0,'screening_unresolved_count':0}
    path=build(payload,Path('isolated_publication/stage4-site/index.html'))
    html=path.read_text().replace('尾盤 ±3%｜第三階段隔離驗收','尾盤 ±3%｜第五階段隔離驗收')
    html=html.replace('<p class="subtitle">','<p id="stage5-summary" class="subtitle"></p><p class="subtitle">',1)
    old="window.Stage3Controller=Stage3View.create(document,Stage3Payload);const endpoint=new URL(location.href).searchParams.get('endpoint');if(endpoint){Stage3Controller.poll(endpoint);setInterval(()=>Stage3Controller.poll(endpoint),1500);}"
    new="""const requestedDate=new URL(location.href).searchParams.get('date');const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());Stage3Payload.trade_date=/^\\d{4}-\\d{2}-\\d{2}$/.test(requestedDate||'')?requestedDate:today;if(Stage3Payload.trade_date.startsWith('2099-')){Stage3Payload.mode='SYNTHETIC';Stage3Payload.is_synthetic=true;}window.Stage3Controller=Stage3View.create(document,Stage3Payload);const endpoint='/data?date='+encodeURIComponent(Stage3Payload.trade_date);Stage3Controller.poll(endpoint);setInterval(()=>{if(document.visibilityState!=='hidden')Stage3Controller.poll(endpoint);},5000);"""
    if old not in html:raise ValueError('ISOLATED_TEMPLATE_BOOTSTRAP_CHANGED')
    path.write_text(html.replace(old,new))


if __name__=='__main__':main()
