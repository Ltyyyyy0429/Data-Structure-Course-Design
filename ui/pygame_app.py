"""Pygame demo UI for the new energy logistics fleet simulation.

Run from the project root:
    python3 ui/pygame_app.py

This file currently uses demo data only. When the simulator from team B is
ready, replace the demo state line with simulator.get_state(), or call
load_state_from_simulator(simulator) from state_adapter.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

try:
    from state_adapter import get_demo_state, load_state_from_simulator
except ImportError:
    from ui.state_adapter import get_demo_state, load_state_from_simulator

try:
    from colors import (
        BACKGROUND,
        BLACK,
        BLOCK_ALT_FILL,
        BLOCK_FILL,
        CHARGING,
        CONTROL_BAR,
        DANGER,
        GRID_LINE,
        INFO,
        MAP_BACKGROUND,
        NORMAL_NODE,
        PANEL_BACKGROUND,
        PANEL_BORDER,
        PANEL_CARD,
        PATH_HIGHLIGHT,
        PATH_HIGHLIGHT_ALT,
        PURPLE,
        ROAD,
        ROAD_MAIN,
        SUCCESS,
        TASK,
        TASK_ASSIGNED,
        TASK_COMPLETED,
        TASK_TIMEOUT,
        TASK_WAITING,
        TARGET_RING,
        TEXT_MAIN,
        TEXT_MUTED,
        VEHICLE,
        VEHICLE_CHARGING,
        VEHICLE_IDLE,
        VEHICLE_MOVING,
        VEHICLE_RETURNING,
        VEHICLE_WAITING,
        WAREHOUSE,
        WARNING,
        WHITE,
    )
except ImportError:
    from ui.colors import (
        BACKGROUND,
        BLACK,
        BLOCK_ALT_FILL,
        BLOCK_FILL,
        CHARGING,
        CONTROL_BAR,
        DANGER,
        GRID_LINE,
        INFO,
        MAP_BACKGROUND,
        NORMAL_NODE,
        PANEL_BACKGROUND,
        PANEL_BORDER,
        PANEL_CARD,
        PATH_HIGHLIGHT,
        PATH_HIGHLIGHT_ALT,
        PURPLE,
        ROAD,
        ROAD_MAIN,
        SUCCESS,
        TASK,
        TASK_ASSIGNED,
        TASK_COMPLETED,
        TASK_TIMEOUT,
        TASK_WAITING,
        TARGET_RING,
        TEXT_MAIN,
        TEXT_MUTED,
        VEHICLE,
        VEHICLE_CHARGING,
        VEHICLE_IDLE,
        VEHICLE_MOVING,
        VEHICLE_RETURNING,
        VEHICLE_WAITING,
        WAREHOUSE,
        WARNING,
        WHITE,
    )


WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700
MAP_RECT = pygame.Rect(24, 24, 730, 604)
PANEL_RECT = pygame.Rect(778, 24, 298, 604)
CONTROL_BAR_RECT = pygame.Rect(24, 646, 1052, 34)
WORLD_WIDTH = 100
WORLD_HEIGHT = 100
FPS = 60
DEFAULT_MAX_BATTERY_KWH = {
    "easy": 120.0,
    "medium": 100.0,
    "hard": 80.0,
}


TEXT = {
    "zh": {
        "title": "新能源物流车队调度仿真",
        "time": "当前时间",
        "scale": "当前规模",
        "strategy": "当前策略",
        "score": "总收益",
        "completed": "完成任务",
        "completed_short": "完成",
        "timeout": "超时任务",
        "timeout_short": "超时",
        "distance": "总路径长度",
        "charges": "充电次数",
        "vehicles": "车辆状态",
        "battery": "电量",
        "status": "状态",
        "summary": "Summary",
        "metrics": "Metrics",
        "charging_pressure": "Charging Pressure",
        "controls": "Controls",
        "requests": "充电需求",
        "queue_events": "排队次数",
        "max_queue": "最大队列",
        "wait_time": "等待总时长",
        "load": "载重",
        "paused": "已暂停",
        "running": "运行中",
        "help1": "SPACE 暂停/继续",
        "help2": "1 nearest  2 largest  3 hybrid",
        "help3": "R 重置  ESC 退出",
        "queue": "队列",
    },
    "en": {
        "title": "New Energy Fleet Dispatch Demo",
        "time": "Current time",
        "scale": "Scale",
        "strategy": "Strategy",
        "score": "Total score",
        "completed": "Completed tasks",
        "completed_short": "Done",
        "timeout": "Timeout tasks",
        "timeout_short": "Timeout",
        "distance": "Total distance",
        "charges": "Charging times",
        "vehicles": "Vehicles",
        "battery": "Battery",
        "status": "Status",
        "summary": "Summary",
        "metrics": "Metrics",
        "charging_pressure": "Charging Pressure",
        "controls": "Controls",
        "requests": "Requests",
        "queue_events": "Queue events",
        "max_queue": "Max queue",
        "wait_time": "Wait time",
        "load": "Load",
        "paused": "Paused",
        "running": "Running",
        "help1": "SPACE pause/resume",
        "help2": "1 nearest  2 largest  3 hybrid",
        "help3": "R reset  ESC quit",
        "queue": "Queue",
    },
}

STATUS_TEXT = {
    "zh": {
        "idle": "空闲",
        "moving": "行驶中",
        "delivering": "配送中",
        "charging": "充电中",
        "waiting_for_charge": "等待充电",
        "returning": "返仓中",
    },
    "en": {
        "idle": "idle",
        "moving": "moving",
        "delivering": "delivering",
        "charging": "charging",
        "waiting_for_charge": "waiting charge",
        "returning": "returning",
    },
}


@dataclass
class FontSet:
    language: str
    title: pygame.font.Font
    normal: pygame.font.Font
    small: pygame.font.Font
    tiny: pygame.font.Font


class DemoWorld:
    """Small fake simulator used before A/B/C modules are connected."""

    def __init__(self) -> None:
        self.strategy = "nearest"
        self.reset()

    def reset(self) -> None:
        self.current_time = 0.0

        self.nodes = [
            {"id": "W", "x": 8, "y": 52, "type": "warehouse"},
            {"id": "N1", "x": 22, "y": 25, "type": "normal"},
            {"id": "N2", "x": 24, "y": 72, "type": "normal"},
            {"id": "C1", "x": 45, "y": 18, "type": "charging"},
            {"id": "N3", "x": 48, "y": 43, "type": "normal"},
            {"id": "N4", "x": 45, "y": 78, "type": "normal"},
            {"id": "N5", "x": 67, "y": 31, "type": "normal"},
            {"id": "N6", "x": 72, "y": 60, "type": "normal"},
            {"id": "C2", "x": 82, "y": 78, "type": "charging"},
            {"id": "N7", "x": 91, "y": 42, "type": "normal"},
        ]

        self.edges = [
            {"from": "W", "to": "N1"},
            {"from": "W", "to": "N2"},
            {"from": "N1", "to": "C1"},
            {"from": "N1", "to": "N3"},
            {"from": "N2", "to": "N4"},
            {"from": "N3", "to": "C1"},
            {"from": "N3", "to": "N5"},
            {"from": "N3", "to": "N6"},
            {"from": "N4", "to": "N6"},
            {"from": "N4", "to": "C2"},
            {"from": "N5", "to": "N7"},
            {"from": "N6", "to": "N7"},
            {"from": "N6", "to": "C2"},
            {"from": "C2", "to": "N7"},
        ]

        self.vehicle_routes = {
            "V1": ["W", "N1", "C1", "N3", "N5", "N7", "N6", "W"],
            "V2": ["W", "N2", "N4", "C2", "N6", "N3", "N1", "W"],
        }
        self.vehicle_offsets = {"V1": 0.0, "V2": 6.0}

        self.task_templates = [
            {"id": "T1", "node_id": "N3", "appear": 2, "finish": 18, "weight": 8},
            {"id": "T2", "node_id": "N5", "appear": 8, "finish": 26, "weight": 13},
            {"id": "T3", "node_id": "N4", "appear": 14, "finish": 32, "weight": 10},
            {"id": "T4", "node_id": "N7", "appear": 22, "finish": 42, "weight": 16},
            {"id": "T5", "node_id": "N6", "appear": 34, "finish": 55, "weight": 12},
        ]

    def set_strategy(self, strategy: str) -> None:
        if strategy in {"nearest", "largest", "energy_aware_hybrid"}:
            self.strategy = strategy

    def update(self, dt: float) -> None:
        self.current_time += dt * 2.2

    def get_state(self) -> Dict:
        node_by_id = {node["id"]: node for node in self.nodes}
        cycle_time = self.current_time % 60

        tasks = []
        for task in self.task_templates:
            if task["appear"] <= cycle_time <= task["finish"]:
                node = node_by_id[task["node_id"]]
                tasks.append(
                    {
                        "id": task["id"],
                        "node_id": task["node_id"],
                        "x": node["x"],
                        "y": node["y"],
                        "weight": task["weight"],
                        "status": "waiting",
                    }
                )

        charging_stations = []
        for index, station_id in enumerate(["C1", "C2"]):
            node = node_by_id[station_id]
            queue_length = int((self.current_time // 9 + index) % 4)
            charging_stations.append(
                {
                    "id": station_id,
                    "node_id": station_id,
                    "x": node["x"],
                    "y": node["y"],
                    "queue": queue_length,
                }
            )

        vehicles = []
        for vehicle_id, route in self.vehicle_routes.items():
            vehicle = self._get_vehicle_on_route(vehicle_id, route, node_by_id)
            vehicles.append(vehicle)

        completed_tasks = int(self.current_time // 7)
        timeout_tasks = int(self.current_time // 31)
        strategy_bonus = 25 if self.strategy == "largest" else 45 if self.strategy == "energy_aware_hybrid" else 0
        distance_factor = 13.5 if self.strategy == "nearest" else 14.2 if self.strategy == "energy_aware_hybrid" else 15.0

        metrics = {
            "current_time": int(self.current_time),
            "scale": "small",
            "strategy": self.strategy,
            "total_score": completed_tasks * 120 - timeout_tasks * 80 + strategy_bonus,
            "completed_tasks": completed_tasks,
            "timeout_tasks": timeout_tasks,
            "total_distance": round(self.current_time * distance_factor, 1),
            "charging_times": int(self.current_time // 24),
            "charging_requests": int(self.current_time // 18),
            "charging_queue_events": int(self.current_time // 52),
            "max_queue_length": int((self.current_time // 36) % 4),
            "total_charging_wait_time": round(max(0, self.current_time - 40) * 0.4, 1),
        }

        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "vehicles": vehicles,
            "tasks": tasks,
            "charging_stations": charging_stations,
            "metrics": metrics,
        }

    def _get_vehicle_on_route(
        self, vehicle_id: str, route: List[str], node_by_id: Dict[str, Dict]
    ) -> Dict:
        seconds_per_edge = 5.0
        route_time = self.current_time + self.vehicle_offsets[vehicle_id]
        route_progress = route_time / seconds_per_edge
        edge_index = int(route_progress) % len(route)
        next_index = (edge_index + 1) % len(route)
        ratio = route_progress - math.floor(route_progress)

        start_node = node_by_id[route[edge_index]]
        end_node = node_by_id[route[next_index]]
        x = start_node["x"] + (end_node["x"] - start_node["x"]) * ratio
        y = start_node["y"] + (end_node["y"] - start_node["y"]) * ratio

        near_start = ratio < 0.20
        if start_node["type"] == "charging" and near_start:
            status = "charging"
            battery = min(100, 62 + int(ratio * 180))
        elif end_node["id"] == "W":
            status = "returning"
            battery = max(20, 90 - int((route_progress * 7) % 70))
        else:
            status = "delivering"
            battery = max(18, 96 - int((route_progress * 6) % 78))

        preview_path = []
        for offset in range(1, 5):
            preview_path.append(route[(edge_index + offset) % len(route)])

        return {
            "id": vehicle_id,
            "x": x,
            "y": y,
            "current_node": start_node["id"],
            "battery": battery,
            "max_battery": 100,
            "load": 120 if vehicle_id == "V1" else 80,
            "status": status,
            "target_node": end_node["id"],
            "path": preview_path,
        }

def choose_fonts() -> FontSet:
    chinese_font_names = [
        "PingFang SC",
        "Heiti SC",
        "Arial Unicode MS",
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
    ]

    font_path = None
    for font_name in chinese_font_names:
        font_path = pygame.font.match_font(font_name)
        if font_path:
            break

    if font_path:
        return FontSet(
            language="zh",
            title=pygame.font.Font(font_path, 25),
            normal=pygame.font.Font(font_path, 19),
            small=pygame.font.Font(font_path, 16),
            tiny=pygame.font.Font(font_path, 13),
        )

    return FontSet(
        language="en",
        title=pygame.font.SysFont(None, 25),
        normal=pygame.font.SysFont(None, 19),
        small=pygame.font.SysFont(None, 16),
        tiny=pygame.font.SysFont(None, 13),
    )


def world_to_screen(x: float, y: float) -> Tuple[int, int]:
    screen_x = MAP_RECT.left + int(x / WORLD_WIDTH * MAP_RECT.width)
    screen_y = MAP_RECT.top + int(y / WORLD_HEIGHT * MAP_RECT.height)
    return screen_x, screen_y


def draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Tuple[int, int, int],
    position: Tuple[int, int],
) -> None:
    text_surface = font.render(text, True, color)
    surface.blit(text_surface, position)


def shorten_text(text, max_chars: int) -> str:
    """Keep labels inside compact UI cards."""

    text = str(text)
    replacements = {
        "energy_aware_hybrid": "hybrid",
        "waiting_for_charge": "wait_charge",
        "delivering": "moving",
    }
    text = replacements.get(text, text)
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3] + "..."


def safe_get_metric(metrics: Dict, key: str, default=0):
    return metrics.get(key, default) if isinstance(metrics, dict) else default


def draw_text_right(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Tuple[int, int, int],
    right: int,
    y: int,
    max_chars: int = 14,
) -> None:
    text_surface = font.render(shorten_text(text, max_chars), True, color)
    surface.blit(text_surface, (right - text_surface.get_width(), y))


def draw_centered_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Tuple[int, int, int],
    center: Tuple[int, int],
) -> None:
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=center)
    surface.blit(text_surface, text_rect)


def build_node_lookup(nodes: Dict) -> Dict:
    """Accept both old list nodes and normalized dict nodes."""

    if isinstance(nodes, dict):
        return {node_id: {"id": node_id, **node} for node_id, node in nodes.items()}

    lookup = {}
    for node in nodes or []:
        node_id = node.get("id")
        if node_id is not None:
            lookup[node_id] = node
    return lookup


def find_node_for_draw(node_by_id: Dict, node_id) -> Dict | None:
    """Find a node while tolerating int/string id differences."""

    if node_id in node_by_id:
        return node_by_id[node_id]

    node_text = str(node_id)
    if node_text in node_by_id:
        return node_by_id[node_text]

    try:
        node_int = int(node_id)
    except (TypeError, ValueError):
        return None

    return node_by_id.get(node_int)


def vehicle_screen_position(vehicle: Dict, node_by_id: Dict) -> Tuple[int, int] | None:
    """Return the vehicle's current screen position if it can be located."""

    if vehicle.get("x") is not None and vehicle.get("y") is not None:
        return world_to_screen(float(vehicle.get("x", 0)), float(vehicle.get("y", 0)))

    current_node = vehicle.get("current_node", vehicle.get("current_node_id"))
    node = find_node_for_draw(node_by_id, current_node)
    if node:
        return world_to_screen(node.get("x", 0), node.get("y", 0))

    return None


