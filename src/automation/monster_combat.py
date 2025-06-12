# automation/monster_combat.py
import logging
import time
from typing import List, Dict, Optional, Tuple
import numpy as np
from datetime import datetime, timedelta


class MonsterCombatHandler:
    def __init__(self, automation_manager):
        self.automation_manager = automation_manager
        self.vision_engine = automation_manager.vision_engine
        self.input_controller = None

        # Combat settings
        self.target_range = 150  # pixels - jak blisko musi być mob
        self.movement_timeout = 5.0  # seconds - jak długo próbować dojść
        self.attack_cooldown = 1.0  # seconds między atakami

        # State tracking
        self.current_target = None
        self.last_attack_time = None
        self.movement_start_time = None
        self.stuck_check_positions = []
        self.stuck_threshold = 10  # pixels movement to not be stuck

        # Movement keys (WASD)
        self.movement_keys = {
            'forward': 'w',
            'backward': 's',
            'left': 'a',
            'right': 'd'
        }

        logging.info("Monster Combat Handler initialized")

    def set_input_controller(self, input_controller):
        """Set input controller for movement and attacks"""
        self.input_controller = input_controller

    def update(self, screenshot):
        """Main update loop - call this from automation manager"""
        if not self.input_controller:
            return

        try:
            # Detect monsters
            monsters = self.vision_engine.detect_monsters(screenshot)

            if not monsters:
                self.current_target = None
                return

            # Select target
            target = self.select_target(monsters, screenshot.shape)

            if not target:
                return

            self.current_target = target

            # Check if in range to attack
            if self.is_in_attack_range(target, screenshot.shape):
                self.attack_target(target)
            else:
                self.move_towards_target(target, screenshot.shape)

        except Exception as e:
            logging.error(f"Monster combat update error: {e}")

    def select_target(self, monsters: List[Dict], image_shape) -> Optional[Dict]:
        """Select best target from detected monsters"""
        if not monsters:
            return None

        # Get screen center
        screen_center = (image_shape[1] // 2, image_shape[0] // 2)

        # Priority: closest to screen center
        def target_priority(monster):
            center = monster['center']
            distance = np.sqrt((center[0] - screen_center[0]) ** 2 +
                               (center[1] - screen_center[1]) ** 2)
            confidence = monster['confidence']
            return distance / confidence  # Lower is better

        return min(monsters, key=target_priority)

    def is_in_attack_range(self, target: Dict, image_shape) -> bool:
        """Check if target is in attack range"""
        screen_center = (image_shape[1] // 2, image_shape[0] // 2)
        target_center = target['center']

        distance = np.sqrt((target_center[0] - screen_center[0]) ** 2 +
                           (target_center[1] - screen_center[1]) ** 2)

        return distance <= self.target_range

    def attack_target(self, target: Dict):
        """Attack the target"""
        now = datetime.utcnow()

        # Check attack cooldown
        if (self.last_attack_time and
                (now - self.last_attack_time).total_seconds() < self.attack_cooldown):
            return

        try:
            # Click on target to select/attack
            center_x, center_y = target['center']

            logging.info(f"Attacking {target['class_name']} at ({center_x}, {center_y})")

            # Right click to attack (or left click depending on game)
            if self.input_controller.click(center_x, center_y, button='right'):
                self.last_attack_time = now
                logging.info(f"Attack command sent to {target['class_name']}")

            # Optional: use attack spell/ability
            # self.input_controller.send_key('1')  # Attack spell on key 1

        except Exception as e:
            logging.error(f"Attack failed: {e}")

    def move_towards_target(self, target: Dict, image_shape):
        """Move towards target"""
        screen_center = (image_shape[1] // 2, image_shape[0] // 2)
        target_center = target['center']

        # Calculate direction vector
        dx = target_center[0] - screen_center[0]
        dy = target_center[1] - screen_center[1]

        # Normalize direction
        distance = np.sqrt(dx ** 2 + dy ** 2)
        if distance == 0:
            return

        dx_norm = dx / distance
        dy_norm = dy / distance

        # Determine movement keys to press
        keys_to_press = []

        # Horizontal movement
        if abs(dx_norm) > 0.3:  # Threshold to avoid micro-movements
            if dx_norm > 0:
                keys_to_press.append(self.movement_keys['right'])
            else:
                keys_to_press.append(self.movement_keys['left'])

        # Vertical movement
        if abs(dy_norm) > 0.3:
            if dy_norm > 0:
                keys_to_press.append(self.movement_keys['backward'])
            else:
                keys_to_press.append(self.movement_keys['forward'])

        # Execute movement
        if keys_to_press:
            self.execute_movement(keys_to_press, target)

    def execute_movement(self, keys: List[str], target: Dict):
        """Execute movement commands"""
        try:
            # Press keys simultaneously for diagonal movement
            logging.info(f"Moving towards {target['class_name']}: pressing {'+'.join(keys)}")

            for key in keys:
                self.input_controller.send_key(key, hold_duration=0.2)

            # Optional: hold keys for smoother movement
            # self.input_controller.hold_keys(keys, duration=0.3)

        except Exception as e:
            logging.error(f"Movement execution failed: {e}")

    def is_stuck(self, current_position: Tuple[int, int]) -> bool:
        """Check if character is stuck (not moving)"""
        self.stuck_check_positions.append(current_position)

        # Keep only last 5 positions
        if len(self.stuck_check_positions) > 5:
            self.stuck_check_positions.pop(0)

        if len(self.stuck_check_positions) < 3:
            return False

        # Check if positions are too similar (stuck)
        positions = np.array(self.stuck_check_positions)
        distances = np.sqrt(np.sum(np.diff(positions, axis=0) ** 2, axis=1))

        return np.mean(distances) < self.stuck_threshold

    def handle_stuck_situation(self):
        """Handle being stuck - try random movement"""
        logging.warning("Character appears stuck, trying unstuck maneuver")

        try:
            # Try backing up and moving sideways
            unstuck_sequence = [
                (self.movement_keys['backward'], 0.5),
                (self.movement_keys['left'], 0.3),
                (self.movement_keys['right'], 0.6),
            ]

            for key, duration in unstuck_sequence:
                self.input_controller.send_key(key, hold_duration=duration)
                time.sleep(0.1)

            # Clear stuck positions
            self.stuck_check_positions.clear()

        except Exception as e:
            logging.error(f"Unstuck maneuver failed: {e}")

    def get_combat_status(self) -> Dict:
        """Get current combat status for debugging"""
        return {
            'has_target': self.current_target is not None,
            'target_class': self.current_target['class_name'] if self.current_target else None,
            'target_confidence': self.current_target['confidence'] if self.current_target else None,
            'last_attack': self.last_attack_time.isoformat() if self.last_attack_time else None,
            'can_attack': self.can_attack_now()
        }

    def can_attack_now(self) -> bool:
        """Check if can attack now (cooldown check)"""
        if not self.last_attack_time:
            return True

        return (datetime.utcnow() - self.last_attack_time).total_seconds() >= self.attack_cooldown