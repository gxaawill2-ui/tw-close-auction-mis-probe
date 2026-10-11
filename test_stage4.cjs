const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {parseHTML}=require('linkedom'),events=require('./docs/events.js'),market=require('./docs/market-closing.js');
const now=new Date('2026-10-12T18:00:00+08:00'),seen='2026-10-11T08:00:00+08:00';
const e={event_id:'a',event_name:'review',index_name:'index',source_url:'https://issuer.example/official',first_seen_at:seen,information_available_as_of:seen,event_status:'DATE_ONLY',close_date_status:'EXPECTED_CLOSE_WATCH_DATE',announcement_date:'2026-10-12',effective_date:'2026-10-20',closing_impact_date:'2026-10-19',affected_stocks:[],related_etf_codes:['0050'],evidence_level:'OFFICIAL_ISSUER_DATE_ONLY'};
const doc=()=>parseHTML(fs.readFileSync('docs/index.html','utf8')).document;
const data=event=>({schema_version:1,timezone:'Asia/Taipei',generated_at:seen,coverage_status:'PARTIAL',events:[event]});
test('calendar-only review is excluded without changing stored dates',()=>{assert.equal(events.model(now,data(e),null).upcoming.length,0);assert.equal(e.effective_date,'2026-10-20');});
test('official nonzero change counts qualify; zero, missing, negative do not',()=>{
 for(const c of [{additions:1,deletions:0},{additions:0,deletions:2}])assert.equal(events.model(now,data({...e,constituent_counts:c}),null).upcoming.length,1);
 for(const c of [undefined,{additions:0,deletions:0},{additions:-1,deletions:2},{additions:'2',deletions:0}])assert.equal(events.model(now,data({...e,constituent_counts:c}),null).upcoming.length,0);
});
test('PARTIAL and failed sources preserve material events with independent caution',()=>{
 const d=doc();events.render(d,events.model(now,data({...e,constituent_counts:{additions:1,deletions:0}}),null,'timeout'));
 assert.equal(d.querySelectorAll('.event-row').length,1);assert.match(d.querySelector('#event-note').textContent,/部分官方來源/);assert.match(d.querySelector('#event-upcoming').textContent,/官方新增 1/);
 assert.match(d.querySelector('#event-upcoming').textContent,/預估/);assert.match(d.querySelector('#event-upcoming').textContent,/不等於基金/);
});
test('material evidence learned after cutoff is unavailable',()=>{assert.equal(events.model(now,data({...e,constituent_counts:{additions:1,deletions:0},information_available_as_of:'2026-10-12T19:00:00+08:00'}),null).upcoming.length,0);});
test('unknown dates cannot be promoted by confirmed material changes',()=>{assert.equal(events.model(now,data({...e,constituent_counts:{additions:1,deletions:0},close_date_status:'DATE_UNVERIFIED'}),null).upcoming.length,0);});
test('homepage empty material state and no controls',()=>{const d=doc();events.render(d,events.model(now,data(e),null));assert.match(d.querySelector('#event-empty').textContent,/目前尚無已確認實質調整/);assert.equal(d.querySelectorAll('button,input,select,form,[role="button"]').length,0);});
const cal={year:2026,status:'OFFICIAL_ANNUAL_CALENDAR',closed_dates:['2026-10-09']};
const sample={schema_version:1,trade_date:'2026-10-12',market_scope:market.SCOPE,generated_at:seen,source_quality:'VERIFIED_SAME_SCOPE',coverage_ratio:1,missing_stocks:[],official_reconciliation:{status:'MATCH_SAME_SCOPE'},closing_auction_turnover_twd:'200',daily_turnover_twd:'1000',closing_turnover_share_pct:20,historical_median_share_pct:10,relative_multiple:2,historical_sample_count:20,threshold_status:'CALIBRATED',is_closing_volume_spike:true,status:'VERIFIED'};
test('market yes/no requires complete calibrated same scope',()=>{assert.equal(market.model(now,sample,cal).status,'有');assert.equal(market.model(now,{...sample,is_closing_volume_spike:false},cal).status,'沒有');});
test('market missing, partial, provisional, future, previous day, invalid figures are unknown',()=>{
 for(const d of [null,{...sample,threshold_status:'PROVISIONAL'},{...sample,coverage_ratio:.99},{...sample,historical_sample_count:19},{...sample,market_scope:'ALL_SECURITIES'},{...sample,closing_turnover_share_pct:21},{...sample,generated_at:'2026-10-12T19:00:00+08:00'},{...sample,trade_date:'2026-10-08'},{...sample,daily_turnover_twd:0},{...sample,missing_stocks:['2330']}])assert.equal(market.model(now,d,cal).status,'尚未確認');
 assert.equal(market.model(now,sample,cal,'timeout').status,'尚未確認');assert.equal(market.model(now,sample,null).status,'尚未確認');
});
test('holiday and preclose states never become negative',()=>{assert.equal(market.model(new Date('2026-10-11T15:00:00+08:00'),null,cal).status,'休市');assert.equal(market.model(new Date('2026-10-12T13:25:00+08:00'),sample,cal).status,'尚未確認');});
test('market DOM uses independent turnover labels without touching seven candidates',()=>{const d=doc();require('./docs/status.js').render(d,require('./docs/status.js').model(new Date('2026-10-08T18:00:00+08:00'),{calendar:JSON.parse(fs.readFileSync('state/calendars/2026.json')),data:JSON.parse(fs.readFileSync('state/candidates/2026-10-08.json'))}));market.render(d,market.model(now,sample,cal));assert.equal(d.querySelectorAll('.candidate-card').length,7);assert.equal(d.querySelector('#market-closing-state').textContent,'有');assert.match(d.querySelector('.market-closing').textContent,/上市普通股/);});
