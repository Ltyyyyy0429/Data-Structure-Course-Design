# 项目完整技术文档

---

## 一、项目分工总览

项目由 4 人小组并行开发，分为四个模块：

### 模块 A — 地图与导航

**负责领域**：城市路网的建模 + "怎么从 A 点到 B 点走最短的路"

**核心文件**：

| 文件 | 作用 |
|------|------|
| `core/graph.py` | 图结构 + Dijkstra 最短路径算法 |
| `core/map_generator.py` | 自动生成 4 种规模的城市地图，支持 grid/cluster 拓扑、瓶颈边删除、单向边 |
| `core/difficulty.py` | EASY/MEDIUM/HARD 三档难度预设，统一控制地图/车辆/任务/充电参数 |

**核心数据结构**：
- `Node`（节点）— 地图上的一个点，可以是仓库、普通路口、充电站、任务送达点
- `Edge`（边）— 两个节点之间的道路，有长度，含 `bidirectional` 字段
- `CityGraph`（城市图）— 所有节点 + 所有道路的集合，内部用**邻接表**存储

**核心函数**：

| 函数 | 用途 | 通俗理解 |
|------|------|----------|
| `CityGraph.dijkstra(start, end)` | Dijkstra 最短路径 | "高德导航：从起点到终点，走哪条路最近" |
| `CityGraph.nearest_node(start, "charging")` | 找最近的充电站 | "车快没电了，最近的充电桩在哪" |
| `CityGraph.from_json(file)` | 从文件加载图 | "把事先画好的地图读进程序" |
| `CityGraph.to_state_nodes/edges()` | 导出给 UI 画图 | "把地图数据转换成画布能画的形式" |

**涉及的算法**：
- **Dijkstra 最短路径**：O((V+E)log V)，用最小堆优先队列，找到达终点立刻停止
- **连通性保证生成**：新节点强制连到离它最近的已有节点（类似 Prim 思想），防止出现"孤岛"
- **瓶颈边删除**：临时删边 + Dijkstra 验证替代路径，只删不影响连通性的冗余边
- **单向边转换**：对仍有替代路径的边进行单向化，标记 `bidirectional=False`

---

### 模块 B — 仿真引擎

**负责领域**：让整个世界"跑起来"——时间一步一步走，车辆移动、耗电、充电、任务超时。

**核心文件**：

| 文件 | 作用 |
|------|------|
| `simulator/simulator.py` | 仿真引擎核心，事件循环 |
| `simulator/models.py` | 数据模型（车辆/任务/充电站/指标） |
| `simulator/task_generator.py` | 动态生成新任务（支持突发爆单） |
| `simulator/pathfinder_adapter.py` | A 和 B 之间的翻译官（封装 CityGraph） |

**核心函数**：

| 函数 | 用途 |
|------|------|
| `RealPathfinder.find_path_and_distance(start, end)` | 规范寻路入口（唯一），内部调 `CityGraph.shortest_path()` |
| `Simulator.update(dt)` | 每个时间步执行一次 |
| `_move_vehicles(dt)` | 让车辆沿路径移动、耗电 |
| `_check_low_battery()` | 检测低电量车辆（移动中车辆使用可达性检查，空闲车辆使用绝对阈值） |
| `_handle_charging(dt)` | 充电逻辑（速率+排队），含防御性去重清理 |
| `_generate_new_tasks(dt)` | 随机产生新任务（支持 burst 突发模式与空间聚集） |
| `_dispatch_tasks()` | 调用策略模块分配任务 |
| `_apply_dispatch()` | 执行分配：能量预检（`_can_reach_and_return`）、载重二级防御 |
| `get_state()` | 导出当前世界状态 |

