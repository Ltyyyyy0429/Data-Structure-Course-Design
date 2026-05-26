"""Demo showing B Simulator using A CityGraph/Dijkstra via RealPathfinder.

Run from the project root:
    python3 demo_simulator_real_pathfinder.py [--difficulty easy|medium|hard]
"""

from __future__ import annotations

import sys

from simulator import Simulator
from simulator.pathfinder_adapter import RealPathfinder
from core.difficulty import get_difficulty_config


def build_b_graph_from_a_pathfinder(pathfinder: RealPathfinder) -> dict:
    """Convert A map data to B simulator's current graph_data shape."""
    nodes = []
    for node_id, node in pathfinder.graph.nodes.items():
        if node.type == "warehouse":
            b_type = "depot"
        elif node.type == "charging":
            b_type = "charging_station"
        else:
            b_type = "task_point"
        nodes.append({"id": node_id, "x": node.x, "y": node.y, "type": b_type})

    edges = []
    for edge in pathfinder.graph.edges:
        edges.append({
            "from_node": edge.from_node,
            "to_node": edge.to_node,
            "distance": edge.distance,
        })

    return {"nodes": nodes, "edges": edges}


def main() -> None:
    difficulty = "easy"
    if len(sys.argv) > 1 and sys.argv[1] == "--difficulty":
        difficulty = sys.argv[2] if len(sys.argv) > 2 else "easy"

    config = get_difficulty_config("small", difficulty)
    print(f"难度: {difficulty.upper()} | 车辆数: {config.vehicle.count_for_scale('small')} | "
          f"电池: {config.vehicle.battery_capacity_kwh}kWh | "
          f"能耗: {config.vehicle.energy_per_km}kWh/km")

    pathfinder = RealPathfinder("data/small_map.json")
    graph_data = build_b_graph_from_a_pathfinder(pathfinder)

    simulator = Simulator(graph_data=graph_data, scale="small", strategy="nearest",
                          pathfinder=pathfinder, config=config)

    simulator.add_test_task("real_t1", 5, 180, 0, 40)
    simulator.add_test_task("real_t2", 6, 220, 0, 55)
    simulator._dispatch_tasks()

    print("Simulator is using:", type(simulator.pathfinder).__name__)
    print("Distance 0 -> 5:", simulator._get_distance(0, 5))
    print("Path 0 -> 5:", simulator._get_path(0, 5))

    for _ in range(5):
        simulator.update(1)

    state = simulator.get_state()
    print("Current time:", state["metrics"]["current_time"])
    print("Total distance:", state["metrics"]["total_distance"])
    print("Completed tasks:", state["metrics"]["completed_tasks"])


if __name__ == "__main__":
    main()
