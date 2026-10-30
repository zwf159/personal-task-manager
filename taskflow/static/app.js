'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {tasks: [], projects: [], view: 'all', project: null, pending: false, page: 0, total: 0, stats: {}, showArchived: false};
const labels = {todo: '待开始', doing: '进行中', done: '已完成', low: '低', medium: '中', high: '高'};

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

async function api(path, method = 'GET', data) {
  const response = await fetch(path, {method, headers: {'Content-Type': 'application/json', 'X-Taskflow-Request': '1'}, body: data === undefined ? undefined : JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作失败，请重试');
  return result;
}

let toastTimer;
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4000);
}

function localDate() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function filteredTasks() {
  return state.tasks;
}

function currentFilters() {
  const filters = {view: state.view, sort: $('#sort').value};
  if (state.project) filters.project_id = state.project;
  for (const key of ['status', 'priority']) if ($(`#${key}`).value) filters[key] = $(`#${key}`).value;
  if ($('#search').value.trim()) filters.q = $('#search').value.trim();
  return filters;
}

function reload() {
  state.page = 0;
  refresh().catch(error => toast(error.message));
}

function render() {
  const done = state.stats.done || 0;
  const progress = state.stats.total ? Math.round(done / state.stats.total * 100) : 0;
  $('#stat-total').textContent = state.stats.total || 0;
  $('#stat-doing').textContent = state.stats.doing || 0;
  $('#stat-done').textContent = done;
  $('#stat-progress').textContent = `${progress}%`;
  $('#progress').value = progress;
  $('#view-title').textContent = state.project ? state.projects.find(p => p.id === state.project)?.name || '项目任务' : {all: '全部任务', today: '今天到期', overdue: '已逾期'}[state.view];
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', !state.project && b.dataset.view === state.view));
  $('#projects').replaceChildren();
  state.projects.filter(p => !p.archived || state.showArchived).forEach(p => {
    const row = element('div', 'project-row');
    const button = element('button', state.project === p.id ? 'active project-link' : 'project-link', `◦  ${p.name}`);
    button.title = p.name;
    button.append(element('span', 'count', p.task_count));
    button.onclick = () => {state.project = p.id; state.view = 'all'; reload();};
    const edit = element('button', 'icon-button', '⋯');
    edit.setAttribute('aria-label', `编辑项目 ${p.name}`);
    edit.onclick = () => openProject(p);
    const remove = element('button', 'icon-button remove-project', '×');
    remove.setAttribute('aria-label', `删除项目 ${p.name}`);
    remove.onclick = () => confirmDelete(`删除“${p.name}”分组？其中的任务将保留并移至未分组。`, () => mutate(`/api/projects/${p.id}`, 'DELETE'));
    row.append(button, edit, remove);
    $('#projects').append(row);
  });
  const tasks = filteredTasks();
  $('#result-count').textContent = `${state.total} 项任务`;
  $('#empty').hidden = tasks.length !== 0;
  $('#task-list').replaceChildren(...tasks.map(taskRow));
  const params = new URLSearchParams(currentFilters());
  $('#export').href = `/api/export.csv?${params}`;
  $('#previous').disabled = state.page === 0;
  $('#next').disabled = (state.page + 1) * 25 >= state.total;
  $('#page-info').textContent = `第 ${state.page + 1} / ${Math.max(1, Math.ceil(state.total / 25))} 页`;
}

function taskRow(task) {
  const row = element('article', `task-row ${task.status === 'done' ? 'completed' : ''}`);
  const check = element('button', 'check', task.status === 'done' ? '✓' : '');
  check.setAttribute('aria-label', `${task.status === 'done' ? '重新打开' : '完成'}任务：${task.title}`);
  check.onclick = () => mutate(`/api/tasks/${task.id}`, 'PATCH', {status: task.status === 'done' ? 'todo' : 'done'});
  const content = element('div', 'task-content');
  const title = element('button', 'task-title', task.title);
  title.onclick = () => openTask(task);
  content.append(title);
  if (task.notes) content.append(element('p', 'task-notes', task.notes));
  const meta = element('div', 'task-meta');
  if (task.project_name) meta.append(element('span', 'project-tag', task.project_name));
  if (task.due_date) meta.append(element('span', task.due_date < localDate() && task.status !== 'done' ? 'overdue' : '', `◷ ${task.due_date}`));
  meta.append(element('span', `priority ${task.priority}`, `${labels[task.priority]}优先级`));
  content.append(meta);
  const status = element('span', `status ${task.status}`, labels[task.status]);
  const remove = element('button', 'icon-button delete-task', '×');
  remove.setAttribute('aria-label', `删除任务：${task.title}`);
  remove.onclick = () => confirmDelete(`将“${task.title}”移入回收站？之后可以恢复。`, () => mutate(`/api/tasks/${task.id}`, 'DELETE'));
  row.append(check, content, status, remove);
  const detail = element('button', 'secondary detail-button', '详情');
  detail.onclick = () => openDetails(task.id);
  row.insertBefore(detail, status);
  return row;
}

