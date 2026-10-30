'use strict';
let runningFocus = null;
const reminderButton = UI.button('提醒', openReminders);
$('#tools').append(reminderButton);

async function loadExecution() {
  const [sessions, reminders] = await Promise.all([api('/api/focus'), api('/api/reminders')]);
  runningFocus = sessions.find(s => !s.ended_at) || null;
  reminderButton.textContent = `提醒 · ${reminders.length}`;
  drawFocus();
}

function drawFocus() {
  const target = $('#focus-status');
  target.hidden = !runningFocus;
  if (!runningFocus) {target.replaceChildren(); target.dataset.focusId = ''; return;}
  const elapsed = Math.max(0, Math.floor((Date.now() - Date.parse(runningFocus.started_at)) / 1000));
  const remaining = Math.max(0, runningFocus.planned_minutes * 60 - elapsed);
  if (target.dataset.focusId !== String(runningFocus.id)) {
    target.dataset.focusId = runningFocus.id;
    target.replaceChildren(element('span'), UI.button('结束专注', async () => {
    await api(`/api/focus/${runningFocus.id}/stop`, 'POST', {});
    await loadExecution(); await refresh(); toast('专注记录已保存');
    }));
  }
  target.firstChild.textContent = `专注：${runningFocus.title} · 剩余 ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`;
  target.lastChild.textContent = remaining ? '结束专注' : '记录本次专注';
}

async function openReminders() {
  const panel = UI.panel('到期提醒');
  async function load() {
    const reminders = await api('/api/reminders');
    if (!panel.dialog.isConnected) return;
    panel.body.replaceChildren(element('p', '', '仅在工具运行且页面打开时查看提醒，不会发送外部通知。'));
    if (!reminders.length) panel.body.append(element('p', '', '暂时没有到期提醒。'));
    for (const reminder of reminders) UI.line(panel.body, reminder.title, [
      UI.button('查看任务', () => {panel.dialog.close(); return openDetails(reminder.task_id);}),
      UI.button('延后15分钟', async () => {await api(`/api/reminders/${reminder.id}`, 'PATCH', {action: 'snooze', minutes: 15}); await load(); await loadExecution();}),
      UI.button('知道了', async () => {await api(`/api/reminders/${reminder.id}`, 'PATCH', {action: 'dismiss'}); await load(); await loadExecution();})]);
  }
  await load();
}

document.addEventListener('taskflow:detail', async event => {
  const {id, task, root, reload: reloadDetail} = event.detail;
  const section = UI.section(root, '计划与执行');
  const base = `/api/tasks/${id}`;
  try {
    const [time, dependencies, reminders] = await Promise.all([api(`${base}/time`), api(`${base}/dependencies`), api(`${base}/reminders`)]);
    if (!root.isConnected) return;
    section.append(element('p', '', `预估 ${time.estimate_minutes} 分钟 · 已记录 ${time.total_minutes} 分钟`));
    section.append(UI.form([{name: 'minutes', label: '预估分钟', type: 'number', min: 0, max: 525600, value: time.estimate_minutes}], async d => {await api(`${base}/estimate`, 'PATCH', {minutes: Number(d.minutes)}); await refresh(); await reloadDetail();}, '保存预估'));
    const ledger = UI.section(section, '时间记录');
    for (const entry of time.entries) UI.line(ledger, `${entry.day} · ${entry.minutes} 分钟 · ${entry.note}`, [UI.button('移除', async () => {await api(`${base}/time/${entry.id}`, 'DELETE'); await reloadDetail(); await refresh();})]);
    ledger.append(UI.form([{name: 'minutes', label: '投入分钟', type: 'number', min: 1, max: 1440}, {name: 'day', label: '工作日期', type: 'date', value: localDate()}, {name: 'note', label: '说明', required: false, maxLength: 1000}], async d => {await api(`${base}/time`, 'POST', {...d, minutes: Number(d.minutes)}); await reloadDetail(); await refresh();}, '记录时间'));
    ledger.append(UI.form([{name: 'minutes', label: '开始专注（分钟）', type: 'number', min: 1, max: 180, value: 25}], async d => {await api('/api/focus', 'POST', {task_id: id, minutes: Number(d.minutes)}); await loadExecution(); toast('专注已开始，关闭详情后可查看计时。');}, '开始专注'));
    const deps = UI.section(section, '前置任务');
    for (const dep of dependencies) UI.line(deps, `#${dep.id} ${dep.title} · ${labels[dep.status]}${dep.deleted_at ? '（已删除）' : ''}`, [UI.button('解除关系', async () => {await api(`${base}/dependencies/${dep.id}`, 'DELETE'); await reloadDetail();})]);
    deps.append(UI.form([{name: 'depends_on', label: '前置任务编号', type: 'number', min: 1}], async d => {await api(`${base}/dependencies`, 'POST', {depends_on: Number(d.depends_on)}); await reloadDetail();}));
    const recurring = UI.section(section, '重复计划');
    recurring.append(element('p', '', '完成时按当前截止日期顺延；0 天表示不重复。'));
    recurring.append(UI.form([{name: 'days', label: '重复间隔（天）', type: 'number', min: 0, max: 3650, value: task.recurrence_days}], async d => {await api(`${base}/recurrence`, 'POST', {days: Number(d.days)}); await refresh(); await reloadDetail();}, '保存间隔'));
    const alerts = UI.section(section, '任务提醒');
    for (const reminder of reminders) UI.line(alerts, `${new Date(reminder.remind_at).toLocaleString()} · ${reminder.dismissed ? '已关闭' : '等待提醒'}`, reminder.dismissed ? [] : [UI.button('关闭', async () => {await api(`/api/reminders/${reminder.id}`, 'PATCH', {action: 'dismiss'}); await reloadDetail(); await loadExecution();})]);
    alerts.append(UI.form([{name: 'when', label: '本地提醒时间', type: 'datetime-local'}], async d => {await api(`${base}/reminders`, 'POST', {remind_at: new Date(d.when).toISOString()}); await reloadDetail(); await loadExecution();}, '设置提醒'));
  } catch (error) {section.append(element('p', 'form-error', error.message));}
});
document.addEventListener('taskflow:refresh', () => loadExecution().catch(e => toast(e.message)));
loadExecution().catch(e => toast(e.message));
setInterval(() => {if (runningFocus) drawFocus();}, 1000);
setInterval(() => loadExecution().catch(() => {}), 60000);
