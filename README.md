# myclaw

`myclaw` 是一个基于本仓库 `s01-s08` 思路拼出来的简版 Agent。

它的目标不是复刻 `s_full.py` 的全部复杂协议，而是在更小的实现里把下面几件事连起来：

- 自循环工具调用
- `plan` / `direct` 两种工作模式
- 持久化计划与任务图
- 一次性子 agent 分发
- 后台命令执行与结果回注
- `skill_for_claw/` -> `myclaw/skills/` 的初始技能复制
- 运行中 skill 自主演化
- 完成后自动验收，不通过则返工迭代
- 长上下文压缩与 transcript 落盘

## 目录

```text
myclaw/
  __init__.py
  background.py
  compression.py
  config.py
  evaluator.py
  main.py
  skill_evolution.py
  skills.py
  skills/
  subagents.py
  tasks.py
  tools.py
```

运行时状态会写到仓库根目录下的 `.myclaw/`：

- `.myclaw/plans/`：持久化计划
- `.myclaw/tasks/`：持久化任务图
- `.myclaw/transcripts/`：上下文压缩前的完整 transcript
- `.myclaw/evolution/`：skill 演化日志

## 工作模式

### `plan`

- 用户给出需求后，agent 先保存计划和任务图
- 保存完计划后停止，不继续执行任务
- 适合先确认拆解结果

### `direct`

- 用户给出需求后，agent 会先做规划
- 然后自动执行当前可运行任务
- 任务完成后进入验收
- 如果验收失败，会生成返工任务并继续迭代
- 如果重复失败，可以触发 skill 演化

## Skills

首次启动时，`myclaw` 会把仓库里的 `skill_for_claw/` 复制到 `myclaw/skills/`，作为初始技能库。

后续运行中：

- 模型可通过 `load_skill` 按需加载技能
- 技能目录会被视作可写知识库
- 如果某类错误反复出现，可通过 `evolve_skill` 新建或改写 skill
- 新 skill 会重新进入索引，供后续回合继续使用

## 运行

确保已经配置好与仓库其它 agent 相同的环境变量，例如：

- `MODEL_ID`
- `ANTHROPIC_API_KEY` 或兼容的 `ANTHROPIC_BASE_URL`

启动方式：

```bash
python3 myclaw/main.py --mode direct
python3 myclaw/main.py --mode plan
```

## REPL 命令

- `/mode plan`
- `/mode direct`
- `/plans`
- `/tasks`
- `/skills`
- `/compact`
- `exit`

## 主要工具

父 agent 可用的核心工具包括：

- `bash`
- `read_file`
- `write_file`
- `edit_file`
- `list_skills`
- `load_skill`
- `plan_create`
- `plan_update`
- `plan_get`
- `plan_list`
- `task_create`
- `task_update`
- `task_get`
- `task_list`
- `background_run`
- `check_background`
- `delegate_task`
- `evolve_skill`
- `compact`

子 agent 只拿到基础文件/命令/skill 工具，不拿计划、任务图和演化控制工具，因此只会返回摘要，不会污染父 agent 的完整上下文。

## 当前实现特点

- 任务图采用磁盘持久化 JSON 文件，参考 `s07`
- 后台任务采用线程 + 通知队列，参考 `s08`
- 子 agent 采用独立 `messages=[]` 上下文，参考 `s04`
- skill 按需加载，参考 `s05`
- 压缩采用旧工具结果占位 + transcript 摘要，参考 `s06`
- 验收失败后会生成返工任务，而不是简单退出

## 已做的本地验证

已完成的非联网本地 smoke 检查：

- `myclaw` 模块编译通过
- CLI 可以正常启动
- `skill_for_claw` 已复制进 `myclaw/skills/`
- 计划/任务持久化可用
- 后台任务完成后可回注并解锁后继任务

依赖真实模型调用的部分，比如：

- 真实子 agent 执行
- 真实验收评估
- 真实 skill 演化内容生成

仍需要在你本地有可用模型配置时再做一次端到端验证。
