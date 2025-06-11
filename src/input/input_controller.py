# src/input/input_controller.py
import time
from typing import Tuple, Dict, Any
import pyautogui
import win32gui
import win32con
import win32api
import ctypes
from ctypes import wintypes

from capture.coordinate_manager import CoordinateManager


class InputController:
    """Klasa do kontroli inputu"""

    def __init__(self, coordinate_manager: CoordinateManager, config: Dict[str, Any]):
        self.coordinate_manager = coordinate_manager
        self.config = config

        # Konfiguracja pyautogui
        pyautogui.FAILSAFE = config['input']['failsafe_enabled']
        pyautogui.PAUSE = config['input']['click_delay']

        # Mapy klawiszy dla Windows API
        self.vk_code_map = {
            'space': 0x20,
            'enter': 0x0D,
            'return': 0x0D,
            'esc': 0x1B,
            'escape': 0x1B,
            'tab': 0x09,
            'shift': 0x10,
            'ctrl': 0x11,
            'alt': 0x12,
            'backspace': 0x08,
            'delete': 0x2E,
            'home': 0x24,
            'end': 0x23,
            'pageup': 0x21,
            'pagedown': 0x22,
            'up': 0x26,
            'down': 0x28,
            'left': 0x25,
            'right': 0x27,
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
            'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
            'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
            '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
            '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
            'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
            'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
            'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
            'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
            'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59, 'z': 0x5A
        }

    def _get_absolute_coords(self, window_x: int, window_y: int) -> Tuple[int, int]:
        """Konwertuj współrzędne okna na współrzędne ekranu"""
        if not self.coordinate_manager.window_info:
            raise Exception("Brak informacji o oknie")

        abs_x, abs_y = self.coordinate_manager.window_to_screen(window_x, window_y)
        return abs_x, abs_y

    def _activate_target_window(self) -> bool:
        """Aktywuj okno docelowe"""
        try:
            window_info = self.coordinate_manager.window_info
            if not window_info:
                return False

            # Znajdź handle okna po tytule
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title and window_info['title'].lower() in window_title.lower():
                        windows.append(hwnd)
                return True

            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)

            if windows:
                hwnd = windows[0]

                # Przywróć okno jeśli zminimalizowane
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.1)

                # Ustaw jako okno z pierwszym planem
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.1)

                return True

            return False

        except Exception as e:
            print(f"Błąd aktywacji okna: {e}")
            return False

    def click(self, x: int, y: int, button: str = 'left', clicks: int = 1) -> bool:
        """Kliknij w określone współrzędne okna"""
        try:
            if self.config['input']['safety_enabled']:
                if not self.coordinate_manager.is_point_in_window(x, y):
                    print(f"Współrzędne poza oknem: ({x}, {y})")
                    return False

            abs_x, abs_y = self._get_absolute_coords(x, y)
            pyautogui.click(abs_x, abs_y, clicks=clicks, button=button)

            print(f"Kliknięto w ({x}, {y}) -> ekran ({abs_x}, {abs_y})")
            return True

        except Exception as e:
            print(f"Błąd podczas klikania: {e}")
            return False

    def right_click(self, x: int, y: int) -> bool:
        """Kliknij prawym przyciskiem"""
        return self.click(x, y, button='right')

    def double_click(self, x: int, y: int) -> bool:
        """Podwójne kliknięcie"""
        return self.click(x, y, clicks=2)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 1.0) -> bool:
        """Przeciągnij od punktu A do B"""
        try:
            abs_start_x, abs_start_y = self._get_absolute_coords(start_x, start_y)
            abs_end_x, abs_end_y = self._get_absolute_coords(end_x, end_y)

            pyautogui.drag(abs_start_x, abs_start_y, abs_end_x - abs_start_x,
                           abs_end_y - abs_start_y, duration=duration)

            print(f"Przeciągnięto z ({start_x}, {start_y}) do ({end_x}, {end_y})")
            return True

        except Exception as e:
            print(f"Błąd podczas przeciągania: {e}")
            return False

    def send_key(self, key: str, method: str = "winapi") -> bool:
        """Wyślij klawisz - różne metody"""
        key = key.lower().strip()

        # Aktywuj okno przed wysłaniem klawisza
        if not self._activate_target_window():
            print("Uwaga: Nie udało się aktywować okna docelowego")

        if method == "auto":
            # Próbuj różne metody w kolejności
            methods = ["winapi", "pyautogui", "ctypes"]
            for m in methods:
                if self._send_key_method(key, m):
                    return True
            return False
        else:
            return self._send_key_method(key, method)

    def _send_key_method(self, key: str, method: str) -> bool:
        """Wyślij klawisz konkretną metodą"""
        try:
            if method == "winapi":
                return self._send_key_winapi(key)
            elif method == "pyautogui":
                return self._send_key_pyautogui(key)
            elif method == "ctypes":
                return self._send_key_ctypes(key)
            else:
                print(f"Nieznana metoda: {method}")
                return False

        except Exception as e:
            print(f"Błąd metody {method} dla klawisza {key}: {e}")
            return False

    def _send_key_winapi(self, key: str) -> bool:
        """Wyślij klawisz przez Windows API (PostMessage)"""
        try:
            window_info = self.coordinate_manager.window_info
            if not window_info:
                return False

            # Znajdź handle okna
            hwnd = win32gui.FindWindow(None, window_info['title'])
            if not hwnd:
                return False

            # Pobierz kod klawisza
            if key in self.vk_code_map:
                vk_code = self.vk_code_map[key]
            else:
                # Dla pojedynczych znaków
                vk_code = ord(key.upper()) if len(key) == 1 else None

            if vk_code is None:
                print(f"Nieznany klawisz: {key}")
                return False

            # Wyślij WM_KEYDOWN i WM_KEYUP
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(0.05)
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)

            print(f"Wysłano klawisz {key} (VK: {vk_code}) przez WinAPI")
            return True

        except Exception as e:
            print(f"Błąd WinAPI: {e}")
            return False

    def _send_key_pyautogui(self, key: str) -> bool:
        """Wyślij klawisz przez pyautogui"""
        try:
            pyautogui.press(key)
            print(f"Wysłano klawisz {key} przez pyautogui")
            return True
        except Exception as e:
            print(f"Błąd pyautogui: {e}")
            return False

    def _send_key_ctypes(self, key: str) -> bool:
        """Wyślij klawisz przez ctypes (SendInput)"""
        try:
            if key in self.vk_code_map:
                vk_code = self.vk_code_map[key]
            else:
                vk_code = ord(key.upper()) if len(key) == 1 else None

            if vk_code is None:
                return False

            # Struktury dla SendInput
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
                ]

            class INPUT(ctypes.Structure):
                class _INPUT(ctypes.Union):
                    _fields_ = [("ki", KEYBDINPUT)]

                _anonymous_ = ("_input",)
                _fields_ = [
                    ("type", wintypes.DWORD),
                    ("_input", _INPUT)
                ]

            # Utwórz struktury input
            key_down = INPUT()
            key_down.type = 1  # INPUT_KEYBOARD
            key_down.ki.wVk = vk_code
            key_down.ki.wScan = 0
            key_down.ki.dwFlags = 0
            key_down.ki.time = 0
            key_down.ki.dwExtraInfo = None

            key_up = INPUT()
            key_up.type = 1
            key_up.ki.wVk = vk_code
            key_up.ki.wScan = 0
            key_up.ki.dwFlags = 2  # KEYEVENTF_KEYUP
            key_up.ki.time = 0
            key_up.ki.dwExtraInfo = None

            # Wyślij input
            user32 = ctypes.windll.user32
            user32.SendInput(1, ctypes.byref(key_down), ctypes.sizeof(INPUT))
            time.sleep(0.05)
            user32.SendInput(1, ctypes.byref(key_up), ctypes.sizeof(INPUT))

            print(f"Wysłano klawisz {key} przez ctypes")
            return True

        except Exception as e:
            print(f"Błąd ctypes: {e}")
            return False

    def send_keys(self, keys: str, method: str = "auto") -> bool:
        """Wyślij kombinację klawiszy"""
        try:
            # Aktywuj okno
            if not self._activate_target_window():
                print("Uwaga: Nie udało się aktywować okna docelowego")

            if ',' in keys:
                # Kombinacja klawiszy (np. "ctrl,c")
                key_list = [k.strip() for k in keys.split(',')]

                if method == "pyautogui" or method == "auto":
                    try:
                        pyautogui.hotkey(*key_list)
                        print(f"Wysłano kombinację klawiszy: {keys}")
                        return True
                    except:
                        pass

                # Fallback - wyślij jeden po drugim
                for key in key_list:
                    if not self.send_key(key, method):
                        return False
                return True
            else:
                # Pojedynczy klawisz
                return self.send_key(keys, method)

        except Exception as e:
            print(f"Błąd podczas wysyłania klawiszy: {e}")
            return False

    def type_text(self, text: str, interval: float = 0.05, method: str = "auto") -> bool:
        """Wpisz tekst"""
        try:
            # Aktywuj okno
            if not self._activate_target_window():
                print("Uwaga: Nie udało się aktywować okna docelowego")

            if method == "pyautogui" or method == "auto":
                try:
                    pyautogui.typewrite(text, interval=interval)
                    print(f"Wpisano tekst: {text}")
                    return True
                except:
                    pass

            # Fallback - po znaku
            for char in text:
                if not self.send_key(char, method):
                    print(f"Błąd przy znaku: {char}")
                    return False
                time.sleep(interval)

            print(f"Wpisano tekst: {text}")
            return True

        except Exception as e:
            print(f"Błąd podczas wpisywania tekstu: {e}")
            return False

    def scroll(self, x: int, y: int, clicks: int) -> bool:
        """Przewiń w określonym miejscu"""
        try:
            abs_x, abs_y = self._get_absolute_coords(x, y)
            pyautogui.scroll(clicks, abs_x, abs_y)

            print(f"Przewinięto {clicks} kliknięć w ({x}, {y})")
            return True

        except Exception as e:
            print(f"Błąd podczas przewijania: {e}")
            return False

    def test_all_key_methods(self, key: str = "space") -> Dict[str, bool]:
        """Przetestuj wszystkie metody wysyłania klawisza"""
        results = {}
        methods = ["winapi", "pyautogui", "ctypes"]

        print(f"Testowanie metod dla klawisza '{key}':")

        for method in methods:
            print(f"  Testowanie {method}...")
            success = self._send_key_method(key, method)
            results[method] = success
            print(f"  {method}: {'✓' if success else '✗'}")
            time.sleep(0.5)  # Pauza między testami

        return results

    def get_available_keys(self) -> list:
        """Pobierz listę dostępnych klawiszy"""
        return list(self.vk_code_map.keys())