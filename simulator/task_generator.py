"""Difficulty-aware task generator supporting burst patterns and tight deadlines."""

import random
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.difficulty import TaskConfig


class TaskGenerator:
    """Generates new tasks according to difficulty-driven configuration.

    Supports:
    - Configurable spawn probability per interval
    - Burst mode: multiple tasks spawned at once with spatial clustering
    - Variable weight and deadline ranges
    """

    def __init__(self, task_points: List[int], config: Optional["TaskConfig"] = None):
        self.task_points = list(task_points)
        self.config = config
        self._rng = random.Random()

    def generate_tasks(self, current_time: float) -> List[dict]:
        """Return a list of new task dicts for the current simulation tick.

        Returns an empty list when no tasks are spawned this interval.
        """
        if not self.task_points:
            return []

        if self.config is None:
            return self._fallback_generate(current_time)

        cfg = self.config
        tasks: List[dict] = []

        # --- Burst check first ---
        if cfg.burst_probability > 0 and self._rng.random() < cfg.burst_probability:
            burst_count = self._rng.randint(cfg.burst_count_min, cfg.burst_count_max)
            # Spatial clustering: burst tasks land on nodes close to a random anchor
            anchor = self._rng.choice(self.task_points)
            nearby = sorted(self.task_points, key=lambda n: abs(n - anchor))
            chosen = nearby[: min(burst_count, len(nearby))]
            for node_id in chosen:
                tasks.append(self._make_task(current_time, node_id, cfg))
            return tasks

        # --- Normal spawn ---
        if self._rng.random() < cfg.spawn_probability:
            node_id = self._rng.choice(self.task_points)
            tasks.append(self._make_task(current_time, node_id, cfg))

        return tasks

    def reset(self, seed: int = None) -> None:
        """Reset internal RNG state."""
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_task(self, current_time: float, node_id: int, cfg: "TaskConfig") -> dict:
        weight = round(
            self._rng.uniform(cfg.weight_min_kg, cfg.weight_max_kg), 1
        )
        deadline = current_time + self._rng.uniform(
            cfg.deadline_min, cfg.deadline_max
        )
        return {
            "node_id": node_id,
            "weight": weight,
            "release_time": current_time,
            "deadline": round(deadline, 1),
        }

    def _fallback_generate(self, current_time: float) -> List[dict]:
        """Legacy behaviour: 30 % chance, weight 50-500, deadline +60-120 min."""
        if self._rng.random() < 0.3 and self.task_points:
            node_id = self._rng.choice(self.task_points)
            return [{
                "node_id": node_id,
                "weight": float(self._rng.randint(50, 500)),
                "release_time": current_time,
                "deadline": current_time + self._rng.randint(60, 120),
            }]
        return []