**关键设计**：
- **能量预检**：分配任务前检查车辆电量是否足够到达任务 + 安全返回最近的充电站或仓库
- **评分公式**：`score = 100 + time_early * 2 - task_distance * 0.3`，task_distance 通过 Dijkstra 预计算
- **载重二级防御**：策略层 + Simulator 层双重检查
- **充电排队去重**：`_queue_for_charging` 入口增加状态一致性检查，防止僵尸条目

---

### 模块 C — 调度策略

**负责领域**：决定"哪辆车该去送哪个任务"——项目核心智力所在。

**核心文件**：`strategy.py` + `strategy_ga.py`

**四种策略**：

| 策略 | 函数 | 通俗描述 |
|------|------|----------|
| 最大任务优先 | `_largest_dispatch()` | "哪个包裹最重就先送哪个" |
| 最近任务优先 | `_nearest_dispatch()` | "离我最近的那个任务，我去" |
| 能量感知综合 | `_energy_aware_hybrid_dispatch()` | "综合考虑收益、紧急度、距离、电量风险、充电排队" |
| 遗传算法 | `strategy_ga.ga_dispatch()` | "进化搜索最优分配：种群 40、30 代、锦标赛选择、均匀交叉" |

策略输出的 action 格式是统一的：

```python
{
    'vehicle_id': 'v1',
    'task_id': 't42',
    'action': 'assign',
    'path': [0, 3, 7, 9]  # Dijkstra 预计算好的路径，B 直接用
}
```

**路径预计算**：策略层调 `pathfinder.find_path_and_distance()` 一次性算出完整路径，放进 action 的 `path` 字段。Simulator 的 `_apply_dispatch()` 直接用，不再重复算，消除了双重 Dijkstra。

`Dispatcher.__init__` 接收 `consume_rate` 参数（由 Simulator 传入实际的 `energy_per_km` 值），确保策略层的能量硬门槛与实际仿真能耗一致。**P1 修复（2026-05-27）**：原先该参数虽被接受但硬编码为 0.5，现已修复为真正使用传入值。

`strategy_ga.py` 为独立 GA 实现文件。GA 适应度函数与 hybrid 策略使用统一的百分制打分公式（车辆载重归一化、缓冲时间紧急度、二次电池惩罚、死亡冲锋硬约束），保证实验结果可比性。两个文件共享相同的 `RealPathfinder` 接口和 `state` 字典契约。`_as_float` / `_is_load_feasible` 因避免循环导入而各自保留（已标记 mirror 注释）。

---

### 模块 D — 可视化

**负责领域**：把仿真过程变成能看的图和表。

**核心文件**：

| 文件 | 作用 |
|------|------|
| `ui/pygame_app.py` | 假数据原型 UI |
| `ui/simulator_app.py` | 真实 UI，连 B 的 Simulator，支持 `--difficulty` 参数 |
| `ui/state_adapter.py` | 格式兼容层，统一所有命名差异 |
| `visualization/plot_results.py` | 读实验结果 CSV，画柱状对比图 |

`state_adapter.py` 的 `normalize_state()` 是所有命名差异的统一修复点：
- `depot` → `warehouse`
- `charging_station` → `charging`
- `from_node`/`to_node` → `from`/`to`
- 给只有 `node_id` 的车/任务补充 `x`/`y` 坐标

---

## 二、A 模块三个文件的配合关系

用一句话概括：**difficulty 是总指挥 → map_generator 按指令盖路网 → graph 提供数据结构和导航算法**

```
                    ┌─────────────────────────┐
                    │    core/difficulty.py    │  总指挥
                    │                         │
                    │  get_difficulty_config(  │
                    │    scale, difficulty)    │
                    │       ↓                  │
                    │  返回 DifficultyConfig:  │
                    │  ├─ MapConfig            │──→ map_generator 用它决定：
                    │  ├─ VehicleConfig        │    拓扑(grid/cluster)、瓶颈比例、
                    │  ├─ TaskConfig           │    单向边比例、充电站分布
                    │  └─ ChargingConfig       │
                    └──────────┬──────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
│ map_generator.py │  │  graph.py    │  │  Simulator (B模块) │
│                  │  │              │  │  使用 Vehicle/     │
│ 按 MapConfig     │  │ 提供给你     │  │  Task/Charging    │
│ 生成节点和边     │  │ 建好的图     │  │ 配置              │
│    │             │  │    ▲         │  │                   │
│    └──► CityGraph ──┘    │         │  └──────────────────┘
│         (add_node,        │         │
│          add_edge)   graph.py 就是  │
│                      存储引擎     │
└────────────────────────────────────┘
```

