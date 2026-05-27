# Data-Structure-Course-Design

本项目是《数据结构》课程设计：新能源物流车队协同调度。

系统目标是在城市路网中模拟新能源物流车队面对动态配送任务时的调度过程。使用邻接表实现图结构路网与 Dijkstra 最短路径寻路，包含仿真引擎、四种调度策略、难度配置系统、批量实验脚本、Matplotlib 图表和 Pygame 可视化。

## 快速运行

安装依赖：

```bash
pip install -r requirements.txt
```

生成地图数据：

```bash
python demo_graph.py
```

运行仿真演示：

```bash
python demo_real_pathfinder.py               # A-B 路径规划集成测试
python demo_simulator_real_pathfinder.py     # 完整仿真 + 真实路径规划 (可选 --difficulty easy|medium|hard)
```

启动可视化 UI：

```bash
python3 ui/pygame_app.py
python3 ui/simulator_app.py
python3 ui/simulator_app.py --scale large --difficulty hard --strategy energy_aware_hybrid
python3 ui/simulator_app.py --scale large --difficulty hard --strategy energy_aware_hybrid --demo-low-battery
```

`ui/pygame_app.py` 是假数据 UI / 备用界面检查入口，不依赖仿真引擎。`ui/simulator_app.py` 是答辩展示推荐入口，连接当前 Simulator，支持 `--scale small|medium|large|extra_large`、`--difficulty easy|medium|hard`、`--strategy nearest|largest|energy_aware_hybrid|genetic_algorithm`。`--demo-low-battery` 会人为降低第一辆车电量，方便录屏时观察充电逻辑；正式实验结果以 `batch_experiment.py` 生成的 `results/experiment_results.csv` 为准。

键盘操作：
- `SPACE`：暂停 / 继续
- `1`：切换 nearest | `2`：切换 largest | `3`：切换 energy_aware_hybrid | `4`：切换 genetic_algorithm
- `D`：循环切换 easy / medium / hard 难度
- `S`：small | `M`：medium | `L`：large | `X`：extra_large
- `R`：重置 | `ESC`：退出

运行批量实验：

```bash
python3 batch_experiment.py all       # 3 难度 x 4 规模 x 4 策略 = 48 组实验
python3 batch_experiment.py medium    # 仅 MEDIUM 难度，16 组
python3 batch_experiment.py hard      # 仅 HARD 难度，16 组
```

生成实验图表：

```bash
python3 visualization/plot_results.py
```

`plot_results.py` 不再自动生成示例数据。请先运行 `python3 batch_experiment.py all`，生成正式的 `results/experiment_results.csv` 后再画图。CSV 中策略原值保持 `nearest`、`largest`、`energy_aware_hybrid`、`genetic_algorithm`；图表图例使用短标签 `nearest`、`largest`、`hybrid`、`GA`。

运行测试：

```bash
python3 test_simulator.py             # 仿真引擎端到端测试
python3 test_strategy.py              # 调度策略单元测试
python3 test_integration.py           # 跨模块集成测试
python3 ui/test_state_adapter.py      # 状态适配器单元测试
```

## 当前模块状态

| 模块 | 负责人 | 当前状态 |
| --- | --- | --- |
| A 图结构与寻路 | A | `core/graph.py` 提供邻接表图、Dijkstra 最短路径、最近充电站查询；`core/map_generator.py` 支持 grid/cluster 拓扑、瓶颈边删除、单向边转换、充电站分布策略；`core/difficulty.py` 提供 EASY/MEDIUM/HARD 三档预设。 |
| B 仿真引擎 | B | `simulator/` 支持车辆移动、电量消耗、载重约束、任务生成（含 burst 模式）、充电排队、评分系统和事件循环。 |
| C 调度策略 | C | `strategy.py` + `strategy_ga.py` 支持 `nearest`、`largest`、`energy_aware_hybrid`、`genetic_algorithm` 四种策略。 |
| D 可视化与实验 | D | `ui/` 提供 Pygame UI 与 state 适配层，`visualization/` 提供 Matplotlib 图表生成，`batch_experiment.py` 输出统一实验 CSV。 |

## A 图结构与寻路模块

模块 A 负责城市路网建模与最短路径导航，是其余三个模块的底层基础设施。

### 地图生成 (map_generator.py)

支持程序化生成四种规模的城市路网 JSON：

| 规模 | 节点数 | 充电站 | extra_neighbors | 文件 |
| --- | --- | --- | --- | --- |
| small | 10 | 2 | 2 | `data/small_map.json` |
| medium | 30 | 4 | 3 | `data/medium_map.json` |
| large | 60 | 6 | 3 | `data/large_map.json` |
| extra_large | 80 | 8 | 4 | `data/extra_large_map.json` |

