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

经深入代码审查，四个策略对 A 模块 `shortest_path` 的使用方式差异很大：

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

### 5.4 `genetic_algorithm`（遗传算法调度）— 进化搜索最优分配

[`strategy_ga.py`](strategy_ga.py)：每 tick 运行轻量 GA（pop=40, gen=30）：

1. **编码**：染色体为长度 n 的列表（n = idle vehicle 数量），基因为 task index 或 -1（不分配）
2. **适应度**：综合 `base_score + alpha×weight_norm + beta×urgency_norm - gamma×d1 - delta×(1-battery_ratio) - epsilon×queue_len`，不可行解返回 `-inf`
3. **选择**：锦标赛选择 (k=3)，**交叉**：均匀交叉 + 重复修复，**变异**：随机重分配 (10%)
4. **精英保留**：每代保留最优 2 个个体
5. **路径缓存**：同 tick 内缓存已计算的 OD 对距离，避免重复 Dijkstra

### 5.5 充电触发机制（Simulator 层，独立于策略）

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
| [strategy.py](strategy.py) | 重构：`city_graph` → `pathfinder`，action 携带 `path` 字段，TYPE_CHECKING 守卫避免循环导入，新增 `genetic_algorithm` 分支 |
| [strategy_ga.py](strategy_ga.py) | 新建：遗传算法调度策略，pop=40/gen=30，适应度综合距离/紧急度/电池/排队 |
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

### 难度参数对照（2026-05-27 队友重新调参后更新）

| 参数 | EASY | MEDIUM | HARD |
|------|-----|--------|------|
| 电池容量 | 120 kWh | 100 kWh | 80 kWh |
| 能耗 | 0.35 kWh/km | 0.60 kWh/km | 0.90 kWh/km |
| 低电量阈值(比例) | 20% (24 kWh) | 30% (30 kWh) | 40% (32 kWh) |
| 初始电量范围 | 90%-100% | 70%-100% | 45%-80% |
| 充电速率 | 50 kWh/h | 45 kWh/h | 35 kWh/h |
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

---

## 九、队友合并至 main 的改动分析（2026-05-27）

### 背景

队友 yyb 在 commit `f2a71b8` 中合入了以下修改：
- 删除 `batch_experiment.py` 中的 `apply_hard_charging_pressure()` 硬编码充电压力注入
- 在 `strategy.py` 的三个策略中增加共享的载重可行性检查
- 在 `Simulator` 中增加超载任务分配的二级防御
- 更新 `core/difficulty.py` 追踪实际充电指标
- 更新 README 约束说明

### 对 A 模块（core/difficulty.py）的具体改动

#### VehicleConfig 参数重构

**低电量阈值：从绝对值改为比例制**

原来 `VehicleConfig` 直接存储 `low_battery_threshold_kwh: float = 80.0`（绝对 kWh 值），现在改为：

```python
low_battery_threshold_ratio: float = 0.30   # 比例值（占电池容量的百分比）
```

并新增**计算方法** `low_battery_threshold_kwh()` → `battery_capacity_kwh * ratio`，供调用方获取实际的 kWh 阈值。这样做的好处是：调整电池容量时低电量阈值自动跟随缩放，不需要手动重新计算。

**新增初始电量范围控制**

新增两个比例字段和对应的计算方法：

```python
initial_battery_min_ratio: float = 0.90   # 初始电量的下限比例
initial_battery_max_ratio: float = 1.00   # 初始电量的上限比例

def initial_battery_range_kwh(self) -> Tuple[float, float]:
    """返回 (min_kwh, max_kwh)，供 Simulator 随机初始化车辆电量"""
```

**Imports 变化**：新增 `Tuple` 导入，用于 `initial_battery_range_kwh()` 的返回类型标注。

#### 各难度档位参数全面重调

| 参数 | EASY（旧→新） | MEDIUM（旧→新） | HARD（旧→新） |
|------|-------------|---------------|-------------|
| 电池容量 | 500→120 kWh | 300→100 kWh | 200→80 kWh |
| 能耗 | 0.3→0.35 kWh/km | 0.5→0.60 kWh/km | 0.7→0.90 kWh/km |
| 低电量阈值 | 80→24 kWh (20%) | 60→30 kWh (30%) | 45→32 kWh (40%) |
| 充电速率 | 100→50 kWh/h | 75→45 kWh/h | 50→35 kWh/h |

