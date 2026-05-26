# Data-Structure-Course-Design

## D 可视化模块使用说明

本模块由 D / yyb 负责，用于展示“新能源物流车队协同调度”的图形界面和实验结果图表。

### 1. 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

### 2. 运行 Pygame UI 原型

```bash
python3 ui/pygame_app.py
```

当前 UI 是假数据原型，不依赖 A/B/C 的真实模块。界面中可以看到道路、节点、仓库、充电站、任务点、车辆和运行指标。

键盘操作：

- `SPACE`：暂停 / 继续
- `1`：切换策略为 `nearest`
- `2`：切换策略为 `largest`
- `3`：切换策略为 `energy_aware_hybrid`
- `R`：重置假数据
- `ESC`：退出

后续 B 的仿真引擎完成后，联调时只需要在 `pygame_app.py` 中把 demo state 替换成 `simulator.get_state()`。

当前已经新增 `ui/state_adapter.py` 作为 UI 和仿真引擎之间的数据对接层：

- `get_demo_state(demo_world)`：保留当前假数据原型。
- `load_state_from_simulator(simulator)`：后续接入真实仿真器时调用，内部会执行 `simulator.get_state()`。
- `validate_state(state)`：检查 state 是否包含 `nodes`、`edges`、`vehicles`、`tasks`、`charging_stations`、`metrics` 六个核心字段。

### 3. 生成 Matplotlib 实验图表

```bash
python3 visualization/plot_results.py
```

脚本会读取 `results/experiment_results.csv`。如果 CSV 不存在或为空，会自动生成一份示例实验数据。

生成的图片会保存到：

```text
results/figures/
```

### 4. 后续需要 A/B/C 提供的统一 state 字典格式

D 模块后续会通过统一的 `state` 字典接入 A/B/C 的真实模块，建议格式如下：

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

其中：

- `nodes`：图中的节点，包括普通节点、仓库、充电站等。
- `edges`：道路边，用于绘制城市路网。
- `vehicles`：车辆信息，包括位置、电量、状态等。
- `tasks`：当前任务点信息，包括位置、重量、状态等。
- `charging_stations`：充电站信息，包括位置和排队长度。
- `metrics`：当前时间、策略、总收益、完成任务数、超时任务数、总路径长度、充电次数等统计指标。

## A 图结构与寻路模块使用说明

本模块由 A 负责，用于提供城市路网图结构、道路边、Dijkstra 最短路，以及小 / 中 / 大 / 特大四种规模的地图数据。

### 1. 生成四种规模地图

```bash
python3 demo_graph.py
```

运行后会生成：

```text
data/small_map.json
data/medium_map.json
data/large_map.json
data/extra_large_map.json
```

### 2. 在代码中使用

```python
from core.graph import CityGraph

graph = CityGraph.from_json("data/small_map.json")
path, distance = graph.shortest_path(0, 5)
print(path, distance)
```

### 3. 给 B/C/D 的接口

- B 仿真引擎可以调用 `shortest_path(start_id, end_id)` 计算车辆移动路径。
- C 调度策略可以调用 `shortest_path(start_id, task_node_id)` 比较车辆到不同任务的距离。
- D 可视化模块可以调用 `to_state_nodes()` 和 `to_state_edges()` 获取绘图所需的地图数据。

### 4. JSON 地图格式

```json
{
  "nodes": [
    {"id": 0, "x": 8.0, "y": 50.0, "type": "warehouse"},
    {"id": 1, "x": 11.89, "y": 5.88, "type": "normal"}
  ],
  "edges": [
    {"from": 1, "to": 0, "distance": 44.29}
  ]
}
```

说明：

- `nodes` 保存图中的节点，包括仓库、普通节点、充电站等。
- `edges` 保存道路。当前地图生成器生成的是双向道路，JSON 中每条道路只保存一条记录，读取时会自动加入双向邻接表。
- 如果 `add_edge()` 没有传入 `distance`，系统会自动根据两个节点的 x/y 坐标计算欧氏距离。

## 联调 state 适配说明

A/B/D 联调时，建议 D 的 Pygame UI 最终读取：

```python
from ui.state_adapter import normalize_state

state = normalize_state(simulator.get_state())
```

