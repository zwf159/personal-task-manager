"use strict";

const PortableBrowser = {
  references: {
    tasks: { project_id: "projects" },
    task_labels: { task_id: "tasks", label_id: "labels" },
    checklist_items: { task_id: "tasks" },
    comments: { task_id: "tasks" },
    time_entries: { task_id: "tasks" },
    task_links: { task_id: "tasks" },
    dependencies: { task_id: "tasks", depends_on: "tasks" },
    goal_tasks: { goal_id: "goals", task_id: "tasks" },
    habit_logs: { habit_id: "habits" },
    notes: { task_id: "tasks" },
    note_revisions: { note_id: "notes" },
    captures: { task_id: "tasks" },
    reminders: { task_id: "tasks" },
  },

  mount(root, document, names) {
    const entities = document.entities;
    const section = element("section", "portable-inspector");
    const toolbar = element("div", "portable-inspector-toolbar");
    const selector = element("select");
    const search = element("input");
    const sort = element("select");
    const direction = element("button", "secondary", "升序");
    const columnPicker = element("div", "portable-columns");
    const count = element("p", "portable-row-count");
    const tableWrap = element("div", "portable-grid-scroll");
    const pager = element("div", "action-strip");
    const details = element("div", "portable-record-detail");
    const breadcrumb = element("p", "portable-breadcrumb");
    const selected = {
      entity:
        Object.keys(entities).find((key) => entities[key].length) ||
        Object.keys(entities)[0],
      query: "",
      sort: "",
      descending: false,
      page: 0,
      size: 25,
      columns: [],
      relation: null,
    };
    const heading = element("h3", "", "数据包记录浏览器");
    section.append(heading);
    section.append(
      element(
        "p",
        "portable-help",
        "这里查看的是文件中的源记录，只在浏览器中筛选和排序，不会修改数据包或现有工作空间。",
      ),
    );
    selector.setAttribute("aria-label", "浏览记录类型");
    search.setAttribute("aria-label", "搜索数据包记录");
    search.placeholder = "在此类记录中搜索";
    search.maxLength = 200;
    sort.setAttribute("aria-label", "记录排序字段");
    direction.type = "button";
    for (const key of Object.keys(entities)) {
      selector.add(
        new Option(`${names[key] || key} · ${entities[key].length}`, key),
      );
    }
    selector.value = selected.entity;
    toolbar.append(selector, search, sort, direction);
    section.append(
      toolbar,
      breadcrumb,
      columnPicker,
      count,
      tableWrap,
      pager,
      details,
    );
    root.append(section);
    let searchTimer;

    function scalar(value) {
      if (value === null || value === undefined) return "";
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
    }

    function fields() {
      const rows = entities[selected.entity] || [];
      return [...new Set(rows.flatMap((row) => Object.keys(row)))];
    }

    function label(value) {
      return names[value] || value;
    }

    function rows() {
      const query = selected.query.trim().toLocaleLowerCase();
      const source = entities[selected.entity] || [];
      const filtered = source
        .map((row, index) => ({ row, index }))
        .filter((item) => {
          if (
            selected.relation &&
            scalar(item.row[selected.relation.field]) !==
              scalar(selected.relation.value)
          )
            return false;
          if (!query) return true;
          return Object.values(item.row).some((value) =>
            scalar(value).toLocaleLowerCase().includes(query),
          );
        });
      filtered.sort((a, b) => {
        const left = a.row[selected.sort];
        const right = b.row[selected.sort];
        let result;
        if (typeof left === "number" && typeof right === "number")
          result = left - right;
        else
          result = scalar(left).localeCompare(scalar(right), "zh-CN", {
            numeric: true,
          });
        if (!result) result = a.index - b.index;
        return selected.descending ? -result : result;
      });
      return filtered;
    }

    function makeCell(tag, value) {
      const cell = element(tag);
      const text = scalar(value);
      cell.textContent =
        text.length > 90 ? text.slice(0, 90) + "…" : text || "—";
      cell.title = text.slice(0, 1000);
      return cell;
    }

    function chooseColumns() {
      const available = fields();
      selected.columns = available.slice(0, 5);
      selected.sort = available[0] || "";
      sort.replaceChildren(
        ...available.map((field) => new Option(field, field)),
      );
      columnPicker.replaceChildren(element("span", "", "显示字段："));
      for (const field of available) {
        const wrapper = element("label", "checkbox-label");
        const checkbox = element("input");
        checkbox.type = "checkbox";
        checkbox.checked = selected.columns.includes(field);
        checkbox.setAttribute("aria-label", `显示字段 ${field}`);
        checkbox.onchange = () => {
          if (checkbox.checked && selected.columns.length >= 6) {
            checkbox.checked = false;
            toast("最多同时显示 6 个字段。");
            return;
          }
          if (!checkbox.checked && selected.columns.length === 1) {
            checkbox.checked = true;
            toast("至少保留一个字段。");
            return;
          }
          selected.columns = checkbox.checked
            ? [...selected.columns, field]
            : selected.columns.filter((value) => value !== field);
          renderTable();
        };
        wrapper.append(checkbox, documentOwner().createTextNode(field));
        columnPicker.append(wrapper);
      }
    }

    function documentOwner() {
      return root.ownerDocument;
    }

    function switchEntity(name, relation = null) {
      selected.entity = name;
      selected.query = "";
      selected.page = 0;
      selected.relation = relation;
      search.value = "";
      selector.value = name;
      details.replaceChildren();
      chooseColumns();
      renderTable();
    }

    function showRecord(item) {
      details.replaceChildren();
      details.append(
        element(
          "h4",
          "",
          `${label(selected.entity)} · 文件中的第 ${item.index + 1} 条`,
        ),
      );
      const definition = element("dl", "portable-definition");
      for (const [field, value] of Object.entries(item.row)) {
        definition.append(element("dt", "", field));
        const description = element("dd", "", scalar(value) || "—");
        definition.append(description);
        const target = PortableBrowser.references[selected.entity]?.[field];
        if (!target || value === null) continue;
        const reference = entities[target]?.find((row) => row.id === value);
        if (!reference) {
          description.append(
            element("p", "portable-warning", `数据包缺少 ${target} #${value}`),
          );
          continue;
        }
        description.append(
          UI.button(`查看 ${label(target)} #${value}`, () => {
            switchEntity(target, { field: "id", value });
            const found = rows()[0];
            if (found) showRecord(found);
          }),
        );
      }
      details.append(definition);
      if (item.row.id === undefined) return;
      const related = element("div", "action-strip");
      for (const [child, references] of Object.entries(
        PortableBrowser.references,
      )) {
        for (const [field, target] of Object.entries(references)) {
          if (target !== selected.entity) continue;
          const quantity = (entities[child] || []).filter(
            (row) => row[field] === item.row.id,
          ).length;
          if (!quantity) continue;
          related.append(
            UI.button(`${label(child)} · ${field} · ${quantity} 条`, () =>
              switchEntity(child, { field, value: item.row.id }),
            ),
          );
        }
      }
      details.append(related);
      details.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    function csvValue(value) {
      let text = scalar(value);
      if (/^[\s]*[=+\-@]/.test(text)) text = "'" + text;
      return '"' + text.replaceAll('"', '""') + '"';
    }

    function exportRows() {
      const current = rows();
      const columns = fields();
      const lines = [columns.map(csvValue).join(",")];
      for (const item of current)
        lines.push(columns.map((field) => csvValue(item.row[field])).join(","));
      const blob = new Blob(["\ufeff", lines.join("\r\n")], {
        type: "text/csv;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const anchor = element("a");
      anchor.href = url;
      anchor.download = `taskflow-package-${selected.entity}.csv`;
      documentOwner().body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function renderTable() {
      const current = rows();
      const pages = Math.max(1, Math.ceil(current.length / selected.size));
      selected.page = Math.min(selected.page, pages - 1);
      const start = selected.page * selected.size;
      const visible = current.slice(start, start + selected.size);
      count.textContent = `${label(selected.entity)}：匹配 ${current.length} 条，展示 ${visible.length} 条。`;
      breadcrumb.textContent = selected.relation
        ? `关联范围：${selected.relation.field} = ${selected.relation.value}`
        : "范围：此类全部源记录";
      const table = element("table", "portable-record-table");
      const head = element("thead");
      const header = element("tr");
      for (const field of selected.columns) {
        const cell = element("th", "", field);
        cell.scope = "col";
        header.append(cell);
      }
      header.append(element("th", "", "查看"));
      head.append(header);
      const body = element("tbody");
      for (const item of visible) {
        const row = element("tr");
        for (const field of selected.columns)
          row.append(makeCell("td", item.row[field]));
        const action = element("td");
        action.append(
          UI.button(`第 ${item.index + 1} 条`, () => showRecord(item)),
        );
        row.append(action);
        body.append(row);
      }
      table.append(head, body);
      tableWrap.replaceChildren(table);
      if (!visible.length)
        tableWrap.append(element("p", "workspace-empty", "没有匹配记录。"));
      const previous = UI.button("上一页", () => {
        selected.page--;
        renderTable();
      });
      const next = UI.button("下一页", () => {
        selected.page++;
        renderTable();
      });
      previous.disabled = selected.page === 0;
      next.disabled = selected.page >= pages - 1;
      pager.replaceChildren(
        previous,
        element("span", "", `${selected.page + 1}/${pages}`),
        next,
      );
      pager.append(UI.button("导出当前筛选 CSV", exportRows));
      if (selected.relation)
        pager.append(
          UI.button("清除关联范围", () => {
            selected.relation = null;
            selected.page = 0;
            renderTable();
          }),
        );
    }

    selector.onchange = () => switchEntity(selector.value);
    search.oninput = () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        selected.query = search.value;
        selected.page = 0;
        renderTable();
      }, 150);
    };
    sort.onchange = () => {
      selected.sort = sort.value;
      selected.page = 0;
      renderTable();
    };
    direction.onclick = () => {
      selected.descending = !selected.descending;
      direction.textContent = selected.descending ? "降序" : "升序";
      renderTable();
    };
    chooseColumns();
    renderTable();
    return {
      destroy() {
        clearTimeout(searchTimer);
        section.remove();
      },
    };
  },
};
