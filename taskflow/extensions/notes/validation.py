from ...validation import object_fields, text, integer, flag


def validate(payload, existing=None):
    object_fields(
        payload,
        ("title", "body", "category", "task_id", "archived", "expected_version"),
    )
    values = {**(existing or {}), **payload}
    task_id = values.get("task_id")
    if task_id is not None:
        integer(task_id, "关联任务编号", 1, 2147483647)
    return {
        "title": text(values.get("title", ""), "笔记标题", 200, True),
        "body": text(values.get("body", ""), "笔记内容", 20000),
        "category": text(values.get("category", "默认"), "笔记分类", 40, True),
        "task_id": task_id,
        "archived": flag(
            (
                bool(values.get("archived", False))
                if "archived" not in payload
                else payload["archived"]
            ),
            "归档状态",
        ),
    }
