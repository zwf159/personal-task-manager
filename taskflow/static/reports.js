'use strict';
$('#tools').append(UI.button('任务看板', openBoard), UI.button('进度统计', openReport));

async function openBoard() {
  const panel = UI.panel('任务看板');
  panel.dialog.classList.add('wide-panel');
  const pages = {todo: 0, doing: 0, done: 0};
  const filter = currentFilters();
  // Board columns replace the list's status filter, retaining search and project.
  delete filter.status;
  async function load() {
    const results = await Promise.all(['todo', 'doing', 'done'].map(status => api(`/api/search?${new URLSearchParams({...filter, status, limit: 10, offset: pages[status] * 10})}`)));
    if (!panel.dialog.isConnected) return;
    panel.body.replaceChildren(element('p', '', '保留当前搜索、项目与优先级条件。通过状态选择框移动任务，每列独立分页。'));
    const board = element('div', 'board');
    results.forEach((result, index) => {
      const status = ['todo', 'doing', 'done'][index];
      if (pages[status] && !result.items.length) {pages[status]--; return;}
      const column = element('section', `board-column ${status}`);
      column.append(element('h3', '', `${labels[status]} · ${result.total}`));
      for (const task of result.items) {
        const card = element('article', 'board-card');
        card.append(UI.button(task.title, () => {panel.dialog.close(); return openDetails(task.id);}, 'task-title'));
        card.append(element('p', '', task.due_date || '暂无截止日期'));
        const move = element('select'); move.setAttribute('aria-label', `移动任务 ${task.title} 的状态`);
        for (const value of ['todo', 'doing', 'done']) move.add(new Option(labels[value], value));
        move.value = status;
        move.onchange = async () => {
          move.disabled = true;
          try {await api(`/api/tasks/${task.id}`, 'PATCH', {status: move.value, expected_version: task.version}); await refresh(); await load();}
          catch (error) {move.value = status; toast(error.message);} finally {move.disabled = false;}
        };
        card.append(move); column.append(card);
      }
      const previous = UI.button('上一页', async () => {pages[status]--; await load();});
      const next = UI.button('下一页', async () => {pages[status]++; await load();});
      previous.disabled = pages[status] === 0;
      next.disabled = (pages[status] + 1) * 10 >= result.total;
      const pager = element('div', 'action-strip'); pager.append(previous, next); column.append(pager);
      board.append(column);
    });
    if (board.childElementCount !== 3) return load();
    panel.body.append(board);
  }
  await load();
}

async function openReport() {
  const panel = UI.panel('最近七天 · 进度统计');
  const stats = await api('/api/stats?days=7');
  if (!panel.dialog.isConnected) return;
  panel.body.append(element('p', '', `活跃任务 ${stats.total} 项 · 已完成 ${stats.done} 项 · 逾期 ${stats.overdue} 项`));
  panel.body.append(element('p', '', `预估总投入 ${stats.estimate_minutes} 分钟 · 累计实际投入 ${stats.logged_minutes} 分钟`));
  const trends = UI.section(panel.body, '每日完成与投入');
  trends.append(element('p', '', '同一任务在同一天多次完成只计一次；已删除任务不计入。'));
  const table = element('table', 'report-table');
  const header = element('tr');
  for (const label of ['日期', '完成任务', '投入分钟']) header.append(element('th', '', label));
  table.append(header);
  for (const day of stats.trend) {
    const row = element('tr');
    for (const value of [day.day, day.completed, day.minutes]) row.append(element('td', '', value));
    table.append(row);
  }
  trends.append(table);
  const projects = UI.section(panel.body, '项目进度');
  for (const project of stats.projects) {
    const line = UI.line(projects, `${project.name} · ${project.done}/${project.total}`);
    const bar = element('progress'); bar.max = Math.max(1, project.total); bar.value = project.done;
    bar.setAttribute('aria-label', `${project.name} 完成进度`); line.append(bar);
  }
}
