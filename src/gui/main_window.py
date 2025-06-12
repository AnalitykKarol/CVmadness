# src/gui/main_window.py
import os
import json
import tkinter as tk
import tkinter.simpledialog
from datetime import datetime
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk
from capture.window_capture import WindowCapture
from input.input_controller import InputController
from automation.automation_manager import AutomationManager
from vision.vision_engine import VisionEngine

class MainWindow:
    """Główne okno aplikacji"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize main window"""
        self.root = tk.Tk()
        self.root.title("WoW Automation")
        self.config = config

        # Initialize window capture
        from capture.window_capture import WindowCapture
        self.window_capture = WindowCapture(config)

        # Initialize status variables
        self.status_var = tk.StringVar(value="Nie połączono z aplikacją")
        self.capture_active = False
        self.target_window_var = tk.StringVar(value="World of Warcraft")

        # OCR variables - ZMIANA: najpierw ustaw domyślne wartości
        self.ocr_x_var = tk.StringVar(value="120")
        self.ocr_y_var = tk.StringVar(value="65")
        self.ocr_w_var = tk.StringVar(value="80")
        self.ocr_h_var = tk.StringVar(value="20")
        self.last_manual_ocr = None

        # HP and Mana regions - ZMIANA: pozostaw jako None, będą załadowane z config
        self.hp_region = None
        self.mana_region = None
        self.hp_value_var = tk.StringVar(value="HP: --")
        self.mana_value_var = tk.StringVar(value="Mana: --")

        # Color variables
        self.color_pick_x_var = tk.StringVar(value="150")
        self.color_pick_y_var = tk.StringVar(value="70")
        self.color_region_x_var = tk.StringVar(value="100")
        self.color_region_y_var = tk.StringVar(value="60")
        self.color_region_w_var = tk.StringVar(value="200")
        self.color_region_h_var = tk.StringVar(value="50")
        self.color_tolerance_var = tk.StringVar(value="15")
        self.current_color_var = tk.StringVar(value="RGB: N/A")
        self.current_hsv_var = tk.StringVar(value="HSV: N/A")

        # Template variables
        self.template_var = tk.StringVar()
        self.template_list = []

        # User settings
        self.saved_colors = {}
        self.current_picked_color = None
        self.user_settings_file = "config/user_settings.json"
        self.saved_regions_var = tk.StringVar(value="")
        self.saved_colors_var = tk.StringVar(value="")

        # Initialize vision engine
        try:
            from vision.vision_engine import VisionEngine
            self.vision_engine = VisionEngine(config)
        except ImportError as e:
            messagebox.showerror("Error", f"Failed to load Vision Engine: {e}")
            self.vision_engine = None

        # Setup GUI
        self.setup_ui()

        # Initialize automation with log widget
        from automation.automation_manager import AutomationManager
        self.automation = AutomationManager(config, self.vision_engine, self.info_text)

        # ZMIANA: Load saved settings - MUSI BYĆ PO setup_ui()
        self.load_user_settings()

        # ZMIANA: Setup auto-save bindings - PO załadowaniu ustawień
        self.setup_auto_save_bindings()

        # Start preview update
        self.update_preview()

        # Set up closing handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_user_settings(self):
        """Load saved user settings"""
        try:
            # Najpierw załaduj domyślne wartości z głównej konfiguracji
            self.load_default_settings()

            # Następnie sprawdź czy istnieje plik user_settings i nadpisz wartości
            if os.path.exists(self.user_settings_file):
                with open(self.user_settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                # Load target window
                if 'target_window' in settings:
                    self.target_window_var.set(settings['target_window'])

                # Load OCR regions
                if 'ocr_regions' in settings:
                    ocr = settings['ocr_regions']
                    if 'current' in ocr:
                        self.ocr_x_var.set(str(ocr['current'].get('x', self.ocr_x_var.get())))
                        self.ocr_y_var.set(str(ocr['current'].get('y', self.ocr_y_var.get())))
                        self.ocr_w_var.set(str(ocr['current'].get('w', self.ocr_w_var.get())))
                        self.ocr_h_var.set(str(ocr['current'].get('h', self.ocr_h_var.get())))

                    # Load HP and Mana regions
                    if 'hp' in ocr:
                        self.hp_region = tuple(ocr['hp'])
                    if 'mana' in ocr:
                        self.mana_region = tuple(ocr['mana'])

                # Load color regions
                if 'color_regions' in settings:
                    color = settings['color_regions']
                    if 'current' in color:
                        self.color_pick_x_var.set(str(color['current'].get('x', self.color_pick_x_var.get())))
                        self.color_pick_y_var.set(str(color['current'].get('y', self.color_pick_y_var.get())))
                        self.color_region_x_var.set(
                            str(color['current'].get('region_x', self.color_region_x_var.get())))
                        self.color_region_y_var.set(
                            str(color['current'].get('region_y', self.color_region_y_var.get())))
                        self.color_region_w_var.set(
                            str(color['current'].get('region_w', self.color_region_w_var.get())))
                        self.color_region_h_var.set(
                            str(color['current'].get('region_h', self.color_region_h_var.get())))
                        self.color_tolerance_var.set(
                            str(color['current'].get('tolerance', self.color_tolerance_var.get())))

                # Load saved colors
                if 'saved_colors' in settings:
                    self.saved_colors = settings['saved_colors']

                logging.info("User settings loaded successfully")
            else:
                logging.info("No user_settings.json found, using default values from config")

        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            # W przypadku błędu, upewnij się że są załadowane domyślne wartości
            self.load_default_settings()

    def load_default_settings(self):
        """Load default settings from main config"""
        try:
            # Załaduj domyślne okno target
            if 'window' in self.config and 'target_titles' in self.config['window']:
                default_target = self.config['window']['target_titles'][0]
                if not self.target_window_var.get():
                    self.target_window_var.set(default_target)

            # Załaduj domyślne regiony OCR z konfiguracji
            if 'vision' in self.config and 'ocr' in self.config['vision'] and 'regions' in self.config['vision']['ocr']:
                ocr_regions = self.config['vision']['ocr']['regions']

                # HP region
                if 'hp' in ocr_regions:
                    hp_region = ocr_regions['hp']
                    if not self.hp_region:
                        self.hp_region = (hp_region['x'], hp_region['y'], hp_region['width'], hp_region['height'])

                    # Ustaw jako current region jeśli nie jest ustawiony
                    if not self.ocr_x_var.get() or self.ocr_x_var.get() == "120":
                        self.ocr_x_var.set(str(hp_region['x']))
                        self.ocr_y_var.set(str(hp_region['y']))
                        self.ocr_w_var.set(str(hp_region['width']))
                        self.ocr_h_var.set(str(hp_region['height']))

                # Mana region
                if 'mana' in ocr_regions:
                    mana_region = ocr_regions['mana']
                    if not self.mana_region:
                        self.mana_region = (
                        mana_region['x'], mana_region['y'], mana_region['width'], mana_region['height'])

            # Alternatywnie, sprawdź starszą strukturę konfiguracji
            elif 'ocr_regions' in self.config:
                if 'hp_region' in self.config['ocr_regions'] and not self.hp_region:
                    hp_data = self.config['ocr_regions']['hp_region']
                    self.hp_region = tuple(hp_data)

                    # Ustaw jako current region jeśli nie jest ustawiony
                    if not self.ocr_x_var.get() or self.ocr_x_var.get() == "120":
                        self.ocr_x_var.set(str(hp_data[0]))
                        self.ocr_y_var.set(str(hp_data[1]))
                        self.ocr_w_var.set(str(hp_data[2]))
                        self.ocr_h_var.set(str(hp_data[3]))

                if 'mana_region' in self.config['ocr_regions'] and not self.mana_region:
                    mana_data = self.config['ocr_regions']['mana_region']
                    self.mana_region = tuple(mana_data)

            # Aktualizuj wyświetlanie
            self.update_saved_regions_display()

            logging.info("Default settings loaded from main config")

        except Exception as e:
            logging.error(f"Error loading default settings: {e}")
            # Fallback do hard-coded defaults
            if not self.hp_region:
                self.hp_region = (270, 125, 50, 29)
            if not self.mana_region:
                self.mana_region = (270, 147, 50, 29)
            if not self.ocr_x_var.get() or self.ocr_x_var.get() == "120":
                self.ocr_x_var.set("270")
                self.ocr_y_var.set("125")
                self.ocr_w_var.set("50")
                self.ocr_h_var.set("29")

    def save_user_settings(self):
        """Save user settings"""
        try:
            settings = {
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
                'saved_colors': self.saved_colors
            }
            
            # Save HP and Mana regions if they exist
            if self.hp_region:
                settings['ocr_regions']['hp'] = self.hp_region
            if self.mana_region:
                settings['ocr_regions']['mana'] = self.mana_region
            
            with open(self.user_settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            
            logging.info("User settings saved successfully")
        except Exception as e:
            logging.error(f"Error saving settings: {e}")

    def auto_save_settings(self):
        """Auto-save settings when changes are made"""
        # Opóźnienie 1 sekunda żeby nie zapisywać przy każdym ruchu myszy
        if hasattr(self, '_save_timer'):
            self.root.after_cancel(self._save_timer)
        
        self._save_timer = self.root.after(1000, self.save_user_settings)

    def setup_auto_save_bindings(self):
        """Setup auto-save bindings for settings changes"""
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
        """Setup GUI elements"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Status display
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Main tab
        main_tab = ttk.Frame(notebook)
        notebook.add(main_tab, text="Main")

        # Preview frame
        preview_frame = ttk.LabelFrame(main_tab, text="Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        # Info frame
        info_frame = ttk.LabelFrame(main_tab, text="Window Info")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create text widget for info with scrollbar
        info_text_frame = ttk.Frame(info_frame)
        info_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.info_text = tk.Text(info_text_frame, height=4, wrap=tk.WORD)
        info_scrollbar = ttk.Scrollbar(info_text_frame, orient="vertical", command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scrollbar.set)
        
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # OCR Data frame
        ocr_frame = ttk.LabelFrame(main_tab, text="OCR Data")
        ocr_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add HP and Mana value display
        values_frame = ttk.Frame(ocr_frame)
        values_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.hp_value_var = tk.StringVar(value="HP: --")
        self.mana_value_var = tk.StringVar(value="Mana: --")
        
        ttk.Label(values_frame, textvariable=self.hp_value_var, font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
        ttk.Label(values_frame, textvariable=self.mana_value_var, font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
        
        # OCR Region input
        ocr_input_frame = ttk.Frame(ocr_frame)
        ocr_input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(ocr_input_frame, text="Region (x, y, w, h):").pack(side=tk.LEFT)
        
        # Create entry fields for OCR coordinates
        coords_frame = ttk.Frame(ocr_input_frame)
        coords_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Entry(coords_frame, textvariable=self.ocr_x_var, width=6).pack(side=tk.LEFT)
        ttk.Label(coords_frame, text=",").pack(side=tk.LEFT, padx=2)
        ttk.Entry(coords_frame, textvariable=self.ocr_y_var, width=6).pack(side=tk.LEFT)
        ttk.Label(coords_frame, text=",").pack(side=tk.LEFT, padx=2)
        ttk.Entry(coords_frame, textvariable=self.ocr_w_var, width=6).pack(side=tk.LEFT)
        ttk.Label(coords_frame, text=",").pack(side=tk.LEFT, padx=2)
        ttk.Entry(coords_frame, textvariable=self.ocr_h_var, width=6).pack(side=tk.LEFT)
        
        # OCR buttons
        ocr_buttons_frame = ttk.Frame(ocr_frame)
        ocr_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(ocr_buttons_frame, text="Test OCR", command=self.test_manual_ocr).pack(side=tk.LEFT, padx=5)
        ttk.Button(ocr_buttons_frame, text="Set HP Region", command=self.set_hp_region).pack(side=tk.LEFT, padx=5)
        ttk.Button(ocr_buttons_frame, text="Set Mana Region", command=self.set_mana_region).pack(side=tk.LEFT, padx=5)
        ttk.Button(ocr_buttons_frame, text="Show Region", command=self.show_ocr_region).pack(side=tk.LEFT, padx=5)
        ttk.Button(ocr_buttons_frame, text="Debug Regions", command=self.debug_hp_mana_regions).pack(side=tk.LEFT,
                                                                                                     padx=5)
        
        # Create text widget for OCR results with scrollbar
        ocr_text_frame = ttk.Frame(ocr_frame)
        ocr_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.ocr_text = tk.Text(ocr_text_frame, height=6, wrap=tk.WORD)
        ocr_scrollbar = ttk.Scrollbar(ocr_text_frame, orient="vertical", command=self.ocr_text.yview)
        self.ocr_text.configure(yscrollcommand=ocr_scrollbar.set)
        
        self.ocr_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ocr_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Control buttons frame
        control_frame = ttk.Frame(main_tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Target window controls
        target_frame = ttk.LabelFrame(control_frame, text="Target Window")
        target_frame.pack(fill=tk.X, pady=5)
        
        # Add target window entry
        target_entry_frame = ttk.Frame(target_frame)
        target_entry_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(target_entry_frame, text="Window Title:").pack(side=tk.LEFT)
        target_entry = ttk.Entry(target_entry_frame, textvariable=self.target_window_var, width=30)
        target_entry.pack(side=tk.LEFT, padx=5)
        
        # Add target window buttons
        target_buttons_frame = ttk.Frame(target_frame)
        target_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(target_buttons_frame, text="Set Target Window", command=self.set_target_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(target_buttons_frame, text="Find Window", command=self.find_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(target_buttons_frame, text="Start Capture", command=self.start_capture).pack(side=tk.LEFT, padx=5)
        ttk.Button(target_buttons_frame, text="Stop Capture", command=self.stop_capture).pack(side=tk.LEFT, padx=5)
        ttk.Button(target_buttons_frame, text="Save Screenshot", command=self.save_screenshot).pack(side=tk.LEFT, padx=5)

        # Input controls
        input_frame = ttk.LabelFrame(control_frame, text="Input Controls")
        input_frame.pack(fill=tk.X, pady=5)
        
        # Click test
        click_frame = ttk.Frame(input_frame)
        click_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(click_frame, text="Test Click (x, y):").pack(side=tk.LEFT)
        self.click_x_var = tk.StringVar(value="400")
        self.click_y_var = tk.StringVar(value="300")
        
        click_coords_frame = ttk.Frame(click_frame)
        click_coords_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Entry(click_coords_frame, textvariable=self.click_x_var, width=8).pack(side=tk.LEFT)
        ttk.Label(click_coords_frame, text=",").pack(side=tk.LEFT, padx=2)
        ttk.Entry(click_coords_frame, textvariable=self.click_y_var, width=8).pack(side=tk.LEFT)
        ttk.Button(click_coords_frame, text="Click", command=self.test_click).pack(side=tk.LEFT, padx=5)
        
        # Key test
        key_frame = ttk.Frame(input_frame)
        key_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(key_frame, text="Test Key:").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value="space")
        self.key_method_var = tk.StringVar(value="auto")
        
        key_input_frame = ttk.Frame(key_frame)
        key_input_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Entry(key_input_frame, textvariable=self.key_var, width=15).pack(side=tk.LEFT)
        ttk.Label(key_input_frame, text="Method:").pack(side=tk.LEFT, padx=5)
        method_combo = ttk.Combobox(key_input_frame, textvariable=self.key_method_var,
                                  values=["auto", "winapi", "pyautogui", "ctypes"], width=10)
        method_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(key_input_frame, text="Send Key", command=self.test_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(key_input_frame, text="Test Methods", command=self.test_key_methods).pack(side=tk.LEFT, padx=5)

        # Vision controls
        vision_frame = ttk.LabelFrame(control_frame, text="Vision Controls")
        vision_frame.pack(fill=tk.X, pady=5)
        ttk.Button(vision_frame, text="Analyze Image", command=self.analyze_current_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(vision_frame, text="Visualize Results", command=self.visualize_results).pack(side=tk.LEFT, padx=5)

        # Template controls
        template_frame = ttk.LabelFrame(control_frame, text="Template Controls")
        template_frame.pack(fill=tk.X, pady=5)
        ttk.Button(template_frame, text="Update Templates", command=self.update_template_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_frame, text="Find Template", command=self.find_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_frame, text="Find & Click", command=self.find_and_click_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_frame, text="Create Template", command=self.create_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_frame, text="Delete Template", command=self.delete_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_frame, text="Show Template", command=self.show_template).pack(side=tk.LEFT, padx=5)

        # Settings tab
        settings_tab = ttk.Frame(notebook)
        notebook.add(settings_tab, text="Settings")

        # Color settings
        color_frame = ttk.LabelFrame(settings_tab, text="Color Settings")
        color_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(color_frame, text="Save HP Color", command=self.save_hp_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(color_frame, text="Save Mana Color", command=self.save_mana_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(color_frame, text="Save Custom Color", command=self.save_custom_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(color_frame, text="Test All Colors", command=self.test_all_saved_colors).pack(side=tk.LEFT, padx=5)

        # Saved regions display
        regions_frame = ttk.LabelFrame(settings_tab, text="Saved Regions")
        regions_frame.pack(fill=tk.X, padx=5, pady=5)
        self.regions_text = tk.Text(regions_frame, height=4, wrap=tk.WORD)
        self.regions_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Saved colors display
        colors_frame = ttk.LabelFrame(settings_tab, text="Saved Colors")
        colors_frame.pack(fill=tk.X, padx=5, pady=5)
        self.colors_text = tk.Text(colors_frame, height=4, wrap=tk.WORD)
        self.colors_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Update saved regions and colors display
        self.update_saved_regions_display()
        self.update_saved_colors_display()

        # Bind mousewheel to text widgets
        def _on_mousewheel(event):
            for widget in [self.regions_text, self.colors_text, self.ocr_text, self.info_text]:
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        for widget in [self.regions_text, self.colors_text, self.ocr_text, self.info_text]:
            widget.bind("<MouseWheel>", _on_mousewheel)

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
        self.current_color_var = tk.StringVar(value="RGB: N/A")
        ttk.Label(color_frame, textvariable=self.current_color_var, foreground="blue").grid(row=4, column=0, sticky=tk.W, pady=(5, 0))

        self.current_hsv_var = tk.StringVar(value="HSV: N/A")
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
            
            # Przekaż input controller do automation manager
            self.automation.set_input_controller(self.input_controller)

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
            logging.info(f"✓ Screenshot zapisany: {default_path}")
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

            logging.info(f"Test OCR dla regionu ({x}, {y}, {w}, {h})")

            screenshot = self.window_capture.capture_window_screenshot()
            if screenshot is not None:
                img_height, img_width = screenshot.shape[:2]
                if x + w > img_width or y + h > img_height:
                    messagebox.showerror("Błąd", f"Region wykracza poza obraz\nObraz: {img_width}x{img_height}")
                    return

                roi = screenshot[y:y + h, x:x + w]
                
                # Zapisz region do debugowania
                debug_dir = os.path.join(self.config['paths']['screenshots'], 'debug')
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                debug_file = os.path.join(debug_dir, f'ocr_region_{timestamp}.png')
                cv2.imwrite(debug_file, roi)
                logging.info(f"Zapisano region OCR do: {debug_file}")

                ocr_results = self.vision_engine.test_manual_ocr_region(roi, x, y, w, h)
                logging.info(f"Wyniki OCR: {ocr_results}")

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
            logging.error(f"Błąd OCR: {e}", exc_info=True)
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
        """Update the display of saved regions"""
        try:
            regions_text = ""
            
            if self.hp_region:
                regions_text += f"HP: ({self.hp_region[0]}, {self.hp_region[1]}, {self.hp_region[2]}, {self.hp_region[3]})\n"
            else:
                regions_text += "HP: brak\n"
                
            if self.mana_region:
                regions_text += f"Mana: ({self.mana_region[0]}, {self.mana_region[1]}, {self.mana_region[2]}, {self.mana_region[3]})"
            else:
                regions_text += "Mana: brak"
            
            self.regions_text.delete(1.0, tk.END)
            self.regions_text.insert(tk.END, regions_text)
        except Exception as e:
            logging.error(f"Failed to update regions display: {e}")
            self.regions_text.delete(1.0, tk.END)
            self.regions_text.insert(tk.END, "Error: Failed to load regions")

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
        """Analyze current image and update OCR data display"""
        if not self.window_capture.is_capturing:
            messagebox.showwarning("Warning", "No active capture")
            return

        try:
            # Get current frame
            frame = self.window_capture.get_latest_frame()
            if frame is None:
                return

            # Analyze HP region
            hp_region = self.config['vision']['regions']['hp']  # (x, y, w, h)
            x, y, w, h = hp_region
            hp_image = frame[y:y + h, x:x + w]
            hp_text = self.vision_engine.ocr_engine.read_text(hp_image)
            hp_value = self.vision_engine.ocr_engine.extract_numbers(hp_text)

            # Analyze Mana region
            mana_region = self.config['vision']['regions']['mana']  # (x, y, w, h)
            x, y, w, h = mana_region
            mana_image = frame[y:y + h, x:x + w]
            mana_text = self.vision_engine.ocr_engine.read_text(mana_image)
            mana_value = self.vision_engine.ocr_engine.extract_numbers(mana_text)

            # Update OCR data display
            self.ocr_text.delete(1.0, tk.END)
            self.ocr_text.insert(tk.END, f"HP Region Raw Text: {hp_text}\n")
            self.ocr_text.insert(tk.END, f"HP Extracted Value: {hp_value}\n")
            self.ocr_text.insert(tk.END, f"Mana Region Raw Text: {mana_text}\n")
            self.ocr_text.insert(tk.END, f"Mana Extracted Value: {mana_value}\n")

            # Update preview with visualization
            self.visualize_results()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze image: {str(e)}")

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
        """Aktualizuj listę wzorców w GUI"""
        try:
            templates = self.vision_engine.template_matcher.get_template_list()
            if hasattr(self, 'template_combo'):
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
        """Update window information display"""
        try:
            if not self.window_capture.is_capturing:
                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(tk.END, "No active window capture")
                return

            window_info = self.window_capture.get_window_info()
            if window_info:
                info_text = f"Window Title: {window_info['title']}\n"
                info_text += f"Position: ({window_info['left']}, {window_info['top']})\n"
                info_text += f"Size: {window_info['width']}x{window_info['height']}\n"
                if window_info.get('handle') is not None:
                    info_text += f"Handle: {window_info['handle']}\n"
                
                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(tk.END, info_text)
            else:
                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(tk.END, "No window information available")
        except Exception as e:
            logging.error(f"Failed to update window info: {e}")
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, f"Error: {str(e)}")

    def update_preview(self):
        """Aktualizuj podgląd"""
        try:
            if self.capture_active:
                latest = self.window_capture.get_latest_screenshot()
                if latest:
                    img = latest['image']
                    height, width = img.shape[:2]

                    # DODAJ: Monster Detection - przed skalowaniem obrazu
                    if hasattr(self, 'vision_engine') and self.vision_engine:
                        try:
                            # Wykryj potwory na pełnym obrazie
                            monsters = self.vision_engine.detect_monsters(img)
                            if monsters:
                                # Narysuj wykrycia na obrazie
                                img = self.vision_engine.monster_detector.draw_detections(img, monsters)

                                # Pokaż info w logach
                                summary = self.vision_engine.monster_detector.get_detection_summary(monsters)
                                logging.info(summary)

                                # Opcjonalnie: zapisz info o potworach do GUI
                                self.info_text.insert(tk.END, f"🎯 {summary}\n")
                                self.info_text.see(tk.END)
                        except Exception as e:
                            logging.error(f"Monster detection error: {e}")
                    # DODAJ po monster detection:
                    if hasattr(self, 'vision_engine') and self.vision_engine:
                        try:
                            monsters = self.vision_engine.detect_monsters(img)
                            if monsters:
                                img = self.vision_engine.monster_detector.draw_detections(img, monsters)

                                # DODAJ: Monster Combat
                                if hasattr(self, 'automation') and self.automation:
                                    self.automation.monster_combat.update(img)

                                    # Show combat status
                                    combat_status = self.automation.monster_combat.get_combat_status()
                                    if combat_status['has_target']:
                                        target_info = f"🎯 Target: {combat_status['target_class']} ({combat_status['target_confidence']:.2f})"
                                        self.info_text.insert(tk.END, f"{target_info}\n")
                                        self.info_text.see(tk.END)
                        except Exception as e:
                            logging.error(f"Combat update error: {e}")

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

                    # Update window info
                    self.update_window_info()

                    # ===== POPRAWIONE HP/MANA OCR =====
                    # Update HP and Mana values if regions are set
                    if hasattr(self, 'hp_region') and self.hp_region and hasattr(self,
                                                                                 'vision_engine') and self.vision_engine:
                        try:
                            x, y, w, h = self.hp_region
                            # POPRAWKA: Przekaż PEŁNY obraz, nie wycięty region
                            hp_text = self.vision_engine.test_manual_ocr_region(img, x, y, w, h)
                            if hp_text and 'numbers_only' in hp_text and hp_text['numbers_only']:
                                self.hp_value_var.set(f"HP: {hp_text['numbers_only']}")
                            elif hp_text and 'full_text' in hp_text and hp_text['full_text']:
                                self.hp_value_var.set(f"HP: {hp_text['full_text']}")
                            elif hp_text and 'default' in hp_text and hp_text['default']:
                                self.hp_value_var.set(f"HP: {hp_text['default']}")
                            else:
                                self.hp_value_var.set("HP: --")

                            print(f"HP OCR wynik: {hp_text}")  # Debug
                        except Exception as e:
                            logging.error(f"Error updating HP value: {e}")
                            self.hp_value_var.set("HP: Error")

                    if hasattr(self, 'mana_region') and self.mana_region and hasattr(self,
                                                                                     'vision_engine') and self.vision_engine:
                        try:
                            x, y, w, h = self.mana_region
                            # POPRAWKA: Przekaż PEŁNY obraz, nie wycięty region
                            mana_text = self.vision_engine.test_manual_ocr_region(img, x, y, w, h)
                            if mana_text and 'numbers_only' in mana_text and mana_text['numbers_only']:
                                self.mana_value_var.set(f"Mana: {mana_text['numbers_only']}")
                            elif mana_text and 'full_text' in mana_text and mana_text['full_text']:
                                self.mana_value_var.set(f"Mana: {mana_text['full_text']}")
                            elif mana_text and 'default' in mana_text and mana_text['default']:
                                self.mana_value_var.set(f"Mana: {mana_text['default']}")
                            else:
                                self.mana_value_var.set("Mana: --")

                            print(f"Mana OCR wynik: {mana_text}")  # Debug
                        except Exception as e:
                            logging.error(f"Error updating Mana value: {e}")
                            self.mana_value_var.set("Mana: Error")

        except Exception as e:
            logging.error(f"Błąd aktualizacji podglądu: {e}")

        update_interval = 1000 // self.config['gui']['preview_fps']
        self.root.after(update_interval, self.update_preview)

    def debug_hp_mana_regions(self):
        """Debug regionów HP i Mana - zapisuje obrazy do analizy"""
        try:
            screenshot = self.window_capture.capture_window_screenshot()
            if screenshot is None:
                print("Brak screenshota")
                return

            print(f"Screenshot size: {screenshot.shape}")

            # Debug HP region
            if hasattr(self, 'hp_region') and self.hp_region:
                x, y, w, h = self.hp_region
                print(f"HP region: ({x}, {y}, {w}, {h})")

                # Sprawdź czy region mieści się w obrazie
                img_height, img_width = screenshot.shape[:2]
                if x + w <= img_width and y + h <= img_height and x >= 0 and y >= 0:
                    hp_roi = screenshot[y:y + h, x:x + w]

                    # Zapisz HP region
                    debug_dir = os.path.join(self.config['paths']['screenshots'], 'debug')
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = datetime.now().strftime('%H%M%S')

                    hp_file = os.path.join(debug_dir, f'hp_region_{timestamp}.png')
                    cv2.imwrite(hp_file, hp_roi)
                    print(f"HP region zapisany: {hp_file}")
                    print(f"HP region shape: {hp_roi.shape}")

                    # Test OCR na HP
                    hp_result = self.vision_engine.test_manual_ocr_region(screenshot, x, y, w, h)
                    print(f"HP OCR result: {hp_result}")
                else:
                    print(f"HP region poza obrazem! Image: {img_width}x{img_height}")

            # Debug Mana region
            if hasattr(self, 'mana_region') and self.mana_region:
                x, y, w, h = self.mana_region
                print(f"Mana region: ({x}, {y}, {w}, {h})")

                # Sprawdź czy region mieści się w obrazie
                img_height, img_width = screenshot.shape[:2]
                if x + w <= img_width and y + h <= img_height and x >= 0 and y >= 0:
                    mana_roi = screenshot[y:y + h, x:x + w]

                    # Zapisz Mana region
                    debug_dir = os.path.join(self.config['paths']['screenshots'], 'debug')
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = datetime.now().strftime('%H%M%S')

                    mana_file = os.path.join(debug_dir, f'mana_region_{timestamp}.png')
                    cv2.imwrite(mana_file, mana_roi)
                    print(f"Mana region zapisany: {mana_file}")
                    print(f"Mana region shape: {mana_roi.shape}")

                    # Test OCR na Mana
                    mana_result = self.vision_engine.test_manual_ocr_region(screenshot, x, y, w, h)
                    print(f"Mana OCR result: {mana_result}")
                else:
                    print(f"Mana region poza obrazem! Image: {img_width}x{img_height}")

            # Zapisz też pełny screenshot z zaznaczonymi regionami
            vis_image = screenshot.copy()

            if hasattr(self, 'hp_region') and self.hp_region:
                x, y, w, h = self.hp_region
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Zielony dla HP
                cv2.putText(vis_image, "HP", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            if hasattr(self, 'mana_region') and self.mana_region:
                x, y, w, h = self.mana_region
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), (255, 0, 0), 2)  # Niebieski dla Mana
                cv2.putText(vis_image, "MANA", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            timestamp = datetime.now().strftime('%H%M%S')
            vis_file = os.path.join(debug_dir, f'regions_overview_{timestamp}.png')
            cv2.imwrite(vis_file, vis_image)
            print(f"Regions overview zapisany: {vis_file}")

        except Exception as e:
            print(f"Błąd debug: {e}")

    # Dodaj też przycisk w GUI do testowania
    def add_debug_button_to_gui(self):
        """Dodaj przycisk debug do GUI"""

    def on_closing(self):
        """Handle window closing"""
        if self.capture_active:
            self.stop_capture()
        if hasattr(self, 'automation') and self.automation:
            self.automation.stop()
        self.root.destroy()

    def run(self):
        """Run the application"""
        self.root.mainloop()
