# src/automation/profile/shaman_profile.py
"""
Enhancement Shaman Profile - kompletny profil dla Enhancement Shamana
"""

import logging
from typing import Dict, List, Optional

from ..core.data_structures import ClassType, Priority
from ..actions.base_action import BaseAction, ActionRequirements
from ..actions.survival_actions import (
    HealthPotionAction, ManaPotionAction, DrinkAction, EatFoodAction
)
from ..rules.base_rule import BaseRule, RuleCategory
from ..rules.survival_rules import EmergencyHealRule, RegularHealRule, ManaManagementRule
from ..rules.combat_rules import TargetAcquisitionRule, BasicAttackRule, ExecuteRule
from .base_profile import BaseProfile, ProfileSettings, PlayStyle


# ===============================
# ENHANCEMENT SHAMAN ACTIONS
# ===============================

class ShamanStormstrikeAction(BaseAction):
    """Stormstrike - główny atak Enhancement Shamana"""

    def __init__(self, key_binding: str = "1"):
        requirements = ActionRequirements(
            required_class=ClassType.SHAMAN,
            requires_target=True,
            mana_cost=30.0,
            max_range=5.0,
            global_cooldown=True
        )

        super().__init__("Stormstrike", "combat", Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.damage = 180.0
        self.nature_vulnerability_duration = 12.0
        self.description = f"Instantly strike for {self.damage} damage and make target vulnerable to nature spells"

    def get_cooldown_duration(self) -> float:
        return 10.0  # Stormstrike has 10s cooldown

    def estimate_effectiveness(self, game_state) -> float:
        """Stormstrike effectiveness - very high for Enhancement"""
        if not game_state.target.exists:
            return 0.0

        target_hp = game_state.target.hp_percent
        mana_percent = game_state.resources.mana_percent

        # High effectiveness, especially with mana available
        base_effectiveness = 0.9

        # Mana efficiency
        mana_factor = min(1.0, mana_percent / 100.0)

        # Target priority - good on all HP ranges
        target_factor = 1.0
        if target_hp < 30.0:
            target_factor = 1.2  # Slightly better on low HP

        return base_effectiveness * mana_factor * target_factor

    def execute_internal(self, game_state, **kwargs):
        """Execute Stormstrike"""
        import time
        start_time = time.time()

        try:
            logging.info("Executing Stormstrike")

            # Simulate critical hit chance
            import random
            actual_damage = self.damage
            if random.random() < 0.25:  # 25% crit chance
                actual_damage *= 2.0
                logging.info(f"Critical Stormstrike! {actual_damage} damage")

            from ..core.data_structures import ActionResult
            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                damage_dealt=actual_damage,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            from ..core.data_structures import ActionResult
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class ShamanLightningBoltAction(BaseAction):
    """Lightning Bolt - ranged spell"""

    def __init__(self, key_binding: str = "2"):
        requirements = ActionRequirements(
            required_class=ClassType.SHAMAN,
            requires_target=True,
            mana_cost=45.0,
            max_range=30.0,
            can_use_while_moving=False,
            global_cooldown=True
        )

        super().__init__("Lightning Bolt", "combat", Priority.MEDIUM, requirements)

        self.key_binding = key_binding
        self.damage = 200.0
        self.cast_time = 2.5
        self.description = f"Hurls a lightning bolt for {self.damage} nature damage"

    def get_cooldown_duration(self) -> float:
        return 0.0

    def estimate_effectiveness(self, game_state) -> float:
        """Lightning Bolt effectiveness"""
        if not game_state.target.exists:
            return 0.0

        target = game_state.target
        mana_percent = game_state.resources.mana_percent

        # Good at range, less effective in melee
        range_factor = 1.0
        if target.distance <= 8.0:
            range_factor = 0.6  # Prefer melee attacks when close
        elif target.distance >= 15.0:
            range_factor = 1.2  # Excellent at range

        # Less effective while moving
        mobility_factor = 0.3 if game_state.is_moving else 1.0

        # Mana efficiency
        mana_factor = min(1.0, mana_percent / 100.0)

        return 0.7 * range_factor * mobility_factor * mana_factor

    def execute_internal(self, game_state, **kwargs):
        """Execute Lightning Bolt"""
        import time
        start_time = time.time()

        try:
            logging.info(f"Casting Lightning Bolt ({self.cast_time}s cast)")

            # Simulate cast time
            actual_damage = self.damage

            from ..core.data_structures import ActionResult
            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                damage_dealt=actual_damage,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            from ..core.data_structures import ActionResult
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class ShamanEarthShockAction(BaseAction):
    """Earth Shock - instant nature damage + interrupt"""

    def __init__(self, key_binding: str = "3"):
        requirements = ActionRequirements(
            required_class=ClassType.SHAMAN,
            requires_target=True,
            mana_cost=60.0,
            max_range=20.0,
            global_cooldown=True
        )

        super().__init__("Earth Shock", "combat", Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.damage = 160.0
        self.interrupt_duration = 2.0
        self.description = f"Instantly deals {self.damage} nature damage and interrupts spellcasting"

    def get_cooldown_duration(self) -> float:
        return 6.0

    def estimate_effectiveness(self, game_state) -> float:
        """Earth Shock effectiveness"""
        if not game_state.target.exists:
            return 0.0

        base_effectiveness = 0.8
        mana_factor = min(1.0, game_state.resources.mana_percent / 100.0)

        # Very high effectiveness if target is casting
        if game_state.target.is_casting:
            base_effectiveness = 1.5  # Interrupt is very valuable

        return base_effectiveness * mana_factor

    def execute_internal(self, game_state, **kwargs):
        """Execute Earth Shock"""
        import time
        start_time = time.time()

        try:
            interrupt_bonus = " + INTERRUPT" if game_state.target.is_casting else ""
            logging.info(f"Earth Shock{interrupt_bonus}")

            from ..core.data_structures import ActionResult
            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                damage_dealt=self.damage,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            from ..core.data_structures import ActionResult
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class ShamanFlameShockAction(BaseAction):
    """Flame Shock - DoT spell"""

    def __init__(self, key_binding: str = "4"):
        requirements = ActionRequirements(
            required_class=ClassType.SHAMAN,
            requires_target=True,
            mana_cost=50.0,
            max_range=20.0,
            global_cooldown=True
        )

        super().__init__("Flame Shock", "combat", Priority.MEDIUM, requirements)

        self.key_binding = key_binding
        self.initial_damage = 120.0
        self.dot_damage = 40.0
        self.dot_duration = 12.0
        self.description = f"Deals {self.initial_damage} fire damage + {self.dot_damage} DoT over {self.dot_duration}s"

    def get_cooldown_duration(self) -> float:
        return 6.0

    def estimate_effectiveness(self, game_state) -> float:
        """Flame Shock effectiveness"""
        if not game_state.target.exists:
            return 0.0

        target_hp = game_state.target.hp_percent
        mana_percent = game_state.resources.mana_percent

        # Better on high HP targets (full DoT value)
        target_factor = 1.0
        if target_hp > 50.0:
            target_factor = 1.2  # DoT has time to tick
        elif target_hp < 20.0:
            target_factor = 0.6  # May not get full DoT value

        # Check if target already has Flame Shock (avoid overwriting)
        # In real implementation, check for debuff

        return 0.75 * target_factor * min(1.0, mana_percent / 100.0)

    def execute_internal(self, game_state, **kwargs):
        """Execute Flame Shock"""
        import time
        start_time = time.time()

        try:
            logging.info("Applied Flame Shock DoT")

            total_damage = self.initial_damage + (self.dot_damage * (self.dot_duration / 3))

            from ..core.data_structures import ActionResult
            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                damage_dealt=total_damage,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            from ..core.data_structures import ActionResult
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class ShamanHealingWaveAction(BaseAction):
    """Healing Wave - powerful heal"""

    def __init__(self, key_binding: str = "F1"):
        requirements = ActionRequirements(
            required_class=ClassType.SHAMAN,
            mana_cost=80.0,
            can_use_while_moving=False,
            global_cooldown=True
        )

        super().__init__("Healing Wave", "survival", Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.healing = 350.0
        self.cast_time = 3.0
        self.description = f"Heals for {self.healing} HP over {self.cast_time}s"

    def get_cooldown_duration(self) -> float:
        return 0.0

    def estimate_effectiveness(self, game_state) -> float:
        """Healing Wave effectiveness"""
        hp_percent = game_state.resources.health_percent
        mana_percent = game_state.resources.mana_percent

        # More effective when health is low
        health_factor = 1.0 - (hp_percent / 100.0)

        # Mana efficiency
        mana_factor = min(1.0, mana_percent / 100.0)

        # Less effective in combat (long cast time)
        combat_factor = 0.4 if game_state.in_combat else 1.0

        # Emergency factor
        emergency_factor = 1.0
        if hp_percent < 30.0:
            emergency_factor = 1.5

        return health_factor * mana_factor * combat_factor * emergency_factor

    def execute_internal(self, game_state, **kwargs):
        """Execute Healing Wave"""
        import time
        start_time = time.time()

        try:
            logging.info(f"Casting Healing Wave ({self.cast_time}s)")

            from ..core.data_structures import ActionResult
            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                healing_done=self.healing,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            from ..core.data_structures import ActionResult
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class ShamanLesserHealingWaveAction(BaseAction):
    """Lesser Healing Wave - fast heal"""

    def __init__(self, key_binding: str = "F2"):
        requirements = ActionRequirements(
            required_class=ClassType.SHAMAN,
            mana_cost=50.0,
            can_use_while_moving=False,
            global_cooldown=True
        )

        super().__init__("Lesser Healing Wave", "survival", Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.healing = 200.0
        self.cast_time = 1.5
        self.description = f"Quickly heals for {self.healing} HP"

    def get_cooldown_duration(self) -> float:
        return 0.0

    def estimate_effectiveness(self, game_state) -> float:
        """Lesser Healing Wave effectiveness"""
        hp_percent = game_state.resources.health_percent
        mana_percent = game_state.resources.mana_percent

        # Good for quick heals, especially in combat
        health_factor = 1.0 - (hp_percent / 100.0)
        mana_factor = min(1.0, mana_percent / 100.0)

        # Better in combat than Healing Wave
        combat_factor = 0.8 if game_state.in_combat else 0.9

        return health_factor * mana_factor * combat_factor

    def execute_internal(self, game_state, **kwargs):
        """Execute Lesser Healing Wave"""
        import time
        start_time = time.time()

        try:
            logging.info(f"Quick heal - Lesser Healing Wave ({self.cast_time}s)")

            from ..core.data_structures import ActionResult
            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                healing_done=self.healing,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            from ..core.data_structures import ActionResult
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class ShamanWindfuryWeaponAction(BaseAction):
    """Windfury Weapon - weapon enhancement"""

    def __init__(self, key_binding: str = "5"):
        requirements = ActionRequirements(
            required_class=ClassType.SHAMAN,
            mana_cost=30.0,
            requires_out_of_combat=True,
            global_cooldown=True
        )

        super().__init__("Windfury Weapon", "buff", Priority.MEDIUM, requirements)

        self.key_binding = key_binding
        self.duration = 1800.0  # 30 minutes
        self.proc_chance = 0.2  # 20% chance for extra attacks
        self.description = f"Enhances weapon with wind, giving chance for extra attacks for {self.duration / 60}min"

    def get_cooldown_duration(self) -> float:
        return 0.0

    def estimate_effectiveness(self, game_state) -> float:
        """Windfury effectiveness"""
        # Check if we already have weapon enhancement
        if game_state.has_buff("Windfury Weapon"):
            return 0.0

        # Only out of combat
        if game_state.in_combat:
            return 0.0

        # High priority if no weapon buff
        mana_factor = min(1.0, game_state.resources.mana_percent / 100.0)
        return 0.9 * mana_factor

    def execute_internal(self, game_state, **kwargs):
        """Execute Windfury Weapon"""
        import time
        start_time = time.time()

        try:
            logging.info("Enhancing weapon with Windfury")

            from ..core.data_structures import ActionResult
            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            from ..core.data_structures import ActionResult
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


# ===============================
# ENHANCEMENT SHAMAN RULES
# ===============================

class ShamanWeaponBuffRule(BaseRule):
    """Reguła utrzymywania buffów na broni"""

    def __init__(self):
        super().__init__(
            name="Weapon Buff Maintenance",
            category=RuleCategory.EFFICIENCY,
            priority=Priority.MEDIUM,
            weight=3.0
        )

        from ..rules.base_rule import create_combat_condition
        self.add_condition(
            "out_of_combat",
            create_combat_condition(False),
            weight=2.0,
            required=True,
            description="Out of combat for buffing"
        )

        self.add_suggested_action("windfury_weapon")

        self.description = "Maintain weapon enhancements"
        self.min_activation_interval = 10.0

    def evaluate_conditions(self, context) -> bool:
        """Oceń warunki weapon buff"""
        game_state = context.game_state

        # Only out of combat
        if game_state.in_combat:
            return False

        # Check if we have weapon buff
        if game_state.has_buff("Windfury Weapon"):
            return False

        # Need mana
        if game_state.resources.mana_percent < 20.0:
            return False

        return True

    def calculate_action_scores(self, context) -> List:
        """Oblicz oceny dla weapon buffs"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        if "windfury_weapon" in available_actions:
            # High priority for weapon enhancement
            from ..core.decision_maker import DecisionScore
            score = DecisionScore(
                action_name="windfury_weapon",
                score=8.0,
                priority=self.priority,
                confidence=0.9
            )

            score.add_reasoning("Missing weapon enhancement", 0.0)
            scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context) -> List[str]:
        """Uzasadnienie weapon buff"""
        return ["Weapon needs enhancement buff"]


class ShamanShockPriorityRule(BaseRule):
    """Reguła priorytetów dla Shock spells"""

    def __init__(self):
        super().__init__(
            name="Shock Priority",
            category=RuleCategory.COMBAT,
            priority=Priority.HIGH,
            weight=4.0
        )

        from ..rules.base_rule import create_target_condition
        self.add_condition(
            "has_target",
            create_target_condition(True),
            weight=2.0,
            required=True,
            description="Has valid target"
        )

        self.add_suggested_action("earth_shock")
        self.add_suggested_action("flame_shock")

        self.description = "Smart Shock spell usage"
        self.min_activation_interval = 0.5

    def evaluate_conditions(self, context) -> bool:
        """Oceń warunki shock priority"""
        game_state = context.game_state

        # Must have target
        if not game_state.target.exists:
            return False

        # Must have mana
        if game_state.resources.mana_percent < 25.0:
            return False

        return True

    def calculate_action_scores(self, context) -> List:
        """Oblicz oceny dla shock spells"""
        scores = []
        game_state = context.game_state
        available_actions = context.available_actions

        target_hp = game_state.target.hp_percent

        # Earth Shock priorities
        if "earth_shock" in available_actions:
            earth_shock_score = 6.0

            # Very high priority if target is casting
            if game_state.target.is_casting:
                earth_shock_score = 12.0

            from ..core.decision_maker import DecisionScore
            score = DecisionScore(
                action_name="earth_shock",
                score=earth_shock_score,
                priority=self.priority,
                confidence=0.85
            )

            if game_state.target.is_casting:
                score.add_reasoning("INTERRUPT TARGET CASTING", 0.0)
            else:
                score.add_reasoning("Instant damage", 0.0)

            scores.append(score)

        # Flame Shock priorities
        if "flame_shock" in available_actions:
            flame_shock_score = 5.0

            # Better on high HP targets (DoT value)
            if target_hp > 60.0:
                flame_shock_score = 7.0
            elif target_hp < 25.0:
                flame_shock_score = 3.0  # DoT may not finish

            from ..core.decision_maker import DecisionScore
            score = DecisionScore(
                action_name="flame_shock",
                score=flame_shock_score,
                priority=self.priority,
                confidence=0.75
            )

            score.add_reasoning(f"DoT on {target_hp:.1f}% HP target", 0.0)
            scores.append(score)

        return scores

    def get_rule_specific_reasoning(self, context) -> List[str]:
        """Uzasadnienie shock priority"""
        game_state = context.game_state
        if game_state.target.is_casting:
            return ["Target casting - interrupt with Earth Shock"]
        else:
            return ["Choose appropriate Shock spell"]


# ===============================
# MAIN ENHANCEMENT SHAMAN PROFILE
# ===============================

class EnhancementShamanProfile(BaseProfile):
    """Kompletny profil Enhancement Shamana"""

    def __init__(self, play_style: PlayStyle = PlayStyle.BALANCED):
        settings = ProfileSettings(
            play_style=play_style,
            engage_distance=20.0,  # Can start with ranged
            disengage_threshold=20.0,  # Shamans are somewhat squishy
            rest_threshold=50.0,
            mana_conservation=True,  # Important for shaman
            health_potion_threshold=25.0,
            mana_potion_threshold=20.0,
            emergency_actions=True
        )

        super().__init__("Enhancement Shaman", ClassType.SHAMAN, settings)

        self.description = "Enhancement Shaman - Melee DPS with elemental magic support"
        self.author = "WoW Automation"
        self.version = "1.0.0"
        self.min_level = 10
        self.recommended_zones = ["Barrens", "Stonetalon Mountains", "Thousand Needles"]

    def setup_actions(self):
        """Skonfiguruj akcje Enhancement Shamana"""
        # Combat actions
        self.add_action("stormstrike", ShamanStormstrikeAction("1"), "1")
        self.add_action("lightning_bolt", ShamanLightningBoltAction("2"), "2")
        self.add_action("earth_shock", ShamanEarthShockAction("3"), "3")
        self.add_action("flame_shock", ShamanFlameShockAction("4"), "4")

        # Weapon enhancement
        self.add_action("windfury_weapon", ShamanWindfuryWeaponAction("5"), "5")

        # Healing
        self.add_action("healing_wave", ShamanHealingWaveAction("F1"), "F1")
        self.add_action("lesser_healing_wave", ShamanLesserHealingWaveAction("F2"), "F2")

        # Consumables
        self.add_action("health_potion", HealthPotionAction("F3"), "F3")
        self.add_action("mana_potion", ManaPotionAction("F4"), "F4")
        self.add_action("drink_water", DrinkAction("F5"), "F5")
        self.add_action("eat_food", EatFoodAction("F6"), "F6")

        logging.info("Enhancement Shaman actions configured")

    def setup_rules(self):
        """Skonfiguruj reguły Enhancement Shamana"""
        # Survival rules - modified for shaman
        self.add_rule(EmergencyHealRule(hp_threshold=18.0,
                                        emergency_actions=["health_potion", "lesser_healing_wave", "healing_wave"]))
        self.add_rule(RegularHealRule(hp_threshold=55.0,
                                      heal_actions=["lesser_healing_wave", "healing_wave", "eat_food"]))
        self.add_rule(ManaManagementRule(mana_threshold=35.0))  # Higher threshold for casters

        # Combat rules
        self.add_rule(TargetAcquisitionRule())

        # Shaman-specific rules
        self.add_rule(ShamanWeaponBuffRule())
        self.add_rule(ShamanShockPriorityRule())

        # Basic attack rule for Enhancement
        basic_attack = BasicAttackRule(preferred_attacks=["stormstrike", "earth_shock", "lightning_bolt"])
        self.add_rule(basic_attack)

        logging.info("Enhancement Shaman rules configured")

    def setup_key_mappings(self):
        """Konfiguracja klawiszy jest już zrobiona w add_action"""
        pass

    def get_rotation_priority(self) -> List[str]:
        """Priorytet rotacji Enhancement Shamana"""
        return [
            # Weapon maintenance (highest priority out of combat)
            "windfury_weapon",

            # Emergency survival
            "health_potion",
            "lesser_healing_wave",

            # Combat rotation
            "stormstrike",  # Main attack when available
            "earth_shock",  # Interrupt or instant damage
            "flame_shock",  # DoT on fresh targets
            "lightning_bolt",  # Filler/ranged

            # Resource management
            "mana_potion",
            "drink_water",
            "healing_wave",  # Out of combat healing
            "eat_food"
        ]


# ===============================
# FACTORY FUNCTION
# ===============================

def create_enhancement_shaman_profile(play_style: PlayStyle = PlayStyle.BALANCED) -> EnhancementShamanProfile:
    """Utwórz profil Enhancement Shamana"""
    profile = EnhancementShamanProfile(play_style)

    if profile.initialize():
        logging.info("Enhancement Shaman profile created successfully")
        return profile
    else:
        logging.error("Failed to initialize Enhancement Shaman profile")
        raise Exception("Profile initialization failed")


# Convenience function
def create_enh_shaman_aggressive() -> EnhancementShamanProfile:
    """Utwórz agresywny profil Enhancement Shamana"""
    return create_enhancement_shaman_profile(PlayStyle.AGGRESSIVE)


def create_enh_shaman_conservative() -> EnhancementShamanProfile:
    """Utwórz conservative profil Enhancement Shamana"""
    return create_enhancement_shaman_profile(PlayStyle.CONSERVATIVE)