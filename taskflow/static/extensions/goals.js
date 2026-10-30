"use strict";
Workspace.register(
  "goals",
  "目标管理",
  "把长期目标关联到实际任务，按完成任务数计算进度。",
  async () => {
    const panel = UI.panel("目标管理");
    panel.dialog.classList.add("goals-panel");
    async function load() {
      const goals = await api("/api/goals");
      if (!panel.dialog.isConnected) return;
      panel.body.replaceChildren();
      panel.body.append(
        UI.form(
          [
            { name: "title", label: "目标名称", maxLength: 160 },
            {
              name: "target",
              label: "目标任务数",
              type: "number",
              min: 1,
              max: 10000,
              value: 3,
            },
            {
              name: "due_date",
              label: "目标日期",
              type: "date",
              required: false,
            },
          ],
          async (d) => {
            await api("/api/goals", "POST", { ...d, target: Number(d.target) });
            await load();
          },
          "创建目标",
        ),
      );
      for (const goal of goals) {
        const card = element("article", "extension-card goal-card");
        card.append(
          element("h3", "", goal.title + (goal.archived ? "（已归档）" : "")),
          element(
            "p",
            "workspace-metric",
            `${goal.completed}/${goal.target} 项 · ${goal.progress}% · ${goal.due_date || "无截止日期"}`,
          ),
        );
        const progress = element("progress");
        progress.max = 100;
        progress.value = goal.progress;
        progress.setAttribute("aria-label", goal.title + "进度");
        card.append(progress);
        for (const task of goal.tasks)
          UI.line(
            card,
            `#${task.id} ${task.title} · ${labels[task.status]}${task.deleted_at ? "（回收站）" : ""}`,
            [
              UI.button("解除关联", async () => {
                await api(`/api/goals/${goal.id}/tasks`, "POST", {
                  task_id: task.id,
                  attach: false,
                });
                await load();
              }),
            ],
          );
        card.append(
          UI.form(
            [
              {
                name: "task_id",
                label: "关联任务编号",
                type: "number",
                min: 1,
              },
            ],
            async (d) => {
              await api(`/api/goals/${goal.id}/tasks`, "POST", {
                task_id: Number(d.task_id),
              });
              await load();
            },
            "关联任务",
          ),
        );
        card.append(
          UI.button(goal.archived ? "恢复目标" : "归档目标", async () => {
            await api(`/api/goals/${goal.id}`, "PATCH", {
              archived: !goal.archived,
            });
            await load();
          }),
        );
        panel.body.append(card);
      }
      if (!goals.length)
        panel.body.append(
          element(
            "p",
            "workspace-empty",
            "创建目标后关联任务，进度随实际完成状态变化。",
          ),
        );
    }
    await load();
  },
);
