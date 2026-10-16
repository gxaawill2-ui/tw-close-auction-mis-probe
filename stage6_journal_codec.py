"""Lossless bounded MIS journal transport; hashes retain original raw evidence."""
import base64
import hashlib
import json
import zlib
from stage3_ticks import canonical

LIMIT=512000

def encode(journal):
    raw=canonical(journal).encode()
    if len(raw)>LIMIT:raise ValueError('JOURNAL_UNCOMPRESSED_OVER_BUDGET')
    return canonical({'encoding':'ZLIB_BASE64_JOURNAL_V1','data':base64.b64encode(zlib.compress(raw)).decode(),
        'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_length':len(raw)})

def decode(raw):
    wrapped=json.loads(raw)
    if wrapped.get('encoding')!='ZLIB_BASE64_JOURNAL_V1':return wrapped
    n=wrapped.get('raw_length')
    if not isinstance(n,int) or isinstance(n,bool) or not 0<n<=LIMIT:raise ValueError('JOURNAL_DECOMPRESSION_BUDGET')
    decoder=zlib.decompressobj()
    data=decoder.decompress(base64.b64decode(wrapped['data'],validate=True),LIMIT+1)
    if len(data)!=n or decoder.unconsumed_tail or decoder.unused_data or not decoder.eof or hashlib.sha256(data).hexdigest()!=wrapped.get('raw_sha256'):
        raise ValueError('JOURNAL_DECOMPRESSION_OR_HASH_MISMATCH')
    return json.loads(data)
