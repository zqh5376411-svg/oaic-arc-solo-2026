# LangGraph / Deep Agents 架构与 ARC-Bench 节省方案

> 核对日期：2026-09-09（北京时间）  
> 范围：LangChain、LangGraph、Deep Agents 官方资料，以及公开参赛仓库；后者只作为工程样本，不代表赛事官方推荐。

## ELI5 结论

现在的 Agent 像一个小朋友，每做一步都重新背一遍整本《GitHub 使用说明书》。真正该学的不是立刻增加更多“小朋友”，而是：

1. 把大题切成 1–3 个相关小题。
2. 每轮只给当前小题、必要前置条件和少量相关文件。
3. 大段工具结果放进文件，只把路径和短摘要交给模型。
4. 做完一包就验证并存档，再开一个干净会话做下一包。

这四点比现在直接引入完整 LangGraph、多 Agent 或向量数据库更适合我们的单人 Harness。

## 这次 GitHub 公开题试跑

[ARC-Bench Playground 的 GitHub 题](http://arc-bench.com/playground/task-bank/web/github)当前展示 47 条原子需求、0 个公开测试。官方需求 API 可以读取完整 `requirements.yaml`，但没有可下载的公开测试，因此本地只能证明输入、生成、自测和轨迹链路，不能声称取得官方通过率。

本地实测结果：

- 官方 YAML 解析后共有 65 个树节点，其中 47 个叶子需求应进入实现状态，包含 64 个 GIVEN/WHEN/THEN 场景。
- 使用公开的 `arcbench-runtime` 0.1.0 完成整棵树干跑；构建、启动、SDK 事件和 Traceability 均通过。
- 第一次干跑暴露两个问题：目录节点被误当作执行任务；无 `id` 的场景没有进入 SDK 的 `scenarios.json`。现已用稳定的 `需求ID-S序号` 补齐场景 ID，并只把叶子需求列为 actionable。
- 完整需求作为当前缩进 JSON 提示词是 175,249 个字符。若连续调用模型 12 次，仅重复需求文本的理论下限就达到 2,102,988 个字符；这是字符数，不是模型计费 Token 数。

结论：现在不应该直接用完整 GitHub 树跑 12 轮模型循环。第一批练习应依次选择 `REQ-1-1-1` 注册、`REQ-1-1-2` 登录、`REQ-1-2` 登出，并为每个场景生成独立黑盒测试。

## 官方架构现在在做什么

### LangGraph

LangGraph 是低层编排运行时，主打把确定性代码步骤和 LLM 步骤放在同一张状态图中，并提供持久化、恢复、流式事件和人工介入。官方也明确建议：只需要常见工具循环时先用更高层的 LangChain Agent，需要精细状态控制时再用 LangGraph。[LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)

这与我们最相关的不是“画图”，而是边界：需求排序、预算、测试、checkpoint 应由确定性代码控制；只有理解需求和改代码交给模型。

### LangChain Agent 与 Context Engineering

官方把 Agent 定义为“模型循环调用工具直到完成”，Harness 则是循环外的提示词、工具和 middleware。[Agents](https://docs.langchain.com/oss/python/langchain/agents)

官方 Context Engineering 文档把成本与可靠性直接联系到五个可控入口：消息、工具、模型、提示词和输出格式；推荐动态筛选工具、按任务选择模型，并在消息增长后做持久化摘要。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)

### Deep Agents 0.7.x

截至核对日，官方仓库最新发布为 `deepagents==0.7.13`（2026-09-02）。它建立在 LangChain/LangGraph 上，内置文件系统、上下文压缩、子 Agent 和持久记忆。[0.7.13 release](https://github.com/langchain-ai/deepagents/releases/tag/deepagents%3D%3D0.7.13)｜[Overview](https://docs.langchain.com/oss/python/deepagents/overview)

值得注意的是，0.7.0 反而主动“做减法”：Todo 规划改为可选、默认基础提示词变为空、重复工具说明被删短，并支持只暴露需要的文件工具。这说明先进架构不等于默认塞进更多角色和提示词。[Deep Agents changelog](https://github.com/langchain-ai/deepagents/blob/a4905a2fe555fef3cd01563392f87c0446acd8aa/libs/deepagents/CHANGELOG.md#070)

官方上下文机制包括：

- 超大工具输入/结果写入文件，只把路径与短预览留在对话中；默认大结果阈值为 20,000 Token。
- 接近模型上下文上限时自动摘要；默认约在可用窗口的 85% 触发，并保留近期消息。
- 子 Agent 使用独立上下文，只向主 Agent 返回一次精简结果。
- 静态提示词缓存能降低部分模型的延迟与费用，但官方自动缓存主要针对 Anthropic 和 Bedrock；不能推断比赛的 Kimi、GLM、MiniMax、DeepSeek 网关也提供同样收益。

来源：[Deep Agents context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)｜[Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)

## 公开参赛实现给我们的启发

这些是参赛者工程样本，不是官方标准：

- [HAFleet ARC](https://github.com/onewesong/hafleet-arc/blob/ce14960fc005968e6de0ac9986f3147135eb2f2a/hafleet_arc/requirements.py)按 ROOT 直属模块做依赖排序；其 capability normalizer 为缺失场景生成稳定 ID，并对描述、列表和引用数量设置硬上限。
- [ShallowCode](https://github.com/TheaDust/Shallow/blob/a218db068f61a356e1517a7b864c4eb5280003fe/README.md)把依赖就绪的 1–3 个原子需求组成 WorkPacket，每次实现/修复使用短会话，并用独立浏览器探针和 accepted SHA 判断是否接纳改动。

我们应该借用“小包、短会话、确定性验收”，暂时不照搬它们的多角色、并行 worktree 和第二个 Judge 模型。

我还把 [HAFleet 的 GitHub 题成品](https://github.com/onewesong/hafleet-github)实际构建并跑了第一组身份流程：注册、登录、会话保持和退出的后端 API 均成功，合法注册页面也会跳到登录页；但非法邮箱会先触发浏览器原生校验，前端因此没有同时显示题目要求的逐字段错误。这不等于判定该作品最终失败，因为公开题没有测试；它只说明“能构建、API 能通”仍不等于 GIVEN/WHEN/THEN 场景已经满足，我们必须用真实页面交互做独立验收。

## 对当前 Harness 的取舍

| 做法 | 现在是否采用 | 原因 |
|---|---:|---|
| 叶子需求识别、稳定场景 ID | 已采用 | 修复真实官方输入兼容问题，几乎无额外运行成本 |
| 1–3 个原子需求的 WorkPacket | 下一优先级 | 直接减少重复需求上下文，并方便失败回滚 |
| 每包新会话、文件保存共享状态 | 下一优先级 | 省掉历史工具输出，同时保留代码事实 |
| 限制读取长度、压缩工具结果 | 下一优先级 | 避免大文件和构建日志反复进入消息历史 |
| 记录网关实际 usage、调用数和墙钟时间 | 下一优先级 | 没有测量就无法证明真的省 Token |
| 动态模型路由、提示词缓存 | 等官方网关合同 | 当前不知道比赛是否允许中途换模型或是否返回缓存计费 |
| 完整 LangGraph / Deep Agents 依赖 | 暂不采用 | 当前流程短、工具只有 5 个；新框架会增加包体、启动和调试风险 |
| Supervisor + 多子 Agent + Judge LLM | 暂不采用 | 会增加模型调用；在正确率没有基线前无法证明收益大于成本 |
| 向量数据库 / 长期记忆 | 暂不采用 | 单次生成题以仓库文件和需求树为事实源，不需要跨用户语义检索 |

## 下一轮可验证实验

1. 为 GitHub 身份模块生成第一个 WorkPacket：注册、登录、登出。
2. 每个包使用新模型会话，只附当前需求、全局权限摘要、已完成能力列表和相关文件路径。
3. 每包完成后运行项目自有 HTTP/浏览器测试；通过才 checkpoint，失败最多修一次。
4. 记录模型调用次数、网关返回的 input/output usage、墙钟时间和场景通过数。
5. 与当前“整棵树 + 单长会话”基线比较；只有节省且不降低通过率才保留。

目前缺少可用模型网关变量，且 GitHub 题没有公开测试，所以本轮没有伪造模型解题或官方成绩。下一次真实跑分需要赛事 Playground 登录/Token，或由用户提供可用的 OpenAI-compatible 测试网关。
