'use strict';
Workspace.register('planner','每日计划','按时间段安排任务，检查时段重叠与每日容量。',async()=>{
  const panel=UI.panel('每日计划');panel.dialog.classList.add('planner-panel');let day=localDate();
  const time=m=>`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
  async function load(){
    const plan=await api(`/api/planner?day=${day}`);if(!panel.dialog.isConnected)return;
    panel.body.replaceChildren();
    panel.body.append(UI.form([{name:'day',label:'计划日期',type:'date',value:day}],async d=>{day=d.day;await load();},'切换日期'));
    panel.body.append(element('p','planner-capacity',`已安排 ${plan.scheduled} 分钟 / 可用 ${plan.capacity} 分钟 · 剩余 ${plan.remaining} 分钟`));
    panel.body.append(UI.form([{name:'minutes',label:'当天可用分钟',type:'number',min:0,max:1440,value:plan.capacity}],async d=>{await api('/api/planner/capacity','POST',{day,minutes:Number(d.minutes)});await load();},'保存容量'));
    for(const item of plan.slots){const card=element('article','extension-card plan-slot');card.append(element('strong','plan-time',`${time(item.start_minute)}–${time(item.end_minute)}`),element('h3','',item.title),element('p','workspace-body',item.note));
      if(item.task_id)card.append(element('p','',`任务 #${item.task_id} · ${labels[item.task_status]||'已移除'}${item.task_deleted?'（回收站）':''}`));
      card.append(UI.button('移除时段',()=>UI.confirm('移除计划时段','只删除此安排，关联任务会保留。',async()=>{await api(`/api/planner/${item.id}`,'DELETE');await load();})));panel.body.append(card);}
    panel.body.append(UI.form([{name:'title',label:'计划名称',maxLength:200},{name:'start_time',label:'开始时间',type:'time',value:'09:00'},{name:'end_time',label:'结束时间',type:'time',value:'10:00'},{name:'task_id',label:'关联任务编号（可选）',type:'number',min:1,required:false},{name:'note',label:'计划说明',required:false,maxLength:2000}],async d=>{await api('/api/planner','POST',{...d,day,task_id:d.task_id?Number(d.task_id):null});await load();},'添加时段'));
  }await load();
});
