# src/automation/profile/base_profile.py
"""
Klasa bazowa dla profili klas - łączy akcje, reguły i konfigurację dla konkretnej klasy
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
from enum import Enum

from ..core.data_structures import ClassType, ActionDefinition, Priority
from ..actions.base_action import BaseAction
from ..rules.base_rule import BaseRule
from ..core.action_executor import ExecutionInstruction, ExecutionMethod


# ===============================
# PROFILE CONFIGURATION
# ===============================

class PlayStyle(Enum):
    """Style gry"""
    CONSERVATIVE = "conservative"  # Bezpieczny, defensive
    BALANCED = "balanced"  # Zrównoważony
    AGGRESSIVE = "aggressive"  # Agresywny, offensive
    EFFICIENT = "efficient"  # Fokus na efektywność
    LEVELING = "leveling"  # Optymalizowany na leveling


@dataclass
class ProfileSettings:
    """Ustawienia profilu"""
    # Basic settings
    play_style: PlayStyle = PlayStyle.BALANCED
    auto_targeting: bool = True
    auto_looting: bool = True

    # Combat settings
    engage_distance: float = 25.0
    disengage_threshold: float = 15.0  # HP% to run away
    rest_threshold: float = 60.0  # HP% to start resting

    # Resource management
    mana_conservation: bool = True
    health_potion_threshold: float = 20.0
    mana_potion_threshold: float = 15.0

    # Efficiency settings
    buff_maintenance: bool = True
    food_drink_optimization: bool = True
    repair_threshold: float = 25.0

    # Safety settings
    emergency_actions: bool = True
    avoid_elites: bool = True
    max_enemies: int = 2

    # Leveling specific
    xp_optimization: bool = False
    quest_priority: bool = False


# ===============================
# PROFILE STATISTICS
# ===============================

@dataclass
class ProfileStats:
    """Statystyki profilu"""
    # Usage stats
    sessions_played: int = 0
    total_playtime: float = 0.0
    total_actions: int = 0
    successful_actions: int = 0

    # Combat stats
    monsters_killed: int = 0
    deaths: int = 0
    damage_dealt: float = 0.0
    healing_done: float = 0.0

    # Efficiency stats
    actions_per_minute: float = 0.0
    kill_speed: float = 0.0  # Average time per kill
    downtime_percent: float = 0.0

    # Resource stats
    potions_used: int = 0
    food_consumed: int = 0
    mana_efficiency: float = 0.0

    def calculate_success_rate(self) -> float:
        """Oblicz współczynnik sukcesu"""
        return (self.successful_actions / max(1, self.total_actions)) * 100.0

    def calculate_survival_rate(self) -> float:
        """Oblicz współczynnik przetrwania"""
        total_encounters = self.monsters_killed + self.deaths
        return (self.monsters_killed / max(1, total_encounters)) * 100.0


# ===============================
# BASE PROFILE CLASS
# ===============================

class BaseProfile(ABC):
    """
    Klasa bazowa dla profili klas postaci

    Profil definiuje:
    - Akcje dostępne dla klasy
    - Reguły decyzyjne
    - Mapowania klawiszy
    - Ustawienia specyficzne dla klasy
    """

    def __init__(self, name: str, character_class: ClassType,
                 settings: Optional[ProfileSettings] = None):
        # Basic information
        self.name = name
        self.character_class = character_class
        self.settings = settings or ProfileSettings()

        # Core components
        self.actions: Dict[str, BaseAction] = {}
        self.rules: List[BaseRule] = []
        self.key_mappings: Dict[str, str] = {}  # action_name -> key

        # Action categories for organization
        self.combat_actions: Dict[str, BaseAction] = {}
        self.survival_actions: Dict[str, BaseAction] = {}
        self.utility_actions: Dict[str, BaseAction] = {}
        self.buff_actions: Dict[str, BaseAction] = {}

        # Rule categories
        self.survival_rules: List[BaseRule] = []
        self.combat_rules: List[BaseRule] = []
        self.efficiency_rules: List[BaseRule] = []

        # Statistics and tracking
        self.stats = ProfileStats()
        self.version = "1.0.0"
        self.created_date = ""
        self.last_modified = ""

        # Configuration
        self.description = ""
        self.author = ""
        self.min_level = 1
        self.max_level = 60
        self.recommended_zones: List[str] = []

        # State
        self.is_loaded = False
        self.initialization_errors: List[str] = []

        logging.info(f"Initialized profile: {name} for {character_class.value}")

    # ===============================
    # ABSTRACT METHODS
    # ===============================

    @abstractmethod
    def setup_actions(self):
        """
        Skonfiguruj akcje specyficzne dla klasy
        Musi być zaimplementowane przez klasy dziedziczące
        """
        pass

    @abstractmethod
    def setup_rules(self):
        """
        Skonfiguruj reguły specyficzne dla klasy
        Musi być zaimplementowane przez klasy dziedziczące
        """
        pass

    @abstractmethod
    def setup_key_mappings(self):
        """
        Skonfiguruj mapowania klawiszy
        Musi być zaimplementowane przez klasy dziedziczące
        """
        pass

    @abstractmethod
    def get_rotation_priority(self) -> List[str]:
        """
        Pobierz priorytet rotacji akcji
        Returns: Lista nazw akcji w kolejności priorytetu
        """
        pass

    # ===============================
    # INITIALIZATION METHODS
    # ===============================

    def initialize(self) -> bool:
        """Inicjalizuj profil"""
        try:
            self.initialization_errors.clear()

            # Setup components
            self.setup_actions()
            self.setup_rules()
            self.setup_key_mappings()

            # Validate setup
            self._validate_setup()

            # Organize actions and rules
            self._organize_components()

            # Apply settings
            self._apply_settings()

            self.is_loaded = True
            logging.info(f"Profile '{self.name}' initialized successfully")
            return True

        except Exception as e:
            error_msg = f"Failed to initialize profile '{self.name}': {e}"
            self.initialization_errors.append(error_msg)
            logging.error(error_msg)
            self.is_loaded = False
            return False

    def _validate_setup(self):
        """Waliduj setup profilu"""
        # Check if we have actions
        if not self.actions:
            raise ValueError("No actions defined")

        # Check if we have rules
        if not self.rules:
            raise ValueError("No rules defined")

        # Check key mappings
        for action_name in self.actions:
            if action_name not in self.key_mappings:
                logging.warning(f"No key mapping for action: {action_name}")

        # Validate action-rule consistency
        suggested_actions = set()
        for rule in self.rules:
            suggested_actions.update(rule.suggested_actions)

        missing_actions = suggested_actions - set(self.actions.keys())
        if missing_actions:
            logging.warning(f"Rules suggest missing actions: {missing_actions}")

    def _organize_components(self):
        """Organizuj komponenty według kategorii"""
        # Organize actions by type
        for name, action in self.actions.items():
            if hasattr(action, 'action_type'):
                if action.action_type.value == "combat":
                    self.combat_actions[name] = action
                elif action.action_type.value == "survival":
                    self.survival_actions[name] = action
                elif action.action_type.value == "utility":
                    self.utility_actions[name] = action
                elif action.action_type.value == "buff":
                    self.buff_actions[name] = action

        # Organize rules by category
        for rule in self.rules:
            if hasattr(rule, 'category'):
                if rule.category.value == "survival":
                    self.survival_rules.append(rule)
                elif rule.category.value == "combat":
                    self.combat_rules.append(rule)
                elif rule.category.value == "efficiency":
                    self.efficiency_rules.append(rule)

    def _apply_settings(self):
        """Zastosuj ustawienia do reguł i akcji"""
        # Adjust rules based on play style
        if self.settings.play_style == PlayStyle.CONSERVATIVE:
            self._apply_conservative_settings()
        elif self.settings.play_style == PlayStyle.AGGRESSIVE:
            self._apply_aggressive_settings()
        elif self.settings.play_style == PlayStyle.EFFICIENT:
            self._apply_efficient_settings()

    def _apply_conservative_settings(self):
        """Zastosuj conservative settings"""
        # Increase healing thresholds
        for rule in self.survival_rules:
            if hasattr(rule, 'hp_threshold'):
                rule.hp_threshold = min(80.0, rule.hp_threshold * 1.3)
            if hasattr(rule, 'mana_threshold'):
                rule.mana_threshold = min(60.0, rule.mana_threshold * 1.2)

        # Reduce combat aggressiveness
        for rule in self.combat_rules:
            rule.weight *= 0.8

        # Increase survival rule weights
        for rule in self.survival_rules:
            rule.weight *= 1.2

    def _apply_aggressive_settings(self):
        """Zastosuj aggressive settings"""
        # Decrease healing thresholds
        for rule in self.survival_rules:
            if hasattr(rule, 'hp_threshold'):
                rule.hp_threshold = max(10.0, rule.hp_threshold * 0.8)

        # Increase combat aggressiveness
        for rule in self.combat_rules:
            rule.weight *= 1.3

    def _apply_efficient_settings(self):
        """Zastosuj efficient settings"""
        # Optimize for efficiency rules
        for rule in self.efficiency_rules:
            rule.weight *= 1.2

        # Enable mana conservation
        self.settings.mana_conservation = True

    # ===============================
    # ACTION MANAGEMENT
    # ===============================

    def add_action(self, name: str, action: BaseAction, key: Optional[str] = None):
        """Dodaj akcję do profilu"""
        self.actions[name] = action

        if key:
            self.key_mappings[name] = key

        logging.debug(f"Added action '{name}' to profile '{self.name}'")

    def remove_action(self, name: str) -> bool:
        """Usuń akcję z profilu"""
        if name in self.actions:
            del self.actions[name]

            if name in self.key_mappings:
                del self.key_mappings[name]

            logging.debug(f"Removed action '{name}' from profile '{self.name}'")
            return True

        return False

    def get_action(self, name: str) -> Optional[BaseAction]:
        """Pobierz akcję po nazwie"""
        return self.actions.get(name)

    def get_actions_by_type(self, action_type: str) -> Dict[str, BaseAction]:
        """Pobierz akcje według typu"""
        type_mapping = {
            "combat": self.combat_actions,
            "survival": self.survival_actions,
            "utility": self.utility_actions,
            "buff": self.buff_actions
        }

        return type_mapping.get(action_type, {})

    def get_available_actions(self, context: Any) -> Dict[str, BaseAction]:
        """Pobierz dostępne akcje w danym kontekście"""
        available = {}

        for name, action in self.actions.items():
            if action.enabled and hasattr(action, 'can_execute'):
                # This would need proper context evaluation
                # For now, return all enabled actions
                available[name] = action

        return available

    # ===============================
    # RULE MANAGEMENT
    # ===============================

    def add_rule(self, rule: BaseRule):
        """Dodaj regułę do profilu"""
        self.rules.append(rule)
        logging.debug(f"Added rule '{rule.name}' to profile '{self.name}'")

    def remove_rule(self, rule_name: str) -> bool:
        """Usuń regułę z profilu"""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                logging.debug(f"Removed rule '{rule_name}' from profile '{self.name}'")
                return True

        return False

    def get_rule(self, name: str) -> Optional[BaseRule]:
        """Pobierz regułę po nazwie"""
        for rule in self.rules:
            if rule.name == name:
                return rule
        return None

    def get_rules_by_category(self, category: str) -> List[BaseRule]:
        """Pobierz reguły według kategorii"""
        category_mapping = {
            "survival": self.survival_rules,
            "combat": self.combat_rules,
            "efficiency": self.efficiency_rules
        }

        return category_mapping.get(category, [])

    def get_enabled_rules(self) -> List[BaseRule]:
        """Pobierz włączone reguły"""
        return [rule for rule in self.rules if rule.enabled]

    # ===============================
    # EXECUTION INTEGRATION
    # ===============================

    def register_action_mappings(self, action_executor):
        """Zarejestruj mapowania akcji w executorze"""
        for action_name, key in self.key_mappings.items():
            if action_name in self.actions:
                # Create execution instruction
                instruction = ExecutionInstruction(
                    method=ExecutionMethod.KEYBOARD,
                    key=key,
                    delay_before=0.0,
                    delay_after=0.1
                )

                # Register with executor
                action_executor.register_action_mapping(action_name, instruction)

        logging.info(f"Registered {len(self.key_mappings)} action mappings")

    def get_action_key(self, action_name: str) -> Optional[str]:
        """Pobierz klawisz dla akcji"""
        return self.key_mappings.get(action_name)

    def set_action_key(self, action_name: str, key: str):
        """Ustaw klawisz dla akcji"""
        if action_name in self.actions:
            self.key_mappings[action_name] = key
            logging.debug(f"Set key '{key}' for action '{action_name}'")

    # ===============================
    # STATISTICS & MONITORING
    # ===============================

    def update_stats(self, action_result: Any):
        """Aktualizuj statystyki profilu"""
        self.stats.total_actions += 1

        if hasattr(action_result, 'success') and action_result.success:
            self.stats.successful_actions += 1

            if hasattr(action_result, 'damage_dealt'):
                self.stats.damage_dealt += action_result.damage_dealt

            if hasattr(action_result, 'healing_done'):
                self.stats.healing_done += action_result.healing_done

    def get_profile_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki profilu"""
        return {
            "name": self.name,
            "character_class": self.character_class.value,
            "play_style": self.settings.play_style.value,

            # Action stats
            "total_actions": len(self.actions),
            "combat_actions": len(self.combat_actions),
            "survival_actions": len(self.survival_actions),
            "utility_actions": len(self.utility_actions),

            # Rule stats
            "total_rules": len(self.rules),
            "enabled_rules": len(self.get_enabled_rules()),
            "survival_rules": len(self.survival_rules),
            "combat_rules": len(self.combat_rules),

            # Usage stats
            "success_rate": self.stats.calculate_success_rate(),
            "total_playtime": self.stats.total_playtime,
            "actions_per_minute": self.stats.actions_per_minute,

            # Performance
            "is_loaded": self.is_loaded,
            "initialization_errors": len(self.initialization_errors)
        }

    def reset_stats(self):
        """Zresetuj statystyki"""
        self.stats = ProfileStats()
        logging.info(f"Reset stats for profile '{self.name}'")

    # ===============================
    # CONFIGURATION METHODS
    # ===============================

    def configure(self, **kwargs):
        """Skonfiguruj profil"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                old_value = getattr(self.settings, key)
                setattr(self.settings, key, value)
                logging.info(f"Profile '{self.name}' setting changed: {key} = {value} (was: {old_value})")

        # Reapply settings
        if self.is_loaded:
            self._apply_settings()

    def set_play_style(self, play_style: PlayStyle):
        """Ustaw styl gry"""
        old_style = self.settings.play_style
        self.settings.play_style = play_style

        if self.is_loaded:
            self._apply_settings()

        logging.info(f"Profile '{self.name}' play style changed: {old_style.value} -> {play_style.value}")

    def enable_action(self, action_name: str) -> bool:
        """Włącz akcję"""
        if action_name in self.actions:
            self.actions[action_name].enable()
            return True
        return False

    def disable_action(self, action_name: str) -> bool:
        """Wyłącz akcję"""
        if action_name in self.actions:
            self.actions[action_name].disable()
            return True
        return False

    def enable_rule(self, rule_name: str) -> bool:
        """Włącz regułę"""
        rule = self.get_rule(rule_name)
        if rule:
            rule.enable()
            return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Wyłącz regułę"""
        rule = self.get_rule(rule_name)
        if rule:
            rule.disable()
            return True
        return False

    # ===============================
    # SERIALIZATION
    # ===============================

    def to_dict(self) -> Dict[str, Any]:
        """Konwertuj profil do dictionary"""
        return {
            "name": self.name,
            "character_class": self.character_class.value,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "settings": {
                "play_style": self.settings.play_style.value,
                "auto_targeting": self.settings.auto_targeting,
                "auto_looting": self.settings.auto_looting,
                "engage_distance": self.settings.engage_distance,
                "disengage_threshold": self.settings.disengage_threshold,
                "rest_threshold": self.settings.rest_threshold,
                "mana_conservation": self.settings.mana_conservation,
                "health_potion_threshold": self.settings.health_potion_threshold,
                "mana_potion_threshold": self.settings.mana_potion_threshold
            },
            "key_mappings": self.key_mappings.copy(),
            "stats": {
                "sessions_played": self.stats.sessions_played,
                "total_playtime": self.stats.total_playtime,
                "total_actions": self.stats.total_actions,
                "successful_actions": self.stats.successful_actions,
                "success_rate": self.stats.calculate_success_rate()
            }
        }

    def save_to_file(self, filepath: str):
        """Zapisz profil do pliku"""
        try:
            profile_data = self.to_dict()
            with open(filepath, 'w') as f:
                json.dump(profile_data, f, indent=2)

            logging.info(f"Profile '{self.name}' saved to {filepath}")

        except Exception as e:
            logging.error(f"Failed to save profile '{self.name}': {e}")
            raise

    @classmethod
    def load_from_file(cls, filepath: str) -> 'BaseProfile':
        """Załaduj profil z pliku"""
        try:
            with open(filepath, 'r') as f:
                profile_data = json.load(f)

            # This would need proper deserialization logic
            # For now, just return a placeholder
            logging.info(f"Profile loaded from {filepath}")

        except Exception as e:
            logging.error(f"Failed to load profile from {filepath}: {e}")
            raise

    # ===============================
    # STRING REPRESENTATION
    # ===============================

    def __str__(self) -> str:
        status = "loaded" if self.is_loaded else "not loaded"
        return f"{self.name} [{self.character_class.value}] ({self.settings.play_style.value}) {status}"

    def __repr__(self) -> str:
        return f"BaseProfile(name='{self.name}', class={self.character_class}, loaded={self.is_loaded})"

    def get_summary(self) -> str:
        """Pobierz podsumowanie profilu"""
        lines = [
            f"Profile: {self.name}",
            f"Class: {self.character_class.value}",
            f"Play Style: {self.settings.play_style.value}",
            f"Actions: {len(self.actions)} ({len(self.get_enabled_actions())} enabled)",
            f"Rules: {len(self.rules)} ({len(self.get_enabled_rules())} enabled)",
            f"Success Rate: {self.stats.calculate_success_rate():.1f}%",
            f"Status: {'Loaded' if self.is_loaded else 'Not Loaded'}"
        ]

        if self.initialization_errors:
            lines.append(f"Errors: {len(self.initialization_errors)}")

        return "\n".join(lines)

    def get_enabled_actions(self) -> Dict[str, BaseAction]:
        """Pobierz włączone akcje"""
        return {name: action for name, action in self.actions.items() if action.enabled}


# ===============================
# UTILITY FUNCTIONS
# ===============================

def create_default_settings(play_style: PlayStyle = PlayStyle.BALANCED) -> ProfileSettings:
    """Utwórz domyślne ustawienia profilu"""
    return ProfileSettings(play_style=play_style)


def validate_profile_compatibility(profile: BaseProfile, character_class: ClassType) -> bool:
    """Sprawdź kompatybilność profilu z klasą"""
    return profile.character_class == character_class


def merge_profiles(base_profile: BaseProfile, override_profile: BaseProfile) -> BaseProfile:
    """Połącz dwa profile (base + overrides)"""
    # This would create a new profile combining elements from both
    # Implementation would depend on specific merge strategy
    pass