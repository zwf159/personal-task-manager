"use strict";
(() => {
  const minuteText = (value) =>
    `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
  const weekday = (value) =>
    new Date(`${value}T12:00:00`).toLocaleDateString("zh-CN", {
      weekday: "short",
    });
  const dateText = (value) =>
    `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  const dateOffset = (value, days) => {
    const day = new Date(`${value}T12:00:00`);
    day.setDate(day.getDate() + days);
    return dateText(day);
  };
  const download = (name, content, mime) => {
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const link = element("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const control = (root, title, type, value) => {
    const label = element("label", "calendar-control", title);
    const input = element(type === "select" ? "select" : "input");
    if (type !== "select") input.type = type;
    input.setAttribute("aria-label", title);
    if (value !== undefined) input.value = value;
    label.append(input);
    root.append(label);
    return input;
  };
  const note = (root, message, warning = false) => {
    const item = element("p", warning ? "calendar-warning" : "muted", message);
    root.append(item);
    return item;
  };
  const slotLabel = (slot) =>
    `${slot.day} ${minuteText(slot.start_minute)}–${minuteText(slot.end_minute)} ${slot.title}`;

  async function openCalendar() {
    const panel = UI.panel("日历排程");
    panel.dialog.classList.add("calendar-panel");
    const toolbar = element("div", "calendar-toolbar");
    const filters = element("div", "calendar-toolbar");
    const actions = element("div", "calendar-actions");
    const status = element("p", "calendar-status");
    status.setAttribute("role", "status");
    const grid = element("div", "calendar-grid");
    const anchor = control(toolbar, "基准日期", "date", localDate());
    const view = control(toolbar, "视图", "select");
    view.add(new Option("周视图", "week"));
    view.add(new Option("月视图", "month"));
    const project = control(filters, "项目", "select");
    project.add(new Option("所有项目与独立安排", ""));
    for (const item of state.projects)
      project.add(new Option(item.name, item.id));
    const search = control(filters, "搜索安排或截止任务", "search", "");
    search.maxLength = 200;
    let data;
    let dragging = null;
    let generation = 0;
    const options = () => ({
      anchor: anchor.value,
      view: view.value,
      project_id: project.value,
      q: search.value,
    });
    const reload = async (focusDay) => {
      const ticket = ++generation;
      status.textContent = "正在读取日历…";
      const result = await api(
        `/api/calendar?${new URLSearchParams(options())}`,
      );
      if (ticket !== generation || !panel.dialog.isConnected) return;
      data = result;
      draw();
      if (focusDay)
        grid
          .querySelector(`[data-day="${focusDay}"] .calendar-day-title`)
          ?.focus();
    };
    const changed = async (day) => {
      await reload(day);
      await Workspace.changed();
    };
    const navigate = async (direction) => {
      if (view.value === "week")
        anchor.value = dateOffset(anchor.value, direction * 7);
      else {
        const current = new Date(`${anchor.value}T12:00:00`);
        current.setDate(1);
        current.setMonth(current.getMonth() + direction);
        anchor.value = dateText(current);
      }
      await reload();
    };
    toolbar.append(
      UI.button("上一段", () => navigate(-1)),
      UI.button("今天", async () => {
        anchor.value = localDate();
        await reload();
      }),
      UI.button("下一段", () => navigate(1)),
    );
    filters.append(UI.button("应用筛选", () => reload()));
    actions.append(
      UI.button("复制周计划", () => copyDialog(anchor.value, changed)),
      UI.button("导入 ICS 日历", () => importDialog(changed)),
      UI.button("导出当前日历", () => exportDialog(options())),
      UI.button("日历偏好", () => settingsDialog(data.settings, reload)),
      UI.button("批次记录", () => historyDialog()),
    );
    panel.body.append(toolbar, filters, actions, status, grid);
    note(
      panel.body,
      "容量统计始终包含隐藏安排。拖动到另一日期或点击时段可预览调整；键盘可用方向键选择日期，Enter 打开当天安排。",
    );
    anchor.onchange = () => reload().catch((error) => toast(error.message));
    view.onchange = anchor.onchange;
    grid.addEventListener("keydown", (event) => {
      if (!event.target.classList.contains("calendar-day-title")) return;
      const offsets = {
        ArrowLeft: -1,
        ArrowRight: 1,
        ArrowUp: -7,
        ArrowDown: 7,
      };
      if (!(event.key in offsets)) return;
      event.preventDefault();
      const buttons = [...grid.querySelectorAll(".calendar-day-title")];
      const index = buttons.indexOf(event.target) + offsets[event.key];
      buttons[index]?.focus();
    });
    function draw() {
      grid.replaceChildren();
      grid.classList.toggle("calendar-month", data.view === "month");
      const first = data.days[0]?.day;
      const last = data.days.at(-1)?.day;
      status.textContent = `${first} 至 ${last} · 可见时段 ${data.total_slots} · 全部安排 ${data.scheduled_minutes} 分钟`;
      for (const day of data.days) {
        const cell = element("section", "calendar-day");
        cell.dataset.day = day.day;
        cell.classList.toggle("calendar-today", day.day === localDate());
        cell.classList.toggle(
          "calendar-outside",
          data.view === "month" &&
            day.day.slice(0, 7) !== anchor.value.slice(0, 7),
        );
        const title = UI.button(
          `${day.day.slice(5)} ${weekday(day.day)}`,
          () => dayDialog(day.day, changed),
          "calendar-day-title",
        );
        const meter = element("meter");
        meter.min = 0;
        meter.max = Math.max(1, day.capacity);
        meter.value = day.scheduled;
        meter.setAttribute(
          "aria-label",
          `${day.day} 已安排 ${day.scheduled} / ${day.capacity} 分钟`,
        );
        cell.append(
          title,
          meter,
          element("small", "", `${day.scheduled}/${day.capacity} 分钟`),
        );
        if (day.hidden_slots)
          cell.append(
            element(
              "small",
              "muted",
              `另有 ${day.hidden_slots} 个安排被筛选隐藏`,
            ),
          );
        for (const slot of day.slots) {
          const button = UI.button(
            `${minuteText(slot.start_minute)}–${minuteText(slot.end_minute)} ${slot.title}`,
            () => editDialog(slot, changed),
            "calendar-slot",
          );
          button.draggable = true;
          button.title = slot.note || "点击编辑，或拖到其他日期";
          button.ondragstart = (event) => {
            dragging = slot;
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", String(slot.id));
          };
          button.ondragend = () => {
            dragging = null;
          };
          if (slot.task_deleted) button.classList.add("calendar-unavailable");
          cell.append(button);
        }
        for (const task of day.due_tasks) {
          const button = UI.button(
            `截止：${task.title}`,
            () => openDetails(task.id),
            "calendar-due",
          );
          if (task.status === "done") button.classList.add("calendar-done");
          cell.append(button);
        }
        cell.ondragover = (event) => {
          if (!dragging) return;
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
        };
        cell.ondrop = async (event) => {
          event.preventDefault();
          const slot = dragging;
          dragging = null;
          if (!slot || slot.day === day.day) return;
          try {
            await editDialog(slot, changed, day.day, true);
          } catch (error) {
            toast(error.message);
          }
        };
        grid.append(cell);
      }
    }
    await reload();
  }

  async function dayDialog(day, changed) {
    const panel = UI.panel(`${day} 当天安排`);
    const data = await api(`/api/planner?${new URLSearchParams({ day })}`);
    const summary = UI.section(panel.body, "容量与时段");
    note(
      summary,
      `已安排 ${data.scheduled} 分钟，剩余 ${data.remaining} 分钟。`,
    );
    summary.append(
      UI.form(
        [
          {
            name: "minutes",
            label: "当天可用分钟",
            type: "number",
            min: data.scheduled,
            max: 1440,
            value: data.capacity,
          },
        ],
        async (values) => {
          await api("/api/planner/capacity", "POST", {
            day,
            minutes: Number(values.minutes),
          });
          panel.dialog.close();
          await changed(day);
        },
        "保存容量",
      ),
    );
    for (const slot of data.slots) {
      UI.line(
        summary,
        `${minuteText(slot.start_minute)}–${minuteText(slot.end_minute)} ${slot.title}`,
        [
          UI.button("编辑", async () => {
            const fresh = await api(
              `/api/calendar?${new URLSearchParams({ anchor: day, view: "week" })}`,
            );
            const current = fresh.days
              .flatMap((row) => row.slots)
              .find((row) => row.id === slot.id);
            if (!current) throw new Error("此安排已删除，请重新打开日历");
            panel.dialog.close();
            await editDialog(current, changed);
          }),
          UI.button("删除", () =>
            UI.confirm(
              "删除时段",
              `确认删除“${slot.title}”？关联任务仍会保留。`,
              async () => {
                await api(`/api/planner/${slot.id}`, "DELETE");
                panel.dialog.close();
                await changed(day);
              },
            ),
          ),
        ],
      );
    }
    const create = UI.section(panel.body, "新增时段");
    create.append(
      UI.form(
        [
          { name: "title", label: "安排名称", maxLength: 200 },
          { name: "start_time", label: "开始 HH:MM", value: "09:00" },
          {
            name: "end_time",
            label: "结束 HH:MM（可填 24:00）",
            value: "10:00",
          },
          {
            name: "task_id",
            label: "关联任务编号（可留空）",
            type: "number",
            min: 1,
            required: false,
          },
          {
            name: "note",
            label: "说明",
            type: "textarea",
            maxLength: 2000,
            required: false,
          },
        ],
        async (values) => {
          await api("/api/planner", "POST", {
            ...values,
            day,
            task_id: values.task_id ? Number(values.task_id) : null,
          });
          panel.dialog.close();
          await changed(day);
        },
        "新增安排",
      ),
    );
  }

  async function editDialog(
    slot,
    changed,
    targetDay = slot.day,
    autoPreview = false,
  ) {
    const panel = UI.panel("预览安排调整");
    const result = element("div", "calendar-preview");
    result.setAttribute("aria-live", "polite");
    let pending;
    let valid = false;
    let revision = 0;
    const apply = UI.button(
      "确认修改",
      async () => {
        if (!valid || !pending) return;
        const saved = await api("/api/calendar/move", "POST", {
          ...pending,
          confirm: true,
        });
        panel.dialog.close();
        await changed(saved.saved.day);
      },
      "primary",
    );
    apply.disabled = true;
    const preview = async (values) => {
      const ticket = ++revision;
      valid = false;
      apply.disabled = true;
      pending = {
        ...values,
        id: slot.id,
        expected_fingerprint: slot.fingerprint,
        task_id: values.task_id ? Number(values.task_id) : null,
      };
      const data = await api("/api/calendar/move", "POST", pending);
      if (ticket !== revision || !panel.dialog.isConnected) return;
      result.replaceChildren();
      note(result, slotLabel(data.candidate));
      renderIssues(result, data.issues);
      valid = data.can_apply;
      apply.disabled = !valid;
      if (valid) note(result, "时间与当天容量检查通过，确认后才会保存。");
      if (data.suggestions.length) {
        const section = UI.section(result, "可用时间建议");
        for (const suggestion of data.suggestions) {
          section.append(
            UI.button(
              `${minuteText(suggestion.start_minute)}–${minuteText(suggestion.end_minute)}`,
              async () => {
                form.elements.start_time.value = minuteText(
                  suggestion.start_minute,
                );
                form.elements.end_time.value = minuteText(
                  suggestion.end_minute,
                );
                await preview(Object.fromEntries(new FormData(form)));
              },
            ),
          );
        }
      }
    };
    const form = UI.form(
      [
        { name: "title", label: "安排名称", value: slot.title, maxLength: 200 },
        { name: "day", label: "安排日期", type: "date", value: targetDay },
        {
          name: "start_time",
          label: "开始 HH:MM",
          value: minuteText(slot.start_minute),
        },
        {
          name: "end_time",
          label: "结束 HH:MM",
          value: minuteText(slot.end_minute),
        },
        {
          name: "task_id",
          label: "关联任务编号",
          type: "number",
          min: 1,
          required: false,
          value: slot.task_id ?? "",
        },
        {
          name: "note",
          label: "说明",
          type: "textarea",
          required: false,
          value: slot.note,
          maxLength: 2000,
        },
      ],
      preview,
      "检查调整",
    );
    form.addEventListener("input", () => {
      revision++;
      valid = false;
      apply.disabled = true;
    });
    panel.body.append(form, result, apply);
    if (autoPreview) await preview(Object.fromEntries(new FormData(form)));
  }

  function renderIssues(root, issues) {
    for (const issue of issues) {
      note(root, issue.message, true);
      for (const item of issue.items || [])
        note(root, `冲突安排 #${item.id} ${item.title}`);
    }
  }

  function renderBatch(root, report) {
    root.replaceChildren();
    note(
      root,
      `来源 ${report.source_count} 项；可写入 ${report.accepted.length} 项；重复 ${report.duplicates.length} 项；冲突 ${report.conflicts.length} 项。`,
    );
    for (const error of report.errors || [])
      note(root, `事件 ${error.event}：${error.error}`, true);
    for (const warning of report.warnings || [])
      note(root, `事件 ${warning.event}：${warning.message}`);
    const accepted = UI.section(root, "待写入安排");
    for (const slot of report.accepted)
      note(
        accepted,
        `${slot.action === "update" ? "更新" : "新增"} ${slotLabel(slot)}`,
      );
    if (!report.accepted.length) note(accepted, "没有需要写入的安排。");
    if (report.duplicates.length) {
      const duplicates = UI.section(root, "跳过重复");
      for (const item of report.duplicates)
        note(
          duplicates,
          `${item.uid || item.title} → 已有 #${item.slot_id || item.existing_id} ${item.reason || "内容相同"}`,
        );
    }
    if (report.conflicts.length) {
      const conflicts = UI.section(root, "冲突详情");
      for (const item of report.conflicts) {
        note(conflicts, slotLabel(item.slot || item.event), true);
        renderIssues(conflicts, item.issues);
      }
    }
    if (report.capacity) {
      const capacity = UI.section(root, "目标周容量（写入前）");
      for (const day of report.capacity)
        note(
          capacity,
          `${day.day}：已安排 ${day.scheduled} / 可用 ${day.capacity} 分钟`,
        );
    }
  }

  function batchControls(panel, kind, changed) {
    const previewRoot = element("div", "calendar-preview");
    previewRoot.setAttribute("aria-live", "polite");
    let pending;
    let report;
    let revision = 0;
    const apply = UI.button(
      "确认写入预览中的安排",
      async () => {
        if (!report?.can_apply) return;
        const receipt = await api(`/api/calendar/${kind}/apply`, "POST", {
          ...pending,
          expected_signature: report.signature,
          confirm: true,
        });
        previewRoot.replaceChildren();
        receiptView(previewRoot, receipt);
        apply.disabled = true;
        report = null;
        await changed();
        toast("日历批次已完成，可在批次记录中查看");
      },
      "primary",
    );
    apply.disabled = true;
    const invalidate = () => {
      revision++;
      report = null;
      apply.disabled = true;
    };
    const preview = async (payload) => {
      invalidate();
      const ticket = revision;
      pending = payload;
      const fresh = await api(`/api/calendar/${kind}/preview`, "POST", payload);
      if (ticket !== revision || !panel.dialog.isConnected) return;
      report = fresh;
      renderBatch(previewRoot, fresh);
      apply.disabled = !fresh.can_apply;
      note(
        previewRoot,
        fresh.can_apply
          ? "预览已完成，确认后写入。跳过冲突时仅处理列表中可写入项。"
          : "当前有阻止写入的问题，请修改选项后重新预览。",
        !fresh.can_apply,
      );
    };
    return { previewRoot, apply, invalidate, preview };
  }

  function copyDialog(anchor, changed) {
    const panel = UI.panel("复制周计划");
    note(
      panel.body,
      "源周与目标周均按周一归一化。复制保留关联任务，已有相同时段会跳过。预览后源周、目标周或容量变化时需要重新预览。",
    );
    const controls = batchControls(panel, "copy", changed);
    const form = UI.form(
      [
        {
          name: "source_week",
          label: "源周内任意日期",
          type: "date",
          value: anchor,
        },
        {
          name: "target_week",
          label: "目标周内任意日期",
          type: "date",
          value: dateOffset(anchor, 7),
        },
        {
          name: "skip_conflicts",
          label: "发生冲突",
          options: [
            ["false", "整批停止"],
            ["true", "明确跳过冲突项"],
          ],
        },
      ],
      (values) =>
        controls.preview({
          ...values,
          skip_conflicts: values.skip_conflicts === "true",
          request_id: crypto.randomUUID(),
        }),
      "预览复制",
    );
    form.addEventListener("input", controls.invalidate);
    panel.body.append(form, controls.previewRoot, controls.apply);
  }

  function importDialog(changed) {
    const panel = UI.panel("导入 ICS 日历");
    note(
      panel.body,
      "支持独立分钟级事件；UTC、浮动本地时间和本机可识别的 TZID。全天事件会跳过，重复规则需先在源日历展开。相同来源名称与 UID 用于识别更新，人工修改过的本地安排会受到保护。",
    );
    const controls = batchControls(panel, "import", changed);
    const fields = element("div", "calendar-toolbar");
    const origin = control(fields, "来源日历名称", "text", "我的日历");
    origin.maxLength = 60;
    const file = control(fields, "选择 ICS 文件（40 KB 内）", "file");
    file.accept = ".ics,text/calendar";
    const skip = control(fields, "冲突处理", "select");
    skip.add(new Option("整批停止", "false"));
    skip.add(new Option("明确跳过冲突项", "true"));
    for (const input of [origin, file, skip])
      input.addEventListener("change", controls.invalidate);
    origin.addEventListener("input", controls.invalidate);
    const preview = UI.button("读取文件并预览", async () => {
      const selected = file.files[0];
      if (!selected) throw new Error("请先选择 ICS 文件");
      if (selected.size > 40000)
        throw new Error(
          "此界面单次支持 40 KB 内的日历文件，请按日期范围分批导出",
        );
      const content = await selected.text();
      const payload = {
        origin: origin.value.trim(),
        ics: content,
        skip_conflicts: skip.value === "true",
        request_id: crypto.randomUUID(),
      };
      if (new TextEncoder().encode(JSON.stringify(payload)).length > 64000)
        throw new Error("日历内容编码后过大，请减少事件数");
      await controls.preview(payload);
    });
    panel.body.append(fields, preview, controls.previewRoot, controls.apply);
  }

  function exportDialog(options) {
    const panel = UI.panel("导出当前日历");
    note(
      panel.body,
      "导出沿用当前周/月与项目、搜索筛选。截止任务以透明全天事件表示；导入时会跳过全天事件。ICS 用于交换安排，完整数据迁移请使用数据迁移模块。",
    );
    const form = UI.form(
      [
        {
          name: "include_due",
          label: "任务截止日期",
          options: [
            ["false", "仅导出时段"],
            ["true", "同时导出截止日期"],
          ],
        },
      ],
      async (values) => {
        const result = await api("/api/calendar/export", "POST", {
          ...options,
          include_due: values.include_due === "true",
        });
        download(result.filename, result.ics, "text/calendar;charset=utf-8");
        note(
          panel.body,
          `已导出 ${result.slots} 个时段、${result.deadlines} 个截止日期。`,
        );
      },
      "下载 ICS 文件",
    );
    panel.body.append(form);
  }

  function settingsDialog(settings, reload) {
    const panel = UI.panel("日历偏好");
    note(
      panel.body,
      "工作时间范围用于生成空闲时间建议；当天容量在日期详情中单独设置。更改偏好不会移动已有安排。",
    );
    panel.body.append(
      UI.form(
        [
          {
            name: "start_hour",
            label: "工作开始小时",
            type: "number",
            min: 0,
            max: 23,
            value: settings.start_hour,
          },
          {
            name: "end_hour",
            label: "工作结束小时",
            type: "number",
            min: 1,
            max: 24,
            value: settings.end_hour,
          },
          {
            name: "week_start",
            label: "每周第一天",
            options: [
              ["0", "周一"],
              ["6", "周日"],
            ],
            value: settings.week_start,
          },
          {
            name: "show_due",
            label: "显示截止任务",
            options: [
              ["true", "显示"],
              ["false", "隐藏"],
            ],
            value: String(settings.show_due),
          },
        ],
        async (values) => {
          await api("/api/calendar/settings", "POST", {
            start_hour: Number(values.start_hour),
            end_hour: Number(values.end_hour),
            week_start: Number(values.week_start),
            show_due: values.show_due === "true",
          });
          panel.dialog.close();
          await reload();
        },
        "保存偏好",
      ),
    );
  }

  function receiptView(root, receipt) {
    note(root, `批次 ${receipt.request_id} · ${receipt.created_at}`);
    note(
      root,
      `新增 ${receipt.created_count || 0} 项，更新 ${receipt.updated_count || 0} 项，重复 ${receipt.duplicates || 0} 项，跳过冲突 ${receipt.skipped_conflicts || 0} 项。`,
    );
    if (receipt.origin) note(root, `来源：${receipt.origin}`);
    if (receipt.source_week)
      note(root, `${receipt.source_week} → ${receipt.target_week}`);
    for (const warning of receipt.warnings || []) note(root, warning.message);
    root.append(
      UI.button("下载批次回执", () =>
        download(
          `calendar-${receipt.request_id}.json`,
          JSON.stringify(receipt, null, 2),
          "application/json;charset=utf-8",
        ),
      ),
    );
  }

  async function historyDialog() {
    const panel = UI.panel("日历批次记录");
    const entries = await api("/api/calendar/history");
    if (!entries.length) note(panel.body, "尚无周计划复制或日历导入记录。");
    for (const entry of entries) {
      const section = UI.section(
        panel.body,
        entry.kind === "ics_import" ? "日历导入" : "周计划复制",
      );
      receiptView(section, entry.report);
    }
  }

  Workspace.register(
    "calendar",
    "日历排程",
    "周/月视图、冲突预览、周计划复制与 ICS 日历交换",
    openCalendar,
  );
})();
