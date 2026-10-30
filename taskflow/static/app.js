'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {tasks: [], projects: [], view: 'all', project: null, pending: false};
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
  const today = localDate();
  const q = $('#search').value.trim().toLocaleLowerCase();
  return state.tasks.filter(t => (!state.project || t.project_id === state.project)
    && (state.view !== 'today' || (t.due_date === today && t.status !== 'done'))
    && (state.view !== 'overdue' || (t.due_date && t.due_date < today && t.status !== 'done'))
    && (!$('#status').value || t.status === $('#status').value)
    && (!$('#priority').value || t.priority === $('#priority').value)
    && (!q || `${t.title}\n${t.notes}`.toLocaleLowerCase().includes(q)));
}

function render() {
  const done = state.tasks.filter(t => t.status === 'done').length;
  const progress = state.tasks.length ? Math.round(done / state.tasks.length * 100) : 0;
  $('#stat-total').textContent = state.tasks.length;
  $('#stat-doing').textContent = state.tasks.filter(t => t.status === 'doing').length;
  $('#stat-done').textContent = done;
  $('#stat-progress').textContent = `${progress}%`;
  $('#progress').value = progress;
  $('#view-title').textContent = state.project ? state.projects.find(p => p.id === state.project)?.name || '项目任务' : {all: '全部任务', today: '今天到期', overdue: '已逾期'}[state.view];
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', !state.project && b.dataset.view === state.view));
  $('#projects').replaceChildren();
  state.projects.forEach(p => {
    const row = element('div', 'project-row');
    const button = element('button', state.project === p.id ? 'active project-link' : 'project-link', `◦  ${p.name}`);
    button.title = p.name;
    button.append(element('span', 'count', p.task_count));
    button.onclick = () => {state.project = p.id; state.view = 'all'; render();};
    const remove = element('button', 'icon-button remove-project', '×');
    remove.setAttribute('aria-label', `删除项目 ${p.name}`);
    remove.onclick = () => confirmDelete(`删除“${p.name}”分组？其中的任务将保留并移至未分组。`, () => mutate(`/api/projects/${p.id}`, 'DELETE'));
    row.append(button, remove);
    $('#projects').append(row);
  });
  const tasks = filteredTasks();
  $('#result-count').textContent = `${tasks.length} 项任务`;
  $('#empty').hidden = tasks.length !== 0;
  $('#task-list').replaceChildren(...tasks.map(taskRow));
  const params = new URLSearchParams();
  if (state.project) params.set('project_id', state.project);
  if (state.view !== 'all') params.set('view', state.view);
  for (const key of ['status', 'priority']) if ($(`#${key}`).value) params.set(key, $(`#${key}`).value);
  if ($('#search').value.trim()) params.set('q', $('#search').value.trim());
  $('#export').href = `/api/export.csv?${params}`;
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
  remove.onclick = () => confirmDelete(`删除“${task.title}”？此操作无法撤销。`, () => mutate(`/api/tasks/${task.id}`, 'DELETE'));
  row.append(check, content, status, remove);
  return row;
}

async function refresh() {
  const [tasks, projects] = await Promise.all([api('/api/tasks'), api('/api/projects')]);
  state.tasks = tasks;
  state.projects = projects;
  if (state.project && !projects.some(p => p.id === state.project)) state.project = null;
  render();
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
$('#add-project').onclick = () => {$('#project-form').reset(); $('#project-error').textContent = ''; $('#project-dialog').showModal();};
$('#views').onclick = event => {
  const button = event.target.closest('[data-view]');
  if (button) {state.view = button.dataset.view; state.project = null; render();}
};
for (const id of ['search', 'status', 'priority']) $(`#${id}`).addEventListener('input', render);

async function submitForm(event, kind) {
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector('[type=submit]');
  if (button.disabled) return;
  button.disabled = true;
  const data = Object.fromEntries(new FormData(form));
  const id = data.id;
  delete data.id;
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
