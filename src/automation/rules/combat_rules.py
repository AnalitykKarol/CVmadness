# src/automation/rules/combat_rules.py
"""
Reguły walki - ataki, targetting, rotacje bojowe
"""

import time
import logging
from typing import List, Dict, Any

from ..core.data_structures import GameState, Priority, ClassType
from ..core.decision_maker import DecisionScore, DecisionContext
from .base_rule import (
    BaseRule, RuleCategory, create_health_condition, create_mana_condition,
    create_combat_condition, create_target_condition, create_target_health_condition
)


# ===============================
# TARGET ACQUISITION RULES
# ===============================

class TargetAcquisitionRule(BaseRule):
    """Reguła znajdowania i atakowania celów"""

    def __init__(self):
        super().__init__(
            name="Target Acquisition",
            category=RuleCategory.COMBAT,
            priority=Priority.HIGH,
            weight=3.0
        )

        # Conditions
        self.add_condition(
            "no_target",
            create_target_condition(False),
            weight=2.0,
            required=True,
            description="No current target"
        )

        self.add_condition(
            "healthy_enough",
            create_health_condition(30.0, "greater_than"),
            weight=1.0,
            required=True,
            description="Health > 30% (safe to engage)"
        )

        self.add_condition(
            "enough_mana",
            create_mana_condition(20.0, "greater_than"),
            weight=1.0,
            required=False,
            description="Enough mana for combat"
        )

        self.add_suggested_action("target_nearest_enemy")
        self.add_suggested_action("charge")  # Gap closer + target

        self.description = "Find and engage new targets when safe"
        self.min_activation_interval = 2.0

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki target acquisition"""
        game_state = context.game_state

        # Must not have target
        if game_state.target.exists:
            return False

        # Must be healthy enough to fight
        if game_state.resources.health_percent < 30.0:
            return False

        # Don't engage if very low mana
        if game_state.resources.mana_percent < 10.0:
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla target acquisition"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        hp = game_state.resources.health_percent
        mana = game_state.resources.mana_percent

        # Readiness factor (higher when more prepared)
        readiness = (hp / 100.0) * 0.7 + (mana / 100.0) * 0.3
        readiness = max(0.2, min(1.0, readiness))

        targeting_actions = {
            "target_nearest_enemy": 5.0,
            "charge": 6.0  # Aggressive engagement
        }

        for action_name, base_score in targeting_actions.items():
            if action_name in available_actions:
                final_score = base_score * readiness

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.7
                )

                score.add_reasoning(f"Ready to engage: {readiness:.1f}", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie target acquisition"""
        hp = context.game_state.resources.health_percent
        mana = context.game_state.resources.mana_percent
        return [
            "No target, looking for enemies",
            f"Combat readiness: HP {hp:.1f}%, Mana {mana:.1f}%"
        ]


# ===============================
# BASIC COMBAT RULES
# ===============================

