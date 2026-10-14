const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {parseHTML}=require('linkedom'),ui=require('./docs/status.js');
const calendar={year:2026,closed_dates:[]};
const day='2026-10-14',now=new Date(day+'T14:10:00+08:00');
function live(){return {trade_date:day,run_id:'original',status:'failed',capture_outcome:'CAPTURE_FAILED',universe_count:1970,
 capture_completion:{research_unresolved_count:24},convergence:{research_calculable_count:1946,both_validated_count:0},
 snapshots:{close_reference_B:{success_count:1920,missing_count:50}},updated_at:day+'T13:34:25+08:00',official_validation:'PENDING_SCHEDULED_POSTMARKET'};}
const model=(extra={})=>ui.model(now,{calendar,live:live(),...extra});
test('skip SUCCESS receipt never overwrites original failed capture',()=>{
 const view=model({execution:{status:'success',mode:'live',run_id:'backup',decision:'skipped_existing_capture'}});
 assert.equal(view.state,'CAPTURE_FAILED');assert.equal(view.rawMissing,50);assert.equal(view.coverage.research_calculable,1946);
 assert.equal(view.verified,0);assert.equal(view.nextCheck,'14:50:00');
});
test('same-day official comparison cannot erase true capture failure',()=>{
 const view=model({official:{trade_date:day,status:'SAME_DATE_COMPARISON_ONLY',source_capture_run_id:'original'}});
 assert.equal(view.state,'CAPTURE_FAILED');assert.equal(view.officialStatus,'SAME_DATE_COMPARISON_ONLY');assert.equal(view.verified,0);
});
test('previous date and wrong capture run official state cannot appear as current validation',()=>{
 for(const official of [{trade_date:'2026-10-13',status:'SAME_DATE_COMPARISON_ONLY'},{trade_date:day,status:'SAME_DATE_COMPARISON_ONLY',source_capture_run_id:'wrong'}]){
  assert.equal(model({official}).official,null);
 }
});
test('failed publication still exposes actual pool, research coverage and raw batch deficit',()=>{
 const doc=parseHTML(fs.readFileSync('docs/index.html','utf8')).document;ui.render(doc,model());
 assert.equal(doc.getElementById('universe').textContent,'1,970');assert.equal(doc.getElementById('calculable').textContent,'1,946');
 assert.equal(doc.getElementById('unknown').textContent,'24');assert.match(doc.getElementById('capture-detail').textContent,/缺 50 檔/);
 assert.match(doc.getElementById('official-detail').textContent,/完整策略已驗證 0/);assert.match(doc.getElementById('updated').textContent,/13:34:25/);
 assert.equal(doc.querySelectorAll('.candidate-card').length,0);
});
test('official schedule shows the next slot and ends without inventing a completed check',()=>{
 for(const [clock,next] of [['14:49:59','14:50:00'],['14:50:00','15:20:00'],['15:20:00','17:50:00'],['17:50:00',null]]){
  const view=ui.model(new Date(day+'T'+clock+'+08:00'),{calendar,live:live()});assert.equal(view.nextCheck,next);assert.equal(view.verified,0);
 }
});
test('partial capture can show research list while official is pending, always validated=false',()=>{
 const old=JSON.parse(fs.readFileSync('state/candidates/2026-10-08.json','utf8'));
 old.trade_date=day;old.generated_at=day+'T13:35:00+08:00';old.capture_outcome='CAPTURE_PARTIAL';
 const state=live();state.capture_outcome='CAPTURE_PARTIAL';state.status='partial';
 const view=model({data:old,live:state});assert.equal(view.state,'PARTIAL');assert.equal(view.rows.length,7);
 assert.equal(view.verified,0);assert.ok(view.rows.every(r=>r.validated===false));assert.match(view.message,/UNKNOWN/);
});
test('a failed candidate fetch cannot hide independent live and official status',async()=>{
 const vm=require('node:vm'),doc=parseHTML(fs.readFileSync('docs/index.html','utf8')).document,RealDate=Date;
 class Clock extends RealDate{constructor(...a){super(...(a.length?a:[day+'T14:10:00+08:00']));}static now(){return new RealDate(day+'T14:10:00+08:00').getTime();}}
 const context={document:doc,Date:Clock,Intl,AbortController,Event:doc.defaultView.Event,
  setTimeout:()=>1,clearTimeout:()=>{},fetch:async url=>{
   const name=String(url).split('/main/')[1].split('?')[0];
   if(name.includes('/candidates/'))return {status:503,ok:false};
   const value=name.includes('/calendars/')?calendar:name.includes('/live/')?live():{trade_date:day,status:'RECHECKING'};
   return {status:200,ok:true,json:async()=>value};
  }};
 vm.runInNewContext(fs.readFileSync('docs/status.js','utf8'),context);await new Promise(resolve=>setImmediate(resolve));
 assert.equal(context.TailDashboardView.state,'CAPTURE_FAILED');assert.equal(doc.getElementById('universe').textContent,'1,970');
 assert.match(doc.getElementById('official-detail').textContent,/正在重新核對/);assert.match(doc.getElementById('network').textContent,/HTTP 503/);
});
