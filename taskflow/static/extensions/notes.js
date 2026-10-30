"use strict";
Workspace.register(
  "notes",
  "工作笔记",
  "记录独立笔记，关联任务，并保留可恢复的编辑版本。",
  async () => {
    const panel = UI.panel("工作笔记");
    panel.dialog.classList.add("notes-panel");
    let q = "",
      archived = false;
    function edit(note) {
      const editor = UI.panel(note ? "编辑笔记" : "新建笔记");
      editor.dialog.classList.add("notes-panel");
      editor.body.append(
        UI.form(
          [
            {
              name: "title",
              label: "笔记标题",
              value: note?.title || "",
              maxLength: 200,
            },
            {
              name: "category",
              label: "分类",
              value: note?.category || "默认",
              maxLength: 40,
            },
            {
              name: "task_id",
              label: "关联任务编号（可选）",
              type: "number",
              min: 1,
              required: false,
              value: note?.task_id || "",
            },
            {
              name: "body",
              label: "笔记正文",
              type: "textarea",
              required: false,
              value: note?.body || "",
              maxLength: 20000,
            },
          ],
          async (d) => {
            await api(
              note ? `/api/notes/${note.id}` : "/api/notes",
              note ? "PATCH" : "POST",
              {
                ...d,
                task_id: d.task_id ? Number(d.task_id) : null,
                ...(note ? { expected_version: note.version } : {}),
              },
            );
            editor.dialog.close();
            await load();
          },
          "保存笔记",
        ),
      );
    }
    async function history(note) {
      const view = UI.panel("笔记历史版本");
      const revisions = await api(`/api/notes/${note.id}/revisions`);
      for (const revision of revisions)
        UI.line(
          view.body,
          `版本 ${revision.version} · ${revision.title} · ${new Date(revision.created_at).toLocaleString()}`,
          [
            UI.button("恢复正文", () =>
              UI.confirm(
                "恢复笔记正文",
                "会创建一个新版本，保留当前内容的历史。",
                async () => {
                  await api(`/api/notes/${note.id}/restore`, "POST", {
                    revision: revision.version,
                    expected_version: note.version,
                  });
                  view.dialog.close();
                  await load();
                },
              ),
            ),
          ],
        );
    }
    async function load() {
      const notes = await api(
        `/api/notes?${new URLSearchParams({ q, archived: archived ? "1" : "0" })}`,
      );
      if (!panel.dialog.isConnected) return;
      panel.body.replaceChildren(
        UI.button("新建笔记", () => edit()),
        UI.button(archived ? "查看使用中" : "查看已归档", async () => {
          archived = !archived;
          await load();
        }),
      );
      panel.body.append(
        UI.form(
          [
            {
              name: "q",
              label: "搜索标题或正文",
              required: false,
              value: q,
              maxLength: 200,
            },
          ],
          async (d) => {
            q = d.q;
            await load();
          },
          "搜索笔记",
        ),
      );
      for (const note of notes) {
        const card = element("article", "extension-card note-card");
        card.append(
          element("h3", "", note.title),
          element(
            "p",
            "note-category",
            `${note.category} · 版本 ${note.version}${note.task_id ? " · 任务 #" + note.task_id : ""}`,
          ),
          element("p", "workspace-body", note.body.slice(0, 500)),
        );
        const actions = element("div", "action-strip");
        actions.append(
          UI.button("查看与编辑", () => edit(note)),
          UI.button("历史版本", () => history(note)),
          UI.button(archived ? "恢复笔记" : "归档笔记", async () => {
            await api(`/api/notes/${note.id}`, "PATCH", {
              archived: !archived,
              expected_version: note.version,
            });
            await load();
          }),
        );
        card.append(actions);
        panel.body.append(card);
      }
      if (!notes.length)
        panel.body.append(
          element(
            "p",
            "workspace-empty",
            "没有匹配笔记。每次展示最近 200 条，正文按纯文本显示。",
          ),
        );
    }
    await load();
  },
);
