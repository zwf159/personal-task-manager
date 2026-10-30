# HTTP 接口

默认地址：`http://127.0.0.1:8765`。成功响应使用 JSON；错误格式为 `{"error":"说明"}`。CSV 除外。

写入请求需包含 `Content-Type: application/json` 与 `X-Taskflow-Request: 1`。若包含 Origin，必须与本机服务地址匹配。不启用 CORS。JSON 请求体最多 64 KB。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 创建任务，返回 201 |
| PATCH | `/api/tasks/{id}` | 部分更新任务 |
| DELETE | `/api/tasks/{id}` | 删除任务 |
| GET | `/api/projects` | 项目与任务数量 |
| POST | `/api/projects` | 创建项目，返回 201 |
| DELETE | `/api/projects/{id}` | 删除分组并保留任务 |
| GET | `/api/export.csv` | 导出筛选后的任务 |

## 任务字段

```json
{
  "title": "完成本周阅读",
  "notes": "记录三条收获",
  "project_id": null,
  "status": "todo",
  "priority": "medium",
  "due_date": "2026-11-03"
}
```

- `title`：必填文本，去除首尾空白后 1–200 字。
- `notes`：最多 5000 字，默认空文本。
- `project_id`：已有项目的正整数 ID，或 null。
- `status`：`todo`、`doing`、`done`，默认 todo。
- `priority`：`low`、`medium`、`high`，默认 medium。
- `due_date`：YYYY-MM-DD 或 null，必须是真实存在的日期。
- 响应另含 `id`、UTC ISO 格式的 `created_at` 和 `updated_at`；列表还包含 `project_name`。
- PATCH 未指定的字段保留原值。ID 和创建时间不接受客户端覆盖。

任务列表与导出支持 `q`、`status`、`priority`、`project_id`、`view=today|overdue` 查询参数。搜索匹配名称或备注，百分号与下划线按字面量处理。排序为未完成在先、有日期在先、日期升序、优先级高到低、ID 倒序。

项目创建请求为 `{"name":"学习"}`，名称 1–60 字且不可重名。

## 状态码

- 200：读取、更新、删除成功。
- 201：创建成功。
- 400：字段或 JSON 格式无效。
- 403：Host、Origin 或写入请求头校验失败。
- 404：资源或接口不存在。
- 500：服务器异常，响应不暴露内部路径或数据库细节。

本服务用于本机单人使用，无身份认证、分页或批量操作协议。