两种拓扑布局：
- **Grid 模式**：网格排列 + 随机抖动，建边分两阶段——连通性保证（每个节点连到最近前驱）+ KNN 稠密化（再加 K 条最近邻边）
- **Cluster 模式**：节点分簇，建边分三阶段——同簇连通 + 簇内 KNN 稠密 + 簇间桥接（每对簇仅一条"咽喉要道"），拓扑难度显著高于 Grid

后处理：
- **瓶颈边删除**（`_apply_bottlenecks`）：临时删边 + Dijkstra 验证替代路径，只删不影响连通性的冗余边
- **单向边转换**（`_apply_one_way_edges`）：将部分边变为单行道，标记 `bidirectional=False`

充电站分布策略：
- `uniform`：按步长均匀分布在节点 ID 序列上
- `clustered`：集中在锚点周围，形成"充电荒漠"
- `scarce`：减少数量 + 随机散布

### 图结构与 Dijkstra (graph.py)

核心数据结构：`Node`（warehouse/normal/charging/task）、`Edge`（含 `bidirectional` 字段）、`CityGraph`（邻接表存储）。

主要接口：

```python
from core.graph import CityGraph

graph = CityGraph.from_json("data/small_map.json")
path, distance = graph.shortest_path(0, 5)         # Dijkstra，O((V+E)log V)
nearest, dist = graph.nearest_node(3, "charging")   # 找最近充电站
graph.save_json("data/out.json")                    # 序列化（节点按 ID 排序）
nodes = graph.to_state_nodes()                      # 导出给 UI 绘图
edges = graph.to_state_edges()
```

`shortest_path()` 到达终点立即终止（不全图遍历），`nearest_node()` 按距离递增出队、首个匹配即为最近。`from_json()` 双格式兼容（同时识别 `"from"/"to"` 和 `"from_node"/"to_node"`）。

### 难度配置系统 (difficulty.py)

`get_difficulty_config(scale, difficulty)` 返回 `DifficultyConfig`，包含四个子配置：

| 子配置 | 控制内容 |
| --- | --- |
| `MapConfig` | 节点数、充电站数、拓扑模式(grid/cluster)、瓶颈比例、单向边比例、充电站分布 |
| `VehicleConfig` | 车辆数、电池容量、单位能耗、速度、载重、低电量阈值(比例)、初始电量范围(比例) |
| `TaskConfig` | 任务生成概率、截止时间、重量范围、burst 概率 |
| `ChargingConfig` | 充电速率、每站端口数 |

三档难度参数：

| 参数 | EASY | MEDIUM | HARD |
| --- | --- | --- | --- |
| 电池容量 | 120 kWh | 100 kWh | 80 kWh |
| 单位能耗 | 0.35 kWh/km | 0.60 kWh/km | 0.90 kWh/km |
| 低电量阈值 | 20% (24 kWh) | 30% (30 kWh) | 40% (32 kWh) |
| 初始电量 | 90%-100% | 70%-100% | 45%-80% |
| 任务生成概率 | 0.30 | 0.35 | 0.40 |
| 截止时间 | 60-120 min | 65-90 min | 45-60 min |
| 充电速率 | 50 kWh/h | 45 kWh/h | 35 kWh/h |
| 每站端口 | 2 | 2 | 1 |
| 拓扑模式 | grid | grid | cluster |
| 瓶颈比例 | 0% | 10% | 20% |
| 单向边比例 | 0% | 5% | 10% |
| 充电分布 | uniform | uniform | clustered |
| 车辆数(s/m/l/xl) | 3/3/3/3 | 3/3/3/3 | 2/3/4/5 |

`VehicleConfig` 采用比例制设计：`low_battery_threshold_ratio` 替代绝对 kWh，`initial_battery_min_ratio` / `initial_battery_max_ratio` 控制初始电量范围，调整电池容量时阈值自动缩放。

## B 仿真引擎与路径规划适配

`simulator/pathfinder_adapter.py` 中的 `RealPathfinder` 将 A 模块的 `CityGraph` 注入 B/C 模块，通过 `find_path_and_distance()` 提供统一的 Dijkstra 寻路入口。

```python
pathfinder = RealPathfinder("data/small_map.json")
sim = Simulator(graph_data, scale, strategy, pathfinder=pathfinder, config=config)
dispatcher = Dispatcher(pathfinder, strategy_name="nearest")
```

