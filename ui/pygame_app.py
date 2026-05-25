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
        CHARGING,
        DANGER,
        GRID_LINE,
        MAP_BACKGROUND,
        NORMAL_NODE,
        PANEL_BACKGROUND,
        PANEL_BORDER,
        ROAD,
        SUCCESS,
        TASK,
        TEXT_MAIN,
        TEXT_MUTED,
        VEHICLE,
        WAREHOUSE,
        WARNING,
        WHITE,
    )
except ImportError:
    from ui.colors import (
        BACKGROUND,
        BLACK,
        CHARGING,
        DANGER,
        GRID_LINE,
        MAP_BACKGROUND,
        NORMAL_NODE,
        PANEL_BACKGROUND,
        PANEL_BORDER,
        ROAD,
        SUCCESS,
        TASK,
        TEXT_MAIN,
        TEXT_MUTED,
        VEHICLE,
        WAREHOUSE,
        WARNING,
        WHITE,
    )


WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700
MAP_RECT = pygame.Rect(24, 24, 730, 652)
PANEL_RECT = pygame.Rect(778, 24, 298, 652)
WORLD_WIDTH = 100
WORLD_HEIGHT = 100
FPS = 60


TEXT = {
    "zh": {
        "title": "新能源物流车队调度仿真",
        "time": "当前时间",
        "scale": "当前规模",
        "strategy": "当前策略",
        "score": "总收益",
        "completed": "完成任务",
        "timeout": "超时任务",
        "distance": "总路径长度",
        "charges": "充电次数",
        "vehicles": "车辆状态",
        "battery": "电量",
        "status": "状态",
        "paused": "已暂停",
        "running": "运行中",
        "help1": "SPACE 暂停/继续",
        "help2": "1 nearest  2 largest",
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
        "timeout": "Timeout tasks",
        "distance": "Total distance",
        "charges": "Charging times",
        "vehicles": "Vehicles",
        "battery": "Battery",
        "status": "Status",
        "paused": "Paused",
        "running": "Running",
        "help1": "SPACE pause/resume",
        "help2": "1 nearest  2 largest",
        "help3": "R reset  ESC quit",
        "queue": "Queue",
    },
}

