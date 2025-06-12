import os
import sys
import json
from pathlib import Path
import tkinter as tk

# Dodaj src do path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from gui.main_window import MainWindow
from vision.vision_engine import VisionEngine


def load_config():
    """Załaduj konfigurację z pliku"""
    config_path = src_path.parent / "config" / "settings.json"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Plik konfiguracji nie znaleziony: {config_path}")
        return get_default_config()
    except json.JSONDecodeError as e:
        print(f"Błąd w pliku konfiguracji: {e}")
        return get_default_config()


def get_default_config():
    """Domyślna konfiguracja"""
    return {
        "window": {
            "target_titles": [
                "WowClassic",
                "World of Warcraft",
                "World of Warcraft®",
                "Retail"
            ],
            "capture_fps": 10,
            "screenshot_format": "png"
        },
        "input": {
            "click_delay": 0.1,
            "safety_enabled": True,
            "failsafe_enabled": True
        },
        "gui": {
            "preview_fps": 5,
            "preview_max_width": 400,
            "preview_max_height": 300,
            "window_width": 800,
            "window_height": 600
        },
        "paths": {
            "data": "data",
            "screenshots": "data/screenshots",
            "templates": "data/templates",
            "models": "models",
            "database": "data/training_data.db"
        },
        "automation": {
            "enabled": True,
            "monitoring": {
                "update_interval": 0.2,
                "resources": True,
                "target": True,
                "combat": True,
                "buffs": True
            },
            "resources": {
                "health": {
                    "enabled": True,
                    "threshold": 30.0,
                    "cooldown": 10.0
                },
                "mana": {
                    "enabled": True,
                    "threshold": 20.0,
                    "cooldown": 10.0
                }
            }
        }
    }

def create_directories(config):
    """Utwórz potrzebne foldery"""
    base_path = src_path.parent

    # Upewnij się, że ścieżka data istnieje
    data_path = base_path / "data"
    data_path.mkdir(parents=True, exist_ok=True)

    # Dodaj ścieżkę data do konfiguracji jeśli jej brakuje
    if 'data' not in config['paths']:
        config['paths']['data'] = "data"

    directories = [
        config['paths']['screenshots'],
        config['paths']['templates'],
        config['paths']['models'],
        "models/yolo_models",
        "models/custom",
        "tests"
    ]

    for directory in directories:
        dir_path = base_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)


def main():
    """Main function"""
    print("WoW Automation - Krok 1: Podstawowe Przechwytywanie")
    print("==================================================")

    # Load configuration
    config = load_config()
    print("✓ Konfiguracja załadowana")

    # Create required directories
    create_directories(config)
    print("✓ Foldery utworzone")

    # Create main window
    app = MainWindow(config)

    # Run application
    app.run()


if __name__ == "__main__":
    main()