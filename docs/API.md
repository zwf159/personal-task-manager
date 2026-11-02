# API 协议

默认地址 `http://127.0.0.1:8765`。除 CSV 外返回 JSON；失败格式 `{"error":"说明"}`。

写入需 `Content-Type: application/json` 与 `X-Taskflow-Request: 1`；Origin（若存在）及 Host 必须匹配本机地址。无 CORS。JSON 对象请求体最多 64 KB。资源 ID 支持 1–2147483647。

JSON 数据包迁移与日历 API 的请求示例、指纹确认流程和边界见 [迁移与日历手册](TRANSFER_CALENDAR.md)。

创建型 POST 返回 201，其余成功 200；校验失败 400、来源拒绝 403、资源不存在 404、编辑或计时冲突 409、内部异常 500。

## 基础任务

| 方法 | 路径 | 请求与说明 |
| --- | --- | --- |
| GET/POST | /api/tasks | 列表或创建 |
| GET/PATCH/DELETE | /api/tasks/{id} | 详情、部分更新、移入回收站 |
| GET | /api/search | 分页：items、total、limit、offset |
| GET | /api/trash | 回收站列表 |
| POST | /api/tasks/{id}/restore | 空对象，恢复 |
| POST | /api/tasks/{id}/duplicate | 可选 title；复制计划与清单标签 |
| POST | /api/tasks/bulk | ids、action、value；最多 100 项，全部成功或全部回滚 |

创建例：`{"title":"完成阅读","notes":"记录收获","project_id":null,"status":"todo","priority":"medium","due_date":"2026-11-03"}`。

title 必填 1–200 字；notes 最多 5000 字。status 为 todo/doing/done，priority 为 low/medium/high。due_date 为真实 YYYY-MM-DD 或 null。project_id 为已有项目 ID 或 null。

PATCH 未指定字段保留，不能覆盖 ID 和创建时间。可附 expected_version，过期返回 409。响应包含 version、UTC created_at/updated_at 和扩展计划字段。

列表、分页、导出支持 q、status、priority、project_id、view（all/today/overdue）、sort（due/newest/oldest/title/updated）。Unicode 大小写归一化，百分号与下划线按字面量。分页增加 limit（1–100，默认 25）、offset（默认 0）；/api/tasks 为首版不分页兼容接口。

批量例：`{"ids":[1,2],"action":"status","value":"done"}`。action 支持 status、project、delete；project 的 value 可为项目 ID 或 null。

## 项目、标签、筛选

| 方法 | 路径 | 请求 |
| --- | --- | --- |
| GET/POST | /api/projects | 创建：name、可选 description 和 archived |
| PATCH/DELETE | /api/projects/{id} | 更新元数据或删除分组；保留任务 |
| GET/POST | /api/labels | 创建：name、可选六位十六进制 color |
| DELETE | /api/labels/{id} | 移除标签及关联 |
| GET/POST | /api/tasks/{id}/labels | 原子赋值：label_ids 数组，最多 30 项 |
| GET/POST | /api/views | 创建：name、filters 对象 |
| DELETE | /api/views/{id} | 删除常用筛选 |

项目名称 1–60 字且唯一，说明最多 2000 字；标签名称 1–40 字且唯一；筛选名称 1–60 字且唯一，filters 只接受搜索字段，不接受分页参数。

## 任务关联资源

| 方法 | 路径 | 请求 |
| --- | --- | --- |
| GET/POST | /api/tasks/{id}/checklist | 创建：title |
| PATCH/DELETE | /api/tasks/{id}/checklist/{item} | 更新：title、done 布尔、position 非负整数 |
| GET/POST | /api/tasks/{id}/comments | 创建：body，1–5000 字 |
| PATCH/DELETE | /api/tasks/{id}/comments/{item} | 编辑 body 或删除，保留创建时间 |
| GET/POST | /api/tasks/{id}/links | 创建：url、可选 title，仅 HTTP/HTTPS，无内嵌凭据 |
| DELETE | /api/tasks/{id}/links/{item} | 移除链接 |
| GET | /api/activity | 全局任务活动 |
| GET | /api/tasks/{id}/activity | 单任务活动，允许查看已删除任务历史 |

关联资源的编辑和删除会检查所属任务。活动按 ID 倒序，支持 limit（1–200，默认 100）和 before 游标。资料链接不由服务器抓取。

## 执行与统计

| 方法 | 路径 | 请求 |
| --- | --- | --- |
| GET/POST | /api/tasks/{id}/dependencies | 创建：depends_on |
| DELETE | /api/tasks/{id}/dependencies/{other} | 解除依赖 |
| PATCH | /api/tasks/{id}/estimate | minutes，0–525600 |
| GET/POST | /api/tasks/{id}/time | 创建：minutes（1–1440）、可选 day 与 note |
| DELETE | /api/tasks/{id}/time/{entry} | 移除工时 |
| POST | /api/tasks/{id}/recurrence | days（0–3650），0 关闭 |
| GET/POST | /api/focus | 创建：task_id、可选 minutes（1–180，默认 25） |
| POST | /api/focus/{id}/stop | 空对象，重复停止幂等 |
| GET | /api/reminders | 最多 100 条已到期、未关闭的未完成任务提醒 |
| GET/POST | /api/tasks/{id}/reminders | 创建：remind_at，含时区 ISO 日期时间 |
| PATCH | /api/reminders/{id} | action 为 dismiss/snooze，可选 minutes（1–10080） |
| GET | /api/stats | days（1–90，默认 7），总量、每日趋势、项目进度 |

依赖不允许环；未完成的前置任务即使删除也仍阻止后续完成。专注计时最多记录计划时长，不足一分钟不入工时。周期任务与本次完成在一个事务中生成且不重复。统计按服务器本地日期，同任务同天完成只计一次。

## 数据管理

| 方法 | 路径 | 请求 |
| --- | --- | --- |
| GET | /api/export.csv | 当前筛选结果，UTF-8 BOM，公式前缀转义 |
| POST | /api/import/csv/preview | csv 文本；返回 rows、valid、skipped、errors |
| POST | /api/import/csv | csv、confirm:true，重新解析并事务写入 |
| GET/POST | /api/backups | 列举或创建一致性备份 |
| POST | /api/backups/restore | name、sha256、confirm:true |
| GET/POST | /api/templates | 创建：task_id、可选 name |
| POST | /api/templates/{id}/apply | 可选 project_id |
| DELETE | /api/templates/{id} | 删除模板，不影响已有任务 |

CSV 必须包含“任务”列，最多 500 行、50,000 字符；任何错误会阻止整批写入。备份仅解析目录内 UUID 名称，拒绝路径穿越和符号链接，校验指纹、结构、完整性与外键，恢复前保存安全备份。模板是独立快照，保留名称、备注、优先级、预估、清单，不复制既往工时和进展。