### 具体配合流程

**Step 1**：`difficulty.py` 的 `get_difficulty_config("small", "hard")` 返回一个装满参数的 `DifficultyConfig` 对象

```python
config = get_difficulty_config("small", "hard")
# config.map.cluster_mode = "cluster"
# config.map.bottleneck_fraction = 0.20
# config.map.one_way_fraction = 0.10
# config.map.seed = 202601
# config.vehicle.battery_capacity_kwh = 80.0
# ... 等等
```

**Step 2**：`map_generator.generate_map_from_config(config.map)` 用 `MapConfig` 生成图

```python
graph = generate_map_from_config(config.map)
# graph 是一个完整的 CityGraph 对象，包含：
#   graph.nodes = {0: warehouse, 1: normal, 3: charging, ...}
#   graph.adjacency = {0: [(1, 45.2), (3, 32.1), ...], ...}
#   graph.edges = [Edge(0→1), Edge(0→3), ...]
```

**Step 3**：`graph.py` 的 `CityGraph` 是纯数据 + 算法层，不知道难度、不知道地图生成

```python
# map_generator 调 graph 的建造方法
graph.add_node(Node(id=0, x=8.0, y=50.0, type="warehouse"))
graph.add_edge(0, 1, bidirectional=True)  # graph 会自动计算距离、填邻接表

# B/C 模块调 graph 的查询方法
path, dist = graph.shortest_path(0, 5)       # Dijkstra
nearest, d = graph.nearest_node(3, "charging")  # 找最近充电站
```

**Step 4**：`difficulty.py` 的 `VehicleConfig/TaskConfig/ChargingConfig` 则直接传给 B 模块的 `Simulator`，控制车辆参数、任务节奏、充电速度

---

## 三、A 模块三个文件核心函数全解

### graph.py — 图结构与最短路径

#### 建图函数

| 函数 | 行号 | 做了什么 |
|------|------|----------|
| `add_node(node)` | 63-70 | 注册一个节点到 `self.nodes` 字典，同时在 `self.adjacency` 里给它开一个空邻居列表 |
| `add_edge(from, to, distance, bidirectional)` | 72-102 | 1) 没传距离就用欧几里得算 2) 往邻接表里加 `from→to` 3) 如果是双向的再加 `to→from` 4) 往 `self.edges` 列表里追加一条 Edge 对象（**只存一份**，不存两个方向） |
| `_add_neighbor(from, to, dist)` | 265-273 | 往邻接表 `from` 的邻居列表里加 `to`，如果已有则更新距离（不重复） |

#### 查询函数

| 函数 | 行号 | 做了什么 |
|------|------|----------|
| `get_node(node_id)` | 104-107 | 查一个节点 |
| `get_neighbors(node_id)` | 109-112 | 返回某节点的所有邻居 `[(邻居ID, 距离), ...]`，返回副本防止外部修改 |

#### 核心算法

**`dijkstra(start_id, end_id)` — graph.py:123-170**

```
准备阶段:
  distances = 所有节点距离都是 ∞
  previous  = 所有节点的前驱都是 None
  distances[起点] = 0
  优先队列 = [(0, 起点)]

循环（直到队列空）:
  弹出当前距离最小的节点 current
  如果 current 已经访问过 → 跳过
  标记 current 已访问

  如果 current == 终点 → 提前结束！（不是遍历全图）

  遍历 current 的每个邻居:
    新距离 = current距离 + 边距离
    如果 新距离 < distances[邻居]:
      更新 distances[邻居] = 新距离
      记录 previous[邻居] = current
      把 (新距离, 邻居) 塞入优先队列

不可达: 返回 ([], ∞)
否则: 从 previous 回溯出完整路径
```

