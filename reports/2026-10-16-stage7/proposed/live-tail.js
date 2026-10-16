(function(root){
 'use strict';
 const columns=['closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct'];
 const escaped=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=v=>v==null||!Number.isFinite(Number(v))?'待確認':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
 const clock=v=>v?new Date(v).toLocaleTimeString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}):'未取得';
 function verified(row,body,liveReleased=false){return liveReleased===true&&body.mode==='LIVE'&&row.validated===true&&row.verification_status==='VERIFIED'&&
  row.independent_evidence?.validated===true&&row.independent_evidence?.source_contract_live_released===true&&
  ['pre_actual_trade_before_1325','pre_last_trade_independently_proven','close_independent_finality','tail_threshold','required_volume_evidence'].every(k=>row.checks?.[k]===true);}
 function order(rows,key,direction){return rows.slice().sort((a,b)=>{
  const x=a[key]==null?null:Number(a[key]),y=b[key]==null?null:Number(b[key]);
  const valid=n=>n!=null&&Number.isFinite(n);if(!valid(x))return valid(y)?1:a.code.localeCompare(b.code);if(!valid(y))return -1;
  return (direction==='asc'?x-y:y-x)||a.code.localeCompare(b.code);
 });}
 function create(doc,initial,configuration={}){
  // Private bootstrap configuration; never read a release flag from API data.
  const liveReleased=configuration.liveReleased===true;
  let body=initial,key=null,direction='desc',lastReadVersion=Number(initial.version)||0,reading=false;const reads=[];
  function render(next){if(next)body=next;
   const rows=key?order(body.rows,key,direction):body.rows;const set=(id,v)=>doc.getElementById(id).textContent=v;
   const status=r=>verified(r,body,liveReleased)?'正式驗證':r.verification_status==='RESEARCH_ONLY'&&r.validated!==true?'研究候選':'資料不足';
   const statuses=rows.map(status);
   set('stage3-mode',body.provenance?.kind==='SAME_DAY_SAVED_CAPTURE_ANALYSIS'?'今日已保存資料驗收｜非逐批即時串流':body.mode==='SYNTHETIC'?'合成測試｜不是真實行情':body.mode==='OFFLINE_REPLAY'?'歷史證據重播｜非當時發布':'隔離即時試驗');
   set('stage3-date',body.trade_date);set('stage3-verified',statuses.filter(s=>s==='正式驗證').length);
   set('stage3-research',statuses.filter(s=>s==='研究候選').length);set('stage3-unknown',statuses.filter(s=>s==='資料不足').length);
   const summary=doc.getElementById('stage5-summary');if(summary)summary.textContent=`初篩候選共 ${rows.length} 檔：研究 ${statuses.filter(s=>s==='研究候選').length} 檔、UNKNOWN ${statuses.filter(s=>s==='資料不足').length} 檔、完整驗證 ${statuses.filter(s=>s==='正式驗證').length} 檔。`;
   set('stage3-screening',`${number(body.screening_calculable_count)}／${number(body.universe_count)}；${number(body.screening_unresolved_count)} 檔無法完整初篩，可能漏選`);
   set('stage3-write',clock(body.public_written_at));set('stage3-generated',clock(body.generated_at));
   set('stage3-audit',(body.final_audit?.scheduled_times||['14:50','15:20','17:50']).join('／')+' 最終官方稽核');
   set('stage3-empty',rows.length?'':'等待候選證據；尚無可顯示的股票。');
   const evidence=r=>r.simulation_passed?'合成證據測試通過，不能當作正式訊號':r.independent_evidence?.reasons?.some(x=>x.includes('CONFLICT'))?'獨立來源與 MIS 矛盾':'獨立證明尚未完成';
   const times=r=>`行情取得 ${clock(r.close_received_at)} · 獨立證據 ${clock(r.source_acquired_at)} · 更新 ${clock(r.updated_at)}`;
   doc.getElementById('stage3-rows').innerHTML=rows.map(r=>`<tr><td><strong>${escaped(r.code)} ${escaped(r.name)}</strong><small>${escaped(times(r))}</small></td><td>${escaped(number(r.P_before))}<small>尚待獨立確認</small></td><td>${escaped(number(r.P_close))}<small>尚待最終確認</small></td><td>${escaped(number(r.tail_return_pct))}%</td>${columns.map(k=>`<td>${escaped(number(r[k]))}</td>`).join('')}<td><strong>${status(r)}</strong><small>${escaped(evidence(r))}</small></td></tr>`).join('');
   doc.getElementById('stage3-cards').innerHTML=rows.map(r=>`<article class="candidate-card"><div class="card-heading"><h3>${escaped(r.code)} ${escaped(r.name)}</h3><strong class="tail">${escaped(number(r.tail_return_pct))}%</strong></div><p class="stage3-status">${status(r)}</p><div class="card-metrics"><div class="metric"><span>13:25 前價（待驗證）</span><strong>${escaped(number(r.P_before))}</strong></div><div class="metric"><span>收盤價（待驗證）</span><strong>${escaped(number(r.P_close))}</strong></div>${columns.map((k,i)=>`<div class="metric"><span>${['最後一盤量','全日盤中量','收盤量占比'][i]}</span><strong>${escaped(number(r[k]))}${i===2?'%':' 張'}</strong></div>`).join('')}</div><div class="stage3-evidence">${escaped(evidence(r))}<br>${escaped(times(r))}</div></article>`).join('');
   for(const button of doc.querySelectorAll('[data-stage3-sort]')){const active=button.dataset.stage3Sort===key;button.querySelector('.sort-arrow').textContent=active?(direction==='desc'?'↓':'↑'):'⇅';button.parentElement.setAttribute('aria-sort',active?(direction==='desc'?'descending':'ascending'):'none');}
   set('stage3-direction',direction==='desc'?'由大到小 ↓':'由小到大 ↑');
  }
  for(const button of doc.querySelectorAll('[data-stage3-sort]'))button.addEventListener('click',()=>{const next=button.dataset.stage3Sort;direction=key===next&&direction==='desc'?'asc':'desc';key=next;render();});
  doc.getElementById('stage3-sort').addEventListener('change',e=>{key=e.target.value||null;direction='desc';render();});
  doc.getElementById('stage3-direction').addEventListener('click',()=>{direction=direction==='desc'?'asc':'desc';render();});
  async function poll(endpoint){
   if(reading)return;reading=true;
   try{
   const url=new URL(endpoint,root.location?.href||'http://localhost');
   if(url.protocol!=='https:'&&!['127.0.0.1','localhost'].includes(url.hostname))throw Error('UNSAFE_ENDPOINT');
   const requestedAt=new Date().toISOString();
   try{const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(8000),headers:{Accept:url.hostname==='api.github.com'?'application/vnd.github.raw+json':'application/json'}});if(!response.ok)throw Error('HTTP_'+response.status);
    const next=await response.json();if(next.trade_date!==body.trade_date||next.version<=Math.max(lastReadVersion,Number(body.version)||0))return;
    if(next.schema_version!=='STAGE3_SELECTION_V1'||!Number.isSafeInteger(next.version)||!Array.isArray(next.rows))throw Error('INVALID_SCHEMA');
    lastReadVersion=next.version;const observedAt=new Date().toISOString();
    reads.push({version:next.version,sha256:next.sha256,public_written_at:next.public_written_at,browser_requested_at:requestedAt,browser_observed_at:observedAt});
    doc.getElementById('stage3-read').textContent=clock(observedAt);doc.getElementById('stage3-network').textContent='隔離端點已讀取；版本 '+next.version;
    render(next);
   }catch{doc.getElementById('stage3-network').textContent='資料讀取失敗，等待重試；保留上一版並顯示原更新時間。';}
   }finally{reading=false;}
  }
  render();return {render,poll,reads,getState:()=>({body,key,direction,rows:key?order(body.rows,key,direction):body.rows})};
 }
 const api={create,verified,order};if(typeof module!=='undefined')module.exports=api;else root.Stage3View=api;
})(typeof window==='undefined'?globalThis:window);

