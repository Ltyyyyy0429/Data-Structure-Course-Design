"""Assert-based tests for the four dispatch strategies.

Run with:
    python3 test_strategy.py
"""

from __future__ import annotations

import random

from strategy import Dispatcher


class MockPathfinder:
    """Small deterministic pathfinder used by strategy tests."""

    def __init__(self, distances: dict[tuple[int, int], float]):
        self.distances = distances

    def find_path_and_distance(self, start_node, end_node):
        start_node = int(start_node)
        end_node = int(end_node)
        if start_node == end_node:
            return [start_node], 0.0

        distance = self.distances.get((start_node, end_node))
        if distance is None:
            distance = self.distances.get((end_node, start_node))
        if distance is None:
            return [], float("inf")
        return [start_node, end_node], float(distance)


def make_base_state() -> dict:
    return {
        "current_time": 0.0,
        "metrics": {"current_time": 0.0, "scale": "small", "strategy": "test"},
        "vehicles": [
            {
                "id": "v1",
                "status": "idle",
                "current_node": 0,
                "battery": 120.0,
                "max_battery": 120.0,
                "load": 0.0,
                "max_load": 1000.0,
            }
        ],
        "tasks": [],
        "charging_stations": [{"node_id": 9, "queue_length": 0}],
    }


def task(task_id: str, node_id: int, weight: float, status: str = "waiting", deadline: float = 999.0) -> dict:
    return {
        "id": task_id,
        "node_id": node_id,
        "weight": weight,
        "status": status,
        "deadline": deadline,
    }


def assert_actions_valid(actions: list[dict], state: dict) -> None:
    """Check common action invariants shared by all strategies."""

    assert isinstance(actions, list), "actions must be a list"

    vehicles = {vehicle["id"]: vehicle for vehicle in state.get("vehicles", [])}
    tasks = {task_data["id"]: task_data for task_data in state.get("tasks", [])}
    assigned_task_ids = set()

    for action in actions:
        assert action.get("action") == "assign", f"unexpected action: {action}"

        vehicle_id = action.get("vehicle_id")
        task_id = action.get("task_id")
        assert vehicle_id in vehicles, f"unknown vehicle_id: {vehicle_id}"
        assert task_id in tasks, f"unknown task_id: {task_id}"
        assert task_id not in assigned_task_ids, f"task assigned twice: {task_id}"
        assigned_task_ids.add(task_id)

        selected_vehicle = vehicles[vehicle_id]
        selected_task = tasks[task_id]
        assert selected_task.get("status") == "waiting", f"task is not waiting: {task_id}"
        assert "target_node" in action, f"action missing target_node: {action}"
        assert action["target_node"] == selected_task["node_id"], (
            f"target_node does not match task node for {task_id}"
        )

        current_load = float(selected_vehicle.get("load", 0) or 0)
        task_weight = float(selected_task.get("weight", 0) or 0)
        capacity = float(
            selected_vehicle.get(
                "max_load",
                selected_vehicle.get("load_capacity", selected_vehicle.get("capacity", 1000.0)),
            )
            or 1000.0
        )
        assert current_load + task_weight <= capacity, f"overloaded assignment: {action}"


def dispatch(strategy_name: str, state: dict, pathfinder: MockPathfinder, **kwargs) -> list[dict]:
    dispatcher = Dispatcher(pathfinder=pathfinder, strategy_name=strategy_name, **kwargs)
    return dispatcher.dispatch(state)


def test_nearest_skips_overload_and_selects_nearest_feasible() -> None:
    state = make_base_state()
    state["vehicles"][0]["load"] = 850.0
    state["tasks"] = [
        task("near_overload", 1, 200.0),
        task("middle_feasible", 2, 100.0),
        task("far_feasible", 3, 100.0),
    ]
    pathfinder = MockPathfinder({(0, 1): 5, (0, 2): 10, (0, 3): 30})

    actions = dispatch("nearest", state, pathfinder)

    assert_actions_valid(actions, state)
    assert len(actions) == 1
    assert actions[0]["task_id"] == "middle_feasible"


