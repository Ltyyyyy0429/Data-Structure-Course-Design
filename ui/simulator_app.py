"""Pygame UI connected to B module Simulator.

Run from the project root:
    python3 ui/simulator_app.py

The original demo UI is still available at:
    python3 ui/pygame_app.py
"""

from __future__ import annotations

import inspect
import random
import sys
from pathlib import Path
from typing import Dict

import pygame

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulator import Simulator
from state_adapter import load_state_from_simulator
import pygame_app


FPS = 60
SIM_MINUTES_PER_REAL_SECOND = 8.0
LOW_BATTERY_DEMO = True
LOW_BATTERY_VALUE = 15.0


def build_demo_graph() -> Dict:
    """Create a small B-style graph that Simulator can read directly."""

    return {
        "nodes": [
            {"id": "depot_1", "x": 8, "y": 52, "type": "depot"},
            {"id": "task_1", "x": 24, "y": 25, "type": "task_point"},
            {"id": "task_2", "x": 25, "y": 72, "type": "task_point"},
            {"id": "cs_1", "x": 45, "y": 18, "type": "charging_station"},
            {"id": "task_3", "x": 48, "y": 43, "type": "task_point"},
            {"id": "task_4", "x": 45, "y": 78, "type": "task_point"},
            {"id": "task_5", "x": 67, "y": 31, "type": "task_point"},
            {"id": "task_6", "x": 72, "y": 60, "type": "task_point"},
            {"id": "cs_2", "x": 82, "y": 78, "type": "charging_station"},
            {"id": "task_7", "x": 91, "y": 42, "type": "task_point"},
        ],
        "edges": [
            {"from_node": "depot_1", "to_node": "task_1", "distance": 31.0},
            {"from_node": "depot_1", "to_node": "task_2", "distance": 26.0},
            {"from_node": "task_1", "to_node": "cs_1", "distance": 22.0},
            {"from_node": "task_1", "to_node": "task_3", "distance": 30.0},
            {"from_node": "task_2", "to_node": "task_4", "distance": 21.0},
            {"from_node": "task_3", "to_node": "cs_1", "distance": 25.0},
            {"from_node": "task_3", "to_node": "task_5", "distance": 23.0},
            {"from_node": "task_3", "to_node": "task_6", "distance": 29.0},
            {"from_node": "task_4", "to_node": "task_6", "distance": 32.0},
            {"from_node": "task_4", "to_node": "cs_2", "distance": 37.0},
            {"from_node": "task_5", "to_node": "task_7", "distance": 26.0},
            {"from_node": "task_6", "to_node": "task_7", "distance": 26.0},
            {"from_node": "task_6", "to_node": "cs_2", "distance": 21.0},
            {"from_node": "cs_2", "to_node": "task_7", "distance": 37.0},
        ],
    }


def create_simulator(strategy: str = "nearest") -> Simulator:
    """Create a Simulator with several initial tasks for the UI demo."""

    random.seed(2026)
    simulator = Simulator(graph_data=build_demo_graph(), scale="small", strategy=strategy)

    if hasattr(simulator, "add_test_task"):
        simulator.add_test_task("ui_t1", "task_1", 180, 0, 30)
        simulator.add_test_task("ui_t2", "task_3", 260, 0, 38)
        simulator.add_test_task("ui_t3", "task_6", 220, 0, 45)
        simulator.add_test_task("ui_t4", "task_7", 320, 3, 55)
        if hasattr(simulator, "next_task_id"):
            simulator.next_task_id = 100

    if LOW_BATTERY_DEMO:
        enable_low_battery_demo(simulator)

    return simulator


def enable_low_battery_demo(simulator: Simulator) -> None:
    """Safely lower the first vehicle battery so charging logic is easy to see."""

    vehicles = getattr(simulator, "vehicles", None)
    if not vehicles:
        print("[Simulator UI] Low battery demo skipped: simulator has no vehicles.")
        return

    first_vehicle = next(iter(vehicles.values())) if isinstance(vehicles, dict) else vehicles[0]
    if not hasattr(first_vehicle, "battery"):
        print("[Simulator UI] Low battery demo skipped: vehicle has no battery field.")
        return

    charging_stations = getattr(simulator, "charging_stations", {})
    if charging_stations and hasattr(first_vehicle, "current_node"):
        first_vehicle.current_node = next(iter(charging_stations.keys()))
        if hasattr(first_vehicle, "target_node"):
            first_vehicle.target_node = ""
        if hasattr(first_vehicle, "path"):
            first_vehicle.path = []

    first_vehicle.battery = LOW_BATTERY_VALUE
    print(
        f"[Simulator UI] Low battery demo enabled: "
        f"{getattr(first_vehicle, 'id', 'first vehicle')} battery = {LOW_BATTERY_VALUE}"
    )


def advance_simulator(simulator: Simulator, dt_minutes: float) -> bool:
    """Call the available simulator time method: update, tick, or step."""

    for method_name in ("update", "tick", "step"):
        method = getattr(simulator, method_name, None)
        if method is None:
            continue

        signature = inspect.signature(method)
        if len(signature.parameters) == 0:
            method()
        else:
            method(dt_minutes)
        return True

    return False


def reset_simulator(strategy: str) -> Simulator:
    print(f"[Simulator UI] Reset simulator with strategy: {strategy}")
    return create_simulator(strategy=strategy)


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Simulator Connected Fleet Dispatch UI")
    screen = pygame.display.set_mode((pygame_app.WINDOW_WIDTH, pygame_app.WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    fonts = pygame_app.choose_fonts()

    strategy = "nearest"
    simulator = create_simulator(strategy=strategy)
    paused = False
    running = True
    warned_no_update = False

    while running:
        dt_seconds = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    simulator = reset_simulator(strategy)
                elif event.key == pygame.K_1:
                    strategy = "nearest"
                    simulator = reset_simulator(strategy)
                elif event.key == pygame.K_2:
                    strategy = "largest"
                    simulator = reset_simulator(strategy)

        if not paused:
            dt_minutes = dt_seconds * SIM_MINUTES_PER_REAL_SECOND
            updated = advance_simulator(simulator, dt_minutes)
            if not updated and not warned_no_update:
                print("[Simulator UI] Simulator has no update/tick/step method.")
                warned_no_update = True

        state = load_state_from_simulator(simulator)

        screen.fill(pygame_app.BACKGROUND)
        pygame_app.draw_map(screen, state, fonts)
        pygame_app.draw_panel(screen, state, fonts, paused)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