STATUS_TEXT = {
    "zh": {
        "idle": "空闲",
        "delivering": "配送中",
        "charging": "充电中",
        "returning": "返仓中",
    },
    "en": {
        "idle": "idle",
        "delivering": "delivering",
        "charging": "charging",
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
        if strategy in {"nearest", "largest"}:
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
        strategy_bonus = 25 if self.strategy == "largest" else 0
        distance_factor = 13.5 if self.strategy == "nearest" else 15.0

        metrics = {
            "current_time": int(self.current_time),
            "scale": "small",
            "strategy": self.strategy,
            "total_score": completed_tasks * 120 - timeout_tasks * 80 + strategy_bonus,
            "completed_tasks": completed_tasks,
            "timeout_tasks": timeout_tasks,
            "total_distance": round(self.current_time * distance_factor, 1),
            "charging_times": int(self.current_time // 24),
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

        return {
            "id": vehicle_id,
            "x": x,
            "y": y,
            "battery": battery,
            "status": status,
            "target_node": end_node["id"],
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


def draw_map(surface: pygame.Surface, state: Dict, fonts: FontSet) -> None:
    pygame.draw.rect(surface, MAP_BACKGROUND, MAP_RECT, border_radius=8)
    pygame.draw.rect(surface, PANEL_BORDER, MAP_RECT, width=1, border_radius=8)
    draw_grid(surface)

    node_by_id = {node["id"]: node for node in state["nodes"]}

    for edge in state["edges"]:
        start_node = node_by_id[edge["from"]]
        end_node = node_by_id[edge["to"]]
        start_pos = world_to_screen(start_node["x"], start_node["y"])
        end_pos = world_to_screen(end_node["x"], end_node["y"])
        pygame.draw.line(surface, ROAD, start_pos, end_pos, width=3)

    for node in state["nodes"]:
        if node["type"] == "normal":
            pygame.draw.circle(surface, NORMAL_NODE, world_to_screen(node["x"], node["y"]), 5)

    for node in state["nodes"]:
        if node["type"] == "warehouse":
            draw_warehouse(surface, node, fonts)

    for station in state["charging_stations"]:
        draw_charging_station(surface, station, fonts)

    for task in state["tasks"]:
        draw_task(surface, task, fonts)

    for vehicle in state["vehicles"]:
        draw_vehicle(surface, vehicle, fonts)


def draw_grid(surface: pygame.Surface) -> None:
    for i in range(1, 5):
        x = MAP_RECT.left + MAP_RECT.width * i // 5
        y = MAP_RECT.top + MAP_RECT.height * i // 5
        pygame.draw.line(surface, GRID_LINE, (x, MAP_RECT.top), (x, MAP_RECT.bottom), width=1)
        pygame.draw.line(surface, GRID_LINE, (MAP_RECT.left, y), (MAP_RECT.right, y), width=1)


def draw_warehouse(surface: pygame.Surface, node: Dict, fonts: FontSet) -> None:
    center = world_to_screen(node["x"], node["y"])
    rect = pygame.Rect(0, 0, 28, 28)
    rect.center = center
    pygame.draw.rect(surface, WAREHOUSE, rect, border_radius=4)
    draw_centered_text(surface, "W", fonts.small, WHITE, center)


def draw_charging_station(surface: pygame.Surface, station: Dict, fonts: FontSet) -> None:
    center = world_to_screen(station["x"], station["y"])
    pygame.draw.circle(surface, CHARGING, center, 13)
    draw_centered_text(surface, "C", fonts.small, WHITE, center)
    label = f"{TEXT[fonts.language]['queue']}: {station['queue']}"
    draw_text(surface, label, fonts.tiny, TEXT_MAIN, (center[0] - 24, center[1] + 15))


def draw_task(surface: pygame.Surface, task: Dict, fonts: FontSet) -> None:
    center = world_to_screen(task["x"], task["y"])
    pygame.draw.circle(surface, TASK, center, 11)
    draw_centered_text(surface, "T", fonts.small, BLACK, center)
    draw_text(surface, f"{task['weight']}kg", fonts.tiny, TEXT_MAIN, (center[0] + 12, center[1] - 8))


def draw_vehicle(surface: pygame.Surface, vehicle: Dict, fonts: FontSet) -> None:
    center = world_to_screen(vehicle["x"], vehicle["y"])
    pygame.draw.circle(surface, VEHICLE, center, 12)
    pygame.draw.circle(surface, WHITE, center, 12, width=2)
    draw_centered_text(surface, vehicle["id"], fonts.tiny, WHITE, center)


def draw_panel(surface: pygame.Surface, state: Dict, fonts: FontSet, paused: bool) -> None:
    labels = TEXT[fonts.language]
    metrics = state["metrics"]

    pygame.draw.rect(surface, PANEL_BACKGROUND, PANEL_RECT, border_radius=8)
    pygame.draw.rect(surface, PANEL_BORDER, PANEL_RECT, width=1, border_radius=8)

    x = PANEL_RECT.left + 18
    y = PANEL_RECT.top + 20
    draw_text(surface, labels["title"], fonts.title, TEXT_MAIN, (x, y))
    y += 42

    run_label = labels["paused"] if paused else labels["running"]
    run_color = WARNING if paused else SUCCESS
    draw_text(surface, run_label, fonts.normal, run_color, (x, y))
    y += 36

    rows = [
        (labels["time"], f"{metrics['current_time']} s"),
        (labels["scale"], metrics["scale"]),
        (labels["strategy"], metrics["strategy"]),
        (labels["score"], str(metrics["total_score"])),
        (labels["completed"], str(metrics["completed_tasks"])),
        (labels["timeout"], str(metrics["timeout_tasks"])),
        (labels["distance"], f"{metrics['total_distance']} km"),
        (labels["charges"], str(metrics["charging_times"])),
    ]

    for label, value in rows:
        draw_text(surface, f"{label}:", fonts.small, TEXT_MUTED, (x, y))
        draw_text(surface, value, fonts.small, TEXT_MAIN, (x + 122, y))
        y += 28

    y += 14
    pygame.draw.line(surface, PANEL_BORDER, (x, y), (PANEL_RECT.right - 18, y), width=1)
    y += 18
    draw_text(surface, labels["vehicles"], fonts.normal, TEXT_MAIN, (x, y))
    y += 34

    for vehicle in state["vehicles"]:
        status = STATUS_TEXT[fonts.language][vehicle["status"]]
        battery = vehicle["battery"]
        battery_color = SUCCESS if battery >= 55 else WARNING if battery >= 30 else DANGER

        draw_text(surface, vehicle["id"], fonts.small, TEXT_MAIN, (x, y))
        draw_text(
            surface,
            f"{labels['battery']}: {battery}%",
            fonts.small,
            battery_color,
            (x + 54, y),
        )
        y += 23
        draw_text(surface, f"{labels['status']}: {status}", fonts.small, TEXT_MUTED, (x + 54, y))
        y += 32

    y = PANEL_RECT.bottom - 82
    draw_text(surface, labels["help1"], fonts.tiny, TEXT_MUTED, (x, y))
    draw_text(surface, labels["help2"], fonts.tiny, TEXT_MUTED, (x, y + 22))
    draw_text(surface, labels["help3"], fonts.tiny, TEXT_MUTED, (x, y + 44))


def main() -> None:
    pygame.init()
    pygame.display.set_caption("New Energy Logistics Fleet Dispatch")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    fonts = choose_fonts()
    demo_world = DemoWorld()
    paused = False
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0

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
                elif event.key == pygame.K_2:
                    demo_world.set_strategy("largest")
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
        draw_map(screen, state, fonts)
        draw_panel(screen, state, fonts, paused)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
