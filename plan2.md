# Plan2: 修复方案（nearest/largest 不做策略层修改）

## 核心约束

**`nearest` 和 `largest` 策略代码不动**——它们作为 baseline 参考策略保留。`largest` 产生负分是其特征（证明纯重量优先不可行），在报告中用于对比分析。策略层仅改进 `energy_aware_hybrid`。

---

## 实际运行数据（来自 plan1 验证）

### EASY 批量实验（12 组）
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

### 单测 MEDIUM/HARD
- MEDIUM nearest: score=-564, completed=6, timeout=19
- HARD nearest: score=-2698, completed=1, timeout=30

### 发现的真实问题
1. **评分公式无路径距离** → 只奖时间不奖路径
2. **Simulator 层不做能量预检** → nearest/largest 分配了电量不够的任务，车辆跑一半没电
3. **EASY 零充电** → 120kWh/0.35 = 342km 续航，地图太小永不需要充电
4. **MEDIUM/HARD 任务洪水** → 生成率远超车队处理能力
5. **hybrid 过于保守** → EASY 下得分远低于 nearest
6. **UI 电池显示 kWh 为百分比**、**无规划路径线**
7. **单向边 JSON 存取丢失**、**add_test_task next_task_id**

---

# A 成员（A 图寻路 + B 仿真核心）

## A-1 (P0) ✅ 评分公式加入路径距离 — 已完成
- **文件**: `simulator/simulator.py`
- **修改**: `score = 100 + time_early * 2 - task_distance * 0.3`
- **实现**: 新增 `self.task_travel_distance` 字典，在 `_apply_dispatch` 分配时通过 Dijkstra 计算路径距离并存储，`_check_tasks_completion` 完成时取出使用，超时时清理
- **与计划的差异**: 未使用 `vehicle_accumulated_distance`（充电中断会归零），改用 `task_travel_distance` 字典存储，不受途中充电影响

## A-2 (P0) ✅ Simulator 层统一能量预检 — 已完成
- **文件**: `simulator/simulator.py`
- **修改**: 新增 `_can_reach_and_return(vehicle, task_node_id)` 方法，在 `_apply_dispatch` 载重检查之后、任务分配之前插入能量预检
- **实现**: 缓存 `self.depot_ids` 避免每次遍历节点；`recovery_dist = min(充电站距离, 仓库距离)`；不修改 `strategy.py`
- **效果**: nearest/largest 均受益于物理约束

## A-3 (P0) ✅ `_move_vehicles` 低电量判断改为可达性 — 已完成
- **文件**: `simulator/simulator.py:_move_vehicles`
- **修改**: 替换 `if vehicle.battery < self.low_battery_threshold` 为可达性检查
- **实现**: `required_energy = (remaining_to_target + charger_dist) * energy_per_km`；`remaining_to_target = max(0, _get_distance(current_node, target_node) - accumulated_distance)`；无充电站时回退为 `remaining * 1.5 * energy_per_km`
- **注意**: `_check_low_battery`（空闲车辆）保持原绝对阈值检查不变

## A-4 (P1) ✅ `add_test_task` 推进 `next_task_id` — 已完成
- **文件**: `simulator/simulator.py:641`
- **修改**: 无论 task_id 格式，始终 `self.next_task_id = max(self.next_task_id, len(self.tasks) + 1000)`

## A-5 (P1) ✅ 充电排队去重集合防御性清理 — 已完成
- **文件**: `simulator/simulator.py:178-183`
- **修改**: `_queue_for_charging` 入口增加：若 `vehicle.id in queued_vehicle_ids` 但 `vehicle.status != WAITING_FOR_CHARGE`，先 discard 并递减 queue_length，再正常入队

## A-6 (P1) ✅ 单向边 JSON 持久化 — 已完成
- **文件**: `core/graph.py:Edge(46)`, `core/graph.py:from_json(248)`, `core/map_generator.py:341-350`
- **修改**: Edge 新增 `bidirectional: bool = True`；`_apply_one_way_edges` 标记被单向化的边（必要时交换 from/to）；`to_json_dict` 输出；`from_json` 读取（默认 True 向后兼容）；4 张地图 JSON 已重新生成

---

# C 成员（调度策略，仅改 energy_aware_hybrid）

## C-1 (P0) 清理 `current_time` 读取
- **文件**: `strategy.py:161`
- **修改**: `current_time = metrics.get('current_time', 0)`（去掉冗余 fallback）

## C-2 (P0) energy_aware_hybrid 参数调优 — 拉开与 baseline 差距
- **文件**: `strategy.py` 超参数 (line 27-31)
- **目标**:
  - EASY: hybrid 应正分（不追求超过 nearest，但不应为负）
  - MEDIUM: hybrid 应明显优于 nearest（充电压力下保守策略更合理）
  - HARD: hybrid 应远优于 nearest（能量预检 + 排队意识关键）
- **调参方向**:
  - 降低 `safety_margin`（当前 5.0 → 2.0）：hybrid 过于保守
  - 降低 `delta`（电量风险惩罚 50.0 → 20.0）：电池比例归一化后风险惩罚偏大
  - 调整 `gamma`（距离惩罚 0.5 → 0.3）：与 A-1 评分中的距离惩罚对齐
