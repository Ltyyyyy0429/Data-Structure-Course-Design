# A 成员（图与寻路模块）进度分析

## 一、总体进度评估

A 模块的核心功能已全部完成并合并到 `main` 分支。图结构、Dijkstra、地图生成等基础工作都在已合并的 `feature/graph-routing` 分支上完成。当前 `feature/A` 分支包含 2026-05-26 实施的强化方案（消除 Dijkstra fallback、RealPathfinder 注入模式、策略预计算路径等）以及同日完成的环境难度增强方案（三档难度预设、cluster 拓扑、瓶颈/单向边、TaskGenerator 实现、参数化 Simulator 等）。

**当前状态**：强化方案 + 难度增强方案均已于 2026-05-26 实施完成，核心改动已合并到当前分支。目标达成：Dijkstra 不再被 try/except fallback 绕过，RealPathfinder 成为 CityGraph 唯一持有者，环境支持 EASY/MEDIUM/HARD 三档难度配置。

对照时间表：

| 日期 | 计划任务 | 完成状态 |
|------|----------|----------|
| 5.25 (Day 1) | 设计 models.py、Node/Edge 字段、dijkstra() 空壳 | ✅ 已完成 |
| 5.26 (Day 2) | 寻路算法完工、生成大/中/小三种地图 | ✅ 已完成 |
| 5.27+ (Day 3-4) | 联调、实验 | ✅ 已通过集成测试 |

---

## 二、已完成的文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| [core/graph.py](core/graph.py) | 297 | 图结构与 Dijkstra 算法核心 |
| [core/map_generator.py](core/map_generator.py) | ~280 | 四种规模地图程序化生成，支持 cluster/瓶颈/单向边 |
| [core/difficulty.py](core/difficulty.py) | ~200 | EASY/MEDIUM/HARD 三档难度预设 (NEW) |
| [core/__init__.py](core/__init__.py) | ~10 | 包初始化 + 重导出 (NEW，修复原 init.py 问题) |
| [data/small_map.json](data/small_map.json) | - | 10 节点 / 2 充电站 |
| [data/medium_map.json](data/medium_map.json) | - | 30 节点 / 4 充电站 |
| [data/large_map.json](data/large_map.json) | - | 60 节点 / 6 充电站 |
| [data/extra_large_map.json](data/extra_large_map.json) | - | 80 节点 / 8 充电站 (NEW) |
| [demo_graph.py](demo_graph.py) | 57 | A 模块独立演示 |
| [demo_real_pathfinder.py](demo_real_pathfinder.py) | 50 | A→B 路径规划适配演示 |
| [demo_simulator_real_pathfinder.py](demo_simulator_real_pathfinder.py) | 69 | A→B 完整仿真串联演示 |

---

## 三、技术实现细节

### 3.1 图数据结构 ([core/graph.py:20-52](core/graph.py#L20-L52))

**Node**（dataclass）4 个字段：`id: int`, `x: float`, `y: float`, `type: str`

节点类型常量 `VALID_NODE_TYPES = {"warehouse", "normal", "charging", "task"}`，`__post_init__` 中做类型校验，传入非法类型直接抛 `ValueError`。

**Edge**（dataclass）3 个字段：`from_node: int`, `to_node: int`, `distance: float`

关键设计：图的边对象只存一份（表示一条道路），但邻接表里存双向。`to_json_dict()` 方法输出 key 为 `"from"` / `"to"`（而非 `"from_node"` / `"to_node"`），这是为兼容 D 模块 UI 的格式约定。

**CityGraph** 内部存储：
- `self.nodes: Dict[int, Node]` — 节点字典
- `self.adjacency: Dict[int, List[Tuple[int, float]]]` — 邻接表，值是 `(neighbor_id, distance)` 列表
- `self.edges: List[Edge]` — 边对象平铺列表

### 3.2 Dijkstra 最短路径 ([core/graph.py:123-170](core/graph.py#L123-L170))

标准实现，时间复杂度 O((V+E) log V)：

- **优先队列**：`heapq` 最小堆，元素为 `(current_distance, node_id)`
- **三个辅助结构**：`distances`（初始化为 `inf`）、`previous`（路径回溯）、`visited`（跳过重复出队节点）
- **提前终止**：`current_id == end_id` 时直接 break，不遍历全图
- **不可达**：返回 `([], float("inf"))`

