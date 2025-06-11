# src/automation/rules/base_rule.py
"""
Klasa bazowa dla wszystkich reguł decyzyjnych w systemie automatyzacji
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..core.data_structures import GameState, Priority, ClassType
from ..core.decision_maker import DecisionScore, DecisionContext


# ===============================
# RULE CONFIGURATION
# ===============================

class RuleCategory(Enum):
    """Kategorie reguł"""
    EMERGENCY = "emergency"  # Krytyczne sytuacje (HP < 10%)
    SURVIVAL = "survival"  # Przetrwanie (healing, mana)
    COMBAT = "combat"  # Walka i ataki
    EFFICIENCY = "efficiency"  # Optymalizacja (buffy, regen)
    UTILITY = "utility"  # Pomocnicze (movement, items)
    SOCIAL = "social"  # Interakcje z graczami


@dataclass
class RuleCondition:
    """Warunek aktywacji reguły"""
    name: str
    condition_func: Callable[[GameState], bool]
    weight: float = 1.0
    required: bool = True  # Czy warunek jest wymagany
    description: str = ""


@dataclass
class RuleMetrics:
    """Metryki dla reguły"""
    activation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_score_generated: float = 0.0
    average_score: float = 0.0
    last_activation: float = 0.0
    last_success: float = 0.0

    def record_activation(self, score: float, success: bool = True):
        """Zapisz aktywację reguły"""
        self.activation_count += 1
        self.total_score_generated += score
        self.average_score = self.total_score_generated / self.activation_count
        self.last_activation = time.time()

        if success:
            self.success_count += 1
            self.last_success = time.time()
        else:
            self.failure_count += 1

    def get_success_rate(self) -> float:
        """Pobierz współczynnik sukcesu"""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100.0) if total > 0 else 0.0


# ===============================
# BASE RULE CLASS
# ===============================

class BaseRule(ABC):
    """
    Klasa bazowa dla wszystkich reguł decyzyjnych

    Reguła definiuje:
    - Warunki aktywacji (kiedy powinna być uruchomiona)
    - Akcje do wykonania (co powinna zrobić)
    - Priorytet i wagę (jak ważna jest)
    - Logikę oceny efektywności
    """

    def __init__(self, name: str, category: RuleCategory, priority: Priority,
                 weight: float = 1.0, enabled: bool = True):
        # Basic properties
        self.name = name
        self.category = category
        self.priority = priority
        self.weight = weight
        self.enabled = enabled

        # Conditions and actions
        self.conditions: List[RuleCondition] = []
        self.suggested_actions: List[str] = []

        # Timing and cooldowns
        self.min_activation_interval = 0.0  # Minimum time between activations
        self.rule_cooldown = 0.0  # Cooldown after activation
        self.last_activation_time = 0.0

        # Metrics and tracking
        self.metrics = RuleMetrics()

        # Configuration
        self.class_restrictions: List[ClassType] = []
        self.level_requirement = 1
        self.required_abilities: List[str] = []

        # Debugging and logging
        self.debug_mode = False
        self.description = ""
        self.reasoning_log: List[str] = []

        logging.debug(f"Initialized rule: {name} ({category.value}, priority: {priority.name})")

    # ===============================
    # ABSTRACT METHODS
    # ===============================

    @abstractmethod
    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """
        Oceń czy warunki reguły są spełnione
        Musi być zaimplementowane przez klasy dziedziczące
        """
        pass

    @abstractmethod
    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """
        Oblicz oceny dla akcji sugerowanych przez tę regułę
        Zwraca listę DecisionScore z uzasadnieniem
        """
        pass

    @abstractmethod
    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """
        Pobierz specyficzne uzasadnienie dla tej reguły
        Używane do debugowania i logowania
        """
        pass

    # ===============================
    # CORE INTERFACE METHODS
    # ===============================

    def can_apply(self, context: DecisionContext) -> bool:
        """
        Sprawdź czy reguła może być zastosowana w danym kontekście
        Implementuje interfejs DecisionRule z decision_maker.py
        """
        if not self.enabled:
            return False

        # Check cooldown
        if self.is_on_cooldown():
            if self.debug_mode:
                self._add_reasoning(f"Rule on cooldown for {self.get_cooldown_remaining():.1f}s")
            return False

        # Check minimum activation interval
        if self._within_min_interval():
            if self.debug_mode:
                self._add_reasoning("Within minimum activation interval")
            return False

        # Check class restrictions
        if not self._check_class_compatibility(context.character_class):
            if self.debug_mode:
                self._add_reasoning(f"Class restriction: requires {self.class_restrictions}")
            return False

        # Check required abilities
        if not self._check_required_abilities(context.available_actions):
            if self.debug_mode:
                self._add_reasoning(f"Missing required abilities: {self.required_abilities}")
            return False

        return True

    def evaluate(self, context: DecisionContext) -> List[DecisionScore]:
        """
        Główna metoda oceny reguły
        Implementuje interfejs DecisionRule z decision_maker.py
        """
        self.reasoning_log.clear()

        if not self.can_apply(context):
            return []

        # Evaluate rule-specific conditions
        if not self.evaluate_conditions(context):
            if self.debug_mode:
                self._add_reasoning("Rule conditions not met")
            return []

        # Calculate action scores
        try:
            scores = self.calculate_action_scores(context)

            # Apply rule weight and priority multiplier
            priority_multiplier = self.get_priority_multiplier()

            for score in scores:
                # Apply rule weight
                score.score *= self.weight
                score.score *= priority_multiplier

                # Add rule-specific reasoning
                rule_reasoning = self.get_rule_specific_reasoning(context)
                score.reasoning.extend(rule_reasoning)

                # Add rule identification
                score.reasoning.append(f"Rule: {self.name}")

            # Record successful activation
            if scores:
                max_score = max(scores, key=lambda s: s.score)
                self.metrics.record_activation(max_score.score, True)
                self.last_activation_time = time.time()

                if self.debug_mode:
                    self._add_reasoning(f"Generated {len(scores)} action suggestions")

            return scores

        except Exception as e:
            logging.error(f"Error evaluating rule '{self.name}': {e}")
            self.metrics.record_activation(0.0, False)
            return []

    # ===============================
    # CONDITION MANAGEMENT
    # ===============================

    def add_condition(self, name: str, condition_func: Callable[[GameState], bool],
                      weight: float = 1.0, required: bool = True, description: str = ""):
        """Dodaj warunek do reguły"""
        condition = RuleCondition(
            name=name,
            condition_func=condition_func,
            weight=weight,
            required=required,
            description=description
        )
        self.conditions.append(condition)

        if self.debug_mode:
            logging.debug(f"Added condition '{name}' to rule '{self.name}'")

    def remove_condition(self, name: str) -> bool:
        """Usuń warunek z reguły"""
        for i, condition in enumerate(self.conditions):
            if condition.name == name:
                del self.conditions[i]
                if self.debug_mode:
                    logging.debug(f"Removed condition '{name}' from rule '{self.name}'")
                return True
        return False

    def evaluate_all_conditions(self, game_state: GameState) -> tuple[bool, float]:
        """
        Oceń wszystkie warunki reguły
        Returns: (all_required_met, weighted_score)
        """
        if not self.conditions:
            return True, 1.0

        required_met = True
        total_weight = 0.0
        met_weight = 0.0

        for condition in self.conditions:
            try:
                is_met = condition.condition_func(game_state)
                total_weight += condition.weight

                if is_met:
                    met_weight += condition.weight
                    if self.debug_mode:
                        self._add_reasoning(f"✓ {condition.name}")
                elif condition.required:
                    required_met = False
                    if self.debug_mode:
                        self._add_reasoning(f"✗ {condition.name} (required)")
                else:
                    if self.debug_mode:
                        self._add_reasoning(f"✗ {condition.name} (optional)")

            except Exception as e:
                logging.error(f"Error evaluating condition '{condition.name}': {e}")
                if condition.required:
                    required_met = False

        weighted_score = met_weight / total_weight if total_weight > 0 else 1.0

        return required_met, weighted_score

    # ===============================
    # ACTION MANAGEMENT
    # ===============================

    def add_suggested_action(self, action_name: str):
        """Dodaj sugerowaną akcję"""
        if action_name not in self.suggested_actions:
            self.suggested_actions.append(action_name)
            if self.debug_mode:
                logging.debug(f"Added suggested action '{action_name}' to rule '{self.name}'")

    def remove_suggested_action(self, action_name: str) -> bool:
        """Usuń sugerowaną akcję"""
        if action_name in self.suggested_actions:
            self.suggested_actions.remove(action_name)
            if self.debug_mode:
                logging.debug(f"Removed suggested action '{action_name}' from rule '{self.name}'")
            return True
        return False

    def get_available_suggested_actions(self, available_actions: Dict[str, Any]) -> List[str]:
        """Pobierz dostępne sugerowane akcje"""
        return [action for action in self.suggested_actions if action in available_actions]

    # ===============================
    # UTILITY METHODS
    # ===============================

    def get_priority_multiplier(self) -> float:
        """Pobierz mnożnik priorytetu"""
        priority_multipliers = {
            Priority.EMERGENCY: 10.0,
            Priority.HIGH: 5.0,
            Priority.MEDIUM: 2.0,
            Priority.LOW: 1.0,
            Priority.IDLE: 0.5
        }
        return priority_multipliers.get(self.priority, 1.0)

    def is_on_cooldown(self) -> bool:
        """Sprawdź czy reguła jest na cooldown"""
        if self.rule_cooldown <= 0:
            return False

        elapsed = time.time() - self.last_activation_time
        return elapsed < self.rule_cooldown

    def get_cooldown_remaining(self) -> float:
        """Pobierz pozostały czas cooldown"""
        if self.rule_cooldown <= 0:
            return 0.0

        elapsed = time.time() - self.last_activation_time
        remaining = self.rule_cooldown - elapsed
        return max(0.0, remaining)

    def _within_min_interval(self) -> bool:
        """Sprawdź czy jesteśmy w minimalnym interwale aktywacji"""
        if self.min_activation_interval <= 0:
            return False

        elapsed = time.time() - self.last_activation_time
        return elapsed < self.min_activation_interval

    def _check_class_compatibility(self, character_class: ClassType) -> bool:
        """Sprawdź kompatybilność z klasą"""
        if not self.class_restrictions:
            return True

        return character_class in self.class_restrictions

    def _check_required_abilities(self, available_actions: Dict[str, Any]) -> bool:
        """Sprawdź czy wymagane umiejętności są dostępne"""
        if not self.required_abilities:
            return True

        for ability in self.required_abilities:
            if ability not in available_actions:
                return False

        return True

    def _add_reasoning(self, reason: str):
        """Dodaj uzasadnienie do logu"""
        self.reasoning_log.append(reason)
        if self.debug_mode:
            logging.debug(f"[{self.name}] {reason}")

    # ===============================
    # CONFIGURATION & MANAGEMENT
    # ===============================

    def enable(self):
        """Włącz regułę"""
        self.enabled = True
        logging.info(f"Rule enabled: {self.name}")

    def disable(self):
        """Wyłącz regułę"""
        self.enabled = False
        logging.info(f"Rule disabled: {self.name}")

    def set_priority(self, priority: Priority):
        """Ustaw priorytet reguły"""
        old_priority = self.priority
        self.priority = priority
        logging.info(f"Rule '{self.name}' priority changed: {old_priority.name} -> {priority.name}")

    def set_weight(self, weight: float):
        """Ustaw wagę reguły"""
        old_weight = self.weight
        self.weight = max(0.0, weight)
        if self.debug_mode:
            logging.debug(f"Rule '{self.name}' weight changed: {old_weight} -> {self.weight}")

    def set_cooldown(self, cooldown: float):
        """Ustaw cooldown reguły"""
        self.rule_cooldown = max(0.0, cooldown)
        if self.debug_mode:
            logging.debug(f"Rule '{self.name}' cooldown set to {self.rule_cooldown}s")

    def add_class_restriction(self, character_class: ClassType):
        """Dodaj ograniczenie klasy"""
        if character_class not in self.class_restrictions:
            self.class_restrictions.append(character_class)
            logging.debug(f"Added class restriction {character_class.value} to rule '{self.name}'")

    def remove_class_restriction(self, character_class: ClassType):
        """Usuń ograniczenie klasy"""
        if character_class in self.class_restrictions:
            self.class_restrictions.remove(character_class)
            logging.debug(f"Removed class restriction {character_class.value} from rule '{self.name}'")

    def set_debug_mode(self, enabled: bool):
        """Włącz/wyłącz tryb debug"""
        self.debug_mode = enabled
        if enabled:
            logging.debug(f"Debug mode enabled for rule: {self.name}")

    # ===============================
    # STATISTICS & ANALYSIS
    # ===============================

    def get_statistics(self) -> Dict[str, Any]:
        """Pobierz statystyki reguły"""
        return {
            "name": self.name,
            "category": self.category.value,
            "priority": self.priority.name,
            "weight": self.weight,
            "enabled": self.enabled,

            # Activation stats
            "activation_count": self.metrics.activation_count,
            "success_count": self.metrics.success_count,
            "failure_count": self.metrics.failure_count,
            "success_rate": self.metrics.get_success_rate(),

            # Score stats
            "total_score_generated": self.metrics.total_score_generated,
            "average_score": self.metrics.average_score,

            # Timing
            "last_activation": self.metrics.last_activation,
            "last_success": self.metrics.last_success,
            "time_since_last_activation": time.time() - self.metrics.last_activation if self.metrics.last_activation > 0 else 0.0,

            # Configuration
            "cooldown": self.rule_cooldown,
            "cooldown_remaining": self.get_cooldown_remaining(),
            "min_activation_interval": self.min_activation_interval,
            "class_restrictions": [cls.value for cls in self.class_restrictions],
            "required_abilities": self.required_abilities.copy(),
            "suggested_actions": self.suggested_actions.copy(),
            "condition_count": len(self.conditions)
        }

    def get_recent_reasoning(self) -> List[str]:
        """Pobierz ostatnie uzasadnienia"""
        return self.reasoning_log.copy()

    def reset_statistics(self):
        """Zresetuj statystyki reguły"""
        self.metrics = RuleMetrics()
        self.reasoning_log.clear()
        logging.info(f"Reset statistics for rule: {self.name}")

    def get_effectiveness_rating(self) -> float:
        """Oblicz ocenę efektywności reguły (0.0 - 1.0)"""
        if self.metrics.activation_count == 0:
            return 0.5  # Neutral for unused rules

        # Success rate factor
        success_factor = self.metrics.get_success_rate() / 100.0

        # Activity factor (more activations = more relevant)
        activity_factor = min(1.0, self.metrics.activation_count / 100.0)

        # Score quality factor
        score_factor = min(1.0, self.metrics.average_score / 10.0) if self.metrics.average_score > 0 else 0.0

        # Combined effectiveness
        return (success_factor * 0.5 + activity_factor * 0.3 + score_factor * 0.2)

    # ===============================
    # STRING REPRESENTATION
    # ===============================

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        cooldown_info = f"(CD: {self.get_cooldown_remaining():.1f}s)" if self.is_on_cooldown() else ""
        return f"{self.name} [{self.category.value}] {status} {cooldown_info}"

    def __repr__(self) -> str:
        return f"BaseRule(name='{self.name}', category={self.category}, priority={self.priority})"


# ===============================
# RULE UTILITIES
# ===============================

def create_health_condition(threshold: float, operator: str = "less_than") -> Callable[[GameState], bool]:
    """Utwórz warunek zdrowia"""

    def condition(game_state: GameState) -> bool:
        hp_percent = game_state.resources.health_percent

        if operator == "less_than":
            return hp_percent < threshold
        elif operator == "greater_than":
            return hp_percent > threshold
        elif operator == "equal":
            return abs(hp_percent - threshold) < 1.0
        elif operator == "less_equal":
            return hp_percent <= threshold
        elif operator == "greater_equal":
            return hp_percent >= threshold

        return False

    return condition


def create_mana_condition(threshold: float, operator: str = "less_than") -> Callable[[GameState], bool]:
    """Utwórz warunek many"""

    def condition(game_state: GameState) -> bool:
        mana_percent = game_state.resources.mana_percent

        if operator == "less_than":
            return mana_percent < threshold
        elif operator == "greater_than":
            return mana_percent > threshold
        elif operator == "equal":
            return abs(mana_percent - threshold) < 1.0
        elif operator == "less_equal":
            return mana_percent <= threshold
        elif operator == "greater_equal":
            return mana_percent >= threshold

        return False

    return condition


def create_combat_condition(in_combat: bool) -> Callable[[GameState], bool]:
    """Utwórz warunek walki"""

    def condition(game_state: GameState) -> bool:
        return game_state.in_combat == in_combat

    return condition


def create_target_condition(has_target: bool) -> Callable[[GameState], bool]:
    """Utwórz warunek celu"""

    def condition(game_state: GameState) -> bool:
        return game_state.target.exists == has_target

    return condition


def create_target_health_condition(threshold: float, operator: str = "less_than") -> Callable[[GameState], bool]:
    """Utwórz warunek zdrowia celu"""

    def condition(game_state: GameState) -> bool:
        if not game_state.target.exists:
            return False

        target_hp = game_state.target.hp_percent

        if operator == "less_than":
            return target_hp < threshold
        elif operator == "greater_than":
            return target_hp > threshold
        elif operator == "equal":
            return abs(target_hp - threshold) < 1.0
        elif operator == "less_equal":
            return target_hp <= threshold
        elif operator == "greater_equal":
            return target_hp >= threshold

        return False

    return condition


def create_buff_condition(buff_name: str, has_buff: bool = True) -> Callable[[GameState], bool]:
    """Utwórz warunek buffa"""

    def condition(game_state: GameState) -> bool:
        return game_state.has_buff(buff_name) == has_buff

    return condition