/* Pure view calculations, shared by the standalone report and Node checks. */
function buildReviewView(records, analysis, months, filter) {
  const rows = records.filter(r => r.time.slice(0,10) >= filter.start && r.time.slice(0,10) <= filter.end &&
    (!filter.platform || (r.platform || '微信') === filter.platform));
  const summarize = items => ({rows:items,count:items.length,
    income:items.filter(r=>r.direction==='收入').reduce((s,r)=>s+r.cents,0),
    expense:items.filter(r=>r.direction==='支出').reduce((s,r)=>s+r.cents,0)});
  const select = group => {const ids=new Set(group.rows);return summarize(rows.filter(r=>ids.has(r.row)))};
  const grouped = items => {
    const groups=new Map();
    items.forEach(r=>{const platform=r.platform||'微信',merchant=r.merchant||'',key=JSON.stringify([platform,merchant]);
      if(!groups.has(key))groups.set(key,{platform,merchant,rows:[]});groups.get(key).rows.push(r)});
    return [...groups.values()].map(g=>({...g,...summarize(g.rows)}));
  };
  const salary=select(analysis.salary);
  salary.sources=grouped(salary.rows).sort((a,b)=>b.income-a.income||a.merchant.localeCompare(b.merchant));
  salary.monthly=months.filter(m=>filter.start<=filter.end&&m.month>=filter.start.slice(0,7)&&m.month<=filter.end.slice(0,7))
    .map(m=>({month:m.month,...summarize(salary.rows.filter(r=>r.time.startsWith(m.month)))}));
  const flow = direction => {
    const field=direction==='收入'?'income':'expense';
    const groups=grouped(rows.filter(r=>r.direction===direction&&r.cents>0))
      .map(g=>({...g,cents:g[field]})).sort((a,b)=>b.cents-a.cents||a.platform.localeCompare(b.platform)||a.merchant.localeCompare(b.merchant));
    const nodes=groups.slice(0,5);
    if(groups.length>5){const rest=groups.slice(5);nodes.push({merchant:'其他交易对方',platform:'所选平台',
      cents:rest.reduce((s,g)=>s+g.cents,0),rows:rest.flatMap(g=>g.rows),residual:true})}
    return {total:groups.reduce((s,g)=>s+g.cents,0),nodes};
  };
  return {salary,large:select(analysis.large),night:select(analysis.night),incoming:flow('收入'),outgoing:flow('支出')};
}
if(typeof module!=='undefined'&&module.exports)module.exports=buildReviewView;
