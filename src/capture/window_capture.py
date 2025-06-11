# src/capture/window_capture.py
import time
import threading
import queue
from datetime import datetime
from typing import Optional, Dict, Any, List
import numpy as np
import cv2
import mss
import pygetwindow as gw
import win32gui
import win32ui
import win32con
from PIL import Image

from capture.coordinate_manager import CoordinateManager


class WindowCapture:
    """Klasa do przechwytywania okien WoW"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.target_window = None
        self.window_info = {}
        self.coordinate_manager = CoordinateManager()

        self.last_screenshot = None
        self.screenshot_thread = None
        self.is_capturing = False
        self.screenshot_queue = queue.Queue(maxsize=10)

    def find_target_window(self, custom_titles: List[str] = None) -> bool:
        """Znajdź okno docelowe"""
        try:
            titles = custom_titles or self.config['window']['target_titles']
            windows = gw.getAllWindows()

            for window in windows:
                for title in titles:
                    if title.lower() in window.title.lower() and len(window.title) > 3:
                        self.target_window = window
                        self._update_window_info()
                        print(f"Znaleziono okno: {window.title}")
                        return True

            print("Nie znaleziono docelowego okna")
            return False

        except Exception as e:
            print(f"Błąd podczas szukania okna: {e}")
            return False

    def _update_window_info(self):
        """Aktualizuj informacje o oknie"""
        if self.target_window:
            try:
                self.window_info = {
                    'title': self.target_window.title,
                    'left': self.target_window.left,
                    'top': self.target_window.top,
                    'width': self.target_window.width,
                    'height': self.target_window.height,
                    'right': self.target_window.right,
                    'bottom': self.target_window.bottom
                }
                self.coordinate_manager.update_window_info(self.window_info)
            except:
                self.window_info = {}

    def capture_window_screenshot(self) -> Optional[np.ndarray]:
        """Przechwytuj screenshot okna (również zminimalizowanego)"""
        if not self.target_window:
            return None

        try:
            # Sprawdź czy okno nadal istnieje
            if not self._is_window_valid():
                if not self.find_target_window():
                    return None

            self._update_window_info()

            # Użyj Windows API dla wszystkich okien (również zminimalizowanych)
            try:
                return self._capture_with_windows_api()
            except Exception as api_error:
                print(f"Windows API failed: {api_error}, używam fallback MSS")
                return self._capture_with_mss()

        except Exception as e:
            print(f"Błąd podczas przechwytywania: {e}")
            return None

    def _capture_with_windows_api(self) -> Optional[np.ndarray]:
        """Przechwytywanie używając Windows API (działa z zminimalizowanymi oknami)"""
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = self.target_window._hWnd

            # Pobierz device context okna
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            # Utwórz bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, self.window_info['width'], self.window_info['height'])
            saveDC.SelectObject(saveBitMap)

            # Użyj ctypes dla PrintWindow
            user32 = ctypes.windll.user32
            PW_RENDERFULLCONTENT = 0x00000002

            result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)

            if result:
                # Konwertuj do numpy array
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)

                img = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1
                )

                img_array = np.array(img)
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

                # Cleanup
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)

                self.last_screenshot = img_bgr
                return img_bgr
            else:
                print("PrintWindow zwrócił błąd")
                return None

        except Exception as e:
            print(f"Błąd Windows API: {e}")
            raise e

    def _capture_with_mss(self) -> Optional[np.ndarray]:
        """Fallback - przechwytywanie MSS dla aktywnych okien"""
        try:
            with mss.mss() as sct:
                monitor = {
                    "top": self.window_info['top'],
                    "left": self.window_info['left'],
                    "width": self.window_info['width'],
                    "height": self.window_info['height']
                }

                screenshot = sct.grab(monitor)
                img_array = np.array(screenshot)
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)

                self.last_screenshot = img_bgr
                return img_bgr

        except Exception as e:
            print(f"Błąd MSS: {e}")
            return None

    def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[np.ndarray]:
        """Przechwytuj określony region okna"""
        if not self.target_window:
            return None

        try:
            # Najpierw przechwytuj całe okno
            full_screenshot = self.capture_window_screenshot()
            if full_screenshot is None:
                return None

            # Wytnij żądany region
            end_x = min(x + width, full_screenshot.shape[1])
            end_y = min(y + height, full_screenshot.shape[0])

            if x >= 0 and y >= 0 and end_x > x and end_y > y:
                region = full_screenshot[y:end_y, x:end_x]
                return region
            else:
                print(f"Nieprawidłowy region: ({x}, {y}, {width}, {height})")
                return None

        except Exception as e:
            print(f"Błąd podczas przechwytywania regionu: {e}")
            return None

    def start_continuous_capture(self, fps: int = None):
        """Rozpocznij ciągłe przechwytywanie"""
        if self.is_capturing:
            return

        fps = fps or self.config['window']['capture_fps']
        self.is_capturing = True
        interval = 1.0 / fps

        def capture_loop():
            while self.is_capturing:
                screenshot = self.capture_window_screenshot()
                if screenshot is not None:
                    timestamp = datetime.now()

                    try:
                        self.screenshot_queue.put_nowait({
                            'image': screenshot,
                            'timestamp': timestamp,
                            'window_info': self.window_info.copy()
                        })
                    except queue.Full:
                        try:
                            self.screenshot_queue.get_nowait()
                            self.screenshot_queue.put_nowait({
                                'image': screenshot,
                                'timestamp': timestamp,
                                'window_info': self.window_info.copy()
                            })
                        except queue.Empty:
                            pass

                time.sleep(interval)

        self.screenshot_thread = threading.Thread(target=capture_loop, daemon=True)
        self.screenshot_thread.start()

    def stop_continuous_capture(self):
        """Zatrzymaj ciągłe przechwytywanie"""
        self.is_capturing = False
        if self.screenshot_thread:
            self.screenshot_thread.join(timeout=1.0)

    def get_latest_screenshot(self) -> Optional[Dict[str, Any]]:
        """Pobierz najnowszy screenshot z kolejki"""
        try:
            return self.screenshot_queue.get_nowait()
        except queue.Empty:
            return None

    def _is_window_valid(self) -> bool:
        """Sprawdź czy okno nadal jest dostępne"""
        try:
            # Sprawdź czy okno nadal istnieje w systemie
            if not self.target_window:
                return False

            # Sprawdź czy handle okna jest nadal ważny
            try:
                hwnd = self.target_window._hWnd
                return win32gui.IsWindow(hwnd)
            except:
                # Fallback - sprawdź przez tytuł
                return bool(self.target_window.title)

        except:
            return False

    def get_window_info(self) -> Dict[str, Any]:
        """Pobierz informacje o oknie"""
        return self.window_info.copy()

    def get_coordinate_manager(self) -> CoordinateManager:
        """Pobierz menedżer współrzędnych"""
        return self.coordinate_manager

    def is_window_minimized(self) -> bool:
        """Sprawdź czy okno jest zminimalizowane"""
        if not self.target_window:
            return False
        try:
            return self.target_window.isMinimized
        except:
            return False

    def get_capture_method_info(self) -> str:
        """Zwróć informację o metodzie przechwytywania"""
        if not self.target_window:
            return "Brak okna"

        if self.is_window_minimized():
            return "Windows API (okno zminimalizowane)"
        else:
            return "Windows API (okno aktywne)"