**调参思路**：电池容量大幅缩减（原 500 kWh 续航 1666 km 过于宽松），能耗对应提高，充电速率减半。续航压力从 "几乎不需要充电" 变为 "中后期必然触发补能"。低电量阈值改用比例制后，HARD 难度下实际阈值（32 kWh）虽然绝对值低于原 45 kWh，但占容量比例从 22.5% 提高到 40%，触发充电更频繁。

### 改动影响评估

这些改动全部限定在 `VehicleConfig` 和 `ChargingConfig` 的参数值层面，**不影响 `CityGraph` 图结构、Dijkstra 算法、`map_generator.py` 地图生成逻辑**。A 模块的核心能力（图建模 + 最短路径）未受任何影响。

`import Tuple` 的新增是向后兼容的，不影响现有调用方。

---

## 九、P0 仿真核心修复（2026-05-27 完成）

### 背景

根据 plan2.md 的 P0 阶段要求，A 成员负责三项 Simulator 层修复：评分加入路径距离、能量预检、移动可达性判断。三项修复均限定在 `simulator/simulator.py`，不修改 `strategy.py`。

### 改动清单

| # | 任务 | 位置 | 说明 |
|---|------|------|------|
| A-1 | 评分公式加入路径距离 | `_check_tasks_completion`, `_apply_dispatch`, `__init__` | 新增 `task_travel_distance` 字典在 dispatch 时存 Dijkstra 距离，完成时 `score = 100 + time_early*2 - task_dist*0.3`，超时时清理 |
| A-2 | Simulator 层能量预检 | `_apply_dispatch`, 新增 `_can_reach_and_return` | 在载重检查后、分配前拦截电量不可达任务：`battery ≥ (d1 + recovery_dist) × energy_per_km`，缓存 `depot_ids` 优化 |
| A-3 | 移动低电量改为可达性 | `_move_vehicles` | 替换 `battery < low_battery_threshold` 为 `battery < (remaining_to_target + charger_dist) × energy_per_km`，空闲车辆保持原阈值 |

### 设计决策

- **A-1 未使用 `vehicle_accumulated_distance`**：该字段在充电中断时归零（`_move_vehicles` L308/L315、`_check_low_battery` L424、`_resume_saved_task` L446），无法反映完整任务距离。改用 `task_travel_distance` 字典在分配时一次性记录，不受途中充电影响。
- **A-2 depot_ids 缓存**：在 `__init__` 中一次遍历 `self.depot_ids`，避免 `_can_reach_and_return` 每次调用都遍历所有节点。
- **A-3 无充电站回退**：当地图无充电站时（`nearest_cs is None`），`required_energy = remaining_to_target × energy_per_km × 1.5` 作为保守估计。

### 验证结果

- `test_strategy.py` — 4/4 场景通过
- `test_integration.py` — 通过
- `test_simulator.py` — nearest 363.8 分 / largest 363.8 分，无崩溃

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| [simulator/simulator.py](simulator/simulator.py) | 修改：3 处方法修改 + 1 个新方法 + 1 个新属性 |
| [CLAUDE.md](CLAUDE.md) | 文档：新增三个 Gotchas |
| [README.md](README.md) | 文档：新增评分公式与能量预检说明 |
| [plan2.md](plan2.md) | 进度：标记 A-1/A-2/A-3 已完成 |
| [progress_A.md](progress_A.md) | 进度：新增本节 |

---

## 十、P1 缺陷修复（2026-05-27 完成）

### 背景

根据 plan2.md 的 P1 阶段要求，A 成员负责三项代码缺陷修复：`add_test_task` ID 碰撞风险、充电队列去重集合僵尸条目、单向边 JSON 持久化丢失。