(function(root){
 'use strict';
 const BASE='https://tw-tail-stage4-20261015-test.gxaawill2.workers.dev';
 const today=now=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
 function check(body,date,now,liveReleased=false){
  if(body?.schema_version!=='STAGE3_SELECTION_V1'||body.trade_date!==date||body.mode!=='LIVE'||body.is_synthetic!==false||body.public_data_policy!=='MIS_DERIVED_RESEARCH_NO_FUGLE_RAW'||!Number.isSafeInteger(body.version)||body.version<1||!Array.isArray(body.rows)||body.rows.length>200)throw Error('INVALID_CURRENT_DAY_LIVE_RESULT');
  if(!Number.isFinite(Date.parse(body.generated_at))||Date.parse(body.generated_at)>now.getTime()+1000||today(new Date(body.generated_at))!==date)throw Error('INVALID_RESULT_TIME');
  const values=['universe_count','screening_calculable_count','screening_unresolved_count','research_count','unknown_candidate_count','verified_count'].map(k=>body[k]);
  if(values.some(x=>!Number.isSafeInteger(x)||x<0)||values[0]<=0||values[0]!==values[1]+values[2]||values[3]+values[4]+values[5]!==body.rows.length)throw Error('INVALID_COUNTS');
  const seen=new Set();let research=0,unknown=0,verified=0;
  for(const r of body.rows){
   const id=r.ex+':'+r.code;
   if(!['tse','otc'].includes(r.ex)||!/^\d{4}$/.test(r.code)||seen.has(id))throw Error('INVALID_SECURITY');seen.add(id);
   if(r.verification_status==='RESEARCH_ONLY'&&r.validated!==true)research++;
   else if(r.verification_status==='UNKNOWN'&&r.validated!==true)unknown++;
   else if(r.verification_status==='VERIFIED'&&root.Stage3View.verified(r,body,liveReleased))verified++;
   else throw Error('UNRELEASED_OR_INVALID_VERIFIED');
  }
  if(research!==body.research_count||unknown!==body.unknown_candidate_count||verified!==body.verified_count)throw Error('INVALID_STATUS_COUNTS');
  return body;
 }
 function setup(doc,configuration){
  const panel=doc.getElementById('stage7-live');
  if(!configuration?.enabled)return null;
  if(configuration.api_base!==BASE||typeof configuration.live_released!=='boolean')throw Error('EXACT_REVIEWED_API_REQUIRED');
  panel.hidden=false;panel.innerHTML=`<h2>即時選股與獨立驗證</h2><p id="stage3-mode"></p><p id="stage5-summary">正在等待當日證據；尚未取得結果。</p><p>交易日 <strong id="stage3-date"></strong></p><div class="stage3-counts"><div>研究候選<strong id="stage3-research">—</strong></div><div>正式驗證<strong id="stage3-verified">—</strong></div><div>UNKNOWN<strong id="stage3-unknown">—</strong></div></div><p>初篩涵蓋：<span id="stage3-screening">未取得</span></p><p>計算：<span id="stage3-generated">未取得</span> · 寫入：<span id="stage3-write">未取得</span> · 本瀏覽器：<span id="stage3-read">未取得</span></p><p id="stage3-network" role="status">等待當日結果</p><p id="stage3-audit"></p><div class="stage3-controls"><label for="stage3-sort">即時結果排序</label><select id="stage3-sort"><option value="">原始順序</option><option value="closing_auction_volume">最後一盤量</option><option value="intraday_total_volume">全日盤中量</option><option value="closing_volume_ratio_pct">收盤量占比</option></select><button id="stage3-direction">由大到小 ↓</button></div><p id="stage3-empty"></p><div class="desktop-wrap"><table><thead><tr><th>股票</th><th>13:25前價</th><th>收盤價</th><th>尾盤漲跌</th><th>最後一盤量</th><th>全日盤中量</th><th>收盤量占比</th><th>驗證狀態</th></tr></thead><tbody id="stage3-rows"></tbody></table></div><div id="stage3-cards"></div><p class="event-note">原有研究名單與盤後核對保留在下方；研究或 UNKNOWN 不代表完整驗證。資料更新中斷時保留原時間。</p>`;
  let controller=null,date=null,lastVersion=0;
  return {apply(body,now=new Date()){
   const current=today(now);check(body,current,now,configuration.live_released);
   if(date===current&&body.version<=lastVersion)return false;
   if(date!==current){controller=null;lastVersion=0;date=current;}
   if(!controller)controller=root.Stage3View.create(doc,body,{liveReleased:configuration.live_released});else controller.render(body);
   lastVersion=body.version;
   doc.getElementById('stage3-read').textContent=now.toLocaleTimeString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});
   doc.getElementById('stage3-network').textContent='當日即時資料；版本 '+body.version;
   return true;
  },clearDay(now){if(date&&date!==today(now)){panel.hidden=true;controller=null;date=null;lastVersion=0;}},fail(){doc.getElementById('stage3-network').textContent='尚未取得當日結果／更新失敗；不以昨日資料代替，也不代表沒有候選。';}};
 }
 const api={check,setup,today};if(typeof module!=='undefined'){module.exports={...module.exports,...api};return;}
 async function start(){
  const configURL=new URL('live-tail-config.json',root.location.href),read=async url=>{const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error('READ_FAILED');return r.json();};
  let config;try{config=await read(configURL);}catch{return;}
  const controller=setup(document,config);if(!controller)return;
  async function refresh(){const now=new Date();controller.clearDay(now);
   try{const data=await read(BASE+'/data?date='+today(now));if(today(new Date())===today(now)){document.getElementById('stage7-live').hidden=false;controller.apply(data,new Date());}}catch{controller.fail();}
   setTimeout(refresh,5000);
  }
  refresh();
 }
 start();
})(typeof window==='undefined'?globalThis:window);
