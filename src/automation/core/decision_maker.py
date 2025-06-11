# src/automation/core/decision_maker.py
"""
System podejmowania decyzji - wybiera najlepszą akcję na podstawie stanu gry i reguł
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections import defaultdict, deque

from .data_structures import (
    GameState, ActionDefinition, ActionResult, Priority, ActionType,
    ClassType, CombatState, Cooldown
)


# ===============================
# DECISION CONTEXT
# ===============================

@dataclass
class DecisionContext:
    """Kontekst decyzji zawierający dodatkowe informacje"""
    game_state: GameState
    character_class: ClassType
    available_actions: Dict[str, 'ActionInstance']
    active_cooldowns: Dict[str, Cooldown]
    recent_actions: List[ActionResult]
    decision_timestamp: float = field(default_factory=time.time)

    # Performance context
    last_decision_time: float = 0.0
    decisions_per_minute: float = 0.0

    # Safety context
    consecutive_failed_actions: int = 0
    last_successful_action_time: float = 0.0


@dataclass
class DecisionScore:
    """Wynik oceny decyzji"""
    action_name: str
    score: float
    priority: Priority
    reasoning: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def add_reasoning(self, reason: str, score_modifier: float = 0.0):
        """Dodaj uzasadnienie i opcjonalnie zmień score"""
        self.reasoning.append(reason)
        self.score += score_modifier


# ===============================
# DECISION RULES INTERFACE
# ===============================

class DecisionRule(ABC):
    """Bazowa klasa dla reguł decyzyjnych"""

    def __init__(self, name: str, priority: Priority, weight: float = 1.0):
        self.name = name
        self.priority = priority
        self.weight = weight
        self.enabled = True
        self.activation_count = 0
        self.last_activation = 0.0

    @abstractmethod
    def evaluate(self, context: DecisionContext) -> List[DecisionScore]:
        """
        Oceń kontekst i zwróć listę rekomendowanych akcji z wynikami
        """
        pass

    @abstractmethod
    def can_apply(self, context: DecisionContext) -> bool:
        """
        Sprawdź czy reguła może być zastosowana w danym kontekście
        """
        pass

    def get_priority_multiplier(self) -> float:
        """Pobierz mnożnik priorytetu (wyższy priorytet = wyższy mnożnik)"""
        priority_multipliers = {
            Priority.EMERGENCY: 10.0,
            Priority.HIGH: 5.0,
            Priority.MEDIUM: 2.0,
            Priority.LOW: 1.0,
            Priority.IDLE: 0.5
        }
        return priority_multipliers.get(self.priority, 1.0)


# ===============================
# ACTION INSTANCE
# ===============================

class ActionInstance:
    """Instancja akcji z trackingiem stanu"""

    def __init__(self, definition: ActionDefinition):
        self.definition = definition
        self.last_used = 0.0
        self.usage_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_damage = 0.0
        self.total_healing = 0.0
        self.enabled = True

        # Performance tracking
        self.average_execution_time = 0.0
        self.last_execution_results = deque(maxlen=10)

    @property
    def success_rate(self) -> float:
        """Współczynnik sukcesu akcji"""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100.0) if total > 0 else 100.0

    @property
    def cooldown_remaining(self) -> float:
        """Pozostały czas cooldown"""
        if self.definition.cooldown <= 0:
            return 0.0
        elapsed = time.time() - self.last_used
        remaining = self.definition.cooldown - elapsed
        return max(0.0, remaining)

    @property
    def is_ready(self) -> bool:
        """Sprawdź czy akcja jest gotowa do użycia"""
        return self.cooldown_remaining <= 0.0 and self.enabled

    def can_execute(self, game_state: GameState, character_class: ClassType) -> Tuple[bool, str]:
        """
        Sprawdź czy akcja może być wykonana
        Returns: (can_execute, reason_if_not)
        """
        if not self.enabled:
            return False, "Action disabled"

        if not self.is_ready:
            return False, f"Cooldown remaining: {self.cooldown_remaining:.1f}s"

        if not self.definition.meets_requirements(game_state, character_class):
            return False, "Requirements not met"

        # Check casting state
        if game_state.is_casting and self.definition.global_cooldown:
            return False, "Currently casting"

        # Check combat requirements
        if self.definition.requires_combat and not game_state.in_combat:
            return False, "Requires combat"

        if self.definition.requires_target and not game_state.target.exists:
            return False, "Requires target"

        return True, ""

    def record_usage(self, result: ActionResult):
        """Zapisz rezultat użycia akcji"""
        self.last_used = time.time()
        self.usage_count += 1

        if result.success:
            self.success_count += 1
            self.total_damage += result.damage_dealt
            self.total_healing += result.healing_done
        else:
            self.failure_count += 1

        # Update performance tracking
        self.last_execution_results.append(result)
        if result.execution_time > 0:
            # Simple moving average
            alpha = 0.2
            self.average_execution_time = (
                    alpha * result.execution_time +
                    (1 - alpha) * self.average_execution_time
            )


# ===============================
# MAIN DECISION MAKER
# ===============================

class DecisionMaker:
    """
    Główny system podejmowania decyzji
    """

    def __init__(self, character_class: ClassType):
        self.character_class = character_class

        # Rules and actions
        self.rules: List[DecisionRule] = []
        self.actions: Dict[str, ActionInstance] = {}
        self.rule_groups: Dict[Priority, List[DecisionRule]] = defaultdict(list)

        # Decision tracking
        self.decision_history = deque(maxlen=100)
        self.last_decision_time = 0.0
        self.min_decision_interval = 0.1  # Minimum 100ms between decisions

        # Performance settings
        self.max_rules_per_evaluation = 20
        self.decision_timeout = 0.05  # Max 50ms for decision making

        # Statistics
        self.stats = {
            'total_decisions': 0,
            'successful_decisions': 0,
            'failed_decisions': 0,
            'average_decision_time': 0.0,
            'decisions_per_minute': 0.0,
            'last_decision_timestamp': 0.0
        }

        logging.info(f"DecisionMaker initialized for class: {character_class.value}")

    # ===============================
    # RULE MANAGEMENT
    # ===============================

    def add_rule(self, rule: DecisionRule):
        """Dodaj regułę decyzyjną"""
        self.rules.append(rule)
        self.rule_groups[rule.priority].append(rule)

        # Sort rules by priority within each group
        self.rule_groups[rule.priority].sort(key=lambda r: r.weight, reverse=True)

        logging.info(f"Added decision rule: {rule.name} (priority: {rule.priority.name})")

    def remove_rule(self, rule_name: str) -> bool:
        """Usuń regułę"""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                # Remove from main list
                removed_rule = self.rules.pop(i)

                # Remove from priority group
                if removed_rule in self.rule_groups[removed_rule.priority]:
                    self.rule_groups[removed_rule.priority].remove(removed_rule)

                logging.info(f"Removed decision rule: {rule_name}")
                return True

        logging.warning(f"Rule not found: {rule_name}")
        return False

    def get_rules_by_priority(self, priority: Priority) -> List[DecisionRule]:
        """Pobierz reguły o danym priorytecie"""
        return self.rule_groups[priority].copy()

    # ===============================
    # ACTION MANAGEMENT
    # ===============================

    def add_action(self, action_name: str, action_definition: ActionDefinition):
        """Dodaj dostępną akcję"""
        self.actions[action_name] = ActionInstance(action_definition)
        logging.info(f"Added action: {action_name}")

    def remove_action(self, action_name: str) -> bool:
        """Usuń akcję"""
        if action_name in self.actions:
            del self.actions[action_name]
            logging.info(f"Removed action: {action_name}")
            return True
        return False

    def get_available_actions(self, game_state: GameState) -> Dict[str, ActionInstance]:
        """Pobierz akcje dostępne w danym stanie gry"""
        available = {}

        for name, action in self.actions.items():
            can_execute, _ = action.can_execute(game_state, self.character_class)
            if can_execute:
                available[name] = action

        return available

    def get_action_cooldowns(self) -> Dict[str, Cooldown]:
        """Pobierz aktywne cooldowny"""
        cooldowns = {}

        for name, action in self.actions.items():
            if action.cooldown_remaining > 0:
                cooldowns[name] = Cooldown(
                    name=name,
                    duration=action.definition.cooldown,
                    started_at=action.last_used
                )

        return cooldowns

    # ===============================
    # MAIN DECISION LOGIC
    # ===============================

    def make_decision(self, game_state: GameState,
                      recent_actions: Optional[List[ActionResult]] = None) -> Optional[str]:
        """
        Podejmij decyzję o następnej akcji
        Returns: nazwa akcji do wykonania lub None
        """
        start_time = time.time()

        # Check minimum interval
        if (start_time - self.last_decision_time) < self.min_decision_interval:
            return None

        # Safety check - don't make decisions if not safe
        if not game_state.is_safe_to_act():
            return None

        try:
            # Create decision context
            context = DecisionContext(
                game_state=game_state,
                character_class=self.character_class,
                available_actions=self.get_available_actions(game_state),
                active_cooldowns=self.get_action_cooldowns(),
                recent_actions=recent_actions or [],
                last_decision_time=self.last_decision_time
            )

            # Get all decision scores
            all_scores = self._evaluate_all_rules(context)

            # Select best action
            best_action = self._select_best_action(all_scores, context)

            # Update tracking
            decision_time = time.time() - start_time
            self._update_decision_stats(decision_time, best_action is not None)
            self.last_decision_time = time.time()

            if best_action:
                logging.debug(f"Decision: {best_action} (took {decision_time * 1000:.1f}ms)")

            return best_action

        except Exception as e:
            logging.error(f"Error in decision making: {e}")
            self.stats['failed_decisions'] += 1
            return None

    def _evaluate_all_rules(self, context: DecisionContext) -> List[DecisionScore]:
        """Oceń wszystkie reguły i zbierz wyniki"""
        all_scores = []
        rules_evaluated = 0

        # Evaluate by priority (Emergency first, then High, etc.)
        for priority in [Priority.EMERGENCY, Priority.HIGH, Priority.MEDIUM, Priority.LOW, Priority.IDLE]:
            if rules_evaluated >= self.max_rules_per_evaluation:
                break

            rules = self.rule_groups[priority]

            for rule in rules:
                if not rule.enabled or not rule.can_apply(context):
                    continue

                try:
                    scores = rule.evaluate(context)

                    # Apply priority multiplier
                    priority_multiplier = rule.get_priority_multiplier()
                    for score in scores:
                        score.score *= priority_multiplier
                        score.score *= rule.weight

                    all_scores.extend(scores)
                    rule.activation_count += 1
                    rule.last_activation = time.time()

                    rules_evaluated += 1

                    # For emergency rules, stop after first match
                    if priority == Priority.EMERGENCY and scores:
                        break

                except Exception as e:
                    logging.error(f"Error evaluating rule '{rule.name}': {e}")
                    continue

        return all_scores

    def _select_best_action(self, scores: List[DecisionScore],
                            context: DecisionContext) -> Optional[str]:
        """Wybierz najlepszą akcję z listy wyników"""
        if not scores:
            return None

        # Filter out actions that can't be executed
        executable_scores = []

        for score in scores:
            if score.action_name in context.available_actions:
                action = context.available_actions[score.action_name]
                can_execute, reason = action.can_execute(
                    context.game_state,
                    context.character_class
                )

                if can_execute:
                    executable_scores.append(score)
                else:
                    logging.debug(f"Skipping {score.action_name}: {reason}")

        if not executable_scores:
            return None

        # Sort by score (highest first)
        executable_scores.sort(key=lambda s: s.score, reverse=True)

        # Log top candidates for debugging
        if len(executable_scores) > 1:
            top_3 = executable_scores[:3]
            logging.debug("Top action candidates:")
            for i, score in enumerate(top_3):
                reasoning = "; ".join(score.reasoning[:2])  # First 2 reasons
                logging.debug(f"  {i + 1}. {score.action_name}: {score.score:.2f} ({reasoning})")

        # Return best action
        best_score = executable_scores[0]
        self.decision_history.append(best_score)

        return best_score.action_name

    # ===============================
    # STATISTICS & MONITORING
    # ===============================

    def _update_decision_stats(self, decision_time: float, success: bool):
        """Aktualizuj statystyki decyzji"""
        self.stats['total_decisions'] += 1

        if success:
            self.stats['successful_decisions'] += 1
        else:
            self.stats['failed_decisions'] += 1

        # Update average decision time (moving average)
        alpha = 0.1
        self.stats['average_decision_time'] = (
                alpha * decision_time +
                (1 - alpha) * self.stats['average_decision_time']
        )

        self.stats['last_decision_timestamp'] = time.time()

        # Calculate decisions per minute
        if len(self.decision_history) >= 2:
            time_span = (self.decision_history[-1].decision_timestamp -
                         self.decision_history[0].decision_timestamp)
            if time_span > 0:
                self.stats['decisions_per_minute'] = (len(self.decision_history) / time_span) * 60

    def get_decision_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki decyzji"""
        stats = self.stats.copy()

        # Add success rate
        total = stats['total_decisions']
        if total > 0:
            stats['success_rate'] = (stats['successful_decisions'] / total) * 100.0
        else:
            stats['success_rate'] = 0.0

        # Add rule statistics
        stats['active_rules'] = len([r for r in self.rules if r.enabled])
        stats['total_rules'] = len(self.rules)
        stats['available_actions'] = len(self.actions)

        return stats

    def get_action_stats(self) -> Dict[str, Dict[str, Any]]:
        """Pobierz statystyki akcji"""
        action_stats = {}

        for name, action in self.actions.items():
            action_stats[name] = {
                'usage_count': action.usage_count,
                'success_rate': action.success_rate,
                'total_damage': action.total_damage,
                'total_healing': action.total_healing,
                'cooldown_remaining': action.cooldown_remaining,
                'average_execution_time': action.average_execution_time,
                'enabled': action.enabled
            }

        return action_stats

    def get_recent_decisions(self, count: int = 10) -> List[DecisionScore]:
        """Pobierz ostatnie decyzje"""
        return list(self.decision_history)[-count:]

    # ===============================
    # CONFIGURATION
    # ===============================

    def configure(self, **kwargs):
        """Skonfiguruj parametry decision maker"""
        if 'min_decision_interval' in kwargs:
            self.min_decision_interval = kwargs['min_decision_interval']

        if 'max_rules_per_evaluation' in kwargs:
            self.max_rules_per_evaluation = kwargs['max_rules_per_evaluation']

        if 'decision_timeout' in kwargs:
            self.decision_timeout = kwargs['decision_timeout']

        logging.info("DecisionMaker configuration updated")

    def enable_rule(self, rule_name: str) -> bool:
        """Włącz regułę"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                logging.info(f"Enabled rule: {rule_name}")
                return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Wyłącz regułę"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                logging.info(f"Disabled rule: {rule_name}")
                return True
        return False

    def enable_action(self, action_name: str) -> bool:
        """Włącz akcję"""
        if action_name in self.actions:
            self.actions[action_name].enabled = True
            logging.info(f"Enabled action: {action_name}")
            return True
        return False

    def disable_action(self, action_name: str) -> bool:
        """Wyłącz akcję"""
        if action_name in self.actions:
            self.actions[action_name].enabled = False
            logging.info(f"Disabled action: {action_name}")
            return True
        return False

    def reset_stats(self):
        """Zresetuj statystyki"""
        self.stats = {
            'total_decisions': 0,
            'successful_decisions': 0,
            'failed_decisions': 0,
            'average_decision_time': 0.0,
            'decisions_per_minute': 0.0,
            'last_decision_timestamp': 0.0
        }

        # Reset action stats
        for action in self.actions.values():
            action.usage_count = 0
            action.success_count = 0
            action.failure_count = 0
            action.total_damage = 0.0
            action.total_healing = 0.0
            action.last_execution_results.clear()

        # Reset rule stats
        for rule in self.rules:
            rule.activation_count = 0
            rule.last_activation = 0.0

        self.decision_history.clear()
        logging.info("DecisionMaker stats reset")