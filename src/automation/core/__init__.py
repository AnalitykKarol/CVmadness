# src/automation/core/__init__.py
"""
Core automation module - główne komponenty systemu automatyzacji
"""

# Data structures
from .data_structures import (
    # Enums
    ActionType,
    Priority,
    ClassType,
    CombatState,
    ResourceType,

    # Core data classes
    GameState,
    Resources,
    Target,
    Position,
    Buff,
    ActionResult,
    Cooldown,
    ActionDefinition,

    # Utility functions
    create_game_state_snapshot,
    merge_game_states,
    calculate_state_diff
)

# Game state monitoring
from .game_state_monitor import (
    GameStateMonitor,
    MonitoringRegions,
    StateChangeCallback
)

# Version info
__version__ = "1.0.0"
__author__ = "WoW Automation Team"

# Core components (will be imported when other files are created)
__all__ = [
    # Enums
    "ActionType",
    "Priority",
    "ClassType",
    "CombatState",
    "ResourceType",

    # Data structures
    "GameState",
    "Resources",
    "Target",
    "Position",
    "Buff",
    "ActionResult",
    "Cooldown",
    "ActionDefinition",

    # Monitoring
    "GameStateMonitor",
    "MonitoringRegions",
    "StateChangeCallback",

    # Utilities
    "create_game_state_snapshot",
    "merge_game_states",
    "calculate_state_diff"
]

# Core module info
CORE_INFO = {
    "version": __version__,
    "components": [
        "data_structures",
        "game_state_monitor",
        "decision_maker",  # Coming next
        "action_executor",  # Coming next
        "automation_engine",  # Coming next
        "safety_manager"  # Coming next
    ],
    "status": "In Development"
}


def get_core_info():
    """Pobierz informacje o module core"""
    return CORE_INFO.copy()