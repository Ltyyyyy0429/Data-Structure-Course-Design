"""Adapter that lets B Simulator use A CityGraph / Dijkstra.

The B simulator currently calls a small MockPathfinder with methods such as
get_shortest_path() and get_distance(). RealPathfinder keeps those method names
so it can be swapped in with very little simulator-side change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.graph import CityGraph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP_FILE = PROJECT_ROOT / "data" / "small_map.json"


class RealPathfinder:
    """Pathfinder backed by A module CityGraph and Dijkstra shortest path."""

    def __init__(self, map_file: str | Path = DEFAULT_MAP_FILE) -> None:
        self.map_file = self._resolve_map_file(map_file)
        self.graph = CityGraph.from_json(self.map_file)

    def find_path_and_distance(self, start_node: Any, end_node: Any) -> Tuple[List[int], float]:
        """规范寻路入口：返回 (完整节点序列, 距离)，异常直接抛出."""

        start_id = self._normalize_node_id(start_node)
        end_id = self._normalize_node_id(end_node)
        return self.graph.shortest_path(start_id, end_id)

    def find_path(self, start_node: Any, end_node: Any) -> Tuple[List[int], float]:
        """Return shortest path and distance using CityGraph.shortest_path()."""

        return self.find_path_and_distance(start_node, end_node)

    def get_shortest_path(self, start_node: Any, end_node: Any) -> List[int]:
        """Compatibility method for B MockPathfinder."""

        path, _ = self.find_path(start_node, end_node)
        return path

    def get_path(self, start_node: Any, end_node: Any) -> List[int]:
        """Compatibility alias used by some routing code."""

        return self.get_shortest_path(start_node, end_node)

    def shortest_path(self, start_node: Any, end_node: Any) -> Tuple[List[int], float]:
        """Compatibility alias matching A CityGraph naming."""

        return self.find_path(start_node, end_node)

    def get_distance(self, start_node: Any, end_node: Any) -> float:
        """Return only the shortest path distance."""

        _, distance = self.find_path(start_node, end_node)
        return distance

    def nearest_charging_station(self, start_node: Any) -> Tuple[int | None, float]:
        """Find the closest charging node from start_node."""

        start_id = self._normalize_node_id(start_node)
        return self.graph.nearest_node(start_id, "charging")

    def get_state_nodes(self) -> Dict[int, Dict]:
        """Return nodes in the simple state format used by D UI."""

        return self.graph.to_state_nodes()

    def get_state_edges(self) -> List[Dict]:
        """Return edges in the simple state format used by D UI."""

        return self.graph.to_state_edges()

    def _normalize_node_id(self, node_id: Any) -> int:
        """Accept int ids and numeric string ids such as '0'."""

        if node_id in self.graph.nodes:
            return node_id

        try:
            normalized_id = int(node_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"node id {node_id!r} cannot be used with {self.map_file}. "
                "RealPathfinder expects A-map node ids such as 0, 1, 2..."
            ) from exc

        if normalized_id not in self.graph.nodes:
            raise KeyError(f"node {normalized_id} does not exist in {self.map_file}")

        return normalized_id

    def _resolve_map_file(self, map_file: str | Path) -> Path:
        path = Path(map_file)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path
