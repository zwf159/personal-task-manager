# 数据迁移与日历排程

两项功能均从“个人工作台”打开。所有请求仍只访问本机 HTTP 服务，使用 API.md 中的请求头；请求体最多 64 KB。预览不会写入业务记录，迁移预览会保存临时会话状态。接口返回 JSON 对象。

## 导出和查看核心数据

在“数据迁移 → 导出数据”选择全部数据或指定项目，点击“生成导出预览”。查看摘要后可下载 JSON，并在记录浏览器中按类型、字段、搜索词查看源记录、引用关系或导出过滤后的 CSV。查看操作不修改原数据。

数据包格式标识为 `taskflow-portable`、版本 `1`；顶层包含 format、version、exported_at、entities。entities 包含 projects、labels、tasks、task_labels、checklist_items、comments、time_entries、task_links、dependencies、goals、goal_tasks、habits、habit_logs、notes、note_revisions、captures、reminders 共 17 类记录。

单包最多 10,000 条记录、5 MiB UTF-8 编码内容。回收站任务、专注会话、每日计划、复盘、规则、项目模板、备份及临时上传不包含在包中。导出任务不保留周期自动生成配置，防止迁移后意外重复生成。完整恢复仍需数据库备份。

指定项目时只包含该项目的活动任务与必要关联；独立笔记和习惯不进入项目包。跨范围关联会解除或省略，摘要给出提示；标签可能作为可复用字典保留。全量导出可选择是否包含归档知识记录。

## 分块导入与确认

1. 选择 JSON 文件，浏览器检查格式并计算 SHA-256。
2. 点击“上传并校验”，以 40,960 原始字节为一块上传；支持暂停后续传。恢复会话时必须重新选择相同指纹文件。
3. 服务端重新检查字节长度、整包指纹、重复 JSON 键、字段、日期、编号、外键、前置无环和笔记版本一致性。
4. 预览列出数量、名称冲突、任务状态和内容重复。项目同名时加前缀改名，标签同名复用；任务或笔记相同内容只提示，确认后会创建独立副本，避免自动去重破坏包内引用。
5. 确认后先创建当前库的保护备份，再在一个事务中导入并重建所有编号关联；任何校验或外键失败都会回滚。
6. 下载回执保存编号映射、源包指纹和安全备份指纹。可复核导入后记录与初始内容的变化，不自动覆盖后续编辑。

最多 5 个未完成会话。会话一小时后过期；创建新会话时清理过期会话及回执，完成后立即清除上传分块。已完成会话在有效期内重复确认返回原回执。项目/标签名称空间在预览后变化会要求重新预览，已有任务不会被导入覆盖。

| 方法 | 路径 | 请求/结果 |
| --- | --- | --- |
| POST | /api/portable/export | 可选 project_id、include_archived；返回 document、summary、bytes、warnings、excluded |
| POST | /api/portable/sessions | name、size、sha256、chunks；返回 token 与状态 |
| GET | /api/portable/sessions | 最近 30 个会话元数据 |
| GET | /api/portable/sessions/{token} | 会话状态、已上传分块、预览或回执 |
| POST | /api/portable/sessions/{token}/chunks | seq 从 0 开始、data 为 Base64；相同分块重试接受，不同内容拒绝 |
| POST | /api/portable/sessions/{token}/preview | 可选 prefix；返回 valid、errors、conflicts、content、duplicates、preview_token |
| POST | /api/portable/sessions/{token}/commit | confirm:true、preview_token；返回新旧编号映射、receipt、safety_backup 和 fingerprints |
| GET | /api/portable/sessions/{token}/verify | 已完成会话；统计未变化/修改/移除/回收 |
| DELETE | /api/portable/sessions/{token} | 取消未完成会话并清理分块；不删除导入后的记录 |

例如小包只有一块时，chunks 为 1；size 是原始文件字节数，不是 Base64 长度。token 为 32 位十六进制 UUID。包版本与字段字典定义见 `extensions/portable/catalog.py`；所有字段均由服务端校验，不接受任意 SQL 或表名。

## 日历安排

