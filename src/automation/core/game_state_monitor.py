# src/automation/core/game_state_monitor.py
"""
Monitor stanu gry - śledzi HP, mana, combat, target itp. w czasie rzeczywistym
"""

import time
import threading
import logging
from typing import Callable, List, Optional, Dict, Any
from collections import deque

from .data_structures import (
    GameState, Resources, Target, Position, Buff, CombatState,
    calculate_state_diff, merge_game_states
)


# ===============================
# MONITORING REGIONS CONFIG
# ===============================

@dataclass
class MonitoringRegions:
    """Konfiguracja obszarów do monitorowania na ekranie"""
    # Player resources
    player_hp_bar: tuple = (50, 50, 200, 30)  # x, y, width, height
    player_mana_bar: tuple = (50, 80, 200, 30)
    player_rage_bar: tuple = (50, 80, 200, 30)  # Same as mana for warriors
    player_energy_bar: tuple = (50, 80, 200, 30)  # Same as mana for rogues

    # Target
    target_frame: tuple = (300, 50, 250, 100)
    target_hp_bar: tuple = (320, 65, 180, 20)
    target_cast_bar: tuple = (320, 90, 180, 15)

    # Combat indicators
    combat_indicator: tuple = (400, 400, 50, 50)
    player_cast_bar: tuple = (300, 300, 200, 30)

    # Buffs and debuffs
    player_buffs: tuple = (600, 50, 300, 40)
    player_debuffs: tuple = (600, 100, 300, 40)
    target_debuffs: tuple = (320, 110, 180, 30)

    # Environment
    minimap: tuple = (850, 50, 150, 150)
    chat_area: tuple = (50, 400, 400, 200)


# ===============================
# STATE CHANGE CALLBACKS
# ===============================

class StateChangeCallback:
    """Callback dla zmian stanu gry"""

    def __init__(self, name: str, callback: Callable[[GameState, GameState], None],
                 trigger_conditions: Optional[Dict[str, Any]] = None):
        self.name = name
        self.callback = callback
        self.trigger_conditions = trigger_conditions or {}
        self.enabled = True

    def should_trigger(self, old_state: GameState, new_state: GameState) -> bool:
        """Sprawdź czy callback powinien być wywołany"""
        if not self.enabled:
            return False

        # Check specific trigger conditions
        for condition, value in self.trigger_conditions.items():
            if condition == "hp_threshold":
                if new_state.resources.health_percent > value:
                    return False
            elif condition == "combat_change":
                if old_state.in_combat == new_state.in_combat:
                    return False
            elif condition == "target_change":
                if (old_state.target.exists == new_state.target.exists and
                        old_state.target.name == new_state.target.name):
                    return False

        return True


# ===============================
# MAIN GAME STATE MONITOR
# ===============================

