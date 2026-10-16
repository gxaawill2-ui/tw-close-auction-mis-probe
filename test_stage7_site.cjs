const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{parseHTML}=require('linkedom');
const view=require('./stage3_view.js');global.Stage3View=view;
const boot=require('./stage7_site_bootstrap.js');
const config={enabled:true,api_base:'https://tw-tail-stage4-20261015-test.gxaawill2.workers.dev',live_released:false};
function sample(){return {schema_version:'STAGE3_SELECTION_V1',trade_date:'2026-10-19',mode:'LIVE',is_synthetic:false,public_data_policy:'MIS_DERIVED_RESEARCH_NO_FUGLE_RAW',version:1,generated_at:'2026-10-19T13:35:00+08:00',universe_count:2,screening_calculable_count:1,screening_unresolved_count:1,research_count:1,unknown_candidate_count:0,verified_count:0,rows:[{ex:'tse',code:'2330',name:'合成介面驗收',verification_status:'RESEARCH_ONLY',validated:false}]};}
test('proposed formal panel is opt-in and cannot display yesterday, synthetic or forged verified',()=>{
 const {document}=parseHTML('<section id="stage7-live" hidden></section><section id="existing">保留正式研究</section>');
 assert.equal(boot.setup(document,{enabled:false}),null);assert.equal(document.getElementById('existing').textContent,'保留正式研究');
 const now=new Date('2026-10-19T13:35:01+08:00'),b=sample();boot.check(b,'2026-10-19',now);
 for(const bad of [{...b,trade_date:'2026-10-16'},{...b,mode:'SYNTHETIC',is_synthetic:true},{...b,verified_count:1,research_count:0,rows:[{...b.rows[0],validated:true,verification_status:'VERIFIED'}]}])assert.throws(()=>boot.check(bad,'2026-10-19',now));
 const c=boot.setup(document,config);assert.equal(c.apply(b,now),true);assert.throws(()=>c.apply({...b,rows:[]},now)); // invalid counts must fail before any render
 assert.equal(c.apply({...b,rows:[],research_count:0},now),false);
});
test('proposed panel withdrawal and daily rollover cannot preserve stale stocks',()=>{
 const {document}=parseHTML('<section id="stage7-live" hidden></section>'),c=boot.setup(document,config),b=sample(),now=new Date('2026-10-19T13:35:01+08:00');
 c.apply(b,now);assert.match(document.getElementById('stage3-rows').textContent,/2330/);
 c.apply({...b,version:2,research_count:0,rows:[]},now);assert.equal(document.getElementById('stage3-rows').textContent,'');
 c.clearDay(new Date('2026-10-20T09:00:00+08:00'));assert.equal(document.getElementById('stage7-live').hidden,true);
});
