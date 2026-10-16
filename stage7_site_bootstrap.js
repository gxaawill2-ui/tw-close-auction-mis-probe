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
