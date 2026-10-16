const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
test('actual workerd immutable private archive, auth boundaries and duplicate copy',async()=>{
 const {worker,url,token,key}=await require('./stage3_worker_runtime.cjs').startWorker();
 try{
  const {canonical}=await import('./isolated_publication/worker.mjs');
  const date=new Date(Date.now()+8*3600000).toISOString().slice(0,10),at=new Date().toISOString();
  const event={source:'FUGLE',kind:'SYNTHETIC_STORAGE_CANARY',raw:'{"is_synthetic":true}',persisted_at:at};event.sha256=hash(event.raw);
  const id=hash(canonical(event)),headers={Authorization:'Bearer '+token};
  const packet=body=>JSON.stringify({body,signature:crypto.createHmac('sha256',key).update(canonical(body)).digest('hex')});
  const source=url+'/private-evidence/'+date+'/'+id,archive=url+'/private-archive/'+date+'/'+id;
  assert.equal((await fetch(source,{method:'POST',headers,body:packet({scope:'PRIVATE_FUGLE_EVIDENCE',trade_date:date,id,event})})).status,200);
  assert.equal((await fetch(archive)).status,401);
  const body={scope:'PRIVATE_FUGLE_ARCHIVE_COPY',trade_date:date,id};
  assert.equal((await fetch(archive,{method:'POST',headers,body:JSON.stringify({body,signature:'x'})})).status,403);
  assert.equal((await fetch(archive,{method:'POST',headers,body:'null'})).status,403);
  assert.equal((await fetch(archive,{method:'POST',headers,body:packet({...body,event})})).status,422);
  const copied=await fetch(archive,{method:'POST',headers,body:packet(body)});assert.equal(copied.status,200);const receipt=await copied.json();
  const read=await fetch(archive,{headers});assert.equal(read.status,200);assert.equal(read.headers.get('access-control-allow-origin'),null);
  const saved=await read.json();assert.deepEqual(saved.event,event);assert.equal(saved.id,id);
  assert.equal(Date.parse(saved.archive_expires_at)-Date.parse(saved.source_private_written_at),30*86400000);
  const duplicate=await (await fetch(archive,{method:'POST',headers,body:packet(body)})).json();
  assert.equal(duplicate.duplicate,true);assert.equal(duplicate.archive_expires_at,receipt.archive_expires_at);
  assert.equal(duplicate.private_written_at,receipt.private_written_at);
  const index=await (await fetch(url+'/private-archive/'+date+'/index',{headers})).json();assert.equal(index.entries.length,1);
  assert.equal((await fetch(archive+'?token=bad',{headers})).status,404);
  assert.equal((await fetch(url+'/private-archive/'+date+'/'+'a'.repeat(64),{method:'POST',headers,body:packet({...body,id:'a'.repeat(64)})})).status,409);
 }finally{await worker.dispose();}
});
function state(){const values=new Map();return {storage:{get:async k=>structuredClone(values.get(k)),put:async(k,v)=>values.set(k,structuredClone(v)),getAlarm:async()=>values.get('_alarm'),setAlarm:async v=>values.set('_alarm',v),transaction:async fn=>fn({put:async(k,v)=>values.set(k,structuredClone(v))}),deleteAll:async()=>values.clear()},blockConcurrencyWhile:fn=>fn(),values};}
test('local source deletion leaves archive recoverable; fixed alarm and expiry deny reads',async()=>{
 const {SelectionStore,canonical}=await import('./isolated_publication/worker.mjs');
 const source=state(),archive=state(),s=new SelectionStore(source,{}),a=new SelectionStore(archive,{});
 const until=new Date(Date.now()+29*86400000).toISOString();
 const body={scope:'PRIVATE_FUGLE_EVIDENCE',id:'a'.repeat(64),trade_date:'2026-10-16',event:{source:'FUGLE',raw:'synthetic',sha256:hash('synthetic')},archive_expires_at:until};
 assert.equal((await a.fetch(new Request('https://actor/archive/2026-10-16/'+body.id,{method:'POST',body:JSON.stringify(body)}))).status,200);
 source.values.set('evidence:'+body.id,{...body});await s.alarm();assert.equal(source.values.size,0);
 assert.equal((await a.fetch(new Request('https://actor/archive/2026-10-16/'+body.id))).status,200);
 assert.equal(archive.values.get('_alarm'),Date.parse(until));
 assert.equal((await a.fetch(new Request('https://actor/archive/2026-10-16/'+body.id,{method:'POST',body:JSON.stringify({...body,archive_expires_at:new Date(Date.now()+30*86400000).toISOString()})}))).status,409);
 archive.values.set('archive_expires_at',new Date(Date.now()-1).toISOString());
 assert.equal((await a.fetch(new Request('https://actor/archive/2026-10-16/'+body.id))).status,410);
 await a.alarm();assert.equal(archive.values.size,0);
});
