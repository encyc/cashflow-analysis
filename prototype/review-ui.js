/* Review panels use row IDs for every drill-down, never merchant guesses. */
function createReviewUI({D,A,$,esc,money,num,inspect}) {
  let groups=[];
  const drill=(rows,label,text='查看流水',className='linkbtn')=>{
    const index=groups.push({ids:rows.map(r=>r.row),label})-1;
    return `<button class="${className}" data-review-group="${index}" ${rows.length?'':'disabled'}>${text}</button>`;
  };
  const panels=`<section class="section" id="review-highlights"><div class="section-title"><h2>重点交易摘要</h2><span class="tag">可回查流水</span></div><p class="scope-caption scope-value"></p><div id="review-highlights-body" class="review-summary-grid"></div><p class="note">大额按单笔 ≥ 10,000 元，夜间按北京时间 22:00–次日 05:59。只统计收入与支出，收入含退款；两组可能重叠。</p></section>
  <section class="section" id="salary"><div class="section-title"><h2>薪资收入线索</h2><span class="tag">收入文字识别</span></div><p class="scope-caption scope-value"></p><div id="salary-kpis"></div><div class="tablewrap" id="salary-months"></div><details><summary>查看收入来源</summary><div class="tablewrap" id="salary-sources"></div></details><p class="note">仅汇总收入中明确包含工资、薪资、薪酬的文字，排除退款、失败、工资卡充值及借贷文字。不据此确认任职单位、发薪日或稳定工资；未识别不代表没有工资收入。</p></section>`;
  $('overall').insertAdjacentHTML('afterend',panels);
  $('portrait').insertAdjacentHTML('beforebegin',`<section class="section" id="fund-flow"><div class="section-title"><h2>主要资金流向</h2><span class="tag">收入来源 / 支出去向</span></div><p class="scope-caption scope-value"></p><div class="chartwrap" id="fund-flow-chart"></div><p class="note">两侧分别展示金额前 5 个交易对方，其余合并为“其他交易对方”，点击节点查看流水。同名对方按平台区分，收入包含退款，不含不计收支；两侧不表示同一笔资金的前后流转。</p></section>`);
  document.querySelector('aside a[href="#overall"]').insertAdjacentHTML('afterend','<a href="#review-highlights">重点交易</a><a href="#salary">薪资线索</a>');
  document.querySelector('aside a[href="#portrait"]').insertAdjacentHTML('beforebegin','<a href="#fund-flow">资金流向</a>');
  document.addEventListener('click',e=>{const target=e.target.closest('[data-review-group]');if(!target)return;
    const group=groups[Number(target.dataset.reviewGroup)];if(group&&group.ids.length)inspect(group.ids,group.label)});
  document.addEventListener('keydown',e=>{const target=e.target.closest('g[data-review-group]');
    if(target&&(e.key==='Enter'||e.key===' ')){e.preventDefault();target.dispatchEvent(new MouseEvent('click',{bubbles:true}))}});

  function flowChart(view) {
    const sides=[view.incoming,view.outgoing],count=Math.max(...sides.map(s=>s.nodes.length),1),height=70+count*72,mid=height/2;
    if(!sides.some(s=>s.total))return '<p class="scene-empty">当前范围没有非零收入或支出记录。</p>';
    let paths='',nodes='';
    sides.forEach((side,index)=>{
      const x=index?615:0,color=index?'#3979e4':'#168375';
      side.nodes.forEach((node,i)=>{
        const y=50+i*72,centerY=y+27,w=Math.max(1,18*node.cents/Math.max(...sides.map(s=>s.total),1));
        paths+=`<path d="${index?`M540 ${mid} C580 ${mid},575 ${centerY},615 ${centerY}`:`M285 ${centerY} C325 ${centerY},320 ${mid},360 ${mid}`}" fill="none" stroke="${color}" stroke-width="${w}" opacity=".3"/>`;
        const name=node.merchant||'未标注交易对方',label=(index?'支出去向':'收入来源')+' · '+node.platform+' · '+name;
        const group=groups.push({ids:node.rows.map(r=>r.row),label})-1;
        nodes+=`<g data-review-group="${group}" tabindex="0" role="button" aria-label="${esc(label)}，${money(node.cents)} 元，查看 ${node.rows.length} 笔流水"><title>${esc(label)}：${money(node.cents)} 元</title><rect class="flow-node" x="${x}" y="${y}" width="285" height="54" rx="5" fill="white" stroke="#d5dfed"/><text x="${x+12}" y="${y+21}">${esc(name.length>17?name.slice(0,17)+'…':name)}</text><text x="${x+12}" y="${y+41}" class="flow-secondary">${esc(node.platform)}</text><text x="${x+272}" y="${y+41}" text-anchor="end" fill="${color}">${money(node.cents)} 元</text></g>`;
      });
    });
    return `<svg class="chart flow-chart" viewBox="0 0 900 ${height}" role="group" aria-label="当前范围主要资金流向，可点击交易对方查看明细"><text x="0" y="25">收入来源</text><text x="615" y="25">支出去向</text>${paths}<rect x="360" y="${mid-64}" width="180" height="128" rx="6" fill="#edf3ff"/><text x="450" y="${mid-36}" text-anchor="middle">所选范围账单</text><text x="450" y="${mid-10}" text-anchor="middle" fill="#168375">收入 ${money(view.incoming.total)}</text><text x="450" y="${mid+16}" text-anchor="middle" fill="#3979e4">支出 ${money(view.outgoing.total)}</text><text x="450" y="${mid+43}" text-anchor="middle" class="flow-secondary">单位：元</text>${nodes}</svg>`;
  }

  return {render(state){
    groups=[];
    const view=buildReviewView(D.records,A.review,D.monthly,state),salary=view.salary;
    $('review-highlights-body').innerHTML=[['large','大额收支','单笔 ≥ 10,000 元'],['night','夜间收支','22:00–次日 05:59']].map(([key,name,note])=>{
      const s=view[key];return `<article class="review-summary"><h3>${name}</h3><small>${note}</small><strong>${num(s.count)} <span>笔</span></strong><p>收入 <b class="income">${money(s.income)}</b> 元<br>支出 <b class="expense">${money(s.expense)}</b> 元</p>${drill(s.rows,name+' · '+state.start+' 至 '+state.end)}</article>`}).join('');
    const last=salary.rows.map(r=>r.time).sort().pop(),hitMonths=salary.monthly.filter(m=>m.count).length;
    $('salary-kpis').innerHTML=`<div class="scene-kpis"><div><small>识别收入（元）</small><strong>${money(salary.income)}</strong></div><div><small>命中记录</small><strong>${num(salary.count)} 笔</strong></div><div><small>命中月份 / 所选区间月份</small><strong>${hitMonths} / ${salary.monthly.length}</strong></div><div><small>最近一笔线索</small><strong class="review-date">${last?last.slice(0,10):'未识别'}</strong></div></div>`;
    const max=Math.max(1,...salary.monthly.map(m=>m.income));
    $('salary-months').innerHTML=salary.count?`<table><thead><tr><th>月份</th><th>识别收入分布</th><th class="num">金额（元）</th><th class="num">笔数</th><th>明细</th></tr></thead><tbody>${salary.monthly.map(m=>`<tr><td>${m.month}</td><td class="salary-bar-cell"><div class="track"><div class="fill" style="width:${100*m.income/max}%"></div></div></td><td class="num">${m.count?money(m.income):'未识别'}</td><td class="num">${m.count}</td><td>${drill(m.rows,'薪资线索 · '+m.month)}</td></tr>`).join('')}</tbody></table>`:'<p class="scene-empty">当前范围未识别到明确薪资收入文字。可在账单明细中核查收入来源。</p>';
    $('salary-sources').innerHTML=salary.sources.length?`<table><thead><tr><th>平台</th><th>交易对方原文</th><th class="num">金额（元）</th><th class="num">笔数</th><th>明细</th></tr></thead><tbody>${salary.sources.map(s=>`<tr><td>${esc(s.platform)}</td><td>${esc(s.merchant||'未标注')}</td><td class="num">${money(s.income)}</td><td class="num">${s.count}</td><td>${drill(s.rows,'薪资线索 · '+s.platform+' · '+(s.merchant||'未标注'))}</td></tr>`).join('')}</tbody></table>`:'<p class="muted">暂无命中来源。</p>';
    $('fund-flow-chart').innerHTML=flowChart(view);
  }};
}
