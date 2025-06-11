from typing import Tuple, Dict, Any, Optional


class CoordinateManager:
    """Zarządzanie współrzędnymi między oknem a ekranem"""

    def __init__(self, window_info: Dict[str, Any] = None):
        self.window_info = window_info or {}

    def update_window_info(self, window_info: Dict[str, Any]):
        """Aktualizuj informacje o oknie"""
        self.window_info = window_info

    def window_to_screen(self, window_x: int, window_y: int) -> Tuple[int, int]:
        """Konwertuj współrzędne okna na współrzędne ekranu"""
        if not self.window_info:
            raise ValueError("Brak informacji o oknie")

        screen_x = self.window_info['left'] + window_x
        screen_y = self.window_info['top'] + window_y

        return screen_x, screen_y

    def screen_to_window(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """Konwertuj współrzędne ekranu na współrzędne okna"""
        if not self.window_info:
            raise ValueError("Brak informacji o oknie")

        window_x = screen_x - self.window_info['left']
        window_y = screen_y - self.window_info['top']

        return window_x, window_y

    def normalize_coordinates(self, x: int, y: int) -> Tuple[float, float]:
        """Normalizuj współrzędne do zakresu 0-1"""
        if not self.window_info:
            raise ValueError("Brak informacji o oknie")

        norm_x = x / self.window_info['width']
        norm_y = y / self.window_info['height']

        return norm_x, norm_y

    def denormalize_coordinates(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Konwertuj znormalizowane współrzędne na rzeczywiste"""
        if not self.window_info:
            raise ValueError("Brak informacji o oknie")

        x = int(norm_x * self.window_info['width'])
        y = int(norm_y * self.window_info['height'])

        return x, y

    def is_point_in_window(self, x: int, y: int) -> bool:
        """Sprawdź czy punkt mieści się w oknie"""
        if not self.window_info:
            return False

        return (0 <= x <= self.window_info['width'] and
                0 <= y <= self.window_info['height'])

    def clamp_to_window(self, x: int, y: int) -> Tuple[int, int]:
        """Ogranicz współrzędne do obszaru okna"""
        if not self.window_info:
            return x, y

        clamped_x = max(0, min(x, self.window_info['width']))
        clamped_y = max(0, min(y, self.window_info['height']))

        return clamped_x, clamped_y