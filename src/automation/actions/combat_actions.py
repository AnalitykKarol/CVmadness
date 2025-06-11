# src/automation/actions/combat_actions.py
"""
Akcje bojowe - ataki, czary ofensywne, ability bojowe
"""

import time
import logging
from typing import Dict, Optional, Any, List

from ..core.data_structures import (
    GameState, ActionResult, ActionType, Priority, ClassType
)
from .base_action import BaseAction, ActionRequirements


# ===============================
# BASE COMBAT ACTIONS
# ===============================

class MeleeAttackAction(BaseAction):
    """Bazowa klasa dla ataków wręcz"""

    def __init__(self, name: str, key_binding: str, damage: float,
                 resource_cost: float, resource_type: str = "mana",
                 cooldown: float = 0.0, priority: Priority = Priority.MEDIUM):

        requirements = ActionRequirements(
            requires_target=True,
            requires_combat=True,
            max_range=5.0,  # Melee range
            global_cooldown=True
        )

        # Set resource cost based on type
        if resource_type == "mana":
            requirements.mana_cost = resource_cost
        elif resource_type == "rage":
            requirements.rage_cost = resource_cost
        elif resource_type == "energy":
            requirements.energy_cost = resource_cost

        super().__init__(name, ActionType.COMBAT, priority, requirements)

        self.key_binding = key_binding
        self.damage = damage
        self.resource_cost = resource_cost
        self.resource_type = resource_type
        self.cooldown = cooldown
        self.description = f"Melee attack dealing {damage} damage"

    def get_cooldown_duration(self) -> float:
        return self.cooldown

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Oceń efektywność ataku melee"""
        if not game_state.target.exists:
            return 0.0

        target = game_state.target
        resources = game_state.resources

        # Target health factor - more effective on lower HP enemies
        target_hp_factor = 1.0
        if target.hp_percent < 20.0:
            target_hp_factor = 1.3  # Execute range
        elif target.hp_percent < 50.0:
            target_hp_factor = 1.1

        # Resource availability
        resource_factor = 1.0
        if self.resource_type == "mana":
            resource_factor = min(1.0, resources.mana_percent / 100.0)
        elif self.resource_type == "rage":
            resource_factor = min(1.0, resources.rage_percent / 100.0)
        elif self.resource_type == "energy":
            resource_factor = min(1.0, resources.energy_percent / 100.0)

        # Damage per resource efficiency
        efficiency = self.damage / max(1.0, self.resource_cost)
        efficiency_factor = min(1.0, efficiency / 10.0)

        # Range factor - prefer if in melee range
        range_factor = 1.0 if target.distance <= 5.0 else 0.5

        return target_hp_factor * resource_factor * efficiency_factor * range_factor

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Wykonaj atak melee"""
        start_time = time.time()

        try:
            # Simulate attack execution
            logging.info(f"Executing {self.name} on target")

            # Calculate actual damage (could vary based on crits, resists, etc.)
            actual_damage = self.damage

            # Simulate critical hits (15% chance)
            import random
            if random.random() < 0.15:
                actual_damage *= 2.0
                logging.info(f"Critical hit! {actual_damage} damage")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                damage_dealt=actual_damage,
                mana_cost=self.requirements.mana_cost,
                rage_cost=self.requirements.rage_cost,
                energy_cost=self.requirements.energy_cost
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class RangedAttackAction(BaseAction):
    """Bazowa klasa dla ataków dystansowych"""

    def __init__(self, name: str, key_binding: str, damage: float,
                 mana_cost: float, cast_time: float, max_range: float = 30.0,
                 cooldown: float = 0.0, priority: Priority = Priority.MEDIUM):

        requirements = ActionRequirements(
            requires_target=True,
            requires_combat=True,
            mana_cost=mana_cost,
            max_range=max_range,
            requires_line_of_sight=True,
            can_use_while_moving=cast_time == 0.0,
            global_cooldown=True
        )

        super().__init__(name, ActionType.COMBAT, priority, requirements)

        self.key_binding = key_binding
        self.damage = damage
        self.cast_time = cast_time
        self.max_range = max_range
        self.cooldown = cooldown
        self.description = f"Ranged attack dealing {damage} damage at {max_range}m range"

    def get_cooldown_duration(self) -> float:
        return self.cooldown

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Oceń efektywność ataku dystansowego"""
        if not game_state.target.exists:
            return 0.0

        target = game_state.target
        resources = game_state.resources

        # Range effectiveness - better at medium range
        range_factor = 1.0
        if target.distance > self.max_range:
            return 0.0  # Out of range
        elif target.distance < 8.0:
            range_factor = 0.7  # Too close for ranged
        elif 8.0 <= target.distance <= 20.0:
            range_factor = 1.0  # Optimal range
        else:
            range_factor = 0.9  # Max range

        # Mana efficiency
        mana_factor = min(1.0, resources.mana_percent / 100.0)
        efficiency = self.damage / max(1.0, self.requirements.mana_cost)
        efficiency_factor = min(1.0, efficiency / 15.0)

        # Cast time factor - instant spells are better while moving/under pressure
        mobility_factor = 1.0
        if self.cast_time > 0:
            if game_state.is_moving:
                mobility_factor = 0.3
            elif target.is_casting:
                mobility_factor = 0.8  # Might need to interrupt

        return range_factor * mana_factor * efficiency_factor * mobility_factor


# ===============================
# WARRIOR COMBAT ACTIONS
# ===============================

class HeroicStrikeAction(MeleeAttackAction):
    """Heroic Strike - podstawowy atak warrior"""

    def __init__(self, key_binding: str = "1"):
        super().__init__(
            name="Heroic Strike",
            key_binding=key_binding,
            damage=120.0,
            resource_cost=15.0,
            resource_type="rage",
            cooldown=0.0,
            priority=Priority.MEDIUM
        )

        self.requirements.required_class = ClassType.WARRIOR
        self.description = "Next melee attack deals additional damage"


class ExecuteAction(MeleeAttackAction):
    """Execute - mocny atak na low HP enemies"""

    def __init__(self, key_binding: str = "2"):
        super().__init__(
            name="Execute",
            key_binding=key_binding,
            damage=300.0,
            resource_cost=25.0,
            resource_type="rage",
            cooldown=0.0,
            priority=Priority.HIGH
        )

        self.requirements.required_class = ClassType.WARRIOR
        self.description = "Powerful attack usable only on low health enemies"

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Execute jest efektywny tylko na low HP targets"""
        if not game_state.target.exists:
            return 0.0

        # Execute is only usable on enemies with <20% HP
        if game_state.target.hp_percent > 20.0:
            return 0.0

        base_effectiveness = super().estimate_effectiveness(game_state)

        # Very high effectiveness in execute range
        execute_bonus = 2.0 - (game_state.target.hp_percent / 20.0)

        return min(1.0, base_effectiveness * execute_bonus)