B 仿真引擎可以先按自己的模型输出 `raw_state`，但建议尽量包含以下六个核心字段：

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

当前 `ui/state_adapter.py` 会做这些兼容处理：

- `depot` 会转换为 `warehouse`。
- `charging_station` 会转换为 `charging`。
- `from_node` / `to_node` 会转换为 `from` / `to`。
- 如果车辆只有 `current_node` 或 `current_node_id`，会根据节点坐标补充 `x` / `y`。
- 如果任务或充电站只有 `node_id`，也会根据节点坐标补充 `x` / `y`。

运行适配层测试：

```bash
python3 ui/test_state_adapter.py
```

## A-B 真实寻路联调说明

运行 RealPathfinder demo：

```bash
python3 demo_real_pathfinder.py
```

`RealPathfinder` 位于 `simulator/pathfinder_adapter.py`，内部使用 A 模块的 `CityGraph.from_json()` 加载地图，并通过 `CityGraph.shortest_path()` 调用 Dijkstra 计算真实最短路径。

它兼容 B 当前 `MockPathfinder` 的主要接口：

- `find_path_and_distance(start_node, end_node)`：规范寻路入口，返回 `(path, distance)`。
- `find_path(start_node, end_node)`：同上，别名。
- `get_shortest_path(start_node, end_node)`：返回路径列表。
- `get_distance(start_node, end_node)`：返回最短路径距离。
- `nearest_charging_station(start_node)`：返回最近充电站节点和距离。

运行真实寻路版仿真 demo：

```bash
python3 demo_simulator_real_pathfinder.py                  # 默认 EASY 难度
python3 demo_simulator_real_pathfinder.py --difficulty hard  # HARD 难度
```

当前接入方式是：构造 `RealPathfinder` 实例，通过 `Simulator` 构造函数的 `pathfinder=` 和 `config=` 参数注入。Simulator 内部不再自行构建 CityGraph，所有路径计算（包括去充电站的导航）统一经过 RealPathfinder → Dijkstra，不再使用欧几里得距离 fallback。

```python
from simulator import Simulator
from simulator.pathfinder_adapter import RealPathfinder
from core.difficulty import get_difficulty_config

pathfinder = RealPathfinder("data/small_map.json")
config = get_difficulty_config("small", "easy")
simulator = Simulator(graph_data, scale="small", strategy="nearest",
                      pathfinder=pathfinder, config=config)
```

真实寻路版 Pygame 演示也可以运行：

```bash
python3 ui/simulator_app.py
```

这个入口会用 `RealPathfinder` 加载 A 的 `data/small_map.json`，创建 B 的 `Simulator`，再通过 D 的 `state_adapter` 和 Pygame 绘制仿真状态。

C 模块调度策略已完全接入，`Dispatcher` 通过 `RealPathfinder.find_path_and_distance()` 计算路径，并在 action 字典中携带 `path` 字段供 Simulator 直接使用。

## Pygame 接入 Simulator 演示说明

原假数据 UI 仍然使用：

```bash
python3 ui/pygame_app.py
```

接入 B 当前 `Simulator` 的真实仿真 UI 使用：

```bash
python3 ui/simulator_app.py                       # 默认 EASY 难度
python3 ui/simulator_app.py --difficulty hard      # HARD 难度
```

B 仿真引擎终端测试使用：

```bash
python3 test_simulator.py
```

`ui/simulator_app.py` 会创建 B 的 `Simulator`，循环调用当前版本提供的 `update(dt)` 方法，并通过 `ui/state_adapter.py` 转换成 D 的 Pygame 可绘制 state。该入口还保留了低电量演示：默认会把第一辆车电量设为 15，方便观察 `charging_times` 或充电站负荷变化。

键盘操作：

- `SPACE`：暂停 / 继续
- `R`：重置 Simulator
- `1`：用 `nearest` 策略重置 Simulator
- `2`：用 `largest` 策略重置 Simulator
- `3`：用 `energy_aware_hybrid` 策略重置 Simulator
- `ESC`：退出

注意：当前 `simulator_app.py` 已使用 A 的 `RealPathfinder` 进行路径计算，调度器已接入 C 的 `Dispatcher`（支持 nearest / largest / energy_aware_hybrid 三种策略）。支持通过 `--difficulty easy|medium|hard` 切换难度配置。