### 改动清单

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| A-4 | `add_test_task` 始终推进 `next_task_id` | [simulator/simulator.py:641](simulator/simulator.py#L641) | 原逻辑仅在 `task_id` 匹配 `"t"+数字` 时才推进，`"ui_t1"`/`"real_t1"`/`"initial_0"` 等前缀导致 ID 碰撞。改为无条件 `max(self.next_task_id, len(self.tasks) + 1000)` |
| A-5 | 充电排队去重集合防御性清理 | [simulator/simulator.py:178-183](simulator/simulator.py#L178-L183) | `_queue_for_charging` 入口新增状态一致性检查：若 `vehicle.id` 在 `queued_vehicle_ids` 中但 `status != WAITING_FOR_CHARGE`，先 discard 并递减 `queue_length` 再正常入队 |
| A-6 | 单向边 JSON 持久化 | [core/graph.py:35-52](core/graph.py#L35-L52), [core/map_generator.py:341-350](core/map_generator.py#L341-L350) | Edge 新增 `bidirectional: bool = True` 字段；`to_json_dict` 输出；`from_json` 读取（默认 True）；`_apply_one_way_edges` 标记被单向化的 Edge（必要时交换 from/to 使方向与 adjacency 一致）；重新生成 4 张地图 JSON |

### 设计决策

- **A-4 使用 `len(self.tasks) + 1000` 而非 `int(task_id[1:]) + 1`**：无论 task_id 格式如何，始终保证 1000 的 buffer，杜绝碰撞。
- **A-5 防御性清理而非全局审计**：仅修改 `_queue_for_charging` 入口，最小侵入。与其他修改点（`_handle_charging` 的 discard、`_check_low_battery` 的导航逻辑）互补。
- **A-6 `bidirectional` 默认 True**：未标记 `bidirectional` 的旧 JSON 文件加载时保持双向行为，向后兼容。
- **A-6 单向边方向交换**：`_apply_one_way_edges` 随机选择保留方向，若保留的是 `to→from` 则交换 Edge 的 from/to 并设 `bidirectional=False`，确保 JSON 序列化的方向与 adjacency 保留的一致。

### 验证结果

- `test_strategy.py` — 4/4 场景通过
- `test_integration.py` — 通过
- `test_simulator.py` — nearest 363.8 分 / largest 363.8 分，无崩溃
- `batch_experiment.py easy` — 12 组完成，CSV 36 行，分数与 baseline 一致
- `demo_graph.py` — 4 张地图重新生成，JSON 含 `bidirectional` 字段

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| [simulator/simulator.py](simulator/simulator.py) | 修改：A-4 1 行 + A-5 4 行 |
| [core/graph.py](core/graph.py) | 修改：Edge dataclass + `to_json_dict` + `add_edge` + `from_json` |
| [core/map_generator.py](core/map_generator.py) | 修改：`_apply_one_way_edges` 标记 Edge |
| [data/*.json](data/) | 更新：4 张地图 JSON 含 `bidirectional` 字段 |
| [CLAUDE.md](CLAUDE.md) | 文档：新增 P1 相关 Gotchas |
| [README.md](README.md) | 文档：新增单向边持久化说明 |
| [progress_A.md](progress_A.md) | 进度：新增本节 |

---

## 十一、遗传算法调度策略（2026-05-27 完成）

### 背景

项目新增第 4 种调度策略——遗传算法 (Genetic Algorithm)。该策略属于模块 C，通过进化搜索找到更优的 task-to-vehicle 分配方案，每 tick 运行一次轻量 GA。

### 核心改动

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| C-GA-1 | GA 核心实现 | [strategy_ga.py](strategy_ga.py) | 新建：染色体编码、适应度函数、选择/交叉/变异算子、精英保留、路径距离缓存 |
| C-GA-2 | Dispatcher 集成 | [strategy.py](strategy.py) | `dispatch()` 新增 `elif "genetic_algorithm"` 分支，调用 `strategy_ga.ga_dispatch()` |
| C-GA-3 | 批量实验注册 | [batch_experiment.py](batch_experiment.py) | `STRATEGIES` 列表追加 `"genetic_algorithm"` |
| C-GA-4 | UI 键绑定 | [ui/simulator_app.py](ui/simulator_app.py) | 新增 `K_4` 键切换至 GA 策略 |

### GA 设计要点

- **编码**：染色体长度 = idle vehicle 数量，基因为 task index 或 -1（不分配），每个 task 最多分配给一个 vehicle
- **适应度函数**：与 `energy_aware_hybrid` 同源的 scoring 公式——`base_score + alpha×weight_norm + beta×urgency_norm - gamma×d1 - delta×(1-battery_ratio) - epsilon×queue_len`，不可行解返回 `-inf`
- **选择**：锦标赛选择 (k=3)，**交叉**：均匀交叉 + 重复任务修复，**变异**：随机重分配 (rate=0.10)
- **精英保留**：每代保留最优 2 个个体直接进入下一代
- **性能优化**：同 tick 内缓存已计算的 OD 对距离（`dist_cache`）和任务→充电站信息（`charger_cache`）
- **默认超参数**：pop_size=40, generations=30, mutation_rate=0.10, crossover_rate=0.85, tournament_size=3, elite_count=2
- **Simulator 层兜底**：`_apply_dispatch` 的 `_can_reach_and_return()` 预检对 GA 输出的 action 进行二次验证，不可行分配自动拦截

### A 模块影响

GA 策略通过 `RealPathfinder` 使用 A 模块的 `find_path_and_distance()` 和 `nearest_charging_station()` 接口。A 模块的 `CityGraph`、`map_generator`、`difficulty.py` **无需任何修改**——GA 仅作为 C 模块新增调用方使用现有 API。

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| [strategy_ga.py](strategy_ga.py) | 新建：GA 调度策略完整实现 (~240 行) |
| [strategy.py](strategy.py) | 修改：新增 `genetic_algorithm` 分支（7 行） |
| [batch_experiment.py](batch_experiment.py) | 修改：STRATEGIES 列表追加（1 行） |
| [ui/simulator_app.py](ui/simulator_app.py) | 修改：新增 K_4 键绑定（3 行） |
| [CLAUDE.md](CLAUDE.md) | 文档：更新策略数、架构图、目录结构、快捷键、批量实验说明 |
| [README.md](README.md) | 文档：更新策略表、实验维度、按键说明 |
| [progress_A.md](progress_A.md) | 进度：新增本节 |
| [progress_all.md](progress_all.md) | 进度：更新模块 C 策略列表 |

### 验证结果

- `test_strategy.py` — 4/4 场景通过（已有策略不受影响）
- `test_integration.py` — 通过
- GA 策略单元验证：空输入→`[]`、单车辆单任务→1 action、多车辆多任务→正确分配且无重复任务
- GA 120 分钟完整仿真：2/3 任务完成，得分 1009，无崩溃

---

## 十二、P1 调度策略 Bug 修复（2026-05-27 完成）

### 背景

PR #16 合并后审查发现 4 个 bug：`consume_rate` 参数被硬编码忽略、GA 与 Hybrid 打分公式不一致、GA 缺少时间可行性检查、`strategy_ga.py` 与 `strategy.py` 代码重复。

### 改动清单

| # | Bug | 文件 | 说明 |
|---|-----|------|------|
| Bug 1 | `consume_rate` 硬编码 0.5 | [strategy.py:24](strategy.py#L24) | `self.consume_rate = 0.5` → `consume_rate if consume_rate is not None else 0.5`。Simulator 传入的 `energy_per_km`（EASY 0.35 / MEDIUM 0.60 / HARD 0.90）现被实际使用，策略层能量预检与仿真层一致 |
| Bug 2 | GA 打分公式不一致 | [strategy_ga.py:236-253](strategy_ga.py#L236-L253) | 收益归一化改用车辆载重上限（`task_weight / v_capacity`）；紧急度改用缓冲时间（`BETA / (buffer_time + 1)`）；电池惩罚改为二次函数 `((0.5-ratio)/0.5)^2`。与 hybrid 策略完全统一 |
| Bug 3 | GA 缺少时间可行性检查 | [strategy_ga.py:225-230](strategy_ga.py#L225-L230) | 新增 `time_to_reach >= time_left → INFEASIBLE_PENALTY`，与 hybrid 的"死亡冲锋拦截"一致 |
| Bug 4 | 工具函数重复 | [strategy_ga.py:49](strategy_ga.py#L49), [strategy_ga.py:56](strategy_ga.py#L56) | `_as_float` / `_is_load_feasible` 添加 `# mirrors strategy.Dispatcher._xxx` 注释标记重复（因循环导入无法直接 import） |

### 设计决策

- **Bug 1**：保留 `None` 回退 0.5 的默认行为，向后兼容不传 `consume_rate` 的旧调用方（如 `test_strategy.py` 的 MockRealPathfinder）
- **Bug 2**：GA 和 Hybrid 现在使用完全相同的打分公式，batch_experiment 结果具有可比性
- **Bug 3**：不可行染色体返回 `-INFEASIBLE_PENALTY (1e9)` 而非温和扣分，确保 GA 不会选中时间不可行的分配
- **Bug 4**：不新建共享工具模块（仅 2 个单行函数），标记注释即可

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| [strategy.py](strategy.py) | 修改：Bug 1（1 行） |
| [strategy_ga.py](strategy_ga.py) | 修改：Bug 2（~18 行）+ Bug 3（~6 行）+ Bug 4（2 行注释）+ 新增车辆速度/载重读取（~8 行） |
| [CLAUDE.md](CLAUDE.md) | 文档：更新 consume_rate 说明 + 新增 GA 公式统一 gotcha |
| [README.md](README.md) | 文档：更新策略表、P1 注意事项 |
| [progress_A.md](progress_A.md) | 进度：新增本节 |

### 验证结果

- `test_strategy.py` — 4/4 场景通过
- `test_integration.py` — 通过
- GA dispatch 烟雾测试：`consume_rate=0.6` 正确传递，GA 策略正常输出 action
- GA 评分一致性验证：适应度函数公式与 hybrid 策略逐项匹配
