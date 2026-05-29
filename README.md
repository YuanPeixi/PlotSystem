# Plot System

## 1. 项目目的
最终目的是实现一个多智能体、可分支的结局剧情推演系统。

## 2. 当前实现
本仓库现在包含一个**可直接运行的 MVP 系统**，提供以下能力：

- **种子文本建模**：输入非结构化种子文本后，自动拆句并抽取关键词，生成一个轻量级知识/关系图谱。
- **多智能体初始化**：自动生成导演智能体、角色智能体、环境智能体、总结智能体、氛围智能体的初始配置。
- **场景模拟**：导演推动场景、角色执行动作、环境根据互动更新状态，并记录每轮导演决策。
- **快照与分支**：每轮场景前自动创建快照，可基于任意快照派生出新的剧情分支项目。
- **长期记忆沉淀**：每个场景结束后，把角色在当前场景中的关键互动压缩进长期记忆。
- **总结导出**：可导出一份风格化文本，汇总导演目标、场景梗概、角色长期记忆和当前环境状态。
- **本地 Web UI + HTTP API**：可以通过浏览器完成创建项目、运行模拟、创建分支和导出总结。

> 这是一个不依赖外部 LLM 服务的可运行版本，重点是把 README 中描述的系统流程完整打通，后续可以继续替换成真实模型和更强的 GraphRAG / AutoGen 能力。

## 3. 与原始设想的对应关系

### 智能体设计
- **导演智能体**：负责确定场景目标，并在每轮后决定继续推进还是进入下一阶段。
- **角色智能体**：按各自目标和人设执行动作并产出对话。
- **环境智能体**：根据场景互动更新环境状态与紧张度。
- **总结智能体**：将场景摘要、记忆、环境状态整合为导出文本。
- **氛围智能体**：通过关键词检测得到氛围标签，用于补充上下文焦点。

### 具体流程
1. 给定种子文本后，生成轻量级知识图谱。
2. 自动初始化角色、环境、导演目标和基础规则。
3. 运行场景模拟前自动快照。
4. 每轮中角色行动、环境变化、导演决策都会被记录。
5. 结束场景后将轮次互动压缩成长期记忆。
6. 可导出总结文本，或者从快照继续创建分支剧情。

## 4. 项目结构

```text
/tmp/workspace/YuanPeixi/PlotSystem
├── README.md
├── data/                     # 默认运行时数据目录
├── plot_system/
│   ├── __init__.py
│   ├── app.py                # 应用服务层
│   ├── domain.py             # 剧情领域逻辑
│   ├── server.py             # HTTP 服务入口
│   └── storage.py            # JSON 持久化
├── static/
│   └── index.html            # 浏览器界面
└── tests/
    └── test_plot_system.py   # 核心流程测试
```

## 5. 运行方式

### 启动系统
在仓库根目录执行：

```bash
cd /tmp/workspace/YuanPeixi/PlotSystem
python3 -m plot_system.server --host 127.0.0.1 --port 8000
```

启动后访问：<http://127.0.0.1:8000>

### 运行测试

```bash
cd /tmp/workspace/YuanPeixi/PlotSystem
python3 -m unittest discover -s tests -v
```

## 6. HTTP API

### 创建项目
```http
POST /api/projects
Content-Type: application/json

{
  "title": "示例剧情",
  "seed_text": "你的种子文本"
}
```

### 运行场景模拟
```http
POST /api/projects/{project_id}/simulate
Content-Type: application/json

{
  "rounds": 2
}
```

### 创建分支
```http
POST /api/projects/{project_id}/branch
Content-Type: application/json

{
  "snapshot_id": "snapshot_xxx",
  "branch_name": "平行分支"
}
```

### 导出总结
```http
POST /api/projects/{project_id}/summary
Content-Type: application/json

{
  "style": "网文"
}
```

## 7. 已实现部分说明
已完成并可运行的部分：

- 基于 README 需求的**完整本地可运行骨架**。
- 从种子文本到知识图谱、角色初始化、场景模拟、快照、分支、总结导出的**端到端主流程**。
- 一个可操作的浏览器界面和一组本地 API。
- 自动化测试，覆盖创建项目、模拟、总结、分支的核心流程。

当前仍是 MVP、尚未接入的高级能力：

- 真实的 GraphRAG 检索与知识库构建。
- 真实大模型/多模型编排与成本优化。
- 更复杂的角色记忆压缩策略与导演重拍逻辑。
- 更细粒度的环境规则系统与总结写作控制。
