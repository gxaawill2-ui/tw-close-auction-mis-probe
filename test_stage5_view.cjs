const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {parseHTML}=require('linkedom'),view=require('./stage3_view.js');
function fixture(){
 const {document}=parseHTML(fs.readFileSync('isolated_publication/stage4-site/index.html','utf8'));
 const rows=Array.from({length:6},(_,i)=>({code:String(2000+i),ex:'tse',name:'合成介面測試',
  P_before:'100',P_close:'104',tail_return_pct:'4',closing_auction_volume:'1',intraday_total_volume:'10',closing_volume_ratio_pct:'10',
  verification_status:i<2?'VERIFIED':'UNKNOWN',validated:i<2,
  independent_evidence:{validated:true,source_contract_live_released:true},
  checks:Object.fromEntries(['pre_actual_trade_before_1325','pre_last_trade_independently_proven','close_independent_finality','tail_threshold','required_volume_evidence'].map(k=>[k,true]))}));
 const body={schema_version:'STAGE3_SELECTION_V1',mode:'LIVE',is_synthetic:false,trade_date:'2026-10-16',
  generated_at:'2026-10-16T13:35:00+08:00',version:10,rows,universe_count:2000,screening_calculable_count:1990,screening_unresolved_count:10};
 return {document,body};
}
test('UI separates total candidates, research, verified and unknown with explicit released test configuration',()=>{
 const {document,body}=fixture();view.create(document,body,{liveReleased:true});
 assert.equal(document.getElementById('stage3-research').textContent,'0');
 assert.equal(document.getElementById('stage3-verified').textContent,'2');
 assert.equal(document.getElementById('stage3-unknown').textContent,'4');
 assert.match(document.getElementById('stage5-summary').textContent,/初篩候選共 6 檔：研究 0 檔、UNKNOWN 4 檔、完整驗證 2 檔/);
 // Actual bootstrap remains unreleased, so supplied flags cannot grant two verified.
 view.create(document,body);assert.equal(document.getElementById('stage3-verified').textContent,'0');
 assert.equal(document.getElementById('stage3-unknown').textContent,'6');
});
test('poll coalesces concurrent reads and records actual browser receipt without accepting older versions',async()=>{
 const {document,body}=fixture(),controller=view.create(document,body),oldFetch=global.fetch;let release,calls=0;
 try{
  global.fetch=()=>{calls++;return new Promise(resolve=>{release=resolve;});};
  const first=controller.poll('http://127.0.0.1/data');
  await controller.poll('http://127.0.0.1/data');assert.equal(calls,1);
  release({ok:true,json:async()=>({...body,version:11,sha256:'test-only',rows:[]})});await first;
  assert.equal(controller.getState().body.version,11);assert.equal(controller.reads.length,1);
  assert.ok(controller.reads[0].browser_observed_at>=controller.reads[0].browser_requested_at);
  global.fetch=async()=>({ok:true,json:async()=>({...body,version:10})});await controller.poll('http://127.0.0.1/data');
  assert.equal(controller.getState().body.version,11);assert.equal(controller.reads.length,1);
 }finally{global.fetch=oldFetch;}
});

test('research and UNKNOWN counts do not overlap and rows remain independently visible',()=>{
 const {document,body}=fixture();
 body.rows[0]={...body.rows[0],validated:false,verification_status:'RESEARCH_ONLY'};
 body.rows[1]={...body.rows[1],validated:false,verification_status:'RESEARCH_ONLY'};
 view.create(document,body);
 assert.equal(document.getElementById('stage3-research').textContent,'2');
 assert.equal(document.getElementById('stage3-unknown').textContent,'4');
 assert.equal(document.getElementById('stage3-verified').textContent,'0');
 assert.equal(document.querySelectorAll('#stage3-rows tr').length,6);
});