class BasicAttackRule(BaseRule):
    """Reguła podstawowych ataków"""

    def __init__(self, preferred_attacks: List[str] = None):
        super().__init__(
            name="Basic Attack",
            category=RuleCategory.COMBAT,
            priority=Priority.MEDIUM,
            weight=2.0
        )

        self.preferred_attacks = preferred_attacks or [
            "heroic_strike", "firebolt", "smite", "auto_attack"
        ]

        # Conditions
        self.add_condition(
            "has_target",
            create_target_condition(True),
            weight=2.0,
            required=True,
            description="Has valid target"
        )

        self.add_condition(
            "target_alive",
            create_target_health_condition(0.0, "greater_than"),
            weight=2.0,
            required=True,
            description="Target is alive"
        )

        self.add_condition(
            "healthy_enough",
            create_health_condition(25.0, "greater_than"),
            weight=1.0,
            required=True,
            description="Healthy enough to attack"
        )

        for attack in self.preferred_attacks:
            self.add_suggested_action(attack)

        self.description = "Basic combat attacks when target available"
        self.min_activation_interval = 0.5

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki basic attack"""
        game_state = context.game_state

        # Must have valid target
        if not game_state.target.exists or game_state.target.hp_percent <= 0:
            return False

        # Don't attack if health too low (heal instead)
        if game_state.resources.health_percent < 25.0:
            return False

        # Don't attack if no mana for casters
        if (context.character_class in [ClassType.MAGE, ClassType.PRIEST] and
                game_state.resources.mana_percent < 15.0):
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla basic attacks"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        target_hp = game_state.target.hp_percent
        our_hp = game_state.resources.health_percent
        our_mana = game_state.resources.mana_percent

        # Aggression factor (higher when we're healthy)
        aggression = (our_hp / 100.0) * 0.8 + (our_mana / 100.0) * 0.2
        aggression = max(0.3, min(1.0, aggression))

        # Target priority (prefer lower HP targets)
        target_priority = 1.0 + (1.0 - target_hp / 100.0) * 0.5

        # Class-specific attack preferences
        attack_preferences = self._get_class_attack_preferences(context.character_class)

        for action_name in self.preferred_attacks:
            if action_name in available_actions:
                base_score = attack_preferences.get(action_name, 3.0)

                # Apply modifiers
                final_score = base_score * aggression * target_priority

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.6
                )

                score.add_reasoning(f"Attacking target: {target_hp:.1f}% HP", 0.0)
                scores.append(score)

        return scores

    def _get_class_attack_preferences(self, character_class: ClassType) -> Dict[str, float]:
        """Pobierz preferencje ataków dla klasy"""
        preferences = {
            ClassType.WARRIOR: {
                "heroic_strike": 6.0,
                "execute": 4.0,  # Will be scored higher by execute rule
                "whirlwind": 3.0,
                "auto_attack": 2.0
            },
            ClassType.MAGE: {
                "firebolt": 5.0,
                "frostbolt": 4.0,
                "fireball": 6.0,
                "auto_attack": 1.0
            },
            ClassType.PRIEST: {
                "smite": 5.0,
                "holy_fire": 4.0,
                "auto_attack": 2.0
            }
        }

        return preferences.get(character_class, {"auto_attack": 3.0})

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie basic attack"""
        target_hp = context.game_state.target.hp_percent
        return [f"Basic combat vs target ({target_hp:.1f}% HP)"]


class ExecuteRule(BaseRule):
    """Reguła execute - wysokie damage na low HP enemies"""

    def __init__(self, hp_threshold: float = 20.0):
        super().__init__(
            name="Execute",
            category=RuleCategory.COMBAT,
            priority=Priority.HIGH,
            weight=5.0
        )

        self.hp_threshold = hp_threshold

        # Conditions
        self.add_condition(
            "has_target",
            create_target_condition(True),
            weight=2.0,
            required=True,
            description="Has target"
        )

        self.add_condition(
            "target_low_hp",
            create_target_health_condition(hp_threshold, "less_than"),
            weight=3.0,
            required=True,
            description=f"Target below {hp_threshold}% HP"
        )

        self.add_suggested_action("execute")
        self.add_suggested_action("fireball")  # High damage spell

        self.description = f"High damage attacks on targets below {hp_threshold}% HP"
        self.min_activation_interval = 0.2

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki execute"""
        game_state = context.game_state

        # Must have target in execute range
        if (not game_state.target.exists or
                game_state.target.hp_percent >= self.hp_threshold):
            return False

        # Must have enough resources
        if game_state.resources.health_percent < 20.0:
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla execute actions"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        target_hp = game_state.target.hp_percent

        # Execute bonus (higher score for lower HP)
        execute_bonus = (self.hp_threshold - target_hp) / self.hp_threshold
        execute_bonus = 1.0 + execute_bonus * 2.0  # Up to 3x multiplier

        execute_actions = {
            "execute": 8.0,  # Warrior execute
            "fireball": 6.0  # High damage spell
        }

        for action_name, base_score in execute_actions.items():
            if action_name in available_actions:
                final_score = base_score * execute_bonus

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.9
                )

                score.add_reasoning(f"EXECUTE RANGE: Target {target_hp:.1f}% HP", 0.0)
                score.add_reasoning(f"Execute bonus: {execute_bonus:.1f}x", 0.0)

                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie execute"""
        target_hp = context.game_state.target.hp_percent
        return [
            f"TARGET IN EXECUTE RANGE: {target_hp:.1f}%",
            "High damage finisher recommended"
        ]


# ===============================
# ADVANCED COMBAT RULES
# ===============================