class GameStateMonitor:
    """
    Monitor stanu gry - główny komponent do śledzenia wszystkich aspektów gry
    """

    def __init__(self, vision_engine, update_interval: float = 0.2):
        self.vision_engine = vision_engine
        self.update_interval = update_interval

        # Current state
        self.current_state = GameState()
        self.previous_state = GameState()

        # Threading
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Callbacks
        self.state_callbacks: List[StateChangeCallback] = []
        self.error_callbacks: List[Callable[[Exception], None]] = []

        # Configuration
        self.regions = MonitoringRegions()
        self.monitoring_enabled = {
            'resources': True,
            'target': True,
            'combat': True,
            'buffs': True,
            'position': False,  # Requires more advanced vision
            'environment': False
        }

        # Performance tracking
        self.state_history = deque(maxlen=100)  # Last 100 states
        self.performance_stats = {
            'updates_per_second': 0.0,
            'avg_processing_time': 0.0,
            'error_count': 0,
            'last_update_time': 0.0
        }

        # Error handling
        self.consecutive_errors = 0
        self.max_consecutive_errors = 10

        logging.info("GameStateMonitor initialized")
        self.resource_callbacks: List[Callable[[Resources], None]] = []

    def add_resource_callback(self, callback: Callable[[Resources], None]):
        """Add a callback that will be called when resources change"""
        self.resource_callbacks.append(callback)

    def _update_game_state(self):
        """Aktualizuj stan gry"""
        with self._lock:
            # ... existing state update code ...

            if self.monitoring_enabled['resources']:
                new_resources = self._read_player_resources()
                # Check if resources changed
                if (new_resources.health_current != self.current_state.resources.health_current or
                        new_resources.mana_current != self.current_state.resources.mana_current):
                    # Call resource callbacks
                    for callback in self.resource_callbacks:
                        try:
                            callback(new_resources)
                        except Exception as e:
                            logging.error(f"Resource callback error: {e}")

                new_state.resources = new_resources
    # ===============================
    # CORE MONITORING METHODS
    # ===============================

    def start_monitoring(self) -> bool:
        """Rozpocznij monitorowanie stanu gry"""
        if self.is_running:
            logging.warning("Monitor is already running")
            return False

        try:
            self.is_running = True
            self.consecutive_errors = 0

            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="GameStateMonitor",
                daemon=True
            )
            self.monitor_thread.start()

            logging.info("Game state monitoring started")
            return True

        except Exception as e:
            logging.error(f"Failed to start monitoring: {e}")
            self.is_running = False
            return False

    def stop_monitoring(self):
        """Zatrzymaj monitorowanie"""
        if not self.is_running:
            return

        self.is_running = False

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
            if self.monitor_thread.is_alive():
                logging.warning("Monitor thread did not stop gracefully")

        logging.info("Game state monitoring stopped")

    def _monitoring_loop(self):
        """Główna pętla monitorowania"""
        last_update_time = time.time()
        update_count = 0

        while self.is_running:
            try:
                start_time = time.time()

                # Update game state
                self._update_game_state()

                # Calculate performance stats
                processing_time = time.time() - start_time
                update_count += 1

                # Update performance stats every second
                if (start_time - last_update_time) >= 1.0:
                    time_diff = start_time - last_update_time
                    self.performance_stats['updates_per_second'] = update_count / time_diff
                    self.performance_stats['avg_processing_time'] = processing_time
                    self.performance_stats['last_update_time'] = start_time

                    last_update_time = start_time
                    update_count = 0

                # Reset error counter on successful update
                self.consecutive_errors = 0

                # Sleep until next update
                sleep_time = max(0, self.update_interval - processing_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                self._handle_monitoring_error(e)

    def _update_game_state(self):
        """Aktualizuj stan gry"""
        with self._lock:
            # Store previous state
            self.previous_state = GameState(
                timestamp=self.current_state.timestamp,
                resources=Resources(
                    health_current=self.current_state.resources.health_current,
                    health_max=self.current_state.resources.health_max,
                    mana_current=self.current_state.resources.mana_current,
                    mana_max=self.current_state.resources.mana_max
                ),
                in_combat=self.current_state.in_combat,
                target=Target(
                    exists=self.current_state.target.exists,
                    hp_percent=self.current_state.target.hp_percent,
                    name=self.current_state.target.name
                ),
                buffs=self.current_state.buffs.copy(),
                debuffs=self.current_state.debuffs.copy()
            )

            # Create new state
            new_state = GameState(timestamp=time.time())

            # Update components based on enabled monitoring
            if self.monitoring_enabled['resources']:
                new_state.resources = self._read_player_resources()

            if self.monitoring_enabled['target']:
                new_state.target = self._read_target_info()

            if self.monitoring_enabled['combat']:
                new_state.combat_state = self._detect_combat_state()
                new_state.in_combat = new_state.combat_state == CombatState.COMBAT
                new_state.is_casting = self._detect_casting()

            if self.monitoring_enabled['buffs']:
                new_state.buffs = self._read_buffs()
                new_state.debuffs = self._read_debuffs()

            if self.monitoring_enabled['environment']:
                new_state.is_resting = self._detect_resting()
                new_state.zone_name = self._read_zone_name()

            # Merge with previous state to preserve data
            self.current_state = merge_game_states(self.current_state, new_state)

            # Add to history
            self.state_history.append(self.current_state)

            # Notify callbacks
            self._notify_state_callbacks()

    # ===============================
    # RESOURCE MONITORING
    # ===============================

    def _read_player_resources(self) -> Resources:
        """Odczytaj zasoby gracza (HP, mana, itp.)"""
        resources = Resources()

        try:
            # Health
            hp_image = self.vision_engine.capture_region(*self.regions.player_hp_bar)
            hp_data = self.vision_engine.analyze_health_bar(hp_image)

            if hp_data:
                resources.health_current = hp_data.get('current', 100)
                resources.health_max = hp_data.get('max', 100)

            # Mana/Rage/Energy (depends on class)
            mana_image = self.vision_engine.capture_region(*self.regions.player_mana_bar)
            mana_data = self.vision_engine.analyze_mana_bar(mana_image)

            if mana_data:
                # This could be mana, rage, or energy depending on class
                resource_type = mana_data.get('type', 'mana')

                if resource_type == 'mana':
                    resources.mana_current = mana_data.get('current', 100)
                    resources.mana_max = mana_data.get('max', 100)
                elif resource_type == 'rage':
                    resources.rage_current = mana_data.get('current', 0)
                    resources.rage_max = mana_data.get('max', 100)
                elif resource_type == 'energy':
                    resources.energy_current = mana_data.get('current', 100)
                    resources.energy_max = mana_data.get('max', 100)

        except Exception as e:
            logging.warning(f"Failed to read player resources: {e}")
            # Return previous values on error
            resources = self.current_state.resources

        return resources

    # ===============================
    # TARGET MONITORING
    # ===============================

    def _read_target_info(self) -> Target:
        """Odczytaj informacje o celu"""
        target = Target()

        try:
            # Check if target frame exists
            target_frame_image = self.vision_engine.capture_region(*self.regions.target_frame)
            target.exists = self.vision_engine.detect_target_frame(target_frame_image)

            if target.exists:
                # Read target HP
                target_hp_image = self.vision_engine.capture_region(*self.regions.target_hp_bar)
                hp_data = self.vision_engine.analyze_target_health_bar(target_hp_image)

                if hp_data:
                    target.hp_percent = hp_data.get('percent', 0.0)

                # Read target name and level
                target_info = self.vision_engine.read_target_nameplate(target_frame_image)
                if target_info:
                    target.name = target_info.get('name', '')
                    target.level = target_info.get('level', 0)
                    target.is_elite = target_info.get('is_elite', False)
                    target.is_hostile = target_info.get('is_hostile', False)

                # Check if target is casting
                cast_bar_image = self.vision_engine.capture_region(*self.regions.target_cast_bar)
                cast_info = self.vision_engine.detect_cast_bar(cast_bar_image)
                if cast_info:
                    target.is_casting = cast_info.get('is_casting', False)
                    target.cast_name = cast_info.get('spell_name', '')

        except Exception as e:
            logging.warning(f"Failed to read target info: {e}")
            # Return previous target on error
            target = self.current_state.target

        return target

    # ===============================
    # COMBAT STATE DETECTION
    # ===============================

    def _detect_combat_state(self) -> CombatState:
        """Wykryj aktualny stan walki"""
        try:
            # Check combat indicator
            combat_image = self.vision_engine.capture_region(*self.regions.combat_indicator)
            in_combat = self.vision_engine.detect_combat_indicator(combat_image)

            if in_combat:
                # Check if casting
                if self._detect_casting():
                    return CombatState.CASTING
                # Check if stunned/incapacitated
                elif self._detect_stunned():
                    return CombatState.STUNNED
                else:
                    return CombatState.COMBAT
            else:
                # Check if dead
                if self.current_state.resources.health_percent <= 0:
                    return CombatState.DEAD
                # Check if casting outside combat
                elif self._detect_casting():
                    return CombatState.CASTING
                else:
                    return CombatState.PEACEFUL

        except Exception as e:
            logging.warning(f"Failed to detect combat state: {e}")
            return self.current_state.combat_state

    def _detect_casting(self) -> bool:
        """Wykryj czy gracz castuje"""
        try:
            cast_bar_image = self.vision_engine.capture_region(*self.regions.player_cast_bar)
            cast_info = self.vision_engine.detect_cast_bar(cast_bar_image)

            return cast_info.get('is_casting', False) if cast_info else False

        except Exception as e:
            logging.warning(f"Failed to detect casting: {e}")
            return False

    def _detect_stunned(self) -> bool:
        """Wykryj czy gracz jest ogłuszony"""
        # This would require detecting specific debuff icons
        # For now, return False - implement based on debuff detection
        return False

    # ===============================
    # BUFF/DEBUFF MONITORING
    # ===============================

    def _read_buffs(self) -> List[Buff]:
        """Odczytaj aktywne buffy"""
        buffs = []

        try:
            buffs_image = self.vision_engine.capture_region(*self.regions.player_buffs)
            buff_data = self.vision_engine.analyze_buff_bar(buffs_image)

            if buff_data:
                for buff_info in buff_data:
                    buff = Buff(
                        name=buff_info.get('name', ''),
                        duration=buff_info.get('duration', 0.0),
                        stacks=buff_info.get('stacks', 1),
                        is_debuff=False
                    )
                    buffs.append(buff)

        except Exception as e:
            logging.warning(f"Failed to read buffs: {e}")
            # Return previous buffs on error
            buffs = self.current_state.buffs

        return buffs

    def _read_debuffs(self) -> List[Buff]:
        """Odczytaj aktywne debuffy"""
        debuffs = []

        try:
            debuffs_image = self.vision_engine.capture_region(*self.regions.player_debuffs)
            debuff_data = self.vision_engine.analyze_debuff_bar(debuffs_image)

            if debuff_data:
                for debuff_info in debuff_data:
                    debuff = Buff(
                        name=debuff_info.get('name', ''),
                        duration=debuff_info.get('duration', 0.0),
                        stacks=debuff_info.get('stacks', 1),
                        is_debuff=True
                    )
                    debuffs.append(debuff)

        except Exception as e:
            logging.warning(f"Failed to read debuffs: {e}")
            debuffs = self.current_state.debuffs

        return debuffs

    # ===============================
    # ENVIRONMENT MONITORING
    # ===============================

    def _detect_resting(self) -> bool:
        """Wykryj czy gracz odpoczywa"""
        # Look for resting icon or text
        try:
            # This would require specific vision detection
            return False  # Placeholder
        except Exception:
            return False

    def _read_zone_name(self) -> str:
        """Odczytaj nazwę strefy"""
        try:
            # This would require OCR on minimap or specific UI element
            return self.current_state.zone_name  # Keep previous
        except Exception:
            return ""

    # ===============================
    # CALLBACK MANAGEMENT
    # ===============================

    def add_state_callback(self, name: str, callback: Callable[[GameState, GameState], None],
                           trigger_conditions: Optional[Dict[str, Any]] = None):
        """Dodaj callback na zmianę stanu"""
        cb = StateChangeCallback(name, callback, trigger_conditions)
        self.state_callbacks.append(cb)
        logging.info(f"Added state callback: {name}")

    def remove_state_callback(self, name: str) -> bool:
        """Usuń callback"""
        for i, cb in enumerate(self.state_callbacks):
            if cb.name == name:
                del self.state_callbacks[i]
                logging.info(f"Removed state callback: {name}")
                return True
        return False

    def add_error_callback(self, callback: Callable[[Exception], None]):
        """Dodaj callback na błędy"""
        self.error_callbacks.append(callback)

    def _notify_state_callbacks(self):
        """Powiadom callbacki o zmianie stanu"""
        if not self.state_callbacks:
            return

        for callback in self.state_callbacks:
            try:
                if callback.should_trigger(self.previous_state, self.current_state):
                    callback.callback(self.previous_state, self.current_state)
            except Exception as e:
                logging.error(f"Error in state callback '{callback.name}': {e}")

    # ===============================
    # ERROR HANDLING & RECOVERY
    # ===============================

    def _handle_monitoring_error(self, error: Exception):
        """Obsłuż błąd monitorowania"""
        self.consecutive_errors += 1
        self.performance_stats['error_count'] += 1

        logging.error(f"Monitoring error #{self.consecutive_errors}: {error}")

        # Notify error callbacks
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logging.error(f"Error in error callback: {e}")

        # Stop monitoring if too many consecutive errors
        if self.consecutive_errors >= self.max_consecutive_errors:
            logging.critical(f"Too many consecutive errors ({self.consecutive_errors}). Stopping monitor.")
            self.stop_monitoring()
        else:
            # Sleep longer after error
            time.sleep(min(self.consecutive_errors * 0.5, 5.0))

    # ===============================
    # PUBLIC INTERFACE
    # ===============================

    def get_current_state(self) -> GameState:
        """Pobierz aktualny stan gry (thread-safe)"""
        with self._lock:
            # Return a copy to prevent modification
            return GameState(
                timestamp=self.current_state.timestamp,
                is_in_game=self.current_state.is_in_game,
                resources=Resources(
                    health_current=self.current_state.resources.health_current,
                    health_max=self.current_state.resources.health_max,
                    mana_current=self.current_state.resources.mana_current,
                    mana_max=self.current_state.resources.mana_max
                ),
                combat_state=self.current_state.combat_state,
                in_combat=self.current_state.in_combat,
                target=Target(
                    exists=self.current_state.target.exists,
                    name=self.current_state.target.name,
                    hp_percent=self.current_state.target.hp_percent,
                    level=self.current_state.target.level,
                    is_elite=self.current_state.target.is_elite,
                    is_hostile=self.current_state.target.is_hostile
                ),
                buffs=self.current_state.buffs.copy(),
                debuffs=self.current_state.debuffs.copy(),
                is_casting=self.current_state.is_casting
            )

    def get_state_history(self, count: int = 10) -> List[GameState]:
        """Pobierz historię stanów"""
        with self._lock:
            return list(self.state_history)[-count:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki wydajności"""
        return self.performance_stats.copy()

    def configure_monitoring(self, **kwargs):
        """Skonfiguruj co ma być monitorowane"""
        for key, value in kwargs.items():
            if key in self.monitoring_enabled:
                self.monitoring_enabled[key] = value
                logging.info(f"Monitoring {key}: {'enabled' if value else 'disabled'}")

    def configure_regions(self, regions: MonitoringRegions):
        """Skonfiguruj obszary monitorowania"""
        self.regions = regions
        logging.info("Monitoring regions updated")

    def is_monitoring_active(self) -> bool:
        """Sprawdź czy monitoring jest aktywny"""
        return self.is_running and (self.monitor_thread is not None and self.monitor_thread.is_alive())