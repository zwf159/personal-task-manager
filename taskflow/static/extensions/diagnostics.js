"use strict";
Workspace.register(
  "diagnostics",
  "数据健康",
  "检查数据库完整性、失效前置关系、长期停滞和遗留专注。",
  async () => {
    const panel = UI.panel("数据健康检查");
    panel.dialog.classList.add("diagnostics-panel");
    let current = null;
    function report(root, value) {
      const card = element(
        "article",
        `extension-card diagnostic-report ${value.status}`,
      );
      card.append(
        element(
          "h3",
          "",
          value.status === "ok"
            ? "检查正常"
            : `发现 ${value.errors} 项错误、${value.warnings} 项待关注`,
        ),
        element("p", "", new Date(value.created_at).toLocaleString()),
      );
      for (const check of value.checks) {
        const section = UI.section(card, `${check.name} · ${check.count} 项`);
        section.classList.add(`check-${check.level}`);
        for (const sample of check.samples)
          UI.line(
            section,
            typeof sample === "string" ? sample : JSON.stringify(sample),
          );
      }
      const inventory = UI.section(card, "数据数量");
      for (const [name, count] of Object.entries(value.inventory))
        UI.line(inventory, `${name}: ${count}`);
      root.append(card);
    }
    async function load() {
      const history = await api("/api/diagnostics");
      if (!panel.dialog.isConnected) return;
      panel.body.replaceChildren(
        element(
          "p",
          "diagnostic-help",
          "检查只读取业务数据并保存报告，不自动删除、修复或移动任务。发现前置约束问题时，请打开相关任务处理。",
        ),
      );
      panel.body.append(
        UI.form(
          [
            {
              name: "stale_days",
              label: "多少天未更新算停滞",
              type: "number",
              min: 1,
              max: 3650,
              value: 30,
            },
          ],
          async (d) => {
            current = await api("/api/diagnostics", "POST", {
              stale_days: Number(d.stale_days),
              include_details: true,
            });
            await load();
          },
          "运行数据检查",
        ),
      );
      if (current) report(panel.body, current);
      const old = UI.section(panel.body, "最近检查记录");
      for (const item of history.slice(0, 20))
        UI.line(
          old,
          `${new Date(item.created_at).toLocaleString()} · ${item.status}`,
          [
            UI.button("查看报告", async () => {
              current = await api(`/api/diagnostics/${item.id}`);
              await load();
            }),
          ],
        );
    }
    await load();
  },
);