- **验证**: 跑 `batch_experiment.py medium`，对比三策略得分

## C-3 (P1) `_get_nearest_charger_info` 性能优化
- **文件**: `strategy.py:223-247`
- **修改**: 同一 tick 内缓存 `task_node → (charger_node, dist, queue_length)`，避免每个候选(vehicle, task) 都遍历所有充电站做 Dijkstra

## C-4 (P2) 进阶算法（加分项，时间允许）
- 可在报告中对比 hybrid 与 baseline 的设计差异（能量预检、排队惩罚、综合加权）
- 不需要实现新算法，充分展示 hybrid 的设计思想即可

---

# D 成员（B 实验管道 + D UI/图表/README）

## D-1 (P0) 难度参数重平衡 — 让 MEDIUM/HARD 可跑通
- **文件**: `core/difficulty.py`
- **现状**: MEDIUM/HARD 下任务数远超车队能力，所有策略（含 nearest）均崩溃
- **分析**:
  - MEDIUM: 50% × (180/5) = 18 动态任务 + 6 初始 + burst = ~26 任务 vs 3 车，deadline 45-90 min
  - HARD: 70% × (180/5) = 25 动态 + 6 初始 + burst = ~33 任务 vs 2 车，deadline 25-60 min
- **建议新参数**:
  - MEDIUM: `spawn_probability: 0.50 → 0.35`, `deadline_min: 45 → 65`, `burst_probability: 0.10 → 0.08`
  - HARD: `spawn_probability: 0.70 → 0.40`, `deadline_min: 25 → 45`, `burst_probability: 0.20 → 0.12`
  - **目标**: 每种难度下 nearest 应完成 ≥ 4 个任务且总分正

## D-2 (P0) UI 电池显示修复
- **文件**: `ui/pygame_app.py:496`
- **修改**: 检测 `max_battery` 字段 → 计算百分比；无此字段 → 保留原值

## D-3 (P0) UI 绘制车辆规划路径
- **文件**: `ui/pygame_app.py:draw_map`
- **修改**: 读取 `vehicle.get('path', [])`，用半透明线绘制从当前位置沿路径的连线

## D-4 (P1) 重新运行完整批量实验
- **前提**: A-6 完成后生成 difficulty-aware 地图
- 跑 `python batch_experiment.py all` → 输出 `results/experiment_results.csv`
- 预期: 36 行，各难度下 nearest/largest/hybrid 均合理

## D-5 (P1) plot_results.py 删除假数据回退
- **文件**: `visualization/plot_results.py:74-82`
- **修改**: 删除 `create_sample_data()` 调用，CSV 不存在时报错退出

## D-6 (P1) README 更新
- **文件**: `README.md`
- 电池参数对齐 `difficulty.py` 实际值、删除过时措辞、补充 hybrid 说明

## D-7 (P2) pygame_app 补充 key=3
- 假数据 UI 按键 3 切换 `energy_aware_hybrid`

## D-8 (P2) simulator_app 增加 --scale 参数
- 允许切换地图规模演示

## D-9 (P2) 测试脚本加 assert
- `test_simulator.py` / `test_strategy.py` 关键输出加 assert

---

## nearest/largest 不改的理由

| 策略 | 保留的原因 | 报告中的定位 |
|------|-----------|-------------|
| `nearest` | 纯距离贪心，正确的 baseline | "朴素贪心：只顾眼前最近" |
| `largest` | 纯重量贪心，暴露盲目追求大单的问题 | "朴素贪心：只挑最大包裹，忽视距离和时效" |
| `energy_aware_hybrid` | 综合优化，体现进阶设计 | "综合调度：能量感知+紧急度+排队意识" |

三者对比恰好体现了调度策略从 naive → sophisticated 的进化，是报告的天然素材。

---

## 实施顺序

```
Round 1 (P0):
  A: A-1(评分) + A-2(Simulator层能量预检) + A-3(移动电量)
  C: C-1(current_time) + C-2(hybrid调参)
  D: D-1(难度参数)

Round 2 (P1):
  A: A-4(task_id) + A-5(队列) + A-6(单向边)
  C: C-3(缓存)
  D: D-4(批量实验) + D-5(plot) + D-6(README)

Round 3 (P2):
  D: D-7(K_3) + D-8(--scale) + D-9(assert)

Round 4 (验收):
  全员: batch_experiment.py all → CSV → plot → 验证
        test_*.py → 全部通过
        simulator_app.py → 交互演示
```

---

## 验证标准

| # | 标准 | 负责 |
|---|------|------|
| 1 | EASY: nearest 正分, hybrid 正分（不要求超过 nearest） | A+C+D |
| 2 | MEDIUM: nearest≥0, hybrid > nearest（充电压力下体现优势） | A+C+D |
| 3 | HARD: hybrid 正分且 > nearest（能量意识关键场景） | A+C+D |
| 4 | 评分 = 100 + time_early*2 - distance*0.3 | A |
| 5 | Simulator 层能量预检生效，不分配不可达任务 | A |
| 6 | 三种难度均有充电事件 | D |
| 7 | UI: 电池显示正确、路径线可见 | D |
| 8 | CSV 36 行完整, plot 图表合理 | D |
| 9 | largest 保持纯重量贪心（可作为报告对比素材） | C |