class ChargeAction(BaseAction):
    """Charge - gap closer"""

    def __init__(self, key_binding: str = "3"):
        requirements = ActionRequirements(
            required_class=ClassType.WARRIOR,
            requires_target=True,
            requires_out_of_combat=True,  # Can only charge out of combat
            min_range=8.0,
            max_range=25.0,
            global_cooldown=True
        )

        super().__init__("Charge", ActionType.COMBAT, Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.damage = 50.0
        self.stun_duration = 1.5
        self.description = f"Charge target, dealing {self.damage} damage and stunning for {self.stun_duration}s"

    def get_cooldown_duration(self) -> float:
        return 15.0

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Charge effectiveness"""
        if not game_state.target.exists:
            return 0.0

        target = game_state.target

        # Only useful out of combat to initiate
        if game_state.in_combat:
            return 0.0

        # Perfect range for charge
        if 8.0 <= target.distance <= 25.0:
            return 1.0

        return 0.0

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Execute charge"""
        start_time = time.time()

        try:
            logging.info("Charging target!")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                damage_dealt=self.damage
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class WhirlwindAction(MeleeAttackAction):
    """Whirlwind - AoE attack"""

    def __init__(self, key_binding: str = "4"):
        super().__init__(
            name="Whirlwind",
            key_binding=key_binding,
            damage=80.0,  # Per target
            resource_cost=25.0,
            resource_type="rage",
            cooldown=10.0,
            priority=Priority.MEDIUM
        )

        self.requirements.required_class = ClassType.WARRIOR
        self.max_targets = 4
        self.description = f"AoE attack hitting up to {self.max_targets} enemies"

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Whirlwind is more effective against multiple enemies"""
        base_effectiveness = super().estimate_effectiveness(game_state)

        # In a real implementation, we'd detect multiple nearby enemies
        # For now, assume it's always somewhat effective if we have a target
        if game_state.target.exists:
            return base_effectiveness * 1.2  # Bonus for AoE potential

        return 0.0


# ===============================
# MAGE COMBAT ACTIONS
# ===============================

class FireboltAction(RangedAttackAction):
    """Firebolt - podstawowy spell mage"""

    def __init__(self, key_binding: str = "1"):
        super().__init__(
            name="Firebolt",
            key_binding=key_binding,
            damage=150.0,
            mana_cost=40.0,
            cast_time=2.5,
            max_range=30.0,
            cooldown=0.0,
            priority=Priority.MEDIUM
        )

        self.requirements.required_class = ClassType.MAGE
        self.description = "Hurls a fiery bolt at the enemy"


class FrostboltAction(RangedAttackAction):
    """Frostbolt - spell z slow effect"""

    def __init__(self, key_binding: str = "2"):
        super().__init__(
            name="Frostbolt",
            key_binding=key_binding,
            damage=120.0,
            mana_cost=35.0,
            cast_time=3.0,
            max_range=30.0,
            cooldown=0.0,
            priority=Priority.MEDIUM
        )

        self.requirements.required_class = ClassType.MAGE
        self.slow_duration = 8.0
        self.description = f"Frost spell that slows enemy for {self.slow_duration}s"

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Frostbolt może być bardziej efektywny gdy target się rusza"""
        base_effectiveness = super().estimate_effectiveness(game_state)

        # Bonus if we need to slow/kite the target
        if game_state.target.exists and game_state.target.distance < 15.0:
            base_effectiveness *= 1.2  # Good for kiting

        return base_effectiveness


class FireballAction(RangedAttackAction):
    """Fireball - mocny spell z długim castem"""

    def __init__(self, key_binding: str = "3"):
        super().__init__(
            name="Fireball",
            key_binding=key_binding,
            damage=300.0,
            mana_cost=80.0,
            cast_time=3.5,
            max_range=35.0,
            cooldown=0.0,
            priority=Priority.HIGH
        )

        self.requirements.required_class = ClassType.MAGE
        self.description = "Powerful fire spell with long cast time"

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Fireball najlepszy gdy mamy czas na cast"""
        base_effectiveness = super().estimate_effectiveness(game_state)

        # Less effective if moving or target is casting (might interrupt)
        if game_state.is_moving:
            base_effectiveness *= 0.2
        elif game_state.target.exists and game_state.target.is_casting:
            base_effectiveness *= 0.7

        return base_effectiveness


class BlinkAction(BaseAction):
    """Blink - teleport escape"""

    def __init__(self, key_binding: str = "4"):
        requirements = ActionRequirements(
            required_class=ClassType.MAGE,
            mana_cost=50.0,
            can_use_while_moving=True,
            can_use_while_casting=True,
            global_cooldown=False
        )

        super().__init__("Blink", ActionType.UTILITY, Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.blink_distance = 15.0
        self.description = f"Instantly teleport {self.blink_distance} meters forward"

    def get_cooldown_duration(self) -> float:
        return 15.0

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Blink effectiveness"""
        resources = game_state.resources

        # Very effective when health is low and in combat
        if game_state.in_combat and resources.health_percent < 40.0:
            return 1.0

        # Useful for positioning
        if game_state.target.exists and game_state.target.distance < 10.0:
            return 0.7  # Get distance

        return 0.2  # Some utility value

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Execute blink"""
        start_time = time.time()

        try:
            logging.info("Blinking away!")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


# ===============================
# PRIEST COMBAT ACTIONS
# ===============================

class HolyFireAction(RangedAttackAction):
    """Holy Fire - priest damage spell"""

    def __init__(self, key_binding: str = "1"):
        super().__init__(
            name="Holy Fire",
            key_binding=key_binding,
            damage=200.0,
            mana_cost=60.0,
            cast_time=3.0,
            max_range=30.0,
            cooldown=10.0,
            priority=Priority.MEDIUM
        )

        self.requirements.required_class = ClassType.PRIEST
        self.dot_damage = 50.0
        self.dot_duration = 7.0
        self.description = f"Holy damage with {self.dot_damage} DoT over {self.dot_duration}s"


class SmiteAction(RangedAttackAction):
    """Smite - quick priest damage"""

    def __init__(self, key_binding: str = "2"):
        super().__init__(
            name="Smite",
            key_binding=key_binding,
            damage=120.0,
            mana_cost=40.0,
            cast_time=2.5,
            max_range=30.0,
            cooldown=0.0,
            priority=Priority.MEDIUM
        )

        self.requirements.required_class = ClassType.PRIEST
        self.description = "Quick holy damage spell"


class PsychicScreamAction(BaseAction):
    """Psychic Scream - fear AoE"""

    def __init__(self, key_binding: str = "3"):
        requirements = ActionRequirements(
            required_class=ClassType.PRIEST,
            mana_cost=50.0,
            max_range=8.0,  # Point blank AoE
            global_cooldown=True
        )

        super().__init__("Psychic Scream", ActionType.UTILITY, Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.fear_duration = 8.0
        self.description = f"Fears nearby enemies for {self.fear_duration}s"

    def get_cooldown_duration(self) -> float:
        return 30.0

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Psychic Scream effectiveness"""
        resources = game_state.resources

        # Very effective when overwhelmed or low health
        if game_state.in_combat:
            if resources.health_percent < 30.0:
                return 1.0  # Emergency fear
            elif game_state.target.exists and game_state.target.distance <= 8.0:
                return 0.8  # Good for getting distance

        return 0.1

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Execute Psychic Scream"""
        start_time = time.time()

        try:
            logging.info("Psychic Scream - fearing nearby enemies!")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                mana_cost=self.requirements.mana_cost
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


# ===============================
# FACTORY FUNCTIONS
# ===============================

def create_warrior_combat_actions() -> Dict[str, BaseAction]:
    """Utwórz akcje bojowe dla Warrior"""
    return {
        "heroic_strike": HeroicStrikeAction("1"),
        "execute": ExecuteAction("2"),
        "charge": ChargeAction("3"),
        "whirlwind": WhirlwindAction("4")
    }


def create_mage_combat_actions() -> Dict[str, BaseAction]:
    """Utwórz akcje bojowe dla Mage"""
    return {
        "firebolt": FireboltAction("1"),
        "frostbolt": FrostboltAction("2"),
        "fireball": FireballAction("3"),
        "blink": BlinkAction("4")
    }


def create_priest_combat_actions() -> Dict[str, BaseAction]:
    """Utwórz akcje bojowe dla Priest"""
    return {
        "smite": SmiteAction("1"),
        "holy_fire": HolyFireAction("2"),
        "psychic_scream": PsychicScreamAction("3")
    }


def create_basic_combat_actions() -> Dict[str, BaseAction]:
    """Utwórz podstawowy zestaw akcji bojowych"""
    # This would be the common actions available to all classes
    return {
        # Could include wand attacks, auto-attack, etc.
    }


# ===============================
# COMBO SYSTEM
# ===============================

class ComboAction(BaseAction):
    """Bazowa klasa dla combo actions"""

    def __init__(self, name: str, combo_actions: List[str], priority: Priority = Priority.HIGH):
        super().__init__(name, ActionType.COMBAT, priority)

        self.combo_actions = combo_actions
        self.current_step = 0
        self.combo_window = 5.0  # Time window to complete combo
        self.last_action_time = 0.0

    def reset_combo(self):
        """Reset combo to beginning"""
        self.current_step = 0
        self.last_action_time = 0.0

    def is_combo_valid(self) -> bool:
        """Check if combo is still valid (within time window)"""
        if self.current_step == 0:
            return True

        return (time.time() - self.last_action_time) <= self.combo_window

    def get_next_action(self) -> Optional[str]:
        """Get next action in combo sequence"""
        if not self.is_combo_valid():
            self.reset_combo()

        if self.current_step < len(self.combo_actions):
            return self.combo_actions[self.current_step]

        return None

    def advance_combo(self):
        """Advance to next step in combo"""
        self.current_step += 1
        self.last_action_time = time.time()

        if self.current_step >= len(self.combo_actions):
            self.reset_combo()  # Combo completed