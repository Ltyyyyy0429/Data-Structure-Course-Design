"""Assert-based integration tests across A, B, C and D state adapter modules.

Run with:
    python3 test_integration.py
"""

from __future__ import annotations

import json
import os
import random
import tempfile

from core.difficulty import get_difficulty_config
from simulator.pathfinder_adapter import RealPathfinder
from simulator.simulator import Simulator
from strategy import Dispatcher
from ui.state_adapter import normalize_state, validate_state


STRATEGIES = ("nearest", "largest", "energy_aware_hybrid", "genetic_algorithm")


def build_temp_map_file() -> str:
    """Create a small A-format map with warehouse, task nodes and charging."""

    map_data = {
        "nodes": [
            {"id": 0, "x": 0.0, "y": 0.0, "type": "warehouse"},
            {"id": 1, "x": 10.0, "y": 0.0, "type": "task"},
            {"id": 2, "x": 20.0, "y": 0.0, "type": "task"},
            {"id": 3, "x": 30.0, "y": 0.0, "type": "charging"},
        ],
        "edges": [
            {"from": 0, "to": 1, "distance": 10.0},
            {"from": 1, "to": 2, "distance": 10.0},
            {"from": 2, "to": 3, "distance": 10.0},
            {"from": 0, "to": 3, "distance": 40.0},
        ],
    }

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(map_data, tmp)
    tmp.close()
    return tmp.name


def build_b_graph_data() -> dict:
    """The same map converted to B Simulator node type names."""

    return {
        "nodes": [
            {"id": 0, "x": 0.0, "y": 0.0, "type": "depot"},
            {"id": 1, "x": 10.0, "y": 0.0, "type": "task_point"},
            {"id": 2, "x": 20.0, "y": 0.0, "type": "task_point"},
            {"id": 3, "x": 30.0, "y": 0.0, "type": "charging_station"},
        ],
        "edges": [
            {"from_node": 0, "to_node": 1, "distance": 10.0},
            {"from_node": 1, "to_node": 2, "distance": 10.0},
            {"from_node": 2, "to_node": 3, "distance": 10.0},
            {"from_node": 0, "to_node": 3, "distance": 40.0},
        ],
    }


def assert_core_state_fields(state: dict) -> None:
    required_fields = {
        "nodes",
        "edges",
        "vehicles",
        "tasks",
        "charging_stations",
        "metrics",
    }
    assert required_fields.issubset(state), f"state missing fields: {required_fields - set(state)}"
    assert isinstance(state["nodes"], list)
    assert isinstance(state["edges"], list)
    assert isinstance(state["vehicles"], list)
    assert isinstance(state["tasks"], list)
    assert isinstance(state["charging_stations"], list)
    assert isinstance(state["metrics"], dict)


def create_simulator(strategy: str, pathfinder: RealPathfinder) -> Simulator:
    random.seed(2026)
    config = get_difficulty_config("small", "easy")
    simulator = Simulator(
        graph_data=build_b_graph_data(),
        scale="small",
        strategy=strategy,
        config=config,
    )
    simulator.pathfinder = pathfinder
    simulator._dispatcher = Dispatcher(
        pathfinder,
        strategy,
        consume_rate=simulator.energy_per_km,
        load_capacity=simulator.load_capacity,
    )
    simulator.add_test_task("it_t1", 1, 100.0, 0.0, 120.0)
    simulator.add_test_task("it_t2", 2, 150.0, 0.0, 130.0)
    return simulator


def test_real_pathfinder() -> str:
    map_file = build_temp_map_file()
    pathfinder = RealPathfinder(map_file)

    path, distance = pathfinder.find_path_and_distance(0, 2)
    assert path == [0, 1, 2], f"unexpected path: {path}"
    assert distance == 20.0, f"unexpected distance: {distance}"

    charging_node, charging_distance = pathfinder.nearest_charging_station(0)
    assert charging_node == 3
    assert charging_distance == 30.0
    return map_file


def test_dispatcher_with_real_pathfinder(map_file: str) -> None:
    pathfinder = RealPathfinder(map_file)
    state = {
        "current_time": 0.0,
        "metrics": {"current_time": 0.0},
        "vehicles": [
            {
                "id": "v1",
                "current_node": 0,
                "status": "idle",
                "battery": 120.0,
                "max_battery": 120.0,
                "load": 0.0,
                "max_load": 1000.0,
            }
        ],
        "tasks": [
            {"id": "t_far", "node_id": 2, "weight": 100.0, "status": "waiting", "deadline": 120.0},
            {"id": "t_near", "node_id": 1, "weight": 100.0, "status": "waiting", "deadline": 120.0},
        ],
        "charging_stations": [{"node_id": 3, "queue_length": 0}],
    }

    actions = Dispatcher(pathfinder, "nearest").dispatch(state)
    assert actions, "nearest dispatcher should assign one task"
    assert actions[0]["task_id"] == "t_near"
    assert actions[0]["target_node"] == 1


def test_simulator_and_state_adapter(map_file: str) -> None:
    pathfinder = RealPathfinder(map_file)

    for strategy in STRATEGIES:
        simulator = create_simulator(strategy, pathfinder)
        simulator.update(1.0)

        state = simulator.get_state()
        assert_core_state_fields(state)
        assert state["metrics"]["strategy"] == strategy
        assert len(state["vehicles"]) > 0
        assert len(state["charging_stations"]) == 1

        normalized = normalize_state(state)
        assert validate_state(normalized) is True
        assert isinstance(normalized["nodes"], dict)
        assert normalized["vehicles"], "normalized vehicles should not be empty"
        assert "x" in normalized["vehicles"][0]
        assert "y" in normalized["vehicles"][0]


def run_tests() -> None:
    map_file = test_real_pathfinder()
    try:
        test_dispatcher_with_real_pathfinder(map_file)
        test_simulator_and_state_adapter(map_file)
    finally:
        if os.path.exists(map_file):
            os.unlink(map_file)

    print("Integration tests passed.")


if __name__ == "__main__":
    run_tests()