**`nearest_node(start_id, node_type)` — graph.py:172-201**

和 Dijkstra 几乎一样，唯一的区别在于**出队时的检查逻辑**：

```
Dijkstra:    出队时检查 "是不是终点？"
nearest_node: 出队时检查 "这个节点的类型是不是我要找的？"

因为 Dijkstra 按距离递增出队，第一个匹配的节点一定是最近的！
```

#### 序列化函数

| 函数 | 行号 | 用途 |
|------|------|------|
| `from_json(file_path)` | 220-249 | 从 JSON 文件加载图。**双格式兼容**：边字段既认 `"from"/"to"`（A 输出格式），也认 `"from_node"/"to_node"`（B 格式），不会因为命名差异崩掉 |
| `save_json(file_path)` | 251-263 | 把当前图存成 JSON，节点按 ID 排序，边用 `"from"/"to"` 格式，含 `bidirectional` 字段 |
| `to_state_nodes()` | 203-213 | 把节点转成 state 字典格式：`{node_id: {x, y, type}}`，供 UI 画地图 |
| `to_state_edges()` | 215-218 | 把边转成 `[{"from":..., "to":..., "distance":...}]` 格式 |

---

### map_generator.py — 地图生成

#### 入口函数

| 函数 | 行号 | 做了什么 |
|------|------|----------|
| `generate_small_map()` | 30-32 | 固定参数调 `_generate_map(10节点, 2充电站, seed=202601)` |
| `generate_medium_map()` | 35-37 | 同理，30节点/4充电站/seed=202602 |
| `generate_large_map()` | 40-42 | 60节点/6充电站/seed=202603 |
| `generate_extra_large_map()` | 45-47 | 80节点/8充电站/seed=202604 |
| `generate_all_maps()` | 50-61 | 一次性生成全部 4 张 + 保存 JSON 到 `data/` |
| `generate_map_from_config(config)` | 68-87 | **难度感知入口**：读 `MapConfig.cluster_mode` 决定走 grid 还是 cluster，然后在生成后的图上应用瓶颈删除和单向边转换 |

#### Grid 模式建图 — `_build_grid_graph()` (行 123-137)

```
步骤 1: 选哪些节点是充电站（_choose_charging_ids）
步骤 2: 生成节点坐标并 add_node
   - 节点 0 = 仓库，固定在 (8, 50)
   - 节点 1~N-1 = 网格排列 + 随机抖动
步骤 3: 建边（_build_base_edges）
```

#### Cluster 模式建图 — `_build_cluster_graph()` (行 144-188)

```
步骤 1: 确定簇的数量（约 node_count/15，3~6 个）
步骤 2: 随机放置簇中心坐标
步骤 3: 每个节点随机分配到某个簇（节点 0 仓库永远在簇 0）
步骤 4: 选充电站节点
步骤 5: 每个节点按其簇中心 + 大幅抖动（jit*3）生成坐标
步骤 6: 建边（_build_cluster_edges，三阶段）
```

#### 建边逻辑对比（理解 grid vs cluster 最关键的部分）

**Grid 的 `_build_base_edges()` — 行 240-260**

```
Phase 1: 连通性保证
  对于节点 1, 2, 3, ..., N-1:
    从 0~(i-1) 中找离节点 i 欧几里得距离最近的，连一条边
  效果：保证全图连通，不可能有孤立节点

Phase 2: 路网稠密化
  对于每个节点 i:
    找离它最近的 K 个邻居（K = extra_neighbors），各连一条边
  效果：图从"树状"变成"网状"，有冗余路径
```

