# strategy_ga.py
"""Genetic Algorithm scheduling strategy for the logistics fleet simulator.

Encoding: each chromosome is a list of length n (idle vehicles), where
each gene is a task index (0..m-1) or -1 for no assignment.  Each task
may be assigned to at most one vehicle.

The GA runs one lightweight evolution per dispatch tick (small population,
few generations) and returns action dicts in the same format as the other
strategies.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

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

# Fitness scoring weights (same semantics as energy_aware_hybrid)
BASE_SCORE = 30.0
ALPHA = 40.0       # weight bonus max
BETA = 30.0        # urgency bonus max
GAMMA = 0.1        # distance penalty per km
DELTA = 20.0       # low-battery penalty max (only when battery < 50 %)
EPSILON = 2.0      # charger queue penalty per vehicle
SAFETY_MARGIN = 1.0

# Hard-constraint penalty — large enough to dominate any feasible solution
INFEASIBLE_PENALTY = 1e9


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _as_float(value, default: float = 0.0) -> float:  # mirrors strategy.Dispatcher._as_float
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_load_feasible(vehicle: dict, task: dict, default_capacity: float = 1000.0) -> bool:  # mirrors strategy.Dispatcher._is_load_feasible
    cur = _as_float(vehicle.get("load", 0))
    w = _as_float(task.get("weight", 0))
    cap = _as_float(
        vehicle.get("max_load", vehicle.get("load_capacity", vehicle.get("capacity", default_capacity))),
        default_capacity,
    )
    return cur + w <= cap


# ---------------------------------------------------------------------------
# GA core
# ---------------------------------------------------------------------------

def _build_chromosome(
    n_vehicles: int, n_tasks: int, veh_task_feasible: list[list[bool]],
) -> list[int]:
    """Create a random chromosome respecting load feasibility and 1-to-1 task constraint."""
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
    """In-place mutation: randomly reassign or clear genes."""
    taken = {g for g in chromo if g >= 0}
    for vi in range(len(chromo)):
        if random.random() >= rate:
            continue
        old = chromo[vi]
        if old >= 0:
            taken.discard(old)
        # pick a new task that is not taken
        candidates = [t for t in range(n_tasks) if t not in taken and veh_task_feasible[vi][t]]
        if candidates:
            new_t = random.choice(candidates)
            chromo[vi] = new_t
            taken.add(new_t)
        else:
            chromo[vi] = -1
    return chromo


def _crossover(parent_a: list[int], parent_b: list[int], n_tasks: int) -> tuple[list[int], list[int]]:
    """Uniform crossover per vehicle position, then repair duplicate tasks."""
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
            if t < 0:
                continue
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
    consume_rate: float, load_capacity: float,
) -> float:
    """Return the total fitness score for *chromo*.  Higher is better."""

    metrics = state.get("metrics", {})
    current_time = _as_float(
        state.get("current_time", metrics.get("current_time", 0))
    )
    chargers = state.get("charging_stations", state.get("chargers", []))

    total = 0.0
    assigned_tasks: set[int] = set()

    for vi, ti in enumerate(chromo):
        if ti < 0:
            continue
        if ti in assigned_tasks:          # duplicate — should not happen after repair
            return -INFEASIBLE_PENALTY
        assigned_tasks.add(ti)

        veh = vehicles[vi]
        task = tasks[ti]

        if not _is_load_feasible(veh, task, load_capacity):
            return -INFEASIBLE_PENALTY

        v_node = int(veh.get("current_node", 0))
        t_node = int(task.get("node_id", 0))
        v_battery = _as_float(veh.get("battery", 100))
        v_max_battery = max(_as_float(veh.get("max_battery", v_battery)), 1.0)
        battery_ratio = max(0.0, min(1.0, v_battery / v_max_battery))
        v_speed = _as_float(veh.get("speed", 1.0), 1.0)

        v_capacity = _as_float(
            veh.get("max_load", veh.get("load_capacity", veh.get("capacity", load_capacity))),
            load_capacity,
        )
        if v_capacity <= 0:
            v_capacity = 1000.0

        # distance vehicle → task  (cached)
        key = (v_node, t_node)
        if key in dist_cache:
            path, d1 = dist_cache[key]
        else:
            try:
                path, d1 = pathfinder.find_path_and_distance(v_node, t_node)
            except Exception:
                path, d1 = [], float("inf")
            dist_cache[key] = (path, d1)

        if d1 == float("inf"):
            return -INFEASIBLE_PENALTY

        # nearest charger from task node  (cached)
        if t_node in charger_cache:
            _, d2, queue_len = charger_cache[t_node]
        else:
            d2 = float("inf")
            best_n, best_d, best_q = 0, float("inf"), 0
            for ch in chargers:
                ch_node = int(ch.get("node_id", ch.get("node", 0)))
                try:
                    _, dist = pathfinder.find_path_and_distance(t_node, ch_node)
                except Exception:
                    dist = float("inf")
                if dist < best_d:
                    best_d = dist
                    best_n = ch_node
                    best_q = int(ch.get("queue_length", 0))
            d2 = best_d
            queue_len = best_q
            charger_cache[t_node] = (best_n, best_d, best_q)

        if d2 == float("inf"):
            return -INFEASIBLE_PENALTY

        # --- time feasibility (death-march guard, same as hybrid) ---
        deadline = _as_float(task.get("deadline", 9999))
        time_left = deadline - current_time
        time_to_reach = d1 / v_speed
        if time_to_reach >= time_left:
            return -INFEASIBLE_PENALTY

        required_energy = (d1 + d2) * consume_rate
        if v_battery < required_energy + SAFETY_MARGIN:
            return -INFEASIBLE_PENALTY

        # --- composite score (same semantics as energy_aware_hybrid) ---
        task_weight = _as_float(task.get("weight", 0), 0.0)
        load_ratio = min(1.0, task_weight / v_capacity)
        profit_score = ALPHA * load_ratio

        buffer_time = max(0.0, time_left - time_to_reach)
        urgency_score = BETA * (1.0 / (buffer_time + 1.0))

        distance_penalty = GAMMA * d1
        if battery_ratio > 0.5:
            battery_risk_penalty = 0.0
        else:
            battery_risk_penalty = DELTA * ((0.5 - battery_ratio) / 0.5) ** 2
        queue_penalty = EPSILON * queue_len

        task_score = BASE_SCORE + profit_score + urgency_score \
                     - distance_penalty - battery_risk_penalty - queue_penalty
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
    *,
    consume_rate: float = 0.5,
    load_capacity: float = 1000.0,
    pop_size: int = POP_SIZE,
    generations: int = GENERATIONS,
) -> list[dict]:
    """Run one GA evolution and return a list of action dicts."""

    n_v = len(idle_vehicles)
    n_t = len(unassigned_tasks)

    if n_v == 0 or n_t == 0:
        return []

    # pre-compute load feasibility matrix
    veh_task_feasible: list[list[bool]] = []
    for v in idle_vehicles:
        row = [_is_load_feasible(v, t, load_capacity) for t in unassigned_tasks]
        veh_task_feasible.append(row)

    # if no feasible assignments exist at all, bail out
    if not any(any(row) for row in veh_task_feasible):
        return []

    # caches (cleared per tick)
    dist_cache: dict[tuple[int, int], tuple[list[int], float]] = {}
    charger_cache: dict[int, tuple[int, float, int]] = {}

    # ---- initialise population ----
    pop = [_build_chromosome(n_v, n_t, veh_task_feasible) for _ in range(max(pop_size, ELITE_COUNT + 2))]
    fitness = [
        _compute_fitness(c, idle_vehicles, unassigned_tasks, pathfinder, state,
                         dist_cache, charger_cache, consume_rate, load_capacity)
        for c in pop
    ]

    best_idx = max(range(len(pop)), key=lambda i: fitness[i])

    # ---- evolve ----
    for gen in range(generations):
        new_pop: list[list[int]] = []

        # elitism
        sorted_idx = sorted(range(len(pop)), key=lambda i: fitness[i], reverse=True)
        for ei in sorted_idx[:ELITE_COUNT]:
            new_pop.append(pop[ei][:])

        # fill the rest
        while len(new_pop) < pop_size:
            # tournament selection
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

        # truncate to pop_size
        pop = new_pop[:pop_size]

        # re-evaluate
        fitness = [
            _compute_fitness(c, idle_vehicles, unassigned_tasks, pathfinder, state,
                             dist_cache, charger_cache, consume_rate, load_capacity)
            for c in pop
        ]
        best_idx = max(range(len(pop)), key=lambda i: fitness[i])

    # ---- decode best chromosome → actions ----
    best = pop[best_idx]
    actions: list[dict] = []
    for vi, ti in enumerate(best):
        if ti < 0:
            continue
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
            "action": "assign",
            "path": path,
        })

    return actions
