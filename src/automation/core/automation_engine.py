# src/automation/core/automation_engine.py
"""
Automation Engine - główny silnik łączący wszystkie komponenty automatyzacji
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from .data_structures import (
    GameState, ActionResult, ClassType, Priority, CombatState
)
from .game_state_monitor import GameStateMonitor, MonitoringRegions
from .decision_maker import DecisionMaker, DecisionRule
from .action_executor import ActionExecutor, ExecutionConfig
from .safety_manager import SafetyManager, SafetyConfig, SafetyLevel


# ===============================
# ENGINE CONFIGURATION
# ===============================

class EngineState(Enum):
    """Stany silnika automatyzacji"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class EngineConfig:
    """Konfiguracja głównego silnika"""
    # Basic settings
    character_class: ClassType = ClassType.WARRIOR
    automation_fps: float = 5.0  # Updates per second (5 FPS = 200ms interval)

    # Component settings
    enable_game_state_monitoring: bool = True
    enable_decision_making: bool = True
    enable_action_execution: bool = True
    enable_safety_manager: bool = True

    # Performance settings
    max_decision_time: float = 0.1  # Max 100ms for decision making
    max_execution_time: float = 2.0  # Max 2s for action execution

    # Recovery settings
    auto_recovery: bool = True
    max_recovery_attempts: int = 3
    recovery_delay: float = 5.0

    # Logging
    enable_performance_logging: bool = False
    log_all_decisions: bool = False
    log_state_changes: bool = False


@dataclass
class EngineStats:
    """Statystyki silnika"""
    # Timing
    uptime: float = 0.0
    actual_fps: float = 0.0
    average_loop_time: float = 0.0

    # Counters
    total_loops: int = 0
    total_decisions: int = 0
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0

    # Performance
    decision_time_avg: float = 0.0
    execution_time_avg: float = 0.0
    monitoring_time_avg: float = 0.0

    # Errors
    error_count: int = 0
    recovery_count: int = 0
    last_error_time: float = 0.0

    def calculate_success_rate(self) -> float:
        """Oblicz współczynnik sukcesu akcji"""
        total = self.successful_actions + self.failed_actions
        return (self.successful_actions / total * 100.0) if total > 0 else 0.0


# ===============================
# ENGINE CALLBACKS
# ===============================

class EngineCallback:
    """Callback dla zdarzeń silnika"""

    def __init__(self, name: str, callback: Callable, event_types: List[str]):
        self.name = name
        self.callback = callback
        self.event_types = event_types
        self.call_count = 0
        self.last_call_time = 0.0
        self.enabled = True

    def should_call(self, event_type: str) -> bool:
        """Sprawdź czy callback powinien być wywołany"""
        return self.enabled and event_type in self.event_types

    def call(self, event_type: str, data: Any):
        """Wywołaj callback"""
        if self.should_call(event_type):
            try:
                self.callback(event_type, data)
                self.call_count += 1
                self.last_call_time = time.time()
            except Exception as e:
                logging.error(f"Error in callback '{self.name}': {e}")


# ===============================
# MAIN AUTOMATION ENGINE
# ===============================

