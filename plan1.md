# Plan: 实际运行后确认的问题清单与分工（ACD 三人）

## 运行结果摘要

实际运行了全部程序，关键数据：

| 运行 | 结果 |
|------|------|
| `demo_graph.py` | ✅ 4 张地图正常生成 |
| `test_strategy.py` | ✅ 4 场景全部通过 |
| `test_integration.py` | ✅ 集成测试通过 |
| `demo_simulator_real_pathfinder.py` | ✅ EASY 端到端正常 |
| `test_simulator.py` | ✅ nearest vs largest 30min 通过 |
| `batch_experiment.py easy` | ⚠️ 见下方分析 |
| `batch_experiment.py` (单测 medium/hard) | ❌ 严重问题 |

### 批量实验真实数据（easy, 12 组）

```
scale        strategy              score     comp  to   dist    charge
small        nearest               1987.8    10    2    554.0   0
small        largest               -221.0    4     9    641.4   0
small        energy_aware_hybrid   270.0     4     7    615.8   0
medium       nearest               1637.2    10    5    661.7   0
medium       largest               -672.6    3     11   665.3   0
medium       energy_aware_hybrid   4.0       4     9    670.9   0
large        nearest               526.0     3     4    671.7   0
large        largest               -592.0    1     7    679.2   0
large        energy_aware_hybrid   634.0     4     4    688.4   0
extra_large  nearest               754.0     5     4    684.6   0
extra_large  largest               -478.0    2     7    678.5   0
extra_large  energy_aware_hybrid   762.0     5     4    674.9   0
```

### 发现的核心问题

**问题 1: `largest` 策略严重负分（-221 到 -672）**
- 在所有规模下均为负分，全策略最差
- 根因：`largest` 按重量降序分配，最大权重任务恰好是最远/最晚截止的（实验设计有远任务=重任务的偏置），车辆在路上耗时过长，大量轻量任务超时
- 修复：`largest` 需增加 deadline 意识和距离惩罚

**问题 2: EASY 难度零充电事件**
- 12 组实验，`charging_times` 全为 0
- 根因：120 kWh / 0.35 kWh/km = 342 km 续航，地图最大仅 80 节点（~100 单位宽），车辆永远不需充电
- 这是难度参数设计问题，easy 确实太 easy

**问题 3: MEDIUM 难度系统崩溃（score=-564, timeout=19）**
- 3 车 100 kWh / 0.6 kWh/km，70-100 kWh 初始
- 任务生成爆发（50%概率/5min → ~18 动态任务 + 6 初始 = 24 任务，deadline 45-90 min）
- 车辆中途电量耗尽 (0.0 kWh)，充电速度 45 kWh/h 跟不上 deadline 节奏
- 最终仅完成 6 个、超时 19 个

**问题 4: HARD 难度完全崩溃（score=-2698, completed=1, timeout=30）**
- 仅 2 辆车 (HARD count_small=2)，80 kWh 电池 / 0.9 kWh/km，初始 36-64 kWh
- 70% 生成概率 + 25-60 min deadline → 任务洪水
- 车辆几乎立刻电量不足，大量任务超时

**问题 5: 评分公式无路径距离**
- `score = 100 + time_early * 2`，只奖励早完成，不惩罚绕远路

**问题 6: `nearest`/`largest` 不做能量预检**
- 车辆被分配任务后跑到一半没电，中断去找充电站，任务超时
- `energy_aware_hybrid` 有这个检查，但 `nearest`/`largest` 没有

---

## 三人分工修复方案

---

# A 成员（A 图寻路 + B 仿真核心）

## A-1 (P0): 评分公式加入路径距离
- **文件**: `simulator/simulator.py:474`
- **现状**: `score = 100 + time_early * 2` → 只奖励时间，不奖励路径
- **修改**: `score = 100 + time_early * 2 - task_distance * 0.3`
  - `task_distance` = `vehicle_accumulated_distance[vehicle.id]`（从分配点到任务点实际行驶距离）
  - 系数 0.3 使距离惩罚与时间奖励在同一量级（10km ≈ -3 分，而 1min early = +2 分）

