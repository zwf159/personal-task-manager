'use strict';
Workspace.register('habits','习惯打卡','记录每天的实际完成量，查看连续达标天数。',async()=>{
  const panel=UI.panel('习惯打卡'); panel.dialog.classList.add('habits-panel');
  async function load(){
    const habits=await api('/api/habits'); if(!panel.dialog.isConnected)return;
    panel.body.replaceChildren();
    panel.body.append(UI.form([{name:'title',label:'习惯名称',maxLength:120},{name:'target',label:'每日目标',type:'number',min:1,value:1},{name:'unit',label:'单位',value:'次',maxLength:20}],async d=>{await api('/api/habits','POST',{...d,target:Number(d.target)});await load();},'创建习惯'));
    for(const habit of habits){
      const card=element('article','extension-card habit-card');
      card.append(element('h3','',habit.title+(habit.archived?'（归档）':'')),element('p','habit-streak',`连续达标 ${habit.streak} 天 · 累计 ${habit.completed_days} 天 · 每日 ${habit.target} ${habit.unit}`));
      if(!habit.archived)card.append(UI.form([{name:'day',label:'打卡日期',type:'date',value:localDate()},{name:'quantity',label:'完成数量',type:'number',min:1,value:habit.target},{name:'note',label:'说明',required:false,maxLength:1000}],async d=>{await api(`/api/habits/${habit.id}/logs`,'POST',{...d,quantity:Number(d.quantity)});await load();},'保存打卡'));
      for(const log of habit.logs.slice(0,7))UI.line(card,`${log.day} · ${log.quantity} ${habit.unit} · ${log.note}`,[UI.button('撤销打卡',()=>UI.confirm('撤销打卡','将清除此日期的完成记录。',async()=>{await api(`/api/habits/${habit.id}/logs/${log.day}`,'DELETE');await load();}))]);
      card.append(UI.button(habit.archived?'恢复习惯':'归档习惯',async()=>{await api(`/api/habits/${habit.id}`,'PATCH',{archived:!habit.archived});await load();}));panel.body.append(card);
    }
    if(!habits.length)panel.body.append(element('p','workspace-empty','创建一个习惯，从今天的真实行动开始。'));
  }await load();
});
