"""Pygame UI connected to B Simulator.

Run from the project root:
    python3 ui/simulator_app.py --scale large --difficulty hard --strategy energy_aware_hybrid
    python3 ui/simulator_app.py --scale large --difficulty hard --strategy energy_aware_hybrid --demo-low-battery

This keeps the original demo UI untouched:
    python3 ui/pygame_app.py
"""

from __future__ import annotations

import inspect
import random
import sys
from pathlib import Path

import pygame

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulator import Simulator
from simulator.pathfinder_adapter import RealPathfinder
from core.difficulty import get_difficulty_config
from strategy import Dispatcher

try:
    from state_adapter import load_state_from_simulator
    import pygame_app
except ImportError:
    from ui.state_adapter import load_state_from_simulator
    from ui import pygame_app


FPS = 60
SIM_MINUTES_PER_REAL_SECOND = 8.0
LOW_BATTERY_DEMO = False
LOW_BATTERY_VALUE = 15.0
UI_DIFFICULTY = "easy"
UI_SCALE = "small"
UI_STRATEGY = "nearest"
SUPPORTED_DIFFICULTIES = ("easy", "medium", "hard")
SCALE_TO_MAP_FILE = {
    "small": "data/small_map.json",
    "medium": "data/medium_map.json",
    "large": "data/large_map.json",
    "extra_large": "data/extra_large_map.json",
}
SUPPORTED_STRATEGIES = {
    "nearest",
    "largest",
    "energy_aware_hybrid",
    "genetic_algorithm",
}


def build_b_graph_from_pathfinder(pathfinder: RealPathfinder) -> dict:
    """Convert A map data to B simulator's current graph_data format."""
    nodes = []
    for node_id, node in pathfinder.graph.nodes.items():
        if node.type == "warehouse":
            node_type = "depot"
        elif node.type == "charging":
            node_type = "charging_station"
        else:
            node_type = "task_point"
        nodes.append({"id": node_id, "x": node.x, "y": node.y, "type": node_type})

    edges = []
    for edge in pathfinder.graph.edges:
        edges.append({
            "from_node": edge.from_node,
            "to_node": edge.to_node,
            "distance": edge.distance,
        })

    return {"nodes": nodes, "edges": edges}


def normalize_scale(scale: str) -> str:
    """Return a supported map scale, falling back to small if needed."""

    scale = str(scale or "small").lower()
    if scale in SCALE_TO_MAP_FILE:
        return scale
    print(f"[Simulator UI] Unknown scale '{scale}', fallback to small.")
    return "small"


def normalize_difficulty(difficulty: str) -> str:
    """Return a supported difficulty, falling back to easy if needed."""

    difficulty = str(difficulty or "easy").lower()
    if difficulty in SUPPORTED_DIFFICULTIES:
        return difficulty
    print(f"[Simulator UI] Unknown difficulty '{difficulty}', fallback to easy.")
    return "easy"


def next_difficulty(difficulty: str) -> str:
    """Cycle easy -> medium -> hard -> easy for live demonstrations."""

    difficulty = normalize_difficulty(difficulty)
    current_index = SUPPORTED_DIFFICULTIES.index(difficulty)
    return SUPPORTED_DIFFICULTIES[(current_index + 1) % len(SUPPORTED_DIFFICULTIES)]


