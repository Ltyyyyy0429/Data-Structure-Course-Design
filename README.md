# Data-Structure-Course-Design

本项目是《数据结构》课程设计：新能源物流车队协同调度。

系统目标是在城市路网中模拟新能源物流车队面对动态配送任务时的调度过程。当前代码已经包含图结构与 Dijkstra 寻路、基础仿真引擎、三种调度策略、批量实验脚本、Matplotlib 图表和 Pygame 可视化入口。

## 快速运行

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

生成或检查地图与寻路：

```bash
python3 demo_graph.py
```

运行仿真测试：

```bash
python3 test_simulator.py
```

运行完整批量实验：

```bash
python3 batch_experiment.py all
```

生成实验图表：

```bash
python3 visualization/plot_results.py
```

运行假数据 Pygame UI：

```bash
python3 ui/pygame_app.py
```

运行接入 Simulator 的 Pygame UI：

```bash
python3 ui/simulator_app.py
python3 ui/simulator_app.py --difficulty hard
```

## 当前模块状态

| 模块 | 负责人 | 当前状态 |
| --- | --- | --- |
| A 图结构与寻路 | A | `core/graph.py` 提供 `CityGraph`、节点、边和 Dijkstra 最短路；`data/` 中有 small / medium / large / extra_large 四种规模地图。 |
| B 仿真引擎 | B | `simulator/` 支持车辆、电量、载重、任务、充电站、排队、任务完成和评分；仍有部分参数与策略效果需要继续调优。 |
| C 调度策略 | C | `strategy.py` 支持 `nearest`、`largest`、`energy_aware_hybrid` 三种策略。 |
| D 可视化与实验 | D / yyb | `ui/` 提供 Pygame UI，`visualization/` 提供图表生成，`batch_experiment.py` 输出统一实验 CSV。 |

## A 图结构与寻路模块

生成四种规模地图：

```bash
python3 demo_graph.py
```

地图文件：

```text
data/small_map.json
data/medium_map.json
data/large_map.json
data/extra_large_map.json
```

代码中使用：

```python
from core.graph import CityGraph

graph = CityGraph.from_json("data/small_map.json")
path, distance = graph.shortest_path(0, 5)
```

主要接口：

- B 可以调用 `shortest_path(start_id, end_id)` 计算车辆移动路径。
- C 可以调用 `shortest_path(start_id, task_node_id)` 比较任务距离。
- D 可以调用 `to_state_nodes()` 和 `to_state_edges()` 绘制地图。

## B 仿真与真实寻路接入

`simulator/pathfinder_adapter.py` 中的 `RealPathfinder` 使用 A 的 `CityGraph.from_json()` 加载地图，并通过 Dijkstra 计算真实最短路径。

常用接口：

- `find_path_and_distance(start_node, end_node)`：返回 `(path, distance)`。
- `find_path(start_node, end_node)`：返回路径和距离。
- `get_distance(start_node, end_node)`：返回最短距离。
- `nearest_charging_station(start_node)`：返回最近充电站节点和距离。
- `get_state_nodes()` / `get_state_edges()`：提供 UI 绘图数据。

真实寻路 demo：

```bash
python3 demo_real_pathfinder.py
python3 demo_simulator_real_pathfinder.py
```

`Simulator` 当前可以通过 `pathfinder=` 参数注入 `RealPathfinder`。批量实验和真实 Pygame UI 都使用这个方式接入 A 的路网与 Dijkstra。

## 三种调度策略定位

当前 `strategy.py` 支持三种策略：

| 策略 | 定位 | 当前实现说明 |
| --- | --- | --- |
| `nearest` | 最近任务优先 baseline | 空闲车辆优先选择距离最近的可行任务，便于作为朴素贪心对照。 |
| `largest` | 最大重量优先 baseline | 优先选择重量较大的可行任务，可能导致距离和时效表现较差，适合在报告中作为反例对比。 |
| `energy_aware_hybrid` | 能量感知综合策略 | 综合任务重量、截止时间、距离、电量风险和充电站排队压力；当前仍处于调参阶段，不应写成已经全面优于 baseline。 |

三种策略都会通过载重可行性过滤，Simulator 在真正分配任务前也会做二次检查，避免明显超载任务被执行。

## 难度配置说明

难度参数由 `core/difficulty.py` 统一管理。当前支持：

| 难度 | 电池容量 | 单位距离耗电 | 低电量阈值 | 初始电量 | 动态任务概率 | 截止时间范围 | 充电桩数量 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `easy` | 120 kWh | 0.35 kWh/km | 20% = 24 kWh | 90% - 100% | 0.30 | 60 - 120 min | 每站 2 个 |
| `medium` | 100 kWh | 0.60 kWh/km | 30% = 30 kWh | 70% - 100% | 0.35 | 65 - 90 min | 每站 2 个 |
| `hard` | 80 kWh | 0.90 kWh/km | 40% = 32 kWh | 45% - 80% | 0.40 | 45 - 60 min | 每站 1 个 |

补充说明：

