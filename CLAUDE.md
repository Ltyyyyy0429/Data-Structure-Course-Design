# CLAUDE.md

## 项目概述 (Project Overview)

本项目是《数据结构课程设计》小组作业——**新能源物流车队协同调度系统**。模拟中央仓库管理一支新能源车队，在城市路网中动态响应配送任务，要求使用图结构实现道路建模与寻路。

### 核心功能

- **图结构路网**：基于邻接表实现的城市道路图，支持程序化生成小/中/大/特大四种规模地图，支持 grid/cluster 两种拓扑布局、瓶颈边删除、单向边
- **Dijkstra 最短路径**：车辆移动、充电站选择均基于真实最短路径计算
- **多策略调度**：已实现 `nearest`（最近任务优先）、`largest`（最大任务优先）、`energy_aware_hybrid`（能量感知综合调度）三种策略
- **难度配置系统**：`core/difficulty.py` 提供 EASY/MEDIUM/HARD 三档预设，统一控制地图拓扑、车辆参数、任务生成、充电设施
- **充电站管理**：电量不足时自动寻路至最近充电站，支持排队与负荷模拟
- **动态任务生成**：仿真期间按概率随机生成任务，支持 burst 突发模式与空间聚集，包含产生时间、坐标、货物重量
- **评分系统**：任务越早完成且路径越短，收益越高；超时未完成（含 ASSIGNED 状态）扣分
- **Pygame 可视化**：实时交互式地图展示车辆移动、任务状态、充电站队列
- **Matplotlib 图表**：批量实验后自动生成策略对比柱状图

### 模块架构

项目由 4 人小组并行开发，分为四个模块：

```
模块 A (core/)         模块 B (simulator/)
  图结构 & Dijkstra  ──►  RealPathfinder (适配层)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              模块 C       仿真引擎    模块 D
             strategy.py  simulator  ui/ + visualization/
             调度策略      事件循环    Pygame + Matplotlib
```

模块间通过统一的 `state` 字典（6 个字段：`nodes`, `edges`, `vehicles`, `tasks`, `charging_stations`, `metrics`）通信。

---

## 技术栈 (Tech Stack)

| 类别 | 详情 |
|------|------|
| **语言** | Python 3.10+（使用 PEP 604 `|` 联合类型语法） |
| **核心依赖** | `pygame`（交互式可视化）, `matplotlib`（图表绘制）, `pandas`（数据处理） |
| **包管理器** | pip + `requirements.txt`（无版本锁定） |
| **类型检查** | 无 mypy/pyright 配置，仅使用 Python 原生 type hints |
| **代码格式化** | 无 Black/Ruff/Flake8 配置 |
| **CI/CD** | 无 |
| **容器化** | 无 |
| **数据建模** | `dataclasses`, `Enum`, `Literal` type hints |
| **测试框架** | 无 pytest/unittest，使用原生 `assert` + `print` |

---

## 目录结构 (Directory Structure)

```
.
├── core/                       # 模块 A: 图结构与最短路径
│   ├── __init__.py
│   ├── graph.py                #   CityGraph 类: 邻接表图、Dijkstra 最短路径
│   ├── map_generator.py        #   程序化生成小/中/大/特大四种规模的城市路网 JSON，支持 cluster/瓶颈/单向边
│   └── difficulty.py           #   难度预设配置: EASY/MEDIUM/HARD 三档，统一控制地图/车辆/任务/充电参数
├── simulator/                  # 模块 B: 仿真引擎
│   ├── __init__.py
│   ├── models.py               #   数据模型: Vehicle, Task, ChargingStation, Metrics 等 (dataclass)
│   ├── simulator.py            #   Simulator 类: 时间步进的事件循环仿真，支持 DifficultyConfig 参数化
│   ├── task_generator.py       #   动态任务生成器 (支持 burst 模式、紧张截止时间、空间聚集)
│   └── pathfinder_adapter.py   #   RealPathfinder: 将 A 模块 CityGraph 适配给 B 模块
├── ui/                         # 模块 D: Pygame 交互式可视化
│   ├── __init__.py
│   ├── pygame_app.py           #   独立 Demo UI (假数据原型)
│   ├── simulator_app.py        #   真实 UI，连接 B 模块 Simulator
│   ├── state_adapter.py        #   状态适配层: 统一模块间的命名差异
│   ├── colors.py               #   颜色常量
│   └── test_state_adapter.py   #   适配器单元测试
├── visualization/              # 模块 D: Matplotlib 静态图表
│   ├── __init__.py
│   └── plot_results.py         #   读取实验结果 CSV，生成对比柱状图 PNG
├── strategy.py                 # 模块 C: 调度策略 (nearest / largest / energy_aware_hybrid)
├── data/                       # 生成的地图 JSON (small / medium / large / extra_large)
├── results/                    # 实验输出: CSV + figures/ 图表 PNG
├── batch_experiment.py         # 批量实验运行器 (多策略 × 多地图规模 × 多难度等级)
├── demo_graph.py               # 地图生成演示
├── demo_real_pathfinder.py     # A-B 路径规划集成演示
├── demo_simulator_real_pathfinder.py  # 完整仿真 + 真实路径规划演示
├── test_simulator.py           # 仿真引擎测试 (全流程对比两种策略)
├── test_strategy.py            # 调度策略单元测试 (含 MockRealPathfinder)
├── test_integration.py         # 跨模块集成测试 (RealPathfinder + Dispatcher)
├── README.md                   # 项目说明文档
└── requirements.txt            # 依赖配置
```