class OpenerRule(BaseRule):
    """Reguła opener - początkowa sekwencja ataków"""

    def __init__(self):
        super().__init__(
            name="Combat Opener",
            category=RuleCategory.COMBAT,
            priority=Priority.HIGH,
            weight=4.0
        )

        # Conditions for opener
        self.add_condition(
            "has_target",
            create_target_condition(True),
            weight=2.0,
            required=True,
            description="Has target"
        )

        self.add_condition(
            "target_full_hp",
            create_target_health_condition(90.0, "greater_than"),
            weight=1.5,
            required=True,
            description="Target near full HP (fresh fight)"
        )

        self.add_condition(
            "out_of_combat",
            create_combat_condition(False),
            weight=1.0,
            required=False,
            description="Not yet in combat"
        )

        self.add_suggested_action("charge")
        self.add_suggested_action("fireball")  # Big opening spell
        self.add_suggested_action("holy_fire")  # DoT opener

        self.description = "Opening moves for fresh combat"
        self.rule_cooldown = 10.0  # Don't spam openers

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki opener"""
        game_state = context.game_state

        # Must be starting fresh fight
        if (not game_state.target.exists or
                game_state.target.hp_percent < 90.0):
            return False

        # Must be healthy enough for aggressive opener
        if game_state.resources.health_percent < 50.0:
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla opener actions"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        # Opener enthusiasm (higher when well prepared)
        enthusiasm = ((game_state.resources.health_percent / 100.0) * 0.6 +
                      (game_state.resources.mana_percent / 100.0) * 0.4)

        # Bonus if out of combat (can prep)
        if not game_state.in_combat:
            enthusiasm *= 1.3

        opener_actions = {
            "charge": 7.0,  # Warrior gap closer
            "fireball": 6.0,  # Big damage opener
            "holy_fire": 5.0  # DoT + damage
        }

        for action_name, base_score in opener_actions.items():
            if action_name in available_actions:
                final_score = base_score * enthusiasm

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.8
                )

                score.add_reasoning("Combat opener sequence", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie opener"""
        return ["Fresh target - opening attack sequence"]


class AoECombatRule(BaseRule):
    """Reguła AoE combat - wiele celów"""

    def __init__(self):
        super().__init__(
            name="AoE Combat",
            category=RuleCategory.COMBAT,
            priority=Priority.HIGH,
            weight=3.0
        )

        # Note: In real implementation, we'd need vision system to detect multiple enemies
        # For now, we'll simulate this condition

        self.add_condition(
            "has_target",
            create_target_condition(True),
            weight=1.0,
            required=True,
            description="Has primary target"
        )

        self.add_suggested_action("whirlwind")  # Warrior AoE
        self.add_suggested_action("blizzard")  # Mage AoE
        self.add_suggested_action("consecration")  # Paladin AoE

        self.description = "AoE attacks when facing multiple enemies"
        self.min_activation_interval = 3.0

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki AoE combat"""
        game_state = context.game_state

        # Must have target
        if not game_state.target.exists:
            return False

        # In real implementation, check for multiple nearby enemies
        # For now, simulate this randomly or based on some logic

        # Placeholder: assume AoE is useful sometimes
        return True  # This would be replaced with actual multi-enemy detection

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla AoE actions"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        # In real implementation, count nearby enemies
        enemy_count = 2  # Placeholder

        # AoE effectiveness increases with enemy count
        aoe_effectiveness = min(2.0, enemy_count / 2.0)

        aoe_actions = {
            "whirlwind": 5.0,
            "blizzard": 6.0,
            "consecration": 4.0
        }

        for action_name, base_score in aoe_actions.items():
            if action_name in available_actions:
                final_score = base_score * aoe_effectiveness

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.7
                )

                score.add_reasoning(f"AoE vs {enemy_count} enemies", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie AoE combat"""
        return ["Multiple enemies detected - AoE recommended"]


# ===============================
# UTILITY COMBAT RULES
# ===============================

