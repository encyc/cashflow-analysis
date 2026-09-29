// Shared report augmentation for a verified multi-platform identity.
if(isCombined){
  document.title=D.meta.nickname+' · 个人流水分析报告';
  document.querySelector('h1').textContent='个人流水分析报告';
  document.querySelector('.header-note').textContent='个人流水 · 审核参考';
  document.querySelector('aside small').innerHTML='微信 + 支付宝';
  document.querySelector('nav[aria-label="报告切换"]').innerHTML='<a class="button" href="combined.html">报告目录</a><a class="button" href="person-1-combined.html">合并报告 1</a><a class="button" href="person-2-combined.html">合并报告 2</a>';
  $('owner').textContent='审核对象：'+D.meta.nickname;
  $('meta').innerHTML=`<span>账单期间 ${D.meta.start} 至 ${D.meta.end}</span><span>${num(S.count)} 笔交易</span><span>交易平台：微信、支付宝</span>`;
  document.querySelector('.hero .tag').textContent='审核参考';
  document.querySelector('.hero .note').textContent='收入包含账单列为收入的退款；不计收支中的退款单列。退款与原支出未相互抵扣，收支差额不等同于净现金流或账户余额。';
  $('kpis').insertAdjacentHTML('afterend',`<div class="scope"><b>不计收支 / 其他：${num(S.neutral_count)} 笔，${money(S.neutral)} 元</b><br>其中退款 ${S.neutral_refund_count} 笔，${money(S.neutral_refund)} 元。不计收支记录单独统计，不计入收入与支出。<br><button class="linkbtn" id="neutralfilter">查看全部不计收支</button>　<button class="linkbtn" id="neutralrefundfilter">查看不计收支中的退款</button></div>`);
  $('averages').insertAdjacentHTML('afterend',`<p class="note">月均按两个平台均完整覆盖的 ${S.complete_months} 个自然月计算。</p>`);
  $('pairsnote').textContent=`发现 ${D.pairs.length} 对同日同金额收支，可查看明细核实交易关系。未抵扣相关金额，不能仅据此认定本人账户互转。`;
  document.querySelector('#activity .note').textContent='活跃日按存在收入或支出记录的自然日计算；分母为导出区间的全部自然日。日内分布图展示全部记录，包含退款及不计收支。';
  const cardLabels=[...new Set(D.payments.flatMap(p=>p.name.match(/[^&]*?(?:储蓄卡|信用卡)[（(]\d+[）)]/g)||[]))];
  $('bankcount').textContent=`出现 ${cardLabels.filter(n=>n.includes('储蓄卡')).length} 个储蓄卡标识、${cardLabels.filter(n=>n.includes('信用卡')).length} 个信用卡标识`;
  $('creditnote').textContent+=' 同一卡片搭配不同优惠券时按一个银行卡标识统计。';
  document.querySelector('#trends .bars + .note').textContent='分类供核查交易用途，点击类别可查看明细；用途不明确的交易列为“未分类”或“待核实”。';
  document.querySelector('#bills thead th').textContent='平台 / 页 / 行';
  $('direction').insertAdjacentHTML('beforeend','<option value="中性交易">不计收支 / 其他</option>');
  document.querySelector('.filters').insertAdjacentHTML('afterbegin','<label>来源平台<select id="platform"><option value="">微信 + 支付宝</option><option>微信</option><option>支付宝</option></select></label>');
  $('platform').addEventListener('input',filter);
  const originalRenderRows=renderRows;
  renderRows=function(){originalRenderRows();const neutral=filtered.filter(r=>r.direction==='中性交易');$('filtertotal').insertAdjacentHTML('beforeend',`<span>不计收支 ${num(neutral.length)} 笔 / ${money(neutral.reduce((a,r)=>a+r.cents,0))} 元</span>`)};
  $('neutralfilter').addEventListener('click',()=>{reset();$('direction').value='中性交易';go()});
  $('neutralrefundfilter').addEventListener('click',()=>{reset();special={label:'不计收支中的退款',test:r=>r.direction==='中性交易'&&r.refund_indicator};go()});
  const methods=[
    ['统计范围','汇总审核对象所提供的微信与支付宝账单。月均仅统计两个平台均完整覆盖的自然月；未提供的账户交易不在本报告范围内。'],
    ['收支与退款','按账单标注统计收入、支出和不计收支。收入包含列为收入的退款；不计收支中的退款单列，未抵扣原支出。收支差额不等同于净现金流或账户余额。'],
    ['场景与标签','根据交易对方、商品说明及交易时间识别，供核查交易用途；可在明细中查看依据。未识别到相关交易不代表不存在。'],
    ['支付方式与交易对方','按账单标注展示；同名交易对方或相同银行卡尾号不一定属于同一主体或账户。信用卡支付金额不代表欠款余额或授信额度。'],
    ['审核参考','借款、租赁及还款情况需结合合同、还款计划等材料核实。账单未提供的信息以“未提供”展示。']
  ];
  document.querySelector('#method ul').innerHTML=methods.map(([k,v])=>`<li><b>${k}：</b>${v}</li>`).join('');
  document.querySelector('.foot').textContent='流水分析报告 · 供审核参考';
}
