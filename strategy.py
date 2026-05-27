# strategy.py
from __future__ import annotations

import math
from typing import TYPE_CHECKING, List, Dict, Any, Tuple, Optional

if TYPE_CHECKING:
    from simulator.pathfinder_adapter import RealPathfinder


class Dispatcher:
    def __init__(
        self,
        pathfinder: RealPathfinder,
        strategy_name: str = "energy_aware_hybrid",
        consume_rate: float = None,
        load_capacity: float = 1000.0,
        cooperative_mode: bool = False,          # 新增：协同模式开关
    ):
        """
        初始化调度中心
        :param pathfinder: RealPathfinder 实例 (用于计算最短路径)
        :param strategy_name: 调度策略，支持 "nearest" (最近优先)、"largest" (最大权重优先) 和 "energy_aware_hybrid" (能量感知综合调度)
        :param load_capacity: 默认最大载重容量
        :param cooperative_mode: 是否允许多辆车协同完成同一任务 (当单辆车载重不足时)
        """
        self.pathfinder = pathfinder
        self.strategy_name = strategy_name
        self.load_capacity = load_capacity
        self.cooperative_mode = cooperative_mode

        self.consume_rate = 0.5      # 每单位距离耗电量
        self.safety_margin = 1.0     # 电池安全余量

        # --- 归一化得分权重配置 ---
        self.base_score = 30.0       # 基础得分底衬
        self.alpha = 40.0            # 收益最大加分 (基于货物占车辆载重比例)
        self.beta = 30.0             # 紧急度最大加分 (基于宽裕时间倒数)
        self.gamma = 0.1             # 距离惩罚系数 (每单位距离扣减分值，温和扣分)
        self.delta = 20.0            # 低电量风险最大扣分 (仅在电量低于50%时触发)
        self.epsilon = 2.0           # 充电站排队惩罚 (每多一辆车扣 2 分)

    def _as_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _is_load_feasible(self, vehicle: dict, task: dict) -> bool:
        """Return True if the vehicle can carry this task without overloading (非协同模式)."""
        current_load = self._as_float(vehicle.get('load', 0), 0.0)
        task_weight = self._as_float(task.get('weight', 0), 0.0)
        capacity = self._as_float(
            vehicle.get('max_load',
                        vehicle.get('load_capacity',
                                    vehicle.get('capacity', self.load_capacity))),
            self.load_capacity,
        )
        return current_load + task_weight <= capacity

    def _get_vehicle_capacity(self, vehicle: dict) -> float:
        """获取车辆的剩余载重能力。"""
        capacity = self._as_float(
            vehicle.get('max_load',
                        vehicle.get('load_capacity',
                                    vehicle.get('capacity', self.load_capacity))),
            self.load_capacity,
        )
        current_load = self._as_float(vehicle.get('load', 0), 0.0)
        return max(0.0, capacity - current_load)

    def _try_cooperative_assignment(
        self,
        idle_vehicles: List[dict],
        task: dict,
        state: dict,
    ) -> Tuple[Optional[List[dict]], Optional[List[int]]]:
        """
        尝试将超重任务分配给多辆车协同完成。
        返回: (actions_list, assigned_vehicle_indices) 或 (None, None) 表示失败。
        actions 中的每一条格式为:
            {'vehicle_id': int, 'task_id': int, 'action': 'assign',
             'path': list, 'load_amount': float}
        """
        if not self.cooperative_mode:
            return None, None

        task_weight = self._as_float(task.get('weight', 0), 0.0)
        if task_weight <= 0:
            return None, None

        # 筛选出能够到达任务点且电量足够的车辆（不考虑载重，仅考虑路径可达性）
        feasible_vehicles = []
        total_remaining_capacity = 0.0
        task_node = int(task.get('node_id', 0))
        current_time = self._as_float(state.get('current_time', 0))

        for veh in idle_vehicles:
            veh_node = int(veh.get('current_node', 0))
            veh_battery = veh.get('battery', 100)
            veh_max_battery = max(veh.get('max_battery', veh_battery), 1)
            battery_ratio = veh_battery / veh_max_battery
            v_speed = self._as_float(veh.get('speed', 1.0), 1.0)

            try:
                path, dist = self.pathfinder.find_path_and_distance(veh_node, task_node)
            except Exception:
                continue

            # 电量检查 (至少能到达任务点，且保留一点余量)
            required_energy = dist * self.consume_rate
            if veh_battery < required_energy + self.safety_margin:
                continue

            # 时间检查 (能否在截止时间前到达)
            deadline = task.get('deadline', 9999)
            time_to_reach = dist / v_speed
            if current_time + time_to_reach >= deadline:
                continue

            remaining_cap = self._get_vehicle_capacity(veh)
            if remaining_cap <= 0:
                continue

            feasible_vehicles.append({
                'vehicle': veh,
                'remaining_capacity': remaining_cap,
                'path': path,
                'dist': dist,
            })
            total_remaining_capacity += remaining_cap

        if total_remaining_capacity < task_weight:
            return None, None  # 所有空闲车辆总载重仍不足

        # 按容量比例分配货物重量
        actions = []
        assigned_indices = []
        remaining_weight = task_weight

        for item in feasible_vehicles:
            veh = item['vehicle']
            cap = item['remaining_capacity']
            # 分配比例 = 该车容量 / 总容量
            assign_ratio = cap / total_remaining_capacity
            assign_weight = task_weight * assign_ratio
            # 避免浮点误差导致超分配
            assign_weight = min(assign_weight, remaining_weight, cap)
            if assign_weight <= 0:
                continue

            actions.append({
                'vehicle_id': veh['id'],
                'task_id': task['id'],
                'action': 'assign',
                'path': item['path'],
                'load_amount': assign_weight,   # 携带的货物重量
            })
            assigned_indices.append(id(veh))  # 仅用于去重标记
            remaining_weight -= assign_weight
            if remaining_weight <= 1e-6:
                break

        if remaining_weight > 0:
            # 理论上不应该发生，但若发生则回退
            return None, None

        return actions, assigned_indices

    def dispatch(self, state: dict) -> list:
        """
        核心调度算法，接收 B 模块的状态字典，返回 B 模块可执行的指令列表
        """
        idle_vehicles = [v for v in state.get('vehicles', [])
                         if str(v.get('status', '')).lower() == 'idle']

        unassigned_tasks = [t for t in state.get('tasks', [])
                            if str(t.get('status', '')).lower() == 'waiting']

        if not idle_vehicles or not unassigned_tasks:
            return []

        if self.strategy_name == "largest":
            return self._largest_dispatch(idle_vehicles, unassigned_tasks, state)
        elif self.strategy_name == "nearest":
            return self._nearest_dispatch(idle_vehicles, unassigned_tasks, state)
        elif self.strategy_name == "energy_aware_hybrid":
            return self._energy_aware_hybrid_dispatch(idle_vehicles, unassigned_tasks, state)
        else:
            return []

    # ==========================================
    # 策略 1：最大权重优先策略 (Largest Weight First)
    # ==========================================
    def _largest_dispatch(self, idle_vehicles, unassigned_tasks, state) -> list:
        actions = []
        unassigned_tasks.sort(key=lambda x: x.get('weight', 0), reverse=True)
        assigned_task_ids = set()

        for vehicle in idle_vehicles:
            if not unassigned_tasks:
                break

            # 找一个可承担的任务（优先尝试单个车辆）
            task = None
            for candidate in unassigned_tasks:
                if candidate['id'] in assigned_task_ids:
                    continue
                if self._is_load_feasible(vehicle, candidate):
                    task = candidate
                    break

            # 单辆车无法装载 → 尝试协同
            if task is None and self.cooperative_mode:
                # 从剩余任务中选择重量最大的进行协同尝试
                for candidate in unassigned_tasks:
                    if candidate['id'] in assigned_task_ids:
                        continue
                    coop_actions, _ = self._try_cooperative_assignment([vehicle], candidate, state)
                    if coop_actions:
                        # 只使用涉及当前车辆的协同动作（实际上_try_cooperative_assignment会返回所有需要的车辆动作，
                        # 但这里我们只对当前车辆循环，所以需要特殊处理：要么一次性分配所有协同车辆，要么修改主循环逻辑。
                        # 更简洁的方式：如果当前车辆参与协同，立即生成完整的协同动作集并跳出车辆循环。
                        # 为保持与原结构一致，这里我们采用“找到第一个可协同的任务后，直接生成所有动作并返回”。
                        all_actions, _ = self._try_cooperative_assignment([vehicle] + idle_vehicles, candidate, state)
                        if all_actions:
                            # 将协同动作加入结果，并从unassigned_tasks中移除该任务
                            actions.extend(all_actions)
                            unassigned_tasks = [t for t in unassigned_tasks if t['id'] != candidate['id']]
                            assigned_task_ids.add(candidate['id'])
                            break
                continue  # 继续处理下一辆车

            if task is None:
                continue

            start_node = int(vehicle.get('current_node', 0))
            target_node = int(task.get('node_id', 0))
            try:
                path, _ = self.pathfinder.find_path_and_distance(start_node, target_node)
            except Exception:
                path = [target_node]

            actions.append({
                'vehicle_id': vehicle['id'],
                'task_id': task['id'],
                'action': 'assign',
                'path': path
            })
            unassigned_tasks.remove(task)
            assigned_task_ids.add(task['id'])

        return actions

    # ==========================================
    # 策略 2：最近任务优先策略 (Nearest Task First)
    # ==========================================
    def _nearest_dispatch(self, idle_vehicles, unassigned_tasks, state) -> list:
        actions = []
        assigned_task_ids = set()

        for vehicle in idle_vehicles:
            if not unassigned_tasks:
                break

            best_task = None
            best_path = None
            shortest_dist = float('inf')
            start_node = int(vehicle.get('current_node', 0))

            for task in unassigned_tasks:
                if task['id'] in assigned_task_ids:
                    continue
                if self._is_load_feasible(vehicle, task):
                    target_node = int(task.get('node_id', 0))
                    try:
                        path, dist = self.pathfinder.find_path_and_distance(start_node, target_node)
                        if dist < shortest_dist:
                            shortest_dist = dist
                            best_task = task
                            best_path = path
                    except Exception:
                        pass

            # 若无单辆车能装载，尝试协同
            if best_task is None and self.cooperative_mode:
                for task in unassigned_tasks:
                    if task['id'] in assigned_task_ids:
                        continue
                    coop_actions, _ = self._try_cooperative_assignment([vehicle], task, state)
                    if coop_actions:
                        all_actions, _ = self._try_cooperative_assignment([vehicle] + idle_vehicles, task, state)
                        if all_actions:
                            actions.extend(all_actions)
                            unassigned_tasks = [t for t in unassigned_tasks if t['id'] != task['id']]
                            assigned_task_ids.add(task['id'])
                            break
                continue

            if best_task:
                actions.append({
                    'vehicle_id': vehicle['id'],
                    'task_id': best_task['id'],
                    'action': 'assign',
                    'path': best_path
                })
                unassigned_tasks.remove(best_task)
                assigned_task_ids.add(best_task['id'])

        return actions

    # ==========================================
    # 策略 3：能量感知综合调度策略 (Energy-Aware Hybrid Strategy)
    # ==========================================
    def _energy_aware_hybrid_dispatch(self, idle_vehicles, unassigned_tasks, state) -> list:
        actions = []
        metrics = state.get('metrics', {})
        current_time = state.get('current_time', metrics.get('current_time', 0))
        chargers = state.get('charging_stations', state.get('chargers', []))
        assigned_task_ids = set()

        # 充电站查询缓存
        charger_info_cache = {}

        # 地图规模自适应参数 (与原逻辑相同)
        map_scale = "medium"
        if 'scenario' in state:
            map_scale = str(state.get('scenario', 'medium')).lower()
        elif metrics and 'total_tasks' in metrics:
            total_tasks = metrics.get('total_tasks', 20)
            if total_tasks <= 15:
                map_scale = "small"
            elif total_tasks >= 40:
                map_scale = "large"

        scale_config = {
            "small":  {"prune_radius": 450.0,  "soc_trigger": 0.40},
            "medium": {"prune_radius": 650.0,  "soc_trigger": 0.55},
            "large":  {"prune_radius": 1000.0, "soc_trigger": 0.65}
        }
        config = scale_config.get(map_scale, scale_config["medium"])
        max_prune_radius = config["prune_radius"]
        dynamic_soc_trigger = config["soc_trigger"]

        for vehicle in idle_vehicles:
            best_task = None
            best_path = None
            max_score = -float('inf')

            veh_node = int(vehicle.get('current_node', 0))
            veh_battery = vehicle.get('battery', 100)
            veh_max_battery = max(vehicle.get('max_battery', veh_battery), 1)
            battery_ratio = max(0.0, min(1.0, veh_battery / veh_max_battery))
            v_speed = self._as_float(vehicle.get('speed', 1.0), 1.0)

            v_capacity = self._as_float(
                vehicle.get('max_load',
                            vehicle.get('load_capacity',
                                        vehicle.get('capacity', self.load_capacity))),
                self.load_capacity,
            )
            if v_capacity <= 0:
                v_capacity = 1000.0

            # 候选任务集合（单辆车可行 + 协同可行）
            feasible_tasks = []
            for task in unassigned_tasks:
                if task['id'] in assigned_task_ids:
                    continue

                # 单辆车载重可行性检查
                single_ok = self._is_load_feasible(vehicle, task)
                coop_ok = False
                if not single_ok and self.cooperative_mode:
                    coop_actions, _ = self._try_cooperative_assignment([vehicle], task, state)
                    coop_ok = (coop_actions is not None)
                if not (single_ok or coop_ok):
                    continue

                task_node = int(task.get('node_id', 0))
                try:
                    path, d1 = self.pathfinder.find_path_and_distance(veh_node, task_node)
                    if d1 > max_prune_radius:
                        continue

                    if task_node in charger_info_cache:
                        nearest_charger_node, d2, queue_length = charger_info_cache[task_node]
                    else:
                        nearest_charger_node, d2, queue_length = self._get_nearest_charger_info(task_node, chargers)
                        charger_info_cache[task_node] = (nearest_charger_node, d2, queue_length)

                    if d2 == float('inf'):
                        continue

                    time_left = task.get('deadline', 9999) - current_time
                    time_to_reach = d1 / v_speed
                    if time_to_reach >= time_left:
                        continue

                    required_energy = (d1 + d2) * self.consume_rate
                    if veh_battery < required_energy + self.safety_margin:
                        continue

                    # 计算得分 (与原逻辑相同)
                    task_weight = self._as_float(task.get('weight', 0), 0.0)
                    load_ratio = min(1.0, task_weight / v_capacity)
                    profit_score = self.alpha * load_ratio
                    buffer_time = max(0.0, time_left - time_to_reach)
                    urgency_score = self.beta * (1.0 / (buffer_time + 1.0))

                    if battery_ratio >= dynamic_soc_trigger:
                        adaptive_gamma = self.gamma * 0.5
                    else:
                        severity = ((dynamic_soc_trigger - battery_ratio) / dynamic_soc_trigger) ** 2
                        adaptive_gamma = self.gamma * (1.0 + 5.0 * severity)
                    distance_penalty = adaptive_gamma * d1
                    queue_penalty = self.epsilon * queue_length

                    if battery_ratio > dynamic_soc_trigger:
                        battery_risk_penalty = 0.0
                    else:
                        battery_risk_penalty = self.delta * ((dynamic_soc_trigger - battery_ratio) / dynamic_soc_trigger) ** 2

                    total_score = self.base_score + profit_score + urgency_score \
                                  - distance_penalty - battery_risk_penalty - queue_penalty
                    total_score = max(0.0, total_score)

                    if total_score > max_score:
                        max_score = total_score
                        best_task = task
                        best_path = path

                except Exception:
                    pass

            if best_task is not None:
                # 先检查单辆车是否可行
                if self._is_load_feasible(vehicle, best_task):
                    actions.append({
                        'vehicle_id': vehicle['id'],
                        'task_id': best_task['id'],
                        'action': 'assign',
                        'path': best_path
                    })
                    assigned_task_ids.add(best_task['id'])
                elif self.cooperative_mode:
                    # 尝试协同：找到所有空闲车辆中能一起完成该任务的集合
                    all_vehicles = [vehicle] + [v for v in idle_vehicles if v['id'] != vehicle['id']]
                    coop_actions, _ = self._try_cooperative_assignment(all_vehicles, best_task, state)
                    if coop_actions:
                        actions.extend(coop_actions)
                        assigned_task_ids.add(best_task['id'])
                        # 从空闲列表中移除已参与协同的车辆（避免重复分配）
                        for act in coop_actions:
                            for v in idle_vehicles:
                                if v['id'] == act['vehicle_id']:
                                    idle_vehicles.remove(v)
                                    break
        return actions

    def _get_nearest_charger_info(self, task_node, chargers):
        """
        辅助函数：寻找离给定任务点最近的充电站，返回 (节点ID, 距离, 当前排队人数)
        """
        if not chargers:
            return None, float('inf'), 0

        min_dist = float('inf')
        best_charger = None

        for charger in chargers:
            charger_node = int(charger.get('node_id', charger.get('node', 0)))
            try:
                _, dist = self.pathfinder.find_path_and_distance(task_node, charger_node)
                if dist < min_dist:
                    min_dist = dist
                    best_charger = charger
            except Exception:
                pass

        if best_charger:
            best_node = best_charger.get('node_id', best_charger.get('node', 0))
            return best_node, min_dist, best_charger.get('queue_length', 0)

        return None, float('inf'), 0