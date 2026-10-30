'use strict';
Workspace.register('inbox','灵感收集箱','先记录想法，再选择项目转为任务，重复转换不会生成重复任务。',async()=>{
  const panel=UI.panel('灵感收集箱');panel.dialog.classList.add('inbox-panel');let filter='open';
  async function load(){
    const items=await api(`/api/inbox?state=${filter}`);if(!panel.dialog.isConnected)return;
    panel.body.replaceChildren();
    const tabs=element('div','action-strip');for(const [value,title] of [['open','待整理'],['converted','已转任务'],['archived','已归档']])tabs.append(UI.button(title,async()=>{filter=value;await load();}));panel.body.append(tabs);
    panel.body.append(UI.form([{name:'title',label:'想法标题',maxLength:200},{name:'body',label:'详细内容',type:'textarea',required:false,maxLength:5000},{name:'source',label:'来源',required:false,maxLength:120}],async d=>{await api('/api/inbox','POST',d);filter='open';await load();},'收集想法'));
    for(const item of items){
      const card=element('article','extension-card capture-card');card.append(element('h3','',item.title),element('p','workspace-body',item.body),element('small','capture-source',`${item.source} · ${new Date(item.created_at).toLocaleString()}`));
      if(item.state==='open'){
        card.append(UI.form([{name:'project_id',label:'转入项目',required:false,options:[['','未分组'],...state.projects.map(p=>[p.id,p.name])]},{name:'due_date',label:'截止日期',type:'date',required:false}],async d=>{const result=await api(`/api/inbox/${item.id}/convert`,'POST',{...d,project_id:d.project_id?Number(d.project_id):null});await Workspace.changed();await load();toast(`已创建任务 #${result.task_id}`);},'转为任务'));
      }
      if(item.state==='converted')card.append(UI.button(`查看任务 #${item.task_id}`,()=>{panel.dialog.close();return openDetails(item.task_id);}));
      else card.append(UI.button(item.state==='archived'?'恢复收集项':'归档',async()=>{await api(`/api/inbox/${item.id}`,'PATCH',{state:item.state==='archived'?'open':'archived'});await load();}));panel.body.append(card);
    }
    if(!items.length)panel.body.append(element('p','workspace-empty','此分类没有收集项。每次显示最近 200 条。'));
  }await load();
});
