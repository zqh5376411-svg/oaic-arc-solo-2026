# Jianxian Solo Harness（剑仙单人智能体）

面向 **OAIC 2026 智能体软件工厂 / ARC-Bench** 的轻量 Coding Agent。

当前是 `v0.3` 备赛基线：入口、受限文件工具、生产轨迹、构建与启动冒烟、生成项目自有测试以及官方 Runtime SDK 优先适配已经落地；尚未在官方平台提交或取得分数。

## 为什么这样做

我先研究了官网公开队伍仓库和两条官方参考路径。多角色流水线能力强，但单人维护、Token 与排错成本都高；固定 Demo 又无法证明能根据新需求生成软件。因此本仓库选择一条窄路线：

```text
requirements.yaml
      ↓
一次有界 Agent 循环
      ↓
只允许修改 frontend/ 与 backend/
      ↓
构建 + 独立端口启动检查
      ↓ 失败时仅一次
定向修复 → 最终结果与轨迹
```

核心取舍记录在 [docs/design-decisions.md](docs/design-decisions.md)。

## ARC-Bench 入口

```bash
python3 main.py <requirements> \
  --output-dir <generated-project> \
  --type web \
  --web-port 3000
```

平台运行时需要注入：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `MODEL`

也支持 `ARCBENCH_TASK_DIR`、`ARCBENCH_TEMPLATE_DIR`、`ARCBENCH_WEB_PORT` 等环境变量。密钥只从环境读取，不写入仓库或轨迹。

Python 3.10 及以上会安装公开的 `arcbench-runtime` 0.1.x；SDK 存在时，Harness 使用其 `arcbench_agent_runtime` 接口。低版本 Python 本地开发时会跳过该依赖并使用兼容兜底。

## 本地验证

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python main.py examples \
  --output-dir /tmp/jianxian-arc-output \
  --dry-run
```

`--dry-run` 只验证脚手架、构建与启动，不调用模型，也不代表通过官方评分。

## 当前能力

- 读取并校验 ROOT `requirements.yaml`。
- 提供 `list_files`、`read_files`、`write_file`、`replace_text`、`run_validation` 五个受限工具。
- 只允许 Agent 写入生成目录下的 `frontend/` 与 `backend/`。
- 前端执行 `npm install` 和 `npm run build`；后端在随机独立端口启动并探活。
- 如生成项目注册了 `test:e2e` 或 `test` 脚本，Harness 会在后端运行期间执行，并注入 `ARCBENCH_BASE_URL` 与 `PLAYWRIGHT_BASE_URL`。
- 最终检查失败时，只给 Agent 一次定向修复机会。
- 检测到 `arcbench_agent_runtime` 时，由官方 SDK 写 Runner 事件、Traceability 与 Git checkpoint；只有 SDK 不存在时才使用本地兜底。
- 额外写入不含密钥的 `.arc/production-trace.jsonl`，记录模型和工具调用过程。
- 在生成目录创建 Git checkpoint，便于平台展示和复盘。

## 当前边界

- 官方 Codex 课程与参考实现链接尚未发布；本版本已在本地用公开的 `arcbench-runtime` 0.1.0 跑通完整模拟，但尚未在赛事 Runner 验证其预装版本与启动合同。
- 尚未连接官方模型网关，也未跑公开题或隐藏测试。
- Traceability 目前只覆盖需求树和节点状态；项目自有测试已能执行，但接口/用例映射仍要等研习营材料明确。

2026-09-09 核对的官方事实、页面冲突和待答疑问题见 [docs/OFFICIAL_QUESTIONS.md](docs/OFFICIAL_QUESTIONS.md)。

## 参考

- [OAIC 智能体软件工厂](https://create.gosim.org/factory26/)
- [Octos ARC-Bench 标准参考适配包](https://github.com/octos-org/arc-adapter)
- [HAFleet ARC](https://github.com/onewesong/hafleet-arc)
- [ARC-Bench 教程](https://arc-bench-tutorial.vercel.app/)

## License

[MIT](LICENSE)