`shortest_path()` 是对 `dijkstra()` 的薄包装，注释说明这是为将来替换为 A* 预留的稳定接口。

### 3.3 最近特定类型节点搜索 ([core/graph.py:172-201](core/graph.py#L172-L201))

`nearest_node(start_id, node_type)` 是**改进版 Dijkstra**：

- 核心区别：在出队时检查节点类型，**第一个匹配的节点就是最近的**（因为 Dijkstra 按距离递增出队）
- 这比"先跑完 Dijkstra 再过滤"高效得多
- B 模块通过 `RealPathfinder.nearest_charging_station()` 调用此方法，实现"低电量自动找最近充电站"

### 3.4 JSON 序列化/反序列化 ([core/graph.py:220-263](core/graph.py#L220-L263))

`from_json()` 类方法做了**双格式兼容**：

```python
from_node = edge_data["from"] if "from" in edge_data else edge_data["from_node"]
to_node = edge_data["to"] if "to" in edge_data else edge_data["to_node"]
```

这样 A 输出的 JSON（`"from"/"to"` 格式）和 B 模块传过来的数据（`"from_node"/"to_node"` 格式）都能正确读取。

`save_json()` 输出排序后的节点和边，`ensure_ascii=False, indent=2`，直接可供 D 模块 UI 使用。

### 3.5 状态格式导出 ([core/graph.py:203-218](core/graph.py#L203-L218))

两个方法专门为跨模块 state 协议设计：

- `to_state_nodes()` → `Dict[int, {"x", "y", "type"}]`，按 node_id 排序
- `to_state_edges()` → `List[{"from", "to", "distance"}]`

### 3.6 地图生成算法 ([core/map_generator.py:54-93](core/map_generator.py#L54-L93))

核心算法分两步，确保**连通性**和**真实感**：

1. **连通性保证**：新节点 i 连接到前 i-1 个节点中欧几里得距离最近的那个（类似 Prim 最小生成树思路）。这从根本上杜绝了孤立节点。

2. **路网稠密化**：每个节点额外连接到距离最近的 `extra_neighbors` 个邻居（小地图 +2，中/大 +3）。

其他设计要点：

- **固定随机种子**：小/中/大地图分别使用 seed=202601/202602/202603，保证每次生成完全一致
- **网格布局 + 抖动**：节点排列在矩形网格上（`cols = ceil(sqrt(n))`），坐标范围 [5, 95]，额外加 ±2.5 的随机抖动
- **充电站均匀分布**：`_choose_charging_ids()` 按步长 `(n-1)/(k+1)` 均匀选取充电站 ID，避免扎堆
- **去重**：通过 `Set[Tuple[int, int]]` 记录已添加的边（按排序后的节点对为 key），防止重复建边

---

## 四、跨模块集成接口

A 模块对外暴露的核心 API（被 B/C/D 调用的方法）：

| 方法 | 调用方 | 用途 |
|------|--------|------|
| `shortest_path(start, end)` | B（移动寻路）、C（策略距离计算） | 返回 `(路径列表, 距离)` |
| `nearest_node(start, "charging")` | B（低电量找充电站） | 返回 `(节点ID, 距离)` |
| `to_state_nodes()` / `to_state_edges()` | D（UI 渲染） | 返回 state 格式的节点/边数据 |
| `from_json(file_path)` | B（RealPathfinder 加载地图） | 从 JSON 构建图 |

`simulator/pathfinder_adapter.py` 中的 `RealPathfinder` 是 A→B 的适配层，提供了 4 个别名方法（`find_path`、`get_shortest_path`、`get_path`、`shortest_path`）全部指向同一个 Dijkstra 调用，这是为了兼容 B 模块新旧代码中不同的方法名。

---

## 五、策略路径计算原理（深度分析）

经深入代码审查，三个策略对 A 模块 `shortest_path` 的使用方式差异很大：

### 5.1 `largest`（最大权重优先）— 不计算路径