class AutomationEngine:
    """
    Główny silnik automatyzacji - łączy wszystkie komponenty
    """

    def __init__(self, vision_engine, input_controller, config: Optional[EngineConfig] = None):
        self.vision_engine = vision_engine
        self.input_controller = input_controller
        self.config = config or EngineConfig()

        # Engine state
        self.state = EngineState.STOPPED
        self.start_time = 0.0
        self.last_loop_time = 0.0

        # Core components
        self.game_state_monitor: Optional[GameStateMonitor] = None
        self.decision_maker: Optional[DecisionMaker] = None
        self.action_executor: Optional[ActionExecutor] = None
        self.safety_manager: Optional[SafetyManager] = None

        # Threading
        self.automation_thread: Optional[threading.Thread] = None
        self.is_running = False
        self._should_stop = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused

        # Profile system
        self.current_profile = None
        self.available_profiles: Dict[str, Any] = {}

        # Statistics and monitoring
        self.stats = EngineStats()
        self.performance_history = deque(maxlen=100)

        # Callbacks
        self.callbacks: List[EngineCallback] = []

        # Error handling
        self.last_error: Optional[Exception] = None
        self.recovery_attempts = 0

        # Initialize components
        self._initialize_components()

        logging.info(f"AutomationEngine initialized for class: {self.config.character_class.value}")

    # ===============================
    # INITIALIZATION
    # ===============================

    def _initialize_components(self):
        """Inicjalizuj wszystkie komponenty"""
        try:
            # Safety Manager (initialize first for safety)
            if self.config.enable_safety_manager:
                safety_config = SafetyConfig(
                    safety_level=SafetyLevel.NORMAL,
                    max_actions_per_minute=30
                )
                self.safety_manager = SafetyManager(safety_config)
                self.safety_manager.add_emergency_callback(self._on_emergency_stop)
                logging.info("Safety manager initialized")

            # Game State Monitor
            if self.config.enable_game_state_monitoring:
                self.game_state_monitor = GameStateMonitor(
                    self.vision_engine,
                    update_interval=1.0 / self.config.automation_fps
                )
                self.game_state_monitor.add_state_callback(self._on_state_change)
                logging.info("Game state monitor initialized")

            # Decision Maker
            if self.config.enable_decision_making:
                self.decision_maker = DecisionMaker(self.config.character_class)
                self.decision_maker.configure(
                    min_decision_interval=1.0 / self.config.automation_fps
                )
                logging.info("Decision maker initialized")

            # Action Executor
            if self.config.enable_action_execution:
                execution_config = ExecutionConfig(
                    min_action_delay=0.1,
                    max_action_delay=0.3,
                    max_actions_per_minute=30
                )
                self.action_executor = ActionExecutor(self.input_controller, execution_config)
                self.action_executor.add_post_execution_callback(self._on_action_executed)
                logging.info("Action executor initialized")

        except Exception as e:
            logging.error(f"Failed to initialize components: {e}")
            self.state = EngineState.ERROR
            raise

    # ===============================
    # PROFILE MANAGEMENT
    # ===============================

    def register_profile(self, profile_name: str, profile):
        """Zarejestruj profil klasy"""
        self.available_profiles[profile_name] = profile
        logging.info(f"Registered profile: {profile_name}")

    def load_profile(self, profile_name: str) -> bool:
        """Załaduj profil klasy"""
        if profile_name not in self.available_profiles:
            logging.error(f"Profile not found: {profile_name}")
            return False

        try:
            profile = self.available_profiles[profile_name]
            self.current_profile = profile

            # Configure decision maker with profile rules and actions
            if self.decision_maker:
                # Clear existing rules and actions
                self.decision_maker = DecisionMaker(self.config.character_class)

                # Load profile actions
                for action_name, action_def in profile.get_actions().items():
                    self.decision_maker.add_action(action_name, action_def)

                # Load profile rules
                for rule in profile.get_rules():
                    self.decision_maker.add_rule(rule)

                # Register action mappings in executor
                if self.action_executor:
                    profile.register_action_mappings(self.action_executor)

            self._emit_event("profile_loaded", {"profile_name": profile_name})
            logging.info(f"Profile loaded: {profile_name}")
            return True

        except Exception as e:
            logging.error(f"Failed to load profile {profile_name}: {e}")
            return False

    # ===============================
    # ENGINE CONTROL
    # ===============================

    def start(self) -> bool:
        """Rozpocznij automatyzację"""
        if self.state != EngineState.STOPPED:
            logging.warning(f"Cannot start engine in state: {self.state}")
            return False

        if not self.current_profile:
            logging.error("No profile loaded")
            return False

        try:
            self.state = EngineState.STARTING

            # Start safety manager
            if self.safety_manager:
                self.safety_manager.start_session()

            # Start game state monitor
            if self.game_state_monitor:
                self.game_state_monitor.start_monitoring()

            # Initialize stats
            self.start_time = time.time()
            self.stats = EngineStats()
            self.recovery_attempts = 0

            # Start main thread
            self.is_running = True
            self._should_stop.clear()
            self._pause_event.set()

            self.automation_thread = threading.Thread(
                target=self._automation_loop,
                name="AutomationEngine",
                daemon=True
            )
            self.automation_thread.start()

            self.state = EngineState.RUNNING
            self._emit_event("engine_started", {"profile": self.current_profile.name})

            logging.info("Automation engine started")
            return True

        except Exception as e:
            logging.error(f"Failed to start engine: {e}")
            self.state = EngineState.ERROR
            self.last_error = e
            return False

    def stop(self):
        """Zatrzymaj automatyzację"""
        if self.state == EngineState.STOPPED:
            return

        logging.info("Stopping automation engine...")
        self.state = EngineState.STOPPING

        # Signal stop
        self.is_running = False
        self._should_stop.set()
        self._pause_event.set()  # Unpause if paused

        # Wait for thread to finish
        if self.automation_thread and self.automation_thread.is_alive():
            self.automation_thread.join(timeout=5.0)
            if self.automation_thread.is_alive():
                logging.warning("Automation thread did not stop gracefully")

        # Stop components
        if self.game_state_monitor:
            self.game_state_monitor.stop_monitoring()

        if self.safety_manager:
            self.safety_manager.stop_session()

        self.state = EngineState.STOPPED
        self._emit_event("engine_stopped", {})

        logging.info("Automation engine stopped")

    def pause(self):
        """Wstrzymaj automatyzację"""
        if self.state != EngineState.RUNNING:
            return

        self._pause_event.clear()
        self.state = EngineState.PAUSED
        self._emit_event("engine_paused", {})
        logging.info("Automation engine paused")

    def resume(self):
        """Wznów automatyzację"""
        if self.state != EngineState.PAUSED:
            return

        self._pause_event.set()
        self.state = EngineState.RUNNING
        self._emit_event("engine_resumed", {})
        logging.info("Automation engine resumed")

    def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Natychmiastowe zatrzymanie"""
        logging.critical(f"EMERGENCY STOP: {reason}")

        if self.safety_manager:
            self.safety_manager.emergency_stop(reason)

        self.stop()

        self._emit_event("emergency_stop", {"reason": reason})

    # ===============================
    # MAIN AUTOMATION LOOP
    # ===============================

    def _automation_loop(self):
        """Główna pętla automatyzacji"""
        loop_interval = 1.0 / self.config.automation_fps

        logging.info(f"Automation loop started (target FPS: {self.config.automation_fps})")

        while self.is_running and not self._should_stop.is_set():
            loop_start = time.time()

            try:
                # Wait if paused
                self._pause_event.wait()

                if not self.is_running:
                    break

                # Execute automation cycle
                self._execute_automation_cycle()

                # Update performance stats
                loop_duration = time.time() - loop_start
                self._update_performance_stats(loop_duration)

                # Sleep to maintain target FPS
                sleep_time = max(0, loop_interval - loop_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                self._handle_automation_error(e)

        logging.info("Automation loop ended")

    def _execute_automation_cycle(self):
        """Wykonaj jeden cykl automatyzacji"""
        cycle_start = time.time()

        # 1. Get current game state
        monitoring_start = time.time()
        if not self.game_state_monitor:
            return

        game_state = self.game_state_monitor.get_current_state()
        monitoring_time = time.time() - monitoring_start

        # 2. Make decision
        decision_start = time.time()
        action_name = None

        if self.decision_maker and game_state.is_safe_to_act():
            # Get recent actions for context
            recent_actions = (self.action_executor.get_recent_executions(5)
                              if self.action_executor else [])

            action_name = self.decision_maker.make_decision(game_state, recent_actions)

        decision_time = time.time() - decision_start

        # 3. Execute action if decided
        execution_time = 0.0
        if action_name and self.action_executor and self.safety_manager:
            # Safety check
            can_execute, reason = self.safety_manager.can_execute_action(action_name, "general")

            if can_execute:
                execution_start = time.time()

                # Get action definition
                if action_name in self.decision_maker.actions:
                    action_instance = self.decision_maker.actions[action_name]
                    action_def = action_instance.definition

                    # Execute action
                    result = self.action_executor.execute_action(
                        action_name, game_state, action_def
                    )

                    # Record in safety manager
                    self.safety_manager.record_action_execution(
                        action_name, "general", result
                    )

                    # Update decision maker
                    action_instance.record_usage(result)

                    # Update stats
                    self.stats.total_actions += 1
                    if result.success:
                        self.stats.successful_actions += 1
                    else:
                        self.stats.failed_actions += 1

                execution_time = time.time() - execution_start
            else:
                if self.config.log_all_decisions:
                    logging.debug(f"Action {action_name} blocked: {reason}")

        # Update stats
        self.stats.total_loops += 1
        if action_name:
            self.stats.total_decisions += 1

        # Update timing averages
        alpha = 0.1  # Moving average factor
        self.stats.monitoring_time_avg = (
                alpha * monitoring_time + (1 - alpha) * self.stats.monitoring_time_avg
        )
        self.stats.decision_time_avg = (
                alpha * decision_time + (1 - alpha) * self.stats.decision_time_avg
        )
        self.stats.execution_time_avg = (
                alpha * execution_time + (1 - alpha) * self.stats.execution_time_avg
        )

        # Log performance if enabled
        if self.config.enable_performance_logging:
            total_cycle_time = time.time() - cycle_start
            if total_cycle_time > 0.5:  # Log slow cycles
                logging.warning(f"Slow automation cycle: {total_cycle_time:.3f}s "
                                f"(monitoring: {monitoring_time:.3f}s, "
                                f"decision: {decision_time:.3f}s, "
                                f"execution: {execution_time:.3f}s)")

    # ===============================
    # ERROR HANDLING & RECOVERY
    # ===============================

    def _handle_automation_error(self, error: Exception):
        """Obsłuż błąd automatyzacji"""
        self.stats.error_count += 1
        self.stats.last_error_time = time.time()
        self.last_error = error

        logging.error(f"Automation error: {error}")

        if self.config.auto_recovery and self.recovery_attempts < self.config.max_recovery_attempts:
            self.recovery_attempts += 1
            self.stats.recovery_count += 1

            logging.info(f"Attempting recovery #{self.recovery_attempts}")

            try:
                # Pause briefly
                time.sleep(self.config.recovery_delay)

                # Try to recover components
                self._recover_components()

                logging.info("Recovery successful")

            except Exception as recovery_error:
                logging.error(f"Recovery failed: {recovery_error}")

                if self.recovery_attempts >= self.config.max_recovery_attempts:
                    logging.critical("Max recovery attempts reached. Stopping engine.")
                    self.emergency_stop("Recovery failed")
        else:
            logging.critical("No auto-recovery or max attempts reached. Stopping engine.")
            self.emergency_stop("Unrecoverable error")

    def _recover_components(self):
        """Próbuj odzyskać komponenty po błędzie"""
        # Reset safety manager if needed
        if self.safety_manager and self.safety_manager.emergency_stop_activated:
            self.safety_manager.reset_emergency_stop()

        # Restart game state monitor if needed
        if self.game_state_monitor and not self.game_state_monitor.is_monitoring_active():
            self.game_state_monitor.start_monitoring()

        # Reset decision maker stats
        if self.decision_maker:
            # Clear recent decision history that might be corrupted
            self.decision_maker.decision_history.clear()

        # Clear action executor history
        if self.action_executor:
            self.action_executor.clear_history()

    # ===============================
    # EVENT CALLBACKS
    # ===============================

    def _on_state_change(self, old_state: GameState, new_state: GameState):
        """Callback na zmianę stanu gry"""
        if self.config.log_state_changes:
            # Log significant changes
            if old_state.combat_state != new_state.combat_state:
                logging.info(f"Combat state changed: {old_state.combat_state} -> {new_state.combat_state}")

            hp_change = new_state.resources.health_percent - old_state.resources.health_percent
            if abs(hp_change) > 10.0:
                logging.info(f"Health changed by {hp_change:.1f}%")

        self._emit_event("state_changed", {
            "old_state": old_state,
            "new_state": new_state
        })

    def _on_action_executed(self, result: ActionResult):
        """Callback na wykonanie akcji"""
        if self.config.log_all_decisions:
            logging.info(f"Action executed: {result.action_name}, "
                         f"success: {result.success}, "
                         f"time: {result.execution_time:.3f}s")

        self._emit_event("action_executed", result)

    def _on_emergency_stop(self, reason: str):
        """Callback na emergency stop"""
        logging.critical(f"Emergency stop triggered: {reason}")
        self.emergency_stop(reason)

    # ===============================
    # STATISTICS & MONITORING
    # ===============================

    def _update_performance_stats(self, loop_duration: float):
        """Aktualizuj statystyki wydajności"""
        # Update uptime
        if self.start_time > 0:
            self.stats.uptime = time.time() - self.start_time

        # Update FPS
        self.stats.actual_fps = 1.0 / loop_duration if loop_duration > 0 else 0.0

        # Update average loop time (moving average)
        alpha = 0.1
        self.stats.average_loop_time = (
                alpha * loop_duration + (1 - alpha) * self.stats.average_loop_time
        )

        # Add to performance history
        self.performance_history.append({
            "timestamp": time.time(),
            "loop_duration": loop_duration,
            "fps": self.stats.actual_fps
        })

    def get_engine_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki silnika"""
        base_stats = {
            "state": self.state.value,
            "uptime": self.stats.uptime,
            "actual_fps": self.stats.actual_fps,
            "target_fps": self.config.automation_fps,
            "average_loop_time": self.stats.average_loop_time,
            "total_loops": self.stats.total_loops,
            "total_decisions": self.stats.total_decisions,
            "total_actions": self.stats.total_actions,
            "success_rate": self.stats.calculate_success_rate(),
            "error_count": self.stats.error_count,
            "recovery_count": self.stats.recovery_count,
            "current_profile": self.current_profile.name if self.current_profile else None
        }

        # Add component stats
        if self.decision_maker:
            base_stats["decision_stats"] = self.decision_maker.get_decision_stats()

        if self.action_executor:
            base_stats["execution_stats"] = self.action_executor.get_execution_stats()

        if self.safety_manager:
            base_stats["safety_stats"] = self.safety_manager.get_safety_status()

        if self.game_state_monitor:
            base_stats["monitoring_stats"] = self.game_state_monitor.get_performance_stats()

        return base_stats

    def get_current_game_state(self) -> Optional[GameState]:
        """Pobierz aktualny stan gry"""
        if self.game_state_monitor:
            return self.game_state_monitor.get_current_state()
        return None

    # ===============================
    # CALLBACK SYSTEM
    # ===============================

    def add_callback(self, name: str, callback: Callable, event_types: List[str]):
        """Dodaj callback na zdarzenia silnika"""
        cb = EngineCallback(name, callback, event_types)
        self.callbacks.append(cb)
        logging.info(f"Added engine callback: {name} for events: {event_types}")

    def remove_callback(self, name: str) -> bool:
        """Usuń callback"""
        for i, cb in enumerate(self.callbacks):
            if cb.name == name:
                del self.callbacks[i]
                logging.info(f"Removed engine callback: {name}")
                return True
        return False

    def _emit_event(self, event_type: str, data: Any):
        """Wywołaj callbacki dla zdarzenia"""
        for callback in self.callbacks:
            callback.call(event_type, data)

    # ===============================
    # CONFIGURATION
    # ===============================

    def configure(self, **kwargs):
        """Skonfiguruj silnik"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                old_value = getattr(self.config, key)
                setattr(self.config, key, value)
                logging.info(f"Engine config updated: {key} = {value} (was: {old_value})")

        # Update component configurations
        if "automation_fps" in kwargs and self.game_state_monitor:
            self.game_state_monitor.update_interval = 1.0 / self.config.automation_fps

    def get_status(self) -> Dict[str, Any]:
        """Pobierz status silnika"""
        return {
            "state": self.state.value,
            "is_running": self.is_running,
            "is_paused": not self._pause_event.is_set(),
            "current_profile": self.current_profile.name if self.current_profile else None,
            "available_profiles": list(self.available_profiles.keys()),
            "components_status": {
                "game_state_monitor": self.game_state_monitor.is_monitoring_active() if self.game_state_monitor else False,
                "decision_maker": self.decision_maker is not None,
                "action_executor": self.action_executor is not None,
                "safety_manager": self.safety_manager.is_active if self.safety_manager else False
            },
            "last_error": str(self.last_error) if self.last_error else None,
            "recovery_attempts": self.recovery_attempts
        }

    def reset_stats(self):
        """Zresetuj statystyki"""
        self.stats = EngineStats()
        self.performance_history.clear()

        if self.decision_maker:
            self.decision_maker.reset_stats()

        if self.action_executor:
            self.action_executor.clear_history()

        logging.info("Engine stats reset")