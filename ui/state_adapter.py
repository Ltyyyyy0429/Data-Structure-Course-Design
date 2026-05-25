"""State adapter between the Pygame UI and simulation engines.

The UI should read one stable state dictionary, no matter whether the data
comes from the current demo world or the future real simulator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


CORE_STATE_FIELDS = (
    "nodes",
    "edges",
    "vehicles",
    "tasks",
    "charging_stations",
    "metrics",
)


def normalize_node_type(node_type: Any) -> str:
    """Convert A/B node type names to the names used by the Pygame UI."""

    type_text = str(node_type or "normal").strip().lower()
    type_mapping = {
        "depot": "warehouse",
        "warehouse": "warehouse",
        "charging_station": "charging",
        "charging": "charging",
        "task": "task",
        "normal": "normal",
    }
    return type_mapping.get(type_text, "normal")


def normalize_edges(edges: Any) -> List[Dict[str, Any]]:
    """Normalize edge fields to {'from': ..., 'to': ..., 'distance': ...}."""

    normalized_edges = []
    for index, edge in enumerate(edges or []):
        if not isinstance(edge, dict):
            raise TypeError(f"edge #{index} must be a dictionary")

        if "from" in edge:
            from_node = edge["from"]
        elif "from_node" in edge:
            from_node = edge["from_node"]
        else:
            raise ValueError(f"edge #{index} is missing 'from' or 'from_node'")

        if "to" in edge:
            to_node = edge["to"]
        elif "to_node" in edge:
            to_node = edge["to_node"]
        else:
            raise ValueError(f"edge #{index} is missing 'to' or 'to_node'")

        normalized_edges.append(
            {
                "from": from_node,
                "to": to_node,
                "distance": edge.get("distance", 0),
            }
        )

    return normalized_edges


def normalize_nodes(nodes: Any) -> Dict[Any, Dict[str, Any]]:
    """Normalize list or dict nodes to the UI node dictionary format."""

    normalized_nodes = {}

    if isinstance(nodes, dict):
        node_items = nodes.items()
    elif isinstance(nodes, list):
        node_items = []
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise TypeError(f"node #{index} must be a dictionary")
            if "id" not in node:
                raise ValueError(f"node #{index} is missing 'id'")
            node_items.append((node["id"], node))
    else:
        raise TypeError("nodes must be a list or a dictionary")

    for node_id, node in node_items:
        if not isinstance(node, dict):
            raise TypeError(f"node {node_id} must be a dictionary")

        normalized_nodes[node_id] = {
            "x": node.get("x", 0),
            "y": node.get("y", 0),
            "type": normalize_node_type(node.get("type", "normal")),
        }

    return normalized_nodes


def attach_vehicle_positions(vehicles: Any, nodes: Dict[Any, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Make sure vehicles have coordinates that the Pygame map can draw."""

    normalized_vehicles = []

    for index, vehicle in enumerate(vehicles or []):
        if not isinstance(vehicle, dict):
            raise TypeError(f"vehicle #{index} must be a dictionary")

        current_node = _first_present(vehicle, "current_node", "current_node_id")
        normalized_vehicle = {
            "id": vehicle.get("id", f"vehicle_{index + 1}"),
            "x": vehicle.get("x"),
            "y": vehicle.get("y"),
            "current_node": current_node,
            "battery": vehicle.get("battery", 0),
            "load": vehicle.get("load", 0),
            "status": vehicle.get("status", "idle"),
            "target_node": vehicle.get("target_node", vehicle.get("target_node_id", "")),
            "path": list(vehicle.get("path") or []),
        }

        node = _find_node(nodes, current_node)
        if (normalized_vehicle["x"] is None or normalized_vehicle["y"] is None) and node:
            normalized_vehicle["x"] = node["x"]
            normalized_vehicle["y"] = node["y"]

        if normalized_vehicle["x"] is None:
            normalized_vehicle["x"] = 0
        if normalized_vehicle["y"] is None:
            normalized_vehicle["y"] = 0

        normalized_vehicles.append(normalized_vehicle)

    return normalized_vehicles


