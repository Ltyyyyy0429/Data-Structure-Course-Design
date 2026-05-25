"""Generate stable city maps for small, medium, and large experiments."""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, Set, Tuple

try:
    from core.graph import CityGraph, Node
except ImportError:
    from graph import CityGraph, Node


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def generate_small_map() -> CityGraph:
    """Generate a small connected map: about 10 nodes and 2 charging stations."""

    return _generate_map(node_count=10, charging_count=2, seed=202601, extra_neighbors=2)


def generate_medium_map() -> CityGraph:
    """Generate a medium connected map: about 30 nodes and 4 charging stations."""

    return _generate_map(node_count=30, charging_count=4, seed=202602, extra_neighbors=3)


def generate_large_map() -> CityGraph:
    """Generate a large connected map: about 60 nodes and 6 charging stations."""

    return _generate_map(node_count=60, charging_count=6, seed=202603, extra_neighbors=3)


def generate_all_maps() -> Dict[str, CityGraph]:
    """Generate and save all map JSON files under data/."""

    maps = {
        "small": generate_small_map(),
        "medium": generate_medium_map(),
        "large": generate_large_map(),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, graph in maps.items():
        graph.save_json(DATA_DIR / f"{name}_map.json")

    return maps


def _generate_map(
    node_count: int,
    charging_count: int,
    seed: int,
    extra_neighbors: int,
) -> CityGraph:
    rng = random.Random(seed)
    graph = CityGraph()
    charging_ids = _choose_charging_ids(node_count, charging_count)

    for node_id in range(node_count):
        if node_id == 0:
            node = Node(id=0, x=8.0, y=50.0, type="warehouse")
        else:
            x, y = _grid_position(node_id, node_count, rng)
            node_type = "charging" if node_id in charging_ids else "normal"
            node = Node(id=node_id, x=x, y=y, type=node_type)
        graph.add_node(node)

    edge_keys: Set[Tuple[int, int]] = set()

    # First connect every new node to one previous node. This guarantees that
    # the whole graph is connected and has no isolated node.
    for node_id in range(1, node_count):
        nearest_previous = min(
            range(node_id),
            key=lambda other_id: _distance_between(graph, node_id, other_id),
        )
        _add_unique_edge(graph, edge_keys, node_id, nearest_previous)

    # Then add several nearby roads so the map looks more like a city network.
    for node_id in range(node_count):
        neighbors = sorted(
            (other_id for other_id in range(node_count) if other_id != node_id),
            key=lambda other_id: _distance_between(graph, node_id, other_id),
        )
        for neighbor_id in neighbors[:extra_neighbors]:
            _add_unique_edge(graph, edge_keys, node_id, neighbor_id)

    return graph


def _choose_charging_ids(node_count: int, charging_count: int) -> Set[int]:
    charging_ids = set()
    step = (node_count - 1) / (charging_count + 1)

    for index in range(charging_count):
        node_id = 1 + round((index + 1) * step)
        charging_ids.add(min(node_count - 1, max(1, node_id)))

    node_id = 1
    while len(charging_ids) < charging_count:
        charging_ids.add(node_id)
        node_id += 1

    return charging_ids


def _grid_position(node_id: int, node_count: int, rng: random.Random) -> Tuple[float, float]:
    cols = math.ceil(math.sqrt(node_count))
    rows = math.ceil(node_count / cols)
    grid_index = node_id - 1
    row = grid_index // cols
    col = grid_index % cols

    x_step = 84 / max(1, cols - 1)
    y_step = 84 / max(1, rows - 1)
    x = 10 + col * x_step + rng.uniform(-2.5, 2.5)
    y = 8 + row * y_step + rng.uniform(-2.5, 2.5)

    return round(_clamp(x, 5, 95), 2), round(_clamp(y, 5, 95), 2)


def _add_unique_edge(graph: CityGraph, edge_keys: Set[Tuple[int, int]], a: int, b: int) -> None:
    if a == b:
        return

    edge_key = tuple(sorted((a, b)))
    if edge_key in edge_keys:
        return

    graph.add_edge(a, b)
    edge_keys.add(edge_key)


def _distance_between(graph: CityGraph, a: int, b: int) -> float:
    node_a = graph.get_node(a)
    node_b = graph.get_node(b)
    return math.hypot(node_a.x - node_b.x, node_a.y - node_b.y)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
