'use strict';
// Only the NEW stage4 Worker. No market API, GitHub API, or production routes.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const NAME='tw-tail-stage4-20261015-test';
const BASE='https://'+NAME+'.gxaawill2.workers.dev';
const BRANCH='stage4/20261015-live-shadow',DATE='2099-01-01';
const CONFIG=path.join(__dirname,'stage4.wrangler.jsonc');
function assert(ok,message){if(!ok)throw Error(message);}
function validateTarget(config,env){
 assert(env.WORKERS_CI==='1'&&env.WORKERS_CI_BRANCH===BRANCH,'REFUSE_OUTSIDE_EXACT_ISOLATED_WORKERS_BUILD');
 assert(/^[a-f0-9]{40}$/.test(env.WORKERS_CI_COMMIT_SHA||''),'MISSING_BUILD_COMMIT');
 assert(config.name===NAME&&config.main==='worker.mjs','REFUSE_OTHER_WORKER');
 assert(config.vars?.ALLOW_LIVE_VERIFIED==='false','REFUSE_LIVE_RELEASE');
 assert(!['route','routes','triggers','env','services','queues'].some(k=>k in config),'REFUSE_EXTERNAL_BINDINGS_OR_SCHEDULES');
 assert(JSON.stringify(config.durable_objects?.bindings)===JSON.stringify([{name:'SELECTION',class_name:'SelectionStore'}]),'REFUSE_OTHER_NAMESPACE');
 assert(JSON.stringify(config.migrations)===JSON.stringify([{tag:'stage4-isolated-v1',new_sqlite_classes:['SelectionStore']}]),'REFUSE_OTHER_MIGRATION');
 assert(config.assets?.directory==='./stage4-site','REFUSE_OTHER_ASSETS');
}
async function acceptance({base=BASE,token,key,fetcher=fetch,wait=ms=>new Promise(r=>setTimeout(r,ms)),allowLoopback=false,commit=null}){
 const url=new URL(base);
 assert(base===BASE||(allowLoopback&&url.protocol==='http:'&&url.hostname==='127.0.0.1'&&!url.search&&!url.hash&&!url.username),'REFUSE_OTHER_PUBLIC_ENDPOINT');
 assert(typeof token==='string'&&token.length>=32&&typeof key==='string'&&key.length>=32,'MISSING_ISOLATED_WRITER_KEYS');
 const {canonical}=await import('./worker.mjs');
 const report={scope:'REAL_CLOUDFLARE_SYNTHETIC_TRANSPORT_NOT_REAL_MARKET_OR_MOBILE',started_at:new Date().toISOString(),trade_date:DATE,checks:[],requests:[],first_server_write_at:null,external_browser_read_at:null,physical_mobile_latency_ms:null};
 async function request(name,route,options={}){
  assert(route.startsWith('/')&&!route.startsWith('//'),'INVALID_ROUTE');
  const target=new URL(route,base);assert(target.origin===url.origin,'REFUSE_REDIRECTED_CREDENTIALS');
  const start=performance.now(),requested_at=new Date().toISOString();
  const response=await fetcher(target,{...options,cache:'no-store',redirect:'error',signal:AbortSignal.timeout(8000)});
  const raw=await response.text();let body;try{body=JSON.parse(raw);}catch{body=null;}
  report.requests.push({name,requested_at,response_received_at:new Date().toISOString(),http_status:response.status,roundtrip_ms:performance.now()-start});
  return {response,body};
 }
 const pass=name=>report.checks.push({name,status:'PASS'});
 async function expect(name,route,status,options){const r=await request(name,route,options);assert(r.response.status===status,name+'_HTTP_'+r.response.status);pass(name);return r;}
 const sign=body=>({body,signature:crypto.createHmac('sha256',key).update(canonical(body)).digest('hex')});
 const post=body=>({method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(sign(body))});
 const nonce=crypto.randomBytes(12).toString('hex'),version=Date.now()*10;
 const body={schema_version:'STAGE3_SELECTION_V1',trade_date:DATE,mode:'SYNTHETIC',is_synthetic:true,version,generated_at:new Date().toISOString(),rows:[],verified_count:0,research_count:0,unknown_candidate_count:0,universe_count:0,screening_calculable_count:0,screening_unresolved_count:0,transport_nonce:nonce};
 let health;for(let i=0;i<4;i++){health=await request('health', '/health');if(health.response.status===200&&health.body?.read_validator_revision==='weak-etag-v2')break;if(i<3)await wait(1000*(i+1));}
 assert(health.response.status===200&&health.body?.read_validator_revision==='weak-etag-v2'&&health.body?.live_validation_released===false,'HEALTH_RELEASE_GATE_FAILED');pass('health-keeps-live-release-closed');
 let written;for(let i=0;i<4;i++){written=await request('first-signed-write','/publish',post(body));if(written.response.status===200)break;assert([401,503].includes(written.response.status),'SIGNED_WRITE_FAILED_'+written.response.status);if(i<3)await wait(1000*(i+1));}
 assert(written.response.status===200&&written.body?.version===version&&Number.isFinite(Date.parse(written.body.public_written_at)),'MISSING_SERVER_WRITE_RECEIPT');
 report.first_server_write_at=written.body.public_written_at;pass('signed-write-server-receipt');
 const data='/data?date='+DATE;
 let read=await expect('anonymous-read',data,200);
 assert(read.body?.transport_nonce===nonce&&read.body.sha256===written.body.sha256&&read.body.version===version&&read.body.verified_count===0,'READ_AFTER_WRITE_MISMATCH');pass('read-matches-nonce-version-and-sha');
 assert(/no-store/.test(read.response.headers.get('cache-control')||'')&&read.response.headers.get('access-control-allow-origin')==='*','CACHE_OR_CORS_FAILED');pass('no-store-and-anonymous-cors');
 const etag=read.response.headers.get('etag');assert(etag,'MISSING_ETAG');
 async function revalidate(name,tag){
  const attempts=[];
  for(let i=0;i<4;i++){
   const r=await request(name,data,{headers:{'If-None-Match':tag}});
   attempts.push({status:r.response.status,etag:r.response.headers.get('etag'),revision:r.response.headers.get('x-read-validator-revision'),cache_status:r.response.headers.get('cf-cache-status'),sent_etag:tag});
   if(r.response.status===304){pass(name);return;}
   // Deployment propagation may temporarily serve the prior implementation.
   // Never count 200 as a pass or retry a different version/hash as unchanged.
   if(r.response.status!==200||r.body?.version!==version||r.body?.sha256!==written.body.sha256)break;
   if(i<3)await wait(1000*(i+1));
  }
  const error=Error(name+'_HTTP_'+attempts.at(-1).status);error.transport_diagnostics={name,attempts};throw error;
 }
 await revalidate('etag-current-304',etag);
 const weakEtag=etag.startsWith('W/')?etag:'W/'+etag;
 await revalidate('etag-weak-current-304',weakEtag);
 await revalidate('etag-list-current-304','"another-version", '+weakEtag);
 await revalidate('etag-wildcard-current-304','*');
 let duplicate=await expect('idempotent-write','/publish',200,post(body));assert(duplicate.body?.duplicate===true,'IDEMPOTENCY_FAILED');
 await expect('stale-version-rejected','/publish',409,post({...body,version:version-1}));
 await expect('same-version-conflict-rejected','/publish',409,post({...body,transport_nonce:'conflicting'}));
 await expect('anonymous-post-denied','/publish',401,{method:'POST',body:'{}'});
 await expect('wrong-token-denied','/publish',401,{...post(body),headers:{Authorization:'Bearer invalid','Content-Type':'application/json'}});
 await expect('bad-signature-denied','/publish',403,{...post(body),body:JSON.stringify({body,signature:'0'.repeat(64)})});
 await expect('large-body-denied','/publish',413,{method:'POST',headers:{Authorization:'Bearer '+token},body:'x'.repeat(131073)});
 await expect('invalid-date-denied','/data?date=bad',400);
 const row={code:'0000',ex:'tse',name:'合成傳輸測試，非真實股票',verification_status:'UNKNOWN',validated:false,P_before:null,P_close:null,tail_return_pct:null,closing_auction_volume:null,intraday_total_volume:null,closing_volume_ratio_pct:null,updated_at:new Date().toISOString()};
 const withRow={...body,version:version+1,rows:[row],unknown_candidate_count:1};
 await expect('per-row-update','/publish',200,post(withRow));
 let changed=await expect('old-etag-does-not-hide-update',data,200,{headers:{'If-None-Match':etag}});assert(changed.body?.rows?.[0]?.code==='0000','ROW_UPDATE_MISSING');
 await expect('forged-verified-denied','/publish',422,post({...withRow,version:version+2,verified_count:1,unknown_candidate_count:0,rows:[{...row,verification_status:'VERIFIED',validated:true}]}));
 await expect('candidate-withdrawal','/publish',200,post({...body,version:version+2}));
 let withdrawn=await expect('withdrawal-public-read',data,200);assert(withdrawn.body?.rows?.length===0,'WITHDRAWAL_NOT_VISIBLE');
 const transport_acceptance={scope:allowLoopback?'SYNTHETIC_LOCAL_WORKERD_NOT_CLOUDFLARE_OR_EXTERNAL_BROWSER':report.scope,commit,started_at:report.started_at,checks_completed_at:new Date().toISOString(),checks:report.checks.slice(),external_browser_read_at:null,physical_mobile_latency_ms:null,writer_keys:'EPHEMERAL_ACCEPTANCE_ONLY_NOT_A_REAL_PUBLISHER_HANDOFF'};
 let final=await expect('final-synthetic-unknown-write','/publish',200,post({...withRow,version:version+3,transport_acceptance}));
 let finalRead=await expect('final-anonymous-read',data,200);assert(finalRead.body?.version===version+3&&finalRead.body?.sha256===final.body?.sha256&&finalRead.body?.mode==='SYNTHETIC'&&finalRead.body?.transport_acceptance?.checks?.length===transport_acceptance.checks.length&&transport_acceptance.checks.length>=19,'FINAL_PUBLIC_READ_MISMATCH');
 report.finished_at=new Date().toISOString();report.version=version+3;report.transport_nonce=nonce;report.sha256=final.body.sha256;report.last_server_write_at=final.body.public_written_at;report.public_data_url=base+data;report.public_page_url=base+'/';
 return report;
}
async function main(){
 const config=JSON.parse(fs.readFileSync(CONFIG,'utf8'));validateTarget(config,process.env);
 function wrangler(args,input){
  // Input goes directly to Wrangler stdin; never echo command output or key values.
  const result=spawnSync('npx',['--yes','wrangler',...args,'--config',CONFIG,'--name',NAME],{input,encoding:'utf8',env:{...process.env,CI:'true',WRANGLER_SEND_METRICS:'false'},timeout:180000,maxBuffer:4*1024*1024});
  assert(result.status===0,'ISOLATED_WRANGLER_STEP_FAILED_'+args[0]+'_'+(result.status??'TIMEOUT'));
 }
 if(config.vars.HANDOFF_REVISION){
  await require('./stage5-cloud-bootstrap.cjs').bootstrap({config,wrangler,acceptance,base:BASE,commit:process.env.WORKERS_CI_COMMIT_SHA});return;
 }
 const {PUBLISH_TOKEN:token,DECISION_KEY:key}={PUBLISH_TOKEN:crypto.randomBytes(32).toString('hex'),DECISION_KEY:crypto.randomBytes(32).toString('hex')};
 const secrets=JSON.stringify({PUBLISH_TOKEN:token,DECISION_KEY:key});
 wrangler(['deploy']);console.log('STAGE4_TEST_WORKER_DEPLOYED');
 wrangler(['secret','bulk'],secrets);console.log('STAGE4_EPHEMERAL_TEST_WRITER_KEYS_INSTALLED_NO_VALUES_LOGGED');
 let report;
 try{report=await acceptance({token,key,commit:process.env.WORKERS_CI_COMMIT_SHA});}
 catch(error){
  // Publish only the bounded synthetic ETag diagnostic; never keys or request headers.
  if(error.transport_diagnostics){
   const body={schema_version:'STAGE3_SELECTION_V1',trade_date:DATE,mode:'SYNTHETIC',is_synthetic:true,version:Date.now()*10+9,generated_at:new Date().toISOString(),rows:[],verified_count:0,research_count:0,unknown_candidate_count:0,universe_count:0,screening_calculable_count:0,screening_unresolved_count:0,
    transport_acceptance:{status:'FAILED',scope:'SYNTHETIC_ETAG_DIAGNOSTIC_NOT_SUCCESS',commit:process.env.WORKERS_CI_COMMIT_SHA,diagnostics:error.transport_diagnostics,external_browser_read_at:null,physical_mobile_latency_ms:null}};
   const {canonical}=await import('./worker.mjs');
   const signature=crypto.createHmac('sha256',key).update(canonical(body)).digest('hex');
   try{await fetch(BASE+'/publish',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({body,signature}),redirect:'error',signal:AbortSignal.timeout(8000)});}catch{}
  }
  throw error;
 }
 report.build_uuid=process.env.WORKERS_CI_BUILD_UUID||null;report.commit=process.env.WORKERS_CI_COMMIT_SHA;
 console.log('STAGE4_SYNTHETIC_TRANSPORT_REPORT '+JSON.stringify(report));
 // These keys are acceptance-only, reissued on the next synthetic test build.
 // They are NOT a persistent credential handoff to the real selection publisher.
}
if(require.main===module)main().catch(error=>{console.error('STAGE4_CLOUD_ACCEPTANCE_FAILED '+error.message);process.exitCode=1;});
module.exports={validateTarget,acceptance,NAME,BRANCH,BASE};
