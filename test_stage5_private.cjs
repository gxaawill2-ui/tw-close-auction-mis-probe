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
