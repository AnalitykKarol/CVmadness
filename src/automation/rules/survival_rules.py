# src/automation/rules/survival_rules.py
"""
Reguły przetrwania - healing, mana management, emergency actions
"""

import time
import logging
from typing import List, Dict, Any

from ..core.data_structures import GameState, Priority, ClassType
from ..core.decision_maker import DecisionScore, DecisionContext
from .base_rule import (
    BaseRule, RuleCategory, create_health_condition, create_mana_condition,
    create_combat_condition, create_target_condition
)


# ===============================
# EMERGENCY SURVIVAL RULES
# ===============================

class EmergencyHealRule(BaseRule):
    """Reguła emergency heal - najwyższy priorytet gdy HP krytyczne"""

    def __init__(self, hp_threshold: float = 15.0, emergency_actions: List[str] = None):
        super().__init__(
            name="Emergency Heal",
            category=RuleCategory.EMERGENCY,
            priority=Priority.EMERGENCY,
            weight=10.0
        )

        self.hp_threshold = hp_threshold
        self.emergency_actions = emergency_actions or [
            "health_potion", "flash_heal", "light_heal", "bandage"
        ]

        # Setup conditions
        self.add_condition(
            "critical_health",
            create_health_condition(hp_threshold, "less_than"),
            weight=2.0,
            required=True,
            description=f"Health below {hp_threshold}%"
        )

        # Add suggested actions
        for action in self.emergency_actions:
            self.add_suggested_action(action)

        self.description = f"Emergency healing when health drops below {hp_threshold}%"
        self.min_activation_interval = 0.5  # Can activate every 0.5s

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki emergency heal"""
        game_state = context.game_state

        # Primary condition: very low health
        if game_state.resources.health_percent >= self.hp_threshold:
            return False

        # Don't heal if already at full health (edge case)
        if game_state.resources.health_percent >= 95.0:
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla emergency actions"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        # Calculate urgency multiplier based on how low health is
        urgency = 1.0 + (self.hp_threshold - game_state.resources.health_percent) / 10.0
        urgency = min(3.0, urgency)  # Cap at 3x multiplier

        # Score emergency actions by preference
        action_priorities = {
            "health_potion": 10.0,  # Instant, no mana cost
            "flash_heal": 8.0,  # Instant but costs mana
            "light_heal": 6.0,  # Fast cast
            "greater_heal": 4.0,  # Slow but powerful
            "bandage": 2.0  # Slow, out of combat only
        }

        for action_name in self.emergency_actions:
            if action_name in available_actions:
                base_score = action_priorities.get(action_name, 5.0)

                # Apply urgency multiplier
                final_score = base_score * urgency

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.95
                )

                score.add_reasoning(
                    f"EMERGENCY: Health at {game_state.resources.health_percent:.1f}%",
                    0.0
                )
                score.add_reasoning(f"Urgency multiplier: {urgency:.1f}x", 0.0)

                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Pobierz uzasadnienie emergency heal"""
        hp = context.game_state.resources.health_percent
        return [
            f"Health critically low: {hp:.1f}% < {self.hp_threshold}%",
            "IMMEDIATE ACTION REQUIRED"
        ]


class CriticalManaRule(BaseRule):
    """Reguła critical mana - wysokie priority gdy mana bardzo niska"""

    def __init__(self, mana_threshold: float = 10.0, mana_actions: List[str] = None):
        super().__init__(
            name="Critical Mana",
            category=RuleCategory.EMERGENCY,
            priority=Priority.HIGH,
            weight=5.0
        )

        self.mana_threshold = mana_threshold
        self.mana_actions = mana_actions or ["mana_potion", "drink_water"]

        # Setup conditions
        self.add_condition(
            "critical_mana",
            create_mana_condition(mana_threshold, "less_than"),
            weight=2.0,
            required=True,
            description=f"Mana below {mana_threshold}%"
        )

        self.add_condition(
            "not_dead",
            create_health_condition(5.0, "greater_than"),
            weight=1.0,
            required=True,
            description="Not dying (health > 5%)"
        )

        for action in self.mana_actions:
            self.add_suggested_action(action)

        self.description = f"Restore mana when below {mana_threshold}%"

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki critical mana"""
        game_state = context.game_state

        # Don't worry about mana if health is critical
        if game_state.resources.health_percent < 20.0:
            return False

        # Don't drink in combat unless really desperate
        if (game_state.in_combat and
                game_state.resources.mana_percent > 5.0):
            return False

        return game_state.resources.mana_percent < self.mana_threshold

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla mana actions"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        mana_percent = game_state.resources.mana_percent
        urgency = (self.mana_threshold - mana_percent) / 10.0
        urgency = max(0.1, min(2.0, urgency))

        action_scores = {
            "mana_potion": 8.0,  # Works in combat
            "drink_water": 5.0  # Out of combat only
        }

        for action_name in self.mana_actions:
            if action_name in available_actions:
                base_score = action_scores.get(action_name, 3.0)

                # Reduce score for drink_water in combat
                if action_name == "drink_water" and game_state.in_combat:
                    base_score *= 0.2

                final_score = base_score * urgency

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.8
                )

                score.add_reasoning(f"Mana critical: {mana_percent:.1f}%", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie critical mana"""
        mana = context.game_state.resources.mana_percent
        return [f"Mana critically low: {mana:.1f}% < {self.mana_threshold}%"]


