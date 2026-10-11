const test=require('node:test'),assert=require('node:assert/strict'),{generateKeyPairSync,verify}=require('node:crypto');
const load=import('./relay/index-events-worker.mjs');
const {privateKey,publicKey}=generateKeyPairSync('rsa',{modulusLength:2048});
const env={APP_CLIENT_ID:'Iv1.synthetic',APP_INSTALLATION_ID:'123',APP_PRIVATE_KEY:privateKey.export({type:'pkcs1',format:'pem'}),CALLER_SECRET:'a'.repeat(43)};
const now=Date.parse('2026-10-12T08:35:00+08:00');
function req(body={schedule_slot:'08:20',self_test:false},secret=env.CALLER_SECRET,path='/dispatch'){return new Request('https://relay.example'+path,{method:'POST',headers:{Authorization:'Bearer '+secret},body:JSON.stringify(body)});}
test('App JWT RS256 verifies for both PKCS1 and PKCS8 with bounded lifetime',async()=>{
 const m=await load;for(const pem of [env.APP_PRIVATE_KEY,privateKey.export({type:'pkcs8',format:'pem'})]){const jwt=await m.appJWT({...env,APP_PRIVATE_KEY:pem},now),[a,b,c]=jwt.split('.');assert.equal(verify('RSA-SHA256',Buffer.from(a+'.'+b),publicKey,Buffer.from(c,'base64url')),true);const claims=JSON.parse(Buffer.from(b,'base64url'));assert.equal(claims.iat,now/1000-60);assert.equal(claims.exp,now/1000+540);}
});
test('caller auth denies missing, invalid and wrong independent credentials',async()=>{const m=await load;assert.equal(await m.authenticated(req(),env.CALLER_SECRET),true);for(const x of ['','bad','b'.repeat(43)])assert.equal(await m.authenticated(req({},x),env.CALLER_SECRET),false);assert.equal(await m.authenticated(req(),'short'),false);});
test('slot identity is Taipei date with fixed bounded backup windows',async()=>{const m=await load;assert.equal(m.slotIdentity('08:20',now),'2026-10-12-0820');assert.equal(m.slotIdentity('17:20',Date.parse('2026-10-12T17:35:00+08:00')),'2026-10-12-1720');assert.equal(m.slotIdentity('08:20',Date.parse('2026-10-13T00:13:00+08:00')),null);assert.equal(m.slotIdentity('08:20',now-60000),null);assert.equal(m.slotIdentity('08:20',now+46*60000),null);});
test('token is requested freshly with only fixed repo Actions and dispatch main',async()=>{
 const m=await load,calls=[];const fetcher=async(u,o)=>{calls.push({u,body:JSON.parse(o.body)});return calls.length%2?Response.json({token:'synthetic-only',expires_at:new Date(now+3600000).toISOString(),permissions:{actions:'write',metadata:'read'},repositories:[{id:1395186758,full_name:'gxaawill2-ui/tw-close-auction-mis-probe'}]},{status:201}):new Response(null,{status:204});};
 await m.dispatch(env,'08:20',true,now,fetcher);await m.dispatch(env,'17:20',false,now,fetcher);assert.equal(calls.length,4);assert.deepEqual(calls[0].body,{repository_ids:[1395186758],permissions:{actions:'write',metadata:'read'}});assert.deepEqual(calls[1].body,{ref:'main',inputs:{schedule_slot:'08:20',self_test:true}});assert.match(calls[1].u,/index-events.yml\/dispatches$/);
});
test('API 401/403, timeout, installation mismatch and excess permissions fail closed',async()=>{
 const m=await load;for(const code of [401,403,500])await assert.rejects(m.dispatch(env,'08:20',false,now,async()=>new Response(null,{status:code})),/TOKEN_HTTP/);
 await assert.rejects(m.dispatch(env,'08:20',false,now,async()=>{throw new Error('synthetic timeout');}),/timeout/);
 for(const extra of [{permissions:{actions:'write',contents:'write'}},{repositories:[]},{expires_at:new Date(now-1000).toISOString()}])await assert.rejects(m.dispatch(env,'08:20',false,now,async()=>Response.json({token:'synthetic',expires_at:new Date(now+3600000).toISOString(),permissions:{actions:'write',metadata:'read'},repositories:[{id:1395186758,full_name:'gxaawill2-ui/tw-close-auction-mis-probe'}],...extra},{status:201})),/TOKEN_SCOPE/);
});
test('relay rejects arbitrary repositories/workflows/refs/body/query and has no secret health output',async()=>{
 const m=await load;for(const body of [{ref:'other',schedule_slot:'08:20',self_test:true},{workflow:'mis',schedule_slot:'08:20',self_test:true},{schedule_slot:'13:00',self_test:true},{schedule_slot:'08:20'}])assert.equal((await m.default.fetch(req(body),env)).status,400);
 assert.equal((await m.default.fetch(req({},'bad'),env)).status,401);assert.equal((await m.default.fetch(req({},env.CALLER_SECRET,'/dispatch?ref=other'),env)).status,404);
 const h=await m.default.fetch(new Request('https://relay.example/health'),env);assert.equal(h.status,200);assert.doesNotMatch(await h.text(),/synthetic|aaaaa/);
});
function storageMock(){const map=new Map();let pending=Promise.resolve();return {map,get:async k=>map.get(k),put:async(k,v)=>map.set(k,v),delete:async k=>map.delete(k),list:async()=>map,transaction(fn){const p=pending.then(()=>fn(this));pending=p.catch(()=>{});return p;}};}
test('atomic daily ledger suppresses simultaneous/delayed duplicate before any API requests',async()=>{
 const m=await load,storage=storageMock(),id=m.slotIdentity('08:20',Date.now(),true);storage.map.set(id,{success:true,attempts:1});const gate=new m.DispatchGate({storage},env);
 const result=await Promise.all([gate.fetch(req({schedule_slot:'08:20',self_test:true})),gate.fetch(req({schedule_slot:'08:20',self_test:true}))]);assert.deepEqual(result.map(r=>r.status),[200,200]);
 storage.map.set(id,{attempts:1,lease_until:Date.now()+60000});assert.equal((await gate.fetch(req({schedule_slot:'08:20',self_test:true}))).status,200);
 storage.map.set(id,{attempts:2});assert.equal((await gate.fetch(req({schedule_slot:'08:20',self_test:true}))).status,429);
});
test('deployment config uses free SQLite DO; no secret values or MIS endpoints in relay config',()=>{const fs=require('node:fs'),s=fs.readFileSync('relay/wrangler.jsonc','utf8');assert.match(s,/new_sqlite_classes/);assert.doesNotMatch(s,/PRIVATE KEY|ghp_|github_pat_|MIS|cron-job/);assert.equal(JSON.parse(s).observability.enabled,false);});

test('current GitHub API 200 dispatch response preserves fixed-scope run id',async()=>{
 const m=await load;let count=0;const fetcher=async()=>++count===1?Response.json({token:'synthetic',expires_at:new Date(now+3600000).toISOString(),permissions:{actions:'write',metadata:'read'},repositories:[{id:1395186758,full_name:'gxaawill2-ui/tw-close-auction-mis-probe'}]},{status:201}):Response.json({workflow_run_id:123,run_url:'https://api.github.com/repos/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/123',html_url:'https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/123'});
 assert.equal((await m.dispatch(env,'08:20',true,now,fetcher)).workflow_run_id,123);
});
test('oversized relay body is bounded even without declared Content-Length',async()=>{const m=await load;assert.equal((await m.default.fetch(req({schedule_slot:'08:20',self_test:true,padding:'x'.repeat(300)}),env)).status,413);});
