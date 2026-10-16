"""Read isolated cloud transport metadata only; never credentials or market bodies."""
import json
import urllib.request
import urllib.error
import re
import hashlib
from datetime import datetime, timezone
BASE='https://tw-tail-stage4-20261015-test.gxaawill2.workers.dev'
CLIENT='tw-close-auction-isolated/5.0 (+https://github.com/gxaawill2-ui/tw-close-auction-mis-probe)'


def main():
    report={'scope':'ISOLATED_CLOUD_PUBLIC_PREFLIGHT','observed_at':datetime.now(timezone.utc).isoformat()}
    for name,path in [('health','/health'),('sealed_handoff','/data?date=2099-01-02')]:
        try:
            request=urllib.request.Request(BASE+path,headers={'User-Agent':CLIENT,'Accept':'application/json','Cache-Control':'no-cache'})
            with urllib.request.urlopen(request,timeout=8) as response:
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
                # The fixed anonymous health endpoint cannot contain private market evidence.
                if name=='health':
                    text=exc.read(12000).decode('utf8',errors='replace')
                    title=re.search(r'<title[^>]*>([^<]{0,200})</title>',text,re.I)
                    report['cloud_error_page_title']=title.group(1) if title else None
                    report['cloud_challenge_detected']=any(marker in text.lower() for marker in ('cf-chl-','checking your browser','verify you are human','just a moment'))
                    # Anonymous health only: extract numeric edge error codes, not arbitrary bodies.
                    codes=re.findall(r'(?:error\s*(?:code)?\s*[:=]?\s*|data-translate="error"[^>]*>\s*)(1\d{3})\b',text,re.I)
                    report['cloud_edge_error_codes']=sorted(set(codes))[:8]
                    report['cloud_error_body_sha256']=hashlib.sha256(text.encode()).hexdigest()
                    report['cloud_error_body_bytes_observed']=len(text.encode())
                    report['cloud_error_content_type']=exc.headers.get('Content-Type')
                    report['cloud_error_classification']=('BROWSER_SIGNATURE_DENIED' if '1010' in codes else 'WORKER_FREE_DAILY_LIMIT' if '1027' in codes else 'UNCLASSIFIED_EDGE_DENIAL')
            if isinstance(exc,urllib.error.URLError):report[name+'_network_error_type']=type(exc.reason).__name__
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
