# strategy.py
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.pathfinder_adapter import RealPathfinder

class Dispatcher:
    def __init__(self, pathfinder: RealPathfinder, strategy_name: str = "energy_aware_hybrid",
                 consume_rate: float = None, load_capacity: float = 1000.0):
        """
        初始化调度中心
        :param pathfinder: RealPathfinder 实例 (用于计算最短路径)
        :param strategy_name: 调度策略，支持 "nearest" (最近优先)、"largest" (最大权重优先) 和 "energy_aware_hybrid" (能量感知综合调度)
        :param consume_rate: 每单位距离耗电量，默认 0.5；传 None 使用原默认值
        """
        self.pathfinder = pathfinder
        self.strategy_name = strategy_name
        self.load_capacity = load_capacity

        # === 能量感知综合策略专用的基础属性和超参数 ===
        self.consume_rate = consume_rate if consume_rate is not None else 0.5
        self.safety_margin = 5.0     # 电池安全余量 (防止刚好没电)
        
        self.alpha = 1.0   # 收益权重 (基于货物重量)
        self.beta = 100.0  # 紧急度权重 (放大时间倒数的影响)
        self.gamma = 0.5   # 距离惩罚系数
        self.delta = 50.0  # 电量风险惩罚系数
        self.epsilon = 10.0 # 充电站排队惩罚系数

    def _as_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _is_load_feasible(self, vehicle: dict, task: dict) -> bool:
        """Return True if the vehicle can carry this task without overloading."""
        current_load = self._as_float(vehicle.get('load', 0), 0.0)
        task_weight = self._as_float(task.get('weight', 0), 0.0)
        capacity = self._as_float(
            vehicle.get('max_load',
                        vehicle.get('load_capacity',
                                    vehicle.get('capacity', self.load_capacity))),
            self.load_capacity,
        )
        return current_load + task_weight <= capacity

    def dispatch(self, state: dict) -> list:
        """
        核心调度算法，接收 B 模块的状态字典，返回 B 模块可执行的指令列表
        """
        # 1. 完美适配 B 同学的状态判定：使用 lower() 兼容 'idle' 和 'waiting'
        idle_vehicles = [v for v in state.get('vehicles', []) 
                         if str(v.get('status', '')).lower() == 'idle']
        
        unassigned_tasks = [t for t in state.get('tasks', []) 
                            if str(t.get('status', '')).lower() == 'waiting']

        # 如果没有空闲车辆或没有待分配任务，直接返回空指令
        if not idle_vehicles or not unassigned_tasks:
            return []

        # 2. 核心路由：根据 strategy_name 调用对应的调度分支
        if self.strategy_name == "largest":
            return self._largest_dispatch(idle_vehicles, unassigned_tasks)
        elif self.strategy_name == "nearest":
            return self._nearest_dispatch(idle_vehicles, unassigned_tasks)
        elif self.strategy_name == "energy_aware_hybrid":
            return self._energy_aware_hybrid_dispatch(idle_vehicles, unassigned_tasks, state)
        else:
            return []

    # ==========================================
    # 策略 1：最大权重优先策略 (Largest Weight First)
    # ==========================================
    def _largest_dispatch(self, idle_vehicles, unassigned_tasks) -> list:
        actions = []
        # 按任务权重降序排列
        unassigned_tasks.sort(key=lambda x: x.get('weight', 0), reverse=True)

        for vehicle in idle_vehicles:
            if not unassigned_tasks:
                break

            task = None
            for candidate in unassigned_tasks:
                if self._is_load_feasible(vehicle, candidate):
                    task = candidate
                    break
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
        return actions

    # ==========================================
    # 策略 2：最近任务优先策略 (Nearest Task First)
    # ==========================================
    def _nearest_dispatch(self, idle_vehicles, unassigned_tasks) -> list:
        actions = []
        for vehicle in idle_vehicles:
            if not unassigned_tasks:
                break

            best_task = None
            best_path = None
            shortest_dist = float('inf')

            start_node = int(vehicle.get('current_node', 0))

            for task in unassigned_tasks:
                if not self._is_load_feasible(vehicle, task):
                    continue

                target_node = int(task.get('node_id', 0))

                try:
                    path, dist = self.pathfinder.find_path_and_distance(start_node, target_node)

                    if dist < shortest_dist:
                        shortest_dist = dist
                        best_task = task
                        best_path = path
                except Exception:
                    pass

            if best_task:
                actions.append({
                    'vehicle_id': vehicle['id'],
                    'task_id': best_task['id'],
                    'action': 'assign',
                    'path': best_path
                })
                unassigned_tasks.remove(best_task)

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

        for vehicle in idle_vehicles:
            best_task = None
            best_path = None
            max_score = -float('inf')

            veh_node = int(vehicle.get('current_node', 0))
            veh_battery = vehicle.get('battery', 100)
            veh_max_battery = max(vehicle.get('max_battery', veh_battery), 1)
            battery_ratio = max(0.0, min(1.0, veh_battery / veh_max_battery))

            for task in unassigned_tasks:
                if task['id'] in assigned_task_ids:
                    continue
                if not self._is_load_feasible(vehicle, task):
                    continue

                task_node = int(task.get('node_id', 0))

                try:
                    path, d1 = self.pathfinder.find_path_and_distance(veh_node, task_node)
                    nearest_charger_node, d2, queue_length = self._get_nearest_charger_info(task_node, chargers)

                    if d2 == float('inf'):
                        continue

                    required_energy = (d1 + d2) * self.consume_rate
                    if veh_battery < required_energy + self.safety_margin:
                        continue

                    profit_score = self.alpha * task.get('weight', 10)
                    time_left = max(1, task.get('deadline', 9999) - current_time)
                    urgency_score = self.beta * (1.0 / time_left)

                    distance_penalty = self.gamma * d1
                    battery_risk_penalty = self.delta * (1.0 - battery_ratio)
                    queue_penalty = self.epsilon * queue_length

                    total_score = profit_score + urgency_score - distance_penalty - battery_risk_penalty - queue_penalty

                    if total_score > max_score:
                        max_score = total_score
                        best_task = task
                        best_path = path
                except Exception:
                    pass

            if best_task is not None:
                actions.append({
                    'vehicle_id': vehicle['id'],
                    'task_id': best_task['id'],
                    'action': 'assign',
                    'path': best_path
                })
                assigned_task_ids.add(best_task['id'])

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
