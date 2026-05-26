"""Generate stable city maps for small, medium, large, and extra-large experiments.

Supports three difficulty-driven topology modes (grid / cluster / sparse),
optional bottleneck removal, one-way edges, and non-uniform charging placement.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from core.graph import CityGraph, Node
    from core.difficulty import MapConfig
except ImportError:
    from graph import CityGraph, Node
    # Fallback for when difficulty.py isn't available
    MapConfig = None  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


# =========================================================================
# Public helpers (backward-compatible)
# =========================================================================

def generate_small_map() -> CityGraph:
    """Generate a small connected map: about 10 nodes and 2 charging stations."""
    return _generate_map(node_count=10, charging_count=2, seed=202601, extra_neighbors=2)


def generate_medium_map() -> CityGraph:
    """Generate a medium connected map: about 30 nodes and 4 charging stations."""
    return _generate_map(node_count=30, charging_count=4, seed=202602, extra_neighbors=3)


def generate_large_map() -> CityGraph:
    """Generate a large connected map: about 60 nodes and 6 charging stations."""
    return _generate_map(node_count=60, charging_count=6, seed=202603, extra_neighbors=3)


def generate_extra_large_map() -> CityGraph:
    """Generate an extra-large connected map: about 80 nodes and 8 charging stations."""
    return _generate_map(node_count=80, charging_count=8, seed=202604, extra_neighbors=4)


def generate_all_maps() -> Dict[str, CityGraph]:
    """Generate and save all map JSON files under data/."""
    maps = {
        "small": generate_small_map(),
        "medium": generate_medium_map(),
        "large": generate_large_map(),
        "extra_large": generate_extra_large_map(),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, graph in maps.items():
        graph.save_json(DATA_DIR / f"{name}_map.json")
    return maps


# =========================================================================
# Config-driven entry point (primary API for difficulty-aware generation)
# =========================================================================

def generate_map_from_config(config: MapConfig) -> CityGraph:
    """Generate a map following the given difficulty MapConfig.

    This is the recommended entry point for difficulty-aware map generation.
    """
    rng = random.Random(config.seed)
    graph = CityGraph()

    if config.cluster_mode == "cluster":
        _build_cluster_graph(graph, config, rng)
    else:
        _build_grid_graph(graph, config, rng)

    # Post-generation topology transforms
    if config.bottleneck_fraction > 0:
        _apply_bottlenecks(graph, config, rng)
    if config.one_way_fraction > 0:
        _apply_one_way_edges(graph, config, rng)

    return graph


# =========================================================================
# Core grid-based generator (preserved for backward compatibility)
# =========================================================================

def _generate_map(
    node_count: int,
    charging_count: int,
    seed: int,
    extra_neighbors: int,
    jitter_range: float = 2.5,
    charging_distribution: str = "uniform",
) -> CityGraph:
    """Build a grid-based connected graph.

    This is the legacy entry point kept for backward compatibility with
    existing callers that pass individual parameters.
    """
    cfg = MapConfig(
        node_count=node_count,
        charging_count=charging_count,
        extra_neighbors=extra_neighbors,
        seed=seed,
        cluster_mode="grid",
        jitter_range=jitter_range,
        charging_distribution=charging_distribution,
    )
    return generate_map_from_config(cfg)


# =========================================================================
# Grid layout
# =========================================================================

def _build_grid_graph(graph: CityGraph, config: MapConfig, rng: random.Random) -> None:
    """Build a graph with nodes laid out on a rectangular grid + jitter."""
    node_count = config.node_count
    charging_ids = _choose_charging_ids(node_count, config.charging_count, config, rng)

    for node_id in range(node_count):
        if node_id == 0:
            node = Node(id=0, x=8.0, y=50.0, type="warehouse")
        else:
            x, y = _grid_position(node_id, node_count, config.jitter_range, rng)
            node_type = "charging" if node_id in charging_ids else "normal"
            node = Node(id=node_id, x=x, y=y, type=node_type)
        graph.add_node(node)

    _build_base_edges(graph, node_count, config.extra_neighbors)


# =========================================================================
# Cluster layout (HARD difficulty)
# =========================================================================

def _build_cluster_graph(graph: CityGraph, config: MapConfig, rng: random.Random) -> None:
    """Build a graph where nodes are grouped into spatial clusters.

    Nodes within a cluster are densely connected; only a few bridge edges
    connect different clusters, creating natural bottlenecks.
    """
    node_count = config.node_count
    # Determine cluster count: ~4-6 clusters depending on node_count
    num_clusters = max(3, min(6, node_count // 15))
    cluster_size = node_count // num_clusters

    # Place cluster centers on the map
    cluster_centers: List[Tuple[float, float]] = []
    for c in range(num_clusters):
        cx = 15 + rng.uniform(0, 70)
        cy = 15 + rng.uniform(0, 70)
        cluster_centers.append((cx, cy))

    # Assign each node to a cluster (node 0 = warehouse, always in first cluster)
    node_cluster: Dict[int, int] = {}
    for node_id in range(node_count):
        if node_id == 0:
            node_cluster[node_id] = 0
        else:
            node_cluster[node_id] = rng.randint(0, num_clusters - 1)

    # Place charging stations using the configured distribution
    charging_ids = _choose_charging_ids(node_count, config.charging_count, config, rng)

    # Create nodes
    for node_id in range(node_count):
        c = node_cluster[node_id]
        cx, cy = cluster_centers[c]
        if node_id == 0:
            node = Node(id=0, x=cx, y=cy, type="warehouse")
        else:
            jit = config.jitter_range
            x = _clamp(cx + rng.uniform(-jit * 3, jit * 3), 5, 95)
            y = _clamp(cy + rng.uniform(-jit * 3, jit * 3), 5, 95)
            node_type = "charging" if node_id in charging_ids else "normal"
            node = Node(id=node_id, x=x, y=y, type=node_type)
        graph.add_node(node)

    # Build intra-cluster edges (dense)
    _build_cluster_edges(graph, node_count, node_cluster, config.extra_neighbors)


def _build_cluster_edges(
    graph: CityGraph,
    node_count: int,
    node_cluster: Dict[int, int],
    extra_neighbors: int,
) -> None:
    """Connect nodes: dense within clusters, sparse bridges between clusters."""
    edge_keys: Set[Tuple[int, int]] = set()

    # --- Phase 1: connectivity guarantee (prefer same-cluster) ---
    for node_id in range(1, node_count):
        c = node_cluster[node_id]
        candidates = [i for i in range(node_id) if node_cluster[i] == c]
        if not candidates:
            candidates = list(range(node_id))  # first node in a new cluster
        nearest = min(candidates, key=lambda other: _distance_between(graph, node_id, other))
        _add_unique_edge(graph, edge_keys, node_id, nearest, bidirectional=True)

    # --- Phase 2: intra-cluster extra edges ---
    for node_id in range(node_count):
        c = node_cluster[node_id]
        same_cluster = [i for i in range(node_count) if i != node_id and node_cluster[i] == c]
        same_cluster.sort(key=lambda other: _distance_between(graph, node_id, other))
        for neighbor_id in same_cluster[:extra_neighbors]:
            _add_unique_edge(graph, edge_keys, node_id, neighbor_id, bidirectional=True)

    # --- Phase 3: inter-cluster bridge edges (at least 1 per cluster pair) ---
    num_clusters = max(node_cluster.values()) + 1
    for c1 in range(num_clusters):
        for c2 in range(c1 + 1, num_clusters):
            nodes_c1 = [i for i in range(node_count) if node_cluster[i] == c1]
            nodes_c2 = [i for i in range(node_count) if node_cluster[i] == c2]
            # Find nearest pair between clusters
            best_dist = float("inf")
            best_pair = None
            for n1 in nodes_c1:
                for n2 in nodes_c2:
                    d = _distance_between(graph, n1, n2)
                    if d < best_dist:
                        best_dist = d
                        best_pair = (n1, n2)
            if best_pair:
                _add_unique_edge(graph, edge_keys, best_pair[0], best_pair[1], bidirectional=True)


# =========================================================================
# Base edge building (shared by grid mode)
# =========================================================================

def _build_base_edges(graph: CityGraph, node_count: int, extra_neighbors: int) -> None:
    """Standard edge construction: MST guarantee + extra nearby edges."""
    edge_keys: Set[Tuple[int, int]] = set()

    # Connectivity guarantee: connect each new node to nearest previous node
    for node_id in range(1, node_count):
        nearest_previous = min(
            range(node_id),
            key=lambda other_id: _distance_between(graph, node_id, other_id),
        )
        _add_unique_edge(graph, edge_keys, node_id, nearest_previous, bidirectional=True)

    # Extra edges for density
    for node_id in range(node_count):
        neighbors = sorted(
            (other_id for other_id in range(node_count) if other_id != node_id),
            key=lambda other_id: _distance_between(graph, node_id, other_id),
        )
        for neighbor_id in neighbors[:extra_neighbors]:
            _add_unique_edge(graph, edge_keys, node_id, neighbor_id, bidirectional=True)


# =========================================================================
# Topology transforms
# =========================================================================

def _apply_bottlenecks(
    graph: CityGraph,
    config: MapConfig,
    rng: random.Random,
) -> None:
    """Remove a fraction of extra edges to create navigation bottlenecks.

    Only edges whose removal would NOT disconnect the graph are eligible.
    Uses Dijkstra to verify an alternate path exists between endpoints.
    """
    if not graph.edges:
        return

    removable_edges: List[int] = []  # store edge indices

    for idx, edge in enumerate(graph.edges):
        a, b = edge.from_node, edge.to_node
        # Temporarily remove both directions
        _remove_adjacency(graph, a, b)
        _remove_adjacency(graph, b, a)

        _, dist = graph.shortest_path(a, b)
        if dist != float("inf"):
            removable_edges.append(idx)

        # Restore
        _restore_adjacency(graph, a, b, edge.distance)
        _restore_adjacency(graph, b, a, edge.distance)

    if not removable_edges:
        return

    remove_count = max(1, int(len(removable_edges) * config.bottleneck_fraction))
    to_remove = set(rng.sample(removable_edges, min(remove_count, len(removable_edges))))

    # Record edges to remove and their endpoints before filtering
    edges_to_delete = [(idx, graph.edges[idx]) for idx in to_remove]

    # Permanently remove adjacency for deleted edges
    for _, edge in edges_to_delete:
        _remove_adjacency(graph, edge.from_node, edge.to_node)
        _remove_adjacency(graph, edge.to_node, edge.from_node)

    # Remove from edge list (reverse order to preserve indices)
    graph.edges = [e for i, e in enumerate(graph.edges) if i not in to_remove]


def _apply_one_way_edges(
    graph: CityGraph,
    config: MapConfig,
    rng: random.Random,
) -> None:
    """Convert a fraction of edges to one-way.

    Only non-MST edges are eligible to avoid creating unreachable nodes.
    We use edge betweenness approximation: edges whose endpoints have an
    alternative path are safe to make one-way.
    """
    if not graph.edges:
        return

    safe_indices: List[int] = []
    for idx, edge in enumerate(graph.edges):
        a, b = edge.from_node, edge.to_node
        # Temporarily remove a→b direction
        _remove_adjacency(graph, a, b)
        path, dist = graph.shortest_path(a, b)
        _restore_adjacency(graph, a, b, edge.distance)

        if dist != float("inf"):
            safe_indices.append(idx)

    count = max(1, int(len(safe_indices) * config.one_way_fraction))
    to_convert = set(rng.sample(safe_indices, min(count, len(safe_indices))))

    for idx in to_convert:
        edge = graph.edges[idx]
        # Randomly choose which direction to keep
        if rng.random() < 0.5:
            _remove_adjacency(graph, edge.to_node, edge.from_node)
        else:
            _remove_adjacency(graph, edge.from_node, edge.to_node)


# =========================================================================
# Charging station placement
# =========================================================================

def _choose_charging_ids(
    node_count: int,
    charging_count: int,
    config: MapConfig,
    rng: random.Random,
) -> Set[int]:
    """Select charging station node IDs based on the configured distribution."""
    if charging_count <= 0:
        return set()

    if config.charging_distribution == "clustered":
        return _choose_charging_ids_clustered(node_count, charging_count, rng)
    elif config.charging_distribution == "scarce":
        scarce_count = max(1, int(charging_count * 0.7))
        return _choose_charging_ids_uniform(node_count, scarce_count)
    else:
        return _choose_charging_ids_uniform(node_count, charging_count)


def _choose_charging_ids_uniform(node_count: int, charging_count: int) -> Set[int]:
    """Evenly spaced charging station IDs (original behavior)."""
    charging_ids: Set[int] = set()
    step = (node_count - 1) / (charging_count + 1)

    for i in range(charging_count):
        node_id = 1 + round((i + 1) * step)
        charging_ids.add(min(node_count - 1, max(1, node_id)))

    node_id = 1
    while len(charging_ids) < charging_count:
        charging_ids.add(node_id)
        node_id += 1

    return charging_ids


def _choose_charging_ids_clustered(
    node_count: int,
    charging_count: int,
    rng: random.Random,
) -> Set[int]:
    """Place all charging stations within 2-3 nearby node groups.

    This creates large areas without charging coverage, increasing difficulty.
    """
    # Pick a random anchor region and concentrate stations around it
    anchor = rng.randint(1, max(1, node_count - 1))
    spread = max(5, node_count // 4)

    candidates: Set[int] = set()
    for node_id in range(1, node_count):
        if abs(node_id - anchor) <= spread:
            candidates.add(node_id)

    if len(candidates) < charging_count:
        # Fall back to all non-warehouse nodes
        candidates = set(range(1, node_count))

    chosen = set(rng.sample(sorted(candidates), min(charging_count, len(candidates))))

    # If we still need more, fill from remaining
    node_id = 1
    while len(chosen) < charging_count:
        if node_id not in chosen:
            chosen.add(node_id)
        node_id += 1

    return chosen


# =========================================================================
# Grid positioning
# =========================================================================

def _grid_position(
    node_id: int,
    node_count: int,
    jitter_range: float,
    rng: random.Random,
) -> Tuple[float, float]:
    cols = math.ceil(math.sqrt(node_count))
    rows = math.ceil(node_count / cols)
    grid_index = node_id - 1
    row = grid_index // cols
    col = grid_index % cols

    x_step = 84 / max(1, cols - 1)
    y_step = 84 / max(1, rows - 1)
    x = 10 + col * x_step + rng.uniform(-jitter_range, jitter_range)
    y = 8 + row * y_step + rng.uniform(-jitter_range, jitter_range)

    return round(_clamp(x, 5, 95), 2), round(_clamp(y, 5, 95), 2)


# =========================================================================
# Edge utilities
# =========================================================================

def _add_unique_edge(
    graph: CityGraph,
    edge_keys: Set[Tuple[int, int]],
    a: int,
    b: int,
    bidirectional: bool = True,
) -> None:
    if a == b:
        return
    edge_key = tuple(sorted((a, b)))
    if edge_key in edge_keys:
        return
    graph.add_edge(a, b, bidirectional=bidirectional)
    edge_keys.add(edge_key)


def _distance_between(graph: CityGraph, a: int, b: int) -> float:
    node_a = graph.get_node(a)
    node_b = graph.get_node(b)
    return math.hypot(node_a.x - node_b.x, node_a.y - node_b.y)


def _remove_adjacency(graph: CityGraph, a: int, b: int) -> None:
    """Remove adjacency a→b if it exists."""
    if a in graph.adjacency:
        graph.adjacency[a] = [
            (nid, d) for nid, d in graph.adjacency[a] if nid != b
        ]


def _restore_adjacency(graph: CityGraph, a: int, b: int, distance: float) -> None:
    """Restore adjacency a→b (no-op if already present)."""
    if a not in graph.adjacency:
        graph.adjacency[a] = []
    for nid, _ in graph.adjacency[a]:
        if nid == b:
            return
    graph.adjacency[a].append((b, distance))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
