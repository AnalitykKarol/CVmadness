# src/gui/main_window.py
import os
import json
import tkinter as tk
import tkinter.simpledialog
from datetime import datetime
from tkinter import ttk, messagebox
from typing import Dict, Any

import cv2
import numpy as np
from PIL import Image, ImageTk
from capture.window_capture import WindowCapture
from input.input_controller import InputController
from ..automation.automation_manager import AutomationManager

class MainWindow:
    """Główne okno aplikacji"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.root = tk.Tk()
        self.root.title("WoW Automation - Computer Vision")
        self.config = config
        self.vision_engine = VisionEngine()

        # Initialize automation
        self.automation = AutomationManager(config, self.vision_engine)
        gui_config = config['gui']
        self.root.geometry(f"{gui_config['window_width']}x{gui_config['window_height']}")

        # Inicjalizacja komponentów
        self.window_capture = WindowCapture(config)
        self.input_controller = None
        self.vision_engine = None

        # GUI elementy
        self.preview_label = None
        self.status_var = tk.StringVar(value="Nie połączono z aplikacją")
        self.capture_active = False

        # Ustawienia użytkownika
        self.saved_colors = {}
        self.current_picked_color = None
        self.user_settings_file = "config/user_settings.json"

        # Setup GUI
        self.setup_ui()

        # Załaduj zapisane ustawienia
        self.load_user_settings()

        # Setup auto-save bindings
        self.setup_auto_save_bindings()

        # Start preview update
        self.update_preview()

    def load_user_settings(self):
        """Załaduj zapisane ustawienia użytkownika"""
        try:
            if os.path.exists(self.user_settings_file):
                with open(self.user_settings_file, 'r', encoding='utf-8') as f:
                    user_settings = json.load(f)

                # Załaduj okno target
                if 'target_window' in user_settings:
                    self.target_window_var.set(user_settings['target_window'])
                    print(f"✓ Załadowano okno: {user_settings['target_window']}")

                # Załaduj regiony OCR
                if 'ocr_regions' in user_settings:
                    ocr = user_settings['ocr_regions']
                    if 'current' in ocr:
                        self.ocr_x_var.set(str(ocr['current'].get('x', '120')))
                        self.ocr_y_var.set(str(ocr['current'].get('y', '65')))
                        self.ocr_w_var.set(str(ocr['current'].get('w', '80')))
                        self.ocr_h_var.set(str(ocr['current'].get('h', '20')))

                    if 'hp_region' in ocr:
                        self.hp_region = tuple(ocr['hp_region'])
                        print(f"✓ Załadowano HP region: {self.hp_region}")

                    if 'mana_region' in ocr:
                        self.mana_region = tuple(ocr['mana_region'])
                        print(f"✓ Załadowano Mana region: {self.mana_region}")

                    self.update_saved_regions_display()

                # Załaduj regiony kolorów
                if 'color_regions' in user_settings:
                    color = user_settings['color_regions']
                    if 'current' in color:
                        self.color_pick_x_var.set(str(color['current'].get('x', '150')))
                        self.color_pick_y_var.set(str(color['current'].get('y', '70')))
                        self.color_region_x_var.set(str(color['current'].get('region_x', '100')))
                        self.color_region_y_var.set(str(color['current'].get('region_y', '60')))
                        self.color_region_w_var.set(str(color['current'].get('region_w', '200')))
                        self.color_region_h_var.set(str(color['current'].get('region_h', '50')))
                        self.color_tolerance_var.set(str(color['current'].get('tolerance', '15')))

                # Załaduj zapisane kolory
                if 'saved_colors' in user_settings:
                    self.saved_colors = user_settings['saved_colors']
                    self.update_saved_colors_display()
                    print(f"✓ Załadowano {len(self.saved_colors)} zapisanych kolorów")

                # Załaduj ostatni wybrany kolor
                if 'current_picked_color' in user_settings and user_settings['current_picked_color']:
                    self.current_picked_color = user_settings['current_picked_color']
                    if self.current_picked_color:
                        self.current_color_var.set(f"RGB: {self.current_picked_color['rgb']}")
                        self.current_hsv_var.set(f"HSV: {self.current_picked_color['hsv']}")

                print("✓ Ustawienia użytkownika załadowane")

            else:
                print("ℹ Brak zapisanych ustawień - używam domyślnych")

        except Exception as e:
            print(f"⚠ Błąd ładowania ustawień: {e}")
            messagebox.showwarning("Uwaga", f"Nie udało się załadować ustawień: {e}")

    def save_user_settings(self):
        """Zapisz aktualne ustawienia użytkownika"""
        try:
            user_settings = {
                'target_window': self.target_window_var.get(),
                'ocr_regions': {
                    'current': {
                        'x': int(self.ocr_x_var.get()) if self.ocr_x_var.get().isdigit() else 120,
                        'y': int(self.ocr_y_var.get()) if self.ocr_y_var.get().isdigit() else 65,
                        'w': int(self.ocr_w_var.get()) if self.ocr_w_var.get().isdigit() else 80,
                        'h': int(self.ocr_h_var.get()) if self.ocr_h_var.get().isdigit() else 20,
                    }
                },
                'color_regions': {
                    'current': {
                        'x': int(self.color_pick_x_var.get()) if self.color_pick_x_var.get().isdigit() else 150,
                        'y': int(self.color_pick_y_var.get()) if self.color_pick_y_var.get().isdigit() else 70,
                        'region_x': int(self.color_region_x_var.get()) if self.color_region_x_var.get().isdigit() else 100,
                        'region_y': int(self.color_region_y_var.get()) if self.color_region_y_var.get().isdigit() else 60,
                        'region_w': int(self.color_region_w_var.get()) if self.color_region_w_var.get().isdigit() else 200,
                        'region_h': int(self.color_region_h_var.get()) if self.color_region_h_var.get().isdigit() else 50,
                        'tolerance': int(self.color_tolerance_var.get()) if self.color_tolerance_var.get().isdigit() else 15,
                    }
                },
                'saved_colors': self.saved_colors,
                'current_picked_color': self.current_picked_color
            }

            # Dodaj zapisane regiony HP/Mana jeśli istnieją
            if hasattr(self, 'hp_region'):
                user_settings['ocr_regions']['hp_region'] = list(self.hp_region)

            if hasattr(self, 'mana_region'):
                user_settings['ocr_regions']['mana_region'] = list(self.mana_region)

            # Upewnij się, że folder config istnieje
            os.makedirs('config', exist_ok=True)

            # Zapisz do pliku
            with open(self.user_settings_file, 'w', encoding='utf-8') as f:
                json.dump(user_settings, f, indent=2, ensure_ascii=False)

            print("✓ Ustawienia zapisane")

        except Exception as e:
            print(f"⚠ Błąd zapisywania ustawień: {e}")

    def auto_save_settings(self):
        """Automatycznie zapisz ustawienia po zmianie"""
        # Opóźnienie 1 sekunda żeby nie zapisywać przy każdym ruchu myszy
        if hasattr(self, '_save_timer'):
            self.root.after_cancel(self._save_timer)

        self._save_timer = self.root.after(1000, self.save_user_settings)

    def setup_auto_save_bindings(self):
        """Ustaw automatyczne zapisywanie przy zmianach w polach"""
        # Auto-save po zmianie okna target
        self.target_window_var.trace('w', lambda *args: self.auto_save_settings())

        # Auto-save po zmianie współrzędnych OCR
        self.ocr_x_var.trace('w', lambda *args: self.auto_save_settings())
        self.ocr_y_var.trace('w', lambda *args: self.auto_save_settings())
        self.ocr_w_var.trace('w', lambda *args: self.auto_save_settings())
        self.ocr_h_var.trace('w', lambda *args: self.auto_save_settings())

        # Auto-save po zmianie współrzędnych kolorów
        self.color_pick_x_var.trace('w', lambda *args: self.auto_save_settings())
        self.color_pick_y_var.trace('w', lambda *args: self.auto_save_settings())
        self.color_region_x_var.trace('w', lambda *args: self.auto_save_settings())
        self.color_region_y_var.trace('w', lambda *args: self.auto_save_settings())
        self.color_region_w_var.trace('w', lambda *args: self.auto_save_settings())
        self.color_region_h_var.trace('w', lambda *args: self.auto_save_settings())
        self.color_tolerance_var.trace('w', lambda *args: self.auto_save_settings())

    def setup_ui(self):
        """Skonfiguruj interfejs użytkownika"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="5")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=0, sticky=tk.W)

        # Target window controls
        target_frame = ttk.LabelFrame(main_frame, text="Wybór Okna", padding="5")
        target_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(target_frame, text="Okno docelowe:").grid(row=0, column=0, sticky=tk.W)
        self.target_window_var = tk.StringVar(value="World of Warcraft")
        target_entry = ttk.Entry(target_frame, textvariable=self.target_window_var, width=30)
        target_entry.grid(row=0, column=1, padx=(5, 0))

        ttk.Button(target_frame, text="Ustaw Okno",
                  command=self.set_target_window).grid(row=0, column=2, padx=(5, 0))

        # Window controls - Left side
        window_frame = ttk.LabelFrame(main_frame, text="Kontrola Okna", padding="5")
        window_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        ttk.Button(window_frame, text="Znajdź Okno",
                   command=self.find_window).grid(row=0, column=0, pady=2, sticky=tk.W)

        ttk.Button(window_frame, text="Start Przechwytywania",
                   command=self.start_capture).grid(row=1, column=0, pady=2, sticky=tk.W)

        ttk.Button(window_frame, text="Stop Przechwytywania",
                   command=self.stop_capture).grid(row=2, column=0, pady=2, sticky=tk.W)

        ttk.Button(window_frame, text="Zapisz Screenshot",
                   command=self.save_screenshot).grid(row=3, column=0, pady=2, sticky=tk.W)

        # Input controls
        self._setup_input_controls(window_frame)

        # Vision controls
        self._setup_vision_controls(window_frame)

        # Preview - Right side
        preview_frame = ttk.LabelFrame(main_frame, text="Podgląd", padding="5")
        preview_frame.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))

        self.preview_label = ttk.Label(preview_frame, text="Brak podglądu")
        self.preview_label.grid(row=0, column=0)

        # Results area - Bottom
        info_frame = ttk.LabelFrame(main_frame, text="Informacje / Wyniki CV", padding="5")
        info_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        self.info_text = tk.Text(info_frame, height=8, width=80)
        self.info_text.grid(row=0, column=0)

        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.info_text.configure(yscrollcommand=scrollbar.set)

        # Configure weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

    def _setup_input_controls(self, parent):
        """Skonfiguruj kontrolki inputu"""
        input_frame = ttk.LabelFrame(parent, text="Test Input", padding="5")
        input_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        # Click test
        ttk.Label(input_frame, text="Test Click (x, y):").grid(row=0, column=0, sticky=tk.W)
        self.click_x_var = tk.StringVar(value="400")
        self.click_y_var = tk.StringVar(value="300")

        click_frame = ttk.Frame(input_frame)
        click_frame.grid(row=1, column=0, sticky=tk.W)

        ttk.Entry(click_frame, textvariable=self.click_x_var, width=8).grid(row=0, column=0)
        ttk.Label(click_frame, text=",").grid(row=0, column=1, padx=2)
        ttk.Entry(click_frame, textvariable=self.click_y_var, width=8).grid(row=0, column=2)
        ttk.Button(click_frame, text="Click", command=self.test_click).grid(row=0, column=3, padx=(5, 0))

        # Key test
        ttk.Label(input_frame, text="Test Key:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        self.key_var = tk.StringVar(value="space")

        key_frame = ttk.Frame(input_frame)
        key_frame.grid(row=3, column=0, sticky=tk.W)

        ttk.Entry(key_frame, textvariable=self.key_var, width=15).grid(row=0, column=0)
        ttk.Button(key_frame, text="Send Key", command=self.test_key).grid(row=0, column=1, padx=(5, 0))

        # Test metod klawiszy
        test_frame = ttk.Frame(input_frame)
        test_frame.grid(row=4, column=0, sticky=tk.W, pady=(10, 0))

        ttk.Label(test_frame, text="Test metod:").grid(row=0, column=0, sticky=tk.W)
        ttk.Button(test_frame, text="Test Wszystkich Metod",
                   command=self.test_key_methods).grid(row=0, column=1, padx=(5, 0))

        # Wybór metody
        method_frame = ttk.Frame(input_frame)
        method_frame.grid(row=5, column=0, sticky=tk.W, pady=(5, 0))

        ttk.Label(method_frame, text="Metoda:").grid(row=0, column=0, sticky=tk.W)
        self.key_method_var = tk.StringVar(value="auto")
        method_combo = ttk.Combobox(method_frame, textvariable=self.key_method_var,
                                    values=["auto", "winapi", "pyautogui", "ctypes"], width=10)
        method_combo.grid(row=0, column=1, padx=(5, 0))

    def _setup_vision_controls(self, parent):
        """Skonfiguruj kontrolki computer vision"""
        vision_frame = ttk.LabelFrame(parent, text="Computer Vision", padding="5")
        vision_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        # Analiza obrazu
        ttk.Button(vision_frame, text="Analizuj Obraz",
                   command=self.analyze_current_image).grid(row=0, column=0, pady=2, sticky=tk.W)

        ttk.Button(vision_frame, text="Wizualizuj Wyniki",
                   command=self.visualize_results).grid(row=0, column=1, pady=2, sticky=tk.W, padx=(5, 0))

        # Template matching
        template_frame = ttk.Frame(vision_frame)
        template_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Label(template_frame, text="Template:").grid(row=0, column=0, sticky=tk.W)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.template_var, width=20, state="readonly")
        self.template_combo.grid(row=0, column=1, padx=(5, 0))

        ttk.Button(template_frame, text="Znajdź",
                   command=self.find_template).grid(row=0, column=2, padx=(5, 0))

        ttk.Button(template_frame, text="Znajdź + Klik",
                   command=self.find_and_click_template).grid(row=0, column=3, padx=(5, 0))

        # Tworzenie wzorców
        create_template_frame = ttk.LabelFrame(vision_frame, text="Utwórz Template", padding="5")
        create_template_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Label(create_template_frame, text="Region (x, y, width, height):").grid(row=0, column=0, sticky=tk.W)

        coords_frame = ttk.Frame(create_template_frame)
        coords_frame.grid(row=1, column=0, sticky=tk.W)

        self.template_x_var = tk.StringVar(value="100")
        self.template_y_var = tk.StringVar(value="100")
        self.template_w_var = tk.StringVar(value="50")
        self.template_h_var = tk.StringVar(value="50")

        ttk.Entry(coords_frame, textvariable=self.template_x_var, width=6).grid(row=0, column=0)
        ttk.Label(coords_frame, text=",").grid(row=0, column=1, padx=2)
        ttk.Entry(coords_frame, textvariable=self.template_y_var, width=6).grid(row=0, column=2)
        ttk.Label(coords_frame, text=",").grid(row=0, column=3, padx=2)
        ttk.Entry(coords_frame, textvariable=self.template_w_var, width=6).grid(row=0, column=4)
        ttk.Label(coords_frame, text=",").grid(row=0, column=5, padx=2)
        ttk.Entry(coords_frame, textvariable=self.template_h_var, width=6).grid(row=0, column=6)

        name_frame = ttk.Frame(create_template_frame)
        name_frame.grid(row=2, column=0, sticky=tk.W, pady=(5, 0))

        ttk.Label(name_frame, text="Nazwa:").grid(row=0, column=0)
        self.template_name_var = tk.StringVar(value="new_template")
        ttk.Entry(name_frame, textvariable=self.template_name_var, width=15).grid(row=0, column=1, padx=2)

        ttk.Label(name_frame, text="Kategoria:").grid(row=0, column=2, padx=(10, 0))
        self.template_category_var = tk.StringVar(value="ui")
        category_combo = ttk.Combobox(name_frame, textvariable=self.template_category_var,
                                      values=["ui", "buttons", "icons", "npc", "items", "spells"], width=10)
        category_combo.grid(row=0, column=3, padx=2)

        ttk.Button(name_frame, text="Utwórz Template",
                   command=self.create_template).grid(row=0, column=4, padx=(10, 0))

        # Template management
        manage_frame = ttk.Frame(create_template_frame)
        manage_frame.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))

        ttk.Button(manage_frame, text="Odśwież Listę",
                   command=self.update_template_list).grid(row=0, column=0)

        ttk.Button(manage_frame, text="Usuń Template",
                   command=self.delete_template).grid(row=0, column=1, padx=(5, 0))

        ttk.Button(manage_frame, text="Pokaż Template",
                   command=self.show_template).grid(row=0, column=2, padx=(5, 0))

        # Manual OCR controls
        manual_ocr_frame = ttk.LabelFrame(vision_frame, text="Ręczny OCR", padding="5")
        manual_ocr_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        # OCR Region input
        ttk.Label(manual_ocr_frame, text="Region OCR (x, y, width, height):").grid(row=0, column=0, sticky=tk.W)

        ocr_coords_frame = ttk.Frame(manual_ocr_frame)
        ocr_coords_frame.grid(row=1, column=0, sticky=tk.W)

        self.ocr_x_var = tk.StringVar(value="120")
        self.ocr_y_var = tk.StringVar(value="65")
        self.ocr_w_var = tk.StringVar(value="80")
        self.ocr_h_var = tk.StringVar(value="20")

        ttk.Entry(ocr_coords_frame, textvariable=self.ocr_x_var, width=6).grid(row=0, column=0)
        ttk.Label(ocr_coords_frame, text=",").grid(row=0, column=1, padx=2)
        ttk.Entry(ocr_coords_frame, textvariable=self.ocr_y_var, width=6).grid(row=0, column=2)
        ttk.Label(ocr_coords_frame, text=",").grid(row=0, column=3, padx=2)
        ttk.Entry(ocr_coords_frame, textvariable=self.ocr_w_var, width=6).grid(row=0, column=4)
        ttk.Label(ocr_coords_frame, text=",").grid(row=0, column=5, padx=2)
        ttk.Entry(ocr_coords_frame, textvariable=self.ocr_h_var, width=6).grid(row=0, column=6)

        # OCR buttons
        ocr_buttons_frame = ttk.Frame(manual_ocr_frame)
        ocr_buttons_frame.grid(row=2, column=0, sticky=tk.W, pady=(5, 0))

        ttk.Button(ocr_buttons_frame, text="Test OCR",
                   command=self.test_manual_ocr).grid(row=0, column=0)

        ttk.Button(ocr_buttons_frame, text="HP Region",
                   command=self.set_hp_region).grid(row=0, column=1, padx=(5, 0))

        ttk.Button(ocr_buttons_frame, text="Mana Region",
                   command=self.set_mana_region).grid(row=0, column=2, padx=(5, 0))

        ttk.Button(ocr_buttons_frame, text="Pokaż Region",
                   command=self.show_ocr_region).grid(row=0, column=3, padx=(5, 0))

        # Saved regions
        ttk.Label(manual_ocr_frame, text="Zapisane regiony:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        self.saved_regions_var = tk.StringVar(value="HP: brak, Mana: brak")
        ttk.Label(manual_ocr_frame, textvariable=self.saved_regions_var, foreground="blue").grid(row=4, column=0, sticky=tk.W)

        # Manual Color Detection
        color_frame = ttk.LabelFrame(vision_frame, text="Ręczny wybór kolorów", padding="5")
        color_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        # Color picker coordinates
        ttk.Label(color_frame, text="Kliknij punkt aby pobrać kolor (x, y):").grid(row=0, column=0, sticky=tk.W)

        color_coords_frame = ttk.Frame(color_frame)
        color_coords_frame.grid(row=1, column=0, sticky=tk.W)

        self.color_pick_x_var = tk.StringVar(value="150")
        self.color_pick_y_var = tk.StringVar(value="70")

        ttk.Entry(color_coords_frame, textvariable=self.color_pick_x_var, width=8).grid(row=0, column=0)
        ttk.Label(color_coords_frame, text=",").grid(row=0, column=1, padx=2)
        ttk.Entry(color_coords_frame, textvariable=self.color_pick_y_var, width=8).grid(row=0, column=2)

        ttk.Button(color_coords_frame, text="Pobierz Kolor",
                   command=self.pick_color_from_point).grid(row=0, column=3, padx=(5, 0))

        # Color tolerance
        ttk.Label(color_frame, text="Tolerancja koloru (0-50):").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        self.color_tolerance_var = tk.StringVar(value="15")
        ttk.Entry(color_frame, textvariable=self.color_tolerance_var, width=8).grid(row=3, column=0, sticky=tk.W)

        # Current color display
        self.current_color_var = tk.StringVar(value="RGB: nie wybrano")
        ttk.Label(color_frame, textvariable=self.current_color_var, foreground="blue").grid(row=4, column=0, sticky=tk.W, pady=(5, 0))

        self.current_hsv_var = tk.StringVar(value="HSV: nie wybrano")
        ttk.Label(color_frame, textvariable=self.current_hsv_var, foreground="green").grid(row=5, column=0, sticky=tk.W)

        # Color region definition
        ttk.Label(color_frame, text="Region do skanowania (x, y, w, h):").grid(row=6, column=0, sticky=tk.W, pady=(10, 0))

        color_region_frame = ttk.Frame(color_frame)
        color_region_frame.grid(row=7, column=0, sticky=tk.W)

        self.color_region_x_var = tk.StringVar(value="100")
        self.color_region_y_var = tk.StringVar(value="60")
        self.color_region_w_var = tk.StringVar(value="200")
        self.color_region_h_var = tk.StringVar(value="50")

        ttk.Entry(color_region_frame, textvariable=self.color_region_x_var, width=6).grid(row=0, column=0)
        ttk.Label(color_region_frame, text=",").grid(row=0, column=1, padx=2)
        ttk.Entry(color_region_frame, textvariable=self.color_region_y_var, width=6).grid(row=0, column=2)
        ttk.Label(color_region_frame, text=",").grid(row=0, column=3, padx=2)
        ttk.Entry(color_region_frame, textvariable=self.color_region_w_var, width=6).grid(row=0, column=4)
        ttk.Label(color_region_frame, text=",").grid(row=0, column=5, padx=2)
        ttk.Entry(color_region_frame, textvariable=self.color_region_h_var, width=6).grid(row=0, column=6)

        # Color test buttons
        color_buttons_frame = ttk.Frame(color_frame)
        color_buttons_frame.grid(row=8, column=0, sticky=tk.W, pady=(10, 0))

        ttk.Button(color_buttons_frame, text="Test Kolor w Regionie",
                   command=self.test_color_in_region).grid(row=0, column=0)

        ttk.Button(color_buttons_frame, text="Zapisz jako HP",
                   command=self.save_hp_color).grid(row=0, column=1, padx=(5, 0))

        ttk.Button(color_buttons_frame, text="Zapisz jako Mana",
                   command=self.save_mana_color).grid(row=0, column=2, padx=(5, 0))

        ttk.Button(color_buttons_frame, text="Zapisz Niestandardowy",
                   command=self.save_custom_color).grid(row=0, column=3, padx=(5, 0))

        # Saved colors display
        ttk.Label(color_frame, text="Zapisane kolory:").grid(row=9, column=0, sticky=tk.W, pady=(10, 0))
        self.saved_colors_var = tk.StringVar(value="HP: brak, Mana: brak")
        ttk.Label(color_frame, textvariable=self.saved_colors_var, foreground="purple").grid(row=10, column=0, sticky=tk.W)

        # Test all saved
        ttk.Button(color_frame, text="Test Wszystkich Zapisanych Kolorów",
                   command=self.test_all_saved_colors).grid(row=11, column=0, pady=(10, 0), sticky=tk.W)

    # ===== WINDOW AND TARGET METHODS =====

    def set_target_window(self):
        """Ustaw okno docelowe"""
        window_title = self.target_window_var.get().strip()
        if window_title:
            if self.window_capture.set_target_window(window_title):
                messagebox.showinfo("Sukces", f"Okno ustawione: {window_title}")
                self.auto_save_settings()
            else:
                messagebox.showerror("Błąd", f"Nie znaleziono okna: {window_title}")
        else:
            messagebox.showerror("Błąd", "Wprowadź nazwę okna")

    def find_window(self):
        """Znajdź okno docelowe"""
        if self.window_capture.find_target_window():
            window_info = self.window_capture.get_window_info()
            self.status_var.set(f"Połączono: {window_info['title']}")

            # Inicjalizuj input controller
            coord_manager = self.window_capture.get_coordinate_manager()
            self.input_controller = InputController(coord_manager, self.config)

            self.update_window_info()
            messagebox.showinfo("Sukces", "Znaleziono okno docelowe!")
        else:
            self.status_var.set("Nie znaleziono okna")
            messagebox.showerror("Błąd", "Nie znaleziono okna docelowego.\nUpewnij się, że aplikacja jest uruchomiona.")

    def start_capture(self):
        """Rozpocznij przechwytywanie"""
        if not self.window_capture.target_window:
            messagebox.showerror("Błąd", "Najpierw znajdź okno!")
            return

        fps = self.config['gui']['preview_fps']
        self.window_capture.start_continuous_capture(fps=fps)
        self.capture_active = True

        window_info = self.window_capture.get_window_info()
        self.status_var.set(f"Przechwytywanie aktywne: {window_info['title']}")

    def stop_capture(self):
        """Zatrzymaj przechwytywanie"""
        self.window_capture.stop_continuous_capture()
        self.capture_active = False

        if self.window_capture.target_window:
            window_info = self.window_capture.get_window_info()
            self.status_var.set(f"Połączono: {window_info['title']}")
        else:
            self.status_var.set("Nie połączono")

    def save_screenshot(self):
        """Zapisz screenshot"""
        if not self.window_capture.target_window:
            messagebox.showerror("Błąd", "Najpierw znajdź okno!")
            return

        screenshot = self.window_capture.capture_window_screenshot()
        if screenshot is not None:
            screenshots_dir = self.config['paths']['screenshots']
            os.makedirs(screenshots_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"screenshot_{timestamp}.png"
            default_path = os.path.join(screenshots_dir, default_filename)

            screenshot_rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(screenshot_rgb)
            im.save(default_path)
            print(f"✓ Screenshot zapisany: {default_path}")
        else:
            messagebox.showerror("Błąd", "Nie udało się zrobić screena.")

    # ===== INPUT TESTING METHODS =====

    def test_click(self):
        """Test kliknięcia"""
        if not self.input_controller:
            messagebox.showerror("Błąd", "Najpierw znajdź okno!")
            return

        try:
            x = int(self.click_x_var.get())
            y = int(self.click_y_var.get())

            if self.input_controller.click(x, y):
                messagebox.showinfo("Sukces", f"Kliknięto w ({x}, {y})")
            else:
                messagebox.showerror("Błąd", "Nie udało się kliknąć")

        except ValueError:
            messagebox.showerror("Błąd", "Wprowadź prawidłowe współrzędne (liczby)")

    def test_key(self):
        """Test klawisza"""
        if not self.input_controller:
            messagebox.showerror("Błąd", "Najpierw znajdź okno!")
            return

        key = self.key_var.get().strip()
        method = self.key_method_var.get()

        if key:
            if self.input_controller.send_key(key, method):
                messagebox.showinfo("Sukces", f"Wysłano klawisz: {key} (metoda: {method})")
            else:
                messagebox.showerror("Błąd", "Nie udało się wysłać klawisza")

    def test_key_methods(self):
        """Przetestuj wszystkie metody wysyłania klawiszy"""
        if not self.input_controller:
            messagebox.showerror("Błąd", "Najpierw znajdź okno!")
            return

        test_key = self.key_var.get().strip() or "space"
        results = self.input_controller.test_all_key_methods(test_key)

        result_text = f"Wyniki testów dla klawisza '{test_key}':\n\n"
        for method, success in results.items():
            status = "✓ DZIAŁA" if success else "✗ NIE DZIAŁA"
            result_text += f"{method.upper()}: {status}\n"

        result_text += "\nSpróbuj użyć metody która działa w dropdownie 'Metoda'"
        messagebox.showinfo("Test Metod Klawiszy", result_text)

    # ===== OCR METHODS =====

    def test_manual_ocr(self):
        """Test OCR w ręcznie wybranym regionie"""
        if not self.vision_engine:
            messagebox.showerror("Błąd", "Najpierw uruchom Vision Engine")
            return

        try:
            x = int(self.ocr_x_var.get())
            y = int(self.ocr_y_var.get())
            w = int(self.ocr_w_var.get())
            h = int(self.ocr_h_var.get())

            screenshot = self.window_capture.capture_window_screenshot()
            if screenshot is not None:
                img_height, img_width = screenshot.shape[:2]
                if x + w > img_width or y + h > img_height:
                    messagebox.showerror("Błąd", f"Region wykracza poza obraz\nObraz: {img_width}x{img_height}")
                    return

                roi = screenshot[y:y + h, x:x + w]
                ocr_results = self.vision_engine.test_manual_ocr_region(roi, x, y, w, h)

                result_text = f"OCR Region ({x}, {y}, {w}, {h}):\n\n"
                for config_name, text in ocr_results.items():
                    result_text += f"{config_name}: '{text}'\n"

                messagebox.showinfo("OCR Results", result_text)

                self.last_manual_ocr = {
                    'region': (x, y, w, h),
                    'results': ocr_results
                }
            else:
                messagebox.showerror("Błąd", "Brak obrazu")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe współrzędne")
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd OCR: {e}")

    def set_hp_region(self):
        """Zapisz aktualny region jako HP region"""
        try:
            x = int(self.ocr_x_var.get())
            y = int(self.ocr_y_var.get())
            w = int(self.ocr_w_var.get())
            h = int(self.ocr_h_var.get())

            self.hp_region = (x, y, w, h)
            self.update_saved_regions_display()
            self.auto_save_settings()
            messagebox.showinfo("Sukces", f"Region HP zapisany: ({x}, {y}, {w}, {h})")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe współrzędne")

    def set_mana_region(self):
        """Zapisz aktualny region jako Mana region"""
        try:
            x = int(self.ocr_x_var.get())
            y = int(self.ocr_y_var.get())
            w = int(self.ocr_w_var.get())
            h = int(self.ocr_h_var.get())

            self.mana_region = (x, y, w, h)
            self.update_saved_regions_display()
            self.auto_save_settings()
            messagebox.showinfo("Sukces", f"Region Mana zapisany: ({x}, {y}, {w}, {h})")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe współrzędne")

    def update_saved_regions_display(self):
        """Aktualizuj wyświetlanie zapisanych regionów"""
        hp_text = f"HP: {getattr(self, 'hp_region', 'brak')}"
        mana_text = f"Mana: {getattr(self, 'mana_region', 'brak')}"
        self.saved_regions_var.set(f"{hp_text}, {mana_text}")

    def show_ocr_region(self):
        """Pokaż region OCR na screenshocie"""
        try:
            x = int(self.ocr_x_var.get())
            y = int(self.ocr_y_var.get())
            w = int(self.ocr_w_var.get())
            h = int(self.ocr_h_var.get())

            screenshot = self.window_capture.capture_window_screenshot()
            if screenshot is not None:
                vis_image = screenshot.copy()
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 255, 255), 2)
                cv2.putText(vis_image, f"OCR Region ({x},{y},{w},{h})",
                            (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"ocr_region_{timestamp}.png"
                filepath = os.path.join(self.config['paths']['screenshots'], filename)

                os.makedirs(self.config['paths']['screenshots'], exist_ok=True)
                cv2.imwrite(filepath, vis_image)

                messagebox.showinfo("Region OCR", f"Region zaznaczony i zapisany: {filename}")
            else:
                messagebox.showerror("Błąd", "Brak obrazu")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe współrzędne")
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd: {e}")

    # ===== COLOR METHODS =====

    def pick_color_from_point(self):
        """Pobierz kolor z określonego punktu na screenshocie"""
        try:
            x = int(self.color_pick_x_var.get())
            y = int(self.color_pick_y_var.get())

            screenshot = self.window_capture.capture_window_screenshot()
            if screenshot is not None:
                img_height, img_width = screenshot.shape[:2]
                if x >= img_width or y >= img_height or x < 0 or y < 0:
                    messagebox.showerror("Błąd", f"Punkt poza obrazem\nObraz: {img_width}x{img_height}")
                    return

                bgr_color = screenshot[y, x]
                rgb_color = (int(bgr_color[2]), int(bgr_color[1]), int(bgr_color[0]))

                hsv_pixel = cv2.cvtColor(np.uint8([[bgr_color]]), cv2.COLOR_BGR2HSV)[0][0]
                hsv_color = (int(hsv_pixel[0]), int(hsv_pixel[1]), int(hsv_pixel[2]))

                self.current_picked_color = {
                    'rgb': rgb_color,
                    'bgr': (int(bgr_color[0]), int(bgr_color[1]), int(bgr_color[2])),
                    'hsv': hsv_color,
                    'point': (x, y)
                }

                self.current_color_var.set(f"RGB: {rgb_color}")
                self.current_hsv_var.set(f"HSV: {hsv_color}")

                self.auto_save_settings()

                messagebox.showinfo("Kolor pobrany",
                                  f"Punkt ({x}, {y})\nRGB: {rgb_color}\nHSV: {hsv_color}")
            else:
                messagebox.showerror("Błąd", "Brak obrazu")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe współrzędne")
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd pobierania koloru: {e}")

    def test_color_in_region(self):
        """Test wykrywania aktualnego koloru w określonym regionie"""
        if not self.current_picked_color:
            messagebox.showerror("Błąd", "Najpierw pobierz kolor!")
            return

        if not self.vision_engine:
            messagebox.showerror("Błąd", "Vision Engine nie jest załadowany")
            return

        try:
            rx = int(self.color_region_x_var.get())
            ry = int(self.color_region_y_var.get())
            rw = int(self.color_region_w_var.get())
            rh = int(self.color_region_h_var.get())
            tolerance = int(self.color_tolerance_var.get())

            screenshot = self.window_capture.capture_window_screenshot()
            if screenshot is not None:
                results = self.vision_engine.detect_custom_color_in_region(
                    screenshot,
                    self.current_picked_color,
                    (rx, ry, rw, rh),
                    tolerance
                )

                if results['detected_areas']:
                    result_text = f"Znaleziono {len(results['detected_areas'])} obszarów z kolorem!\n\n"
                    for i, area in enumerate(results['detected_areas'][:5]):
                        result_text += f"Obszar {i+1}: ({area['x']}, {area['y']}) {area['width']}x{area['height']}\n"
                        result_text += f"  Pokrycie: {area['coverage']:.1f}%\n"
                else:
                    result_text = "Nie znaleziono koloru w regionie"

                result_text += f"\nParametry:\nKolor HSV: {self.current_picked_color['hsv']}\nTolerance: {tolerance}\nRegion: ({rx}, {ry}, {rw}, {rh})"

                messagebox.showinfo("Test koloru", result_text)
                self.save_color_detection_visualization(screenshot, results, (rx, ry, rw, rh))

            else:
                messagebox.showerror("Błąd", "Brak obrazu")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe wartości")
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd testu koloru: {e}")

    def save_hp_color(self):
        """Zapisz aktualny kolor jako kolor HP"""
        if not self.current_picked_color:
            messagebox.showerror("Błąd", "Najpierw pobierz kolor!")
            return

        try:
            region = (
                int(self.color_region_x_var.get()),
                int(self.color_region_y_var.get()),
                int(self.color_region_w_var.get()),
                int(self.color_region_h_var.get())
            )
            tolerance = int(self.color_tolerance_var.get())

            self.saved_colors['HP'] = {
                'color': self.current_picked_color.copy(),
                'region': region,
                'tolerance': tolerance
            }

            self.update_saved_colors_display()
            self.auto_save_settings()
            messagebox.showinfo("Sukces", f"Kolor HP zapisany!\nHSV: {self.current_picked_color['hsv']}")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe wartości")

    def save_mana_color(self):
        """Zapisz aktualny kolor jako kolor Mana"""
        if not self.current_picked_color:
            messagebox.showerror("Błąd", "Najpierw pobierz kolor!")
            return

        try:
            region = (
                int(self.color_region_x_var.get()),
                int(self.color_region_y_var.get()),
                int(self.color_region_w_var.get()),
                int(self.color_region_h_var.get())
            )
            tolerance = int(self.color_tolerance_var.get())

            self.saved_colors['Mana'] = {
                'color': self.current_picked_color.copy(),
                'region': region,
                'tolerance': tolerance
            }

            self.update_saved_colors_display()
            self.auto_save_settings()
            messagebox.showinfo("Sukces", f"Kolor Mana zapisany!\nHSV: {self.current_picked_color['hsv']}")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe wartości")

    def save_custom_color(self):
        """Zapisz niestandardowy kolor"""
        if not self.current_picked_color:
            messagebox.showerror("Błąd", "Najpierw pobierz kolor!")
            return

        name = tk.simpledialog.askstring("Nazwa koloru", "Podaj nazwę dla tego koloru:")
        if not name:
            return

        try:
            region = (
                int(self.color_region_x_var.get()),
                int(self.color_region_y_var.get()),
                int(self.color_region_w_var.get()),
                int(self.color_region_h_var.get())
            )
            tolerance = int(self.color_tolerance_var.get())

            self.saved_colors[name] = {
                'color': self.current_picked_color.copy(),
                'region': region,
                'tolerance': tolerance
            }

            self.update_saved_colors_display()
            self.auto_save_settings()
            messagebox.showinfo("Sukces", f"Kolor '{name}' zapisany!\nHSV: {self.current_picked_color['hsv']}")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe wartości")

    def update_saved_colors_display(self):
        """Aktualizuj wyświetlanie zapisanych kolorów"""
        if not self.saved_colors:
            self.saved_colors_var.set("Brak zapisanych kolorów")
            return

        color_list = []
        for name, data in self.saved_colors.items():
            hsv = data['color']['hsv']
            color_list.append(f"{name}: HSV{hsv}")

        self.saved_colors_var.set(", ".join(color_list))

    def test_all_saved_colors(self):
        """Test wszystkich zapisanych kolorów"""
        if not self.saved_colors:
            messagebox.showwarning("Uwaga", "Brak zapisanych kolorów")
            return

        if not self.vision_engine:
            messagebox.showerror("Błąd", "Vision Engine nie jest załadowany")
            return

        screenshot = self.window_capture.capture_window_screenshot()
        if screenshot is not None:
            all_results = {}

            for name, data in self.saved_colors.items():
                results = self.vision_engine.detect_custom_color_in_region(
                    screenshot,
                    data['color'],
                    data['region'],
                    data['tolerance']
                )
                all_results[name] = results

            result_text = "Wyniki wszystkich kolorów:\n\n"
            for name, results in all_results.items():
                count = len(results['detected_areas'])
                result_text += f"{name}: {count} obszarów\n"
                if count > 0:
                    largest = max(results['detected_areas'], key=lambda x: x['area'])
                    result_text += f"  Największy: {largest['coverage']:.1f}% pokrycia\n"

            messagebox.showinfo("Test wszystkich kolorów", result_text)
            self.save_all_colors_visualization(screenshot, all_results)
        else:
            messagebox.showerror("Błąd", "Brak obrazu")

    def save_color_detection_visualization(self, image, results, region):
        """Zapisz wizualizację wykrywania koloru"""
        try:
            vis_image = image.copy()

            # Narysuj region skanowania
            rx, ry, rw, rh = region
            cv2.rectangle(vis_image, (rx, ry), (rx + rw, ry + rh), (255, 255, 0), 2)

            # Narysuj wykryte obszary
            for area in results['detected_areas']:
                cv2.rectangle(vis_image,
                            (area['x'], area['y']),
                            (area['x'] + area['width'], area['y'] + area['height']),
                            (0, 255, 0), 2)
                cv2.putText(vis_image, f"{area['coverage']:.1f}%",
                           (area['x'], area['y'] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"color_detection_{timestamp}.png"
            filepath = os.path.join(self.config['paths']['screenshots'], filename)

            cv2.imwrite(filepath, vis_image)
            print(f"Wizualizacja koloru zapisana: {filename}")

        except Exception as e:
            print(f"Błąd zapisywania wizualizacji: {e}")

    def save_all_colors_visualization(self, image, all_results):
        """Zapisz wizualizację wszystkich kolorów"""
        try:
            vis_image = image.copy()
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]

            for i, (name, results) in enumerate(all_results.items()):
                color = colors[i % len(colors)]

                for area in results['detected_areas']:
                    cv2.rectangle(vis_image,
                                (area['x'], area['y']),
                                (area['x'] + area['width'], area['y'] + area['height']),
                                color, 2)
                    cv2.putText(vis_image, name,
                               (area['x'], area['y'] - 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"all_colors_{timestamp}.png"
            filepath = os.path.join(self.config['paths']['screenshots'], filename)

            cv2.imwrite(filepath, vis_image)
            messagebox.showinfo("Wizualizacja", f"Wszystkie kolory zapisane: {filename}")

        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd zapisywania: {e}")

    # ===== COMPUTER VISION METHODS =====

    def analyze_current_image(self):
        """Analizuj aktualny obraz używając Computer Vision"""
        if not self.vision_engine:
            try:
                from vision.vision_engine import VisionEngine
                self.vision_engine = VisionEngine(self.config)
            except ImportError as e:
                messagebox.showerror("Błąd", f"Nie można załadować Vision Engine: {e}")
                return

        screenshot = self.window_capture.capture_window_screenshot()
        if screenshot is not None:
            try:
                results = self.vision_engine.analyze_image(screenshot)
                self.last_cv_results = results

                info_text = "=== ANALIZA COMPUTER VISION ===\n"
                info_text += f"Obraz: {screenshot.shape[1]}x{screenshot.shape[0]} pikseli\n\n"

                # Templates
                if results['templates']:
                    info_text += "ZNALEZIONE WZORCE:\n"
                    for template_name, matches in results['templates'].items():
                        info_text += f"• {template_name}: {len(matches)} dopasowań\n"
                        for match in matches[:3]:
                            info_text += f"  └─ Pozycja: ({match['center_x']}, {match['center_y']}), Pewność: {match['confidence']:.2f}\n"
                    info_text += "\n"
                else:
                    info_text += "WZORCE: Brak dopasowań\n\n"

                # HP/Mana bars
                health_count = len(results['colors']['health_bars'])
                mana_count = len(results['colors']['mana_bars'])
                info_text += f"PASKI STATUSU:\n• HP: {health_count} pasków\n• Mana: {mana_count} pasków\n"

                if health_count > 0:
                    for i, bar in enumerate(results['colors']['health_bars'][:3]):
                        info_text += f"  └─ HP{i + 1}: ({bar['center_x']}, {bar['center_y']}) {bar['width']}x{bar['height']}px\n"

                if mana_count > 0:
                    for i, bar in enumerate(results['colors']['mana_bars'][:3]):
                        info_text += f"  └─ Mana{i + 1}: ({bar['center_x']}, {bar['center_y']}) {bar['width']}x{bar['height']}px\n"

                info_text += "\n"

                # Text (OCR)
                if results['text']:
                    info_text += f"ROZPOZNANY TEKST: {len(results['text'])} regionów\n"
                    for text_info in results['text'][:5]:
                        clean_text = text_info['text'].replace('\n', ' ').strip()
                        if clean_text:
                            info_text += f"• '{clean_text}' na ({text_info['x']}, {text_info['y']})\n"
                else:
                    info_text += "TEKST: Brak rozpoznanego tekstu\n"

                info_text += "\n"

                # UI Elements
                ui_count = len(results['ui_elements']['elements'])
                info_text += f"ELEMENTY UI: {ui_count} wykrytych\n"

                button_count = sum(1 for elem in results['ui_elements']['elements'] if elem.get('probable_type') == 'button')
                panel_count = sum(1 for elem in results['ui_elements']['elements'] if elem.get('probable_type') == 'panel')

                if button_count > 0:
                    info_text += f"• Przyciski: {button_count}\n"
                if panel_count > 0:
                    info_text += f"• Panele: {panel_count}\n"

                info_text += f"\n=== UŻYJ 'Wizualizuj Wyniki' ABY ZOBACZYĆ NA OBRAZIE ==="

                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(1.0, info_text)

                self.update_template_list()
                messagebox.showinfo("Analiza", "Analiza CV zakończona - sprawdź wyniki poniżej!")

            except Exception as e:
                messagebox.showerror("Błąd CV", f"Błąd podczas analizy: {e}")
                import traceback
                traceback.print_exc()
        else:
            messagebox.showerror("Błąd", "Brak obrazu do analizy")

    def visualize_results(self):
        """Pokaż wyniki CV na obrazie"""
        if not hasattr(self, 'last_cv_results') or not self.vision_engine:
            messagebox.showwarning("Uwaga", "Najpierw wykonaj analizę obrazu")
            return

        screenshot = self.window_capture.capture_window_screenshot()
        if screenshot is not None:
            try:
                vis_image = self.vision_engine.visualize_results(screenshot, self.last_cv_results)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                vis_filename = f"cv_analysis_{timestamp}.png"
                vis_path = os.path.join(self.config['paths']['screenshots'], vis_filename)

                os.makedirs(self.config['paths']['screenshots'], exist_ok=True)
                cv2.imwrite(vis_path, vis_image)

                messagebox.showinfo("Wizualizacja", f"Analiza CV zapisana: {vis_filename}")

            except Exception as e:
                messagebox.showerror("Błąd", f"Błąd wizualizacji: {e}")

    # ===== TEMPLATE METHODS =====

    def update_template_list(self):
        """Aktualizuj listę dostępnych templates"""
        if self.vision_engine:
            try:
                templates = self.vision_engine.get_template_matcher().get_template_list()
                self.template_combo['values'] = templates

                if templates and not self.template_var.get():
                    self.template_var.set(templates[0])

            except Exception as e:
                print(f"Błąd aktualizacji listy templates: {e}")

    def find_template(self):
        """Znajdź wybrany template"""
        if not self.vision_engine:
            messagebox.showerror("Błąd", "Najpierw uruchom analizę obrazu")
            return

        template_name = self.template_var.get()
        if not template_name:
            messagebox.showerror("Błąd", "Wybierz template z listy")
            return

        screenshot = self.window_capture.capture_window_screenshot()
        if screenshot is not None:
            try:
                matches = self.vision_engine.get_template_matcher().find_template(screenshot, template_name)

                if matches:
                    match = matches[0]
                    info = f"Znaleziono '{template_name}':\n"
                    info += f"Pozycja: ({match['center_x']}, {match['center_y']})\n"
                    info += f"Pewność: {match['confidence']:.2f}\n"
                    info += f"Rozmiar: {match['width']}x{match['height']}px"

                    messagebox.showinfo("Template Znaleziony", info)

                    self.click_x_var.set(str(match['center_x']))
                    self.click_y_var.set(str(match['center_y']))

                else:
                    messagebox.showwarning("Nie znaleziono", f"Template '{template_name}' nie został znaleziony na obrazie")

            except Exception as e:
                messagebox.showerror("Błąd", f"Błąd podczas szukania template: {e}")

    def find_and_click_template(self):
        """Znajdź template i automatycznie kliknij"""
        if not self.vision_engine or not self.input_controller:
            messagebox.showerror("Błąd", "Najpierw znajdź okno i uruchom analizę")
            return

        template_name = self.template_var.get()
        if not template_name:
            messagebox.showerror("Błąd", "Wybierz template z listy")
            return

        screenshot = self.window_capture.capture_window_screenshot()
        if screenshot is not None:
            try:
                success = self.vision_engine.find_and_click_template(
                    screenshot, template_name, self.input_controller
                )

                if success:
                    messagebox.showinfo("Sukces", f"Znaleziono i kliknięto template '{template_name}'")
                else:
                    messagebox.showwarning("Nie znaleziono", f"Template '{template_name}' nie został znaleziony")

            except Exception as e:
                messagebox.showerror("Błąd", f"Błąd podczas znajdowania i klikania: {e}")

    def create_template(self):
        """Utwórz nowy template z aktualnego obrazu"""
        try:
            x = int(self.template_x_var.get())
            y = int(self.template_y_var.get())
            w = int(self.template_w_var.get())
            h = int(self.template_h_var.get())
            name = self.template_name_var.get().strip()
            category = self.template_category_var.get().strip()

            if not name:
                messagebox.showerror("Błąd", "Podaj nazwę template")
                return

            if not category:
                category = "ui"

            if not self.vision_engine:
                from vision.vision_engine import VisionEngine
                self.vision_engine = VisionEngine(self.config)

            screenshot = self.window_capture.capture_window_screenshot()
            if screenshot is not None:
                img_height, img_width = screenshot.shape[:2]
                if x < 0 or y < 0 or x + w > img_width or y + h > img_height:
                    messagebox.showerror("Błąd", f"Region wykracza poza obraz\nObraz: {img_width}x{img_height}, Region: ({x},{y},{w},{h})")
                    return

                success = self.vision_engine.create_template_from_region(
                    screenshot, x, y, w, h, name, category,
                    f"Created from GUI at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                if success:
                    messagebox.showinfo("Sukces", f"Template '{category}/{name}' został utworzony i zapisany")
                    self.update_template_list()
                    self.template_name_var.set("new_template")
                else:
                    messagebox.showerror("Błąd", "Nie udało się utworzyć template")
            else:
                messagebox.showerror("Błąd", "Brak obrazu do utworzenia template")

        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowe współrzędne - wprowadź liczby")
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd podczas tworzenia template: {e}")

    def delete_template(self):
        """Usuń wybrany template"""
        if not self.vision_engine:
            messagebox.showerror("Błąd", "Vision Engine nie jest załadowany")
            return

        template_name = self.template_var.get()
        if not template_name:
            messagebox.showerror("Błąd", "Wybierz template do usunięcia")
            return

        if messagebox.askyesno("Potwierdzenie", f"Czy na pewno chcesz usunąć template '{template_name}'?"):
            try:
                success = self.vision_engine.get_template_matcher().delete_template(template_name)

                if success:
                    messagebox.showinfo("Sukces", f"Template '{template_name}' został usunięty")
                    self.update_template_list()
                    self.template_var.set("")
                else:
                    messagebox.showerror("Błąd", "Nie udało się usunąć template")

            except Exception as e:
                messagebox.showerror("Błąd", f"Błąd podczas usuwania template: {e}")

    def show_template(self):
        """Pokaż wybrany template w nowym oknie"""
        if not self.vision_engine:
            messagebox.showerror("Błąd", "Vision Engine nie jest załadowany")
            return

        template_name = self.template_var.get()
        if not template_name:
            messagebox.showerror("Błąd", "Wybierz template do wyświetlenia")
            return

        try:
            template_matcher = self.vision_engine.get_template_matcher()

            if template_name in template_matcher.templates:
                template_image = template_matcher.templates[template_name]

                template_window = tk.Toplevel(self.root)
                template_window.title(f"Template: {template_name}")

                img_rgb = cv2.cvtColor(template_image, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb)
                img_tk = ImageTk.PhotoImage(img_pil)

                label = tk.Label(template_window, image=img_tk)
                label.image = img_tk
                label.pack(padx=10, pady=10)

                info = template_matcher.template_info.get(template_name, {})
                info_text = f"Nazwa: {template_name}\n"
                info_text += f"Rozmiar: {template_image.shape[1]}x{template_image.shape[0]}px\n"
                info_text += f"Próg pewności: {info.get('confidence_threshold', 'N/A')}\n"
                info_text += f"Opis: {info.get('description', 'Brak opisu')}"

                info_label = tk.Label(template_window, text=info_text, justify=tk.LEFT)
                info_label.pack(padx=10, pady=(0, 10))

            else:
                messagebox.showerror("Błąd", f"Template '{template_name}' nie został znaleziony")

        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd podczas wyświetlania template: {e}")

    # ===== UTILITY METHODS =====

    def update_window_info(self):
        """Aktualizuj informacje o oknie"""
        window_info = self.window_capture.get_window_info()
        if window_info:
            capture_method = "N/A"
            if hasattr(self.window_capture, 'get_capture_method_info'):
                capture_method = self.window_capture.get_capture_method_info()

            text = f"""INFORMACJE O OKNIE:
Tytuł: {window_info.get('title', 'N/A')}
Pozycja: ({window_info.get('left', 0)}, {window_info.get('top', 0)})
Rozmiar: {window_info.get('width', 0)} x {window_info.get('height', 0)} pikseli
Prawy dolny róg: ({window_info.get('right', 0)}, {window_info.get('bottom', 0)})
Metoda przechwytywania: {capture_method}

INSTRUKCJE UŻYCIA:
1. Kliknij 'Znajdź Okno' aby połączyć się z aplikacją
2. Użyj 'Start Przechwytywania' aby włączyć podgląd na żywo  
3. 'Analizuj Obraz' - uruchomi Computer Vision na aktualnym obrazie
4. Test kliknięć używa współrzędnych względem okna (nie ekranu)
5. Dostępne klawisze: space, enter, esc, tab, w, a, s, d, 1-9, f1-f12, ctrl,c itp.

COMPUTER VISION:
• Automatycznie wykrywa: wzorce, paski HP/Mana, tekst, elementy UI
• Twórz templates: podaj współrzędne regionu i nazwę
• Znajdź + Klik: automatyczne klikanie w znalezione wzorce
• Screenshots i wizualizacje są zapisywane w folderze data/screenshots/
• Templates są zapisywane w folderze data/templates/

KLAWISZE:
• Testuj różne metody: WinAPI, pyautogui, ctypes
• Wybierz metodę która działa z Twoim WoW
• 'Test Wszystkich Metod' sprawdzi automatycznie
"""

            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, text)

    def update_preview(self):
        """Aktualizuj podgląd"""
        try:
            if self.capture_active:
                latest = self.window_capture.get_latest_screenshot()
                if latest:
                    img = latest['image']
                    height, width = img.shape[:2]

                    max_width = self.config['gui']['preview_max_width']
                    max_height = self.config['gui']['preview_max_height']
                    scale = min(max_width / width, max_height / height)

                    new_width = int(width * scale)
                    new_height = int(height * scale)

                    resized = cv2.resize(img, (new_width, new_height))
                    img_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    img_pil = Image.fromarray(img_rgb)
                    img_tk = ImageTk.PhotoImage(img_pil)

                    self.preview_label.configure(image=img_tk, text="")
                    self.preview_label.image = img_tk

        except Exception as e:
            print(f"Błąd aktualizacji podglądu: {e}")

        update_interval = 1000 // self.config['gui']['preview_fps']
        self.root.after(update_interval, self.update_preview)

    def run(self):
        """Uruchom aplikację"""

        try:
            # Start automation if enabled
            if self.config['automation']['enabled']:
                self.automation.start()
            from vision.vision_engine import VisionEngine
            self.vision_engine = VisionEngine(self.config)
            self.update_template_list()
        except ImportError:
            print("Vision Engine nie jest dostępny przy starcie - zostanie załadowany przy pierwszym użyciu")

        self.root.mainloop()
        self.stop_capture()
        finally:
            # Clean up
            if self.automation:
                self.automation.stop()