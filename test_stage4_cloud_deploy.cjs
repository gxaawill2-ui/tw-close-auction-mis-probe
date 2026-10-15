'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {validateTarget,acceptance,BRANCH}=require('./isolated_publication/stage4-cloud-deploy.cjs');
const configuration=()=>JSON.parse(fs.readFileSync('./isolated_publication/stage4.wrangler.jsonc','utf8'));
const environment=()=>({WORKERS_CI:'1',WORKERS_CI_BRANCH:BRANCH,WORKERS_CI_COMMIT_SHA:'a'.repeat(40)});
test('deployment refuses local invocation, main, wrong Worker, namespace, routes and live release before mutation',()=>{
 assert.doesNotThrow(()=>validateTarget(configuration(),environment()));
 for(const env of [{}, {...environment(),WORKERS_CI_BRANCH:'main'},{...environment(),WORKERS_CI_COMMIT_SHA:'bad'}])assert.throws(()=>validateTarget(configuration(),env));
 for(const change of [c=>c.name='tw-index-events-relay',c=>c.vars.ALLOW_LIVE_VERIFIED='true',c=>c.routes=[],c=>c.triggers={},c=>c.durable_objects.bindings[0].class_name='DispatchGate',c=>c.migrations[0].new_sqlite_classes=['DispatchGate'],c=>c.assets.directory='../docs']){
  const c=configuration();change(c);assert.throws(()=>validateTarget(c,environment()));
 }
});
test('acceptance refuses another destination before sending keys',async()=>{
 let called=false;await assert.rejects(()=>acceptance({base:'https://example.com',token:'x'.repeat(64),key:'y'.repeat(64),fetcher:()=>{called=true;}}));assert.equal(called,false);
});
test('synthetic cloud acceptance against REAL LOCAL workerd SQLite: signed writes, conflicts, tamper, withdrawal and no forged verification',async()=>{
 const {worker,token,key,url}=await require('./stage3_worker_runtime.cjs').startWorker();
 try{
  const report=await acceptance({base:url,token,key,allowLoopback:true});
  assert.ok(report.checks.length>=20);assert.ok(report.requests.every(r=>r.response_received_at>=r.requested_at));assert.equal(report.external_browser_read_at,null);assert.equal(report.physical_mobile_latency_ms,null);
  report.scope='SYNTHETIC_LOCAL_WORKERD_NOT_CLOUDFLARE_OR_EXTERNAL_BROWSER';
  const encoded=JSON.stringify(report);assert.ok(!encoded.includes(token)&&!encoded.includes(key));
  fs.mkdirSync('reports/2026-10-15-stage4/cloud-preparation',{recursive:true});fs.writeFileSync('reports/2026-10-15-stage4/cloud-preparation/transport-local.json',JSON.stringify(report,null,2)+'\n');
 }finally{await worker.dispose();}
});
