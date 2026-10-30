"use strict";
Workspace.register(
  "rules",
  "规则批处理",
  "保存筛选与操作，先预览再手动执行，不在后台自动改任务。",
  async () => {
    const panel = UI.panel("规则批处理");
    panel.dialog.classList.add("rules-panel");
    async function preview(rule) {
      const result = await api(`/api/rules/${rule.id}/run`, "POST", {
        preview: true,
      });
      const view = UI.panel("规则预览");
      view.body.append(
        element(
          "p",
          "rule-summary",
          `匹配 ${result.matched} 项，将修改 ${result.would_update} 项。执行时会重新匹配。`,
        ),
      );
      for (const task of result.tasks)
        UI.line(view.body, `#${task.id} ${task.title}`);
      view.body.append(
        UI.button("确认执行规则", async () => {
          const applied = await api(`/api/rules/${rule.id}/run`, "POST", {
            preview: false,
          });
          await Workspace.changed();
          view.dialog.close();
          await load();
          toast(`已修改 ${applied.updated} 项任务`);
        }),
      );
    }
    async function load() {
      const rules = await api("/api/rules");
      if (!panel.dialog.isConnected) return;
      panel.body.replaceChildren(
        element(
          "p",
          "rule-help",
          "目标值：状态填 todo/doing/done，优先级填 low/medium/high，项目填编号（空值表示未分组）。单次最多匹配 100 项。",
        ),
      );
      panel.body.append(
        UI.form(
          [
            { name: "name", label: "规则名称", maxLength: 100 },
            { name: "q", label: "任务关键词", required: false, maxLength: 200 },
            {
              name: "status",
              label: "筛选状态",
              required: false,
              options: [
                ["", "所有状态"],
                ...["todo", "doing", "done"].map((v) => [v, labels[v]]),
              ],
            },
            {
              name: "action",
              label: "操作类型",
              options: [
                ["priority", "设置优先级"],
                ["status", "设置状态"],
                ["project", "移动项目"],
              ],
            },
            { name: "value", label: "目标值", required: false, value: "high" },
          ],
          async (d) => {
            const filters = {};
            if (d.q) filters.q = d.q;
            if (d.status) filters.status = d.status;
            await api("/api/rules", "POST", {
              name: d.name,
              filters,
              action: d.action,
              value:
                d.action === "project"
                  ? d.value
                    ? Number(d.value)
                    : null
                  : d.value,
            });
            await load();
          },
          "保存规则",
        ),
      );
      for (const rule of rules) {
        const card = element("article", "extension-card rule-card");
        card.append(
          element("h3", "", rule.name + (rule.enabled ? "" : "（停用）")),
          element(
            "p",
            "",
            `${rule.action} → ${rule.value === null ? "未分组" : rule.value} · 关键词 ${rule.filters.q || "不限"}`,
          ),
        );
        const actions = element("div", "action-strip");
        actions.append(
          UI.button("预览匹配", () => preview(rule)),
          UI.button(rule.enabled ? "停用规则" : "启用规则", async () => {
            await api(`/api/rules/${rule.id}`, "PATCH", {
              enabled: !rule.enabled,
              expected_version: rule.version,
            });
            await load();
          }),
          UI.button("执行记录", async () => {
            const view = UI.panel("规则执行记录");
            for (const r of await api(`/api/rules/${rule.id}/runs`))
              UI.line(
                view.body,
                `${new Date(r.created_at).toLocaleString()} · ${r.preview ? "预览" : "执行"} · 匹配 ${r.matched} · 修改 ${r.updated}`,
              );
          }),
        );
        card.append(actions);
        panel.body.append(card);
      }
    }
    await load();
  },
);
