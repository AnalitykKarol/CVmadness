from typing import Optional
from datetime import datetime
import logging
from .core.data_structures import Resources
from .core.game_state_monitor import GameStateMonitor


class ResourceAutomationHandler:
    def __init__(self, game_monitor: GameStateMonitor):
        self.game_monitor = game_monitor
        self.last_health_action: Optional[datetime] = None
        self.last_mana_action: Optional[datetime] = None
        self.health_cooldown = 10  # seconds between health actions
        self.mana_cooldown = 10  # seconds between mana actions

        # Register callback
        self.game_monitor.add_resource_callback(self.handle_resource_change)

    def handle_resource_change(self, resources: Resources):
        """Handle resource changes"""
        now = datetime.utcnow()

        # Check health
        if (resources.is_low_health() and
                (not self.last_health_action or
                 (now - self.last_health_action).total_seconds() > self.health_cooldown)):
            self.handle_low_health(resources)
            self.last_health_action = now

        # Check mana
        if (resources.is_low_mana() and
                (not self.last_mana_action or
                 (now - self.last_mana_action).total_seconds() > self.mana_cooldown)):
            self.handle_low_mana(resources)
            self.last_mana_action = now

    def handle_low_health(self, resources: Resources):
        """Handle low health condition"""
        logging.info(f"Low health detected: {resources.health_percent:.1f}%")
        # Add your health potion or healing spell logic here
        # Example:
        # if resources.health_percent < 30:
        #     use_health_potion()
        # elif resources.health_percent < 50:
        #     use_healing_spell()

    def handle_low_mana(self, resources: Resources):
        """Handle low mana condition"""
        logging.info(f"Low mana detected: {resources.mana_percent:.1f}%")
        # Add your mana potion or drink logic here
        # Example:
        # if resources.mana_percent < 20:
        #     use_mana_potion()
        # elif resources.mana_percent < 40:
        #     use_drink()