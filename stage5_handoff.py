"""Recover this isolated Worker's existing writer pair into a private local file.

No network, no key rotation, no Secret writes. Never print its output file.
"""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
from stage5_archive import private_write


def recover(envelope,private_key,private_output):
    if envelope.get('revision')!='stage5-20261016-v1' or envelope.get('algorithm')!='RSA-OAEP-SHA256' or envelope.get('scope')!='ISOLATED_WORKER_WRITER_ONLY':
        raise ValueError('REFUSE_OTHER_HANDOFF')
    key=Path(private_key).resolve();output=Path(private_output).resolve();repo=Path(__file__).parent.resolve()
    if key.stat().st_mode&0o077 or output==repo or repo in output.parents or not output.parent.is_dir() or output.parent.stat().st_mode&0o077:
        raise ValueError('PRIVATE_HANDOFF_PATH_OR_PERMISSION')
    encrypted=base64.b64decode(envelope['sealed'],validate=True)
    result=subprocess.run(['openssl','pkeyutl','-decrypt','-inkey',str(key),'-pkeyopt','rsa_padding_mode:oaep',
        '-pkeyopt','rsa_oaep_md:sha256'],input=encrypted,capture_output=True,timeout=5)
    if result.returncode:raise ValueError('PRIVATE_HANDOFF_DECRYPT_FAILED')
    pair=json.loads(result.stdout)
    if set(pair)!={'token','key'} or not all(isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v) for v in pair.values()):
        raise ValueError('ISOLATED_WRITER_FORMAT_FAILED')
    private_write(output,{'STAGE5_PUBLISH_TOKEN':pair['token'],'STAGE5_DECISION_KEY':pair['key']})
    return {'scope':'ISOLATED_EXISTING_WRITER_RECOVERED_LOCALLY','revision':envelope['revision'],
        'names':['STAGE5_PUBLISH_TOKEN','STAGE5_DECISION_KEY'],'plaintext_logged':False,'github_secrets_saved':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('envelope',type=Path);p.add_argument('private_key',type=Path);p.add_argument('private_output',type=Path);a=p.parse_args()
    try:print(json.dumps(recover(json.loads(a.envelope.read_text()),a.private_key,a.private_output)))
    except Exception as exc:print(json.dumps({'status':'HANDOFF_NOT_RECOVERED','error_type':type(exc).__name__}));raise SystemExit(1)
