"""Read isolated cloud transport metadata only; never credentials or market bodies."""
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
BASE='https://tw-tail-stage4-20261015-test.gxaawill2.workers.dev'


def main():
    report={'scope':'ISOLATED_CLOUD_PUBLIC_PREFLIGHT','observed_at':datetime.now(timezone.utc).isoformat()}
    for name,path in [('health','/health'),('sealed_handoff','/data?date=2099-01-02')]:
        try:
            with urllib.request.urlopen(BASE+path,timeout=8) as response:
                data=json.loads(response.read(32000));report[name+'_http_status']=response.status
            if name=='health':
                report[name]={k:data.get(k) for k in ('handoff_revision','private_evidence_available','live_validation_released','read_validator_revision')}
            else:
                handoff=data.get('credential_handoff',{})
                report[name]={k:handoff.get(k) for k in ('revision','algorithm','sealed','scope')}
                report['cloud_written_at']=data.get('public_written_at')
                report['source_commit']=data.get('transport_acceptance',{}).get('commit')
        except Exception as exc:
            report[name+'_error']='CLOUD_READ_UNAVAILABLE'
            report[name+'_error_type']=type(exc).__name__
            if isinstance(exc,urllib.error.HTTPError):report[name+'_http_status']=exc.code
            if isinstance(exc,urllib.error.HTTPError):
                report[name+'_response_headers']={k:v for k,v in exc.headers.items() if k.lower() in ('server','cf-ray','x-deny-reason','x-mitmproxy-blocked-reason')}
            if isinstance(exc,urllib.error.URLError):report[name+'_network_error_type']=type(exc.reason).__name__
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
