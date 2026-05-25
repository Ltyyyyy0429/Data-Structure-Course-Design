"""Demo for A-B real pathfinder integration.

Run from the project root:
    python3 demo_real_pathfinder.py
"""

from __future__ import annotations

from pprint import pprint

from simulator.pathfinder_adapter import RealPathfinder


def main() -> None:
    pathfinder = RealPathfinder("data/small_map.json")

    print("Loaded map: data/small_map.json")
    print(f"Node count: {len(pathfinder.graph.nodes)}")
    print(f"Edge count: {len(pathfinder.graph.edges)}")
    print()

    start_node = 0
    end_node = 5
    path, distance = pathfinder.find_path(start_node, end_node)
    print(f"Shortest path from {start_node} to {end_node}:")
    print(f"Path: {path}")
    print(f"Distance: {distance:.2f}")
    print()

    charging_node, charging_distance = pathfinder.nearest_charging_station(start_node)
    print(f"Nearest charging station from {start_node}:")
    print(f"Node: {charging_node}, distance: {charging_distance:.2f}")
    print()

    state_nodes = pathfinder.get_state_nodes()
    state_edges = pathfinder.get_state_edges()
    first_node_ids = sorted(state_nodes.keys())[:3]
    first_nodes = {node_id: state_nodes[node_id] for node_id in first_node_ids}

    print("Sample UI state nodes:")
    pprint(first_nodes)
    print()

    print("Sample UI state edges:")
    pprint(state_edges[:3])


if __name__ == "__main__":
    main()
