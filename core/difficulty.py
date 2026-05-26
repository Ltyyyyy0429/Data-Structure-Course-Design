"""Difficulty presets for the new-energy logistics fleet simulation.

Provides EASY / MEDIUM / HARD presets controlling map topology,
vehicle parameters, task generation, and charging infrastructure.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional


class DifficultyPreset(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MapConfig:
    """Map generation parameters for a specific scale."""

    node_count: int
    charging_count: int
    extra_neighbors: int
    seed: int
    # Topology
    cluster_mode: str = "grid"          # "grid" | "cluster" | "sparse"
    bottleneck_fraction: float = 0.0    # fraction of extra edges to drop (0.0-0.3)
    one_way_fraction: float = 0.0       # fraction of extra edges to make one-way (0.0-0.15)
    charging_distribution: str = "uniform"  # "uniform" | "clustered" | "scarce"
    jitter_range: float = 2.5           # coordinate jitter amplitude


@dataclass
class VehicleConfig:
    """Vehicle parameters."""

    count_small: int = 3
    count_medium: int = 3
    count_large: int = 3
    count_extra_large: int = 3
    battery_capacity_kwh: float = 500.0
    energy_per_km: float = 0.3
    speed_kmh: float = 40.0
    load_capacity_kg: float = 1000.0
    low_battery_threshold_kwh: float = 80.0

    def count_for_scale(self, scale: str) -> int:
        return {
            "small": self.count_small,
            "medium": self.count_medium,
            "large": self.count_large,
            "extra_large": self.count_extra_large,
        }.get(scale, 3)


@dataclass
class TaskConfig:
    """Task generation parameters."""

    spawn_probability: float = 0.3
    spawn_interval_minutes: float = 5.0
    deadline_min: float = 60.0          # minutes
    deadline_max: float = 120.0
    weight_min_kg: float = 50.0
    weight_max_kg: float = 500.0
    burst_probability: float = 0.0      # chance of spawning a burst each interval
    burst_count_min: int = 2
    burst_count_max: int = 4


@dataclass
class ChargingConfig:
    """Charging infrastructure parameters."""

    charging_rate_kwh_per_hour: float = 100.0
    ports_per_station: int = 2


@dataclass
class DifficultyConfig:
    """Top-level difficulty preset aggregating all sub-configs."""

    map: MapConfig
    vehicle: VehicleConfig
    task: TaskConfig
    charging: ChargingConfig


# ---------------------------------------------------------------------------
# Map scale definitions (shared across difficulties)
# ---------------------------------------------------------------------------

_SCALE_MAP_PARAMS = {
    "small":       dict(node_count=10, charging_count=2, extra_neighbors=2, seed=202601),
    "medium":      dict(node_count=30, charging_count=4, extra_neighbors=3, seed=202602),
    "large":       dict(node_count=60, charging_count=6, extra_neighbors=3, seed=202603),
    "extra_large": dict(node_count=80, charging_count=8, extra_neighbors=4, seed=202604),
}


def _map_config_for(scale: str, difficulty: DifficultyPreset) -> MapConfig:
    """Build a MapConfig for *scale* under *difficulty*."""
    base = _SCALE_MAP_PARAMS.get(scale, _SCALE_MAP_PARAMS["small"]).copy()

    if difficulty == DifficultyPreset.EASY:
        return MapConfig(
            **base,
            cluster_mode="grid",
            bottleneck_fraction=0.0,
            one_way_fraction=0.0,
            charging_distribution="uniform",
            jitter_range=2.5,
        )

    if difficulty == DifficultyPreset.MEDIUM:
        return MapConfig(
            **base,
            cluster_mode="grid",
            bottleneck_fraction=0.10,
            one_way_fraction=0.05,
            charging_distribution="uniform",
            jitter_range=4.0,
        )

    # HARD
    return MapConfig(
        **base,
        cluster_mode="cluster",
        bottleneck_fraction=0.20,
        one_way_fraction=0.10,
        charging_distribution="clustered",
        jitter_range=8.0,
    )


def _vehicle_config_for(difficulty: DifficultyPreset) -> VehicleConfig:
    if difficulty == DifficultyPreset.EASY:
        return VehicleConfig()
    if difficulty == DifficultyPreset.MEDIUM:
        return VehicleConfig(
            battery_capacity_kwh=300.0,
            energy_per_km=0.5,
            low_battery_threshold_kwh=60.0,
            count_small=3, count_medium=3, count_large=3, count_extra_large=3,
        )
    # HARD
    return VehicleConfig(
        count_small=2, count_medium=3, count_large=4, count_extra_large=5,
        battery_capacity_kwh=200.0,
        energy_per_km=0.7,
        low_battery_threshold_kwh=45.0,
    )


def _task_config_for(difficulty: DifficultyPreset) -> TaskConfig:
    if difficulty == DifficultyPreset.EASY:
        return TaskConfig()
    if difficulty == DifficultyPreset.MEDIUM:
        return TaskConfig(
            spawn_probability=0.50,
            deadline_min=45.0,
            deadline_max=90.0,
            weight_min_kg=80.0,
            burst_probability=0.10,
        )
    # HARD
    return TaskConfig(
        spawn_probability=0.70,
        deadline_min=25.0,
        deadline_max=60.0,
        weight_min_kg=100.0,
        burst_probability=0.20,
        burst_count_min=2,
        burst_count_max=4,
    )


def _charging_config_for(difficulty: DifficultyPreset) -> ChargingConfig:
    if difficulty == DifficultyPreset.EASY:
        return ChargingConfig()
    if difficulty == DifficultyPreset.MEDIUM:
        return ChargingConfig(charging_rate_kwh_per_hour=75.0, ports_per_station=2)
    # HARD
    return ChargingConfig(charging_rate_kwh_per_hour=50.0, ports_per_station=1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_difficulty_config(scale: str, difficulty: str = "easy") -> DifficultyConfig:
    """Return a fully-resolved DifficultyConfig for the given scale and difficulty.

    Args:
        scale: one of ``"small"``, ``"medium"``, ``"large"``, ``"extra_large"``.
        difficulty: ``"easy"``, ``"medium"``, or ``"hard"`` (case-insensitive).

    Returns:
        DifficultyConfig with all sub-configs resolved.
    """
    try:
        preset = DifficultyPreset(difficulty.lower())
    except ValueError:
        raise ValueError(
            f"Unknown difficulty '{difficulty}'. "
            f"Choose from: {[d.value for d in DifficultyPreset]}"
        )

    if scale not in _SCALE_MAP_PARAMS:
        raise ValueError(
            f"Unknown scale '{scale}'. "
            f"Choose from: {list(_SCALE_MAP_PARAMS)}"
        )

    return DifficultyConfig(
        map=_map_config_for(scale, preset),
        vehicle=_vehicle_config_for(preset),
        task=_task_config_for(preset),
        charging=_charging_config_for(preset),
    )
