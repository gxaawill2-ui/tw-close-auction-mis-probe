const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
test('private evidence is authenticated, signed, immutable, isolated from public data and has no CORS',async()=>{
 const {worker,token,key,url}=await require('./stage3_worker_runtime.cjs').startWorker();
 try{
  const {canonical}=await import('./isolated_publication/worker.mjs');
  const date=new Date(Date.now()+8*3600000).toISOString().slice(0,10),raw='{"private_synthetic_marker":"never-public"}';
  const event={source:'FUGLE',raw,sha256:crypto.createHash('sha256').update(raw).digest('hex')};
  const id=crypto.createHash('sha256').update(canonical(event)).digest('hex'),route=url+'/private-evidence/'+date+'/'+id;
  const body={trade_date:date,id,scope:'PRIVATE_FUGLE_EVIDENCE',event};
  const signed=async b=>JSON.stringify({body:b,signature:crypto.createHmac('sha256',key).update(canonical(b)).digest('hex')});
  const opts={method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:await signed(body)};
  assert.equal((await fetch(route)).status,401);
  assert.equal((await fetch(route,{...opts,body:JSON.stringify({body,signature:'bad'})})).status,403);
  const write=await fetch(route,opts);assert.equal(write.status,200);assert.equal(write.headers.get('access-control-allow-origin'),null);
  const receipt=await write.json();assert.ok(receipt.private_written_at);assert.equal(JSON.stringify(receipt).includes('never-public'),false);
  assert.equal((await (await fetch(route,opts)).json()).duplicate,true);
  const read=await fetch(route,{headers:{Authorization:'Bearer '+token}});assert.equal((await read.json()).event.raw,raw);
  assert.equal((await fetch(url+'/private-evidence/'+date+'/index')).status,401);
  const publicData=await fetch(url+'/data?date='+date);assert.equal(publicData.status,404);
  const forged={...body,event:{...event,raw:'changed'}};assert.equal((await fetch(route,{...opts,body:await signed(forged)})).status,422);
  assert.equal((await fetch(url+'/private-evidence/2000-01-01/'+id,{...opts,body:await signed({...body,trade_date:'2000-01-01'})})).status,422);
  const view={schema_version:'STAGE3_SELECTION_V1',trade_date:date,mode:'SYNTHETIC',is_synthetic:true,version:1,generated_at:new Date().toISOString(),rows:[],verified_count:0,research_count:0,unknown_candidate_count:0,universe_count:0,screening_calculable_count:0,screening_unresolved_count:0,independent_evidence:{pre_tick:{price:123}}};
  assert.equal((await fetch(url+'/publish',{...opts,body:await signed(view)})).status,422);
 }finally{await worker.dispose();}
});
test('routine Cloudflare redeploy preserves stored writer keys; missing handoff never rotates',async()=>{
 const {bootstrap}=require('./isolated_publication/stage5-cloud-bootstrap.cjs');let calls=[];
 const args={config:{vars:{HANDOFF_REVISION:'stage5-20261016-v1'}},base:'https://test.invalid',wrangler:a=>calls.push(a),
  fetcher:async u=>({json:async()=>u.endsWith('/health')?{handoff_revision:'stage5-20261016-v1'}:{credential_handoff:{revision:'stage5-20261016-v1'}}})};
 await bootstrap(args);assert.deepEqual(calls,[['deploy']]);calls=[];
 await assert.rejects(()=>bootstrap({...args,fetcher:async()=>({json:async()=>({handoff_revision:'stage5-20261016-v1'})})}));assert.deepEqual(calls,[]);
});
test('dormant MIS bridge uses write-only credentials, private reads and independent namespace',async()=>{
 const bridgeToken='c'.repeat(64),{worker,token,key,url}=await require('./stage3_worker_runtime.cjs').startWorker({bridgeToken});
 try{
  const {canonical}=await import('./isolated_publication/worker.mjs');
  const at=new Date(),date=new Date(at.getTime()+8*3600000).toISOString().slice(0,10);
  const raw=canonical({origin:'MIS_LOCAL_DURABLE_JOURNAL',record:{received_at:new Date(at.getTime()-1000).toISOString()},persisted_at:at.toISOString()});
  const event={source:'MIS',raw,sha256:crypto.createHash('sha256').update(raw).digest('hex')};
  const id=crypto.createHash('sha256').update(canonical(event)).digest('hex');
  const body={trade_date:date,id,scope:'PRIVATE_MIS_JOURNAL',event};
  const packet=JSON.stringify({body,signature:crypto.createHmac('sha256',bridgeToken).update(canonical(body)).digest('hex')});
  const route=url+'/private-mis-journal/'+date+'/'+id;
  assert.equal((await fetch(route,{method:'POST',headers:{Authorization:'Bearer '+token},body:packet})).status,401);
  const saved=await fetch(route,{method:'POST',headers:{Authorization:'Bearer '+bridgeToken},body:packet});assert.equal(saved.status,200);assert.ok((await saved.json()).private_written_at);
  assert.equal((await fetch(route,{headers:{Authorization:'Bearer '+bridgeToken}})).status,401);
  const read=await fetch(route,{headers:{Authorization:'Bearer '+token}});assert.equal((await read.json()).event.raw,raw);
  assert.equal((await fetch(url+'/private-evidence/'+date+'/'+id,{headers:{Authorization:'Bearer '+bridgeToken}})).status,401);
  assert.equal((await fetch(url+'/private-evidence/'+date+'/'+id,{headers:{Authorization:'Bearer '+token}})).status,404);
  assert.equal((await fetch(url+'/publish',{method:'POST',headers:{Authorization:'Bearer '+bridgeToken},body:'{}'})).status,401);
 }finally{await worker.dispose();}
});