---

## 开发规范 (Development Conventions)

### Git 分支策略

- **主分支**: `main` —— 稳定版本，通过 PR 合并
- **功能分支**: 按模块命名，如 `feature/A`（图结构）、`feature/c-strategy`（调度策略）、`feature/pygame-ui`（可视化）等
- **合并方式**: Pull Request → `main`

### Commit 格式

```
feat(X): 描述
```

其中 `X` 为模块标识（A/B/C/D），描述可使用中文或英文。示例：

```
feat(B): 完整集成A+C模块，统一整数ID，实现逐节点移动
feat: 完成能量感知综合调度策略及单元测试校验
feat: integrate real pathfinder with simulator
```

### 代码风格

| 方面 | 规范 |
|------|------|
| **命名** | `snake_case` 函数/变量, `PascalCase` 类, `UPPER_CASE` 常量, `_` 前缀私有方法 |
| **类型标注** | 所有公共函数签名必须包含 type hints |
| **文档字符串** | 所有公共类和公共方法需有三引号 docstring（Google 风格或 reST 风格均可） |
| **数据建模** | 优先使用 `@dataclass`；枚举使用 `Enum` |
| **导入顺序** | 标准库 → 第三方库 → 项目内部模块 |
| **模块通信** | 通过统一的 `state` 字典（6 字段）传递状态，如需新增字段需同步更新 `ui/state_adapter.py` |

### 测试规范

- 测试文件命名为 `test_*.py`，放在模块目录或根目录
- 使用原生 `assert` 进行断言，结果通过 `print` 输出
- Mock 类定义在测试文件内部，不引入额外 mocking 框架
- 测试分层：单元测试（如 `test_strategy.py`）→ 集成测试（如 `test_integration.py`）→ 端到端测试（如 `test_simulator.py`）

---

## 常用命令 (Common Commands)

### 安装依赖

```bash
pip install -r requirements.txt
```

### 生成地图数据

```bash
python demo_graph.py          # 生成 data/small_map.json, medium_map.json, large_map.json, extra_large_map.json
```

### 运行仿真演示

```bash
python demo_real_pathfinder.py               # A-B 路径规划集成测试
python demo_simulator_real_pathfinder.py     # 完整仿真 + 真实路径规划 (可选 --difficulty easy|medium|hard)
```

### 启动可视化 UI

```bash
python ui/pygame_app.py       # 独立 Pygame Demo (假数据原型)
python ui/simulator_app.py    # 真实 Pygame UI (连接仿真引擎，可选 --difficulty easy|medium|hard)
```

键盘操作（UI）：

- `SPACE`：暂停 / 继续
- `1`：切换策略为 `nearest`
- `2`：切换策略为 `largest`
- `3`：切换策略为 `energy_aware_hybrid`
- `R`：重置
- `ESC`：退出

### 生成实验图表

```bash
python visualization/plot_results.py   # 读取 results/experiment_results.csv 生成 PNG 图表
```

### 批量实验

```bash
python batch_experiment.py              # 3 策略 × 4 规模 × EASY 难度 = 12 组实验
python batch_experiment.py medium       # 12 组实验，使用 MEDIUM 难度参数
python batch_experiment.py hard         # 12 组实验，使用 HARD 难度参数
```

### 运行测试

```bash
python test_simulator.py      # 仿真引擎端到端测试 (nearest vs largest 策略对比)
python test_strategy.py       # 调度策略单元测试 (4 个场景: 满电/低电/临界/充电排队)
python test_integration.py    # 跨模块集成测试 (RealPathfinder + Dispatcher)
python ui/test_state_adapter.py  # 状态适配器单元测试
```

---

## 注意事项 (Gotchas)

### 难度配置系统 (Difficulty Config)

`core/difficulty.py` 提供 EASY / MEDIUM / HARD 三档预设，通过 `DifficultyConfig` 统一控制所有模块参数：

