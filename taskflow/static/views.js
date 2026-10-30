'use strict';
$('#tools').append(UI.button('常用筛选', openSavedViews));

async function openSavedViews() {
  const panel = UI.panel('常用筛选');
  const filters = currentFilters();
  async function load() {
    const views = await api('/api/views');
    if (!panel.dialog.isConnected) return;
    panel.body.replaceChildren(element('p', '', '把当前的项目、搜索词、状态、优先级和排序保存下来，下次一键使用。'));
    const current = UI.section(panel.body, '保存当前筛选');
    const descriptions = [state.project ? state.projects.find(p => p.id === state.project)?.name : '所有项目',
      filters.q ? `搜索：${filters.q}` : '不限关键词', filters.status ? labels[filters.status] : '全部状态',
      filters.priority ? `${labels[filters.priority]}优先级` : '全部优先级'];
    current.append(element('p', '', descriptions.join(' · ')));
    current.append(UI.form([{name: 'name', label: '筛选名称', maxLength: 60}], async data => {
      await api('/api/views', 'POST', {...data, filters}); await load(); toast('常用筛选已保存');
    }, '保存筛选'));
    const list = UI.section(panel.body, '已保存');
    if (!views.length) list.append(element('p', '', '还没有常用筛选。'));
    for (const view of views) UI.line(list, view.name, [UI.button('应用', () => {
      state.project = view.filters.project_id ? Number(view.filters.project_id) : null;
      state.view = view.filters.view || 'all';
      $('#search').value = view.filters.q || '';
      $('#status').value = view.filters.status || '';
      $('#priority').value = view.filters.priority || '';
      $('#sort').value = view.filters.sort || 'due';
      panel.dialog.close(); reload();
    }), UI.button('移除', () => UI.confirm('移除筛选', '只删除保存的筛选条件，不修改任务。', async () => {await api(`/api/views/${view.id}`, 'DELETE'); await load();}))]);
  }
  await load();
}