let requestGeneration = 0;
async function refresh() {
  const generation = ++requestGeneration;
  const params = new URLSearchParams({...currentFilters(), limit: 25, offset: state.page * 25});
  const [page, projects, stats] = await Promise.all([api(`/api/search?${params}`), api('/api/projects'), api('/api/stats')]);
  if (generation !== requestGeneration) return;
  state.tasks = page.items;
  state.total = page.total;
  state.stats = stats;
  state.projects = projects;
  if (state.page && state.page * 25 >= state.total) {state.page--; return refresh();}
  if (state.project && !projects.some(p => p.id === state.project)) state.project = null;
  render();
  document.dispatchEvent(new CustomEvent('taskflow:refresh'));
}

async function mutate(path, method, payload) {
  if (state.pending) return;
  state.pending = true;
  try {
    await api(path, method, payload);
    await refresh();
    toast('已保存');
  } catch (error) {toast(error.message);}
  finally {state.pending = false;}
}

function openTask(task) {
  const form = $('#task-form');
  form.reset();
  $('#task-error').textContent = '';
  $('#dialog-title').textContent = task ? '编辑任务' : '新建任务';
  const select = form.elements.project_id;
  select.replaceChildren(new Option('未分组', ''), ...state.projects.map(p => new Option(p.name, p.id)));
  for (const key of ['id', 'title', 'notes', 'due_date', 'priority', 'status', 'project_id']) {
    if (task) form.elements[key].value = task[key] ?? '';
  }
  if (!task && state.project) select.value = state.project;
  form.dataset.version = task?.version || '';
  $('#task-dialog').showModal();
  form.elements.title.focus();
}

let confirmAction;
function confirmDelete(message, action) {
  $('#confirm-message').textContent = message;
  confirmAction = action;
  $('#confirm-dialog').showModal();
  $('#confirm-cancel').focus();
}
$('#confirm-cancel').onclick = () => $('#confirm-dialog').close();
$('#confirm-delete').onclick = () => {$('#confirm-dialog').close(); confirmAction?.();};
document.querySelectorAll('.close-dialog').forEach(b => {b.onclick = () => b.closest('dialog').close();});
$('#new-task').onclick = $('#empty-create').onclick = () => openTask();
function openProject(project) {
  const form = $('#project-form');
  form.reset();
  $('#project-error').textContent = '';
  $('#project-dialog-title').textContent = project ? '编辑项目' : '新建项目';
  if (project) {
    for (const key of ['id', 'name', 'description']) form.elements[key].value = project[key] || '';
    form.elements.archived.checked = Boolean(project.archived);
  }
  $('#project-dialog').showModal();
}
$('#add-project').onclick = () => openProject();
$('#toggle-archived').onclick = () => {state.showArchived = !state.showArchived; $('#toggle-archived').textContent = state.showArchived ? '隐藏已归档项目' : '显示已归档项目'; render();};
$('#views').onclick = event => {
  const button = event.target.closest('[data-view]');
  if (button) {state.view = button.dataset.view; state.project = null; reload();}
};
for (const id of ['search', 'status', 'priority', 'sort']) $(`#${id}`).addEventListener('input', reload);
$('#previous').onclick = () => {state.page--; refresh().catch(e => toast(e.message));};
$('#next').onclick = () => {state.page++; refresh().catch(e => toast(e.message));};

async function submitForm(event, kind) {
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector('[type=submit]');
  if (button.disabled) return;
  button.disabled = true;
  const data = Object.fromEntries(new FormData(form));
  const id = data.id;
  delete data.id;
  if (kind === 'task' && id) data.expected_version = Number(form.dataset.version);
  if (kind === 'project') data.archived = form.elements.archived.checked;
  if (kind === 'task') data.project_id = data.project_id ? Number(data.project_id) : null;
  try {
    await api(`/api/${kind === 'task' ? 'tasks' : 'projects'}${id ? `/${id}` : ''}`, id ? 'PATCH' : 'POST', data);
    form.closest('dialog').close();
    await refresh();
    toast(kind === 'task' ? '任务已保存' : '项目已创建');
  } catch (error) {
    $(`#${kind}-error`).textContent = error.message;
    toast(error.message);
  } finally {button.disabled = false;}
}
$('#task-form').onsubmit = event => submitForm(event, 'task');
$('#project-form').onsubmit = event => submitForm(event, 'project');
refresh().catch(error => {$('#subtitle').textContent = '加载失败，请刷新页面重试。'; toast(error.message);});
