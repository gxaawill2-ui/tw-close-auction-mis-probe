const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {startWorker}=require('./stage3_worker_runtime.cjs');
async function main(){
 const {worker,token,key,url}=await startWorker();
 const {canonical}=await import('./isolated_publication/worker.mjs');
 const view=JSON.parse(fs.readFileSync(path.join(__dirname,'reports/2026-10-14-stage3/replay/stage3-results.json')));
 const checks=[],timings=[];let version=0;
 async function post(body,override){
  const signed={body,signature:crypto.createHmac('sha256',key).update(canonical(body)).digest('hex')};
  const start=performance.now();const r=await fetch(url+'/publish',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(override||signed)});
  timings.push({kind:'LOCAL_WORKER_HTTP_NOT_PUBLIC_INTERNET',http_status:r.status,roundtrip_ms:performance.now()-start});return r;
 }
 const pass=(name)=>checks.push({name,status:'PASS'});
 try{
  assert.equal((await fetch(url+'/data?date='+view.trade_date)).status,404);pass('empty-is-404-not-completed');
  let body={...view,version:++version};let r=await post(body);assert.equal(r.status,200);const receipt=await r.json();assert.ok(receipt.public_written_at);pass('signed-write-has-real-receipt');
  const start=performance.now(),read=await fetch(url+'/data?date='+body.trade_date),saved=await read.json();
  assert.equal(saved.version,body.version);assert.equal(saved.sha256,receipt.sha256);assert.equal(saved.verified_count,0);
  timings.push({kind:'LOCAL_WORKER_HTTP_NOT_PUBLIC_INTERNET',read_ms:performance.now()-start,public_written_at:saved.public_written_at,external_browser_observed_at:null});pass('read-after-write-matches-content');
  assert.match(read.headers.get('Cache-Control'),/no-store/);assert.equal(read.headers.get('Access-Control-Allow-Origin'),'*');pass('no-store-and-public-read-cors');
  r=await post(body);assert.equal(r.status,200);assert.equal((await r.json()).duplicate,true);pass('same-version-idempotent');
  r=await post({...body,version:body.version,rows:[],research_count:0});assert.equal(r.status,409);pass('same-version-conflict-rejected');
  r=await post({...body,version:++version,rows:body.rows.slice(0,1),research_count:1});assert.equal(r.status,200);pass('partial-batch-published-without-market-barrier');
  const fresh=await fetch(url+'/data?date='+body.trade_date,{headers:{'If-None-Match':read.headers.get('ETag')}});assert.equal(fresh.status,200);pass('old-etag-cannot-hide-update');
  r=await post({...body,version:1});assert.equal(r.status,409);pass('version-regression-rejected');
  const forged={...body,version:++version,verified_count:1,rows:[{...body.rows[0],validated:true,verification_status:'VERIFIED'}]};
  r=await post(forged);assert.equal(r.status,422);pass('fabricated-verified-rejected-even-signed');
  r=await post(body,{body,signature:'0'.repeat(64)});assert.equal(r.status,403);pass('signature-tamper-rejected');
  r=await fetch(url+'/publish',{method:'POST',body:'{}'});assert.equal(r.status,401);pass('anonymous-write-denied');
  r=await fetch(url+'/publish',{method:'POST',headers:{Authorization:'Bearer '+token},body:'x'.repeat(131073)});assert.equal(r.status,413);pass('large-payload-rejected');
  assert.equal((await fetch(url+'/data?date=garbage')).status,400);pass('invalid-date-denied');
  const output=process.env.STAGE3_REPORT_DIR||path.join(__dirname,'reports/2026-10-14-stage3');fs.mkdirSync(output,{recursive:true});
  fs.writeFileSync(path.join(output,'worker-acceptance.json'),JSON.stringify({runtime:'Miniflare / workerd SQLite Durable Object',scope:'LOOPBACK_ONLY_NOT_PUBLIC_DEPLOYMENT',checks,timings,formal_signals:0},null,2));
  console.log(JSON.stringify(checks));
 }finally{await worker.dispose();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