def get_vehicle_color(status: str) -> Tuple[int, int, int]:
    status_text = str(status or "").lower()
    if status_text in {"idle", "waiting"}:
        return VEHICLE_IDLE
    if status_text in {"moving", "delivering"}:
        return VEHICLE_MOVING
    if status_text == "charging":
        return VEHICLE_CHARGING
    if status_text == "waiting_for_charge":
        return VEHICLE_WAITING
    if status_text == "returning":
        return VEHICLE_RETURNING
    return VEHICLE


def get_task_color(status: str) -> Tuple[int, int, int]:
    status_text = str(status or "waiting").lower()
    if status_text == "assigned":
        return TASK_ASSIGNED
    if status_text in {"delivering", "in_progress", "moving"}:
        return INFO
    if status_text == "completed":
        return TASK_COMPLETED
    if status_text in {"timeout", "timed_out", "failed"}:
        return TASK_TIMEOUT
    return TASK_WAITING


def node_key(node_id) -> str:
    return str(node_id)


def build_edge_lookup(edges: List[Dict]) -> set[Tuple[str, str]]:
    """Build a visual edge lookup so demo paths do not invent roads."""

    lookup = set()
    for edge in edges or []:
        from_id = edge.get("from", edge.get("from_node"))
        to_id = edge.get("to", edge.get("to_node"))
        if from_id is None or to_id is None:
            continue
        lookup.add((node_key(from_id), node_key(to_id)))
        lookup.add((node_key(to_id), node_key(from_id)))
    return lookup


