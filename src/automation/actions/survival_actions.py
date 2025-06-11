# src/automation/actions/survival_actions.py
"""
Akcje przetrwania - healing, mana, food, escape itp.
"""

import time
import logging
from typing import Dict, Optional, Any

from ..core.data_structures import (
    GameState, ActionResult, ActionType, Priority, ClassType
)
from .base_action import BaseAction, ActionRequirements


# ===============================
# HEALING ACTIONS
# ===============================

class HealingSpellAction(BaseAction):
    """Bazowa klasa dla czarów leczących"""

    def __init__(self, name: str, key_binding: str, mana_cost: float,
                 healing_amount: float, cast_time: float, cooldown: float = 0.0,
                 priority: Priority = Priority.HIGH):

        requirements = ActionRequirements(
            mana_cost=mana_cost,
            can_use_while_moving=cast_time == 0.0,  # Instant spells can be used while moving
            global_cooldown=True
        )

        super().__init__(name, ActionType.SURVIVAL, priority, requirements)

        self.key_binding = key_binding
        self.healing_amount = healing_amount
        self.cast_time = cast_time
        self.cooldown = cooldown
        self.description = f"Heals for {healing_amount} HP over {cast_time}s"

    def get_cooldown_duration(self) -> float:
        return self.cooldown

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Ocen efektywność heal spell"""
        resources = game_state.resources

        # Higher effectiveness when HP is lower
        hp_factor = 1.0 - (resources.health_percent / 100.0)

        # Lower effectiveness if mana is low
        mana_factor = min(1.0, resources.mana_percent / 100.0)

        # Healing efficiency (healing per mana)
        efficiency = self.healing_amount / max(1.0, self.requirements.mana_cost)
        efficiency_factor = min(1.0, efficiency / 10.0)  # Normalize

        # Emergency factor - very high when health is critical
        emergency_factor = 1.0
        if resources.health_percent < 20.0:
            emergency_factor = 2.0
        elif resources.health_percent < 40.0:
            emergency_factor = 1.5

        return min(1.0, hp_factor * mana_factor * efficiency_factor * emergency_factor)

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Wykonaj czar leczący"""
        start_time = time.time()

        try:
            # Simulate casting time for non-instant spells
            if self.cast_time > 0:
                # In real implementation, this would be handled by the input system
                logging.info(f"Casting {self.name} (cast time: {self.cast_time}s)")

            # Execute the heal
            # In real implementation: input_controller.send_key(self.key_binding)
            logging.info(f"Executed healing spell: {self.name}")

            execution_time = time.time() - start_time

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=execution_time,
                mana_cost=self.requirements.mana_cost,
                healing_done=self.healing_amount
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class LightHealAction(HealingSpellAction):
    """Lekki czar leczący - szybki, tani"""

    def __init__(self, key_binding: str = "2"):
        super().__init__(
            name="Light Heal",
            key_binding=key_binding,
            mana_cost=30.0,
            healing_amount=150.0,
            cast_time=2.0,
            cooldown=0.0,
            priority=Priority.HIGH
        )


class GreaterHealAction(HealingSpellAction):
    """Mocny czar leczący - wolny, drogi, dużo leczy"""

    def __init__(self, key_binding: str = "3"):
        super().__init__(
            name="Greater Heal",
            key_binding=key_binding,
            mana_cost=80.0,
            healing_amount=400.0,
            cast_time=3.5,
            cooldown=0.0,
            priority=Priority.MEDIUM
        )