def test_largest_skips_overload_and_selects_largest_feasible() -> None:
    state = make_base_state()
    state["vehicles"][0]["load"] = 700.0
    state["tasks"] = [
        task("too_heavy", 1, 400.0),
        task("largest_feasible", 2, 250.0),
        task("light_feasible", 3, 80.0),
    ]
    pathfinder = MockPathfinder({(0, 1): 5, (0, 2): 20, (0, 3): 10})

    actions = dispatch("largest", state, pathfinder)

    assert_actions_valid(actions, state)
    assert len(actions) == 1
    assert actions[0]["task_id"] == "largest_feasible"


def test_energy_aware_hybrid_uses_energy_and_load_constraints() -> None:
    high_state = make_base_state()
    high_state["tasks"] = [
        task("overload", 1, 1200.0),
        task("safe_near", 2, 100.0),
        task("safe_far", 3, 200.0),
    ]
    high_state["charging_stations"] = [{"node_id": 9, "queue_length": 0}]
    pathfinder = MockPathfinder({
        (0, 1): 5,
        (0, 2): 10,
        (0, 3): 50,
        (1, 9): 5,
        (2, 9): 5,
        (3, 9): 5,
    })

    high_actions = dispatch(
        "energy_aware_hybrid",
        high_state,
        pathfinder,
        consume_rate=1.0,
        load_capacity=1000.0,
    )
    assert_actions_valid(high_actions, high_state)
    assert high_actions, "high-battery hybrid scenario should assign a feasible task"
    assert all(action["task_id"] != "overload" for action in high_actions)

    low_state = make_base_state()
    low_state["vehicles"][0]["battery"] = 5.0
    low_state["tasks"] = [task("energy_unsafe", 2, 100.0)]
    low_state["charging_stations"] = [{"node_id": 9, "queue_length": 0}]

    low_actions = dispatch(
        "energy_aware_hybrid",
        low_state,
        pathfinder,
        consume_rate=1.0,
        load_capacity=1000.0,
    )
    assert low_actions == [], "low battery should block unsafe assignment"


def test_genetic_algorithm_returns_valid_constrained_actions() -> None:
    random.seed(2026)
    state = make_base_state()
    state["vehicles"] = [
        {
            "id": "v1",
            "status": "idle",
            "current_node": 0,
            "battery": 120.0,
            "max_battery": 120.0,
            "load": 0.0,
            "max_load": 500.0,
        },
        {
            "id": "v2",
            "status": "idle",
            "current_node": 0,
            "battery": 120.0,
            "max_battery": 120.0,
            "load": 350.0,
            "max_load": 500.0,
        },
    ]
    state["tasks"] = [
        task("waiting_a", 1, 200.0),
        task("waiting_b", 2, 120.0),
        task("not_waiting", 3, 100.0, status="assigned"),
        task("overload_for_all", 4, 900.0),
    ]
    state["charging_stations"] = [{"node_id": 9, "queue_length": 1}]
    pathfinder = MockPathfinder({
        (0, 1): 10,
        (0, 2): 12,
        (0, 3): 8,
        (0, 4): 6,
        (1, 9): 5,
        (2, 9): 5,
        (3, 9): 5,
        (4, 9): 5,
    })

    actions = dispatch(
        "genetic_algorithm",
        state,
        pathfinder,
        consume_rate=0.2,
        load_capacity=500.0,
    )

    assert_actions_valid(actions, state)
    assert actions, "GA should find at least one feasible assignment"
    assert all(action["task_id"] != "not_waiting" for action in actions)
    assert all(action["task_id"] != "overload_for_all" for action in actions)


def run_tests() -> None:
    test_nearest_skips_overload_and_selects_nearest_feasible()
    test_largest_skips_overload_and_selects_largest_feasible()
    test_energy_aware_hybrid_uses_energy_and_load_constraints()
    test_genetic_algorithm_returns_valid_constrained_actions()
    print("Strategy tests passed.")


if __name__ == "__main__":
    run_tests()
