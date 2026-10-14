const {test}=require('node:test'),assert=require('node:assert/strict'),view=require('./fast_view.js');
test('missing values sort last in both directions',()=>{
 const rows=[{code:'1',intraday_total_volume:null},{code:'2',intraday_total_volume:'40'},{code:'3',intraday_total_volume:'3'}];
 assert.deepEqual(view.ordered(rows,'intraday_total_volume','desc').map(r=>r.code),['2','3','1']);
 assert.deepEqual(view.ordered(rows,'intraday_total_volume','asc').map(r=>r.code),['3','2','1']);
});
test('a supplied validated boolean cannot bypass missing checks',()=>{
 assert.equal(view.verified({validated:true,verification_status:'VERIFIED',checks:{tail_threshold:true}}),false);
});
test('saved rows remain research only',()=>{
 const payload=require('./reports/2026-10-14-fast/replay/fast-results.json');
 assert.equal(payload.rows.length,6);assert.equal(payload.rows.filter(view.verified).length,0);
 assert.equal(payload.metrics.first_public_observed_at,null);
});