def choose_demo_task_nodes(pathfinder: RealPathfinder, count: int = 3) -> list[int]:
    """Pick a few non-charging, non-warehouse nodes for UI demo tasks."""

    candidates = [
        node_id
        for node_id, node in sorted(pathfinder.graph.nodes.items())
        if node.type not in {"warehouse", "charging"}
    ]
    if not candidates:
        return [5, 6, 9]

    if len(candidates) <= count:
        return candidates

    indexes = [len(candidates) // 4, len(candidates) // 2, len(candidates) - 1]
    selected = []
    for index in indexes:
        node_id = candidates[index]
        if node_id not in selected:
            selected.append(node_id)
    return selected[:count]


def get_actual_vehicle_count(simulator: Simulator) -> int:
    """Read the fleet size that B's Simulator actually created."""

    vehicles = getattr(simulator, "vehicles", None)
    if vehicles is None:
        return 0
    return len(vehicles)


def print_actual_fleet_size(simulator: Simulator, scale: str, difficulty: str) -> None:
    """Print the true fleet size after Simulator initialization."""

    print(
        f"[Simulator UI] Actual fleet size: "
        f"scale={scale}, difficulty={difficulty}, vehicles={get_actual_vehicle_count(simulator)}"
    )


def add_ui_demo_tasks(simulator: Simulator, pathfinder: RealPathfinder) -> None:
    """Add a few visible tasks for the Pygame demonstration."""

    if not hasattr(simulator, "add_test_task"):
        return

    task_nodes = choose_demo_task_nodes(pathfinder)
    weights = [180, 260, 220]
    deadlines = [60, 75, 90]
    for index, node_id in enumerate(task_nodes):
        simulator.add_test_task(
            f"ui_t{index + 1}",
            node_id,
            weights[index % len(weights)],
            0,
            deadlines[index % len(deadlines)],
        )

    if hasattr(simulator, "next_task_id"):
        simulator.next_task_id = 100


def create_simulator(strategy: str = "nearest", difficulty: str = "easy", scale: str = "small") -> Simulator:
    """Create a Simulator with RealPathfinder and optional difficulty config."""
    random.seed(2026)
    scale = normalize_scale(scale)
    difficulty = normalize_difficulty(difficulty)
    strategy = normalize_strategy(strategy)
    map_file = SCALE_TO_MAP_FILE[scale]
    pathfinder = RealPathfinder(map_file)
    config = get_difficulty_config(scale, difficulty)
    graph_data = build_b_graph_from_pathfinder(pathfinder)
    simulator = Simulator(
        graph_data=graph_data,
        scale=scale,
        strategy=strategy,
        config=config,
    )
    # Keep B's converted graph/state, but use A's RealPathfinder for routing.
    simulator.pathfinder = pathfinder
    simulator._dispatcher = Dispatcher(
        pathfinder,
        strategy,
        consume_rate=simulator.energy_per_km,
        load_capacity=simulator.load_capacity,
    )

    add_ui_demo_tasks(simulator, pathfinder)

    if LOW_BATTERY_DEMO:
        enable_low_battery_demo(simulator)

    print_actual_fleet_size(simulator, scale, difficulty)
    return simulator


def enable_low_battery_demo(simulator: Simulator) -> None:
    """Safely lower the first vehicle battery so charging can be observed."""

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


def reset_simulator(strategy: str, difficulty: str = "easy", scale: str = "small") -> Simulator:
    scale = normalize_scale(scale)
    difficulty = normalize_difficulty(difficulty)
    strategy = normalize_strategy(strategy)
    print(
        f"[Simulator UI] Reset simulator with strategy: {strategy}, "
        f"difficulty: {difficulty}, scale: {scale}"
    )
    return create_simulator(strategy=strategy, difficulty=difficulty, scale=scale)


def normalize_strategy(strategy: str) -> str:
    """Return a supported strategy, falling back to nearest if needed."""

    strategy = str(strategy or "nearest")
    if strategy in SUPPORTED_STRATEGIES:
        return strategy
    print(f"[Simulator UI] Unknown strategy '{strategy}', fallback to nearest.")
    return "nearest"


def parse_cli_args(argv: list[str]) -> tuple[str, str, str, bool]:
    """Parse simple command-line options without adding dependencies."""

    scale = UI_SCALE
    difficulty = UI_DIFFICULTY
    strategy = UI_STRATEGY
    low_battery_demo = LOW_BATTERY_DEMO
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == "--scale" and index + 1 < len(argv):
            scale = normalize_scale(argv[index + 1])
            index += 2
        elif arg == "--difficulty" and index + 1 < len(argv):
            difficulty = normalize_difficulty(argv[index + 1])
            index += 2
        elif arg == "--strategy" and index + 1 < len(argv):
            strategy = normalize_strategy(argv[index + 1])
            index += 2
        elif arg == "--demo-low-battery":
            low_battery_demo = True
            index += 1
        else:
            print(f"[Simulator UI] Ignored argument: {arg}")
            index += 1
    return scale, difficulty, strategy, low_battery_demo


def main() -> None:
    pygame.init()
    pygame_app.configure_responsive_layout()
    pygame.display.set_caption("Simulator Connected Fleet Dispatch UI")
    screen = pygame.display.set_mode((pygame_app.WINDOW_WIDTH, pygame_app.WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    fonts = pygame_app.choose_fonts()

    current_scale = UI_SCALE
    current_difficulty = UI_DIFFICULTY
    strategy = UI_STRATEGY
    simulator = create_simulator(strategy=strategy, difficulty=current_difficulty, scale=current_scale)
    paused = False
    running = True
    warned_no_update = False
    frame_count = 0
    toast_message = ""
    toast_until = 0.0

    while running:
        dt_seconds = clock.tick(FPS) / 1000.0
        frame_count += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    simulator = reset_simulator(strategy, current_difficulty, current_scale)
                    toast_message = f"Reset {current_scale} / {strategy}"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_1:
                    strategy = "nearest"
                    simulator = reset_simulator(strategy, current_difficulty, current_scale)
                    toast_message = "Reset with strategy: nearest"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_2:
                    strategy = "largest"
                    simulator = reset_simulator(strategy, current_difficulty, current_scale)
                    toast_message = "Reset with strategy: largest"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_3:
                    strategy = "energy_aware_hybrid"
                    try:
                        simulator = reset_simulator(strategy, current_difficulty, current_scale)
                        toast_message = "Reset with strategy: energy_aware_hybrid"
                    except Exception:
                        strategy = "nearest"
                        simulator = reset_simulator(strategy, current_difficulty, current_scale)
                        toast_message = "Hybrid strategy is not available"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_4:
                    strategy = "genetic_algorithm"
                    try:
                        simulator = reset_simulator(strategy, current_difficulty, current_scale)
                        toast_message = "Reset with strategy: genetic_algorithm"
                    except Exception:
                        strategy = "nearest"
                        simulator = reset_simulator(strategy, current_difficulty, current_scale)
                        toast_message = "GA strategy is not available"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key == pygame.K_d:
                    current_difficulty = next_difficulty(current_difficulty)
                    simulator = reset_simulator(strategy, current_difficulty, current_scale)
                    toast_message = f"Reset with difficulty: {current_difficulty}"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8
                elif event.key in (pygame.K_s, pygame.K_m, pygame.K_l, pygame.K_x):
                    key_to_scale = {
                        pygame.K_s: "small",
                        pygame.K_m: "medium",
                        pygame.K_l: "large",
                        pygame.K_x: "extra_large",
                    }
                    current_scale = key_to_scale[event.key]
                    simulator = reset_simulator(strategy, current_difficulty, current_scale)
                    toast_message = f"Reset with scale: {current_scale}"
                    toast_until = pygame.time.get_ticks() / 1000.0 + 1.8

        if not paused:
            dt_minutes = dt_seconds * SIM_MINUTES_PER_REAL_SECOND
            updated = advance_simulator(simulator, dt_minutes)
            if not updated and not warned_no_update:
                print("[Simulator UI] Simulator has no update/tick/step method.")
                warned_no_update = True

        state = load_state_from_simulator(simulator)
        state.setdefault("metrics", {})
        state["metrics"]["difficulty"] = current_difficulty
        state["metrics"]["vehicle_count"] = get_actual_vehicle_count(simulator)

        screen.fill(pygame_app.BACKGROUND)
        pygame_app.draw_map(screen, state, fonts, frame_count, paused)
        pygame_app.draw_panel(screen, state, fonts, paused)
        pygame_app.draw_toast_message(screen, toast_message, toast_until, fonts)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    UI_SCALE, UI_DIFFICULTY, UI_STRATEGY, LOW_BATTERY_DEMO = parse_cli_args(sys.argv)
    main()