class FlashHealAction(HealingSpellAction):
    """Szybki heal - instant, drogi"""

    def __init__(self, key_binding: str = "4"):
        super().__init__(
            name="Flash Heal",
            key_binding=key_binding,
            mana_cost=60.0,
            healing_amount=200.0,
            cast_time=0.0,  # Instant
            cooldown=0.0,
            priority=Priority.HIGH
        )

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Flash heal jest bardziej efektywny w emergencies"""
        base_effectiveness = super().estimate_effectiveness(game_state)

        # Bonus for emergency situations (low HP or in combat)
        if game_state.resources.health_percent < 30.0 or game_state.in_combat:
            base_effectiveness *= 1.3

        return min(1.0, base_effectiveness)


# ===============================
# POTION ACTIONS
# ===============================

class PotionAction(BaseAction):
    """Bazowa klasa dla mikstur"""

    def __init__(self, name: str, key_binding: str, effect_amount: float,
                 cooldown: float, priority: Priority, effect_type: str = "healing"):
        requirements = ActionRequirements(
            can_use_while_moving=True,
            can_use_while_casting=True,
            global_cooldown=False  # Potions don't trigger GCD
        )

        super().__init__(name, ActionType.SURVIVAL, priority, requirements)

        self.key_binding = key_binding
        self.effect_amount = effect_amount
        self.cooldown = cooldown
        self.effect_type = effect_type
        self.description = f"Restores {effect_amount} {effect_type}"

    def get_cooldown_duration(self) -> float:
        return self.cooldown


class HealthPotionAction(PotionAction):
    """Mikstura zdrowia"""

    def __init__(self, key_binding: str = "F1", healing_amount: float = 500.0):
        super().__init__(
            name="Health Potion",
            key_binding=key_binding,
            effect_amount=healing_amount,
            cooldown=30.0,  # WoW potion cooldown
            priority=Priority.EMERGENCY,
            effect_type="health"
        )

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Health potion effectiveness"""
        resources = game_state.resources

        # Very high effectiveness when health is low
        if resources.health_percent < 20.0:
            return 1.0
        elif resources.health_percent < 40.0:
            return 0.8
        elif resources.health_percent < 60.0:
            return 0.5
        else:
            return 0.2  # Still some value for topping off

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Użyj health potion"""
        start_time = time.time()

        try:
            # Use health potion
            # input_controller.send_key(self.key_binding)
            logging.info(f"Used {self.name}")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                healing_done=self.effect_amount
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class ManaPotionAction(PotionAction):
    """Mikstura many"""

    def __init__(self, key_binding: str = "F2", mana_amount: float = 300.0):
        super().__init__(
            name="Mana Potion",
            key_binding=key_binding,
            effect_amount=mana_amount,
            cooldown=120.0,  # Mana potions have longer cooldown
            priority=Priority.HIGH,
            effect_type="mana"
        )

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Mana potion effectiveness"""
        resources = game_state.resources

        # Most effective when mana is low and we're not in immediate danger
        mana_factor = 1.0 - (resources.mana_percent / 100.0)

        # Less effective if health is critical (heal first)
        health_factor = 1.0
        if resources.health_percent < 30.0:
            health_factor = 0.3  # Much lower priority when low HP

        # More effective out of combat (have time to drink)
        combat_factor = 0.7 if game_state.in_combat else 1.0

        return mana_factor * health_factor * combat_factor

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Użyj mana potion"""
        start_time = time.time()

        try:
            logging.info(f"Used {self.name}")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                mana_cost=-self.effect_amount  # Negative because it restores mana
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
# FOOD & DRINK ACTIONS
# ===============================

class DrinkAction(BaseAction):
    """Picie wody/napojów regenerujących mana"""

    def __init__(self, key_binding: str = "F3", mana_per_second: float = 50.0):
        requirements = ActionRequirements(
            requires_out_of_combat=True,
            can_use_while_moving=False,
            can_use_while_casting=False
        )

        super().__init__("Drink Water", ActionType.SURVIVAL, Priority.MEDIUM, requirements)

        self.key_binding = key_binding
        self.mana_per_second = mana_per_second
        self.description = f"Restores {mana_per_second} mana per second while drinking"

    def get_cooldown_duration(self) -> float:
        return 1.0  # Can try to drink every second

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Drinking effectiveness"""
        resources = game_state.resources

        # Only effective out of combat
        if game_state.in_combat:
            return 0.0

        # More effective when mana is low
        mana_factor = 1.0 - (resources.mana_percent / 100.0)

        # Don't drink if health is very low (heal first)
        if resources.health_percent < 20.0:
            return 0.0

        # Less effective if moving or in dangerous area
        safety_factor = 0.8 if game_state.is_moving else 1.0

        return mana_factor * safety_factor

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Start drinking"""
        start_time = time.time()

        try:
            logging.info("Started drinking water")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class EatFoodAction(BaseAction):
    """Jedzenie regenerujące HP"""

    def __init__(self, key_binding: str = "F4", health_per_second: float = 40.0):
        requirements = ActionRequirements(
            requires_out_of_combat=True,
            can_use_while_moving=False,
            can_use_while_casting=False
        )

        super().__init__("Eat Food", ActionType.SURVIVAL, Priority.LOW, requirements)

        self.key_binding = key_binding
        self.health_per_second = health_per_second
        self.description = f"Restores {health_per_second} health per second while eating"

    def get_cooldown_duration(self) -> float:
        return 1.0

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Food effectiveness"""
        resources = game_state.resources

        # Only out of combat
        if game_state.in_combat:
            return 0.0

        # More effective when health is low but not critical
        if resources.health_percent < 10.0:
            return 0.0  # Too dangerous, use potions instead
        elif resources.health_percent < 80.0:
            return 0.8
        else:
            return 0.3  # Still some value for topping off

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Start eating food"""
        start_time = time.time()

        try:
            logging.info("Started eating food")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time
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
# ESCAPE & DEFENSIVE ACTIONS
# ===============================

class BandageAction(BaseAction):
    """Bandażowanie - wolne ale darmowe leczenie"""

    def __init__(self, key_binding: str = "F5", healing_amount: float = 200.0):
        requirements = ActionRequirements(
            requires_out_of_combat=True,
            can_use_while_moving=False,
            can_use_while_casting=False
        )

        super().__init__("First Aid Bandage", ActionType.SURVIVAL, Priority.MEDIUM, requirements)

        self.key_binding = key_binding
        self.healing_amount = healing_amount
        self.bandage_time = 8.0  # Bandaging takes time
        self.description = f"Heals {healing_amount} HP over {self.bandage_time} seconds"

    def get_cooldown_duration(self) -> float:
        return 60.0  # First aid cooldown

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Bandage effectiveness"""
        resources = game_state.resources

        # Only out of combat
        if game_state.in_combat:
            return 0.0

        # Good when health is low but we have time
        health_factor = 1.0 - (resources.health_percent / 100.0)

        # Less effective if mana is high (use spells instead)
        mana_factor = 1.0 - (resources.mana_percent / 100.0)

        # Safety factor - need safe environment for long channeling
        safety_factor = 0.5 if game_state.target.exists else 1.0

        return health_factor * (0.3 + 0.7 * mana_factor) * safety_factor

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Use bandage"""
        start_time = time.time()

        try:
            logging.info(f"Started bandaging (will take {self.bandage_time}s)")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                healing_done=self.healing_amount
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


class RunAwayAction(BaseAction):
    """Ucieczka z walki"""

    def __init__(self):
        requirements = ActionRequirements(
            can_use_while_moving=True,
            can_use_while_casting=True,
            global_cooldown=False
        )

        super().__init__("Run Away", ActionType.SURVIVAL, Priority.EMERGENCY, requirements)
        self.description = "Attempt to escape from dangerous situation"

    def get_cooldown_duration(self) -> float:
        return 5.0  # Can try to run every 5 seconds

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Run away effectiveness"""
        resources = game_state.resources

        # Very effective when health is critical
        if resources.health_percent < 15.0:
            return 1.0
        elif resources.health_percent < 30.0 and game_state.in_combat:
            return 0.8
        else:
            return 0.0  # Don't run unless in danger

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Attempt to run away"""
        start_time = time.time()

        try:
            # This would involve complex movement AI
            # For now, just simulate the attempt
            logging.warning("Attempting to run away from danger!")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time
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
# CLASS-SPECIFIC SURVIVAL ACTIONS
# ===============================

class WarriorShieldWallAction(BaseAction):
    """Shield Wall - warrior defensive cooldown"""

    def __init__(self, key_binding: str = "5"):
        requirements = ActionRequirements(
            required_class=ClassType.WARRIOR,
            global_cooldown=True
        )

        super().__init__("Shield Wall", ActionType.SURVIVAL, Priority.HIGH, requirements)

        self.key_binding = key_binding
        self.damage_reduction = 0.75  # 75% damage reduction
        self.duration = 10.0
        self.description = f"Reduces damage by {self.damage_reduction * 100}% for {self.duration}s"

    def get_cooldown_duration(self) -> float:
        return 1800.0  # 30 minutes

    def estimate_effectiveness(self, game_state: GameState) -> float:
        """Shield Wall effectiveness"""
        resources = game_state.resources

        # Very effective when health is low and in combat
        if not game_state.in_combat:
            return 0.0

        if resources.health_percent < 30.0:
            return 1.0
        elif resources.health_percent < 50.0:
            return 0.7
        else:
            return 0.3

    def execute_internal(self, game_state: GameState, **kwargs) -> ActionResult:
        """Use Shield Wall"""
        start_time = time.time()

        try:
            logging.info("Activated Shield Wall - 75% damage reduction!")

            return ActionResult(
                success=True,
                action_name=self.name,
                timestamp=start_time,
                execution_time=time.time() - start_time
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

def create_basic_survival_actions() -> Dict[str, BaseAction]:
    """Utwórz podstawowy zestaw akcji survival"""
    return {
        # Healing spells
        "light_heal": LightHealAction("2"),
        "greater_heal": GreaterHealAction("3"),
        "flash_heal": FlashHealAction("4"),

        # Potions
        "health_potion": HealthPotionAction("F1"),
        "mana_potion": ManaPotionAction("F2"),

        # Food & Drink
        "drink_water": DrinkAction("F3"),
        "eat_food": EatFoodAction("F4"),

        # First Aid
        "bandage": BandageAction("F5"),

        # Emergency
        "run_away": RunAwayAction()
    }


def create_warrior_survival_actions() -> Dict[str, BaseAction]:
    """Utwórz survival actions dla Warrior"""
    actions = create_basic_survival_actions()

    # Remove healing spells (warriors don't have them)
    del actions["light_heal"]
    del actions["greater_heal"]
    del actions["flash_heal"]

    # Add warrior-specific actions
    actions["shield_wall"] = WarriorShieldWallAction("5")

    return actions


def create_priest_survival_actions() -> Dict[str, BaseAction]:
    """Utwórz survival actions dla Priest"""
    actions = create_basic_survival_actions()

    # Priests have all healing spells
    # Maybe add priest-specific like Shield, Psychic Scream, etc.

    return actions


def create_mage_survival_actions() -> Dict[str, BaseAction]:
    """Utwórz survival actions dla Mage"""
    actions = create_basic_survival_actions()

    # Remove healing spells (mages don't have healing)
    del actions["light_heal"]
    del actions["greater_heal"]
    del actions["flash_heal"]

    # Could add mage-specific like Ice Block, Blink, etc.

    return actions