"""City road graph and Dijkstra shortest path algorithm.

This module is the basic version for team A. It only uses Python standard
library code, so it is easy for beginners to read, run, and modify.
"""

from __future__ import annotations

import heapq
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


VALID_NODE_TYPES = {"warehouse", "normal", "charging", "task"}


@dataclass
class Node:
    """A point in the city road network."""

    id: int
    x: float
    y: float
    type: str = "normal"

    def __post_init__(self) -> None:
        if self.type not in VALID_NODE_TYPES:
            valid_text = ", ".join(sorted(VALID_NODE_TYPES))
            raise ValueError(f"invalid node type: {self.type}. Valid types: {valid_text}")


@dataclass
class Edge:
    """A road between two nodes.

    The graph stores one Edge object for one road in the JSON file. For a
    bidirectional road, adjacency will contain both directions.
    """

    from_node: int
    to_node: int
    distance: float
    bidirectional: bool = True

    def to_json_dict(self) -> Dict:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "distance": round(self.distance, 2),
            "bidirectional": self.bidirectional,
        }


class CityGraph:
    """Road network based on nodes, edges, and adjacency lists."""

    def __init__(self) -> None:
        self.nodes: Dict[int, Node] = {}
        self.adjacency: Dict[int, List[Tuple[int, float]]] = {}
        self.edges: List[Edge] = []

    def add_node(self, node: Node) -> None:
        """Add one node to the graph."""

        if node.id in self.nodes:
            raise ValueError(f"node {node.id} already exists")

        self.nodes[node.id] = node
        self.adjacency[node.id] = []

    def add_edge(
        self,
        from_node: int,
        to_node: int,
        distance: Optional[float] = None,
        bidirectional: bool = True,
    ) -> None:
        """Add a road between two nodes.

        If distance is not given, it is calculated from x/y coordinates using
        Euclidean distance.
        """

        if from_node not in self.nodes:
            raise KeyError(f"from_node {from_node} does not exist")
        if to_node not in self.nodes:
            raise KeyError(f"to_node {to_node} does not exist")
        if from_node == to_node:
            raise ValueError("from_node and to_node cannot be the same")

        if distance is None:
            distance = self._euclidean_distance(from_node, to_node)
        if distance < 0:
            raise ValueError("distance cannot be negative")

        distance = float(distance)
        self._add_neighbor(from_node, to_node, distance)
        if bidirectional:
            self._add_neighbor(to_node, from_node, distance)

        self.edges.append(Edge(from_node=from_node, to_node=to_node, distance=distance, bidirectional=bidirectional))

    def get_node(self, node_id: int) -> Node:
        """Return a node by id."""

        return self.nodes[node_id]

    def get_neighbors(self, node_id: int) -> List[Tuple[int, float]]:
        """Return all neighbor nodes and road distances."""

        return list(self.adjacency.get(node_id, []))

    def shortest_path(self, start_id: int, end_id: int) -> Tuple[List[int], float]:
        """Public shortest path method.

        Currently it uses Dijkstra. This wrapper lets B/C call one stable
        method even if A later changes the internal algorithm to A*.
        """

        return self.dijkstra(start_id, end_id)

    def dijkstra(self, start_id: int, end_id: int) -> Tuple[List[int], float]:
        """Find the shortest path using Dijkstra and a heap priority queue.

        Returns:
            (path, distance)

        If the target cannot be reached, returns:
            ([], float("inf"))
        """

        if start_id not in self.nodes:
            raise KeyError(f"start node {start_id} does not exist")
        if end_id not in self.nodes:
            raise KeyError(f"end node {end_id} does not exist")

        distances = {node_id: float("inf") for node_id in self.nodes}
        previous: Dict[int, Optional[int]] = {node_id: None for node_id in self.nodes}
        distances[start_id] = 0.0

        # heapq always pops the node with the smallest current distance.
        priority_queue: List[Tuple[float, int]] = [(0.0, start_id)]
        visited = set()

        while priority_queue:
            current_distance, current_id = heapq.heappop(priority_queue)

            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == end_id:
                break

            for neighbor_id, edge_distance in self.adjacency[current_id]:
                if neighbor_id in visited:
                    continue

                new_distance = current_distance + edge_distance
                if new_distance < distances[neighbor_id]:
                    distances[neighbor_id] = new_distance
                    previous[neighbor_id] = current_id
                    heapq.heappush(priority_queue, (new_distance, neighbor_id))

        if distances[end_id] == float("inf"):
            return [], float("inf")

        path = self._rebuild_path(previous, start_id, end_id)
        return path, distances[end_id]

    def nearest_node(self, start_id: int, node_type: str) -> Tuple[Optional[int], float]:
        """Find the nearest node of the given type from start_id."""

        if start_id not in self.nodes:
            raise KeyError(f"start node {start_id} does not exist")
        if node_type not in VALID_NODE_TYPES:
            valid_text = ", ".join(sorted(VALID_NODE_TYPES))
            raise ValueError(f"invalid node type: {node_type}. Valid types: {valid_text}")

        distances = {node_id: float("inf") for node_id in self.nodes}
        distances[start_id] = 0.0
        priority_queue: List[Tuple[float, int]] = [(0.0, start_id)]
        visited = set()

        while priority_queue:
            current_distance, current_id = heapq.heappop(priority_queue)
            if current_id in visited:
                continue
            visited.add(current_id)

            if self.nodes[current_id].type == node_type:
                return current_id, current_distance

            for neighbor_id, edge_distance in self.adjacency[current_id]:
                new_distance = current_distance + edge_distance
                if new_distance < distances[neighbor_id]:
                    distances[neighbor_id] = new_distance
                    heapq.heappush(priority_queue, (new_distance, neighbor_id))

        return None, float("inf")

    def to_state_nodes(self) -> Dict[int, Dict]:
        """Convert nodes to the simple state format used by the UI."""

        state_nodes = {}
        for node_id, node in sorted(self.nodes.items()):
            state_nodes[node_id] = {
                "x": node.x,
                "y": node.y,
                "type": node.type,
            }
        return state_nodes

    def to_state_edges(self) -> List[Dict]:
        """Convert edges to the simple state format used by the UI."""

        return [edge.to_json_dict() for edge in self.edges]

    @classmethod
    def from_json(cls, file_path: str | Path) -> "CityGraph":
        """Load a graph from a JSON file."""

        path = Path(file_path)
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        graph = cls()
        for node_data in data.get("nodes", []):
            graph.add_node(
                Node(
                    id=int(node_data["id"]),
                    x=float(node_data["x"]),
                    y=float(node_data["y"]),
                    type=node_data.get("type", "normal"),
                )
            )

        for edge_data in data.get("edges", []):
            from_node = edge_data["from"] if "from" in edge_data else edge_data["from_node"]
            to_node = edge_data["to"] if "to" in edge_data else edge_data["to_node"]
            graph.add_edge(
                int(from_node),
                int(to_node),
                float(edge_data["distance"]),
                bidirectional=edge_data.get("bidirectional", True),
            )

        return graph

    def save_json(self, file_path: str | Path) -> None:
        """Save the graph to a JSON file."""

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "nodes": [asdict(node) for _, node in sorted(self.nodes.items())],
            "edges": [edge.to_json_dict() for edge in self.edges],
        }

        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _add_neighbor(self, from_node: int, to_node: int, distance: float) -> None:
        """Add or update one direction in the adjacency list."""

        neighbors = self.adjacency[from_node]
        for index, (neighbor_id, _) in enumerate(neighbors):
            if neighbor_id == to_node:
                neighbors[index] = (to_node, distance)
                return
        neighbors.append((to_node, distance))

    def _euclidean_distance(self, from_node: int, to_node: int) -> float:
        start = self.nodes[from_node]
        end = self.nodes[to_node]
        return math.hypot(start.x - end.x, start.y - end.y)

    def _rebuild_path(
        self,
        previous: Dict[int, Optional[int]],
        start_id: int,
        end_id: int,
    ) -> List[int]:
        path = []
        current_id: Optional[int] = end_id

        while current_id is not None:
            path.append(current_id)
            if current_id == start_id:
                break
            current_id = previous[current_id]

        path.reverse()
        return path
