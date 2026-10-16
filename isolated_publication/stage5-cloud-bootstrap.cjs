'use strict';
// Persist this isolated Worker's writer keys; only an explicit new revision rotates them.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
async function bootstrap({config,wrangler,acceptance,base,commit,fetcher=fetch}){
 const revision=config.vars.HANDOFF_REVISION;
 if(!/^stage5-20261016-v\d+$/.test(revision))throw Error('INVALID_HANDOFF_REVISION');
 const old=await fetcher(base+'/health',{redirect:'error',signal:AbortSignal.timeout(8000)}).then(r=>r.json());
 if(old.handoff_revision===revision){
  // Do not silently invalidate GitHub's stored credentials on a routine build.
  const prior=await fetcher(base+'/data?date=2099-01-02',{redirect:'error',signal:AbortSignal.timeout(8000)}).then(r=>r.json());
  if(prior.credential_handoff?.revision!==revision)throw Error('PRIOR_HANDOFF_NOT_RECOVERABLE_DO_NOT_ROTATE');
  wrangler(['deploy']);
  console.log('STAGE5_DEPLOYED_EXISTING_WRITER_CREDENTIALS_PRESERVED');return;
 }
 const token=crypto.randomBytes(32).toString('hex'),key=crypto.randomBytes(32).toString('hex');
 const publicKey=fs.readFileSync(path.join(__dirname,'stage5-handoff-public.pem'));
 const sealed=crypto.publicEncrypt({key:publicKey,oaepHash:'sha256'},Buffer.from(JSON.stringify({token,key}))).toString('base64');
 wrangler(['secret','bulk'],JSON.stringify({PUBLISH_TOKEN:token,DECISION_KEY:key}));
 wrangler(['deploy']);
 const report=await acceptance({token,key,commit});
 const {canonical}=await import('./worker.mjs');
 const body={schema_version:'STAGE3_SELECTION_V1',trade_date:'2099-01-02',mode:'SYNTHETIC',is_synthetic:true,
  version:Date.now()*10,generated_at:new Date().toISOString(),rows:[],verified_count:0,research_count:0,unknown_candidate_count:0,
  universe_count:0,screening_calculable_count:0,screening_unresolved_count:0,
  credential_handoff:{revision,algorithm:'RSA-OAEP-SHA256',sealed,scope:'ISOLATED_WORKER_WRITER_ONLY'},
  transport_acceptance:{scope:report.scope,checks:report.checks,commit,external_browser_read_at:null,physical_mobile_latency_ms:null}};
 const signature=crypto.createHmac('sha256',key).update(canonical(body)).digest('hex');
 const r=await fetcher(base+'/publish',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
  body:JSON.stringify({body,signature}),redirect:'error',signal:AbortSignal.timeout(8000)});
 if(r.status!==200)throw Error('SEALED_HANDOFF_WRITE_FAILED_'+r.status);
 console.log('STAGE5_PERSISTENT_WRITER_HANDOFF_SEALED_NO_PLAINTEXT_LOGGED');
 console.log('STAGE5_SYNTHETIC_TRANSPORT_REPORT '+JSON.stringify(report));
}
module.exports={bootstrap};