**Cluster 的 `_build_cluster_edges()` — 行 191-233**

```
Phase 1: 连通性保证（优先同簇）
  对于节点 1, 2, ..., N-1:
    从前 i-1 个节点里找同簇的，选最近的一个连边
    如果 i 是自己簇里的第一个节点 → 退化为从所有前驱里找最近

Phase 2: 簇内密集连接
  对于每个节点 i:
    在同簇节点中找最近的 K 个，连边
  效果：每个簇内部道路很密集

Phase 3: 簇间桥接（每对簇至少 1 条）
  遍历每对簇 (c1, c2):
    找两个簇之间欧几里得距离最近的那对节点，连一条桥接边
  效果：簇与簇之间只有 1 条"咽喉要道"
```

这就是 cluster 难度高的原因——簇内怎么走都行，但**跨簇只有一条路**，瓶颈边删除 + 单向化后，可能整个簇被孤立。

#### 后处理：瓶颈删除 + 单向边

**`_apply_bottlenecks()` — 行 266-310**

```
对于每条边:
  临时删掉它的两个方向
  用 Dijkstra 检查两端是否还有别的路能通
  如果能通 → 这条边是"冗余边"，可以删
  恢复

从可删边中按 bottleneck_fraction 比例随机抽一批，永久删除
```

核心安全逻辑：**只删"删了也不会让图不连通"的边**，通过临时删边 + Dijkstra 验证替代路径来保证。

**`_apply_one_way_edges()` — 行 313-347**

```
对于每条边:
  临时删掉 a→b 方向
  检查 a 是否还能到达 b（走别的路线）
  如果能 → 这条边可以单向化
  恢复

从可单向化的边中按比例随机抽一批
对每条抽中的边，随机决定保留 a→b 还是 b→a
标记 bidirectional=False，必要时交换 from/to 使方向与邻接表一致
```

#### 充电站分布策略

| 函数 | 行号 | 策略 | 效果 |
|------|------|------|------|
| `_choose_charging_ids_uniform()` | 373-387 | 均匀分布 | 按步长 `(N-1)/(k+1)` 把充电站均匀撒在节点 ID 序列上 |
| `_choose_charging_ids_clustered()` | 390-421 | 聚集分布 | 随机选一个锚点，充电站全部集中在锚点周围 ±spread 范围内，形成"充电荒漠"区域 |
| `_choose_charging_ids_scarce()` | - | 稀缺分布 | 减少数量 + 随机散布 |

---

### difficulty.py — 难度与规模配置

`difficulty.py` 是一个**工厂函数 + 三档预设表**：

```
get_difficulty_config(scale, difficulty)
  │
  ├─ 查 _SCALE_MAP_PARAMS[scale] → 拿到 node_count, charging_count, extra_neighbors, seed
  │
  ├─ 根据 difficulty 调 _map_config_for()     → MapConfig（拓扑、瓶颈、单向、充电分布）
  ├─ 根据 difficulty 调 _vehicle_config_for() → VehicleConfig（电池、能耗、速度、车辆数、低电量阈值比例、初始电量范围比例）
  ├─ 根据 difficulty 调 _task_config_for()    → TaskConfig（任务概率、截止时间、突发概率）
  └─ 根据 difficulty 调 _charging_config_for() → ChargingConfig（充电速率、端口数）
```

**各难度参数总览**：