Simulator 核心流程：时间步进 → 车辆沿路径移动耗电 → 低电量检测（移动车辆使用可达性检查，空闲车辆使用绝对阈值） → 充电排队处理 → 动态任务生成 → 调用调度策略分配任务 → 任务完成评分。

关键设计：
- Simulator 层能量预检：分配任务前检查车辆电量是否足够到达任务 + 安全返回最近的充电站或仓库（`_can_reach_and_return`）
- 评分公式：`score = 100 + time_early * 2 - task_distance * 0.3`，task_distance 通过 Dijkstra 预计算
- 载重二级防御：策略层 + Simulator 层双重检查载重可行性
- TaskGenerator：支持 burst 突发模式与空间聚集，由 DifficultyConfig 参数化控制
- 充电排队去重防御性清理

## C 四种调度策略

| 策略 | 函数 | 定位 |
| --- | --- | --- |
| `nearest` | `_nearest_dispatch()` | 最近任务优先 baseline |
| `largest` | `_largest_dispatch()` | 最大重量优先 baseline |
| `energy_aware_hybrid` | `_energy_aware_hybrid_dispatch()` | 百分制综合打分：base=30 + 收益40 + 紧急度30 - 距离/电池/排队惩罚 |
| `genetic_algorithm` | `strategy_ga.ga_dispatch()` | 每 tick 运行轻量 GA（pop=40, gen=30），适应度公式与 hybrid 统一 |

策略层通过 `pathfinder.find_path_and_distance()` 预计算完整路径，放入 action 的 `path` 字段，Simulator 直接使用避免重复 Dijkstra。`Dispatcher.__init__` 接收 `consume_rate` 参数（Simulator 传入实际 `energy_per_km`），确保策略层能量硬门槛与实际能耗一致。

GA 适应度与 Hybrid 打分使用统一的百分制公式：收益归一化用车辆载重上限、紧急度用缓冲时间（扣除赶路时间）、电池惩罚用二次函数、死亡冲锋硬约束。`_as_float` / `_is_load_feasible` 因避免循环导入各自保留。

## D 可视化与实验

### Pygame UI

- `ui/pygame_app.py`：假数据 UI / 备用界面检查入口，独立运行，不依赖 Simulator
- `ui/simulator_app.py`：真实仿真 UI，连接 Simulator，用于答辩演示和录屏
- `ui/state_adapter.py`：`normalize_state()` 统一命名差异（`depot`→`warehouse`、`from_node`→`from` 等），补充缺失坐标

推荐展示命令：

```bash
python3 ui/pygame_app.py
python3 ui/simulator_app.py
python3 ui/simulator_app.py --scale large --difficulty hard --strategy energy_aware_hybrid
python3 ui/simulator_app.py --scale large --difficulty hard --strategy energy_aware_hybrid --demo-low-battery
```

`ui/simulator_app.py` 支持四种规模、三种难度和四种策略：

- 规模：`small`, `medium`, `large`, `extra_large`
- 难度：`easy`, `medium`, `hard`
- 策略：`nearest`, `largest`, `energy_aware_hybrid`, `genetic_algorithm`

其中 `--demo-low-battery` 只用于可视化演示，方便观察低电量与充电行为；正式实验数据不以 UI 演示为准。

### Matplotlib 图表

```bash
python3 visualization/plot_results.py   # 读取 results/experiment_results.csv 生成 PNG
```

图表输出到 `results/figures/`，覆盖总收益、完成任务数、超时任务数、总路径长度、充电次数、充电需求、排队次数、最大队列长度、总等待时间。图表脚本只读取正式 CSV，不会自动生成示例数据；如果 CSV 缺失、列缺失或不是 48 行，会提示先运行完整批量实验。每次生成前会清理旧 PNG，避免报告误用旧图。

### 批量实验

正式批量实验命令：

```bash
python3 batch_experiment.py all
```

实验维度：4 scales × 3 difficulties × 4 strategies = 48 runs，默认仿真 180 分钟。

统一输出 `results/experiment_results.csv`，字段包括：`difficulty`, `scale`, `strategy`, `total_score`, `completed_tasks`, `timeout_tasks`, `total_distance`, `charging_times`, `low_battery_events`, `charging_requests`, `charging_queue_events`, `total_charging_wait_time`, `max_queue_length`。

正式报告和图表以 `results/experiment_results.csv` 为准；`ui/simulator_app.py` 主要用于展示系统运行过程、车辆状态、任务点、充电站压力和策略切换效果。

## State 字典（模块间唯一契约）

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

新增 state 字段时需同步更新 `ui/state_adapter.py`。
