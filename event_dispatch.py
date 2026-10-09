"""Bounded event-only HTTP integration test. Uses short-lived CI token only."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPOSITORY='gxaawill2-ui/tw-close-auction-mis-probe'
ENDPOINT='https://api.github.com/repos/'+REPOSITORY+'/actions/workflows/index-events.yml/dispatches'


def dispatch(token, ref, opener=urlopen):
    if not token or ref=='main' or not ref.startswith('improve/'): raise ValueError('Self-test requires isolated improve branch')
    request=Request(ENDPOINT,data=json.dumps({'ref':ref,'inputs':{'schedule_slot':'17:20','self_test':True}}).encode(),
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},method='POST')
    for attempt in range(2):
        try:
            with opener(request,timeout=10) as response:
                if response.status!=204: raise RuntimeError('Unexpected dispatch status')
                return {'http_status':204,'attempts':attempt+1,'workflow':'index-events.yml','self_test':True}
        except HTTPError as error:
            if error.code in (400,401,403,404,422) or attempt==1: raise RuntimeError('Dispatch HTTP '+str(error.code)) from None
        except (TimeoutError,OSError):
            if attempt==1: raise RuntimeError('Dispatch timeout/network failure after two attempts') from None
    raise RuntimeError('Dispatch unavailable')

if __name__=='__main__':
    import os
    print(json.dumps(dispatch(os.environ['GH_TOKEN'],os.environ['GITHUB_REF_NAME'])))
