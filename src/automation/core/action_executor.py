# src/automation/core/action_executor.py
"""
Action Executor - bezpieczne wykonywanie akcji w grze z human-like timing
"""

import time
import random
import threading
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from .data_structures import (
    GameState, ActionResult, ActionDefinition, Priority
)


# ===============================
# EXECUTION CONFIGURATION
# ===============================

@dataclass
class ExecutionConfig:
    """Konfiguracja wykonywania akcji"""
    # Timing settings
    min_action_delay: float = 0.1  # Minimum delay between actions
    max_action_delay: float = 0.3  # Maximum delay between actions
    typing_delay_per_char: float = 0.02  # Delay per character when typing

    # Human-like variations
    timing_variance: float = 0.1  # Random variance in timing (±10%)
    click_position_variance: int = 3  # Pixel variance in click position

    # Safety limits
    max_actions_per_minute: int = 30  # Safety limit for APM
    max_consecutive_failures: int = 5  # Stop after X consecutive failures
    action_timeout: float = 5.0  # Max time to wait for action completion

    # Error handling
    retry_failed_actions: bool = True
    max_retries: int = 2
    retry_delay: float = 1.0

    # Performance
    execution_history_size: int = 100
    enable_detailed_logging: bool = False


class ExecutionMethod(Enum):
    """Metody wykonywania akcji"""
    KEYBOARD = "keyboard"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DRAG = "mouse_drag"
    COMBINATION = "combination"


@dataclass
class ExecutionInstruction:
    """Instrukcja wykonania akcji"""
    method: ExecutionMethod

    # Keyboard instructions
    key: Optional[str] = None
    key_combination: Optional[List[str]] = None
    text_to_type: Optional[str] = None

    # Mouse instructions
    click_position: Optional[Tuple[int, int]] = None
    drag_start: Optional[Tuple[int, int]] = None
    drag_end: Optional[Tuple[int, int]] = None
    mouse_button: str = "left"

    # Timing
    hold_duration: float = 0.0
    delay_before: float = 0.0
    delay_after: float = 0.0

    # Validation
    expected_result: Optional[str] = None
    validation_timeout: float = 1.0


# ===============================
# EXECUTION RESULT TRACKING
# ===============================

@dataclass
class ExecutionAttempt:
    """Pojedyncza próba wykonania akcji"""
    attempt_number: int
    start_time: float
    end_time: float
    success: bool
    error_message: str = ""
    execution_method: Optional[ExecutionMethod] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class DetailedActionResult(ActionResult):
    """Rozszerzony rezultat akcji z detalami wykonania"""
    attempts: List[ExecutionAttempt] = field(default_factory=list)
    total_attempts: int = 0
    execution_method: Optional[ExecutionMethod] = None
    pre_execution_state: Optional[GameState] = None
    post_execution_state: Optional[GameState] = None

    # Performance metrics
    input_delay: float = 0.0
    validation_time: float = 0.0
    total_execution_time: float = 0.0

    def add_attempt(self, attempt: ExecutionAttempt):
        """Dodaj próbę wykonania"""
        self.attempts.append(attempt)
        self.total_attempts += 1
        if attempt.success:
            self.success = True
            self.execution_time = attempt.duration


# ===============================
# SAFETY MANAGER
# ===============================