| 参数 | EASY | MEDIUM | HARD |
|------|------|--------|------|
| 拓扑模式 | grid | grid | cluster |
| 瓶颈比例 | 0% | 10% | 20% |
| 单向边比例 | 0% | 5% | 10% |
| 充电分布 | uniform | uniform | clustered |
| 电池容量 | 120 kWh | 100 kWh | 80 kWh |
| 单位能耗 | 0.35 kWh/km | 0.60 kWh/km | 0.90 kWh/km |
| 低电量阈值 | 20% (24 kWh) | 30% (30 kWh) | 40% (32 kWh) |
| 初始电量 | 90%-100% | 70%-100% | 45%-80% |
| 车辆数(s/m/l/xl) | 3/3/3/3 | 3/3/3/3 | 2/3/4/5 |
| 任务概率 | 0.30 | 0.35 | 0.40 |
| 截止时间 | 60-120 min | 65-90 min | 45-60 min |
| burst 概率 | 0% | 8% | 12% |
| 充电速率 | 50 kWh/h | 45 kWh/h | 35 kWh/h |
| 每站端口 | 2 | 2 | 1 |

**VehicleConfig 关键设计**：

- `low_battery_threshold_ratio`（比例值）替代了原来的绝对 kWh 值，通过 `low_battery_threshold_kwh()` 方法计算 `capacity × ratio`，调整电池容量时阈值自动缩放
- `initial_battery_min_ratio` / `initial_battery_max_ratio` + `initial_battery_range_kwh()` 方法控制车辆初始电量的随机范围
- 各难度参数经过调优：电池容量 80~120 kWh、充电速率 35~50 kWh/h，补能压力随难度自然递增

**`MapConfig` 同时控制 `map_generator` 的行为和 `Simulator` 的参数。** `VehicleConfig`/`TaskConfig`/`ChargingConfig` 则直接传给 B 模块的 `Simulator`，难度系统因此能**统一调控**从地图生成到仿真运行的所有环节。

---

## 四、A 模块完整函数调用关系图

```
外部调用方                     A 模块内部
══════════                   ════════════

demo_graph.py ──► generate_all_maps()
                      │
                      ├─► generate_small_map()
                      ├─► generate_medium_map()     每个都走:
                      ├─► generate_large_map()       _generate_map()
                      └─► generate_extra_large_map()     │
                                                         ├─► CityGraph() (新建)
batch_experiment.py 或                                   ├─► _grid_position()
simulator_app.py                                         ├─► Node(...).add_node()
    │                                                    ├─► _choose_charging_ids()
    ├─► get_difficulty_config()                          ├─► _build_base_edges()
    │       │                                                │
    │       └─► MapConfig / VehicleConfig / ...              ├─ 1. 连通性: 连到最近前驱
    │                                                       └─ 2. 稠密化: 连K个最近邻
    └─► generate_map_from_config(config.map)
            │                                         ── 或者 ──
            ├─ cluster_mode="grid"
            │   └─► _build_grid_graph()              _build_cluster_graph()
            │                                           │
            └─ cluster_mode="cluster"                   ├─ 1. 同簇连通
                └─► _build_cluster_graph()              ├─ 2. 簇内KNN
                    └─► _build_cluster_edges()          └─ 3. 簇间桥接
                         │
                    后处理:
                    ├─► _apply_bottlenecks()  删冗余边
                    └─► _apply_one_way_edges() 变为单行道

B/C 模块通过 RealPathfinder 调用:
    pathfinder.find_path_and_distance(start, end)  ──► graph.shortest_path() ──► dijkstra() ──► _rebuild_path()
    pathfinder.nearest_charging_station(start)     ──► graph.nearest_node(start, "charging") ──► 改进Dijkstra
    graph.save_json(path)                          ──► 导出 JSON
    graph.from_json(path)                          ──► 从 JSON 加载
```

---

## 五、关键概念速查

