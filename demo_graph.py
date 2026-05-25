"""Demo for team A graph and routing module.

Run from the project root:
    python3 demo_graph.py
"""

from __future__ import annotations

from pprint import pprint

from core.graph import CityGraph
from core.map_generator import generate_all_maps


def main() -> None:
    generate_all_maps()
    print("Generated map files:")
    print("- data/small_map.json")
    print("- data/medium_map.json")
    print("- data/large_map.json")
    print()

    graph = CityGraph.from_json("data/small_map.json")
    print("Loaded data/small_map.json")
    print(f"Node count: {len(graph.nodes)}")
    print(f"Edge count: {len(graph.edges)}")
    print()

    start_id = 0
    end_id = 5
    path, distance = graph.shortest_path(start_id, end_id)
    print(f"Shortest path from {start_id} to {end_id}:")
    print(f"Path: {path}")
    print(f"Distance: {distance:.2f}")
    print()

    nearest_charging_id, charging_distance = graph.nearest_node(start_id, "charging")
    print(f"Nearest charging node from {start_id}:")
    print(f"Node: {nearest_charging_id}, distance: {charging_distance:.2f}")
    print()

    state_nodes = graph.to_state_nodes()
    state_edges = graph.to_state_edges()
    sample_node_ids = sorted(state_nodes.keys())[:3]
    sample_nodes = {node_id: state_nodes[node_id] for node_id in sample_node_ids}

    print("Sample UI state nodes:")
    pprint(sample_nodes)
    print()

    print("Sample UI state edges:")
    pprint(state_edges[:3])


if __name__ == "__main__":
    main()
