'use strict';
async function openDetails(id) {
  const panel = UI.panel('任务详情');
  const base = `/api/tasks/${id}`;
  async function load() {
    const [task, checklist, comments, labels, assigned, links, activity] = await Promise.all(
      [base, `${base}/checklist`, `${base}/comments`, '/api/labels', `${base}/labels`, `${base}/links`, `${base}/activity`].map(path => api(path)));
    if (!panel.dialog.isConnected) return;
    panel.body.replaceChildren(element('h2', '', `#${task.id} · ${task.title}`), element('p', 'detail-notes', task.notes));
    const actions = element('div', 'action-strip');
    actions.append(UI.button('编辑基本信息', () => {panel.dialog.close(); openTask(task);}),
      UI.button('复制任务', async () => {await api(`${base}/duplicate`, 'POST', {}); await refresh(); toast('已复制任务');}));
    panel.body.append(actions);
    const check = UI.section(panel.body, `子任务清单 · ${checklist.filter(i => i.done).length}/${checklist.length}`);
    for (const item of checklist) {
      UI.line(check, `${item.done ? '✓' : '○'} ${item.title}`, [
        UI.button(item.done ? '取消完成' : '完成', async () => {await api(`${base}/checklist/${item.id}`, 'PATCH', {done: !item.done}); await load();}),
        UI.button('移除', async () => {await api(`${base}/checklist/${item.id}`, 'DELETE'); await load();})]);
    }
    check.append(UI.form([{name: 'title', label: '清单内容', maxLength: 200}], async data => {await api(`${base}/checklist`, 'POST', data); await load();}));
    const tags = UI.section(panel.body, '标签');
    const selected = new Set(assigned.map(l => l.id));
    const choices = element('div', 'tag-choices');
    for (const label of labels) {
      const choice = element('label', 'checkbox-label');
      const input = element('input');
      input.type = 'checkbox'; input.value = label.id; input.checked = selected.has(label.id);
      choice.append(input, document.createTextNode(label.name)); choices.append(choice);
    }
    tags.append(choices, UI.button('保存标签选择', async () => {
      const label_ids = [...choices.querySelectorAll('input:checked')].map(i => Number(i.value));
      await api(`${base}/labels`, 'POST', {label_ids}); toast('标签已保存');
    }));
    tags.append(UI.form([{name: 'name', label: '新标签', maxLength: 40}], async data => {await api('/api/labels', 'POST', data); await load();}, '创建标签'));
    const notes = UI.section(panel.body, '任务记录');
    for (const note of comments) {
      UI.line(notes, `${new Date(note.created_at).toLocaleString()}\n${note.body}`, [UI.button('移除', async () => {await api(`${base}/comments/${note.id}`, 'DELETE'); await load();})]);
    }
    notes.append(UI.form([{name: 'body', label: '补充进展', type: 'textarea', maxLength: 5000}], async data => {await api(`${base}/comments`, 'POST', data); await load();}, '记录进展'));
    const refs = UI.section(panel.body, '参考资料');
    for (const link of links) {
      const line = UI.line(refs, '', [UI.button('移除', async () => {await api(`${base}/links/${link.id}`, 'DELETE'); await load();})]);
      const anchor = element('a', '', link.title); anchor.href = link.url; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
      line.firstChild.append(anchor);
    }
    refs.append(UI.form([{name: 'title', label: '标题', maxLength: 120}, {name: 'url', label: '网址', type: 'url', maxLength: 2048}], async data => {await api(`${base}/links`, 'POST', data); await load();}));
    const history = UI.section(panel.body, '最近操作');
    const actionLabels = {created: '创建', updated: '更新', deleted: '移入回收站', restored: '恢复', duplicated: '复制', estimate: '调整预估', bulk_status: '批量改状态', bulk_project: '批量移动', bulk_delete: '批量删除', imported: '导入', from_template: '从模板创建'};
    for (const event of activity.slice(0, 15)) UI.line(history, `${new Date(event.created_at).toLocaleString()} · ${actionLabels[event.action] || event.action}`);
    document.dispatchEvent(new CustomEvent('taskflow:detail', {detail: {id, task, root: panel.body, reload: load}}));
  }
  try {await load();} catch (error) {panel.body.textContent = error.message;}
}