| 概念 | 文件位置 | 一句话解释 |
|------|----------|-----------|
| `Node` | `core/graph.py:20` | 地图上的一个点，4 种类型：warehouse/normal/charging/task |
| `Edge` | `core/graph.py:35` | 两点之间的道路，只存一份但邻接表有双向。含 `bidirectional` 字段 |
| `CityGraph` | `core/graph.py:55` | 邻接表图，包含节点字典 + 邻居列表 + 边列表 |
| `_build_base_edges()` | `core/map_generator.py:240` | Grid 模式的二阶段建边：连通性保证 + KNN 稠密化 |
| `_build_cluster_edges()` | `core/map_generator.py:191` | Cluster 模式的三阶段建边：同簇连通 + 簇内KNN + 簇间桥接 |
| `_apply_bottlenecks()` | `core/map_generator.py:266` | 删冗余边制造瓶颈（只删不影响连通性的边） |
| `_apply_one_way_edges()` | `core/map_generator.py:313` | 把部分边变单行道（只变仍有替代路径的边），标记 bidirectional=False |
| `DifficultyConfig` | `core/difficulty.py:84` | 聚合四个子配置，统一控制地图/车辆/任务/充电 |
| `RealPathfinder` | `simulator/pathfinder_adapter.py:20` | A 到 B/C 的桥梁，持有 CityGraph，提供所有寻路服务 |

---

## 六、关键修复记录

以下修复在 P1 阶段（2026-05-27）完成，记录于此供后续开发参考：

| 修复项 | 描述 |
|--------|------|
| **consume_rate 硬编码修复** | `Dispatcher.__init__` 原先接受 `consume_rate` 参数但硬编码为 0.5，现已正确使用 Simulator 传入的实际 `energy_per_km`（EASY 0.35 / MEDIUM 0.60 / HARD 0.90）。GA 策略同步受益。 |
| **GA 与 Hybrid 打分统一** | `strategy_ga.py` 适应度函数与 `strategy.py` 的 `_energy_aware_hybrid_dispatch` 使用相同的百分制打分公式——收益归一化用车辆载重上限、紧急度用缓冲时间（扣除赶路时间）、电池惩罚用二次函数。 |
| **VehicleConfig 比例制** | `low_battery_threshold_kwh` 从绝对 kWh 改为比例制（`low_battery_threshold_ratio`），通过 `capacity × ratio` 计算。新增 `initial_battery_min_ratio` / `initial_battery_max_ratio` 控制初始电量范围。 |
| **Simulator 层能量预检** | `_apply_dispatch()` 分配任务前调用 `_can_reach_and_return()`，检查电量是否足够到达任务 + 安全返回最近充电站或仓库。nearest/largest 作为 baseline 照常输出，Simulator 层统一拦截不可行分配。 |
| **移动中低电量改为可达性检查** | `_move_vehicles` 不再仅比较 `battery < threshold` 绝对值，而是计算 `remaining_to_target + charger_dist × energy_per_km` 作为所需电量。 |
| **充电排队去重防御** | `_queue_for_charging` 入口增加状态一致性检查——若车辆已在队列中但状态不对，先清理再入队，防止僵尸条目。 |
| **Edge bidirectional 字段** | `Edge` dataclass 新增 `bidirectional: bool = True`，单向边标记 `bidirectional=False` 并在必要时交换 from/to。 |
| **GA 死亡冲锋硬约束** | GA 包含时间可行性预检：若赶路时间已超过 deadline 剩余时间，该分配直接判不可行，与 hybrid 策略一致。 |
| **任务 ID 碰撞防护** | `add_test_task` 始终执行 `self.next_task_id = max(self.next_task_id, len(self.tasks) + 1000)`，确保 UI 手动加任务与自动生成任务 ID 不碰撞。 |
| **TaskGenerator 已实现** | `simulator/task_generator.py` 不再是死代码。Simulator 在提供 `config` 时会构造 `TaskGenerator` 实例并委托任务生成。 |
| **车辆数覆盖 Bug 修复 (2026-05-28)** | `simulator/simulator.py` 第 96-102 行无条件覆盖难度配置中的车辆数为 5/10/15，导致 HARD 难度车辆数被抬高 2-4 倍、策略差异被抹平。修复方式：将规模覆盖移入 `else` 分支（无 config fallback），有 config 时 `vc.count_for_scale(scale)` 原样生效。 |