class InterruptRule(BaseRule):
    """Reguła przerwania castów przeciwnika"""

    def __init__(self):
        super().__init__(
            name="Interrupt",
            category=RuleCategory.COMBAT,
            priority=Priority.HIGH,
            weight=6.0  # High priority
        )

        # Conditions
        self.add_condition(
            "has_target",
            create_target_condition(True),
            weight=2.0,
            required=True,
            description="Has target"
        )

        # In real implementation, we'd detect target casting
        # This would need vision system integration

        self.add_suggested_action("kick")  # Rogue interrupt
        self.add_suggested_action("pummel")  # Warrior interrupt
        self.add_suggested_action("counterspell")  # Mage interrupt

        self.description = "Interrupt enemy spellcasting"
        self.min_activation_interval = 1.0

    def evaluate_conditions(self, context: DecisionContext) -> bool:
        """Oceń warunki interrupt"""
        game_state = context.game_state

        # Must have target that's casting
        if not game_state.target.exists:
            return False

        # Check if target is casting (from game state)
        if not game_state.target.is_casting:
            return False

        return True

    def calculate_action_scores(self, context: DecisionContext) -> List[DecisionScore]:
        """Oblicz oceny dla interrupt actions"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        # Interrupt is always high priority when target casting
        urgency = 2.0  # High urgency for interrupts

        interrupt_actions = {
            "kick": 8.0,
            "pummel": 8.0,
            "counterspell": 8.0
        }

        for action_name, base_score in interrupt_actions.items():
            if action_name in available_actions:
                final_score = base_score * urgency

                score = DecisionScore(
                    action_name=action_name,
                    score=final_score,
                    priority=self.priority,
                    confidence=0.95
                )

                score.add_reasoning("INTERRUPT TARGET CASTING", 0.0)
                scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context: DecisionContext) -> List[str]:
        """Uzasadnienie interrupt"""
        cast_name = context.game_state.target.cast_name
        return [
            f"Target casting: {cast_name}",
            "INTERRUPT IMMEDIATELY"
        ]


# ===============================
# FACTORY FUNCTIONS
# ===============================

def create_basic_combat_rules() -> List[BaseRule]:
    """Utwórz podstawowe reguły walki"""
    return [
        TargetAcquisitionRule(),
        BasicAttackRule(),
        ExecuteRule(hp_threshold=20.0),
        OpenerRule(),
        AoECombatRule(),
        InterruptRule()
    ]


def create_warrior_combat_rules() -> List[BaseRule]:
    """Utwórz reguły walki dla Warrior"""
    rules = create_basic_combat_rules()

    # Customize for warrior
    for rule in rules:
        if isinstance(rule, BasicAttackRule):
            rule.preferred_attacks = ["heroic_strike", "execute", "whirlwind"]
        elif isinstance(rule, OpenerRule):
            rule.suggested_actions = ["charge"]

        rule.add_class_restriction(ClassType.WARRIOR)

    return rules


def create_mage_combat_rules() -> List[BaseRule]:
    """Utwórz reguły walki dla Mage"""
    rules = create_basic_combat_rules()

    # Customize for mage
    for rule in rules:
        if isinstance(rule, BasicAttackRule):
            rule.preferred_attacks = ["firebolt", "frostbolt", "fireball"]
        elif isinstance(rule, OpenerRule):
            rule.suggested_actions = ["fireball"]

        rule.add_class_restriction(ClassType.MAGE)

    return rules


def create_priest_combat_rules() -> List[BaseRule]:
    """Utwórz reguły walki dla Priest"""
    rules = create_basic_combat_rules()

    # Customize for priest
    for rule in rules:
        if isinstance(rule, BasicAttackRule):
            rule.preferred_attacks = ["smite", "holy_fire"]
        elif isinstance(rule, OpenerRule):
            rule.suggested_actions = ["holy_fire"]

        rule.add_class_restriction(ClassType.PRIEST)

    return rules


def create_aggressive_combat_rules() -> List[BaseRule]:
    """Utwórz agresywne reguły walki"""
    rules = create_basic_combat_rules()

    # Make more aggressive
    for rule in rules:
        if isinstance(rule, TargetAcquisitionRule):
            # Lower health threshold for engagement
            rule.conditions[1].condition_func = create_health_condition(20.0, "greater_than")
        elif isinstance(rule, BasicAttackRule):
            # Lower health threshold for attacking
            rule.conditions[2].condition_func = create_health_condition(15.0, "greater_than")
        elif isinstance(rule, ExecuteRule):
            # Higher execute threshold
            rule.hp_threshold = 25.0

    return rules


def create_defensive_combat_rules() -> List[BaseRule]:
    """Utwórz defensywne reguły walki"""
    rules = create_basic_combat_rules()

    # Make more defensive
    for rule in rules:
        if isinstance(rule, TargetAcquisitionRule):
            # Higher health threshold for engagement
            rule.conditions[1].condition_func = create_health_condition(50.0, "greater_than")
        elif isinstance(rule, BasicAttackRule):
            # Higher health threshold for attacking
            rule.conditions[2].condition_func = create_health_condition(40.0, "greater_than")

        # Reduce aggressiveness
        rule.weight *= 0.8

    return rules