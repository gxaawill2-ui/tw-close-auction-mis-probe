const {test}=require('node:test'),assert=require('node:assert/strict'),view=require('./stage3_view.js');
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
