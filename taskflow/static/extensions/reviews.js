"use strict";
Workspace.register(
  "reviews",
  "每周复盘",
  "记录收获、阻碍与下一步，保存该周的任务和投入统计快照。",
  async () => {
    const panel = UI.panel("每周复盘");
    panel.dialog.classList.add("reviews-panel");
    async function load() {
      const reviews = await api("/api/reviews");
      if (!panel.dialog.isConnected) return;
      panel.body.replaceChildren();
      panel.body.append(
        UI.form(
          [
            {
              name: "week",
              label: "选择周内任一天",
              type: "date",
              value: localDate(),
            },
          ],
          async (d) => {
            await api("/api/reviews", "POST", d);
            await load();
          },
          "创建该周复盘",
        ),
      );
      for (const review of reviews) {
        const card = element("article", "extension-card review-card");
        card.append(
          element(
            "h3",
            "",
            `${review.week} 开始的一周${review.locked ? " · 已定稿" : ""}`,
          ),
        );
        const m = review.metrics;
        card.append(
          element(
            "p",
            "review-metrics",
            `新增任务 ${m.created_tasks} · 完成 ${m.completed_tasks} · 投入 ${m.work_minutes} 分钟 · 计划 ${m.planned_minutes} 分钟 · 习惯达标 ${m.habit_days} 次`,
          ),
        );
        if (review.locked) {
          for (const [key, title] of [
            ["wins", "本周收获"],
            ["blockers", "遇到的阻碍"],
            ["next_steps", "下周行动"],
          ])
            card.append(
              element("strong", "", title),
              element("p", "workspace-body", review[key] || "未填写"),
            );
        } else
          card.append(
            UI.form(
              [
                {
                  name: "wins",
                  label: "本周收获",
                  type: "textarea",
                  value: review.wins,
                  required: false,
                  maxLength: 5000,
                },
                {
                  name: "blockers",
                  label: "遇到的阻碍",
                  type: "textarea",
                  value: review.blockers,
                  required: false,
                  maxLength: 5000,
                },
                {
                  name: "next_steps",
                  label: "下周行动",
                  type: "textarea",
                  value: review.next_steps,
                  required: false,
                  maxLength: 5000,
                },
              ],
              async (d) => {
                await api(`/api/reviews/${review.id}`, "PATCH", {
                  ...d,
                  expected_version: review.version,
                });
                await load();
              },
              "保存复盘",
            ),
          );
        const actions = element("div", "action-strip");
        actions.append(
          UI.button(review.locked ? "解除定稿" : "定稿并冻结", async () => {
            await api(`/api/reviews/${review.id}`, "PATCH", {
              locked: !review.locked,
              expected_version: review.version,
            });
            await load();
          }),
        );
        if (!review.locked)
          actions.append(
            UI.button("重新计算统计", async () => {
              await api(`/api/reviews/${review.id}/refresh`, "POST", {
                expected_version: review.version,
              });
              await load();
            }),
          );
        card.append(actions);
        panel.body.append(card);
      }
    }
    await load();
  },
);