## A-2 (P0): 调度前增加能量可达性预检（所有策略）
- **文件**: `simulator/simulator.py:_apply_dispatch`（约 line 550）
- **现状**: `nearest`/`largest` 不检查电量能否完成任务；`energy_aware_hybrid` 做了但不完整
- **修改**: 在 `_apply_dispatch` 中，分配前调用新方法 `_can_complete_mission(vehicle, task_node)`:
  ```python
  d1 = Dijkstra(当前位置, 任务点)
  d2 = min(Dijkstra(任务点, 最近充电站), Dijkstra(任务点, 仓库))
  required = (d1 + d2) * energy_per_km
  return battery >= required
  ```
- **效果**: 电量不够的 (vehicle, task) 对直接跳过，不再无效分配

## A-3 (P0): 修复 `_move_vehicles` 中电量耗尽才找充电站的问题
- **文件**: `simulator/simulator.py:_move_vehicles` (line 278)
- **现状**: 仅比较 `battery < low_battery_threshold`，不等同于"能否到达目标+返回"
- **修改**: 改用与 A-2 一致的可达性判断。移动中不仅检测阈值，还检测 `battery < required_to_target + required_to_safety`

## A-4 (P1): `add_test_task` 始终推进 `next_task_id`
- **文件**: `simulator/simulator.py:600-607`
- **现状**: 仅 "t" 前缀推进
- **修改**: `self.next_task_id = max(self.next_task_id, len(self.tasks) + 1000)`

## A-5 (P1): 充电排队去重集合防御性清理
- **文件**: `simulator/simulator.py:106, 175-187`
- **现状**: `queued_vehicle_ids` 仅充电完成时清理
- **修改**: `_queue_for_charging` 入口增加状态一致性检查

## A-6 (P1): 单向边 JSON 存取
- **文件**: `core/graph.py:Edge`, `core/graph.py:from_json`
- **现状**: `from_json` 硬编码 `bidirectional=True`
- **修改**: Edge 新增 `bidirectional` 字段 + JSON 序列化支持

---

# C 成员（调度策略）

## C-1 (P0): `largest` 策略增加 deadline 意识（紧急修复）
- **文件**: `strategy.py:_largest_dispatch` (line 79-111)
- **现状**: 纯按重量降序，完全忽略 deadline 和距离 → 产生严重负分
- **修改**: 改为加权排序 `weight / (deadline - current_time) * distance_penalty`，或简单地在 weight 排序前先过滤掉 deadline 过紧的任务
- **最低限度修复**: 在 `_largest_dispatch` 中增加与 `nearest` 一致的距离检查，不分配车辆开不到的远任务

## C-2 (P0): `energy_aware_hybrid` 的 `current_time` 读取
- **文件**: `strategy.py:161`
- **现状**: 冗余 fallback `state.get('current_time', metrics.get('current_time', 0))`
- **修改**: `current_time = metrics.get('current_time', 0)`

## C-3 (P1): 三种策略参数调优
- **文件**: `strategy.py` 超参数
- **现状**: EASY 下 nearest(1987) >> hybrid(270) >> largest(-221)，hybrid 过于保守
- **目标**: 
  - EASY: 三种策略均正分，nearest ≈ largest > hybrid（距离优化 vs 重量优化 vs 保守）
  - MEDIUM: 差异更明显，hybrid 在充电压力下优于其他
  - HARD: hybrid 优势最明显
- **修改**: 调整 `alpha/beta/gamma/delta/epsilon`；降低 `safety_margin`；增加 `consume_rate` 敏感度

## C-4 (P1): `largest` 增加能量预检
- **说明**: A 将在 simulator 层增加统一的能量预检（A-2），C 只需在策略层确保 `_largest_dispatch` 也考虑距离

## C-5 (P2): `_get_nearest_charger_info` 缓存
- **文件**: `strategy.py:223-247`
- **现状**: 每次遍历所有充电站，重复 Dijkstra
- **修改**: 同一 tick 内缓存 task_node → (nearest_charger, distance, queue_length)

---

# D 成员（B 实验管道 + D UI/图表/README）

## D-1 (P0): 重新设计 MEDIUM/HARD 难度参数 — 让仿真可跑通
- **文件**: `core/difficulty.py`
- **现状**: MEDIUM/HARD 下 task 数量远超 fleet 处理能力，所有策略均大面积负分，实验无意义
- **分析**:
  - MEDIUM: 50%概率/5min × 180min = 18 动态任务 + 6 初始 + burst = ~28 任务，3 车各跑 3-4 趟
  - HARD: 70%概率 + burst + 2 车 + 25-60min deadline → 完全不可行
