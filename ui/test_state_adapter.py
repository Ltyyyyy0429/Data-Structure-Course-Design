"""Simple state adapter checks.

Run from the project root:
    python3 ui/test_state_adapter.py
"""

from __future__ import annotations

from state_adapter import get_demo_state, normalize_state, validate_state


class DemoStateSource:
    """Small fake source used to test get_demo_state without opening Pygame."""

    def get_state(self):
        return {
            "nodes": [
                {"id": 0, "x": 10, "y": 20, "type": "warehouse"},
                {"id": 1, "x": 30, "y": 40, "type": "charging"},
            ],
            "edges": [
                {"from": 0, "to": 1, "distance": 25},
            ],
            "vehicles": [
                {"id": "v1", "current_node": 0, "battery": 80, "status": "idle"},
            ],
            "tasks": [],
            "charging_stations": [
                {"node_id": 1, "queue": 0},
            ],
            "metrics": {
                "current_time": 0,
                "scale": "small",
                "strategy": "nearest",
                "total_score": 0,
                "completed_tasks": 0,
                "timeout_tasks": 0,
                "total_distance": 0,
                "charging_times": 0,
            },
        }


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_demo_state():
    state = get_demo_state(DemoStateSource())
    assert_true(validate_state(state), "demo state should be valid")
    assert_true(state["vehicles"][0]["x"] == 10, "demo vehicle should get x from current_node")
    assert_true(state["vehicles"][0]["y"] == 20, "demo vehicle should get y from current_node")


def test_b_style_state():
    raw_state = {
        "nodes": [
            {"id": "depot_1", "x": 0, "y": 0, "type": "depot"},
            {"id": "task_1", "x": 10, "y": 0, "type": "task_point"},
            {"id": "cs_1", "x": 5, "y": 5, "type": "charging_station"},
        ],
        "edges": [
            {"from_node": "depot_1", "to_node": "task_1", "distance": 10},
            {"from_node": "task_1", "to_node": "cs_1", "distance": 7},
        ],
        "vehicles": [
            {
                "id": "v1",
                "current_node": "depot_1",
                "battery": 100,
                "max_battery": 120,
                "load": 0,
                "max_load": 1000,
                "load_capacity": 1000,
                "status": "idle",
                "target_node": "",
                "charging_target": "cs_1",
                "current_task_id": "t1",
                "path": [],
            },
        ],
        "tasks": [
            {"id": "t1", "node_id": "task_1", "weight": 20, "status": "waiting"},
        ],
        "charging_stations": [
            {"node_id": "cs_1", "queue_length": 2, "charging_count": 1},
        ],
        "metrics": {
            "current_time": 12,
            "scale": "small",
            "strategy": "nearest",
            "total_score": 50,
            "completed_tasks": 1,
            "timeout_tasks": 0,
            "total_distance": 10,
            "charging_times": 0,
        },
    }

    state = normalize_state(raw_state)
    assert_true(validate_state(state), "normalized B style state should be valid")
    assert_true(state["nodes"]["depot_1"]["type"] == "warehouse", "depot should become warehouse")
    assert_true(state["nodes"]["cs_1"]["type"] == "charging", "charging_station should become charging")
    assert_true("from" in state["edges"][0], "edge should have from field")
    assert_true("to" in state["edges"][0], "edge should have to field")
    assert_true("from_node" not in state["edges"][0], "edge should not keep from_node field")
    assert_true(state["vehicles"][0]["x"] == 0, "vehicle should get x from current_node")
    assert_true(state["vehicles"][0]["y"] == 0, "vehicle should get y from current_node")
    assert_true(state["vehicles"][0]["max_battery"] == 120, "vehicle should keep max_battery")
    assert_true(state["vehicles"][0]["max_load"] == 1000, "vehicle should keep max_load")
    assert_true(state["vehicles"][0]["load_capacity"] == 1000, "vehicle should keep load_capacity")
    assert_true(state["vehicles"][0]["charging_target"] == "cs_1", "vehicle should keep charging_target")
    assert_true(state["vehicles"][0]["current_task_id"] == "t1", "vehicle should keep current_task_id")
    assert_true(state["tasks"][0]["x"] == 10, "task should get x from node_id")
    assert_true(state["charging_stations"][0]["queue"] == 2, "queue_length should become queue")


def main():
    test_demo_state()
    test_b_style_state()
    print("State adapter tests passed.")


if __name__ == "__main__":
    main()
