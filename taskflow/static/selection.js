'use strict';
const selectedTasks = new Set();
const selectionSummary = element('span', 'selection-summary');
const selectionActions = element('div', 'action-strip selection-actions');
selectionActions.append(UI.button('选择本页', () => {
  if (selectedTasks.size + state.tasks.filter(t => !selectedTasks.has(t.id)).length > 100) throw new Error('最多选择 100 项');
  state.tasks.forEach(t => selectedTasks.add(t.id)); drawSelection();
}), UI.button('清空选择', () => {selectedTasks.clear(); drawSelection();}), UI.button('批量操作', openBulk), selectionSummary);
$('.workspace').insertBefore(selectionActions, $('.list-heading'));

function drawSelection() {
  selectionSummary.textContent = `已选 ${selectedTasks.size} 项（跨页保留）`;
  for (const row of document.querySelectorAll('.task-row')) {
    const id = Number(row.dataset.taskId);
    let checkbox = row.querySelector('.task-select');
    if (!checkbox) {
      checkbox = element('input', 'task-select'); checkbox.type = 'checkbox';
      checkbox.setAttribute('aria-label', `选择任务 #${id}`);
      checkbox.onchange = () => {
        if (checkbox.checked && selectedTasks.size >= 100) {checkbox.checked = false; toast('最多选择 100 项'); return;}
        checkbox.checked ? selectedTasks.add(id) : selectedTasks.delete(id);
        selectionSummary.textContent = `已选 ${selectedTasks.size} 项（跨页保留）`;
      };
      row.prepend(checkbox);
    }
    checkbox.checked = selectedTasks.has(id);
  }
}

async function openBulk() {
  if (!selectedTasks.size) throw new Error('请先选择任务');
  const panel = UI.panel(`批量操作 · ${selectedTasks.size} 项`);
  const ids = [...selectedTasks];
  panel.body.append(element('p', '', `任务编号：${ids.join('、')}。所有任务将一起修改；任一任务无效时全部取消。`));
  async function apply(action, value) {
    await api('/api/tasks/bulk', 'POST', {ids, action, value});
    selectedTasks.clear(); panel.dialog.close(); await refresh(); toast('批量操作已完成');
  }
  panel.body.append(UI.form([{name: 'status', label: '改为状态', options: ['todo', 'doing', 'done'].map(v => [v, labels[v]])}], data => apply('status', data.status), '更新状态'));
  panel.body.append(UI.form([{name: 'project', label: '移动到项目', required: false, options: [['', '未分组'], ...state.projects.map(p => [p.id, p.name])]}], data => apply('project', data.project ? Number(data.project) : null), '移动任务'));
  panel.body.append(UI.button('移入回收站', () => UI.confirm('批量移入回收站', `将 ${ids.length} 项任务移入回收站，之后可以恢复。`, () => apply('delete'))));
}
document.addEventListener('taskflow:refresh', drawSelection);
drawSelection();
