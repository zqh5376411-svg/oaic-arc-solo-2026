# OAIC / ARC-Bench 官方信息与待确认问题

> 最后核对：2026-09-08（北京时间）  
> 原则：只把第一方页面明确写出的内容列为“已确认”；页面没有给出的细节一律标记为“未确认”。

## 今天的结论

我们的 `v0.2` 已经具备 Python 入口、可运行生成物、构建/启动验证、项目自有测试和本地轨迹，但现在出现了一个必须优先确认的兼容风险：ARC-Bench API 文档要求 Agent 调用内置 `arcbench_agent_runtime` SDK，并明确要求不要手工构造事件；当前仓库仍由 `solo_harness/runtime.py` 自行写 `.arc/runner-events.jsonl`、Traceability JSON 和 Git 通知。

在官方运行环境验证 SDK 之前，不能把当前自写格式称为“已兼容官方协议”。

## 已确认

### 1. 赛程与赛题

- 研习营：2026-09-07 至 09-20；初赛：09-21 至 09-30；决赛：10-01 至 10-07；颁奖：10-17。初赛 Top 20 进入决赛。[比赛首页](https://create.gosim.org/factory26/)｜[赛制与规则](https://create.gosim.org/factory26/rules)
- 初赛方向为 GitHub 与 Spreadsheets 功能复刻；官网列出的 GitHub 功能包括 Actions、组织权限、审计和 Rulesets。[赛制与规则](https://create.gosim.org/factory26/rules)
- 研习营共六讲课程、三场答疑，均在 09-07 至 09-20 之间；截至本次核对，所有具体日期与会议链接仍显示“时间待定”。课程有录像，出席不计分。[研习营](https://create.gosim.org/factory26/bootcamp)

### 2. 模型、Harness 与评分

- 组织方计划提供 Kimi、GLM、MiniMax、DeepSeek 的开源模型 Token，并通过统一网关限额和计量。[赛制与规则](https://create.gosim.org/factory26/rules)
- Harness 路线不限，自研、Octos、HAgency、ARC、Claude Code 等均可；参赛者能改自己的 Harness，不能修改测试、网关计量和评分。[赛制与规则](https://create.gosim.org/factory26/rules)
- 初赛自动采集三项指标：GUI 测试用例通过率、总 Token、墙钟运行时间；权重尚未公布。[比赛首页](https://create.gosim.org/factory26/)｜[赛制与规则](https://create.gosim.org/factory26/rules)

### 3. ARC-Bench 当前公开页面

- ARC-Bench 主页目前公开了 Playground、Competition、Research、API Doc、Login 和 Register 页面；登录页同时提供 “ARC-Bench account” 与 “Hackathon account” 入口。[ARC-Bench](http://arc-bench.com/)｜[登录页](http://arc-bench.com/login)
- Competition 页面展示的流程是：上传 Agent → 编译长需求 → 运行混合任务 → 检查结果；本次核对时公开比赛列表仍显示 `0 available`。[Competition](http://arc-bench.com/competition)
- Playground 的 Web 任务说明为全栈 Web 任务，并由可执行 Playwright 测试套件验收。[Playground](http://arc-bench.com/playground)

### 4. 官方 Runtime API 文档

- 官方页面要求 Agent 使用内置 Python 包 `arcbench_agent_runtime`；SDK 负责固定事件协议、`.arc/runner-events.jsonl`、`.arc/traceability/*.json` 和 Git/前端刷新通知。[API Doc](http://arc-bench.com/api-doc)
- API 文档明确写着不要手工构造事件 payload，应调用 SDK 的高级方法。[API Doc](http://arc-bench.com/api-doc)
- 页面公开了节点状态 API，例如 `mark_design_done`、`mark_implementation_done`、`mark_test_passed`、`mark_test_failed` 与整次运行的开始/完成/失败状态。[API Doc](http://arc-bench.com/api-doc)
- Traceability API 覆盖 requirements、scenarios、interfaces、tests、node states、call edges 和 node contracts；Git API 覆盖建仓、提交、回滚、重置与状态读取。[API Doc](http://arc-bench.com/api-doc)
- 上传入口文件已明确：Python 使用 `main.py` + `requirements.txt`，JavaScript 使用 `index.js` + `package.json`，TypeScript 使用 `index.ts` + `package.json`；存在 `package.json` 时 Runner 会先安装 Node 依赖。[API Doc](http://arc-bench.com/api-doc)
- API 页面称所有 Agent 使用固定 CLI 启动，但当前可见页面没有列出完整参数、环境变量和输出目录合同，因此这些细节仍未确认。[API Doc](http://arc-bench.com/api-doc)

## 官网内部需要澄清的表述

1. **登录状态不一致**：比赛首页仍写 ARC-Bench 的开放与登录方式“另行通知”、收到通知前无需额外操作；但 ARC-Bench 已出现注册和 Hackathon 登录入口。页面可访问不等于本届赛事账号已经正式启用。
2. **提交物不一致**：比赛首页 FAQ 写“只需向黑客松比赛平台提交智能体，其他材料均不需要”；规则页同时列出“可运行的复刻（源码与启动方式）、完整生产轨迹、3–5 分钟 Demo”。目前不清楚后三项是平台自动产生、随 Agent 一并上传，还是需要人工另交。
3. **入口合同不完整**：API Doc 确认了入口文件和内置 SDK，却没有在可见页面列出完整 CLI 参数、目录结构、环境变量和资源限制。

## 当前仓库与官方页面的差距

| 项目 | 当前状态 | 判断 |
|---|---|---|
| Python `main.py` + `requirements.txt` | 已有 | 与公开入口文件要求一致 |
| 生成可运行 Web 前后端 | 已有 | 本地模拟已验证，官方环境未验证 |
| 构建、启动和项目自有测试 | 已有 | 本地验证通过 |
| 生产轨迹与 Git checkpoint | 已有自写实现 | 数据存在，但官方格式兼容性未确认 |
| `arcbench_agent_runtime` | 尚未接入 | **P0 兼容风险** |
| 完整固定 CLI 与环境变量 | 依据公开参考仓库实现 | API 页面未完整列出，仍需官方确认 |
| 官方模型网关与隐藏 Playwright 测试 | 尚未接入 | 未验证，不能视为官方成绩 |

## 待确认问题

### P0：会决定 Agent 能否启动或提交

1. **赛事账号是否已启用？** 现在能否直接用报名邮箱选择 “Hackathon account” 登录，还是必须等待组织方通知？——未确认。
2. **固定启动合同是什么？** Python Agent 的完整命令行参数、必需环境变量、requirements 输入位置、项目输出位置分别是什么？——未确认。
3. **Runtime SDK 是否强制？** `arcbench_agent_runtime` 的预装版本和导入方式是什么；手写 JSONL/Traceability 是否会被拒绝或无法刷新 UI？——API 页面要求使用 SDK，但平台强制程度及版本未确认。
4. **究竟提交什么？** 只上传 Agent 包，还是还要人工上传源码、生产轨迹与 3–5 分钟 Demo？Demo 的格式、入口和截止时间是什么？——官网页面表述冲突。
5. **初赛运行与提交限制是什么？** 每队每天/全程可运行几次，能否重复提交，排行榜取最好一次、最后一次还是平均值？——未确认。
6. **09-30 的具体截止时刻和时区是什么？**——未确认。

### P1：会直接影响正确率、Token 和速度

1. 三项指标的权重、归一化方法、并列规则和淘汰规则是什么？——权重官网明确仍待公布，其余未确认。
2. 每队 Token 总额度、单次额度、不同模型价格/折算方式、模型选择方式和限流规则是什么？——仅确认由组织方统一发放并计量。
3. 沙箱的 Python/Node 版本、CPU/内存/磁盘、单次总时限、网络访问、允许的依赖源和上传包大小是多少？——未确认。
4. Playwright 的浏览器、视口、测试并发、数据重置方式，以及前后端固定端口/健康检查要求是什么？——未确认。
5. Traceability 各表的必填字段、状态枚举和推荐调用顺序是什么？人工干预点如何记录？——API 页面列出方法组，但完整 schema 未确认。

### P2：影响复盘、合规与决赛准备

1. 能否使用公开开源 Agent、模板和第三方组件；需要怎样保留许可证和署名？——未确认。
2. 失败运行能否申诉，申诉窗口、证据格式和处理时限是什么？——仅确认可以审计/申诉，流程未确认。
3. 初赛 Top 20 的确认时间、决赛新题开放时间及是否沿用同一 Agent 包是什么？——未确认。

## 可直接复制到官方答疑的 8 个问题

> 大家好，我们是单人自研 Python Harness 队伍，想确认以下会直接影响兼容与提交的问题：  
> 1. 现在可以用报名邮箱在 ARC-Bench 选择 “Hackathon account” 登录吗，还是要等单独通知？  
> 2. Python Agent 的完整启动命令、必需环境变量、输入目录和输出目录合同是什么？  
> 3. `arcbench_agent_runtime` 是否强制使用？平台预装的版本和完整 API/schema 文档在哪里？手写 `.arc` 事件是否不再兼容？  
> 4. 最终到底只上传 Agent 包，还是还需人工提交源码、生产轨迹与 3–5 分钟 Demo？Demo 在哪里提交？  
> 5. 初赛每队有多少次运行/提交机会，排行榜按最好一次、最后一次还是多次平均？  
> 6. GUI 通过率、Token、耗时的权重、并列规则分别是什么？  
> 7. 模型 Token 配额，以及沙箱的 Python/Node 版本、网络、资源、依赖安装和单次时限是什么？  
> 8. 9 月 30 日的准确截止时刻与时区是什么？

## 后续处理规则

- 每次官网或答疑更新后，只把得到明确回答的条目从“未确认”移动到“已确认”，并保留来源和核对日期。
- 在第 2、3 项 P0 问题解决前，不宣称当前 Harness 已通过 ARC-Bench 官方协议验收。
- 需要账号、Token、最终上传或点击提交的步骤由参赛者本人完成。
