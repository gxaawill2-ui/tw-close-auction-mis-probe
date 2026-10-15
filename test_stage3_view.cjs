const {test}=require('node:test'),assert=require('node:assert/strict'),view=require('./stage3_view.js');
test('worker +/-3 percent inclusive threshold uses exact decimals',async()=>{
 const {meetsTailThreshold}=await import('./isolated_publication/worker.mjs');
 for(const [price,expected] of [['0.412',true],['0.388',true],['0.411999999999999999',false],['0.388000000000000001',false]])assert.equal(meetsTailThreshold('0.4',price),expected);
 for(const bad of [null,'NaN',true,'-1',{},'1e99999'])assert.equal(meetsTailThreshold('0.4',bad),false);
 assert.equal(meetsTailThreshold('4e-1','4.12e-1'),true);
});
test('first endpoint read cannot replace an embedded newer version',async()=>{
 const {parseHTML}=require('linkedom'),fs=require('node:fs');
 const {document}=parseHTML(fs.readFileSync('reports/2026-10-14-stage3/replay/stage3-preview.html','utf8'));
 const initial=JSON.parse(fs.readFileSync('reports/2026-10-14-stage3/replay/stage3-results.json'));
 const controller=view.create(document,initial),originalFetch=global.fetch;
 try{
  global.fetch=async()=>({ok:true,json:async()=>({...initial,version:initial.version-1,rows:[]})});
  await controller.poll('http://127.0.0.1/data');
  assert.equal(controller.getState().body.version,initial.version);
  assert.equal(controller.getState().body.rows.length,6);assert.equal(controller.reads.length,0);
 }finally{global.fetch=originalFetch;}
});
test('stage3 keeps missing values last for both sort directions',()=>{
 const rows=[{code:'1',closing_auction_volume:null},{code:'2',closing_auction_volume:'4'},{code:'3',closing_auction_volume:'2'}];
 assert.deepEqual(view.order(rows,'closing_auction_volume','desc').map(r=>r.code),['2','3','1']);
 assert.deepEqual(view.order(rows,'closing_auction_volume','asc').map(r=>r.code),['3','2','1']);
});
test('synthetic success is never a formal verified row',()=>assert.equal(view.verified({validated:true,verification_status:'VERIFIED'},{mode:'SYNTHETIC'}),false));
test('external verified flag without raw-derived checks rejected',()=>assert.equal(view.verified({validated:true,verification_status:'VERIFIED'},{mode:'LIVE'}),false));
test('independent evidence unreleased contract rejected',()=>assert.equal(view.verified({validated:true,verification_status:'VERIFIED',independent_evidence:{validated:true,source_contract_live_released:false}},{mode:'LIVE'}),false));
test('even complete supplied proof flags cannot release the page policy',()=>{
 const row={validated:true,verification_status:'VERIFIED',independent_evidence:{validated:true,source_contract_live_released:true},checks:{pre_actual_trade_before_1325:true,pre_last_trade_independently_proven:true,close_independent_finality:true,tail_threshold:true,required_volume_evidence:true}};
 assert.equal(view.verified(row,{mode:'LIVE',liveReleased:true}),false);
});
test('worker default refuses live validation flags',async()=>{
 const {validate}=await import('./isolated_publication/worker.mjs');
 const body={schema_version:'STAGE3_SELECTION_V1',trade_date:'2026-10-14',version:1,mode:'OFFLINE_REPLAY',is_synthetic:false,generated_at:'2026-10-14T13:35:00+08:00',rows:[{code:'2330',ex:'tse',verification_status:'VERIFIED',validated:true}]};
 assert.equal(validate(body,{ALLOW_LIVE_VERIFIED:'false'}),'LIVE_VALIDATION_NOT_RELEASED');
});
