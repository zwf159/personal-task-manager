'use strict';
Workspace.register('bundles','项目模板','把整组任务、清单、标签和项目内依赖保存为可重用计划。',async()=>{
  const panel=UI.panel('项目模板');panel.dialog.classList.add('bundles-panel');
  async function apply(bundle){
    const view=UI.panel('从模板创建项目');const request_id=crypto.randomUUID();
    view.body.append(element('p','bundle-warning',`将创建 ${bundle.recipe.tasks.length} 个待开始任务。不会复制工时、日志和跨项目依赖。截止日期按模板保存时的偏移量计算。`));
    view.body.append(UI.form([{name:'name',label:'新项目名称',maxLength:60},{name:'start_day',label:'计划基准日期',type:'date',value:localDate()}],async d=>{const result=await api(`/api/project-bundles/${bundle.id}/apply`,'POST',{...d,request_id});await Workspace.changed();view.dialog.close();await load();toast(`已创建项目 #${result.project_id}`);},'创建完整项目'));
  }
  async function load(){
    const bundles=await api('/api/project-bundles');if(!panel.dialog.isConnected)return;panel.body.replaceChildren();
    const projectOptions=state.projects.map(p=>[p.id,p.name]);
    if(projectOptions.length)panel.body.append(UI.form([{name:'project_id',label:'源项目',options:projectOptions},{name:'name',label:'模板名称',maxLength:100}],async d=>{await api('/api/project-bundles','POST',{...d,project_id:Number(d.project_id)});await load();},'保存项目模板'));
    else panel.body.append(element('p','workspace-empty','先创建包含任务的项目，再保存为模板。'));
    for(const bundle of bundles){const card=element('article','extension-card bundle-card');card.append(element('h3','',bundle.name),element('p','',`${bundle.recipe.tasks.length} 个任务 · 跳过 ${bundle.recipe.external_dependencies_omitted} 条跨项目依赖`));
      for(const task of bundle.recipe.tasks.slice(0,8))UI.line(card,`${task.title} · 清单 ${task.checklist.length} 项`);
      card.append(UI.button('应用项目模板',()=>apply(bundle)));panel.body.append(card);}
  }await load();
});
