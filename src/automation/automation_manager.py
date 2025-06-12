import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
import json
import tkinter as tk

from .core.game_state_monitor import GameStateMonitor
from .core.data_structures import Resources, GameState
from vision.vision_engine import VisionEngine
from .monster_combat import MonsterCombatHandler


class GUILogHandler(logging.Handler):
    """Custom logging handler that updates GUI text widget"""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)  # Scroll to the end


class AutomationManager:
    def __init__(self, config: Dict, vision_engine: Optional[VisionEngine] = None, log_widget=None):
        self.config = config
        self.vision_engine = vision_engine or VisionEngine()
        self.game_monitor = GameStateMonitor(
            self.vision_engine,
            update_interval=config['automation']['monitoring']['update_interval']
        )

        # Configure monitoring
        self.game_monitor.configure_monitoring(**config['automation']['monitoring'])

        # Resource management
        self.last_health_action: Optional[datetime] = None
        self.last_mana_action: Optional[datetime] = None

        # Register callbacks
        self.game_monitor.add_resource_callback(self.handle_resource_change)

        self.monster_combat = MonsterCombatHandler(self)
        self.combat_enabled = config['automation'].get('combat', {}).get('enabled', False)
        # Set up logging
        log_path = Path(config['paths']['screenshots']) / 'automation.log'
        
        # Configure root logger
        logging.basicConfig(
            filename=str(log_path),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Add GUI handler if widget is provided
        if log_widget:
            gui_handler = GUILogHandler(log_widget)
            gui_handler.setLevel(logging.INFO)
            logging.getLogger().addHandler(gui_handler)
        
        logging.info("=== Automation Manager Initialized ===")
        logging.info(f"Config: {json.dumps(config['automation'], indent=2)}")

    def set_input_controller(self, input_controller):
        # ... existing code ...
        self.monster_combat.set_input_controller(input_controller)

    def start(self):
        # ... existing code ...
        if self.combat_enabled:
            logging.info("Monster combat enabled")

    def set_input_controller(self, input_controller):
        """Set the input controller for automation"""
        self.game_monitor.set_input_controller(input_controller)
        logging.info("Input controller set for automation")

    def start(self):
        """Start automation"""
        if not self.config['automation']['enabled']:
            logging.info("Automation is disabled in config")
            return

        if not self.game_monitor.is_game_window_active():
            logging.warning("Cannot start automation: game window is not active")
            return

        logging.info("=== Starting Automation ===")
        logging.info("Game window is active")
        logging.info("Starting game state monitoring")
        self.game_monitor.start_monitoring()
        logging.info("Automation started successfully")

    def stop(self):
        """Stop automation"""
        logging.info("=== Stopping Automation ===")
        self.game_monitor.stop_monitoring()
        logging.info("Automation stopped")

    def handle_resource_change(self, resources: Resources):
        """Handle resource changes"""
        now = datetime.utcnow()

        # Check health
        if self.should_handle_health(resources, now):
            logging.info(f"Health check triggered - Current health: {resources.health_percent:.1f}%")
            self.handle_low_health(resources)
            self.last_health_action = now
            logging.info("Health action executed")

        # Check mana
        if self.should_handle_mana(resources, now):
            logging.info(f"Mana check triggered - Current mana: {resources.mana_percent:.1f}%")
            self.handle_low_mana(resources)
            self.last_mana_action = now
            logging.info("Mana action executed")

    def should_handle_health(self, resources: Resources, now: datetime) -> bool:
        """Check if we should handle health"""
        health_config = self.config['automation']['resources']['health']

        if not health_config['enabled']:
            return False

        if resources.health_percent > health_config['threshold']:
            return False

        if self.last_health_action:
            cooldown = timedelta(seconds=health_config['cooldown'])
            if now - self.last_health_action < cooldown:
                logging.debug(f"Health action on cooldown. Time remaining: {(cooldown - (now - self.last_health_action)).total_seconds():.1f}s")
                return False

        return True

    def should_handle_mana(self, resources: Resources, now: datetime) -> bool:
        """Check if we should handle mana"""
        mana_config = self.config['automation']['resources']['mana']

        if not mana_config['enabled']:
            return False

        if resources.mana_percent > mana_config['threshold']:
            return False

        if self.last_mana_action:
            cooldown = timedelta(seconds=mana_config['cooldown'])
            if now - self.last_mana_action < cooldown:
                logging.debug(f"Mana action on cooldown. Time remaining: {(cooldown - (now - self.last_mana_action)).total_seconds():.1f}s")
                return False

        return True

    def handle_low_health(self, resources: Resources):
        """Handle low health condition"""
        health_percent = resources.health_percent
        logging.info(f"Low health detected: {health_percent:.1f}%")

        # Log state
        game_state = self.game_monitor.get_current_state()
        self.log_action_state("health", health_percent, game_state)

        # Naciśnij Shift+2 gdy życie jest niskie
        if health_percent < self.config['automation']['resources']['health']['threshold']:
            try:
                # Pobierz input controller z game monitor
                input_controller = self.game_monitor.get_input_controller()
                if input_controller:
                    logging.info("Sending Shift+2 key press for low health")
                    # Naciśnij Shift+2
                    input_controller.send_key('shift+2')
                    logging.info("Shift+2 key press sent successfully")
                else:
                    logging.warning("No input controller available for health action")
            except Exception as e:
                logging.error(f"Failed to send key for health action: {e}")

    def handle_low_mana(self, resources: Resources):
        """Handle low mana condition"""
        mana_percent = resources.mana_percent
        logging.info(f"Low mana detected: {mana_percent:.1f}%")

        # Log state
        game_state = self.game_monitor.get_current_state()
        self.log_action_state("mana", mana_percent, game_state)

        # TODO: Implement your mana potion or drink logic here
        # Example:
        # if mana_percent < 10:
        #     use_mana_potion()
        # elif mana_percent < 30:
        #     use_drink()

    def log_action_state(self, action_type: str, resource_percent: float, game_state: GameState):
        """Log detailed state when action is taken"""
        state_info = {
            'timestamp': datetime.utcnow().isoformat(),
            'action_type': action_type,
            'resource_percent': resource_percent,
            'in_combat': game_state.in_combat,
            'target_exists': game_state.target.exists,
            'target_hp': game_state.target.hp_percent if game_state.target.exists else None
        }

        log_path = Path(self.config['paths']['screenshots']) / 'action_log.json'

        try:
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            else:
                log_data = []

            log_data.append(state_info)

            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logging.error(f"Failed to log action state: {e}")