# ===============================
# REGULAR SURVIVAL RULES
# ===============================

class RegularHealRule(BaseRule):
    """Reguła regular healing - gdy HP średnio niskie"""

    def __init__(self, hp_threshold: float = 60.0, heal_actions: List[str] = None):
        super().__init__(
            name="Regular Heal",
            category=RuleCategory.SURVIVAL,
            priority=Priority.HIGH,
            weight=3.0
        )

        self.hp_threshold = hp_threshold
        self.heal_actions = heal_actions or [
            "light_heal", "greater_heal", "bandage", "eat_food"
        ]

        # Conditions
        self.add_condition(
            "moderate_damage",
            create_health_condition(hp_threshold, "less_than"),
            weight=1.5,
            required=True,
            description=f"Health below {hp_threshold}%"
        )

        self.add_condition(
            "not_emergency",
            create_health_condition(20.0, "greater_than"),
            weight=1.0,
            required=True,
            description="Not emergency (health > 20%)"
        )

        for action in self.heal_actions:
            self.add_suggested_action(action)

        self.description = f"Regular healing when health below {hp_threshold}%"
        self.min_activation_interval = 2.0  # Don't spam heals

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki regular heal"""
        game_state = context.game_state
        hp = game_state.resources.health_percent

        # Must be in the sweet spot - not emergency, not full
        if hp <= 20.0 or hp >= self.hp_threshold:
            return False

        # Don't heal if mana is very low (unless health is getting dangerous)
        if (game_state.resources.mana_percent < 15.0 and hp > 40.0):
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla regular healing"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        hp = game_state.resources.health_percent
        mana = game_state.resources.mana_percent

        # Calculate healing need (higher score when more damaged)
        heal_need = (self.hp_threshold - hp) / self.hp_threshold
        heal_need = max(0.1, min(1.0, heal_need))

        # Efficiency preferences
        action_preferences = {
            "light_heal": 6.0,  # Fast, efficient
            "greater_heal": 4.0,  # Slow, powerful
            "bandage": 3.0,  # Free but slow
            "eat_food": 2.0  # Very slow, out of combat
        }

        for action_name in self.heal_actions:
            if action_name in available_actions:
                base_score = action_preferences.get(action_name, 3.0)

                # Adjust based on context
                if action_name in ["bandage", "eat_food"]:
                    if game_state.in_combat:
                        base_score *= 0.1  # Very low priority in combat
                    elif mana < 30.0:
                        base_score *= 2.0  # Higher priority when low mana

                # Mana efficiency bonus
                if action_name == "bandage" and mana > 80.0:
                    base_score *= 0.5  # Use mana instead if plenty available

                final_score = base_score * heal_need

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.7
                )

                score.add_reasoning(f"Health at {hp:.1f}%, healing needed", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie regular heal"""
        hp = context.game_state.resources.health_percent
        return [f"Moderate damage: {hp:.1f}% < {self.hp_threshold}%"]


