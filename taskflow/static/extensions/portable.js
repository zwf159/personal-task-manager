"use strict";

Workspace.register(
  "portable",
  "数据迁移",
  "以可查看的 JSON 数据包迁移任务和知识记录，先校验关联再事务导入。",
  async () => {
    const panel = UI.panel("核心数据导出与迁移");
    panel.dialog.classList.add("portable-panel");
    const tabs = element("div", "portable-tabs");
    const content = element("div", "portable-content");
    const status = element("p", "portable-status");
    status.setAttribute("role", "status");
    const error = element("p", "portable-error");
    error.setAttribute("role", "alert");
    const names = {
      projects: "项目",
      labels: "标签",
      tasks: "任务",
      task_labels: "任务标签关联",
      checklist_items: "清单项",
      comments: "进展记录",
      time_entries: "工时",
      task_links: "参考链接",
      dependencies: "前置关系",
      goals: "目标",
      goal_tasks: "目标任务关联",
      habits: "习惯",
      habit_logs: "打卡记录",
      notes: "笔记",
      note_revisions: "笔记历史",
      captures: "收集项",
      reminders: "应用内提醒",
    };
    let selectedFile = null;
    let selectedDocument = null;
    let bytes = null;
    let digest = null;
    let session = null;
    let report = null;
    let uploading = false;
    let aborted = false;
    let prefix = "导入-";
    const chunkSize = 40960;
    const maxBytes = 5 * 1024 * 1024;
    const localKey = "taskflow-portable-session";

    function remember(token) {
      try {
        if (token) localStorage.setItem(localKey, token);
        else localStorage.removeItem(localKey);
      } catch {
        status.textContent =
          "浏览器不允许保存恢复标记，刷新后可从历史会话继续。";
      }
    }

    function download(value, filename) {
      const blob = new Blob([JSON.stringify(value)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = element("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function showCounts(root, counts) {
      const table = element("table", "portable-table");
      const header = element("tr");
      header.append(element("th", "", "记录类型"), element("th", "", "数量"));
      table.append(header);
      for (const [key, count] of Object.entries(counts)) {
        const row = element("tr");
        row.append(
          element("td", "", names[key] || key),
          element("td", "", count),
        );
        table.append(row);
      }
      root.append(table);
    }

    function clearView() {
      content.replaceChildren();
      error.textContent = "";
      status.textContent = "";
    }

    function heading(title, message) {
      content.append(
        element("h3", "", title),
        element("p", "portable-help", message),
      );
    }

    async function exportView() {
      clearView();
      heading(
        "导出可移植核心数据",
        "此数据包用于查看和跨工作空间迁移，不代替完整数据库备份。计划、复盘、规则、专注和备份文件不包含在内。",
      );
      content.append(
        UI.form(
          [
            {
              name: "project_id",
              label: "导出范围",
              required: false,
              options: [
                ["", "全部项目与知识数据"],
                ...state.projects.map((p) => [p.id, p.name]),
              ],
            },
            {
              name: "include_archived",
              label: "归档知识记录",
              options: [
                ["1", "包含"],
                ["0", "不包含"],
              ],
            },
          ],
          async (values) => {
            const result = await api("/api/portable/export", "POST", {
              project_id: values.project_id ? Number(values.project_id) : null,
              include_archived: values.include_archived === "1",
            });
            const summary = UI.section(content, "导出摘要");
            showCounts(summary, result.summary);
            summary.append(element("p", "", `编码后 ${result.bytes} 字节。`));
            for (const warning of result.warnings)
              summary.append(element("p", "portable-warning", warning));
            summary.append(
              element(
                "p",
                "portable-help",
                "未包含：" + result.excluded.join("、"),
              ),
            );
            summary.append(
              UI.button("下载 JSON 数据包", () =>
                download(result.document, `taskflow-${localDate()}.json`),
              ),
            );
            PortableBrowser.mount(summary, result.document, names);
            status.textContent = "数据包已生成，请检查摘要后下载。";
          },
          "生成导出预览",
        ),
      );
    }

    async function chooseFile(file) {
      if (!file) return;
      if (!file.size || file.size > maxBytes)
        throw new Error("请选择不超过 5 MB 的 JSON 文件。");
      const buffer = await file.arrayBuffer();
      const parsed = JSON.parse(
        new TextDecoder("utf-8", { fatal: true }).decode(buffer),
      );
      if (parsed.format !== "taskflow-portable" || parsed.version !== 1)
        throw new Error("不是支持的 Taskflow 数据包。");
      selectedFile = file;
      selectedDocument = parsed;
      bytes = new Uint8Array(buffer);
      const hash = await crypto.subtle.digest("SHA-256", bytes);
      digest = [...new Uint8Array(hash)]
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
      session = null;
      report = null;
      status.textContent = `已选择 ${file.name}，${file.size} 字节。指纹 ${digest.slice(0, 16)}…`;
    }

    function encodedChunk(start, end) {
      let binary = "";
      for (const value of bytes.subarray(start, end))
        binary += String.fromCharCode(value);
      return btoa(binary);
    }

    async function upload(progress, label) {
      if (!bytes || !selectedFile) throw new Error("先选择需要迁移的数据包。");
      if (uploading) return;
      uploading = true;
      aborted = false;
      try {
        if (!session) {
          session = await api("/api/portable/sessions", "POST", {
            name: selectedFile.name,
            size: bytes.length,
            sha256: digest,
            chunks: Math.ceil(bytes.length / chunkSize),
          });
          remember(session.token);
        }
        const current = await api(`/api/portable/sessions/${session.token}`);
        if (current.sha256 !== digest)
          throw new Error("所选文件与原会话不同，请取消会话后重新上传。");
        const received = new Set(current.received);
        progress.max = current.chunks;
        progress.value = received.size;
        for (let seq = 0; seq < current.chunks; seq++) {
          if (aborted || !panel.dialog.isConnected) return;
          if (received.has(seq)) continue;
          const result = await api(
            `/api/portable/sessions/${session.token}/chunks`,
            "POST",
            {
              seq,
              data: encodedChunk(
                seq * chunkSize,
                Math.min(bytes.length, (seq + 1) * chunkSize),
              ),
            },
          );
          progress.value = result.received;
          label.textContent = `已上传 ${result.received}/${current.chunks} 块`;
        }
        if (!aborted) await loadPreview();
      } finally {
        uploading = false;
      }
    }

    async function importView() {
      clearView();
      heading(
        "选择数据包并上传",
        "导入只添加记录，不覆盖现有任务和笔记。服务器重新校验全部字段与关联；同名项目改名，同名标签复用。会话一小时后过期。",
      );
      const picker = element("input", "portable-file");
      picker.type = "file";
      picker.accept = ".json,application/json";
      picker.setAttribute("aria-label", "选择 Taskflow JSON 数据包");
      picker.onchange = async () => {
        try {
          await chooseFile(picker.files[0]);
          error.textContent = "";
        } catch (failure) {
          bytes = null;
          error.textContent = failure.message;
        }
      };
      content.append(picker);
      const prefixField = element("input");
      prefixField.value = prefix;
      prefixField.maxLength = 20;
      prefixField.setAttribute("aria-label", "同名项目前缀");
      prefixField.oninput = () => {
        prefix = prefixField.value;
      };
      const prefixLabel = element("label", "portable-prefix", "同名项目前缀");
      prefixLabel.append(prefixField);
      content.append(prefixLabel);
      const progress = element("progress");
      progress.max = 1;
      progress.value = 0;
      progress.setAttribute("aria-label", "文件上传进度");
      const label = element("span", "portable-progress-label", "等待上传");
      const actions = element("div", "action-strip");
      actions.append(UI.button("上传并校验", () => upload(progress, label)));
      actions.append(
        UI.button("暂停上传", () => {
          aborted = true;
          label.textContent = "已请求暂停，可再次点击上传继续。";
        }),
      );
      actions.append(
        UI.button("取消当前会话", async () => {
          aborted = true;
          if (session)
            await api(`/api/portable/sessions/${session.token}`, "DELETE");
          session = null;
          remember(null);
          status.textContent = "迁移会话已取消，业务数据没有改变。";
        }),
      );
      content.append(progress, label, actions);
      const stored = localStorage.getItem(localKey);
      if (stored)
        content.append(UI.button("查看上次迁移会话", () => resume(stored)));
    }

    function renderErrors(root, errors) {
      if (!errors.length) return;
      const box = UI.section(root, "需要修正的源数据");
      for (const item of errors) {
        UI.line(
          box,
          `${names[item.entity] || item.entity} · 第 ${item.row} 条：${item.error}`,
        );
      }
      box.append(
        element(
          "p",
          "portable-help",
          "请在源工作空间修复后重新导出，不要直接忽略关联错误。",
        ),
      );
    }

    function renderConflicts(root, conflicts) {
      const box = UI.section(root, "名称冲突处理");
      if (!conflicts.length)
        box.append(element("p", "", "未发现项目或标签名称冲突。"));
      for (const item of conflicts) {
        UI.line(
          box,
          `${names[item.entity]}：${item.source} → ${item.target}（${item.action === "reuse" ? "复用现有记录" : "新记录改名"}）`,
        );
      }
    }

    function renderContent(root, data) {
      const box = UI.section(root, "数据关系摘要");
      UI.line(
        box,
        `未分组任务 ${data.unassigned_tasks} 项；工时 ${data.time_minutes} 分钟。`,
      );
      UI.line(
        box,
        `前置关系 ${data.dependencies.relationships} 条；有前置的任务 ${data.dependencies.tasks_with_prerequisites} 项。`,
      );
      for (const project of data.projects)
        UI.line(
          box,
          `${project.name} · ${project.tasks} 个任务${project.archived ? " · 已归档" : ""}`,
        );
      for (const [key, value] of Object.entries(data.task_statuses))
        UI.line(box, `${labels[key] || key}：${value}`);
    }

    async function loadPreview() {
      if (!session) throw new Error("没有可预览的会话。");
      report = await api(
        `/api/portable/sessions/${session.token}/preview`,
        "POST",
        { prefix },
      );
      renderPreview();
    }

    function renderPreview() {
      clearView();
      heading(
        "迁移预览",
        report.valid
          ? "校验通过。请检查记录数量、名称冲突和关联，再决定是否导入。"
          : `发现 ${report.error_count} 项问题，本次不会写入业务数据。`,
      );
      content.append(element("p", "portable-policy", report.policy));
      showCounts(content, report.counts);
      renderErrors(content, report.errors);
      renderConflicts(content, report.conflicts);
      renderContent(content, report.content);
      const duplicates = UI.section(
        content,
        `内容重复提示 · ${report.duplicates.total} 项`,
      );
      duplicates.append(
        element("p", "portable-help", report.duplicates.policy),
      );
      for (const group of [report.duplicates.tasks, report.duplicates.notes]) {
        for (const duplicate of group.samples) {
          UI.line(
            duplicates,
            `${names[duplicate.entity]}：源 #${duplicate.source_id} 与现有 #${duplicate.existing_id} 内容相同 · ${duplicate.title}`,
          );
        }
        if (group.total > group.samples.length) {
          duplicates.append(
            element(
              "p",
              "",
              `仅显示前 ${group.samples.length} 条，共 ${group.total} 条匹配。`,
            ),
          );
        }
      }
      if (report.duplicates.total) {
        duplicates.append(
          element(
            "p",
            "portable-warning",
            "确认导入将创建独立副本。若不需要副本，请取消会话，重新选择导出范围。",
          ),
        );
      }
      if (selectedDocument)
        PortableBrowser.mount(content, selectedDocument, names);
      const actions = element("div", "action-strip");
      actions.append(UI.button("重新检查目标状态", loadPreview));
      if (report.valid)
        actions.append(
          UI.button("确认导入此数据包", () =>
            UI.confirm(
              "确认迁移",
              "系统会先备份当前数据库，然后整批添加记录。现有记录不会被覆盖，是否继续？",
              async () => {
                const result = await api(
                  `/api/portable/sessions/${session.token}/commit`,
                  "POST",
                  {
                    confirm: true,
                    preview_token: report.preview_token,
                  },
                );
                remember(null);
                await Workspace.changed();
                renderReceipt(result);
              },
            ),
          ),
        );
      content.append(actions);
    }

    function renderReceipt(result) {
      clearView();
      heading(
        "迁移已完成",
        "重复确认同一会话不会再次创建记录。请保存回执，并核对导入的项目、任务和笔记。",
      );
      const receipt = result.receipt;
      content.append(
        element(
          "p",
          "portable-success",
          `已创建 ${receipt.created_records} 条记录，复用 ${receipt.reused_records} 条记录。`,
        ),
      );
      showCounts(content, result.created);
      const safety = UI.section(content, "恢复保护");
      safety.append(
        element("p", "", `导入前备份：${result.safety_backup.name}`),
      );
      safety.append(
        element("p", "portable-digest", result.safety_backup.sha256),
      );
      const mapping = UI.section(content, "任务编号映射");
      for (const [oldId, newId] of Object.entries(receipt.task_mappings).slice(
        0,
        100,
      ))
        UI.line(mapping, `源任务 #${oldId} → 新任务 #${newId}`);
      if (Object.keys(receipt.task_mappings).length > 100)
        mapping.append(
          element("p", "", "页面显示前 100 项，完整映射在回执中。"),
        );
      content.append(
        UI.button("下载导入回执", () =>
          download(result, `taskflow-import-receipt-${localDate()}.json`),
        ),
      );
      content.append(
        UI.button("复核导入后的记录", async () => {
          const checked = await api(
            `/api/portable/sessions/${result.session}/verify`,
          );
          const view = UI.panel("导入内容复核");
          view.body.append(element("p", "portable-help", checked.note));
          const states = {
            unchanged: "未变化",
            modified: "已修改",
            missing: "已移除",
            recycled: "已回收",
          };
          for (const [state, quantity] of Object.entries(checked.counts)) {
            UI.line(view.body, `${states[state]}：${quantity} 条`);
          }
          for (const sample of checked.samples) {
            UI.line(
              view.body,
              `${names[sample.entity]} #${sample.id} · ${states[sample.state]}`,
            );
          }
        }),
      );
    }

    async function resume(token) {
      const value = await api(`/api/portable/sessions/${token}`);
      session = value;
      if (value.state === "committed") return renderReceipt(value.report);
      if (value.state === "previewed") {
        report = value.report;
        return renderPreview();
      }
      if (value.received.length === value.chunks) return loadPreview();
      clearView();
      heading(
        "文件上传未完成",
        `已收到 ${value.received.length}/${value.chunks} 块。重新选择相同文件后可继续上传。`,
      );
      const picker = element("input");
      picker.type = "file";
      picker.accept = ".json";
      picker.setAttribute("aria-label", "重新选择原数据包");
      picker.onchange = async () => {
        try {
          await chooseFile(picker.files[0]);
          if (digest !== value.sha256)
            throw new Error("所选文件指纹与会话不同。");
          session = value;
          const progress = element("progress");
          const label = element("span");
          content.append(progress, label);
          await upload(progress, label);
        } catch (failure) {
          error.textContent = failure.message;
        }
      };
      content.append(picker);
    }

    async function historyView() {
      clearView();
      heading(
        "最近迁移会话",
        "上传内容保存在本机临时数据库中，一小时后过期；新建会话时清理过期内容。最多同时保留五个未完成会话。",
      );
      const rows = await api("/api/portable/sessions");
      for (const row of rows) {
        UI.line(
          content,
          `${row.name} · ${row.state} · ${new Date(row.created_at).toLocaleString()}`,
          [UI.button("查看", () => resume(row.token))],
        );
      }
      if (!rows.length)
        content.append(element("p", "workspace-empty", "暂无迁移会话。"));
    }

    tabs.append(UI.button("导出数据", exportView));
    tabs.append(UI.button("导入数据", importView));
    tabs.append(UI.button("最近会话", historyView));
    panel.body.append(tabs, status, error, content);
    panel.dialog.addEventListener("close", () => {
      aborted = true;
    });
    await exportView();
  },
);
