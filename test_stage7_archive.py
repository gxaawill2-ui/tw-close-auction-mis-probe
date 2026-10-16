import copy
from datetime import datetime,timedelta
import hashlib
import json
import unittest
from unittest.mock import patch
import freshness as f
from stage3_ticks import canonical
from stage7_archive import validate_index,snapshot_digest,copy_snapshot,recover_snapshot

class Fake:
    def __init__(self):
        raw='{"is_synthetic":true}';at=datetime.now(f.TZ)
        event={'source':'FUGLE','kind':'SYNTHETIC_STORAGE_CANARY','raw':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
        ident=hashlib.sha256(canonical(event).encode()).hexdigest()
        self.entries=[{'id':ident,'sha256':event['sha256']}]
        self.saved={'scope':'PRIVATE_FUGLE_EVIDENCE','id':ident,'trade_date':'2026-10-16','event':event,'private_written_at':at.isoformat(),'source_private_written_at':at.isoformat(),'archive_expires_at':(at+timedelta(days=30)).isoformat()}
    def read(self,date,ident):return copy.deepcopy({'entries':self.entries} if ident=='index' else self.saved)
    def copy(self,date,ident):return {**self.saved,'sha256':self.saved['event']['sha256']}

class ArchiveTests(unittest.TestCase):
    def test_independent_recovery_hashes(self):
        v=Fake()
        with patch('stage7_archive.time.sleep'):report=copy_snapshot(v,v,'2026-10-16')
        restored=recover_snapshot(v,'2026-10-16',report)
        self.assertEqual(restored['source_namespace_reads'],0);self.assertEqual(restored['object_count'],1)
    def test_tampered_raw(self):
        v=Fake()
        with patch('stage7_archive.time.sleep'):r=copy_snapshot(v,v,'2026-10-16')
        v.saved['event']['raw']='tampered'
        with self.assertRaisesRegex(ValueError,'INTEGRITY'):recover_snapshot(v,'2026-10-16',r)
    def test_missing_objects(self):
        v=Fake()
        with patch('stage7_archive.time.sleep'):r=copy_snapshot(v,v,'2026-10-16')
        v.entries=[]
        with self.assertRaises(ValueError):recover_snapshot(v,'2026-10-16',r)
    def test_manifest_tampering(self):
        v=Fake()
        with patch('stage7_archive.time.sleep'):r=copy_snapshot(v,v,'2026-10-16')
        r['manifest_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'MANIFEST'):recover_snapshot(v,'2026-10-16',r)
    def test_duplicate_index(self):
        v=Fake()
        with self.assertRaises(ValueError):validate_index({'entries':v.entries*2})
    def test_index_invalid_hash(self):
        with self.assertRaises(ValueError):validate_index({'entries':[{'id':'bad','sha256':'bad'}]})
