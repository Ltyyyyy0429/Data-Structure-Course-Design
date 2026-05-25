"""State adapter between the Pygame UI and simulation engines.

The UI should read one stable state dictionary, no matter whether the data
comes from the current demo world or the future real simulator.
"""

from __future__ import annotations

from typing import Any, Dict


CORE_STATE_FIELDS = (
    "nodes",
    "edges",
    "vehicles",
    "tasks",
    "charging_stations",
    "metrics",
)


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

    return True


def get_demo_state(demo_world: Any) -> Dict[str, Any]:
    """Return demo data for the current standalone UI prototype."""

    state = demo_world.get_state()
    validate_state(state)
    return state


def load_state_from_simulator(simulator: Any) -> Dict[str, Any]:
    """Return real simulator data after B module provides simulator.get_state()."""

    state = simulator.get_state()
    validate_state(state)
    return state
