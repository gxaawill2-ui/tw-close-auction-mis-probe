"""Compare already-private evidence to MIS; export only equality booleans.

No provider requests, no public writes, no source-contract release.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import freshness as f
from fast_selection import atomic
from stage3_ticks import identity, trade_time
from stage5_runtime import Vault, restore_bundle


def compare(bundle, reference):
    quote=json.loads(bundle['quote_after']['raw'])
    ticks=[t for page in bundle['pages'] for t in json.loads(page['raw'])['data']]
    last=quote['lastTrade']
    cutoff=f.parsed_time('2026-10-16T13:25:00+08:00')
    pre=[t for t in ticks if trade_time(t['time'])<cutoff]
    latest_pre=max((t['time'] for t in pre),default=None)
    group=[t for t in pre if t['time']==latest_pre]
    prices={f.decimal_value(t['price']) for t in group}
    expected_close=f.decimal_value(reference['P_close'])
    head=ticks[0] if ticks else None
    return {'code':reference['code'],'ex':reference['ex'],
        'mis_reference_admitted':reference['admitted_research_candidate'],
        'quote_close_matches_mis_price':f.decimal_value(quote.get('closePrice'))==expected_close,
        'quote_last_trade_matches_mis_price':f.decimal_value(last['price'])==expected_close,
        'quote_last_trade_matches_mis_time':trade_time(last['time']).strftime('%H:%M:%S')==reference['P_close_trade_time'],
        'trades_head_matches_mis_price':bool(head and f.decimal_value(head['price'])==expected_close),
        'trades_head_matches_mis_time':bool(head and trade_time(head['time']).strftime('%H:%M:%S')==reference['P_close_trade_time']),
        'trades_contain_mis_close_identity':any(f.decimal_value(t['price'])==expected_close and trade_time(t['time']).strftime('%H:%M:%S')==reference['P_close_trade_time'] for t in ticks),
        'quote_last_trade_matches_trades_head':bool(head and identity(last)==identity(head)),
        'trades_head_after_quote_trade':bool(head and head['time']>last['time']),
        'latest_pre_time_matches_mis':bool(group and trade_time(latest_pre).strftime('%H:%M:%S')==reference['P_before_trade_time']),
        'latest_pre_group_has_unique_price':len(prices)==1,
        'latest_pre_all_prices_match_mis':bool(prices) and prices=={f.decimal_value(reference['P_before'])},
        'quote_has_delayed_signal':quote.get('isDelayedClose') is True,
        'verified':False,'raw_provider_values_exported':False}


def main():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    root=Path('reports/2026-10-16-stage5')
    refs=json.loads((root/'mis-comparison-references.json').read_text())
    manifests={}
    for name in ('real-candidate-private-audit.json','real-remaining-candidate-audit.json'):
        for item in json.loads((root/name).read_text())['audits']:manifests[item['symbol']]=item['private_manifest_id']
    manifests['5546']=json.loads((root/'real-delayed-private-audit.json').read_text())['diagnostic']['private_manifest_id']
    vault=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'))
    results=[]
    for reference in refs['rows']:
        bundle=restore_bundle(vault,refs['trade_date'],manifests[reference['code']])
        results.append(compare(bundle,reference))
    report={'scope':'RESTORED_PRIVATE_VS_MIS_EQUALITY_DIAGNOSTICS_NOT_VERIFIED',
        'trade_date':refs['trade_date'],'run_id':os.getenv('GITHUB_RUN_ID'),
        'source_commit':os.getenv('GITHUB_SHA'),'observed_at':datetime.now(f.TZ).isoformat(),
        'fugle_requests':0,'mis_requests':0,'public_writes':0,'verified_count':0,'results':results}
    output=Path('stage5-source-compare-report');output.mkdir(exist_ok=True)
    atomic(output/'safe.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'PRIVATE_COMPARISON_NOT_PASSED','error_type':type(exc).__name__}));raise SystemExit(1)
