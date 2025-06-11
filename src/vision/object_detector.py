# src/vision/object_detector.py
import cv2
import numpy as np
from typing import List, Dict, Any, Optional


class BasicObjectDetector:
    """Podstawowy detektor obiektów (bez deep learning)"""

    def __init__(self):
        pass

    def detect_circles(self, image: np.ndarray, min_radius: int = 10, max_radius: int = 100) -> List[Dict[str, Any]]:
        """Wykryj okrągłe obiekty (minimap, targety)"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # HoughCircles
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=30,
                param1=50,
                param2=30,
                minRadius=min_radius,
                maxRadius=max_radius
            )

            detected_circles = []

            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")

                for (x, y, r) in circles:
                    circle_info = {
                        'type': 'circle',
                        'center_x': int(x),
                        'center_y': int(y),
                        'radius': int(r),
                        'x': int(x - r),
                        'y': int(y - r),
                        'width': int(2 * r),
                        'height': int(2 * r)
                    }
                    detected_circles.append(circle_info)

            return detected_circles

        except Exception as e:
            print(f"Błąd podczas wykrywania okręgów: {e}")
            return []

    def detect_lines(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Wykryj linie (interfejs, panele)"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)

            lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)

            detected_lines = []

            if lines is not None:
                for line in lines:
                    rho, theta = line[0]
                    a = np.cos(theta)
                    b = np.sin(theta)
                    x0 = a * rho
                    y0 = b * rho

                    x1 = int(x0 + 1000 * (-b))
                    y1 = int(y0 + 1000 * (a))
                    x2 = int(x0 - 1000 * (-b))
                    y2 = int(y0 - 1000 * (a))

                    line_info = {
                        'type': 'line',
                        'x1': x1,
                        'y1': y1,
                        'x2': x2,
                        'y2': y2,
                        'rho': float(rho),
                        'theta': float(theta)
                    }
                    detected_lines.append(line_info)

            return detected_lines

        except Exception as e:
            print(f"Błąd podczas wykrywania linii: {e}")
            return []