- `easy` 续航压力较低，批量实验中可能不会触发充电。
- `medium` 会提高能耗和任务压力，更容易出现补能需求。
- `hard` 初始电量更低、能耗更高、充电速度更慢，并且每站充电桩更少，更容易出现排队。
- 当前 hard 难度依赖参数自然制造补能压力，不再通过人工把车辆塞进充电站或手动制造队列。

## 批量实验说明

完整实验命令：

```bash
python3 batch_experiment.py all
```

实验维度：

- 难度：`easy / medium / hard`
- 规模：`small / medium / large / extra_large`
- 策略：`nearest / largest / energy_aware_hybrid`

完整运行后应输出 36 行结果：

```text
3 difficulties × 4 scales × 3 strategies = 36 rows
```

统一结果文件：

```text
results/experiment_results.csv
```

CSV 字段包括：

- `difficulty`
- `scale`
- `strategy`
- `total_score`
- `completed_tasks`
- `timeout_tasks`
- `total_distance`
- `charging_times`
- `low_battery_events`
- `charging_requests`
- `charging_queue_events`
- `total_charging_wait_time`
- `max_queue_length`

当前 P1 阶段最近一次运行结果显示：`nearest` 在多个场景中仍然较强，`energy_aware_hybrid` 还需要继续调参才能稳定体现中高难度优势。因此报告中可以把当前结果写成“阶段性实验结果”，不要写成最终优化结论。

## Matplotlib 图表说明

生成图表：

```bash
python3 visualization/plot_results.py
```

脚本读取：

```text
results/experiment_results.csv
```

图表输出目录：

```text
results/figures/
```

当前图表覆盖总收益、完成任务数、超时任务数、总路径长度、充电次数、充电需求、排队次数、最大队列长度和总等待时间等指标。

注意：当前 `plot_results.py` 仍保留开发阶段的示例数据回退逻辑。如果 CSV 不存在或字段不完整，脚本会生成示例数据。最终报告前建议执行 Plan2 的 D-5，删除该回退逻辑，确保图表一定来自真实批量实验。

## D 可视化模块说明

### 假数据 UI

运行：

```bash
python3 ui/pygame_app.py
```

说明：

- 使用 `DemoWorld` 假数据，不依赖 Simulator。
- 显示城市路网、仓库、充电站、任务点、车辆和右侧指标面板。
- 支持车辆规划路径线：如果 vehicle state 中包含 `path`，会用半透明线条绘制。
- 电池显示会优先使用 `battery / max_battery` 计算百分比；如果没有 `max_battery`，保留原来的显示方式。

按键：

- `SPACE`：暂停 / 继续
- `1`：切换 `nearest`
- `2`：切换 `largest`
- `R`：重置假数据
- `ESC`：退出

### Simulator UI

运行：

```bash
python3 ui/simulator_app.py
python3 ui/simulator_app.py --difficulty medium
python3 ui/simulator_app.py --difficulty hard
```

说明：

- 使用 `data/small_map.json` 创建 `RealPathfinder`。
- 创建 B 的 `Simulator`，并通过 `ui/state_adapter.py` 转换成 Pygame 可绘制 state。
- 当前支持 `easy / medium / hard` 难度切换，但还没有 `--scale` 参数。
- 当前保留低电量演示逻辑，会把第一辆车电量设低，方便观察充电行为。

按键：

- `SPACE`：暂停 / 继续
- `R`：重置 Simulator
- `1`：使用 `nearest` 重置
- `2`：使用 `largest` 重置
- `3`：使用 `energy_aware_hybrid` 重置
- `ESC`：退出

### State 适配层

`ui/state_adapter.py` 用于隔离 UI 和仿真引擎数据格式。

运行测试：

```bash
python3 ui/test_state_adapter.py
```

适配内容：

- `depot` 转成 `warehouse`。
- `charging_station` 转成 `charging`。
- `from_node` / `to_node` 转成 `from` / `to`。
- 车辆如果只有 `current_node` 或 `current_node_id`，会根据节点补充 `x` / `y`。
- 任务和充电站如果只有 `node_id`，也会根据节点补充坐标。

推荐 UI 读取方式：

```python
from ui.state_adapter import normalize_state

state = normalize_state(simulator.get_state())
```

统一 state 建议包含：

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

## 当前 P1 阶段注意事项

- `batch_experiment.py all` 可以生成 36 行统一 CSV。
- `visualization/plot_results.py` 可以从 CSV 生成图表，但示例数据回退逻辑还应在 D-5 中删除。
- `ui/pygame_app.py` 是稳定的假数据展示入口，不负责真实仿真。
- `ui/simulator_app.py` 是真实仿真展示入口，目前固定 small 地图，支持难度切换。
- `energy_aware_hybrid` 已接入能量和排队因素，但当前实验结果还没有稳定压过 `nearest`，后续 C 模块仍需调参和验证。
- README 中的功能说明以当前代码为准，不把未完成的 `--scale`、更复杂 GUI、全局最优算法等内容写成已实现。
