import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

from .core.game_state_monitor import GameStateMonitor
from .core.data_structures import Resources, GameState
from vision.vision_engine import VisionEngine


class AutomationManager:
    def __init__(self, config: Dict, vision_engine: Optional[VisionEngine] = None):
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

        # Set up logging
        log_path = Path(config['paths']['screenshots']) / 'automation.log'
        logging.basicConfig(
            filename=str(log_path),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def start(self):
        """Start automation"""
        if self.config['automation']['enabled']:
            logging.info("Starting automation")
            self.game_monitor.start_monitoring()

    def stop(self):
        """Stop automation"""
        logging.info("Stopping automation")
        self.game_monitor.stop_monitoring()

    def handle_resource_change(self, resources: Resources):
        """Handle resource changes"""
        now = datetime.utcnow()

        # Check health
        if self.should_handle_health(resources, now):
            self.handle_low_health(resources)
            self.last_health_action = now

        # Check mana
        if self.should_handle_mana(resources, now):
            self.handle_low_mana(resources)
            self.last_mana_action = now

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
                return False

        return True

    def handle_low_health(self, resources: Resources):
        """Handle low health condition"""
        health_percent = resources.health_percent
        logging.info(f"Low health detected: {health_percent:.1f}%")

        # Log state
        game_state = self.game_monitor.get_current_state()
        self.log_action_state("health", health_percent, game_state)

        # TODO: Implement your health potion or healing spell logic here
        # Example:
        # if health_percent < 20:
        #     use_emergency_healing()
        # elif health_percent < 50:
        #     use_normal_healing()

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