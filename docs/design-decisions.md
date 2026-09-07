# 设计决策（2026-09-07）

## 研究样本

- 官方 [octos-org/arc-adapter](https://github.com/octos-org/arc-adapter)：确认 `main.py` 调用合同、`frontend/ + backend/` 产物、Runner 事件、Git checkpoint 与独立 smoke port。
- 官方 [onewesong/hafleet-arc](https://github.com/onewesong/hafleet-arc)：学习 Architect → Implementer → Reviewer → Postflight 的闭环，但不照搬多角色和并行 worktree。
- 公开队伍 [LuZhong-Li/gosim-demo-26](https://github.com/LuZhong-Li/gosim-demo-26)：学习权限、Rulesets、Actions 与审计的领域拆分；同时避免把固定 Mock Demo 当成可泛化 Agent。
- 公开项目 [ArisLiWind/mioa-harness](https://github.com/ArisLiWind/mioa-harness)：学习有界 Turn/Step 和追加式事件记录。
- 公开 Factory26 项目 [bugtakue/langqi-forge](https://github.com/bugtakue/langqi-forge)：学习验证门、受限写入和证据边界；其完整能力内核不适合我们的第一版。

这里只吸收公开架构思想与平台合同；本仓库代码独立实现。

## 决策

### 1. 单 Agent，而非多角色

原因：评分同时看正确率、Token 和耗时。第一版用一个有界工具循环，最多 12 个常规 Turn；只有最终验证失败才追加最多 4 个修复 Turn。

### 2. 工具白名单，而非任意 Shell

模型只能查看和修改 `frontend/`、`backend/`，验证命令由 Harness 固定执行。这样可以限制误删、越界写入和任意依赖脚本。

### 3. 先确定性验证，再相信模型总结

完成标准不是模型说“完成”，而是：目录完整、前端构建通过、后端能在非评分端口启动并通过 HTTP 探活。

### 4. 一次定向修复

最终检查失败后，把精简错误交回同一会话，只修验证指出的问题。这样保留反馈闭环，同时控制 Token 与墙钟时间。

### 5. 暂不预置题目答案

模板只包含可构建、可启动的空白 Web 外壳，不硬编码 GitHub 或 Spreadsheet 公开题答案。等官方研习营明确题包和合法复用边界后再决定是否加入能力模块。

### 6. 运行生成项目自有测试

只有“能构建、能启动”不足以发现业务和 HTTP 语义错误。借鉴 HAFleet 的项目测试发现方式和 Octos 的最终 API 验收思路，Harness 现在会在独立冒烟端口运行时发现并执行前后端 `test:e2e` 或 `test` 脚本。没有注册测试的旧项目仍兼容，避免把通用 Harness 绑死在某道题的 API 上。

## 待官方材料确认

- Codex 参考实现是否提供可复用运行时。
- Runner 事件与 traceability 的最终字段要求。
- 公开题包、提交包上限、依赖安装与网络限制。
- 是否必须上传 GitHub URL，或由 ARC-Bench 直接上传压缩包。