class ManaManagementRule(BaseRule):
    """Reguła zarządzania maną - picie gdy bezpiecznie"""

    def __init__(self, mana_threshold: float = 40.0):
        super().__init__(
            name="Mana Management",
            category=RuleCategory.EFFICIENCY,
            priority=Priority.MEDIUM,
            weight=2.0
        )

        self.mana_threshold = mana_threshold

        # Conditions
        self.add_condition(
            "low_mana",
            create_mana_condition(mana_threshold, "less_than"),
            weight=1.5,
            required=True,
            description=f"Mana below {mana_threshold}%"
        )

        self.add_condition(
            "safe_health",
            create_health_condition(70.0, "greater_than"),
            weight=1.0,
            required=True,
            description="Health safe (> 70%)"
        )

        self.add_condition(
            "out_of_combat",
            create_combat_condition(False),
            weight=2.0,
            required=False,  # Preferred but not required
            description="Out of combat"
        )

        self.add_suggested_action("drink_water")
        self.add_suggested_action("mana_potion")

        self.description = f"Manage mana when below {mana_threshold}% and safe"
        self.min_activation_interval = 3.0

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki mana management"""
        game_state = context.game_state

        # Must have reasonable health
        if game_state.resources.health_percent < 70.0:
            return False

        # Prefer out of combat but allow in combat if desperate
        if game_state.in_combat and game_state.resources.mana_percent > 20.0:
            return False

        return game_state.resources.mana_percent < self.mana_threshold

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla mana management"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        mana = game_state.resources.mana_percent
        mana_need = (self.mana_threshold - mana) / self.mana_threshold

        actions = {
            "drink_water": 5.0,
            "mana_potion": 3.0  # Save for emergencies
        }

        for action_name, base_score in actions.items():
            if action_name in available_actions:
                # Out of combat bonus
                if not game_state.in_combat:
                    base_score *= 1.5

                final_score = base_score * mana_need

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.6
                )

                score.add_reasoning(f"Mana management: {mana:.1f}%", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie mana management"""
        mana = context.game_state.resources.mana_percent
        combat_status = "in combat" if context.game_state.in_combat else "safe"
        return [
            f"Mana low: {mana:.1f}% < {self.mana_threshold}%",
            f"Status: {combat_status}"
        ]


# ===============================
# DEFENSIVE & ESCAPE RULES
# ===============================

class RunAwayRule(BaseRule):
    """Reguła ucieczki - gdy sytuacja beznadziejna"""

    def __init__(self, hp_threshold: float = 20.0):
        super().__init__(
            name="Run Away",
            category=RuleCategory.EMERGENCY,
            priority=Priority.EMERGENCY,
            weight=8.0
        )

        self.hp_threshold = hp_threshold

        # Conditions for running away
        self.add_condition(
            "very_low_health",
            create_health_condition(hp_threshold, "less_than"),
            weight=2.0,
            required=True,
            description=f"Health below {hp_threshold}%"
        )

        self.add_condition(
            "in_combat",
            create_combat_condition(True),
            weight=1.0,
            required=True,
            description="Currently in combat"
        )

        self.add_suggested_action("run_away")
        self.add_suggested_action("psychic_scream")  # Fear to create distance
        self.add_suggested_action("blink")  # Mage escape

        self.description = f"Escape when health below {hp_threshold}% in combat"
        self.rule_cooldown = 10.0  # Don't spam run attempts

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki ucieczki"""
        game_state = context.game_state

        # Must be in danger and in combat
        if not game_state.in_combat:
            return False

        if game_state.resources.health_percent >= self.hp_threshold:
            return False

        # Don't run if we have good healing options available
        if (game_state.resources.mana_percent > 50.0 and
                "health_potion" not in context.available_actions):
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla escape actions"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        hp = game_state.resources.health_percent

        # Panic level increases as health decreases
        panic_level = (self.hp_threshold - hp) / self.hp_threshold
        panic_level = max(0.5, min(2.0, panic_level))

        escape_actions = {
            "run_away": 8.0,
            "psychic_scream": 7.0,  # Fear enemies
            "blink": 6.0  # Teleport away
        }

        for action_name, base_score in escape_actions.items():
            if action_name in available_actions:
                final_score = base_score * panic_level

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.9
                )

                score.add_reasoning(f"DANGER: Health at {hp:.1f}%!", 0.0)
                score.add_reasoning(f"Panic level: {panic_level:.1f}x", 0.0)

                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie run away"""
        hp = context.game_state.resources.health_percent
        return [
            f"CRITICAL SITUATION: {hp:.1f}% health in combat",
            "RETREAT RECOMMENDED"
        ]