```python
from core.difficulty import get_difficulty_config

config = get_difficulty_config("small", "hard")
sim = Simulator(graph_data, scale, strategy, pathfinder=pathfinder, config=config)
```

`DifficultyConfig` 包含四个子配置：
- `MapConfig` — 节点数、充电站数、拓扑模式(grid/cluster)、瓶颈比例、单向边比例、充电站分布(uniform/clustered/scarce)
- `VehicleConfig` — 车辆数(按规模)、电池容量、能耗、速度、载重、低电量阈值
- `TaskConfig` — 生成概率、截止时间范围、重量范围、burst 概率
- `ChargingConfig` — 充电速率、每站端口数

**向后兼容**：`Simulator.__init__` 的 `config` 参数默认为 `None`，此时使用原类常量（= EASY 行为）。所有现有测试和 Demo 无需传 config 即可运行。

**Dispatcher 新增 `consume_rate` 参数**：`Dispatcher.__init__` 新增 `consume_rate` 参数（默认 0.5）。Simulator 构造 Dispatcher 时会传入实际 `energy_per_km` 值，确保策略层的能量硬门槛与实际仿真能耗一致。

**TaskGenerator 已实现**：`simulator/task_generator.py` 不再是死代码。Simulator 在提供 `config` 时会构造 `TaskGenerator` 实例并委托任务生成；无 config 时使用原有简单随机逻辑。

### 重复的数据模型

项目中存在两套 `Node` / `Edge` dataclass：

| 文件 | Node.type 可选值 |
|------|-----------------|
| `core/graph.py` | `"warehouse"`, `"normal"`, `"charging"`, `"task"` |
| `simulator/models.py` | `"depot"`, `"task_point"`, `"charging_station"` |

**Simulator 不再自行构建 CityGraph 或做 type_mapping 转换。** 所有图结构操作统一通过注入的 `RealPathfinder` 实例完成（Dijkstra 寻路、最近充电站查询等）。两套模型的映射仅在需要将 A 的 JSON 地图数据转换为 B 的 `graph_data` 格式时生效（如 `demo_simulator_real_pathfinder.py` 中的 `build_b_graph_from_a_pathfinder()` 和 `batch_experiment.py` 中的 `load_graph_data()`）。

### RealPathfinder 注入模式

`RealPathfinder`（`simulator/pathfinder_adapter.py`）是 CityGraph 的**唯一持有者**，通过构造函数注入 `Simulator` 和 `Dispatcher`：

```python
pathfinder = RealPathfinder("data/small_map.json")
config = get_difficulty_config("small", "easy")  # 可选，默认 None = EASY
sim = Simulator(graph_data, scale, strategy, pathfinder=pathfinder, config=config)
dispatcher = Dispatcher(pathfinder, strategy_name="nearest")
```

- `find_path_and_distance(start, end) -> Tuple[List[int], float]` 是规范寻路入口
- C 模块 action 字典中携带 `path` 字段，B 的 `_apply_dispatch()` 直接使用，不再自行调 shortest_path
- 充电站导航走 `RealPathfinder.nearest_charging_station()`，基于 Dijkstra 最短路径，不使用欧几里得距离

### State 字典是模块间唯一契约

A/B/C/D 四个模块通过 6 字段 `state` 字典通信：

```python
{
    "nodes": ...,
    "edges": ...,
    "vehicles": ...,
    "tasks": ...,
    "charging_stations": ...,
    "metrics": ...
}
```

`ui/state_adapter.py` 的 `normalize_state()` 负责字段名兼容（`from_node` → `from`，`depot` → `warehouse` 等）。**新增 state 字段时必须在 state_adapter 中同步处理。**

### 硬编码路径

多处文件路径以字符串硬编码（如 `"data/small_map.json"`, `"results/experiment_results.csv"`），修改目录结构时需全局搜索替换。

### 类型标注与文档字符串不一致

- `from __future__ import annotations` 在 `core/graph.py`、`strategy.py`、`simulator/pathfinder_adapter.py` 中使用；`strategy.py` 同时使用 `TYPE_CHECKING` 守卫避免循环导入
- 文档字符串语言混用：模块 A 使用英文，模块 B/C 使用中文
- `strategy.py` 的私有方法缺少 type hints

### 依赖与环境

- `requirements.txt` 中的依赖未锁定版本号
- `pandas` 在依赖列表中但当前源代码中未见直接引用（可能为预留依赖）
- 项目无 `.python-version`、虚拟环境创建指引，新成员上手需口头传递环境配置
- Python 版本需 ≥ 3.10（代码中使用了 PEP 604 `str | Path` 联合类型语法）

### 测试

- 测试通过直接 `python test_*.py` 运行，无 pytest/unittest 封装
- 模块 A（图算法核心）和模块 D（UI 渲染）缺少独立的自动化测试
