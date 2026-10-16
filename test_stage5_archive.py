import copy
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import freshness as f
from stage3_ticks import canonical
from stage5_archive import checked,export,probe
from stage5_runtime import Source,LocalVault,restore_bundle
from test_stage5_runtime import Response
from stage3_fixtures import DAY,example


class MemoryVault:
    def __init__(self):self.objects={}
    def save(self,event,date):
        ident=hashlib.sha256(canonical(event).encode()).hexdigest()
        self.objects[ident]={'id':ident,'trade_date':date,'scope':'PRIVATE_FUGLE_EVIDENCE',
            'event':copy.deepcopy(event),'private_written_at':DAY+'T13:35:00+08:00'}
        return {'id':ident,'sha256':event['sha256'],'private_written_at':DAY+'T13:35:00+08:00','recoverable_after_job':True}
    def read(self,date,ident):
        if ident=='index':return {'entries':[{'id':i,'sha256':v['event']['sha256']} for i,v in self.objects.items()]}
        return copy.deepcopy(self.objects[ident])


class ArchiveTests(unittest.TestCase):
    def test_private_canary_export_restart_and_hash_tampering(self):
        vault=MemoryVault();clock=lambda:f.parsed_time(DAY+'T13:35:00+08:00')
        receipt=probe(vault,DAY,clock=clock)
        self.assertEqual(receipt['scope'],'SYNTHETIC_PRIVATE_STORAGE_NOT_MARKET_ACCEPTANCE')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'private'
            result=export(vault,DAY,root);self.assertEqual(result['status'],'SNAPSHOT_COMPLETE')
            self.assertEqual(root.stat().st_mode&0o777,0o700)
            path=root/(receipt['id']+'.json');self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(export(vault,DAY,root)['manifest_sha256'],result['manifest_sha256'])
            data=json.loads(path.read_text());data['event']['raw']='tampered';path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'INTEGRITY'):export(vault,DAY,root)
        with self.assertRaises(ValueError):export(vault,DAY,Path(__file__).parent/'private-should-not-exist')

    def test_durable_failure_stops_shared_source_before_more_provider_requests(self):
        at=f.parsed_time(DAY+'T13:35:00+08:00');row,bundle=example();calls=[]
        class Broken:
            def save(self,*a):raise OSError('do not log private details')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'DURABLE_ARCHIVE'):Source('K'*30,tmp,LocalVault(),require_durable=True)
            def opener(*a,**k):calls.append(1);return Response(bundle['quote_before']['raw'].encode())
            source=Source('K'*30,tmp,Broken(),require_durable=True,clock=lambda:at,opener=opener)
            for _ in range(2):
                with self.assertRaises(ValueError) as err:source.request(row,'quote',{},at+timedelta(minutes=1))
                self.assertNotIn('private details',str(err.exception))
            self.assertTrue(source.stopped);self.assertEqual(len(calls),1)

    def test_manifest_outer_identity_must_match(self):
        vault=MemoryVault();event={'source':'FUGLE','kind':'bundle_manifest','raw':'{}','sha256':hashlib.sha256(b'{}').hexdigest()}
        receipt=vault.save(event,DAY);ident=receipt['id'];vault.objects[ident]['trade_date']='1999-01-01'
        with self.assertRaisesRegex(ValueError,'MANIFEST_HASH'):restore_bundle(vault,DAY,ident)


if __name__=='__main__':unittest.main()
