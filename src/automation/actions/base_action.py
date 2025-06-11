# src/automation/actions/base_action.py
"""
Klasa bazowa dla wszystkich akcji w grze
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from ..core.data_structures import (
    GameState, ActionResult, ActionDefinition, ActionType,
    Priority, ClassType, CombatState
)


# ===============================
# ACTION VALIDATION
# ===============================

class ValidationResult:
    """Rezultat walidacji akcji"""

    def __init__(self, is_valid: bool, reason: str = "", details: Optional[Dict] = None):
        self.is_valid = is_valid
        self.reason = reason
        self.details = details or {}

    def __bool__(self) -> bool:
        return self.is_valid


@dataclass
class ActionRequirements:
    """Wymagania dla akcji"""
    # Basic requirements
    min_level: int = 1
    required_class: Optional[ClassType] = None

    # Resource requirements
    mana_cost: float = 0.0
    rage_cost: float = 0.0
    energy_cost: float = 0.0
    health_threshold: Optional[float] = None  # Minimum HP% to use

    # State requirements
    requires_target: bool = False
    requires_combat: bool = False
    requires_out_of_combat: bool = False
    forbidden_in_combat: bool = False

    # Positioning requirements
    max_range: float = 0.0  # 0 = melee range
    min_range: float = 0.0
    requires_line_of_sight: bool = False

    # Buff/debuff requirements
    required_buffs: List[str] = None
    forbidden_buffs: List[str] = None
    required_target_debuffs: List[str] = None

    # Cooldown and timing
    global_cooldown: bool = True
    can_use_while_moving: bool = True
    can_use_while_casting: bool = False

    def __post_init__(self):
        if self.required_buffs is None:
            self.required_buffs = []
        if self.forbidden_buffs is None:
            self.forbidden_buffs = []
        if self.required_target_debuffs is None:
            self.required_target_debuffs = []


# ===============================
# BASE ACTION CLASS
# ===============================

class BaseAction(ABC):
    """
    Klasa bazowa dla wszystkich akcji w grze
    """

    def __init__(self, name: str, action_type: ActionType, priority: Priority,
                 requirements: Optional[ActionRequirements] = None):
        # Basic properties
        self.name = name
        self.action_type = action_type
        self.priority = priority
        self.requirements = requirements or ActionRequirements()

        # State tracking
        self.enabled = True
        self.last_used = 0.0
        self.cooldown_duration = 0.0

        # Statistics
        self.usage_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_damage = 0.0
        self.total_healing = 0.0

        # Performance tracking
        self.average_execution_time = 0.0
        self.min_execution_time = float('inf')
        self.max_execution_time = 0.0

        # Metadata
        self.description = ""
        self.tooltip = ""
        self.icon_path = ""

        logging.debug(f"Initialized action: {name} ({action_type.value})")

    # ===============================
    # ABSTRACT METHODS
    # ===============================

    @abstractmethod
    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """
        Wewnętrzna implementacja wykonania akcji
        Musi być zaimplementowana przez klasy dziedziczące
        """
        pass

    @abstractmethod
    def get_cooldown_duration(self) -> float:
        """
        Pobierz czas cooldown akcji
        """
        pass

    @abstractmethod
    def estimate_effectiveness(self, game_state: GameState) -> float:
        """
        Oszacuj efektywność akcji w danym stanie gry (0.0 - 1.0)
        Używane przez decision maker do wyboru najlepszej akcji
        """
        pass

    # ===============================
    # VALIDATION METHODS
    # ===============================

    def can_execute(self, game_state: GameState, character_class: ClassType) -> ValidationResult:
        """
        Sprawdź czy akcja może być wykonana
        """
        # Check if action is enabled
        if not self.enabled:
            return ValidationResult(False, "Action is disabled")

        # Check cooldown
        if self.is_on_cooldown():
            remaining = self.get_cooldown_remaining()
            return ValidationResult(False, f"On cooldown for {remaining:.1f}s")

        # Check class requirements
        if (self.requirements.required_class and
                self.requirements.required_class != character_class):
            return ValidationResult(False, f"Requires class: {self.requirements.required_class.value}")

        # Check basic state requirements
        state_validation = self._validate_game_state(game_state)
        if not state_validation:
            return state_validation

        # Check resource requirements
        resource_validation = self._validate_resources(game_state)
        if not resource_validation:
            return resource_validation

        # Check target requirements
        target_validation = self._validate_target(game_state)
        if not target_validation:
            return target_validation

        # Check buff/debuff requirements
        buff_validation = self._validate_buffs_debuffs(game_state)
        if not buff_validation:
            return buff_validation

        # Check position and range
        position_validation = self._validate_position(game_state)
        if not position_validation:
            return position_validation

        return ValidationResult(True, "All requirements met")

    def _validate_game_state(self, game_state: GameState) -> ValidationResult:
        """Waliduj stan gry"""
        # Check if in game
        if not game_state.is_in_game:
            return ValidationResult(False, "Not in game")

        # Check if safe to act
        if not game_state.is_safe_to_act():
            return ValidationResult(False, "Not safe to act")

        # Check combat requirements
        if self.requirements.requires_combat and not game_state.in_combat:
            return ValidationResult(False, "Requires combat")

        if self.requirements.requires_out_of_combat and game_state.in_combat:
            return ValidationResult(False, "Requires out of combat")

        if self.requirements.forbidden_in_combat and game_state.in_combat:
            return ValidationResult(False, "Cannot be used in combat")

        # Check casting state
        if game_state.is_casting and not self.requirements.can_use_while_casting:
            return ValidationResult(False, "Cannot use while casting")

        # Check movement
        if game_state.is_moving and not self.requirements.can_use_while_moving:
            return ValidationResult(False, "Cannot use while moving")

        # Check health threshold
        if (self.requirements.health_threshold and
                game_state.resources.health_percent < self.requirements.health_threshold):
            return ValidationResult(False, f"Health too low (need {self.requirements.health_threshold}%)")

        return ValidationResult(True)

    def _validate_resources(self, game_state: GameState) -> ValidationResult:
        """Waliduj zasoby"""
        resources = game_state.resources

        # Check mana
        if (self.requirements.mana_cost > 0 and
                resources.mana_current < self.requirements.mana_cost):
            return ValidationResult(False, f"Not enough mana ({resources.mana_current}/{self.requirements.mana_cost})")

        # Check rage
        if (self.requirements.rage_cost > 0 and
                resources.rage_current < self.requirements.rage_cost):
            return ValidationResult(False, f"Not enough rage ({resources.rage_current}/{self.requirements.rage_cost})")

        # Check energy
        if (self.requirements.energy_cost > 0 and
                resources.energy_current < self.requirements.energy_cost):
            return ValidationResult(False,
                                    f"Not enough energy ({resources.energy_current}/{self.requirements.energy_cost})")

        return ValidationResult(True)

    def _validate_target(self, game_state: GameState) -> ValidationResult:
        """Waliduj target"""
        target = game_state.target

        # Check if target required
        if self.requirements.requires_target and not target.exists:
            return ValidationResult(False, "Requires target")

        # If we have a target, validate it
        if target.exists:
            # Check range
            if self.requirements.max_range > 0 and target.distance > self.requirements.max_range:
                return ValidationResult(False,
                                        f"Target too far ({target.distance:.1f}m > {self.requirements.max_range}m)")

            if self.requirements.min_range > 0 and target.distance < self.requirements.min_range:
                return ValidationResult(False,
                                        f"Target too close ({target.distance:.1f}m < {self.requirements.min_range}m)")

            # Check if target is hostile (for offensive actions)
            if self.action_type == ActionType.COMBAT and not target.is_hostile:
                return ValidationResult(False, "Target is not hostile")

            # Check target debuffs
            if self.requirements.required_target_debuffs:
                # This would require debuff detection from target
                # Placeholder implementation
                pass

        return ValidationResult(True)

    def _validate_buffs_debuffs(self, game_state: GameState) -> ValidationResult:
        """Waliduj buffy i debuffy"""
        # Check required buffs
        for required_buff in self.requirements.required_buffs:
            if not game_state.has_buff(required_buff):
                return ValidationResult(False, f"Missing required buff: {required_buff}")

        # Check forbidden buffs
        for forbidden_buff in self.requirements.forbidden_buffs:
            if game_state.has_buff(forbidden_buff):
                return ValidationResult(False, f"Cannot use with buff: {forbidden_buff}")

        return ValidationResult(True)

    def _validate_position(self, game_state: GameState) -> ValidationResult:
        """Waliduj pozycję"""
        # Line of sight check would require advanced vision system
        # Placeholder for now
        if self.requirements.requires_line_of_sight:
            # This would check if there are obstacles between player and target
            pass

        return ValidationResult(True)

    # ===============================
    # EXECUTION METHODS
    # ===============================

    def execute(self, game_state: GameState, character_class: ClassType, **kwargs) -> ActionResult:
        """
        Główna metoda wykonania akcji
        """
        start_time = time.time()

        # Pre-execution validation
        validation = self.can_execute(game_state, character_class)
        if not validation:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                error_message=validation.reason
            )

        try:
            # Execute the action
            result = self.execute_internal(game_state, **kwargs)

            # Post-execution processing
            self._post_execution_processing(result)

            return result

        except Exception as e:
            error_result = ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=f"Execution error: {str(e)}"
            )

            self._record_failure(error_result)
            logging.error(f"Action '{self.name}' failed: {e}")

            return error_result

    def _post_execution_processing(self, result: ActionResult):
        """Przetwarzanie po wykonaniu akcji"""
        # Update usage statistics
        self.usage_count += 1
        self.last_used = result.timestamp

        if result.success:
            self.success_count += 1
            self.total_damage += result.damage_dealt
            self.total_healing += result.healing_done

            # Set cooldown
            if self.get_cooldown_duration() > 0:
                self.cooldown_duration = self.get_cooldown_duration()
        else:
            self.failure_count += 1

        # Update execution time statistics
        if result.execution_time > 0:
            # Update average (moving average)
            alpha = 0.2
            if self.average_execution_time == 0:
                self.average_execution_time = result.execution_time
            else:
                self.average_execution_time = (
                        alpha * result.execution_time +
                        (1 - alpha) * self.average_execution_time
                )

            # Update min/max
            self.min_execution_time = min(self.min_execution_time, result.execution_time)
            self.max_execution_time = max(self.max_execution_time, result.execution_time)

    def _record_failure(self, result: ActionResult):
        """Zapisz niepowodzenie akcji"""
        self.usage_count += 1
        self.failure_count += 1

    # ===============================
    # COOLDOWN MANAGEMENT
    # ===============================

    def is_on_cooldown(self) -> bool:
        """Sprawdź czy akcja jest na cooldown"""
        if self.cooldown_duration <= 0:
            return False

        elapsed = time.time() - self.last_used
        return elapsed < self.cooldown_duration

    def get_cooldown_remaining(self) -> float:
        """Pobierz pozostały czas cooldown"""
        if self.cooldown_duration <= 0:
            return 0.0

        elapsed = time.time() - self.last_used
        remaining = self.cooldown_duration - elapsed
        return max(0.0, remaining)

    def get_cooldown_progress(self) -> float:
        """Pobierz postęp cooldown (0.0 - 1.0)"""
        if self.cooldown_duration <= 0:
            return 1.0

        elapsed = time.time() - self.last_used
        progress = elapsed / self.cooldown_duration
        return min(1.0, max(0.0, progress))

    def reset_cooldown(self):
        """Zresetuj cooldown (dla testów/emergencies)"""
        self.last_used = 0.0
        self.cooldown_duration = 0.0
        logging.debug(f"Reset cooldown for action: {self.name}")

    # ===============================
    # STATISTICS & ANALYSIS
    # ===============================

    def get_success_rate(self) -> float:
        """Pobierz współczynnik sukcesu (%))"""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100.0) if total > 0 else 0.0

    def get_damage_per_use(self) -> float:
        """Pobierz średnie damage na użycie"""
        return self.total_damage / max(1, self.success_count)

    def get_healing_per_use(self) -> float:
        """Pobierz średnie healing na użycie"""
        return self.total_healing / max(1, self.success_count)

    def get_effectiveness_rating(self) -> float:
        """Pobierz ocenę efektywności (0.0 - 1.0)"""
        # Combines success rate, damage/healing output, and execution time
        success_factor = self.get_success_rate() / 100.0

        # Damage/healing factor (normalized)
        output_factor = min(1.0, (self.get_damage_per_use() + self.get_healing_per_use()) / 1000.0)

        # Execution time factor (faster is better)
        time_factor = 1.0 / max(0.1, self.average_execution_time) if self.average_execution_time > 0 else 1.0
        time_factor = min(1.0, time_factor)

        # Combined rating
        return (success_factor * 0.4 + output_factor * 0.4 + time_factor * 0.2)

    def get_statistics(self) -> Dict[str, Any]:
        """Pobierz pełne statystyki akcji"""
        return {
            "name": self.name,
            "type": self.action_type.value,
            "priority": self.priority.value,
            "enabled": self.enabled,

            # Usage stats
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.get_success_rate(),

            # Performance stats
            "total_damage": self.total_damage,
            "total_healing": self.total_healing,
            "damage_per_use": self.get_damage_per_use(),
            "healing_per_use": self.get_healing_per_use(),

            # Timing stats
            "average_execution_time": self.average_execution_time,
            "min_execution_time": self.min_execution_time if self.min_execution_time != float('inf') else 0.0,
            "max_execution_time": self.max_execution_time,

            # Cooldown info
            "cooldown_duration": self.get_cooldown_duration(),
            "cooldown_remaining": self.get_cooldown_remaining(),
            "is_on_cooldown": self.is_on_cooldown(),

            # Overall rating
            "effectiveness_rating": self.get_effectiveness_rating(),

            # Last used
            "last_used": self.last_used,
            "time_since_last_use": time.time() - self.last_used if self.last_used > 0 else 0.0
        }

    # ===============================
    # CONFIGURATION
    # ===============================

    def enable(self):
        """Włącz akcję"""
        self.enabled = True
        logging.info(f"Action enabled: {self.name}")

    def disable(self):
        """Wyłącz akcję"""
        self.enabled = False
        logging.info(f"Action disabled: {self.name}")

    def set_priority(self, priority: Priority):
        """Ustaw priorytet akcji"""
        old_priority = self.priority
        self.priority = priority
        logging.info(f"Action '{self.name}' priority changed: {old_priority.value} -> {priority.value}")

    def update_requirements(self, **kwargs):
        """Aktualizuj wymagania akcji"""
        for key, value in kwargs.items():
            if hasattr(self.requirements, key):
                old_value = getattr(self.requirements, key)
                setattr(self.requirements, key, value)
                logging.debug(f"Action '{self.name}' requirement updated: {key} = {value} (was: {old_value})")

    def reset_statistics(self):
        """Zresetuj statystyki"""
        self.usage_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_damage = 0.0
        self.total_healing = 0.0
        self.average_execution_time = 0.0
        self.min_execution_time = float('inf')
        self.max_execution_time = 0.0
        logging.info(f"Reset statistics for action: {self.name}")

    # ===============================
    # STRING REPRESENTATION
    # ===============================

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        cooldown_info = f"(CD: {self.get_cooldown_remaining():.1f}s)" if self.is_on_cooldown() else ""
        return f"{self.name} [{self.action_type.value}] {status} {cooldown_info}"

    def __repr__(self) -> str:
        return f"BaseAction(name='{self.name}', type={self.action_type}, priority={self.priority})"