def normalize_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize demo state or simulator.get_state() output for the Pygame UI."""

    validate_state(raw_state)

    nodes = normalize_nodes(raw_state["nodes"])
    normalized_state = {
        "nodes": nodes,
        "edges": normalize_edges(raw_state["edges"]),
        "vehicles": attach_vehicle_positions(raw_state["vehicles"], nodes),
        "tasks": _attach_task_positions(raw_state["tasks"], nodes),
        "charging_stations": _attach_charging_station_positions(
            raw_state["charging_stations"],
            nodes,
        ),
        "metrics": _normalize_metrics(raw_state["metrics"]),
    }

    validate_state(normalized_state)
    return normalized_state


def validate_state(state: Dict[str, Any]) -> bool:
    """Check that a state dictionary contains the fields required by the UI.

    Returns True when the state is valid. Raises a clear error when it is not,
    so later integration problems are easier for beginners to locate.
    """

    if not isinstance(state, dict):
        raise TypeError("state must be a dictionary")

    missing_fields = [field for field in CORE_STATE_FIELDS if field not in state]
    if missing_fields:
        missing_text = ", ".join(missing_fields)
        raise ValueError(f"state is missing required fields: {missing_text}")

    if not isinstance(state["metrics"], dict):
        raise TypeError("state['metrics'] must be a dictionary")

    return True


def get_demo_state(demo_world: Any) -> Dict[str, Any]:
    """Return demo data for the current standalone UI prototype."""

    raw_state = demo_world.get_state()
    return normalize_state(raw_state)


def load_state_from_simulator(simulator: Any) -> Dict[str, Any]:
    """Return real simulator data after B module provides simulator.get_state()."""

    raw_state = simulator.get_state()
    return normalize_state(raw_state)


def _attach_task_positions(tasks: Any, nodes: Dict[Any, Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_tasks = []

    for index, task in enumerate(tasks or []):
        if not isinstance(task, dict):
            raise TypeError(f"task #{index} must be a dictionary")

        node_id = _first_present(task, "node_id", "current_node", "node")
        normalized_task = dict(task)
        normalized_task.setdefault("id", f"task_{index + 1}")
        normalized_task.setdefault("weight", 0)
        normalized_task.setdefault("status", "waiting")
        normalized_task["node_id"] = node_id

        node = _find_node(nodes, node_id)
        if ("x" not in normalized_task or "y" not in normalized_task) and node:
            normalized_task["x"] = node["x"]
            normalized_task["y"] = node["y"]

        normalized_task.setdefault("x", 0)
        normalized_task.setdefault("y", 0)
        normalized_tasks.append(normalized_task)

    return normalized_tasks


def _attach_charging_station_positions(
    charging_stations: Any,
    nodes: Dict[Any, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    normalized_stations = []

    for index, station in enumerate(charging_stations or []):
        if not isinstance(station, dict):
            raise TypeError(f"charging station #{index} must be a dictionary")

        node_id = _first_present(station, "node_id", "id", "current_node")
        normalized_station = {
            "id": station.get("id", node_id),
            "node_id": node_id,
            "x": station.get("x"),
            "y": station.get("y"),
            "queue": station.get("queue", station.get("queue_length", 0)),
            "queue_length": station.get("queue_length", station.get("queue", 0)),
            "charging_count": station.get("charging_count", 0),
        }

        node = _find_node(nodes, node_id)
        if (normalized_station["x"] is None or normalized_station["y"] is None) and node:
            normalized_station["x"] = node["x"]
            normalized_station["y"] = node["y"]

        if normalized_station["x"] is None:
            normalized_station["x"] = 0
        if normalized_station["y"] is None:
            normalized_station["y"] = 0

        normalized_stations.append(normalized_station)

    return normalized_stations


def _normalize_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    normalized_metrics = dict(metrics)
    normalized_metrics.setdefault("current_time", 0)
    normalized_metrics.setdefault("scale", "unknown")
    normalized_metrics.setdefault("strategy", "unknown")
    normalized_metrics.setdefault("total_score", 0)
    normalized_metrics.setdefault("completed_tasks", 0)
    normalized_metrics.setdefault("timeout_tasks", 0)
    normalized_metrics.setdefault("total_distance", 0)
    normalized_metrics.setdefault("charging_times", 0)
    return normalized_metrics


def _first_present(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _find_node(nodes: Dict[Any, Dict[str, Any]], node_id: Any) -> Optional[Dict[str, Any]]:
    if node_id in nodes:
        return nodes[node_id]

    node_text = str(node_id)
    if node_text in nodes:
        return nodes[node_text]

    try:
        node_int = int(node_id)
    except (TypeError, ValueError):
        return None

    return nodes.get(node_int)
