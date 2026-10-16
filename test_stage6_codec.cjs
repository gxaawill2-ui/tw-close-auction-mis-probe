const test=require('node:test'),assert=require('node:assert/strict'),zlib=require('node:zlib'),crypto=require('node:crypto');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
test('bounded journal decompression preserves bytes and rejects tampered digest and inflated sizes',async()=>{
 const {decodeJournal}=await import('./isolated_publication/stage6-journal-codec.mjs');
 const data={record:{received_at:new Date().toISOString(),padding:'MIS_SYNTHETIC'.repeat(12000)},persisted_at:new Date().toISOString()};
 const raw=JSON.stringify(data),wrapper={encoding:'ZLIB_BASE64_JOURNAL_V1',raw_length:Buffer.byteLength(raw),raw_sha256:hash(raw),data:zlib.deflateSync(raw).toString('base64')};
 assert.deepEqual(await decodeJournal(JSON.stringify(wrapper)),data);
 await assert.rejects(()=>decodeJournal(JSON.stringify({...wrapper,raw_sha256:'0'.repeat(64)})));
 await assert.rejects(()=>decodeJournal(JSON.stringify({...wrapper,raw_length:512001})));
 const bomb='x'.repeat(512001);
 await assert.rejects(()=>decodeJournal(JSON.stringify({...wrapper,raw_length:1,data:zlib.deflateSync(bomb).toString('base64')})));
});
test('compressed private MIS bridge is accepted by actual local workerd while public reads remain denied',async()=>{
 const bridgeToken='c'.repeat(64),{worker,token,url}=await require('./stage3_worker_runtime.cjs').startWorker({bridgeToken});
 try{
  const {canonical}=await import('./isolated_publication/worker.mjs');
  const at=new Date(),date=new Date(at.getTime()+8*3600000).toISOString().slice(0,10);
  const raw=canonical({origin:'MIS_LOCAL_DURABLE_JOURNAL',record:{received_at:new Date(at-1000).toISOString(),padding:'SYNTHETIC'.repeat(20000)},persisted_at:at.toISOString()});
  const encoded=canonical({encoding:'ZLIB_BASE64_JOURNAL_V1',raw_length:Buffer.byteLength(raw),raw_sha256:hash(raw),data:zlib.deflateSync(raw).toString('base64')});
  const event={source:'MIS',raw:encoded,sha256:hash(encoded)},id=hash(canonical(event));
  const body={trade_date:date,id,scope:'PRIVATE_MIS_JOURNAL',event};
  const packet=JSON.stringify({body,signature:crypto.createHmac('sha256',bridgeToken).update(canonical(body)).digest('hex')});
  assert.ok(Buffer.byteLength(packet)<98304);
  const route=url+'/private-mis-journal/'+date+'/'+id;
  const r=await fetch(route,{method:'POST',headers:{Authorization:'Bearer '+bridgeToken},body:packet});assert.equal(r.status,200);
  assert.equal((await fetch(route)).status,401);
  assert.equal((await (await fetch(route,{headers:{Authorization:'Bearer '+token}})).json()).event.raw,encoded);
 }finally{await worker.dispose();}
});
