# strategy_ga.py
"""Genetic Algorithm scheduling strategy for the logistics fleet simulator.

已与 Hybrid 策略完成对齐，共享评分公式、距离剪枝与电池安全阈值。
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulator.pathfinder_adapter import RealPathfinder

# ---------------------------------------------------------------------------
# GA hyper-parameters (tunable)
# ---------------------------------------------------------------------------
POP_SIZE = 40
GENERATIONS = 30
MUTATION_RATE = 0.10
CROSSOVER_RATE = 0.85
TOURNAMENT_SIZE = 3
ELITE_COUNT = 2

# 移除了原有的写死权重，统一从 dispatcher 获取

# Hard-constraint penalty
INFEASIBLE_PENALTY = 1e9

# ---------------------------------------------------------------------------
# GA core
# ---------------------------------------------------------------------------

def _build_chromosome(
    n_vehicles: int, n_tasks: int, veh_task_feasible: list[list[bool]],
) -> list[int]:
    chromo = [-1] * n_vehicles
    available = list(range(n_tasks))
    random.shuffle(available)
    taken: set[int] = set()
    indices = list(range(n_vehicles))
    random.shuffle(indices)
    for vi in indices:
        for ti in available:
            if ti in taken:
                continue
            if veh_task_feasible[vi][ti]:
                chromo[vi] = ti
                taken.add(ti)
                break
    return chromo

def _mutate(
    chromo: list[int], n_tasks: int, veh_task_feasible: list[list[bool]], rate: float,
) -> list[int]:
    taken = {g for g in chromo if g >= 0}
    for vi in range(len(chromo)):
        if random.random() >= rate:
            continue
        old = chromo[vi]
        if old >= 0:
            taken.discard(old)
        candidates = [t for t in range(n_tasks) if t not in taken and veh_task_feasible[vi][t]]
        if candidates:
            new_t = random.choice(candidates)
            chromo[vi] = new_t
            taken.add(new_t)
        else:
            chromo[vi] = -1
    return chromo

def _crossover(parent_a: list[int], parent_b: list[int], n_tasks: int) -> tuple[list[int], list[int]]:
    n = len(parent_a)
    child_a = [-1] * n
    child_b = [-1] * n
    for i in range(n):
        if random.random() < 0.5:
            child_a[i], child_b[i] = parent_a[i], parent_b[i]
        else:
            child_a[i], child_b[i] = parent_b[i], parent_a[i]

    def _repair(child: list[int]) -> list[int]:
        seen: set[int] = set()
        for i in range(n):
            t = child[i]
            if t < 0: continue
            if t in seen:
                child[i] = -1
            else:
                seen.add(t)
        return child

    return _repair(child_a), _repair(child_b)

# ---------------------------------------------------------------------------
# fitness
# ---------------------------------------------------------------------------

def _compute_fitness(
    chromo: list[int], vehicles: list[dict], tasks: list[dict],
    pathfinder: RealPathfinder, state: dict,
    dist_cache: dict[tuple[int, int], tuple[list[int], float]],
    charger_cache: dict[int, tuple[int, float, int]],
    dispatcher: Any, config: dict,
) -> float:
    metrics = state.get("metrics", {})
    current_time = dispatcher._as_float(state.get("current_time", metrics.get("current_time", 0)))
    chargers = state.get("charging_stations", state.get("chargers", []))

    total = 0.0
    assigned_tasks: set[int] = set()

    # 从统一配置读取参数
    max_prune_radius = config["prune_radius"]
    dynamic_soc_trigger = config["soc_trigger"]

    for vi, ti in enumerate(chromo):
        if ti < 0: continue
        if ti in assigned_tasks: return -INFEASIBLE_PENALTY
        assigned_tasks.add(ti)

        veh = vehicles[vi]
        task = tasks[ti]

        if not dispatcher._is_load_feasible(veh, task):
            return -INFEASIBLE_PENALTY

        v_node = int(veh.get("current_node", 0))
        t_node = int(task.get("node_id", 0))
        v_battery = dispatcher._as_float(veh.get("battery", 100))
        v_max_battery = max(dispatcher._as_float(veh.get("max_battery", v_battery)), 1.0)
        battery_ratio = max(0.0, min(1.0, v_battery / v_max_battery))
        v_speed = dispatcher._as_float(veh.get("speed", 1.0), 1.0)
        v_capacity = dispatcher._as_float(
            veh.get("max_load", veh.get("load_capacity", veh.get("capacity", dispatcher.load_capacity))),
            dispatcher.load_capacity,
        )
        if v_capacity <= 0: v_capacity = 1000.0

        key = (v_node, t_node)
        if key in dist_cache:
            path, d1 = dist_cache[key]
        else:
            try:
                path, d1 = pathfinder.find_path_and_distance(v_node, t_node)
            except Exception:
                path, d1 = [], float("inf")
            dist_cache[key] = (path, d1)

        # 结合任务剪枝
        if d1 > max_prune_radius or d1 == float("inf"):
            return -INFEASIBLE_PENALTY

        if t_node in charger_cache:
            _, d2, queue_len = charger_cache[t_node]
        else:
            # 统一调用 Hybrid 寻找充电站算法
            best_n, d2, queue_len = dispatcher._get_nearest_charger_info(t_node, chargers)
            charger_cache[t_node] = (best_n, d2, queue_len)

        if d2 == float("inf"): return -INFEASIBLE_PENALTY

        deadline = dispatcher._as_float(task.get("deadline", 9999))
        time_left = deadline - current_time
        time_to_reach = d1 / v_speed
        if time_to_reach >= time_left: return -INFEASIBLE_PENALTY

        required_energy = (d1 + d2) * dispatcher.consume_rate
        if v_battery < required_energy + dispatcher.safety_margin:
            return -INFEASIBLE_PENALTY

        # --- 像素级还原 Hybrid 打分公式 ---
        task_weight = dispatcher._as_float(task.get("weight", 0), 0.0)
        load_ratio = min(1.0, task_weight / v_capacity)
        profit_score = dispatcher.alpha * load_ratio

        buffer_time = max(0.0, time_left - time_to_reach)
        urgency_score = dispatcher.beta * (1.0 / (buffer_time + 1.0))

        if battery_ratio >= dynamic_soc_trigger:
            adaptive_gamma = dispatcher.gamma * 0.5
        else:
            severity = ((dynamic_soc_trigger - battery_ratio) / dynamic_soc_trigger) ** 2
            adaptive_gamma = dispatcher.gamma * (1.0 + 5.0 * severity)
        distance_penalty = adaptive_gamma * d1
        queue_penalty = dispatcher.epsilon * queue_len

        if battery_ratio > dynamic_soc_trigger:
            battery_risk_penalty = 0.0
        else:
            battery_risk_penalty = dispatcher.delta * ((dynamic_soc_trigger - battery_ratio) / dynamic_soc_trigger) ** 2

        task_score = dispatcher.base_score + profit_score + urgency_score - distance_penalty - battery_risk_penalty - queue_penalty
        task_score = max(0.0, task_score)

        total += task_score

    return total

# ---------------------------------------------------------------------------
# main entry point called by Dispatcher.dispatch()
# ---------------------------------------------------------------------------

def ga_dispatch(
    idle_vehicles: list[dict],
    unassigned_tasks: list[dict],
    pathfinder: RealPathfinder,
    state: dict,
    dispatcher: Any,
    pop_size: int = POP_SIZE,
    generations: int = GENERATIONS,
) -> list[dict]:

    n_v = len(idle_vehicles)
    n_t = len(unassigned_tasks)

    if n_v == 0 or n_t == 0: return []

    # 统一提取 scale 设定
    config = dispatcher._get_scale_config(state)
    max_prune_radius = config["prune_radius"]

    dist_cache: dict[tuple[int, int], tuple[list[int], float]] = {}
    charger_cache: dict[int, tuple[int, float, int]] = {}

    # 生成矩阵前引入 Hybrid 距离剪枝逻辑
    veh_task_feasible: list[list[bool]] = []
    for v in idle_vehicles:
        row = []
        v_node = int(v.get("current_node", 0))
        for t in unassigned_tasks:
            t_node = int(t.get("node_id", 0))
            is_feasible = dispatcher._is_load_feasible(v, t)
            
            if is_feasible:
                key = (v_node, t_node)
                if key not in dist_cache:
                    try:
                        path, d1 = pathfinder.find_path_and_distance(v_node, t_node)
                    except Exception:
                        path, d1 = [], float("inf")
                    dist_cache[key] = (path, d1)
                else:
                    d1 = dist_cache[key][1]
                
                # Prune 过远任务
                if d1 > max_prune_radius:
                    is_feasible = False
                    
            row.append(is_feasible)
        veh_task_feasible.append(row)

    if not any(any(row) for row in veh_task_feasible): return []

    # ---- initialise population ----
    pop = [_build_chromosome(n_v, n_t, veh_task_feasible) for _ in range(max(pop_size, ELITE_COUNT + 2))]
    fitness = [
        _compute_fitness(c, idle_vehicles, unassigned_tasks, pathfinder, state,
                         dist_cache, charger_cache, dispatcher, config)
        for c in pop
    ]

    best_idx = max(range(len(pop)), key=lambda i: fitness[i])

    # ---- evolve ----
    for gen in range(generations):
        new_pop: list[list[int]] = []
        sorted_idx = sorted(range(len(pop)), key=lambda i: fitness[i], reverse=True)
        for ei in sorted_idx[:ELITE_COUNT]:
            new_pop.append(pop[ei][:])

        while len(new_pop) < pop_size:
            if random.random() < CROSSOVER_RATE and len(new_pop) + 2 <= pop_size:
                t_a = random.sample(range(len(pop)), min(TOURNAMENT_SIZE, len(pop)))
                t_b = random.sample(range(len(pop)), min(TOURNAMENT_SIZE, len(pop)))
                p_a = pop[max(t_a, key=lambda i: fitness[i])]
                p_b = pop[max(t_b, key=lambda i: fitness[i])]
                c_a, c_b = _crossover(p_a, p_b, n_t)
                new_pop.append(c_a)
                new_pop.append(c_b)
            else:
                t_idx = random.sample(range(len(pop)), min(TOURNAMENT_SIZE, len(pop)))
                parent = pop[max(t_idx, key=lambda i: fitness[i])]
                child = _mutate(parent[:], n_t, veh_task_feasible, MUTATION_RATE)
                new_pop.append(child)

        pop = new_pop[:pop_size]
        fitness = [
            _compute_fitness(c, idle_vehicles, unassigned_tasks, pathfinder, state,
                             dist_cache, charger_cache, dispatcher, config)
            for c in pop
        ]
        best_idx = max(range(len(pop)), key=lambda i: fitness[i])

    # ---- decode best chromosome → actions ----
    best = pop[best_idx]
    actions: list[dict] = []
    for vi, ti in enumerate(best):
        if ti < 0: continue
        veh = idle_vehicles[vi]
        task = unassigned_tasks[ti]
        v_node = int(veh.get("current_node", 0))
        t_node = int(task.get("node_id", 0))

        key = (v_node, t_node)
        if key in dist_cache:
            path, _ = dist_cache[key]
        else:
            try:
                path, _ = pathfinder.find_path_and_distance(v_node, t_node)
            except Exception:
                path = [t_node]
            dist_cache[key] = (path, 0.0)

        actions.append({
            "vehicle_id": veh["id"],
            "task_id": task["id"],
            "target_node": t_node,
            "action": "assign",
            "path": path,
        })

    return actions