- **修改建议**:
  - MEDIUM: spawn_probability 0.5→0.35, deadline_min 45→60
  - HARD: spawn_probability 0.7→0.45, deadline_min 25→40, burst_probability 0.2→0.15
  - 或者: 减少仿真时长到 120min，减少总任务数
  - **目标**: 各难度下 nearest 应能完成 ≥50% 任务且获得正分

## D-2 (P0): 修复 UI 电池显示
- **文件**: `ui/pygame_app.py:496`
- **现状**: `f"{battery}%"` 硬编码百分比，真实 Simulator 输出 kWh 值（如 120 kWh 显示为 "120%"）
- **修改**: 判断是否有 `max_battery` 字段，有则计算 `battery/max_battery*100%`，无则原值（兼容 DemoWorld）

## D-3 (P0): UI 绘制车辆规划路径
- **文件**: `ui/pygame_app.py:draw_map`
- **现状**: Simulator 在 `get_state()` 中输出 `vehicle.path`，但 UI 未使用
- **修改**: 用半透明虚线绘制从 vehicle 当前位置沿 `path` 的路线

## D-4 (P1): 重新运行完整批量实验
- **命令**: `python batch_experiment.py all`
- **要求**: 
  - 先生成 difficulty-aware 地图（见 A-6）
  - 确保 36 行 CSV (3 difficulty × 4 scale × 3 strategy)
  - CSV 文件名: `results/experiment_results.csv`（与 plot 脚本一致）

## D-5 (P1): 更新 plot_results.py
- **文件**: `visualization/plot_results.py`
- **现状**: CSV 缺失时生成假数据，混淆视听
- **修改**: 删除 `create_sample_data()` 回退，CSV 不存在时直接报错退出

## D-6 (P1): 更新 README
- **文件**: `README.md`
- **修改**: 
  - 电池参数对齐当前 `difficulty.py` 实际值
  - 删除 "后续接入" 等过时措辞
  - 补充 `energy_aware_hybrid` 策略说明
  - 统一命令示例

## D-7 (P2): `pygame_app.py` 补充按键 3
- **现状**: 仅支持 1 (nearest) / 2 (largest)，无 3 (energy_aware_hybrid)

## D-8 (P2): `simulator_app.py` 增加 --scale 参数
- **现状**: 硬编码 `"data/small_map.json"`，只能演示 small 地图

## D-9 (P2): 测试脚本加 assert
- **文件**: `test_simulator.py`, `test_strategy.py`
- **修改**: 关键输出加 assert（score>0、completed>0 等）

---

## 实施顺序

```
Round 1 (必须): 
  A: A-1(评分) + A-2(能量预检) + A-3(移动中电量)
  C: C-1(largest修deadline) + C-2(current_time)
  D: D-1(难度参数调优) + 重跑实验验证

Round 2 (应该):
  A: A-4(task_id) + A-5(队列) + A-6(单向边JSON)
  C: C-3(调参对比) + C-4(能量预检) + C-5(缓存)
  D: D-2(电池显示) + D-3(路径绘制) + D-4(完整实验) + D-5(plot)

Round 3 (完善):
  D: D-6(README) + D-7(K_3) + D-8(--scale) + D-9(assert)

Round 4 (验收):
  全员: python batch_experiment.py all → CSV → plot → 确认36行合理
        python ui/simulator_app.py → 交互正常
        python test_*.py → 全部通过 (有assert)
```

---

## 验证标准

| # | 标准 | 负责 |
|---|------|------|
| 1 | EASY 三种策略均正分，nearest > largest≥0 | A+C |
| 2 | MEDIUM 三种策略均正分或微负，至少一种策略完成率 > 40% | A+C+D |
| 3 | HARD 至少一种策略完成率 > 20%，充电事件 > 0 | A+C+D |
| 4 | 评分 = 100 + time_early*2 - distance*0.3 | A |
| 5 | 能量预检: 不会分配电量不够的任务 | A |
| 6 | largest 在 EASY 下不产生大面积负分 | C |
| 7 | UI 电池显示正确、路径线可见 | D |
| 8 | CSV 36 行, plot 生成图表 | D |
| 9 | 三条命令可完整演示 | D |
