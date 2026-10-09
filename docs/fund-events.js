(async function(){
 'use strict';
 const esc=x=>String(x??'未確認').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const levels={HIGH:'高',MEDIUM:'中',LOW:'低',DATA_INSUFFICIENT:'資料不足'};
 const dates={CONFIRMED_CLOSE_IMPLEMENTATION:'指數官方确认收盤實施；基金委託時間未確認',EXPECTED_CLOSE_WATCH_DATE:'預估收盤觀察日',EXPECTED_MULTIDAY_TRANSITION:'預估多日過渡期間',DATE_UNVERIFIED:'收盤實施日未確認'};
 async function refresh(){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
 try{const response=await fetch('https://raw.githubusercontent.com/gxaawill2-ui/tw-close-auction-mis-probe/main/state/events/fund-events.json?v='+Math.floor(Date.now()/300000),{signal:controller.signal,cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);
  const data=await response.json();if(data.schema_version!==1||!Array.isArray(data.fund_events))throw Error('資料格式未確認');
  const now=Date.now();const rows=data.fund_events.filter(r=>Date.parse(r.information_available_as_of)<=now);
  document.getElementById('funds').innerHTML=rows.map(r=>'<article><h2>'+esc(r.closing_impact_date||r.implementation_window?.start||r.effective_date)+' · '+esc(r.fund_code+' '+r.fund_name)+'</h2><strong>'+esc(r.event_name)+'</strong><p class="tags">重要程度：'+esc(levels[r.importance_level])+(r.importance_confidence==='PROVISIONAL'?'（暫定）':'')+' · 日期證據：'+esc(dates[r.close_date_status])+'</p><p>生效：'+esc(r.effective_date)+'；過渡：'+esc((r.implementation_window?.dates||[]).join('、')||null)+'</p><ul>'+r.importance_reason.map(reason=>'<li>'+esc(reason)+'</li>').join('')+'</ul><p>基金淨資產：'+(r.fund_aum?esc(new Intl.NumberFormat('zh-TW').format(r.fund_aum))+' 元；資料日 '+esc(r.aum_as_of):'未取得／已過期')+'。評級截至 '+esc(r.information_available_as_of)+'；方法 '+esc(r.importance_method_version)+'</p><p>'+r.source_urls.filter(url=>/^https:\/\//.test(url)).map(url=>'<a href="'+esc(url)+'" rel="noopener noreferrer" target="_blank">官方來源</a>').join(' · ')+'</p></article>').join('');
  document.getElementById('error').textContent='共 '+rows.length+' 筆基金 × 事件紀錄；受限來源仍為 PARTIAL。';
 }catch(error){document.getElementById('error').textContent='重要程度資料尚未確認；請保留舊資料並稍後查看。';}finally{clearTimeout(timeout);setTimeout(refresh,300000);}}
 refresh();
})();
