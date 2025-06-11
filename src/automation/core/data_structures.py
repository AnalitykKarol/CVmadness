# src/automation/core/data_structures.py
"""
Podstawowe struktury danych dla systemu automatyzacji WoW
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


# ===============================
# ENUMS
# ===============================

class ActionType(Enum):
    """Typy akcji w grze"""
    COMBAT = "combat"
    SURVIVAL = "survival"
    MOVEMENT = "movement"
    UTILITY = "utility"
    BUFF = "buff"
    CONSUME = "consume"


class Priority(Enum):
    """Priorytety akcji - niższa liczba = wyższy priorytet"""
    EMERGENCY = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    IDLE = 5


class ClassType(Enum):
    """Klasy postaci w WoW"""
    WARRIOR = "warrior"
    MAGE = "mage"
    PRIEST = "priest"
    HUNTER = "hunter"
    WARLOCK = "warlock"
    PALADIN = "paladin"
    DRUID = "druid"
    ROGUE = "rogue"
    SHAMAN = "shaman"


class CombatState(Enum):
    """Stan walki"""
    PEACEFUL = "peaceful"
    COMBAT = "combat"
    CASTING = "casting"
    CHANNELING = "channeling"
    STUNNED = "stunned"
    DEAD = "dead"


class ResourceType(Enum):
    """Typy zasobów postaci"""
    HEALTH = "health"
    MANA = "mana"
    RAGE = "rage"
    ENERGY = "energy"


# ===============================
# CORE DATA STRUCTURES
# ===============================

@dataclass
class Position:
    """Pozycja w grze"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: 'Position') -> float:
        """Oblicz dystans do innej pozycji"""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2) ** 0.5