周视图显示连续 7 天；月视图包含相邻月份，共 42 天。基准日期、项目和搜索词可组合筛选。容量及已安排分钟始终按所有时段统计，筛选隐藏的安排会另行计数。任务截止日期显示为独立标记，不占用计划容量。

点击日期可新增时段或修改当天容量；点击时段编辑，或拖到另一日期。调整先显示时段、容量、关联任务问题和工作时间内的可用建议，明确确认后才写入。表单修改会使旧预览失效；另一窗口修改同一时段时拒绝过期指纹。

“复制周计划”将源周时段按星期偏移复制到目标周，两周都按周一归一化，复制保留关联任务。默认冲突阻止整批；明确选择“跳过冲突项”时只写入可接受项。相同内容、时间、任务和说明的已有安排跳过。预览后源周、目标周或容量变化必须重新预览。复制范围为整周，不受主日历筛选影响。

日历偏好配置每周第一天、空闲建议工作时间和截止任务显示。工作时间不是强制时段限制，不会移动已有安排；每日容量单独配置。键盘方向键移动日期焦点，Enter 打开当天详情。

## ICS 日历交换

导出遵循当前周/月、项目和搜索筛选。时段以 UTC DTSTART/DTEND 及稳定 UID 写出；文本换行、逗号、分号和反斜线转义，UTF-8 行按 75 字节折行。可选截止日期使用透明全天事件，显式勾选可覆盖日历的隐藏截止任务偏好。

导入界面单文件 40 KB，服务端最多 50,000 字符和 200 个事件，另受 64 KB JSON 请求体限制。支持 UTC、浮动服务器本地时间和本机 ZoneInfo 可识别的 TZID。TZID 不可识别、夏令时切换歧义、非整分钟、无结束时间或非正持续时长会报错。支持 DTEND 或 PTnHnM DURATION，不能同时提供。

全天和取消事件会提示并跳过；METHOD:CANCEL 不删除本地安排。RRULE/RDATE/EXDATE、跨日事件不支持，结束于次日 00:00 可作为当天 24:00。应先在源日历展开重复事件；不抓取 URL 或附件。

相同来源名称与 UID 识别后续更新。源内容未变化时保留本地安排；源内容变化但本地已被人工修改时报告冲突，避免覆盖。文件内 UID 重复或协议校验错误阻止整批，即使启用跳过冲突也不会忽略格式错误。预览后目标时段、容量或来源关联变化会拒绝写入。重复批次编号返回原回执，不重复创建；相同编号用于不同内容返回冲突。

| 方法 | 路径 | 请求/结果 |
| --- | --- | --- |
| GET | /api/calendar | anchor:YYYY-MM-DD、view:week/month，可选 project_id、q；返回 days、settings、total_slots、scheduled_minutes |
| GET/POST | /api/calendar/settings | POST：start_hour:0–23、end_hour:1–24、week_start:0–6（周一为 0）、show_due:boolean |
| POST | /api/calendar/move | id、expected_fingerprint，可选 day/title/note/task_id/start_time/end_time；默认预览，confirm:true 才保存 |
| POST | /api/calendar/copy/preview | source_week、target_week、request_id:UUID、可选 skip_conflicts:boolean；返回 accepted/duplicates/conflicts、signature、can_apply |
| POST | /api/calendar/copy/apply | 上述原参数、expected_signature、confirm:true |
| POST | /api/calendar/import/preview | origin、ics、request_id:UUID、可选 skip_conflicts；返回 errors/warnings、accepted/duplicates/conflicts、signature、can_apply |
| POST | /api/calendar/import/apply | 上述原参数、expected_signature、confirm:true |
| POST | /api/calendar/export | anchor、view，可选 project_id/q/include_due；返回 ics、filename、slots、deadlines |
| GET | /api/calendar/history | 最近 30 个周复制/ICS 导入批次及回执 |

时段创建、删除与日容量接口仍使用 `/api/planner`，见工作台手册。移动请求返回候选 candidate、issues、suggestions、fingerprint，确认成功另含 saved。日期与统计均以服务端本地时区为准，跨时区浏览器建议先核对日期。
