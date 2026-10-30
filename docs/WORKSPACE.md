# 个人工作台手册

入口：启动工具后，点击顶部“个人工作台”。九个入口共享本机数据库，备份会包含这些新增数据。新增写入接口沿用 API.md 的 JSON、请求头、Host 和 Origin 约束。

## 目标管理

创建目标名称和目标任务数，填入详情中的任务编号建立关联。只有已完成且不在回收站的关联任务贡献进度；进度最多 100%。可解除关联和归档恢复。目标进度不是手工填写的百分比。

- GET/POST `/api/goals`：列表或创建；title、description、target（1–10000）、due_date、archived。
- PATCH `/api/goals/{id}`：部分编辑目标。
- POST `/api/goals/{id}/tasks`：task_id、attach 布尔（默认 true）。重复关联幂等，回收站任务可解除关联。

## 习惯打卡

创建习惯、每日目标和单位。选择今天或过去的日期填完成量；同一天再次保存会覆盖该天记录，不重复累计。只有达到每日目标才计为达标。连续天数允许今天尚未打卡，从昨天开始计算。

- GET/POST `/api/habits`：列表或创建；title、target、unit。
- PATCH `/api/habits/{id}`：archived 布尔；归档后不能新增打卡。
- POST `/api/habits/{id}/logs`：day、quantity（1–100000）、note。
- DELETE `/api/habits/{id}/logs/{YYYY-MM-DD}`：撤销指定日期记录。

界面展示最近 7 条，接口返回最近 90 条；连续天数及累计数按完整历史计算。

## 灵感收集箱

先保存标题、内容和来源，再转为任务。转换时选择项目和日期。转换与任务创建在同一个事务中；重复请求返回原关联，不会新建第二个任务。已转换的记录保留关联，不能重置为未转换。

- GET `/api/inbox?state=open|converted|archived|all`：最近 200 条。
- POST `/api/inbox`：title、body、source。
- PATCH `/api/inbox/{id}`：state 为 open 或 archived。
- POST `/api/inbox/{id}/convert`：可选 project_id、due_date、priority。

已转换任务被删除后，收集记录仍保留原编号，请从任务回收站恢复。

## 工作笔记

支持分类、可选任务关联、正文搜索、归档和历史版本。正文最多 20000 字，按纯文本显示。每次编辑创建不可覆盖的版本；恢复历史也会创建新版本，不删除当前历史。旧窗口编辑会报冲突。

- GET `/api/notes?q=关键词&archived=0|1`：最近 200 条，Unicode 搜索。
- POST `/api/notes`：title、body、category、task_id。
- PATCH `/api/notes/{id}`：待修改字段与 expected_version。
- GET `/api/notes/{id}/revisions`：最近 100 个历史版本。
- POST `/api/notes/{id}/restore`：revision、expected_version。

## 每日计划

先选择日期，设置当天可用分钟，再添加起止时段和任务关联。相邻时段可共用边界；时间重叠或总时长超过当天容量时拒绝保存。默认容量 480 分钟，仅表示计划预算，不是已完成工作量。

- GET `/api/planner?day=YYYY-MM-DD`：时段和容量汇总。
- GET `/api/planner/week?day=YYYY-MM-DD`：从该日开始的七天。
- POST `/api/planner`：day、title、start_time/end_time（HH:MM）、task_id、note。
- PATCH/DELETE `/api/planner/{id}`：编辑或移除时段，不删除关联任务。
- POST `/api/planner/capacity`：day、minutes（0–1440）。

API 可用 24:00 作为结束，页面时间控件使用标准浏览器时间选择。计划不会自动改变任务状态或生成工时。

## 每周复盘

选择周内任一天，自动归到周一。每周只允许一份复盘。填写收获、阻碍、下周行动，并保存统计快照；定稿后正文和统计冻结，解除定稿后可继续编辑。

- GET/POST `/api/reviews`：列表或创建；week、wins、blockers、next_steps。
- PATCH `/api/reviews/{id}`：正文或 locked，加 expected_version。
- POST `/api/reviews/{id}/refresh`：expected_version；只重新统计，不覆盖文字。

统计包含本地周内新增与完成动作的活跃任务、所有记录的投入分钟、计划分钟及习惯达标次数。它不是历史状态回放；快照只在创建和手动重算时更新，定稿后保持原值。

## 规则批处理

保存任务筛选和目标操作。先预览匹配，再明确点击执行。执行时重新匹配，所有修改在同一个事务内。规则不会定时运行，也不会绕过前置约束或周期任务的幂等规则。

- GET/POST `/api/rules`：name、filters、action（status/priority/project）、value、enabled。
- PATCH `/api/rules/{id}`：待修改字段与 expected_version。
- POST `/api/rules/{id}/run`：preview 布尔，默认 true；返回 matched、would_update、updated 和任务摘要。
- GET `/api/rules/{id}/runs`：最近 100 次预览或执行记录。

筛选字段与任务搜索一致，不接受分页。匹配超过 100 项会拒绝，需缩小范围。设置同一值不会重复计为修改。

## 项目模板

选择已有非空项目保存蓝图。快照包含任务正文、预估、清单、标签及项目内依赖；保留模板捕获时的日期偏移。创建新项目时所有任务重置为待开始，清单未完成，不复制工时、专注、日志、周期设置、提醒、目标关联及跨项目依赖。

- GET/POST `/api/project-bundles`：创建需 project_id、name。
- POST `/api/project-bundles/{id}/apply`：新项目 name、start_day、UUID request_id。

最多 100 个任务。相同请求编号重试返回同一项目；同名项目冲突时整批回滚。源项目后续修改或删除不改变已保存模板。

## 数据健康

检查 SQLite 完整性和外键、长期未更新任务、已完成任务的未完成前置、计划时段重叠、超时未结束专注。只读取业务数据并保存报告，不自动修复或删除任务。

- GET `/api/diagnostics`：最近 100 次报告摘要。
- POST `/api/diagnostics`：stale_days（1–3650）、include_details 布尔。
- GET `/api/diagnostics/{id}`：报告全文，包含检查项和数据数量。

warning 表示需要人工关注，不等于数据库损坏。每项明细最多保留 20 个样本。
