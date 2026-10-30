'use strict';
$('#tools').append(UI.button('数据与回收站', openData), UI.button('任务模板', openTemplates));

async function openData() {
  const panel = UI.panel('数据管理');
  async function load() {
    const [trash, backups, labels] = await Promise.all([api('/api/trash'), api('/api/backups'), api('/api/labels')]);
    if (!panel.dialog.isConnected) return;
    panel.body.replaceChildren();
    const bin = UI.section(panel.body, `回收站 · ${trash.length} 项`);
    if (!trash.length) bin.append(element('p', '', '没有已删除的任务。'));
    for (const task of trash) UI.line(bin, task.title, [UI.button('恢复任务', async () => {await api(`/api/tasks/${task.id}/restore`, 'POST', {}); await refresh(); await load();})]);
    const copies = UI.section(panel.body, '数据库备份');
    copies.append(element('p', '', '备份包含任务、记录和设置，存放在本机 data/backups。恢复会替换当前数据，操作前会自动保存一份恢复用备份。'));
    copies.append(UI.button('创建完整备份', async () => {await api('/api/backups', 'POST', {}); await load(); toast('备份已创建并验证');}));
    for (const backup of backups) UI.line(copies, `${new Date(backup.created_at).toLocaleString()} · ${Math.round(backup.bytes / 1024)} KB · ${backup.sha256.slice(0, 12)}`, [UI.button('恢复此备份', () => UI.confirm('恢复备份', '当前数据将替换为所选备份。系统会先自动备份当前数据，是否继续？', async () => {
      await api('/api/backups/restore', 'POST', {...backup, confirm: true}); await refresh(); await load(); toast('已恢复；原数据已另存为安全备份');
    }))]);
    const imports = UI.section(panel.body, 'CSV 导入');
    imports.append(element('p', '', '单次最多 500 行、50,000 字符。格式与导出一致，至少包含“任务”列；项目需提前创建。名称、项目和截止日期相同的记录会跳过。'));
    const picker = element('input'); picker.type = 'file'; picker.accept = '.csv,text/csv'; picker.setAttribute('aria-label', '选择 CSV 文件');
    const preview = element('div', 'import-preview');
    let content = null;
    picker.onchange = async () => {
      try {
        const file = picker.files[0];
        if (!file) return;
        if (file.size > 60000) throw new Error('文件过大，请分批导入（最多约 60 KB）');
        content = await file.text();
        const report = await api('/api/import/csv/preview', 'POST', {csv: content});
        preview.replaceChildren(element('p', '', `可导入 ${report.valid} 项，跳过 ${report.skipped} 项，错误 ${report.errors.length} 项。`));
        for (const error of report.errors.slice(0, 20)) preview.append(element('p', 'form-error', `第 ${error.row} 行：${error.error}`));
        for (const row of report.rows.slice(0, 10)) UI.line(preview, row.title);
        if (!report.errors.length && report.valid) preview.append(UI.button('确认导入', async () => {
          const result = await api('/api/import/csv', 'POST', {csv: content, confirm: true}); await refresh(); preview.replaceChildren(element('p', '', `已导入 ${result.imported} 项，跳过 ${result.skipped} 项。`));
        }));
      } catch (error) {content = null; preview.textContent = error.message;}
    };
    imports.append(picker, preview);
    const tags = UI.section(panel.body, '标签管理');
    for (const label of labels) UI.line(tags, label.name, [UI.button('删除标签', () => UI.confirm('删除标签', '将移除此标签及任务上的关联，任务本身会保留。', async () => {await api(`/api/labels/${label.id}`, 'DELETE'); await load();}))]);
  }
  await load();
}

async function openTemplates() {
  const panel = UI.panel('任务模板');
  async function load() {
    const templates = await api('/api/templates');
    if (!panel.dialog.isConnected) return;
    panel.body.replaceChildren(element('p', '', '在任务详情中保存模板。模板会保留名称、备注、预估时长和清单；创建任务时重新开始。'));
    if (!templates.length) panel.body.append(element('p', '', '还没有模板。'));
    for (const template of templates) UI.line(panel.body, `${template.name} · ${template.recipe.checklist.length} 个清单项`, [
      UI.button('创建任务', async () => {await api(`/api/templates/${template.id}/apply`, 'POST', {project_id: state.project}); await refresh(); toast('已从模板创建任务');}),
      UI.button('删除模板', () => UI.confirm('删除模板', '只删除此模板，已创建的任务会保留。', async () => {await api(`/api/templates/${template.id}`, 'DELETE'); await load();}))]);
  }
  await load();
}

document.addEventListener('taskflow:detail', event => {
  const {id, task, root} = event.detail;
  const section = UI.section(root, '保存为模板');
  section.append(UI.form([{name: 'name', label: '模板名称', value: task.title.slice(0, 100), maxLength: 100}], async data => {await api('/api/templates', 'POST', {...data, task_id: id}); toast('已保存为独立模板');}, '保存模板'));
});
