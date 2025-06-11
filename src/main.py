import os
import sys
import json
from pathlib import Path

# Dodaj src do path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from gui.main_window import MainWindow


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
            "screenshots": "data/screenshots",
            "templates": "data/templates",
            "models": "models",
            "database": "data/training_data.db"
        }
    }


def create_directories(config):
    """Utwórz potrzebne foldery"""
    base_path = src_path.parent

    directories = [
        config['paths']['screenshots'],
        config['paths']['templates'],
        config['paths']['models'],
        "data",
        "models/yolo",
        "models/custom",
        "tests"
    ]

    for directory in directories:
        dir_path = base_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)


def main():
    """Główna funkcja aplikacji"""
    print("WoW Automation - Krok 1: Podstawowe Przechwytywanie")
    print("=" * 50)

    # Załaduj konfigurację
    config = load_config()
    print("✓ Konfiguracja załadowana")

    # Utwórz potrzebne foldery
    create_directories(config)
    print("✓ Foldery utworzone")

    # Uruchom aplikację
    try:
        app = MainWindow(config)
        print("✓ Aplikacja uruchomiona")
        app.run()
    except KeyboardInterrupt:
        print("\nZatrzymano przez użytkownika")
    except Exception as e:
        print(f"Błąd aplikacji: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()