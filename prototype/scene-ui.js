if(D.insights){
  const A=D.insights, rowMap=new Map(D.records.map(r=>[r.row,r]));
  const names={rental:'租赁',loan:'借款及还款往来',credit:'信用履约',recycling:'回收及二手平台'};
  const state={days:'all',platform:'',start:D.meta.start,end:D.meta.end,channels:{},pages:{},sort:'count'};
  const within=(r)=>r.time.slice(0,10)>=state.start&&r.time.slice(0,10)<=state.end&&(!state.platform||(r.platform||'微信')===state.platform);
  const totals=rows=>({count:rows.length,income:rows.filter(r=>r.direction==='收入').reduce((n,r)=>n+r.cents,0),expense:rows.filter(r=>r.direction==='支出').reduce((n,r)=>n+r.cents,0),neutral:rows.filter(r=>r.direction==='中性交易').reduce((n,r)=>n+r.cents,0)});
  const amountCards=(t,last)=>`<div class="scene-kpis"><div><small>记录数</small><strong>${num(t.count)} 笔</strong></div><div><small>收入（元）</small><strong class="income">${money(t.income)}</strong></div><div><small>支出（元）</small><strong class="expense">${money(t.expense)}</strong></div><div><small>${last||'不计收支（元）'}</small><strong>${money(t.neutral)}</strong></div></div>`;
  const caption=()=>`${state.start} 至 ${state.end} · ${state.platform||'全部平台'}`;
  const inspect=(ids,label)=>{reset();const set=new Set(ids);special={label,test:r=>set.has(r.row)};go()};
  const periodStart=(days,end)=>{const d=new Date(end+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-days+1);return d.toISOString().slice(0,10)};
  const tbody=(hits)=>hits.map(m=>{const r=rowMap.get(m.row);return `<tr><td class="nowrap">${r.time.slice(0,10)}<br><small>${r.time.slice(11)}</small></td><td class="break">${esc(r.merchant||'未标注')}<br><small>${esc(r.item)}</small></td><td>${esc(r.raw_direction||r.direction)}</td><td class="num">${money(r.cents)}</td><td class="evidence"><span class="evidence-tag ${m.inferred?'amber':''}">${esc(m.event)}</span><br>${esc(m.basis)}</td><td class="source">${esc(r.platform||'微信')}<br><small>${r.source_page?'第 '+r.source_page+' 页 / '+r.source_table_row+' 行':'原表第 '+r.row+' 行'}</small></td><td><button class="linkbtn" data-evidence-row="${r.row}">定位原流水</button></td></tr>`}).join('');
  document.querySelector('.filters').insertAdjacentHTML('beforeend','<label>识别场景<select id="bill-scene"><option value="">全部场景</option><option value="rental">租赁</option><option value="loan">借款及还款往来</option><option value="credit">信用履约</option><option value="recycling">回收及二手平台</option></select></label>');
  $('bill-scene').addEventListener('input',filter);
  const previousPairs=[$('pairsnote'),$('pairfilter')];
  document.querySelector('#scenarios').remove();
  const blocks=`<section class="section" id="scenarios"><div class="section-title"><h2>场景识别</h2><span class="tag">场景时间轴</span></div><p class="scope-caption">选择时间与平台，查看整体交易、薪资线索、借还款、信用履约、回收及资金流向。近 N 天截至账单截止日 ${A.anchor}。</p><div class="period-tabs" aria-label="场景时间周期">${[['all','全部'],[7,'7天'],[15,'15天'],[30,'30天'],[90,'90天'],[180,'180天']].map(([v,n])=>`<button data-period="${v}" aria-pressed="${v==='all'}">${n}</button>`).join('')}</div><div class="scene-controls"><label>交易平台<select id="scene-platform"><option value="">全部平台</option>${[...new Set(D.records.map(r=>r.platform||'微信'))].map(p=>`<option>${esc(p)}</option>`).join('')}</select></label><label>开始日期<input type="date" id="scene-start" value="${D.meta.start}"></label><label>结束日期<input type="date" id="scene-end" value="${D.meta.end}"></label><button class="button" id="scene-reset">重置筛选</button></div><p class="scope-caption" id="scene-scope" aria-live="polite"></p><div class="scenario-grid" id="scene-overview"></div><div class="tablewrap" id="scene-timeline"></div><p class="note">点击月度笔数查看对应流水。每笔交易归入一个主要场景；识别结果供核查交易用途。</p></section>
  <section class="section" id="overall"><div class="section-title"><h2>整体交易</h2><button class="linkbtn" id="overall-details">查看范围内全部流水</button></div><p class="scope-caption scope-value"></p><div id="overall-kpis"></div><div class="legend overall-legend"><span><i class="dot" style="background:#168375"></i>收入（柱）</span><span><i class="dot" style="background:#3979e4"></i>支出（柱）</span><span><i class="line-key"></i>笔数（线）</span></div><div class="chartwrap" id="overall-chart"></div><p class="note">左轴：金额（元）；右轴：交易笔数。笔数包含不计收支记录，收入包含退款。点击月份查看对应流水。</p><details><summary>查看月度金额明细</summary><div class="tablewrap" id="overall-monthly"></div></details></section>
  ${Object.entries(names).map(([key,name])=>`<section class="section" id="${key}"><div class="section-title"><h2>${name}</h2><span class="tag" id="${key}-count"></span></div><p class="scope-caption scope-value"></p><div id="${key}-kpis"></div>${['loan','credit'].includes(key)?'<h3>各周期交易汇总</h3><div class="tablewrap" id="'+key+'-periods"></div><p class="note">各周期存在重叠，金额不可相加。还款相关支出按账单说明识别，营销收入单列。</p>':''}<div class="channel-tabs" id="${key}-channels" role="tablist" aria-label="${name}渠道"></div><div id="${key}-panel"></div><p class="note">${key==='rental'?'按交易商户查看渠道流水，授权、取消、退款与支出分别标注。在租情况和应还金额需结合租赁合同核实。':key==='loan'?'本栏包括金融机构往来及借还款相关交易，机构红包单列为营销收入。具体借款及还款情况请结合合同核实。':key==='credit'?'本栏按花呗、白条、月付、分付及信用卡还款文字识别。还款、退款和其他产品往来分别标注；付款方式中的信用卡或花呗不作为还款依据。':'平台收入、支出及退款分别展示；二手平台购物与回收变现请结合明细区分。'}</p></section>`).join('')}
  <section class="section" id="portrait"><div class="section-title"><h2>交易画像分析</h2><label>画像排序 <select id="profile-sort"><option value="count">频次</option><option value="expense">支出金额</option><option value="income">收入金额</option></select></label></div><p class="scope-caption scope-value"></p><h3>交易对方标签</h3><div class="keyword-cloud" id="counterparty-tags"></div><h3>画像标签</h3><div class="profile-grid" id="profile-tags"></div><p class="note">标签反映账单中的交易特征，点击可查看相关流水。同一笔交易可能涉及多个标签，标签金额不可相加。</p></section>`;
  document.querySelector('#trends').insertAdjacentHTML('beforebegin',blocks);
  const pairsDetails=document.createElement('details');pairsDetails.innerHTML='<summary>同日同金额交易（全部账单）</summary>';previousPairs.forEach(e=>pairsDetails.append(e));$('overall').append(pairsDetails);
  const oldNav=document.querySelector('aside a[href="#scenarios"]');
  oldNav.outerHTML='<a href="#scenarios">场景识别</a><a href="#overall">整体交易</a><a href="#rental">租赁渠道</a><a href="#loan">借还款往来</a><a href="#credit">信用履约</a><a href="#recycling">回收交易</a><a href="#portrait">画像标签</a>';
  document.querySelector('aside a[href="#portrait"]').after(document.querySelector('aside a[href="#trends"]'));
  document.querySelector('aside small').innerHTML=(isCombined?'微信 + 支付宝':'微信账单')+'<br>审核参考';
  const reviewUI=createReviewUI({D,A,$,esc,money,num,inspect});
  const baseShowDetail=showDetail;
  showDetail=function(row){baseShowDetail(row);const m=A.matches.find(h=>h.row===row);const dt=[...$('detailfields').querySelectorAll('dt')].find(e=>e.textContent==='场景关键词');if(dt){dt.textContent='场景识别依据';dt.nextElementSibling.textContent=m?m.evidence.join('、'):'未识别到相关场景'}if(m)$('detailfields').insertAdjacentHTML('beforeend',`<dt>识别场景</dt><dd>${esc(names[m.scene])} / ${esc(m.channel)}</dd><dt>事件线索</dt><dd>${esc(m.event)}</dd><dt>场景依据</dt><dd>${esc(m.basis)}</dd>`);$('detailfields').insertAdjacentHTML('beforeend',`<dt>交易画像标签</dt><dd>${esc(A.profiles.filter(p=>p.rows.includes(row)).map(p=>p.name).join('、')||'未命中')}</dd>`)};
  const mtable=(rows)=>{const months=[...new Set(rows.map(r=>r.time.slice(0,7)))].sort().reverse();return `<table><thead><tr><th>月份</th><th class="num">笔数</th><th class="num">收入（元）</th><th class="num">支出（元）</th><th class="num">不计收支（元）</th><th>明细</th></tr></thead><tbody>${months.map(m=>{const t=totals(rows.filter(r=>r.time.startsWith(m)));return `<tr><td>${m}</td><td class="num">${t.count}</td><td class="num">${money(t.income)}</td><td class="num">${money(t.expense)}</td><td class="num">${money(t.neutral)}</td><td><button class="linkbtn" data-overall-month="${m}">查看</button></td></tr>`}).join('')}</tbody></table>`};
  function overallChart(rows){
    if(!rows.length)return '<p class="scene-empty">当前范围无交易记录。</p>';
    const months=D.monthly.map(m=>m.month).filter(m=>m>=state.start.slice(0,7)&&m<=state.end.slice(0,7));
    const series=months.map(month=>({month,...totals(rows.filter(r=>r.time.startsWith(month)))}));
    const axisMax=(max,integer=false)=>{const raw=Math.max(max,1)/4,power=10**Math.floor(Math.log10(raw)),step=Math.ceil(raw/power)*power;return (integer?Math.max(1,Math.ceil(step)):step)*4};
    const amountMax=axisMax(Math.max(...series.map(m=>Math.max(m.income,m.expense)))/100),countMax=axisMax(Math.max(...series.map(m=>m.count)),true);
    const W=960,H=330,left=80,right=62,top=35,bottom=50,cw=W-left-right,ch=H-top-bottom,step=cw/series.length,bw=Math.min(23,step*.24);
    const x=i=>left+step*(i+.5),moneyY=c=>top+ch-ch*(c/100)/amountMax,countY=n=>top+ch-ch*n/countMax;
    let svg=`<svg class="chart overall-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="月度整体交易组合图：收入和支出柱状图，交易笔数折线图"><text x="${left}" y="17">金额（元）</text><text x="${W-right}" y="17" text-anchor="end">笔数（笔）</text>`;
    for(let i=0;i<=4;i++){const y=top+ch*i/4;svg+=`<line x1="${left}" y1="${y}" x2="${W-right}" y2="${y}" stroke="#e4eaf2"/><text x="${left-12}" y="${y+4}" text-anchor="end">${(amountMax*(4-i)/4).toLocaleString('zh-CN',{maximumFractionDigits:2})}</text><text x="${W-right+12}" y="${y+4}">${num(countMax*(4-i)/4)}</text>`}
    series.forEach((m,i)=>{svg+=`<rect data-series="income" x="${x(i)-bw-2}" y="${moneyY(m.income)}" width="${bw}" height="${top+ch-moneyY(m.income)}" fill="#168375" rx="2"/><rect data-series="expense" x="${x(i)+2}" y="${moneyY(m.expense)}" width="${bw}" height="${top+ch-moneyY(m.expense)}" fill="#3979e4" rx="2"/><text x="${x(i)}" y="${H-20}" text-anchor="middle">${m.month}</text>`});
    svg+=`<path data-series="count" d="${series.map((m,i)=>(i?'L':'M')+x(i)+','+countY(m.count)).join(' ')}" fill="none" stroke="#b87513" stroke-width="2.5" stroke-linejoin="round"/>`;
    series.forEach((m,i)=>{const label=`${m.month}：${m.count} 笔，收入 ${money(m.income)} 元，支出 ${money(m.expense)} 元`;svg+=`<g data-overall-month="${m.month}" tabindex="0" role="button" aria-label="${label}，查看流水"><title>${label}</title><circle cx="${x(i)}" cy="${countY(m.count)}" r="4" fill="#fff" stroke="#b87513" stroke-width="2.5"/><rect class="month-hit" x="${left+step*i}" y="${top}" width="${step}" height="${ch+34}" fill="transparent"/></g>`});
    return svg+'</svg>';
  }
  function renderChannel(key,hits){
    const channels=[...new Set(hits.map(m=>m.channel))].sort((a,b)=>{const last=c=>hits.filter(m=>m.channel===c).map(m=>rowMap.get(m.row).time).sort().pop();return last(b).localeCompare(last(a))||a.localeCompare(b)});
    if(!channels.includes(state.channels[key]))state.channels[key]=channels[0];
    const selected=state.channels[key];
    $(key+'-channels').innerHTML=channels.map((c,i)=>`<button role="tab" aria-selected="${c===selected}" data-channel-scene="${key}" data-channel-name="${esc(c)}">${esc(c)} <small>(${hits.filter(m=>m.channel===c).length})</small></button>`).join('');
    if(!selected){$(key+'-panel').innerHTML='<div class="scene-empty">当前范围未识别到相关交易，可调整时间范围或查看全部流水。</div>';return}
    const chosen=hits.filter(m=>m.channel===selected).sort((a,b)=>rowMap.get(b.row).time.localeCompare(rowMap.get(a.row).time)||a.row-b.row);
    const pages=Math.max(1,Math.ceil(chosen.length/8));state.pages[key]=Math.min(state.pages[key]||1,pages);
    const page=state.pages[key],t=totals(chosen.map(m=>rowMap.get(m.row)));
    $(key+'-panel').innerHTML=`<div class="channel-panel" role="tabpanel"><h3>${esc(selected)}</h3><p class="muted">${num(chosen.length)} 笔 · 首次 ${rowMap.get(chosen[chosen.length-1].row).time.slice(0,10)} · 最近 ${rowMap.get(chosen[0].row).time.slice(0,10)}</p><p>支出 ${money(t.expense)} 元 · 收入 ${money(t.income)} 元 · 不计收支 ${money(t.neutral)} 元</p><div class="tablewrap"><table class="scene-results"><thead><tr><th>交易时间</th><th>交易对方 / 商品原文</th><th>原始收支</th><th class="num">金额（元）</th><th>识别依据</th><th>来源</th><th>操作</th></tr></thead><tbody>${tbody(chosen.slice((page-1)*8,page*8))}</tbody></table></div><div class="pager"><span class="muted">第 ${page} / ${pages} 页，每页 8 笔</span><div class="toolbar"><button class="button" data-channel-page="${key}" data-step="-1" ${page===1?'disabled':''}>上一页</button><button class="button" data-channel-page="${key}" data-step="1" ${page===pages?'disabled':''}>下一页</button><button class="linkbtn" data-channel-all="${key}">查看该渠道全部流水</button></div></div></div>`;
  }
  function periodHits(key,days){
    const start=days==='all'?D.meta.start:periodStart(Number(days),A.anchor);
    return A.matches.filter(m=>m.scene===key&&rowMap.get(m.row).time.slice(0,10)>=start&&rowMap.get(m.row).time.slice(0,10)<=A.anchor&&(!state.platform||(rowMap.get(m.row).platform||'微信')===state.platform));
  }
  function renderPeriods(key){
    $(key+'-periods').innerHTML='<table><thead><tr><th>周期</th><th class="num">渠道数</th><th class="num">笔数</th><th class="num">支出（元）</th><th class="num">其中还款相关支出</th><th class="num">收入（元）</th><th class="num">其中营销收入</th><th class="num">不计收支（元）</th><th>流水</th></tr></thead><tbody>'+['all',7,15,30,90,180].map(days=>{
      const h=periodHits(key,days),t=totals(h.map(m=>rowMap.get(m.row)));
      return `<tr><td>${days==='all'?'全部':'近'+days+'天'}</td><td class="num">${new Set(h.map(m=>m.channel)).size}</td><td class="num">${h.length}</td><td class="num">${money(t.expense)}</td><td class="num">${money(h.filter(m=>m.event==='还款文字线索').reduce((v,m)=>v+rowMap.get(m.row).cents,0))}</td><td class="num">${money(t.income)}</td><td class="num">${money(h.filter(m=>m.event==='营销收入').reduce((v,m)=>v+rowMap.get(m.row).cents,0))}</td><td class="num">${money(t.neutral)}</td><td><button class="linkbtn" data-finance-scene="${key}" data-finance-period="${days}" ${h.length?'':'disabled'}>查看</button></td></tr>`;
    }).join('')+'</tbody></table><p class="note">周期统计截至 '+A.anchor+'，按所选平台展示；自定义日期仅用于渠道明细。</p>';
  }
  function renderScenes(){
    const invalid=state.start>state.end;
    $('scene-scope').textContent=invalid?'开始日期晚于结束日期，请调整日期。':caption();
    document.querySelectorAll('.scope-value').forEach(e=>e.textContent=caption());
    const rows=D.records.filter(within),ids=new Set(rows.map(r=>r.row)),hits=A.matches.filter(m=>ids.has(m.row));
    document.querySelectorAll('[data-period]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.period===state.days));
    $('scene-overview').innerHTML=Object.entries(names).map(([k,n])=>{const h=hits.filter(m=>m.scene===k),t=totals(h.map(m=>rowMap.get(m.row)));return `<button class="scenario-card" data-scene-jump="${k}">${n}<strong>${h.length} 笔</strong><small>${new Set(h.map(m=>m.channel)).size} 个渠道（含待核实） · 支出 ${money(t.expense)} 元</small></button>`}).join('');
    const months=[...new Set(rows.map(r=>r.time.slice(0,7)))].sort();
    $('scene-timeline').innerHTML=`<table class="timeline-table"><thead><tr><th>场景 / 月份</th>${months.map(m=>`<th>${m}</th>`).join('')}</tr></thead><tbody>${Object.entries(names).map(([key,name])=>`<tr><td>${name}</td>${months.map(m=>{const count=hits.filter(h=>h.scene===key&&rowMap.get(h.row).time.startsWith(m)).length;return `<td><button class="timeline-dot" data-type="${key}" data-scene-month="${m}" ${count?'':'disabled'}>${count||'—'}</button></td>`}).join('')}</tr>`).join('')}</tbody></table>`;
    $('overall-kpis').innerHTML=amountCards(totals(rows));$('overall-chart').innerHTML=overallChart(rows);$('overall-monthly').innerHTML=rows.length?mtable(rows):'<p class="scene-empty">当前范围无交易记录。</p>';
    Object.keys(names).forEach(key=>{const h=hits.filter(m=>m.scene===key);$(key+'-count').textContent=new Set(h.map(m=>m.channel)).size+' 个渠道（含待核实）';$(key+'-kpis').innerHTML=amountCards(totals(h.map(m=>rowMap.get(m.row))));renderChannel(key,h);const events=[...new Set(h.map(m=>m.event))];$(key+'-kpis').insertAdjacentHTML('beforeend','<div class="period-tabs" aria-label="事件类型">'+events.map(event=>`<button data-event-scene="${key}" data-event-name="${esc(event)}">${esc(event)} ${h.filter(m=>m.event===event).length} 笔</button>`).join('')+'</div>')});
    for(const key of ['loan','credit'])renderPeriods(key);
    reviewUI.render(state);
    $('counterparty-tags').innerHTML=A.keywords.map((p,i)=>{const r=p.rows.filter(id=>ids.has(id));return r.length?`<button data-keyword="${i}">${esc(p.name)} <small>${r.length} 笔</small></button>`:''}).join('')||'<p class="muted">当前范围暂无交易对方标签。</p>';
    const profiles=A.profiles.map((p,i)=>({...p,index:i,...totals(p.rows.filter(id=>ids.has(id)).map(id=>rowMap.get(id)))})).sort((a,b)=>b[state.sort]-a[state.sort]);const max=Math.max(1,...profiles.map(p=>p[state.sort]));
    $('profile-tags').innerHTML=profiles.map(p=>`<div class="profile-card"><button class="linkbtn" data-profile="${p.index}" ${p.count?'':'disabled'}>${esc(p.name)}</button><p>${p.count} 笔 · 支出 ${money(p.expense)} 元<br>收入 ${money(p.income)} 元 · 其他 ${money(p.neutral)} 元</p><div class="track"><div class="fill" style="width:${p[state.sort]/max*100}%"></div></div><p>${esc(p.basis)}</p></div>`).join('');
  }
  $('scene-platform').addEventListener('change',()=>{state.platform=$('scene-platform').value;state.pages={};renderScenes()});
  ['start','end'].forEach(k=>$('scene-'+k).addEventListener('change',()=>{state[k]=$('scene-'+k).value||D.meta[k];state.days='custom';state.pages={};renderScenes()}));
  $('scene-reset').addEventListener('click',()=>{state.start=D.meta.start;state.end=D.meta.end;state.days='all';state.platform='';state.pages={};$('scene-start').value=state.start;$('scene-end').value=state.end;$('scene-platform').value='';renderScenes()});
  $('profile-sort').addEventListener('change',()=>{state.sort=$('profile-sort').value;renderScenes()});
  $('overall-details').addEventListener('click',()=>inspect(D.records.filter(within).map(r=>r.row),'整体交易 · '+caption()));
  document.addEventListener('click',e=>{const b=e.target.closest('button,[data-overall-month]');if(!b)return;
    if(b.dataset.period){state.days=b.dataset.period;state.end=A.anchor;state.start=state.days==='all'?D.meta.start:periodStart(Number(state.days),A.anchor);$('scene-start').value=state.start;$('scene-end').value=state.end;state.pages={};renderScenes()}
    else if(b.dataset.eventScene)inspect(A.matches.filter(m=>m.scene===b.dataset.eventScene&&m.event===b.dataset.eventName&&within(rowMap.get(m.row))).map(m=>m.row),names[b.dataset.eventScene]+' · '+b.dataset.eventName);
    else if(b.dataset.sceneJump)$(b.dataset.sceneJump).scrollIntoView({behavior:'instant'});
    else if(b.dataset.channelScene){state.channels[b.dataset.channelScene]=b.dataset.channelName;state.pages[b.dataset.channelScene]=1;renderScenes()}
    else if(b.dataset.channelPage){state.pages[b.dataset.channelPage]+=Number(b.dataset.step);renderScenes()}
    else if(b.dataset.evidenceRow){showDetail(Number(b.dataset.evidenceRow))}
    else if(b.dataset.channelAll){const key=b.dataset.channelAll;inspect(A.matches.filter(m=>m.scene===key&&m.channel===state.channels[key]&&within(rowMap.get(m.row))).map(m=>m.row),names[key]+' · '+state.channels[key])}
    else if(b.dataset.sceneMonth)inspect(A.matches.filter(m=>m.scene===b.dataset.type&&rowMap.get(m.row).time.startsWith(b.dataset.sceneMonth)&&within(rowMap.get(m.row))).map(m=>m.row),names[b.dataset.type]+' · '+b.dataset.sceneMonth);
    else if(b.dataset.overallMonth)inspect(D.records.filter(r=>within(r)&&r.time.startsWith(b.dataset.overallMonth)).map(r=>r.row),'整体交易 · '+b.dataset.overallMonth);
    else if(b.dataset.financeScene)inspect(periodHits(b.dataset.financeScene,b.dataset.financePeriod).map(m=>m.row),names[b.dataset.financeScene]+' · 截至 '+A.anchor+' / '+(b.dataset.financePeriod==='all'?'全部':'近'+b.dataset.financePeriod+'天'))
    else if(b.dataset.profile!==undefined){const p=A.profiles[Number(b.dataset.profile)];inspect(p.rows.filter(id=>within(rowMap.get(id))),'画像：'+p.name+'；'+p.basis)}
    else if(b.dataset.keyword!==undefined){const p=A.keywords[Number(b.dataset.keyword)];inspect(p.rows.filter(id=>within(rowMap.get(id))),'交易对方含“'+p.name+'”')}
  });
  document.querySelectorAll('#scenarios,#overall,#review-highlights,#salary,#rental,#loan,#credit,#recycling,#fund-flow,#portrait').forEach(s=>observer.observe(s));
  document.addEventListener('keydown',e=>{const el=e.target.closest('g[data-overall-month]');if(el&&(e.key==='Enter'||e.key===' ')){e.preventDefault();el.dispatchEvent(new MouseEvent('click',{bubbles:true}))}});
  renderScenes();
}
