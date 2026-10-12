const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {parseHTML}=require('linkedom'),ui=require('./docs/status.js'),events=require('./docs/events.js');
const payload=JSON.parse(fs.readFileSync('state/candidates/2026-10-08.json'));
const calendar=JSON.parse(fs.readFileSync('state/calendars/2026.json'));
const doc=()=>parseHTML(fs.readFileSync('docs/index.html','utf8')).document;
const view=()=>ui.model(new Date('2026-10-08T18:30:00+08:00'),{calendar,data:payload});
const keys=['closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct'];
test('market section stays in DOM hidden and data logic can still render it',()=>{
 const d=doc();assert.equal(d.querySelector('.market-closing').hidden,true);
 assert.match(fs.readFileSync('docs/status.css','utf8'),/\[hidden\]\{display:none!important\}/);
 assert.equal(d.querySelectorAll('.market-metrics dd').length,5);
});
test('tail display rounds to two fixed places with signs on both layouts; payload unchanged',()=>{
 const before=JSON.stringify(payload),d=doc(),v=view();
 v.rows=v.rows.map((r,i)=>({...r,tail_return_pct:[5.959,4.609,3.935,3.279,3.261,-3.935,-3][i]}));
 ui.render(d,v);
 const expected=['+5.96%','+4.61%','+3.94%','+3.28%','+3.26%','-3.94%','-3.00%'];
 for(const selector of ['#desktop-list .tail','#mobile-list .tail'])assert.deepEqual([...d.querySelectorAll(selector)].map(x=>x.textContent),expected);
 assert.equal(JSON.stringify(payload),before);
});
test('rounded 3.00 does not admit a raw 2.9999 candidate, raw 3.0001 still qualifies',()=>{
 for(const [pct,valid] of [[2.9999,false],[3.0001,true],[-2.9999,false],[-3.0001,true]]){
  const p=structuredClone(payload),r=p.candidate_list[0];r.P_before='100';r.P_close=String(100*(1+pct/100));r.tail_return_pct=String(pct);
  const v=ui.model(new Date('2026-10-08T18:30:00+08:00'),{calendar,data:p});
  assert.equal(v.rows.length,valid?7:0);
 }
});
for(const key of keys)for(const direction of ['desc','asc'])test(key+' '+direction+' uses raw numeric values, stable ties and missing last',()=>{
 const rows=[['small','2'],['large','10'],['tie','2'],['missing',null],['undefined',undefined],['invalid','bad'],['unverified','100'],['precise','2.0001'],['empty','']].map(([code,value])=>({code,[key]:value,volume_status:code==='unverified'?'UNVERIFIED':'MIS_EVIDENCE_CONFIRMED'}));
 const original=structuredClone(rows),sorted=ui.sortRows(rows,{key,direction});
 assert.deepEqual(sorted.map(x=>x.code),direction==='desc'?['large','precise','small','tie','missing','undefined','invalid','unverified','empty']:['small','tie','precise','large','missing','undefined','invalid','unverified','empty']);
 assert.deepEqual(rows,original);assert.equal(sorted.length,rows.length);
});
test('sort changes descend first, toggle ascending and reset when field changes',()=>{
 let s=ui.nextSort(null,keys[0]);assert.equal(s.direction,'desc');s=ui.nextSort(s,keys[0]);assert.equal(s.direction,'asc');s=ui.nextSort(s,keys[1]);assert.equal(s.direction,'desc');
 const d=doc(),v=view();ui.render(d,v,s);
 assert.equal(d.querySelectorAll('th[aria-sort="descending"]').length,1);
 assert.equal(d.querySelectorAll('th[aria-sort="none"]').length,2);
 assert.match(d.getElementById('sort-summary').textContent,/全日盤中量.*↓/);
 assert.equal(d.getElementById('mobile-sort-field').value,keys[1]);
 assert.deepEqual([...d.querySelectorAll('#desktop-list tr')].map(x=>x.dataset.code),[...d.querySelectorAll('.candidate-card')].map(x=>x.dataset.code));
});
test('native desktop buttons bind, render immediately and keep the active sort across refresh',()=>{
 const d=doc(),v=view();let sort=null;ui.bindSort(d,()=>sort,next=>{sort=next;ui.render(d,v,sort);});
 d.querySelector('[data-sort-key="closing_auction_volume"]').click();assert.equal(sort.direction,'desc');
 d.querySelector('[data-sort-key="closing_auction_volume"]').click();assert.equal(sort.direction,'asc');
 ui.render(d,v,sort);assert.equal(d.querySelector('th[aria-sort="ascending"] button').dataset.sortKey,keys[0]);
});
test('unconfirmed relation uses exact text; official match label and evidence remain intact',()=>{
 const label='ETF／指數換股關聯：資料不足，尚無法確認';
 assert.equal(events.relation({code:'2330',market:'TWSE'},[],'2026-10-08','2026-10-08T18:30:00+08:00').label,label);
 const e={event_name:'MSCI 定審',information_available_as_of:'2026-10-07T00:00:00+08:00',closing_impact_date:'2026-10-08',affected_stocks:[{code:'2330',market:'TWSE',market_status:'OFFICIAL_CONFIRMED',change_type:'ADDITION'}]};
 const before=JSON.stringify(e),r=events.relation({code:'2330',market:'TWSE'},[e],'2026-10-08','2026-10-08T18:30:00+08:00');
 assert.equal(r.label,'MSCI 定審 · 納入');assert.equal(r.matches.length,1);
 assert.equal(events.relation({code:'2330',market:'TPEx'},[e],'2026-10-08','2026-10-08T18:30:00+08:00').label,label);assert.equal(JSON.stringify(e),before);
});
