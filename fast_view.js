(function(root){
  'use strict';
  const labels={pre_actual_trade_before_1325:'13:25 前實際成交',pre_durably_saved_before_1325:'13:25 前保存',pre_last_trade_independently_proven:'最後成交獨立證明',close_research_converged:'收盤研究收斂',close_independent_finality:'收盤獨立確認',tail_threshold:'達到 ±3%',required_volume_evidence:'必要成交量證據'};
  const keys=['closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct'];
  const sourceLabels={NOT_CHECKED:'尚未即時查核',OBSERVATION_ONLY:'已取得參考資料，尚未驗證',OBSERVATION_MATCH_UNPROVEN:'價格與時間一致，證明仍不足',NO_USABLE_OBSERVATION:'尚無可用資料',NOT_CONFIGURED:'尚未接通來源',SOURCE_ERROR:'來源暫時失敗'};
  const format=(v)=>v==null?'待確認':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
  const clock=(v)=>v?new Date(v).toLocaleTimeString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}):'未取得';
  const esc=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const verified=(r)=>r.validated===true&&r.verification_status==='VERIFIED'&&Object.keys(labels).every(k=>r.checks?.[k]===true);
  function ordered(rows,key,direction){
    return rows.slice().sort((a,b)=>{
      const av=a[key]==null?null:Number(a[key]),bv=b[key]==null?null:Number(b[key]);
      const valid=v=>v!=null&&Number.isFinite(v);
      if(!valid(av))return valid(bv)?1:a.code.localeCompare(b.code);
      if(!valid(bv))return -1;
      return (direction==='asc'?av-bv:bv-av)||a.code.localeCompare(b.code);
    });
  }
  function create(doc,payload){
    let data=payload,key=null,direction='desc';
    function render(next){
      if(next)data=next;
      const rows=key?ordered(data.rows,key,direction):data.rows;
      const confirmed=rows.filter(verified).length;
      const set=(id,value)=>{doc.getElementById(id).textContent=value;};
      set('trade-date',data.trade_date);set('fast-count',rows.length);set('fast-verified',confirmed);
      set('fast-universe',format(data.universe_count));set('fast-observed',format(data.observed_symbols));
      set('fast-pending',format(data.universe_count-confirmed));
      set('fast-first',clock(data.metrics.first_candidate_evidence_available_at));
      set('fast-complete',clock(data.metrics.first_complete_research_evidence_at));
      set('fast-last',clock(data.metrics.last_evidence_update_at));
      set('fast-audit',(data.final_audit.scheduled_times||[]).join('／')+' 預定；與即時結果分開');
      set('fast-empty',rows.length?'':'目前沒有證據足夠的研究候選。');
      set('fast-note',confirmed?'部分股票通過驗證；全市場仍未完成。':'正式驗證 0 檔。研究名單尚缺獨立證據，不能當作正式交易訊號。');
      const missing=r=>Object.entries(labels).filter(([k])=>r.checks?.[k]!==true).map(([,name])=>name).join('、');
      const evidence=r=>`初次出現 ${clock(r.first_seen_at)} · 收盤取得 ${clock(r.close_received_at)} · 更新 ${clock(r.updated_at)} · 13:25 前保存 ${clock(r.pre_saved_at)}`;
      const status=r=>verified(r)?'完整驗證':'研究／待確認';
      const sourceStatus=r=>sourceLabels[r.crosscheck_status]||'待確認';
      doc.getElementById('fast-rows').innerHTML=rows.map(r=>`<tr><td><strong>${esc(r.code)} ${esc(r.name)}</strong><small>${esc(evidence(r))}</small></td><td>${esc(format(r.tail_return_pct))}%</td><td>${esc(format(r.P_before))}<small>成交 ${esc(r.P_before_trade_time)}</small></td><td>${esc(format(r.P_close))}<small>成交 ${esc(r.P_close_trade_time)}</small></td>${keys.map(k=>`<td>${esc(format(r[k]))}</td>`).join('')}<td>${status(r)}<small>尚缺：${esc(missing(r)||'無')}</small><small>交叉查核：${esc(sourceStatus(r))}</small></td></tr>`).join('');
      doc.getElementById('fast-cards').innerHTML=rows.map(r=>`<article class="candidate-card"><div class="card-heading"><h3>${esc(r.code)} ${esc(r.name)}</h3><strong class="tail">${esc(format(r.tail_return_pct))}%</strong></div><p class="fast-badge">${status(r)}</p><div class="card-metrics"><div class="metric"><span>13:25 前價</span><strong>${esc(format(r.P_before))}</strong></div><div class="metric"><span>收盤價</span><strong>${esc(format(r.P_close))}</strong></div>${keys.map((k,i)=>`<div class="metric"><span>${['最後一盤量','全日盤中量','收盤量占比'][i]}</span><strong>${esc(format(r[k]))}${i===2?'%':' 張'}</strong></div>`).join('')}</div><div class="fast-evidence">${esc(evidence(r))}</div><p class="fast-missing">尚缺：${esc(missing(r)||'無')}<br>交叉查核：${esc(sourceStatus(r))}</p></article>`).join('');
      for(const button of doc.querySelectorAll('[data-fast-sort]')){
        const active=button.dataset.fastSort===key;button.querySelector('.sort-arrow').textContent=active?(direction==='desc'?'↓':'↑'):'⇅';
        button.parentElement.setAttribute('aria-sort',active?(direction==='desc'?'descending':'ascending'):'none');
      }
      doc.getElementById('fast-direction').textContent=direction==='desc'?'由大到小 ↓':'由小到大 ↑';
    }
    for(const button of doc.querySelectorAll('[data-fast-sort]'))button.addEventListener('click',()=>{
      const next=button.dataset.fastSort;direction=key===next&&direction==='desc'?'asc':'desc';key=next;render();
    });
    doc.getElementById('fast-sort').addEventListener('change',event=>{key=event.target.value||null;direction='desc';render();});
    doc.getElementById('fast-direction').addEventListener('click',()=>{direction=direction==='desc'?'asc':'desc';render();});
    render();return {render,getState:()=>({key,direction,rows:key?ordered(data.rows,key,direction):data.rows})};
  }
  const api={create,ordered,verified};
  if(typeof module!=='undefined')module.exports=api;else root.FastView=api;
})(typeof window==='undefined'?globalThis:window);
