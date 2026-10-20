'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const {parseHTML}=require('linkedom'),ui=require('./docs/status.js');
const path='state/candidates/2026-10-19.json',bytes=fs.readFileSync(path),real=JSON.parse(bytes),live=JSON.parse(fs.readFileSync('state/live/2026-10-19.json'));
// Historical fixture clock: include every valid update on this Taipei trading day.
// Keep the day fixed so future-day evidence still fails production validation.
const calendar=JSON.parse(fs.readFileSync('state/calendars/2026.json')),now=new Date('2026-10-19T23:59:59.999+08:00');
const copy=x=>structuredClone(x),doc=()=>parseHTML(fs.readFileSync('docs/index.html','utf8')).document;
const view=(data=real,health=live)=>ui.model(now,{calendar,data,live:health});
function rendered(data=real,health=live){const d=doc(),v=view(data,health);ui.render(d,v);return {d,v};}

test('real October19 eleven candidates and every price/volume/official field are unchanged',()=>{
 const original=JSON.stringify(real),{d,v}=rendered();
 assert.equal(real.candidate_count,11);assert.deepEqual(real.coverage,{research_calculable:1941,tradable_universe:1974,unknown:33});
 assert.equal(d.getElementById('candidate-count').textContent,'11');assert.equal(v.rows.length,11);
 assert.deepEqual([...v.rows].sort((a,b)=>a.code.localeCompare(b.code)),[...real.candidate_list].sort((a,b)=>a.code.localeCompare(b.code)));
 assert.equal(d.querySelectorAll('.candidate-card').length,11);assert.equal(d.querySelectorAll('#desktop-list tr').length,11);
 assert.match(d.getElementById('message').textContent,/MIS 多次確認通過/);assert.doesNotMatch(d.getElementById('message').textContent,/UNKNOWN|資料不足|33/);
 assert.equal(JSON.stringify(real),original);assert.equal(v.warnings.length,0);
});
test('coverage and pending details are collapsed, with the update time beside the candidate count',()=>{
 const {d}=rendered(),advanced=d.getElementById('coverage-details');assert.equal(advanced.hasAttribute('open'),false);
 for(const id of ['universe','calculable','unknown'])assert.equal(d.getElementById(id).closest('details'),advanced);
 assert.equal(d.getElementById('unknown').textContent,'33');assert.equal(d.querySelector('.overview #unknown'),null);
 assert.ok(d.querySelector('.overview #updated'));assert.equal(d.getElementById('system-warning').hidden,true);
});
test('pending official checks never hide MIS-qualified candidates',()=>{
 const p=copy(real);for(const r of p.candidate_list)r.official_price_result='PENDING';const {d,v}=rendered(p);
 assert.equal(v.rows.length,11);assert.equal(d.querySelectorAll('.candidate-card').length,11);assert.match(d.querySelector('.candidate-card').textContent,/待盤後核對/);
});
for(const [name,health,pattern] of [
 ['whole market failure',{capture_outcome:'CAPTURE_FAILED',status:'failed'},/擷取未完整完成/],
 ['incomplete pool',{universe_audit_status:'INCOMPLETE_OFFICIAL_SOURCES'},/股票池來源不完整/],
 ['interrupted capture',{status:'running'},/流程逾時/],
 ['publication failure',{candidate_publication:{status:'FAILED'}},/候選發布失敗/],
 ['failed mandatory phase',{capture_completion:{core_capture_complete:false}},/擷取未完整完成/],
])test(name+' stays visible even beside a previously published valid result',()=>{
 const h={trade_date:'2026-10-19',...health},{d,v}=rendered(real,h);
 assert.equal(v.rows.length,11);assert.equal(d.getElementById('system-warning').hidden,false);assert.match(d.getElementById('system-warning').textContent,pattern);
});
test('no published result after the close cannot appear as zero qualified stocks',()=>{
 const {d,v}=rendered(null,null);assert.notEqual(v.state,'ZERO_CANDIDATES');assert.equal(v.rows.length,0);
 assert.match(d.getElementById('system-warning').textContent,/尚未成功載入或發布/);
});
test('major coverage anomalies warn without changing qualification or filling missing evidence',()=>{
 const p=copy(real);p.coverage.unknown=100;p.coverage.research_calculable=1874;
 const {v,d}=rendered(p,null);assert.equal(v.rows.length,11);assert.match(d.getElementById('system-warning').textContent,/大量股票/);
 const zero=copy(real);zero.candidate_list=[];zero.candidate_count=0;zero.coverage.research_calculable=0;zero.coverage.unknown=1974;
 assert.notEqual(view(zero,null).state,'ZERO_CANDIDATES');assert.match(view(zero,null).headline,/尚無.*已確認候選/);
});
test('synthetic revision, withdrawal, UNKNOWN and rejection of older revisions still work',()=>{
 const p=copy(real),removed=p.candidate_list.shift();p.candidate_count--;p.revision++;p.evidence_sequence++;p.content_hash='a'.repeat(64);
 p.unknown_candidate_list=[{ex:removed.ex,code:removed.code,reason:'MISSING_COMPARISON_BASELINE'}];
 p.withdrawals=[{ex:removed.ex,code:removed.code,reason:'UNKNOWN'}];
 const accepted=ui.acceptRevision(real,p),{d,v}=rendered(accepted);
 assert.equal(v.rows.length,10);assert.equal(d.querySelector('[data-code="'+removed.code+'"]'),null);
 assert.match(d.getElementById('message').textContent,/已撤回/);assert.match(d.getElementById('pending-details').textContent,new RegExp(removed.code));
 assert.equal(d.getElementById('coverage-details').hasAttribute('open'),false);assert.throws(()=>ui.acceptRevision(p,real),/舊版本/);
});
test('same historical dates remain readable, other dates cannot substitute today',()=>{
 const old=JSON.parse(fs.readFileSync('state/candidates/2026-10-08.json'));
 assert.equal(ui.model(new Date('2026-10-08T18:30:00+08:00'),{calendar,data:old}).rows.length,7);
 const v=view(old,null);assert.equal(v.rows.length,0);assert.equal(v.state,'UPDATE_FAILED');assert.match(v.error,/日期不符/);
});
test('the original JSON bytes and all unresolved symbols remain untouched',()=>{
 const before=crypto.createHash('sha256').update(bytes).digest('hex');rendered();
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex'),before);
 assert.equal(real.unresolved_symbols.length,33);assert.equal(real.coverage.unknown,33);
});

