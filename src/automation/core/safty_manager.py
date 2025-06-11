# src/automation/core/safety_manager.py
"""
Safety Manager - kompleksowy system bezpieczeństwa dla automatyzacji WoW
"""

import time
import threading
import logging
import psutil
import os
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import json

from .data_structures import GameState, ActionResult, Priority


# ===============================
# SAFETY CONFIGURATION
# ===============================

class SafetyLevel(Enum):
    """Poziomy bezpieczeństwa"""
    STRICT = "strict"  # Maksymalne zabezpieczenia
    NORMAL = "normal"  # Standardowe zabezpieczenia
    RELAXED = "relaxed"  # Zrelaksowane zabezpieczenia
    DISABLED = "disabled"  # Wyłączone (tylko do testów)


class ThreatLevel(Enum):
    """Poziomy zagrożenia"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SafetyConfig:
    """Konfiguracja systemu bezpieczeństwa"""
    # Overall safety level
    safety_level: SafetyLevel = SafetyLevel.NORMAL

    # Rate limiting
    max_actions_per_minute: int = 30
    max_actions_per_hour: int = 1200
    max_clicks_per_minute: int = 40
    max_keystrokes_per_minute: int = 50

    # Timing constraints
    min_action_interval: float = 0.1  # Minimum time between actions
    max_session_duration: float = 7200  # Max 2 hours continuous
    mandatory_break_interval: float = 3600  # Break every hour
    mandatory_break_duration: float = 300  # 5 minute breaks

    # Detection avoidance
    enable_human_patterns: bool = True
    random_pause_chance: float = 0.02  # 2% chance of random pause
    random_pause_duration: tuple = (5.0, 30.0)  # 5-30 second pauses
    typing_variation: bool = True
    mouse_movement_variation: bool = True

    # Error handling
    max_consecutive_failures: int = 5
    max_total_failures_per_hour: int = 20
    error_backoff_multiplier: float = 1.5

    # Process monitoring
    monitor_system_resources: bool = True
    max_cpu_usage: float = 80.0  # Max CPU usage %
    max_memory_usage: float = 80.0  # Max memory usage %

    # Emergency triggers
    emergency_hotkey: str = "ctrl+alt+q"
    auto_stop_on_user_input: bool = True
    auto_stop_on_window_focus_loss: bool = True

    # Logging and auditing
    log_all_actions: bool = True
    log_safety_events: bool = True
    keep_audit_trail: bool = True
    audit_trail_max_size: int = 10000


# ===============================
# SAFETY EVENTS & ALERTS
# ===============================

@dataclass
class SafetyEvent:
    """Zdarzenie bezpieczeństwa"""
    timestamp: float
    event_type: str
    threat_level: ThreatLevel
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    action_taken: Optional[str] = None
    resolved: bool = False


class SafetyAlert:
    """Alert bezpieczeństwa"""

    def __init__(self, name: str, condition: Callable[[Dict[str, Any]], bool],
                 threat_level: ThreatLevel, message: str,
                 action: Optional[Callable[[], None]] = None):
        self.name = name
        self.condition = condition
        self.threat_level = threat_level
        self.message = message
        self.action = action
        self.triggered = False
        self.last_trigger_time = 0.0
        self.trigger_count = 0
        self.enabled = True

    def check(self, context: Dict[str, Any]) -> bool:
        """Sprawdź czy alert powinien być wywołany"""
        if not self.enabled:
            return False

        if self.condition(context):
            self.triggered = True
            self.last_trigger_time = time.time()
            self.trigger_count += 1

            if self.action:
                self.action()

            return True

        return False


# ===============================
# RATE LIMITERS
# ===============================

class RateLimiter:
    """Limiter częstotliwości akcji"""

    def __init__(self, max_actions: int, time_window: float):
        self.max_actions = max_actions
        self.time_window = time_window
        self.action_timestamps = deque()
        self._lock = threading.Lock()

    def can_perform_action(self) -> bool:
        """Sprawdź czy można wykonać akcję"""
        with self._lock:
            current_time = time.time()

            # Remove old timestamps
            while (self.action_timestamps and
                   (current_time - self.action_timestamps[0]) > self.time_window):
                self.action_timestamps.popleft()

            return len(self.action_timestamps) < self.max_actions

    def record_action(self):
        """Zapisz wykonanie akcji"""
        with self._lock:
            self.action_timestamps.append(time.time())

    def get_current_count(self) -> int:
        """Pobierz aktualną liczbę akcji w oknie"""
        with self._lock:
            current_time = time.time()

            # Clean old timestamps
            while (self.action_timestamps and
                   (current_time - self.action_timestamps[0]) > self.time_window):
                self.action_timestamps.popleft()

            return len(self.action_timestamps)

    def get_time_until_next_action(self) -> float:
        """Pobierz czas do następnej możliwej akcji"""
        with self._lock:
            if self.can_perform_action():
                return 0.0

            if not self.action_timestamps:
                return 0.0

            oldest_action = self.action_timestamps[0]
            return self.time_window - (time.time() - oldest_action)


# ===============================
# PATTERN DETECTION
# ===============================

class PatternDetector:
    """Detektor podejrzanych wzorców"""

    def __init__(self):
        self.action_patterns = deque(maxlen=50)
        self.timing_patterns = deque(maxlen=50)
        self.suspicious_patterns = 0

    def record_action(self, action_name: str, timestamp: float):
        """Zapisz akcję do analizy wzorców"""
        self.action_patterns.append(action_name)
        self.timing_patterns.append(timestamp)

    def detect_suspicious_patterns(self) -> List[str]:
        """Wykryj podejrzane wzorce"""
        suspicious = []

        # Check for too regular timing
        if len(self.timing_patterns) >= 10:
            intervals = []
            for i in range(1, len(self.timing_patterns)):
                interval = self.timing_patterns[i] - self.timing_patterns[i - 1]
                intervals.append(interval)

            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)

                # If timing is too regular (low variance)
                if variance < 0.01 and avg_interval < 1.0:
                    suspicious.append("Too regular timing pattern detected")

        # Check for repetitive action sequences
        if len(self.action_patterns) >= 6:
            recent_actions = list(self.action_patterns)[-6:]
            for i in range(len(recent_actions) - 2):
                if (recent_actions[i] == recent_actions[i + 2] and
                        recent_actions[i + 1] == recent_actions[i + 3]):
                    suspicious.append("Repetitive action sequence detected")
                    break

        # Check for impossible action speed
        if len(self.timing_patterns) >= 2:
            last_interval = self.timing_patterns[-1] - self.timing_patterns[-2]
            if last_interval < 0.05:  # Less than 50ms between actions
                suspicious.append("Impossibly fast action sequence")

        self.suspicious_patterns += len(suspicious)
        return suspicious


# ===============================
# SYSTEM MONITOR
# ===============================

class SystemMonitor:
    """Monitor zasobów systemowych"""

    def __init__(self, check_interval: float = 5.0):
        self.check_interval = check_interval
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        self.current_stats = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_usage": 0.0,
            "process_count": 0,
            "last_update": 0.0
        }

        self.alert_callbacks: List[Callable[[str, float], None]] = []

    def start_monitoring(self):
        """Rozpocznij monitorowanie systemu"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logging.info("System monitoring started")

    def stop_monitoring(self):
        """Zatrzymaj monitorowanie"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logging.info("System monitoring stopped")

    def _monitoring_loop(self):
        """Pętla monitorowania"""
        while self.is_monitoring:
            try:
                self._update_stats()
                time.sleep(self.check_interval)
            except Exception as e:
                logging.error(f"System monitoring error: {e}")
                time.sleep(self.check_interval)

    def _update_stats(self):
        """Aktualizuj statystyki systemu"""
        try:
            self.current_stats.update({
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "process_count": len(psutil.pids()),
                "last_update": time.time()
            })

            # Check for alerts
            self._check_resource_alerts()

        except Exception as e:
            logging.warning(f"Failed to update system stats: {e}")

    def _check_resource_alerts(self):
        """Sprawdź alerty zasobów"""
        for callback in self.alert_callbacks:
            try:
                callback("cpu", self.current_stats["cpu_percent"])
                callback("memory", self.current_stats["memory_percent"])
            except Exception as e:
                logging.error(f"Error in resource alert callback: {e}")

    def add_alert_callback(self, callback: Callable[[str, float], None]):
        """Dodaj callback dla alertów zasobów"""
        self.alert_callbacks.append(callback)

    def get_stats(self) -> Dict[str, float]:
        """Pobierz aktualne statystyki"""
        return self.current_stats.copy()


# ===============================
# MAIN SAFETY MANAGER
# ===============================

class SafetyManager:
    """
    Główny manager bezpieczeństwa dla systemu automatyzacji
    """

    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()

        # Core components
        self.rate_limiters = {
            "actions": RateLimiter(self.config.max_actions_per_minute, 60.0),
            "clicks": RateLimiter(self.config.max_clicks_per_minute, 60.0),
            "keystrokes": RateLimiter(self.config.max_keystrokes_per_minute, 60.0),
            "hourly": RateLimiter(self.config.max_actions_per_hour, 3600.0)
        }

        self.pattern_detector = PatternDetector()
        self.system_monitor = SystemMonitor()

        # State tracking
        self.is_active = False
        self.emergency_stop_activated = False
        self.session_start_time = 0.0
        self.last_break_time = 0.0
        self.consecutive_failures = 0
        self.total_failures = 0

        # Event tracking
        self.safety_events = deque(maxlen=self.config.audit_trail_max_size)
        self.alerts: List[SafetyAlert] = []
        self.blocked_actions: Set[str] = set()

        # Callbacks
        self.emergency_callbacks: List[Callable[[str], None]] = []
        self.violation_callbacks: List[Callable[[SafetyEvent], None]] = []

        # Threading
        self._lock = threading.Lock()

        # Initialize default alerts
        self._setup_default_alerts()

        logging.info(f"SafetyManager initialized with level: {self.config.safety_level.value}")

    # ===============================
    # CORE SAFETY METHODS
    # ===============================

    def start_session(self):
        """Rozpocznij sesję automatyzacji"""
        with self._lock:
            if self.is_active:
                logging.warning("Safety session already active")
                return

            self.is_active = True
            self.emergency_stop_activated = False
            self.session_start_time = time.time()
            self.last_break_time = time.time()
            self.consecutive_failures = 0

            # Start system monitoring
            if self.config.monitor_system_resources:
                self.system_monitor.start_monitoring()

            self._log_safety_event("session_started", ThreatLevel.NONE, "Safety session started")
            logging.info("Safety session started")

    def stop_session(self):
        """Zakończ sesję automatyzacji"""
        with self._lock:
            if not self.is_active:
                return

            self.is_active = False

            # Stop system monitoring
            self.system_monitor.stop_monitoring()

            session_duration = time.time() - self.session_start_time
            self._log_safety_event(
                "session_ended",
                ThreatLevel.NONE,
                f"Safety session ended after {session_duration:.1f} seconds"
            )

            logging.info(f"Safety session ended (duration: {session_duration:.1f}s)")

    def can_execute_action(self, action_name: str, action_type: str = "general") -> tuple[bool, str]:
        """
        Sprawdź czy akcja może być wykonana
        Returns: (can_execute, reason_if_not)
        """
        if not self.is_active:
            return False, "Safety session not active"

        if self.emergency_stop_activated:
            return False, "Emergency stop activated"

        if action_name in self.blocked_actions:
            return False, f"Action {action_name} is blocked"

        # Check session duration
        session_duration = time.time() - self.session_start_time
        if session_duration > self.config.max_session_duration:
            self.emergency_stop("Maximum session duration exceeded")
            return False, "Session duration limit exceeded"

        # Check mandatory breaks
        time_since_break = time.time() - self.last_break_time
        if time_since_break > self.config.mandatory_break_interval:
            return False, "Mandatory break required"

        # Check rate limits
        rate_limit_check = self._check_rate_limits(action_type)
        if not rate_limit_check[0]:
            return rate_limit_check

        # Check system resources
        if self.config.monitor_system_resources:
            resource_check = self._check_system_resources()
            if not resource_check[0]:
                return resource_check

        # Check for suspicious patterns
        suspicious_patterns = self.pattern_detector.detect_suspicious_patterns()
        if suspicious_patterns and self.config.safety_level != SafetyLevel.DISABLED:
            threat_level = ThreatLevel.MEDIUM
            self._log_safety_event(
                "suspicious_pattern",
                threat_level,
                f"Suspicious patterns detected: {suspicious_patterns}"
            )

            if self.config.safety_level == SafetyLevel.STRICT:
                return False, f"Suspicious pattern detected: {suspicious_patterns[0]}"

        return True, ""

    def record_action_execution(self, action_name: str, action_type: str,
                                result: ActionResult):
        """Zapisz wykonanie akcji"""
        current_time = time.time()

        # Record in rate limiters
        self.rate_limiters["actions"].record_action()

        if action_type == "click":
            self.rate_limiters["clicks"].record_action()
        elif action_type == "keystroke":
            self.rate_limiters["keystrokes"].record_action()

        self.rate_limiters["hourly"].record_action()

        # Record in pattern detector
        self.pattern_detector.record_action(action_name, current_time)

        # Track failures
        if not result.success:
            self.consecutive_failures += 1
            self.total_failures += 1

            if self.consecutive_failures >= self.config.max_consecutive_failures:
                self.emergency_stop("Too many consecutive failures")
        else:
            self.consecutive_failures = 0

        # Check alerts
        self._check_alerts()

        # Log if configured
        if self.config.log_all_actions:
            self._log_safety_event(
                "action_executed",
                ThreatLevel.NONE,
                f"Action {action_name} executed with result: {result.success}",
                {"action_name": action_name, "action_type": action_type, "success": result.success}
            )

    def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Aktywuj emergency stop"""
        with self._lock:
            if self.emergency_stop_activated:
                return

            self.emergency_stop_activated = True

            self._log_safety_event(
                "emergency_stop",
                ThreatLevel.CRITICAL,
                f"Emergency stop activated: {reason}"
            )

            # Notify callbacks
            for callback in self.emergency_callbacks:
                try:
                    callback(reason)
                except Exception as e:
                    logging.error(f"Error in emergency callback: {e}")

            logging.critical(f"EMERGENCY STOP ACTIVATED: {reason}")

    def reset_emergency_stop(self) -> bool:
        """Zresetuj emergency stop"""
        with self._lock:
            if not self.emergency_stop_activated:
                return False

            self.emergency_stop_activated = False
            self.consecutive_failures = 0

            self._log_safety_event(
                "emergency_stop_reset",
                ThreatLevel.NONE,
                "Emergency stop has been reset"
            )

            logging.info("Emergency stop reset")
            return True

    def take_mandatory_break(self, duration: Optional[float] = None):
        """Rozpocznij obowiązkową przerwę"""
        break_duration = duration or self.config.mandatory_break_duration

        self._log_safety_event(
            "mandatory_break",
            ThreatLevel.LOW,
            f"Taking mandatory break for {break_duration} seconds"
        )

        # This would typically pause the automation
        # Implementation depends on the main automation engine

        self.last_break_time = time.time()
        logging.info(f"Taking mandatory break for {break_duration} seconds")

    # ===============================
    # PRIVATE HELPER METHODS
    # ===============================

    def _check_rate_limits(self, action_type: str) -> tuple[bool, str]:
        """Sprawdź limity częstotliwości"""
        # Check general action limit
        if not self.rate_limiters["actions"].can_perform_action():
            time_until_next = self.rate_limiters["actions"].get_time_until_next_action()
            return False, f"Action rate limit exceeded. Wait {time_until_next:.1f}s"

        # Check hourly limit
        if not self.rate_limiters["hourly"].can_perform_action():
            return False, "Hourly action limit exceeded"

        # Check specific action type limits
        if action_type == "click" and not self.rate_limiters["clicks"].can_perform_action():
            return False, "Click rate limit exceeded"

        if action_type == "keystroke" and not self.rate_limiters["keystrokes"].can_perform_action():
            return False, "Keystroke rate limit exceeded"

        return True, ""

    def _check_system_resources(self) -> tuple[bool, str]:
        """Sprawdź zasoby systemowe"""
        stats = self.system_monitor.get_stats()

        if stats["cpu_percent"] > self.config.max_cpu_usage:
            return False, f"CPU usage too high: {stats['cpu_percent']:.1f}%"

        if stats["memory_percent"] > self.config.max_memory_usage:
            return False, f"Memory usage too high: {stats['memory_percent']:.1f}%"

        return True, ""

    def _setup_default_alerts(self):
        """Skonfiguruj domyślne alerty"""
        # High failure rate alert
        self.alerts.append(SafetyAlert(
            name="high_failure_rate",
            condition=lambda ctx: self.consecutive_failures >= 3,
            threat_level=ThreatLevel.HIGH,
            message="High failure rate detected",
            action=lambda: logging.warning("High failure rate detected")
        ))

        # Resource usage alert
        self.alerts.append(SafetyAlert(
            name="high_cpu_usage",
            condition=lambda ctx: self.system_monitor.get_stats()["cpu_percent"] > 90,
            threat_level=ThreatLevel.MEDIUM,
            message="CPU usage critically high",
            action=lambda: self._log_safety_event("high_cpu", ThreatLevel.MEDIUM, "CPU usage > 90%")
        ))

        # Long session alert
        self.alerts.append(SafetyAlert(
            name="long_session",
            condition=lambda ctx: (time.time() - self.session_start_time) > (self.config.max_session_duration * 0.9),
            threat_level=ThreatLevel.MEDIUM,
            message="Session approaching time limit",
            action=lambda: logging.warning("Session time limit approaching")
        ))

    def _check_alerts(self):
        """Sprawdź wszystkie alerty"""
        context = {
            "consecutive_failures": self.consecutive_failures,
            "session_duration": time.time() - self.session_start_time,
            "system_stats": self.system_monitor.get_stats()
        }

        for alert in self.alerts:
            if alert.check(context):
                self._log_safety_event(
                    f"alert_{alert.name}",
                    alert.threat_level,
                    alert.message
                )

    def _log_safety_event(self, event_type: str, threat_level: ThreatLevel,
                          message: str, details: Optional[Dict[str, Any]] = None):
        """Zaloguj zdarzenie bezpieczeństwa"""
        if not self.config.log_safety_events and threat_level == ThreatLevel.NONE:
            return

        event = SafetyEvent(
            timestamp=time.time(),
            event_type=event_type,
            threat_level=threat_level,
            message=message,
            details=details or {}
        )

        self.safety_events.append(event)

        # Log based on threat level
        if threat_level == ThreatLevel.CRITICAL:
            logging.critical(f"SAFETY: {message}")
        elif threat_level == ThreatLevel.HIGH:
            logging.error(f"SAFETY: {message}")
        elif threat_level == ThreatLevel.MEDIUM:
            logging.warning(f"SAFETY: {message}")
        else:
            logging.info(f"SAFETY: {message}")

        # Notify violation callbacks
        if threat_level != ThreatLevel.NONE:
            for callback in self.violation_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logging.error(f"Error in violation callback: {e}")

    # ===============================
    # PUBLIC INTERFACE
    # ===============================

    def add_emergency_callback(self, callback: Callable[[str], None]):
        """Dodaj callback dla emergency stop"""
        self.emergency_callbacks.append(callback)

    def add_violation_callback(self, callback: Callable[[SafetyEvent], None]):
        """Dodaj callback dla naruszeń bezpieczeństwa"""
        self.violation_callbacks.append(callback)

    def block_action(self, action_name: str, reason: str = "Blocked by safety manager"):
        """Zablokuj akcję"""
        self.blocked_actions.add(action_name)
        self._log_safety_event(
            "action_blocked",
            ThreatLevel.MEDIUM,
            f"Action {action_name} blocked: {reason}"
        )

    def unblock_action(self, action_name: str):
        """Odblokuj akcję"""
        if action_name in self.blocked_actions:
            self.blocked_actions.remove(action_name)
            self._log_safety_event(
                "action_unblocked",
                ThreatLevel.NONE,
                f"Action {action_name} unblocked"
            )

    def get_safety_status(self) -> Dict[str, Any]:
        """Pobierz status bezpieczeństwa"""
        current_time = time.time()

        return {
            "is_active": self.is_active,
            "emergency_stop": self.emergency_stop_activated,
            "safety_level": self.config.safety_level.value,
            "session_duration": current_time - self.session_start_time if self.is_active else 0,
            "time_since_break": current_time - self.last_break_time if self.is_active else 0,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "blocked_actions": list(self.blocked_actions),
            "rate_limits": {
                name: limiter.get_current_count()
                for name, limiter in self.rate_limiters.items()
            },
            "system_stats": self.system_monitor.get_stats(),
            "recent_events": len([e for e in self.safety_events
                                  if (current_time - e.timestamp) < 300])  # Last 5 minutes
        }

    def get_recent_events(self, count: int = 20) -> List[SafetyEvent]:
        """Pobierz ostatnie zdarzenia bezpieczeństwa"""
        return list(self.safety_events)[-count:]

    def configure(self, **kwargs):
        """Skonfiguruj safety manager"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logging.info(f"Safety config updated: {key} = {value}")

        # Update rate limiters if changed
        if "max_actions_per_minute" in kwargs:
            self.rate_limiters["actions"] = RateLimiter(
                self.config.max_actions_per_minute, 60.0
            )

    def export_audit_trail(self, filepath: str):
        """Eksportuj audit trail do pliku"""
        try:
            events_data = []
            for event in self.safety_events:
                events_data.append({
                    "timestamp": event.timestamp,
                    "event_type": event.event_type,
                    "threat_level": event.threat_level.value,
                    "message": event.message,
                    "details": event.details,
                    "action_taken": event.action_taken,
                    "resolved": event.resolved
                })

            with open(filepath, 'w') as f:
                json.dump(events_data, f, indent=2)

            logging.info(f"Audit trail exported to {filepath}")

        except Exception as e:
            logging.error(f"Failed to export audit trail: {e}")