@dataclass
class Buff:
    """Reprezentacja buffa/debuffa"""
    name: str
    duration: float = 0.0
    stacks: int = 1
    is_debuff: bool = False
    timestamp: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Sprawdź czy buff wygasł"""
        if self.duration <= 0:
            return False  # Permanent buff
        return (time.time() - self.timestamp) >= self.duration


@dataclass
class Target:
    """Informacje o celu"""
    exists: bool = False
    name: str = ""
    hp_percent: float = 0.0
    level: int = 0
    is_elite: bool = False
    is_hostile: bool = False
    distance: float = 0.0
    is_casting: bool = False
    cast_name: str = ""

    def is_low_hp(self, threshold: float = 20.0) -> bool:
        """Sprawdź czy cel ma mało HP"""
        return self.exists and self.hp_percent <= threshold


@dataclass
class Resources:
    """Zasoby postaci (HP, Mana, etc.)"""
    health_current: int = 100
    health_max: int = 100
    mana_current: int = 100
    mana_max: int = 100
    rage_current: int = 0
    rage_max: int = 100
    energy_current: int = 100
    energy_max: int = 100

    @property
    def health_percent(self) -> float:
        """HP w procentach"""
        if self.health_max == 0:
            return 0.0
        return (self.health_current / self.health_max) * 100.0

    @property
    def mana_percent(self) -> float:
        """Mana w procentach"""
        if self.mana_max == 0:
            return 0.0
        return (self.mana_current / self.mana_max) * 100.0

    @property
    def rage_percent(self) -> float:
        """Rage w procentach"""
        if self.rage_max == 0:
            return 0.0
        return (self.rage_current / self.rage_max) * 100.0

    @property
    def energy_percent(self) -> float:
        """Energy w procentach"""
        if self.energy_max == 0:
            return 0.0
        return (self.energy_current / self.energy_max) * 100.0

    def is_low_health(self, threshold: float = 30.0) -> bool:
        """Sprawdź czy HP jest niskie"""
        return self.health_percent <= threshold

    def is_low_mana(self, threshold: float = 20.0) -> bool:
        """Sprawdź czy mana jest niska"""
        return self.mana_percent <= threshold


@dataclass
class GameState:
    """Kompletny stan gry"""
    # Podstawowe informacje
    timestamp: float = field(default_factory=time.time)
    is_in_game: bool = False

    # Zasoby postaci
    resources: Resources = field(default_factory=Resources)

    # Stan walki
    combat_state: CombatState = CombatState.PEACEFUL
    in_combat: bool = False

    # Pozycja i ruch
    position: Position = field(default_factory=Position)
    is_moving: bool = False
    is_falling: bool = False

    # Castowanie
    is_casting: bool = False
    cast_name: str = ""
    cast_time_remaining: float = 0.0

    # Cel
    target: Target = field(default_factory=Target)

    # Buffy i debuffy
    buffs: List[Buff] = field(default_factory=list)
    debuffs: List[Buff] = field(default_factory=list)

    # Stan środowiska
    zone_name: str = ""
    is_resting: bool = False
    is_in_water: bool = False
    is_mounted: bool = False

    # Inventory
    bag_slots_free: int = 0
    has_food: bool = False
    has_drink: bool = False

    def __post_init__(self):
        """Post-initialization validation"""
        # Update combat state based on flags
        if self.in_combat and self.combat_state == CombatState.PEACEFUL:
            self.combat_state = CombatState.COMBAT
        elif not self.in_combat and self.combat_state == CombatState.COMBAT:
            self.combat_state = CombatState.PEACEFUL

    def get_active_buffs(self) -> List[Buff]:
        """Pobierz aktywne buffy (nie wygasłe)"""
        return [buff for buff in self.buffs if not buff.is_expired()]

    def get_active_debuffs(self) -> List[Buff]:
        """Pobierz aktywne debuffy"""
        return [debuff for debuff in self.debuffs if not debuff.is_expired()]

    def has_buff(self, buff_name: str) -> bool:
        """Sprawdź czy ma aktywny buff"""
        return any(buff.name == buff_name and not buff.is_expired()
                   for buff in self.buffs)

    def has_debuff(self, debuff_name: str) -> bool:
        """Sprawdź czy ma aktywny debuff"""
        return any(debuff.name == debuff_name and not debuff.is_expired()
                   for debuff in self.debuffs)

    def is_safe_to_act(self) -> bool:
        """Sprawdź czy bezpiecznie można wykonać akcję"""
        return (self.is_in_game and
                not self.is_casting and
                self.combat_state not in [CombatState.STUNNED, CombatState.DEAD])

    def needs_emergency_heal(self, threshold: float = 15.0) -> bool:
        """Sprawdź czy potrzeba emergency heal"""
        return self.resources.health_percent <= threshold

    def can_afford_mana(self, mana_cost: float) -> bool:
        """Sprawdź czy stać na mana cost"""
        return self.resources.mana_current >= mana_cost


@dataclass
class ActionResult:
    """Rezultat wykonania akcji"""
    success: bool
    action_name: str
    timestamp: float = field(default_factory=time.time)
    execution_time: float = 0.0

    # Error handling
    error_message: str = ""
    error_code: Optional[int] = None

    # Action details
    mana_cost: float = 0.0
    cooldown_applied: float = 0.0
    damage_dealt: float = 0.0
    healing_done: float = 0.0

    # State changes
    state_before: Optional[GameState] = None
    state_after: Optional[GameState] = None

    def was_successful(self) -> bool:
        """Sprawdź czy akcja się powiodła"""
        return self.success and not self.error_message

    def get_effectiveness(self) -> float:
        """Oblicz efektywność akcji (damage/healing per mana)"""
        if self.mana_cost <= 0:
            return float('inf') if (self.damage_dealt + self.healing_done) > 0 else 0.0
        return (self.damage_dealt + self.healing_done) / self.mana_cost


@dataclass
class Cooldown:
    """Informacje o cooldown"""
    name: str
    duration: float
    started_at: float = field(default_factory=time.time)

    @property
    def remaining_time(self) -> float:
        """Pozostały czas cooldown"""
        elapsed = time.time() - self.started_at
        remaining = self.duration - elapsed
        return max(0.0, remaining)

    @property
    def is_ready(self) -> bool:
        """Sprawdź czy cooldown się skończył"""
        return self.remaining_time <= 0.0

    @property
    def progress_percent(self) -> float:
        """Postęp cooldown w procentach (0-100)"""
        if self.duration <= 0:
            return 100.0
        elapsed = time.time() - self.started_at
        progress = (elapsed / self.duration) * 100.0
        return min(100.0, max(0.0, progress))


@dataclass
class ActionDefinition:
    """Definicja akcji (template)"""
    name: str
    action_type: ActionType
    priority: Priority

    # Execution details
    key_binding: str = ""
    click_coordinates: Optional[tuple] = None

    # Requirements
    min_level: int = 1
    required_class: Optional[ClassType] = None
    mana_cost: float = 0.0
    rage_cost: float = 0.0
    energy_cost: float = 0.0

    # Cooldown & timing
    cooldown: float = 0.0
    cast_time: float = 0.0
    global_cooldown: bool = True

    # Conditions
    requires_target: bool = False
    requires_combat: bool = False
    max_range: float = 0.0  # 0 = melee

    # Effects
    damage: float = 0.0
    healing: float = 0.0
    buff_applied: Optional[str] = None
    debuff_applied: Optional[str] = None

    def can_be_used_by_class(self, character_class: ClassType) -> bool:
        """Sprawdź czy klasa może użyć tej akcji"""
        return self.required_class is None or self.required_class == character_class

    def meets_requirements(self, game_state: GameState, character_class: ClassType) -> bool:
        """Sprawdź czy akcja spełnia wymagania"""
        # Class requirement
        if not self.can_be_used_by_class(character_class):
            return False

        # Target requirement
        if self.requires_target and not game_state.target.exists:
            return False

        # Combat requirement
        if self.requires_combat and not game_state.in_combat:
            return False

        # Resource requirements
        if not game_state.can_afford_mana(self.mana_cost):
            return False

        # Range requirement
        if self.max_range > 0 and game_state.target.exists:
            if game_state.target.distance > self.max_range:
                return False

        return True


# ===============================
# UTILITY FUNCTIONS
# ===============================

def create_game_state_snapshot() -> GameState:
    """Utwórz snapshot aktualnego stanu gry"""
    return GameState(
        timestamp=time.time(),
        is_in_game=True  # This would be determined by vision system
    )


def merge_game_states(old_state: GameState, new_state: GameState) -> GameState:
    """Połącz stary stan z nowym (preserve niektóre wartości)"""
    # Keep some values from old state if new state doesn't have them
    if new_state.zone_name == "" and old_state.zone_name != "":
        new_state.zone_name = old_state.zone_name

    return new_state


def calculate_state_diff(state1: GameState, state2: GameState) -> Dict[str, Any]:
    """Oblicz różnice między stanami"""
    diff = {}

    # Health changes
    hp_diff = state2.resources.health_percent - state1.resources.health_percent
    if abs(hp_diff) > 0.1:  # Only significant changes
        diff['health_change'] = hp_diff

    # Mana changes
    mana_diff = state2.resources.mana_percent - state1.resources.mana_percent
    if abs(mana_diff) > 0.1:
        diff['mana_change'] = mana_diff

    # Combat state changes
    if state1.combat_state != state2.combat_state:
        diff['combat_state_change'] = {
            'from': state1.combat_state,
            'to': state2.combat_state
        }

    # New buffs/debuffs
    old_buff_names = {buff.name for buff in state1.get_active_buffs()}
    new_buff_names = {buff.name for buff in state2.get_active_buffs()}

    added_buffs = new_buff_names - old_buff_names
    removed_buffs = old_buff_names - new_buff_names

    if added_buffs:
        diff['buffs_added'] = list(added_buffs)
    if removed_buffs:
        diff['buffs_removed'] = list(removed_buffs)

    return diff