class DefensiveCooldownRule(BaseRule):
    """Reguła defensive cooldowns - shield wall, etc."""

    def __init__(self, hp_threshold: float = 40.0):
        super().__init__(
            name="Defensive Cooldowns",
            category=RuleCategory.SURVIVAL,
            priority=Priority.HIGH,
            weight=4.0
        )

        self.hp_threshold = hp_threshold

        # Conditions
        self.add_condition(
            "moderate_danger",
            create_health_condition(hp_threshold, "less_than"),
            weight=1.5,
            required=True,
            description=f"Health below {hp_threshold}%"
        )

        self.add_condition(
            "in_combat",
            create_combat_condition(True),
            weight=2.0,
            required=True,
            description="In combat"
        )

        # Class-specific defensive abilities
        self.add_suggested_action("shield_wall")  # Warrior
        self.add_suggested_action("ice_block")  # Mage
        self.add_suggested_action("fade")  # Priest

        self.description = f"Use defensive cooldowns when health below {hp_threshold}%"
        self.min_activation_interval = 5.0

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki defensive cooldowns"""
        game_state = context.game_state

        # Must be in combat and taking damage
        if not game_state.in_combat:
            return False

        # Must be in moderate danger
        if game_state.resources.health_percent >= self.hp_threshold:
            return False

        # Don't use if health is critical (heal instead)
        if game_state.resources.health_percent < 15.0:
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla defensive cooldowns"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        hp = game_state.resources.health_percent
        danger_level = (self.hp_threshold - hp) / self.hp_threshold
        danger_level = max(0.3, min(1.5, danger_level))

        defensive_abilities = {
            "shield_wall": 8.0,  # Very strong damage reduction
            "ice_block": 6.0,  # Immunity but can't act
            "fade": 4.0  # Threat reduction
        }

        for action_name, base_score in defensive_abilities.items():
            if action_name in available_actions:
                final_score = base_score * danger_level

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.8
                )

                score.add_reasoning(f"Defensive action needed: {hp:.1f}% health", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie defensive cooldowns"""
        hp = context.game_state.resources.health_percent
        return [
            f"Health moderate: {hp:.1f}% < {self.hp_threshold}%",
            "Defensive cooldown recommended"
        ]


# ===============================
# FACTORY FUNCTIONS
# ===============================

def create_basic_survival_rules() -> List[BaseRule]:
    """Utwórz podstawowe reguły przetrwania"""
    return [
        EmergencyHealRule(hp_threshold=15.0),
        CriticalManaRule(mana_threshold=10.0),
        RegularHealRule(hp_threshold=60.0),
        ManaManagementRule(mana_threshold=40.0),
        RunAwayRule(hp_threshold=20.0),
        DefensiveCooldownRule(hp_threshold=40.0)
    ]


def create_conservative_survival_rules() -> List[BaseRule]:
    """Utwórz conservative survival rules (wyższe thresholdy)"""
    return [
        EmergencyHealRule(hp_threshold=20.0),
        CriticalManaRule(mana_threshold=15.0),
        RegularHealRule(hp_threshold=75.0),
        ManaManagementRule(mana_threshold=50.0),
        RunAwayRule(hp_threshold=25.0),
        DefensiveCooldownRule(hp_threshold=50.0)
    ]


def create_aggressive_survival_rules() -> List[BaseRule]:
    """Utwórz aggressive survival rules (niższe thresholdy)"""
    return [
        EmergencyHealRule(hp_threshold=10.0),
        CriticalManaRule(mana_threshold=5.0),
        RegularHealRule(hp_threshold=45.0),
        ManaManagementRule(mana_threshold=30.0),
        RunAwayRule(hp_threshold=15.0),
        DefensiveCooldownRule(hp_threshold=30.0)
    ]


def create_class_specific_survival_rules(character_class: ClassType) -> List[BaseRule]:
    """Utwórz survival rules specyficzne dla klasy"""
    base_rules = create_basic_survival_rules()

    # Modify rules based on class
    for rule in base_rules:
        if character_class == ClassType.WARRIOR:
            # Warriors are tankier
            if isinstance(rule, EmergencyHealRule):
                rule.hp_threshold = 10.0  # Can go lower
            elif isinstance(rule, RegularHealRule):
                rule.hp_threshold = 50.0  # Less frequent healing

        elif character_class == ClassType.MAGE:
            # Mages are squishy
            if isinstance(rule, EmergencyHealRule):
                rule.hp_threshold = 20.0  # Heal earlier
            elif isinstance(rule, RunAwayRule):
                rule.hp_threshold = 30.0  # Run earlier

        elif character_class == ClassType.PRIEST:
            # Priests have good healing
            if isinstance(rule, ManaManagementRule):
                rule.mana_threshold = 50.0  # Keep more mana for healing

        # Add class restriction
        rule.add_class_restriction(character_class)

    return base_rules