test('per-stock check columns and mobile labels are hidden without dropping underlying data',()=>{
 const {d,v}=rendered();assert.equal(d.querySelectorAll('th.candidate-check').length,2);
 assert.equal(d.querySelectorAll('#desktop-list td.candidate-check').length,22);
 const css=fs.readFileSync('docs/status.css','utf8');assert.match(css,/#candidate-table \.candidate-check,\.candidate-card \.card-footer,\.candidate-card \.card-volume-status\{display:none\}/);
 assert.equal(v.rows.length,11);assert.ok(v.rows.every(r=>r.official_price_result&&r.confidence_level));assert.match(d.getElementById('message').textContent,/MIS 多次確認通過/);
});
test('an official close mismatch still warns even when the individual check label is hidden',()=>{
 const p=copy(real);p.candidate_list[0].official_price_result='MISMATCH';const {d,v}=rendered(p);
 assert.equal(v.rows.length,11);assert.equal(d.getElementById('system-warning').hidden,false);assert.match(d.getElementById('system-warning').textContent,/官方盤後資料不符/);
});

test('historical rendering accepts late same-day official updates through the final millisecond',()=>{
 for(const time of ['17:50:33.938','20:00:00.000','22:43:08.185','23:59:59.999']){
  const p=copy(real);p.updated_at='2026-10-19T'+time+'+08:00';
  assert.equal(view(p).rows.length,11,time);assert.equal(view(p).error,'',time);
 }
});
test('future same-day updates still fail at an actual earlier viewing time',()=>{
 const p=copy(real);p.updated_at='2026-10-19T17:50:00+08:00';
 const v=ui.model(new Date('2026-10-19T16:00:00+08:00'),{calendar,data:p});
 assert.equal(v.rows.length,0);assert.equal(v.state,'UPDATE_FAILED');assert.match(v.error,/更新時間不符/);
});
test('next-day updates remain invalid for the fixed historical trading day',()=>{
 const p=copy(real);p.updated_at='2026-10-20T00:00:00+08:00';
 assert.equal(view(p).rows.length,0);assert.match(view(p).error,/更新時間不符/);
 const next=copy(real);next.trade_date='2026-10-20';
 assert.equal(view(next).rows.length,0);assert.match(view(next).error,/日期不符/);
});
test('an older update cannot overwrite accepted data even with a higher revision',()=>{
 const p=copy(real);p.revision++;p.evidence_sequence++;p.content_hash='c'.repeat(64);
 p.updated_at=new Date(new Date(real.updated_at).getTime()-1).toISOString();
 assert.throws(()=>ui.acceptRevision(real,p),/拒絕較早更新的資料/);
});