class ExecutionSafetyManager:
    """Zarządzanie bezpieczeństwem wykonywania akcji"""

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.action_timestamps = deque(maxlen=100)
        self.failure_count = 0
        self.consecutive_failures = 0
        self.is_emergency_stop = False
        self.last_safety_check = time.time()

    def can_execute_action(self) -> Tuple[bool, str]:
        """Sprawdź czy można wykonać akcję"""
        if self.is_emergency_stop:
            return False, "Emergency stop activated"

        # Check APM limit
        current_time = time.time()
        recent_actions = [t for t in self.action_timestamps
                          if (current_time - t) <= 60.0]

        if len(recent_actions) >= self.config.max_actions_per_minute:
            return False, f"APM limit exceeded ({len(recent_actions)}/min)"

        # Check consecutive failures
        if self.consecutive_failures >= self.config.max_consecutive_failures:
            return False, f"Too many consecutive failures ({self.consecutive_failures})"

        return True, ""

    def record_action_start(self):
        """Zapisz rozpoczęcie akcji"""
        self.action_timestamps.append(time.time())

    def record_action_result(self, success: bool):
        """Zapisz rezultat akcji"""
        if success:
            self.consecutive_failures = 0
        else:
            self.failure_count += 1
            self.consecutive_failures += 1

    def emergency_stop(self):
        """Aktywuj emergency stop"""
        self.is_emergency_stop = True
        logging.warning("Execution emergency stop activated")

    def reset_emergency_stop(self):
        """Zresetuj emergency stop"""
        self.is_emergency_stop = False
        self.consecutive_failures = 0
        logging.info("Emergency stop reset")

    def get_safety_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki bezpieczeństwa"""
        current_time = time.time()
        recent_actions = [t for t in self.action_timestamps
                          if (current_time - t) <= 60.0]

        return {
            "actions_last_minute": len(recent_actions),
            "apm_limit": self.config.max_actions_per_minute,
            "total_failures": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "max_consecutive_failures": self.config.max_consecutive_failures,
            "emergency_stop": self.is_emergency_stop
        }


# ===============================
# MAIN ACTION EXECUTOR
# ===============================

class ActionExecutor:
    """
    Główny komponent wykonywania akcji w grze
    """

    def __init__(self, input_controller, config: Optional[ExecutionConfig] = None):
        self.input_controller = input_controller
        self.config = config or ExecutionConfig()

        # Safety and tracking
        self.safety_manager = ExecutionSafetyManager(self.config)
        self.execution_history = deque(maxlen=self.config.execution_history_size)

        # Threading
        self._execution_lock = threading.Lock()

        # Callbacks
        self.pre_execution_callbacks: List[Callable[[str, GameState], None]] = []
        self.post_execution_callbacks: List[Callable[[ActionResult], None]] = []
        self.error_callbacks: List[Callable[[Exception, str], None]] = []

        # Performance tracking
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0,
            "actions_per_minute": 0.0,
            "last_execution_time": 0.0
        }

        # Action mappings
        self.action_mappings: Dict[str, ExecutionInstruction] = {}

        logging.info("ActionExecutor initialized")

    # ===============================
    # ACTION MAPPING MANAGEMENT
    # ===============================

    def register_action_mapping(self, action_name: str, instruction: ExecutionInstruction):
        """Zarejestruj mapowanie akcji na instrukcję wykonania"""
        self.action_mappings[action_name] = instruction
        logging.debug(f"Registered action mapping: {action_name} -> {instruction.method.value}")

    def register_keyboard_action(self, action_name: str, key: str,
                                 delay_before: float = 0.0, delay_after: float = 0.0):
        """Zarejestruj akcję klawiatury"""
        instruction = ExecutionInstruction(
            method=ExecutionMethod.KEYBOARD,
            key=key,
            delay_before=delay_before,
            delay_after=delay_after
        )
        self.register_action_mapping(action_name, instruction)

    def register_click_action(self, action_name: str, position: Tuple[int, int],
                              button: str = "left", delay_before: float = 0.0, delay_after: float = 0.0):
        """Zarejestruj akcję kliknięcia"""
        instruction = ExecutionInstruction(
            method=ExecutionMethod.MOUSE_CLICK,
            click_position=position,
            mouse_button=button,
            delay_before=delay_before,
            delay_after=delay_after
        )
        self.register_action_mapping(action_name, instruction)

    def register_combination_action(self, action_name: str, keys: List[str],
                                    delay_before: float = 0.0, delay_after: float = 0.0):
        """Zarejestruj akcję kombinacji klawiszy"""
        instruction = ExecutionInstruction(
            method=ExecutionMethod.KEYBOARD,
            key_combination=keys,
            delay_before=delay_before,
            delay_after=delay_after
        )
        self.register_action_mapping(action_name, instruction)

    # ===============================
    # MAIN EXECUTION METHODS
    # ===============================

    def execute_action(self, action_name: str, game_state: GameState,
                       action_definition: Optional[ActionDefinition] = None) -> ActionResult:
        """
        Wykonaj akcję w grze
        """
        with self._execution_lock:
            return self._execute_action_internal(action_name, game_state, action_definition)

    def _execute_action_internal(self, action_name: str, game_state: GameState,
                                 action_definition: Optional[ActionDefinition]) -> ActionResult:
        """Wewnętrzna implementacja wykonywania akcji"""
        start_time = time.time()

        # Safety check
        can_execute, safety_reason = self.safety_manager.can_execute_action()
        if not can_execute:
            return self._create_failed_result(action_name, f"Safety check failed: {safety_reason}", start_time)

        # Check if action mapping exists
        if action_name not in self.action_mappings:
            return self._create_failed_result(action_name, f"No mapping found for action: {action_name}", start_time)

        instruction = self.action_mappings[action_name]

        # Create detailed result
        result = DetailedActionResult(
            success=False,
            action_name=action_name,
            timestamp=start_time,
            pre_execution_state=game_state,
            execution_method=instruction.method
        )

        try:
            # Pre-execution callbacks
            self._call_pre_execution_callbacks(action_name, game_state)

            # Record start
            self.safety_manager.record_action_start()

            # Execute with retries
            max_attempts = self.config.max_retries + 1

            for attempt_num in range(max_attempts):
                attempt = self._execute_single_attempt(
                    instruction, action_name, attempt_num + 1, game_state
                )
                result.add_attempt(attempt)

                if attempt.success:
                    result.success = True
                    result.execution_time = attempt.duration
                    break

                # Wait before retry
                if attempt_num < max_attempts - 1 and self.config.retry_failed_actions:
                    self._human_like_delay(self.config.retry_delay)

            # Record result
            self.safety_manager.record_action_result(result.success)

            # Calculate total time
            result.total_execution_time = time.time() - start_time

            # Post-execution callbacks
            self._call_post_execution_callbacks(result)

            # Update stats
            self._update_execution_stats(result)

            # Add to history
            self.execution_history.append(result)

            if self.config.enable_detailed_logging:
                logging.info(f"Action executed: {action_name}, success: {result.success}, "
                             f"attempts: {result.total_attempts}, time: {result.total_execution_time:.3f}s")

            return result

        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            logging.error(error_msg)

            self._call_error_callbacks(e, action_name)
            self.safety_manager.record_action_result(False)

            return self._create_failed_result(action_name, error_msg, start_time)

    def _execute_single_attempt(self, instruction: ExecutionInstruction,
                                action_name: str, attempt_num: int,
                                game_state: GameState) -> ExecutionAttempt:
        """Wykonaj pojedynczą próbę akcji"""
        start_time = time.time()

        try:
            # Pre-execution delay
            if instruction.delay_before > 0:
                self._human_like_delay(instruction.delay_before)

            # Execute based on method
            if instruction.method == ExecutionMethod.KEYBOARD:
                success = self._execute_keyboard_action(instruction)
            elif instruction.method == ExecutionMethod.MOUSE_CLICK:
                success = self._execute_mouse_click(instruction)
            elif instruction.method == ExecutionMethod.MOUSE_DRAG:
                success = self._execute_mouse_drag(instruction)
            else:
                success = False

            # Post-execution delay
            if instruction.delay_after > 0:
                self._human_like_delay(instruction.delay_after)

            # Validate result if specified
            if success and instruction.expected_result:
                success = self._validate_execution_result(instruction, game_state)

            end_time = time.time()

            return ExecutionAttempt(
                attempt_number=attempt_num,
                start_time=start_time,
                end_time=end_time,
                success=success,
                execution_method=instruction.method
            )

        except Exception as e:
            end_time = time.time()

            return ExecutionAttempt(
                attempt_number=attempt_num,
                start_time=start_time,
                end_time=end_time,
                success=False,
                error_message=str(e),
                execution_method=instruction.method
            )

    # ===============================
    # SPECIFIC EXECUTION METHODS
    # ===============================

    def _execute_keyboard_action(self, instruction: ExecutionInstruction) -> bool:
        """Wykonaj akcję klawiatury"""
        try:
            if instruction.key:
                # Single key press
                self.input_controller.send_key(instruction.key)
                self._human_like_delay()  # Small random delay

            elif instruction.key_combination:
                # Key combination
                self.input_controller.send_key_combination(instruction.key_combination)
                self._human_like_delay()

            elif instruction.text_to_type:
                # Type text
                self._type_text_human_like(instruction.text_to_type)

            else:
                logging.error("No keyboard instruction specified")
                return False

            return True

        except Exception as e:
            logging.error(f"Keyboard execution failed: {e}")
            return False

    def _execute_mouse_click(self, instruction: ExecutionInstruction) -> bool:
        """Wykonaj kliknięcie myszą"""
        try:
            if not instruction.click_position:
                logging.error("No click position specified")
                return False

            # Add human-like position variance
            x, y = instruction.click_position
            variance = self.config.click_position_variance
            x += random.randint(-variance, variance)
            y += random.randint(-variance, variance)

            # Execute click
            self.input_controller.click(x, y, instruction.mouse_button)

            # Hold if specified
            if instruction.hold_duration > 0:
                time.sleep(instruction.hold_duration)

            self._human_like_delay()
            return True

        except Exception as e:
            logging.error(f"Mouse click execution failed: {e}")
            return False

    def _execute_mouse_drag(self, instruction: ExecutionInstruction) -> bool:
        """Wykonaj przeciągnięcie myszą"""
        try:
            if not instruction.drag_start or not instruction.drag_end:
                logging.error("Drag start or end position not specified")
                return False

            # Add variance to positions
            variance = self.config.click_position_variance

            start_x, start_y = instruction.drag_start
            start_x += random.randint(-variance, variance)
            start_y += random.randint(-variance, variance)

            end_x, end_y = instruction.drag_end
            end_x += random.randint(-variance, variance)
            end_y += random.randint(-variance, variance)

            # Execute drag
            self.input_controller.drag(start_x, start_y, end_x, end_y)
            self._human_like_delay()
            return True

        except Exception as e:
            logging.error(f"Mouse drag execution failed: {e}")
            return False

    # ===============================
    # HUMAN-LIKE BEHAVIORS
    # ===============================

    def _human_like_delay(self, base_delay: Optional[float] = None) -> None:
        """Dodaj human-like delay"""
        if base_delay is None:
            base_delay = random.uniform(
                self.config.min_action_delay,
                self.config.max_action_delay
            )

        # Add variance
        variance = base_delay * self.config.timing_variance
        actual_delay = base_delay + random.uniform(-variance, variance)
        actual_delay = max(0.01, actual_delay)  # Minimum 10ms

        time.sleep(actual_delay)

    def _type_text_human_like(self, text: str) -> None:
        """Wpisz tekst w sposób podobny do człowieka"""
        for char in text:
            self.input_controller.type_character(char)

            # Variable delay between characters
            char_delay = self.config.typing_delay_per_char
            variance = char_delay * 0.5
            actual_delay = char_delay + random.uniform(-variance, variance)
            actual_delay = max(0.005, actual_delay)  # Minimum 5ms

            time.sleep(actual_delay)

    # ===============================
    # VALIDATION & VERIFICATION
    # ===============================

    def _validate_execution_result(self, instruction: ExecutionInstruction,
                                   game_state: GameState) -> bool:
        """Zweryfikuj czy akcja została wykonana poprawnie"""
        if not instruction.expected_result:
            return True

        # This would require integration with vision system
        # to check if expected changes occurred in game state

        # Placeholder implementation
        validation_start = time.time()
        timeout = instruction.validation_timeout

        while (time.time() - validation_start) < timeout:
            # Check for expected changes
            # This would use vision system to verify
            time.sleep(0.1)

        return True  # Placeholder

    # ===============================
    # CALLBACK MANAGEMENT
    # ===============================

    def add_pre_execution_callback(self, callback: Callable[[str, GameState], None]):
        """Dodaj callback wywoływany przed wykonaniem akcji"""
        self.pre_execution_callbacks.append(callback)

    def add_post_execution_callback(self, callback: Callable[[ActionResult], None]):
        """Dodaj callback wywoływany po wykonaniu akcji"""
        self.post_execution_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[Exception, str], None]):
        """Dodaj callback wywoływany przy błędzie"""
        self.error_callbacks.append(callback)

    def _call_pre_execution_callbacks(self, action_name: str, game_state: GameState):
        """Wywołaj pre-execution callbacks"""
        for callback in self.pre_execution_callbacks:
            try:
                callback(action_name, game_state)
            except Exception as e:
                logging.error(f"Error in pre-execution callback: {e}")

    def _call_post_execution_callbacks(self, result: ActionResult):
        """Wywołaj post-execution callbacks"""
        for callback in self.post_execution_callbacks:
            try:
                callback(result)
            except Exception as e:
                logging.error(f"Error in post-execution callback: {e}")

    def _call_error_callbacks(self, error: Exception, action_name: str):
        """Wywołaj error callbacks"""
        for callback in self.error_callbacks:
            try:
                callback(error, action_name)
            except Exception as e:
                logging.error(f"Error in error callback: {e}")

    # ===============================
    # STATISTICS & MONITORING
    # ===============================

    def _update_execution_stats(self, result: ActionResult):
        """Aktualizuj statystyki wykonania"""
        self.stats["total_executions"] += 1

        if result.success:
            self.stats["successful_executions"] += 1
        else:
            self.stats["failed_executions"] += 1

        # Update average execution time (moving average)
        alpha = 0.1
        if result.execution_time > 0:
            self.stats["average_execution_time"] = (
                    alpha * result.execution_time +
                    (1 - alpha) * self.stats["average_execution_time"]
            )

        self.stats["last_execution_time"] = time.time()

        # Calculate APM
        if len(self.execution_history) >= 2:
            time_span = (self.execution_history[-1].timestamp -
                         self.execution_history[0].timestamp)
            if time_span > 0:
                self.stats["actions_per_minute"] = (len(self.execution_history) / time_span) * 60

    def get_execution_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki wykonania"""
        stats = self.stats.copy()

        # Add success rate
        total = stats["total_executions"]
        if total > 0:
            stats["success_rate"] = (stats["successful_executions"] / total) * 100.0
        else:
            stats["success_rate"] = 0.0

        # Add safety stats
        stats.update(self.safety_manager.get_safety_stats())

        return stats

    def get_recent_executions(self, count: int = 10) -> List[ActionResult]:
        """Pobierz ostatnie wykonania"""
        return list(self.execution_history)[-count:]

    # ===============================
    # UTILITY METHODS
    # ===============================

    def _create_failed_result(self, action_name: str, error_message: str,
                              start_time: float) -> ActionResult:
        """Utwórz rezultat błędu"""
        return ActionResult(
            success=False,
            action_name=action_name,
            timestamp=start_time,
            execution_time=time.time() - start_time,
            error_message=error_message
        )

    def emergency_stop(self):
        """Aktywuj emergency stop"""
        self.safety_manager.emergency_stop()

    def reset_emergency_stop(self):
        """Zresetuj emergency stop"""
        self.safety_manager.reset_emergency_stop()

    def configure(self, **kwargs):
        """Skonfiguruj executor"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logging.info(f"Updated config: {key} = {value}")

    def clear_history(self):
        """Wyczyść historię wykonań"""
        self.execution_history.clear()
        logging.info("Execution history cleared")

    def is_ready(self) -> bool:
        """Sprawdź czy executor jest gotowy"""
        can_execute, _ = self.safety_manager.can_execute_action()
        return can_execute and self.input_controller is not None