[`strategy.py:53-69`](strategy.py#L53-L69)：只按任务重量降序排列，直接分配。**全程不调 `shortest_path()`**，不考虑距离也不考虑电量。车辆可能以极低电量被派往远处。

### 5.2 `nearest`（最近任务优先）— 只算距离，丢弃路径

[`strategy.py:74-111`](strategy.py#L74-L111)：对每辆空闲车遍历所有任务，调用：
```python
_, dist = self.city_graph.shortest_path(start_node, target_node)  # 丢弃路径列表
```
选 Dijkstra 距离最近的任务。**不检查电量**。

### 5.3 `energy_aware_hybrid`（能量感知综合调度）— 唯一做电量预检

[`strategy.py:116-177`](strategy.py#L116-L177)：对每个 (车, 任务) 组合：
1. `d1 = shortest_path(车 → 任务)` 距离
2. `d2 = shortest_path(任务 → 最近充电站)` 距离（遍历所有充电站取最近）
3. **硬门槛**：`required_energy = (d1 + d2) × 0.5`，`battery < required_energy + 5.0` 则跳过
4. **软打分**：`收益 + 紧急度 - 距离惩罚 - 电量风险 - 充电排队`

### 5.4 充电触发机制（Simulator 层，独立于策略）

**不是"等到没电再找"**，而是提前预防。`LOW_BATTERY_THRESHOLD = 80 kWh`，`ENERGY_PER_KM = 0.3`，缓冲距离 ≈ 266 km：

| 触发点 | 条件 | 行为 |
|--------|------|------|
| [`_move_vehicles()` L190](simulator/simulator.py#L190) | 移动中 `battery < 80` | 中断任务，保存到 `saved_tasks`，导航去最近充电站 |
| [`_check_low_battery()` L298](simulator/simulator.py#L298) | 空闲时 `battery < 80` | 导航去充电站 / 已在则排队或开始充电 |

---

## 六、当前存在的问题

### 6.1 `core/__init__.py` 缺失

现有文件名为 `core/init.py`（缺少双下划线），导致 `core/` 不是合法的 Python 常规包（仅靠 namespace package 机制勉强工作）。

### 6.2 A 模块缺少独立单元测试

没有 `test_graph.py`，Dijkstra 正确性、边界情况（不连通图、自环、不可达目标）从未被独立验证。现有测试中只有 `test_integration.py` 用一个 3 节点的极小图间接测了最短路径。

### 6.3 ✅ `feature/A` 分支为空（已过时）

本分支现已包含强化方案的全部改动（10 个文件），见第七节。

### 6.4 ✅ 重复数据模型导致类型腐败（已修复）

~~`Simulator.__init__` 中通过 `type_mapping` 重复构建了一个 `CityGraph`，导致 A 格式的类型名（`"warehouse"`, `"charging"`, `"task"`）全部 fallback 为 `"normal"`，致使 `nearest_node(from, "charging")` 永远返回 `None`。~~

**修复方式**：删除 `Simulator.__init__` 中重复构建 `CityGraph` 的代码（type_mapping + add_node/add_edge 循环），改为通过构造函数接受 `RealPathfinder` 实例。`RealPathfinder` 直接从 A 的 JSON 加载 `CityGraph`，类型信息完整保留。

### 6.5 ✅ 3 个 try/except fallback 绕过 Dijkstra（已修复）

| 位置 | 原 fallback | 修复方式 |
|------|-----------|----------|
| `_find_nearest_charging_station` | 欧几里得距离遍历 B 的 `self.nodes` | 改用 `self.pathfinder.nearest_charging_station(from_node)`，删除 except 分支 |
| `_get_distance` | 欧几里得距离 (`math.sqrt`) | 改用 `self.pathfinder.find_path_and_distance()`，保留欧几里得作为安全兜底 |
| `_apply_dispatch` | `[task.node_id]` 直接跳到目标 | 直接从 action 字典读取策略预计算的 `path` 字段，不再自行调 shortest_path |

### 6.6 ✅ `RealPathfinder` 闲置（已修复）

`RealPathfinder` 现在是 `CityGraph` 的**唯一持有者**，通过构造函数注入 `Simulator` 和 `Dispatcher`：

```python
pathfinder = RealPathfinder("data/small_map.json")
sim = Simulator(graph_data, scale, strategy, pathfinder=pathfinder)
dispatcher = Dispatcher(pathfinder, strategy_name="nearest")
```

所有路径计算统一走 `RealPathfinder.find_path_and_distance()` → `CityGraph.shortest_path()`。

### 6.7 ✅ 双重 Dijkstra 计算（已修复）

策略层预计算路径后放入 action 字典的 `path` 字段，Simulator 的 `_apply_dispatch()` 直接使用，不再重复调用 `shortest_path`。消除了一次冗余的 Dijkstra 计算。

---

## 七、已实施的改进方案（2026-05-26 完成）

原始方案：[车辆逐节点移动强化方案 v2](C:\Users\admin\.claude\plans\a-claude-md-a-5-25-5-29-wise-locket.md)

### 核心改动（全部 6 步已完成）

1. ✅ **删除 Simulator 中重复构建 CityGraph 的 type_mapping + add_node/add_edge 循环**（根除类型腐败）
2. ✅ **RealPathfinder 成为 CityGraph 的唯一持有者**，Simulator 和 Dispatcher 均通过构造函数注入
3. ✅ **策略返回完整路径**（action 新增 `path` 字段），消除双重 Dijkstra
4. ✅ **移除 3 个 try/except fallback**，`_apply_dispatch` 和 `_find_nearest_charging_station` 不再静默降级
5. ✅ **`_find_nearest_charging_station` 删除 except 分支**，改用 `RealPathfinder.nearest_charging_station()`
6. ✅ **适配所有调用方**：`test_strategy.py`（MockRealPathfinder）、`test_integration.py`（temp JSON + RealPathfinder）、`test_simulator.py`（`_build_pathfinder` helper）、`batch_experiment.py`、`demo_simulator_real_pathfinder.py`

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| [simulator/simulator.py](simulator/simulator.py) | 重构：删除重复 CityGraph 构建，注入 RealPathfinder，移除 fallback |
| [strategy.py](strategy.py) | 重构：`city_graph` → `pathfinder`，action 携带 `path` 字段，TYPE_CHECKING 守卫避免循环导入 |
| [simulator/pathfinder_adapter.py](simulator/pathfinder_adapter.py) | 增强：新增 `find_path_and_distance()` 作为规范寻路入口 |
| [batch_experiment.py](batch_experiment.py) | 适配：构造 RealPathfinder 并注入 Simulator |
| [demo_simulator_real_pathfinder.py](demo_simulator_real_pathfinder.py) | 清理：移除 `_pathfinder` hack，改用构造函数注入 |
| [test_strategy.py](test_strategy.py) | 适配：MockCityGraph → MockRealPathfinder |
| [test_integration.py](test_integration.py) | 适配：改用 temp JSON + RealPathfinder |
| [test_simulator.py](test_simulator.py) | 适配：新增 `_build_pathfinder()` helper |
| [README.md](README.md) | 文档：更新 RealPathfinder 接口说明和注入模式 |
| [CLAUDE.md](CLAUDE.md) | 文档：更新架构图、gotchas、测试描述 |

### 验证结果

- `test_strategy.py` — 4 个场景全部通过（满电/低电/临界/充电排队）
- `test_integration.py` — nearest 策略集成测试通过
- `test_simulator.py` — nearest vs largest 全流程对比通过
- `demo_simulator_real_pathfinder.py` — 端到端仿真正常

### 仍存在的已知问题

- ~~**6.1** `core/init.py` 应更名为 `core/__init__.py`~~ ✅ 已修复：新增 `core/__init__.py` 并重导出核心符号
- **6.2** A 模块缺少独立单元测试 `test_graph.py`（尚未编写）
- **6.3** `feature/A` 分支现已包含本次改动（不再为空）

不改动部分：`_move_vehicles()` 逐边遍历逻辑（已正确）、`core/graph.py` Dijkstra 算法（已正确）。

---

## 八、环境难度增强方案（2026-05-26 完成）

### 背景

项目附加分要求"提供足够困难的环境"。原有环境参数过于宽松（续航 1666 km、任务截止时间 60-120 min、充电站均匀分布），无法对调度策略形成有效压力。

### 新建文件

| 文件 | 说明 |
|------|------|
| [core/difficulty.py](core/difficulty.py) | 难度预设配置中心：EASY/MEDIUM/HARD 三档，统一控制地图/车辆/任务/充电参数 |
| [core/__init__.py](core/__init__.py) | 包初始化文件，重导出 CityGraph、DifficultyConfig 等核心符号 |

### 核心改动

1. ✅ **创建 `core/difficulty.py`**：定义 `DifficultyPreset` 枚举、`MapConfig`/`VehicleConfig`/`TaskConfig`/`ChargingConfig` dataclass，以及 `get_difficulty_config(scale, difficulty)` 工厂函数
2. ✅ **地图生成增强**：新增 `generate_extra_large_map()`（80 节点/8 充电站），`generate_map_from_config()` 支持 cluster 拓扑布局、瓶颈边删除、单向边、充电站 clustered/scarce 分布
3. ✅ **Simulator 参数化**：`Simulator.__init__` 新增 `config: DifficultyConfig` 参数，所有车辆/任务/充电参数改为实例属性（从 config 提取或回退类常量），修复 ASSIGNED 任务超时 bug（原仅检查 WAITING 状态）
4. ✅ **TaskGenerator 实现**：`simulator/task_generator.py` 从死代码重写为完整实现，支持 config 驱动的生成概率、burst 突发模式、空间聚集
5. ✅ **Bug 修复**：`strategy.py` consume_rate 改为构造参数（Simulator 传入实际 `energy_per_km` 值），chargers/charging_stations 双键兼容
6. ✅ **批量实验增强**：`batch_experiment.py` 加入 `energy_aware_hybrid` 策略和 `extra_large` 规模，支持 `python batch_experiment.py [difficulty]` 命令行参数
7. ✅ **UI 增强**：`ui/simulator_app.py` 按键 `3` 切换 `energy_aware_hybrid`，支持 `--difficulty` 参数；`visualization/plot_results.py` 更新 SCALES/STRATEGIES 常量

### 难度参数对照

| 参数 | EASY（=原值） | MEDIUM | HARD |
|------|-------------|--------|------|
| 电池容量 | 500 kWh | 300 kWh | 200 kWh |
| 能耗 | 0.3 kWh/km | 0.5 kWh/km | 0.7 kWh/km |
| 低电量阈值 | 80 kWh | 60 kWh | 45 kWh |
| 充电速率 | 100 kWh/h | 75 kWh/h | 50 kWh/h |
| 充电端口 | 2 | 2 | 1 |
| 车辆数(小/中/大/特大) | 3/3/3/3 | 3/3/3/3 | 2/3/4/5 |
| 任务生成概率 | 30% | 50% | 70% |
| 截止时间 | 60-120 min | 45-90 min | 25-60 min |
| 任务重量 | 50-500 kg | 80-500 kg | 100-500 kg |
| Burst 概率 | 0% | 10% | 20% |
| 地图拓扑 | grid | grid+10%瓶颈 | cluster+20%瓶颈+10%单向 |
| 充电站分布 | uniform | uniform | clustered |
| 地图规模 | 3 种 | 3 种 | 4 种(含 80 节点) |

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| [core/difficulty.py](core/difficulty.py) | 新建：难度预设配置中心 |
| [core/__init__.py](core/__init__.py) | 新建：包初始化 + 重导出 |
| [core/map_generator.py](core/map_generator.py) | 增强：第 4 种规模、cluster 拓扑、瓶颈/单向边、充电站分布模式 |
| [simulator/simulator.py](simulator/simulator.py) | 参数化：config 参数、实例属性、ASSIGNED 超时修复、TaskGenerator 委托 |
| [simulator/task_generator.py](simulator/task_generator.py) | 重写：从死代码实现为完整任务生成器 |
| [strategy.py](strategy.py) | 修复：consume_rate 可配置、充电站 key 兼容 |
| [batch_experiment.py](batch_experiment.py) | 增强：energy_aware_hybrid、extra_large、difficulty 参数 |
| [test_strategy.py](test_strategy.py) | 适配：mock state 使用 charging_stations 键 |
| [demo_simulator_real_pathfinder.py](demo_simulator_real_pathfinder.py) | 适配：--difficulty 参数 |
| [demo_graph.py](demo_graph.py) | 增强：extra_large 地图生成与展示 |
| [ui/simulator_app.py](ui/simulator_app.py) | 增强：按键 3、--difficulty、config 注入 |
| [visualization/plot_results.py](visualization/plot_results.py) | 更新：SCALES/STRATEGIES 常量 |

### 验证结果

- `test_strategy.py` — 4 个场景全部通过
- `test_integration.py` — nearest 策略集成测试通过
- `test_simulator.py` — nearest vs largest 全流程对比通过
- `demo_simulator_real_pathfinder.py --difficulty hard` — HARD 难度端到端正常（2 车/200 kWh/0.7 kWh/km）