def edge_exists(edge_lookup: set[Tuple[str, str]], from_id, to_id) -> bool:
    return (node_key(from_id), node_key(to_id)) in edge_lookup


def safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def target_kind_for_node(node: Dict, task_node_keys: set[str], charging_node_keys: set[str]) -> str:
    node_id = node_key(node.get("id"))
    node_type = str(node.get("type", "normal")).lower()
    if node_id in charging_node_keys or node_type == "charging":
        return "charging"
    if node_id in task_node_keys or node_type == "task":
        return "task"
    return "normal"


def draw_target_highlight(
    surface: pygame.Surface,
    node_position: Tuple[int, int],
    target_kind: str,
    frame_count: int,
) -> None:
    if target_kind == "charging":
        color = CHARGING
    elif target_kind == "task":
        color = TASK_WAITING
    else:
        color = TARGET_RING

    pulse = int((math.sin(frame_count * 0.10) + 1) * 3)
    pygame.draw.circle(surface, color, node_position, 18 + pulse, width=3)
    pygame.draw.circle(surface, WHITE, node_position, 23 + pulse, width=1)


def draw_route_flow_markers(
    overlay: pygame.Surface,
    path_points: List[Tuple[int, int]],
    frame_count: int,
    color: Tuple[int, int, int, int],
) -> None:
    if len(path_points) < 2:
        return

    phase = (frame_count % 60) / 60.0
    marker_spacing = 38

    for start, end in zip(path_points, path_points[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        segment_length = math.hypot(dx, dy)
        if segment_length < 1:
            continue
        marker_count = max(1, int(segment_length // marker_spacing))
        for index in range(marker_count):
            t = (index + phase) / marker_count
            if 0 < t < 1:
                x = int(start[0] + dx * t)
                y = int(start[1] + dy * t)
                pygame.draw.circle(overlay, color, (x, y), 4)


def draw_vehicle_paths(
    surface: pygame.Surface,
    vehicles: List[Dict],
    node_by_id: Dict,
    edges: List[Dict],
    tasks: List[Dict],
    charging_stations: List[Dict],
    frame_count: int = 0,
) -> None:
    """Draw each vehicle's planned path without failing on missing path nodes."""

    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    edge_lookup = build_edge_lookup(edges)
    task_node_keys = {node_key(task.get("node_id")) for task in tasks or [] if task.get("node_id") is not None}
    charging_node_keys = {
        node_key(station.get("node_id", station.get("current_node")))
        for station in charging_stations or []
        if station.get("node_id", station.get("current_node")) is not None
    }
    path_colors = [
        (*PATH_HIGHLIGHT, 145),
        (*PATH_HIGHLIGHT_ALT, 135),
        (*PURPLE, 125),
    ]

    for index, vehicle in enumerate(vehicles or []):
        path = vehicle.get("path") or []
        drawable_segments = []
        current_segment = []
        start_pos = vehicle_screen_position(vehicle, node_by_id)
        if start_pos and path:
            current_segment.append(start_pos)

        previous_node_id = vehicle.get("current_node", vehicle.get("current_node_id"))
        for node_id in path:
            node = find_node_for_draw(node_by_id, node_id)
            if not node:
                if len(current_segment) >= 2:
                    drawable_segments.append(current_segment)
                current_segment = []
                previous_node_id = None
                continue

            node_pos = world_to_screen(node.get("x", 0), node.get("y", 0))
            if previous_node_id is not None and previous_node_id != node_id:
                if edge_exists(edge_lookup, previous_node_id, node_id):
                    current_segment.append(node_pos)
                else:
                    if len(current_segment) >= 2:
                        drawable_segments.append(current_segment)
                    current_segment = [node_pos]
            elif not current_segment:
                current_segment.append(node_pos)
            previous_node_id = node_id

        if len(current_segment) >= 2:
            drawable_segments.append(current_segment)

        if drawable_segments:
            path_color = path_colors[index % len(path_colors)]
            for points in drawable_segments:
                pygame.draw.lines(overlay, path_color, False, points, width=7)
                pygame.draw.lines(overlay, (*WHITE, 105), False, points, width=2)
                draw_route_flow_markers(overlay, points, frame_count, (*WHITE, 180))

        target_node = find_node_for_draw(node_by_id, vehicle.get("target_node"))
        if target_node:
            target_pos = world_to_screen(target_node.get("x", 0), target_node.get("y", 0))
            target_kind = target_kind_for_node(target_node, task_node_keys, charging_node_keys)
            draw_target_highlight(overlay, target_pos, target_kind, frame_count)

    surface.blit(overlay, (0, 0))


def draw_map(surface: pygame.Surface, state: Dict, fonts: FontSet, frame_count: int = 0, paused: bool = False) -> None:
    pygame.draw.rect(surface, MAP_BACKGROUND, MAP_RECT, border_radius=10)
    draw_city_blocks(surface)
    pygame.draw.rect(surface, PANEL_BORDER, MAP_RECT, width=1, border_radius=10)

    node_by_id = build_node_lookup(state.get("nodes", {}))
    nodes = list(node_by_id.values())

    draw_roads(surface, state.get("edges", []), node_by_id)

    for node in nodes:
        if node.get("type") == "normal":
            pygame.draw.circle(surface, NORMAL_NODE, world_to_screen(node.get("x", 0), node.get("y", 0)), 3)

    draw_vehicle_paths(
        surface,
        state.get("vehicles", []),
        node_by_id,
        state.get("edges", []),
        state.get("tasks", []),
        state.get("charging_stations", []),
        frame_count,
    )

    for node in nodes:
        if node.get("type") == "warehouse":
            draw_warehouse(surface, node, fonts)

    for station in state.get("charging_stations", []):
        draw_charging_station(surface, station, fonts)

    for task in state.get("tasks", []):
        draw_task(surface, task, fonts)

    metrics = state.get("metrics", {})
    for vehicle in state.get("vehicles", []):
        draw_vehicle(surface, vehicle, fonts, frame_count, metrics)

    if paused:
        draw_paused_overlay(surface, MAP_RECT, fonts)


def draw_city_blocks(surface: pygame.Surface) -> None:
    """Draw a light map-like background with blocks and minor streets."""

    block_width = MAP_RECT.width // 5
    block_height = MAP_RECT.height // 4

    for row in range(4):
        for col in range(5):
            x = MAP_RECT.left + col * block_width + 12
            y = MAP_RECT.top + row * block_height + 12
            width = block_width - 24
            height = block_height - 24
            color = BLOCK_FILL if (row + col) % 2 == 0 else BLOCK_ALT_FILL
            pygame.draw.rect(surface, color, (x, y, width, height), border_radius=5)

    draw_grid(surface)


def draw_grid(surface: pygame.Surface) -> None:
    for i in range(1, 10):
        x = MAP_RECT.left + MAP_RECT.width * i // 10
        pygame.draw.line(surface, GRID_LINE, (x, MAP_RECT.top + 8), (x, MAP_RECT.bottom - 8), width=1)

    for i in range(1, 8):
        y = MAP_RECT.top + MAP_RECT.height * i // 8
        pygame.draw.line(surface, GRID_LINE, (MAP_RECT.left + 8, y), (MAP_RECT.right - 8, y), width=1)


def get_edge_nodes(edge: Dict, node_by_id: Dict) -> Tuple[Dict | None, Dict | None]:
    from_id = edge.get("from", edge.get("from_node"))
    to_id = edge.get("to", edge.get("to_node"))
    return find_node_for_draw(node_by_id, from_id), find_node_for_draw(node_by_id, to_id)


def get_edge_distance(edge: Dict, start_node: Dict, end_node: Dict) -> float:
    distance = edge.get("distance")
    try:
        return float(distance)
    except (TypeError, ValueError):
        dx = float(start_node.get("x", 0)) - float(end_node.get("x", 0))
        dy = float(start_node.get("y", 0)) - float(end_node.get("y", 0))
        return math.hypot(dx, dy)


def draw_roads(surface: pygame.Surface, edges: List[Dict], node_by_id: Dict) -> None:
    road_items = []
    for edge in edges or []:
        start_node, end_node = get_edge_nodes(edge, node_by_id)
        if not start_node or not end_node:
            continue
        road_items.append((edge, start_node, end_node, get_edge_distance(edge, start_node, end_node)))

    distances = [item[3] for item in road_items]
    main_threshold = sorted(distances)[max(0, int(len(distances) * 0.65) - 1)] if distances else 9999

    for edge, start_node, end_node, distance in road_items:
        start_pos = world_to_screen(start_node.get("x", 0), start_node.get("y", 0))
        end_pos = world_to_screen(end_node.get("x", 0), end_node.get("y", 0))
        is_main_road = distance >= main_threshold or edge.get("main", False)
        width = 6 if is_main_road else 3
        color = ROAD_MAIN if is_main_road else ROAD
        pygame.draw.line(surface, WHITE, start_pos, end_pos, width=width + 2)
        pygame.draw.line(surface, color, start_pos, end_pos, width=width)


def draw_warehouse(surface: pygame.Surface, node: Dict, fonts: FontSet) -> None:
    center = world_to_screen(node.get("x", 0), node.get("y", 0))
    base_rect = pygame.Rect(0, 0, 34, 24)
    base_rect.center = (center[0], center[1] + 4)
    roof_points = [
        (base_rect.left - 3, base_rect.top + 2),
        (center[0], base_rect.top - 13),
        (base_rect.right + 3, base_rect.top + 2),
    ]
    pygame.draw.polygon(surface, WAREHOUSE, roof_points)
    pygame.draw.rect(surface, WAREHOUSE, base_rect, border_radius=4)
    pygame.draw.rect(surface, WHITE, base_rect, width=2, border_radius=4)
    door = pygame.Rect(0, 0, 8, 13)
    door.midbottom = (center[0], base_rect.bottom - 2)
    pygame.draw.rect(surface, (26, 81, 148), door, border_radius=2)
    draw_centered_text(surface, "W", fonts.tiny, WHITE, (center[0], center[1] - 1))


def draw_charging_station(surface: pygame.Surface, station: Dict, fonts: FontSet) -> None:
    if station.get("x") is None or station.get("y") is None:
        return
    center = world_to_screen(station.get("x", 0), station.get("y", 0))
    pin_points = [(center[0], center[1] + 19), (center[0] - 10, center[1] + 4), (center[0] + 10, center[1] + 4)]
    pygame.draw.polygon(surface, CHARGING, pin_points)
    pygame.draw.circle(surface, CHARGING, center, 15)
    pygame.draw.circle(surface, WHITE, center, 15, width=2)
    draw_centered_text(surface, "C", fonts.small, WHITE, center)
    queue = safe_int(station.get("queue_length", station.get("queue", 0)))
    charging_count = safe_int(station.get("charging_count", 0))
    label = f"Q{queue} / P{charging_count}"
    draw_label(surface, label, fonts.tiny, TEXT_MAIN, (center[0] - 24, center[1] + 22))
    draw_charging_queue_dots(surface, center, queue, fonts)


def draw_charging_queue_dots(
    surface: pygame.Surface,
    station_position: Tuple[int, int],
    queue_length: int,
    fonts: FontSet,
) -> None:
    if queue_length <= 0:
        return

    start_x = station_position[0] + 22
    start_y = station_position[1] - 13
    visible_count = min(queue_length, 5)
    for index in range(visible_count):
        dot_center = (start_x + index * 8, start_y)
        pygame.draw.circle(surface, WARNING, dot_center, 4)
        pygame.draw.circle(surface, WHITE, dot_center, 4, width=1)

    if queue_length > visible_count:
        draw_text(surface, f"+{queue_length - visible_count}", fonts.tiny, WARNING, (start_x + visible_count * 8 + 2, start_y - 7))


def draw_task(surface: pygame.Surface, task: Dict, fonts: FontSet) -> None:
    if task.get("x") is None or task.get("y") is None:
        return
    center = world_to_screen(task.get("x", 0), task.get("y", 0))
    status = str(task.get("status", "waiting")).lower()
    color = get_task_color(status)
    radius = 9 if status == "completed" else 13
    pin_points = [(center[0], center[1] + 17), (center[0] - 9, center[1] + 3), (center[0] + 9, center[1] + 3)]
    pygame.draw.polygon(surface, color, pin_points)
    pygame.draw.circle(surface, color, center, radius)
    pygame.draw.circle(surface, WHITE, center, radius, width=2)
    task_label = str(task.get("id", "T"))
    task_label = "T" if len(task_label) > 3 else task_label
    if status in {"timeout", "timed_out", "failed"}:
        task_label = "!"
    draw_centered_text(surface, task_label, fonts.tiny, BLACK if color == TASK_WAITING else WHITE, center)
    if status != "completed":
        weight = task.get("weight", "-")
        draw_label(surface, f"{weight}kg", fonts.tiny, TEXT_MAIN, (center[0] + 12, center[1] - 12))


def draw_low_battery_warning(
    surface: pygame.Surface,
    position: Tuple[int, int],
    frame_count: int,
) -> None:
    pulse = int((math.sin(frame_count * 0.22) + 1) * 3)
    pygame.draw.circle(surface, DANGER, position, 20 + pulse, width=3)
    if frame_count % 42 < 22:
        pygame.draw.circle(surface, WARNING, position, 15 + pulse, width=1)


def draw_vehicle(
    surface: pygame.Surface,
    vehicle: Dict,
    fonts: FontSet,
    frame_count: int = 0,
    metrics: Dict | None = None,
) -> None:
    if vehicle.get("x") is None or vehicle.get("y") is None:
        return
    center = world_to_screen(vehicle.get("x", 0), vehicle.get("y", 0))
    color = get_vehicle_color(vehicle.get("status", "idle"))
    battery_level, battery_text = get_battery_display(vehicle, metrics)
    body = pygame.Rect(0, 0, 30, 16)
    body.center = center
    cab = pygame.Rect(body.left + 7, body.top - 5, 13, 8)
    if battery_level < 20:
        draw_low_battery_warning(surface, center, frame_count)
    pygame.draw.rect(surface, color, body, border_radius=5)
    pygame.draw.rect(surface, color, cab, border_radius=3)
    pygame.draw.rect(surface, WHITE, body, width=2, border_radius=5)
    pygame.draw.circle(surface, BLACK, (body.left + 7, body.bottom), 3)
    pygame.draw.circle(surface, BLACK, (body.right - 7, body.bottom), 3)
    draw_centered_text(surface, str(vehicle.get("id", "V")), fonts.tiny, WHITE, (center[0], center[1] - 1))
    draw_label(surface, battery_text, fonts.tiny, TEXT_MAIN, (center[0] + 17, center[1] - 21))


def draw_label(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Tuple[int, int, int],
    position: Tuple[int, int],
) -> None:
    text_surface = font.render(str(text), True, color)
    rect = text_surface.get_rect(topleft=position).inflate(8, 4)
    pygame.draw.rect(surface, (*WHITE, 255), rect, border_radius=4)
    pygame.draw.rect(surface, PANEL_BORDER, rect, width=1, border_radius=4)
    surface.blit(text_surface, text_surface.get_rect(center=rect.center))


def get_default_max_battery(metrics: Dict | None = None) -> float:
    """Return UI fallback battery capacity when vehicle max_battery is missing."""

    difficulty = ""
    if isinstance(metrics, dict):
        difficulty = str(metrics.get("difficulty", "")).lower()
    return DEFAULT_MAX_BATTERY_KWH.get(difficulty, DEFAULT_MAX_BATTERY_KWH["easy"])


def get_battery_display(vehicle: Dict, metrics: Dict | None = None) -> Tuple[float, str]:
    """Return battery ratio for bars and label for text.

    If max_battery is missing, the UI uses a difficulty-aware fallback:
    hard=80kWh, medium=100kWh, otherwise 120kWh.
    """

    try:
        battery_value = float(vehicle.get("battery", 0) or 0)
    except (TypeError, ValueError):
        battery_value = 0.0

    max_battery = vehicle.get("max_battery")
    if max_battery is not None:
        try:
            max_battery_value = float(max_battery)
        except (TypeError, ValueError):
            max_battery_value = 0.0

    else:
        max_battery_value = get_default_max_battery(metrics)

    if max_battery_value <= 0:
        max_battery_value = get_default_max_battery(metrics)

    percent = battery_value / max_battery_value * 100
    ratio_for_bar = max(0.0, min(100.0, percent))
    return ratio_for_bar, f"{ratio_for_bar:.0f}%"


def format_battery_display(vehicle: Dict, metrics: Dict | None = None) -> Tuple[str, float]:
    """Backward-compatible wrapper for older drawing code."""

    ratio_for_bar, battery_label = get_battery_display(vehicle, metrics)
    return battery_label, ratio_for_bar


def draw_card(surface: pygame.Surface, rect: pygame.Rect, title: str, fonts: FontSet) -> pygame.Rect:
    pygame.draw.rect(surface, PANEL_CARD, rect, border_radius=8)
    pygame.draw.rect(surface, PANEL_BORDER, rect, width=1, border_radius=8)
    draw_text(surface, shorten_text(title, 24), fonts.small, TEXT_MAIN, (rect.left + 12, rect.top + 8))
    pygame.draw.line(
        surface,
        PANEL_BORDER,
        (rect.left + 12, rect.top + 30),
        (rect.right - 12, rect.top + 30),
        width=1,
    )
    return pygame.Rect(rect.left + 12, rect.top + 34, rect.width - 24, rect.height - 44)


def draw_metric_row(
    surface: pygame.Surface,
    label: str,
    value,
    fonts: FontSet,
    rect: pygame.Rect,
    y: int,
    value_color: Tuple[int, int, int] = TEXT_MAIN,
    line_height: int = 17,
    label_chars: int = 16,
    value_chars: int = 14,
) -> int | None:
    if y + line_height > rect.bottom:
        return None

    draw_text(surface, f"{shorten_text(label, label_chars)}:", fonts.tiny, TEXT_MUTED, (rect.left, y))
    draw_text_right(surface, value, fonts.tiny, value_color, rect.right, y, value_chars)
    return y + line_height


def draw_status_badge(
    surface: pygame.Surface,
    text: str,
    fonts: FontSet,
    rect: pygame.Rect,
    color: Tuple[int, int, int],
    max_chars: int = 12,
) -> None:
    text_surface = fonts.tiny.render(shorten_text(text, max_chars), True, WHITE)
    pygame.draw.rect(surface, color, rect, border_radius=rect.height // 2)
    surface.blit(text_surface, text_surface.get_rect(center=rect.center))


def draw_status_pill(
    surface: pygame.Surface,
    text: str,
    color: Tuple[int, int, int],
    fonts: FontSet,
    position: Tuple[int, int],
) -> None:
    text_surface = fonts.tiny.render(shorten_text(text, 12), True, WHITE)
    rect = text_surface.get_rect(topleft=position).inflate(14, 6)
    draw_status_badge(surface, text, fonts, rect, color)


def draw_battery_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    battery_level: float,
    battery_text: str,
    fonts: FontSet,
) -> None:
    battery_level = max(0.0, min(100.0, battery_level))
    fill_width = int(rect.width * battery_level / 100)
    fill_color = SUCCESS if battery_level >= 50 else WARNING if battery_level >= 20 else DANGER

    pygame.draw.rect(surface, (229, 235, 243), rect, border_radius=rect.height // 2)
    if fill_width > 0:
        fill_rect = pygame.Rect(rect.left, rect.top, fill_width, rect.height)
        pygame.draw.rect(surface, fill_color, fill_rect, border_radius=rect.height // 2)
    pygame.draw.rect(surface, PANEL_BORDER, rect, width=1, border_radius=rect.height // 2)
    draw_centered_text(surface, battery_text, fonts.tiny, TEXT_MAIN, rect.center)


def draw_metric_big_number(
    surface: pygame.Surface,
    label: str,
    value,
    rect: pygame.Rect,
    fonts: FontSet,
    color: Tuple[int, int, int],
) -> None:
    draw_text(surface, shorten_text(label, 18), fonts.tiny, TEXT_MUTED, (rect.left, rect.top))
    value_text = shorten_text(value, 13)
    value_surface = fonts.title.render(value_text, True, color)
    surface.blit(value_surface, (rect.left, rect.top + 15))


def draw_summary_card(
    surface: pygame.Surface,
    rect: pygame.Rect,
    metrics: Dict,
    fonts: FontSet,
    labels: Dict,
    paused: bool,
) -> None:
    inner = draw_card(surface, rect, labels["summary"], fonts)
    project_name = "新能源车队调度" if fonts.language == "zh" else "Fleet Dispatch System"
    draw_text(surface, shorten_text(project_name, 17), fonts.tiny, TEXT_MAIN, (inner.left, inner.top))

    run_label = labels["paused"] if paused else labels["running"]
    badge_rect = pygame.Rect(inner.right - 70, inner.top - 2, 70, 20)
    draw_status_badge(surface, run_label, fonts, badge_rect, WARNING if paused else SUCCESS)

    y = inner.top + 20
    y = draw_metric_row(surface, labels["time"], f"{safe_get_metric(metrics, 'current_time', 0)} min", fonts, inner, y, line_height=16) or y
    strategy = shorten_text(safe_get_metric(metrics, "strategy", "-"), 12)
    y = draw_metric_row(surface, labels["strategy"], strategy, fonts, inner, y, line_height=16) or y
    difficulty = safe_get_metric(metrics, "difficulty", None)
    scale = safe_get_metric(metrics, "scale", "-")
    if difficulty is not None:
        mode_value = f"{shorten_text(difficulty, 7)} / {shorten_text(scale, 8)}"
        draw_metric_row(surface, "Mode", mode_value, fonts, inner, y, line_height=16, value_chars=18)
    else:
        draw_metric_row(surface, labels["scale"], scale, fonts, inner, y, line_height=16)


def draw_metrics_card(surface: pygame.Surface, rect: pygame.Rect, metrics: Dict, fonts: FontSet, labels: Dict) -> None:
    inner = draw_card(surface, rect, labels["metrics"], fonts)
    score_rect = pygame.Rect(inner.left, inner.top, inner.width, 48)
    draw_metric_big_number(
        surface,
        labels["score"],
        f"{safe_get_metric(metrics, 'total_score', 0)}",
        score_rect,
        fonts,
        INFO,
    )

    lower_y = inner.top + 55
    completed = safe_get_metric(metrics, "completed_tasks", 0)
    timeout = safe_get_metric(metrics, "timeout_tasks", 0)
    draw_text(surface, labels.get("completed_short", labels["completed"]), fonts.tiny, TEXT_MUTED, (inner.left, lower_y))
    draw_text(surface, str(completed), fonts.normal, SUCCESS, (inner.left, lower_y + 16))
    draw_text_right(surface, labels.get("timeout_short", labels["timeout"]), fonts.tiny, TEXT_MUTED, inner.right, lower_y)
    draw_text_right(surface, str(timeout), fonts.normal, DANGER, inner.right, lower_y + 16)


def draw_charging_card(surface: pygame.Surface, rect: pygame.Rect, metrics: Dict, fonts: FontSet, labels: Dict) -> None:
    inner = draw_card(surface, rect, labels["charging_pressure"], fonts)
    rows = [
        ("Requests", safe_get_metric(metrics, "charging_requests", 0), TEXT_MAIN),
        ("Charging", safe_get_metric(metrics, "charging_times", 0), SUCCESS),
        ("Queue events", safe_get_metric(metrics, "charging_queue_events", 0), WARNING),
        ("Max queue", safe_get_metric(metrics, "max_queue_length", 0), WARNING),
        ("Wait time", safe_get_metric(metrics, "total_charging_wait_time", 0), TEXT_MAIN),
    ]

    y = inner.top
    for label, value, color in rows:
        next_y = draw_metric_row(surface, label, value, fonts, inner, y, color, line_height=15, value_chars=11)
        if next_y is None:
            draw_text(surface, "...", fonts.tiny, TEXT_MUTED, (inner.left, max(inner.top, inner.bottom - 15)))
            break
        y = next_y


def draw_vehicle_list_card(
    surface: pygame.Surface,
    rect: pygame.Rect,
    vehicles: List[Dict],
    fonts: FontSet,
    labels: Dict,
    metrics: Dict | None = None,
) -> None:
    inner = draw_card(surface, rect, labels["vehicles"], fonts)
    row_height = 30
    max_rows = min(5, max(0, (inner.height - 18) // row_height))
    shown = 0

    for index, vehicle in enumerate(vehicles or []):
        if shown >= max_rows:
            break
        row_y = inner.top + shown * row_height
        if row_y + row_height > inner.bottom - 16:
            break

        vehicle_id = shorten_text(vehicle.get("id", f"V{index + 1}"), 8)
        status_key = str(vehicle.get("status", "idle")).lower()
        status = STATUS_TEXT[fonts.language].get(status_key, status_key)
        status_color = get_vehicle_color(status_key)
        battery_level, battery_text = get_battery_display(vehicle, metrics)

        draw_text(surface, vehicle_id, fonts.tiny, TEXT_MAIN, (inner.left, row_y))
        badge_rect = pygame.Rect(inner.left + 34, row_y - 2, 68, 19)
        draw_status_badge(surface, status, fonts, badge_rect, status_color, max_chars=9)
        if battery_level < 20:
            low_rect = pygame.Rect(inner.left + 106, row_y - 2, 36, 19)
            draw_status_badge(surface, "LOW", fonts, low_rect, DANGER, max_chars=5)

        bar_rect = pygame.Rect(inner.right - 98, row_y, 98, 15)
        draw_battery_bar(surface, bar_rect, battery_level, battery_text, fonts)

        load_value = vehicle.get("load", "N/A")
        load_text = f"{labels['load']}: {shorten_text(load_value, 8)}"
        draw_text(surface, load_text, fonts.tiny, TEXT_MUTED, (inner.left + 34, row_y + 17))
        shown += 1

    remaining = max(0, len(vehicles or []) - shown)
    if remaining > 0:
        draw_text(surface, f"+{remaining} more vehicles", fonts.tiny, TEXT_MUTED, (inner.left, rect.bottom - 22))


def draw_panel(surface: pygame.Surface, state: Dict, fonts: FontSet, paused: bool) -> None:
    labels = TEXT[fonts.language]
    metrics = state.get("metrics", {})
    vehicles = state.get("vehicles", [])

    pygame.draw.rect(surface, PANEL_BACKGROUND, PANEL_RECT, border_radius=10)
    pygame.draw.rect(surface, PANEL_BORDER, PANEL_RECT, width=1, border_radius=10)

    x = PANEL_RECT.left + 14
    y = PANEL_RECT.top + 12
    card_w = PANEL_RECT.width - 28
    gap = 10

    summary_rect = pygame.Rect(x, y, card_w, 114)
    draw_summary_card(surface, summary_rect, metrics, fonts, labels, paused)

    y += summary_rect.height + gap
    metrics_rect = pygame.Rect(x, y, card_w, 118)
    draw_metrics_card(surface, metrics_rect, metrics, fonts, labels)

    y += metrics_rect.height + gap
    charging_rect = pygame.Rect(x, y, card_w, 126)
    draw_charging_card(surface, charging_rect, metrics, fonts, labels)

    y += charging_rect.height + gap
    vehicles_h = max(0, PANEL_RECT.bottom - y - 10)
    vehicles_rect = pygame.Rect(x, y, card_w, vehicles_h)
    draw_vehicle_list_card(surface, vehicles_rect, vehicles, fonts, labels, metrics)

    draw_control_bar(surface, fonts)


def draw_control_bar(surface: pygame.Surface, fonts: FontSet) -> None:
    pygame.draw.rect(surface, CONTROL_BAR, CONTROL_BAR_RECT, border_radius=10)
    hints = [
        ("SPACE", "Pause"),
        ("R", "Reset"),
        ("1", "Near"),
        ("2", "Max"),
        ("3", "Hybrid"),
        ("S", "Small"),
        ("M", "Medium"),
        ("L", "Large"),
        ("X", "XL"),
        ("ESC", "Quit"),
    ]
    total_width = sum(measure_key_hint(fonts, key, label) for key, label in hints) + 12 * (len(hints) - 1)
    if total_width > CONTROL_BAR_RECT.width - 24:
        draw_centered_text(
            surface,
            "SPACE Pause | R Reset | 1/2/3 Strategy | S/M/L/X Map Scale | ESC Quit",
            fonts.tiny,
            WHITE,
            CONTROL_BAR_RECT.center,
        )
        return

    x = CONTROL_BAR_RECT.centerx - total_width // 2
    y = CONTROL_BAR_RECT.centery - 10
    for key, label in hints:
        used_width = draw_key_hint(surface, key, label, fonts, x, y)
        x += used_width + 12


def measure_key_hint(fonts: FontSet, key: str, label: str) -> int:
    key_width = fonts.tiny.size(key)[0] + 16
    label_width = fonts.tiny.size(label)[0]
    return key_width + label_width + 8


def draw_key_hint(surface: pygame.Surface, key: str, label: str, fonts: FontSet, x: int, y: int) -> int:
    key_rect = pygame.Rect(x, y, fonts.tiny.size(key)[0] + 16, 20)
    pygame.draw.rect(surface, (229, 235, 243), key_rect, border_radius=5)
    draw_centered_text(surface, key, fonts.tiny, CONTROL_BAR, key_rect.center)
    draw_text(surface, label, fonts.tiny, WHITE, (key_rect.right + 6, y + 3))
    return measure_key_hint(fonts, key, label)


def draw_paused_overlay(surface: pygame.Surface, map_rect: pygame.Rect, fonts: FontSet) -> None:
    overlay = pygame.Surface(map_rect.size, pygame.SRCALPHA)
    overlay.fill((31, 41, 55, 88))
    surface.blit(overlay, map_rect.topleft)

    pause_rect = pygame.Rect(0, 0, 180, 62)
    pause_rect.center = map_rect.center
    pygame.draw.rect(surface, (31, 41, 55), pause_rect, border_radius=12)
    pygame.draw.rect(surface, WHITE, pause_rect, width=2, border_radius=12)
    draw_centered_text(surface, "PAUSED", fonts.title, WHITE, pause_rect.center)


def draw_toast_message(
    surface: pygame.Surface,
    message: str,
    expire_time: float,
    fonts: FontSet,
    now_seconds: float | None = None,
) -> None:
    if not message:
        return

    now_seconds = pygame.time.get_ticks() / 1000.0 if now_seconds is None else now_seconds
    if now_seconds >= expire_time:
        return

    text = shorten_text(message, 44)
    text_surface = fonts.small.render(text, True, WHITE)
    toast_rect = text_surface.get_rect()
    toast_rect.inflate_ip(28, 14)
    toast_rect.center = (MAP_RECT.centerx, MAP_RECT.top + 30)

    overlay = pygame.Surface(toast_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(overlay, (31, 41, 55, 225), overlay.get_rect(), border_radius=10)
    surface.blit(overlay, toast_rect.topleft)
    surface.blit(text_surface, text_surface.get_rect(center=toast_rect.center))


def main() -> None:
    pygame.init()
    pygame.display.set_caption("New Energy Logistics Fleet Dispatch")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    fonts = choose_fonts()
    demo_world = DemoWorld()
    paused = False
    running = True
    frame_count = 0
    toast_message = ""
    toast_until = 0.0

    while running:
        dt = clock.tick(FPS) / 1000.0
        frame_count += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_1:
                    demo_world.set_strategy("nearest")
                    toast_message = "Strategy switched to nearest"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_2:
                    demo_world.set_strategy("largest")
                    toast_message = "Strategy switched to largest"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_3:
                    demo_world.set_strategy("energy_aware_hybrid")
                    toast_message = "Strategy switched to energy_aware_hybrid"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_r:
                    current_strategy = demo_world.strategy
                    demo_world.reset()
                    demo_world.set_strategy(current_strategy)

        if not paused:
            demo_world.update(dt)

        # Future change: replace this line with simulator.get_state(), or use:
        # state = load_state_from_simulator(simulator)
        state = get_demo_state(demo_world)

        screen.fill(BACKGROUND)
        draw_map(screen, state, fonts, frame_count, paused)
        draw_panel(screen, state, fonts, paused)
        draw_toast_message(screen, toast_message, toast_until, fonts)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
