# src/vision/vision_engine.py
import cv2
import numpy as np
from typing import List, Tuple, Dict, Any, Optional

from vision.template_matcher import TemplateMatcher

import os

try:
    import pytesseract

    # Sprawdź typowe lokalizacje Tesseract na Windows
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]

    # Dodaj WinGet paths
    username = os.environ.get('USERNAME', '')
    winget_base = rf'C:\Users\{username}\AppData\Local\Microsoft\WinGet\Packages'

    if os.path.exists(winget_base):
        for folder in os.listdir(winget_base):
            if 'tesseract' in folder.lower():
                tesseract_exe = os.path.join(winget_base, folder, 'tesseract.exe')
                tesseract_paths.append(tesseract_exe)

    # Znajdź działający Tesseract
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"✓ Tesseract znaleziony: {path}")
            break
    else:
        print("⚠ Tesseract nie znaleziony w standardowych lokalizacjach")

except ImportError:
    print("⚠ pytesseract nie zainstalowany")

class VisionEngine:
    """Główny silnik computer vision dla WoW"""

    # Dodaj te metody do klasy VisionEngine w src/vision/vision_engine.py

    def _preprocess_for_wow_numbers(self, image: np.ndarray) -> np.ndarray:
        """Specjalny preprocessing dla liczb WoW"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # WoW ma białe liczby z czarnymi cieniami - zwiększ kontrast
        # Bardzo duże skalowanie dla małych liczb
        height, width = gray.shape
        scale_factor = 5  # Większe skalowanie
        resized = cv2.resize(gray, (width * scale_factor, height * scale_factor), interpolation=cv2.INTER_CUBIC)

        # Bardzo wysokie zwiększenie kontrastu dla białego tekstu
        contrast = cv2.convertScaleAbs(resized, alpha=4.0, beta=0)

        # Próg adaptacyjny - lepszy dla różnych tła
        thresh = cv2.adaptiveThreshold(contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        # Morphological operations - poprawa jakości tekstu
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def extract_wow_hp_mana_text(self, image: np.ndarray) -> Dict[str, Any]:
        """Specjalna metoda dla liczb HP/Mana w WoW"""
        if not self.ocr_available:
            return {'hp_text': [], 'mana_text': []}

        try:
            import pytesseract

            # Zakresy gdzie WoW zwykle pokazuje HP/Mana (górny lewy róg)
            player_hp_region = (80, 80, 120, 25)  # Region z HP gracza
            player_mana_region = (80, 105, 120, 25)  # Region z maną gracza

            # Config OCR dla WoW (tylko cyfry, /, %)
            wow_config = '--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789/%'

            results = {'hp_text': [], 'mana_text': []}

            # Test różnych regionów gdzie mogą być liczby HP/Mana
            test_regions = [
                ('hp', player_hp_region),
                ('mana', player_mana_region),
                # Dodatkowe regiony dla targetów, party itp.
                ('target_hp', (400, 80, 120, 25)),
                ('party1_hp', (20, 200, 80, 20)),
            ]

            for region_type, (x, y, w, h) in test_regions:
                # Sprawdź czy region mieści się w obrazie
                if x + w > image.shape[1] or y + h > image.shape[0]:
                    continue

                roi = image[y:y + h, x:x + w]

                # Specjalny preprocessing dla WoW
                processed = self._preprocess_for_wow_numbers(roi)

                try:
                    text = pytesseract.image_to_string(processed, config=wow_config).strip()

                    # Sprawdź czy tekst wygląda jak HP/Mana (zawiera cyfry)
                    if text and any(c.isdigit() for c in text):
                        result = {
                            'type': region_type,
                            'text': text,
                            'x': x, 'y': y, 'width': w, 'height': h,
                            'confidence': self._calculate_wow_text_confidence(text)
                        }

                        if 'hp' in region_type:
                            results['hp_text'].append(result)
                        elif 'mana' in region_type:
                            results['mana_text'].append(result)

                except Exception as e:
                    print(f"OCR error dla {region_type}: {e}")

            return results

        except Exception as e:
            print(f"WoW HP/Mana extraction error: {e}")
            return {'hp_text': [], 'mana_text': []}

    def _calculate_wow_text_confidence(self, text: str) -> float:
        """Oblicz pewność rozpoznania tekstu WoW"""
        # Sprawdź czy tekst ma typowy format WoW
        confidence = 0.5

        if '/' in text:  # Format "1000/1000"
            confidence += 0.3

        if '%' in text:  # Format "100%"
            confidence += 0.2

        # Sprawdź czy wszystkie znaki to cyfry, /, %
        valid_chars = set('0123456789/%')
        if all(c in valid_chars for c in text):
            confidence += 0.2

        return min(confidence, 1.0)

    def detect_wow_ui_numbers(self, image: np.ndarray) -> Dict[str, Any]:
        """Kompletna detekcja liczb w WoW UI"""
        results = {
            'hp_mana_numbers': self.extract_wow_hp_mana_text(image),
            'general_numbers': [],
            'debug_regions': []
        }

        # Dodaj ogólne regiony gdzie mogą być liczby
        general_regions = [
            (50, 50, 200, 50),  # Górny lewy - status gracza
            (1000, 50, 200, 50),  # Górny prawy - minimap/czas
            (50, 600, 800, 100),  # Dolny obszar - chat/UI
        ]

        for i, (x, y, w, h) in enumerate(general_regions):
            # Sprawdź czy region mieści się w obrazie
            if x + w <= image.shape[1] and y + h <= image.shape[0]:
                results['debug_regions'].append({
                    'id': i,
                    'x': x, 'y': y, 'width': w, 'height': h,
                    'purpose': f'debug_region_{i}'
                })

        return results

    # Aktualizuj analyze_image aby używał nowych metod
    def analyze_image(self, image: np.ndarray) -> Dict[str, Any]:
        """Kompletna analiza obrazu - ZAKTUALIZOWANA dla WoW"""
        results = {
            'templates': self.template_matcher.find_all_templates(image),
            'colors': self.detect_health_mana_bars(image),
            'text': self.extract_text_regions(image) if self.ocr_available else [],
            'ui_elements': self.detect_ui_elements(image),
            'wow_numbers': self.detect_wow_ui_numbers(image) if self.ocr_available else {}
        }

        return results

    # DODAJ te metody do klasy VisionEngine w src/vision/vision_engine.py:

    def detect_custom_color_in_region(self, image: np.ndarray, target_color: Dict[str, Any],
                                      region: Tuple[int, int, int, int], tolerance: int = 15) -> Dict[str, Any]:
        """Wykryj niestandardowy kolor w określonym regionie"""
        try:
            rx, ry, rw, rh = region

            # Sprawdź czy region mieści się w obrazie
            img_height, img_width = image.shape[:2]
            if rx + rw > img_width or ry + rh > img_height or rx < 0 or ry < 0:
                return {'detected_areas': [], 'error': 'Region poza obrazem'}

            # Wytnij region
            roi = image[ry:ry + rh, rx:rx + rw]

            # Konwertuj na HSV dla lepszego dopasowania kolorów
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            # Utwórz maskę koloru z tolerancją
            target_hsv = target_color['hsv']

            # Oblicz zakresy HSV z tolerancją
            lower_hsv, upper_hsv = self._calculate_hsv_range(target_hsv, tolerance)

            # Stwórz maskę
            mask = cv2.inRange(hsv_roi, lower_hsv, upper_hsv)

            # Znajdź kontury obszarów z tym kolorem
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            detected_areas = []

            for contour in contours:
                area = cv2.contourArea(contour)

                # Filtruj bardzo małe obszary
                if area < 10:
                    continue

                # Prostokąt otaczający
                x, y, w, h = cv2.boundingRect(contour)

                # Przelicz współrzędne na cały obraz (dodaj offset regionu)
                global_x = rx + x
                global_y = ry + y

                # Oblicz pokrycie (% pikseli w prostokącie który ma ten kolor)
                rect_area = w * h
                coverage = (area / rect_area * 100) if rect_area > 0 else 0

                area_info = {
                    'x': global_x,
                    'y': global_y,
                    'width': w,
                    'height': h,
                    'area': int(area),
                    'coverage': coverage,
                    'center_x': global_x + w // 2,
                    'center_y': global_y + h // 2
                }

                detected_areas.append(area_info)

            # Sortuj według rozmiaru (największe pierwsze)
            detected_areas.sort(key=lambda x: x['area'], reverse=True)

            return {
                'detected_areas': detected_areas,
                'total_detected_pixels': int(np.sum(mask > 0)),
                'region_coverage': (np.sum(mask > 0) / (rw * rh) * 100) if (rw * rh) > 0 else 0,
                'mask_debug': mask  # Do debugowania
            }

        except Exception as e:
            return {'detected_areas': [], 'error': f'Color detection error: {e}'}

    def _calculate_hsv_range(self, target_hsv: Tuple[int, int, int], tolerance: int) -> Tuple[np.ndarray, np.ndarray]:
        """Oblicz zakres HSV z tolerancją"""
        h, s, v = target_hsv

        # Hue (odcień) - specjalne traktowanie bo to koło (0-179 w OpenCV)
        h_tolerance = min(tolerance, 30)  # Max 30 dla Hue
        if h - h_tolerance < 0:
            # Wrap around (np. czerwony może być 170-179 lub 0-10)
            lower_h = 0
            upper_h = h + h_tolerance
        elif h + h_tolerance > 179:
            lower_h = h - h_tolerance
            upper_h = 179
        else:
            lower_h = h - h_tolerance
            upper_h = h + h_tolerance

        # Saturation i Value - normalne zakresy z ograniczeniami
        s_tolerance = min(tolerance * 2, 50)  # Większa tolerancja dla saturacji
        v_tolerance = min(tolerance * 2, 50)

        lower_s = max(0, s - s_tolerance)
        upper_s = min(255, s + s_tolerance)

        lower_v = max(0, v - v_tolerance)
        upper_v = min(255, v + v_tolerance)

        lower_hsv = np.array([lower_h, lower_s, lower_v])
        upper_hsv = np.array([upper_h, upper_s, upper_v])

        return lower_hsv, upper_hsv

    def detect_multiple_custom_colors(self, image: np.ndarray, color_definitions: Dict[str, Dict]) -> Dict[str, Any]:
        """Wykryj wiele niestandardowych kolorów jednocześnie"""
        results = {}

        for name, definition in color_definitions.items():
            try:
                color_result = self.detect_custom_color_in_region(
                    image,
                    definition['color'],
                    definition['region'],
                    definition['tolerance']
                )
                results[name] = color_result
            except Exception as e:
                results[name] = {'detected_areas': [], 'error': f'Error: {e}'}

        return results

    def create_color_analysis_report(self, image: np.ndarray, color_definitions: Dict[str, Dict]) -> str:
        """Stwórz raport analizy kolorów"""
        results = self.detect_multiple_custom_colors(image, color_definitions)

        report = "=== RAPORT ANALIZY KOLORÓW ===\n\n"

        for name, result in results.items():
            report += f"{name.upper()}:\n"

            if 'error' in result:
                report += f"  ❌ Błąd: {result['error']}\n"
            else:
                areas = result['detected_areas']
                coverage = result.get('region_coverage', 0)

                report += f"  📊 Znaleziono: {len(areas)} obszarów\n"
                report += f"  📈 Pokrycie regionu: {coverage:.1f}%\n"

                if areas:
                    largest = areas[0]  # Pierwszy = największy
                    report += f"  🎯 Największy obszar: ({largest['center_x']}, {largest['center_y']})\n"
                    report += f"     Rozmiar: {largest['width']}x{largest['height']}px\n"
                    report += f"     Pokrycie: {largest['coverage']:.1f}%\n"
                else:
                    report += f"  ⚠️ Nie wykryto koloru\n"

            report += "\n"

        return report

    def get_dominant_colors_in_region(self, image: np.ndarray, region: Tuple[int, int, int, int],
                                      k: int = 5) -> List[Dict[str, Any]]:
        """Znajdź dominujące kolory w regionie (pomocnicze do wybierania kolorów)"""
        try:
            rx, ry, rw, rh = region
            roi = image[ry:ry + rh, rx:rx + rw]

            # Konwertuj na RGB dla k-means
            rgb_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)

            # Reshape do listy pikseli
            pixels = rgb_roi.reshape(-1, 3).astype(np.float32)

            # K-means clustering
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

            # Policz częstość każdego koloru
            unique, counts = np.unique(labels, return_counts=True)

            colors = []
            for i, (color_idx, count) in enumerate(zip(unique, counts)):
                rgb = centers[color_idx].astype(int)
                bgr = (int(rgb[2]), int(rgb[1]), int(rgb[0]))  # Konwersja RGB->BGR

                # Konwertuj na HSV
                hsv_pixel = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
                hsv = (int(hsv_pixel[0]), int(hsv_pixel[1]), int(hsv_pixel[2]))

                percentage = (count / len(pixels)) * 100

                colors.append({
                    'rgb': tuple(rgb),
                    'bgr': bgr,
                    'hsv': hsv,
                    'percentage': percentage,
                    'pixel_count': int(count)
                })

            # Sortuj według częstości
            colors.sort(key=lambda x: x['percentage'], reverse=True)

            return colors

        except Exception as e:
            print(f"Błąd analizy dominujących kolorów: {e}")
            return []

    # Aktualizuj visualize_results aby pokazywał WoW numbers
    def visualize_results(self, image: np.ndarray, results: Dict[str, Any]) -> np.ndarray:
        """Narysuj wyniki analizy na obrazie - ZAKTUALIZOWANE dla WoW"""
        vis_image = image.copy()

        try:
            # Rysuj dopasowane wzorce (jak wcześniej)
            if 'templates' in results:
                for template_name, matches in results['templates'].items():
                    for match in matches:
                        cv2.rectangle(vis_image,
                                      (match['x'], match['y']),
                                      (match['x'] + match['width'], match['y'] + match['height']),
                                      (0, 255, 0), 2)
                        label = f"{template_name.split('/')[-1]}: {match['confidence']:.2f}"
                        cv2.putText(vis_image, label,
                                    (match['x'], match['y'] - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Rysuj paski HP/Mana (jak wcześniej)
            if 'colors' in results:
                for bar in results['colors'].get('health_bars', []):
                    cv2.rectangle(vis_image,
                                  (bar['x'], bar['y']),
                                  (bar['x'] + bar['width'], bar['y'] + bar['height']),
                                  (0, 0, 255), 2)
                    cv2.putText(vis_image, "HP",
                                (bar['x'], bar['y'] - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

                for bar in results['colors'].get('mana_bars', []):
                    cv2.rectangle(vis_image,
                                  (bar['x'], bar['y']),
                                  (bar['x'] + bar['width'], bar['y'] + bar['height']),
                                  (255, 0, 0), 2)
                    cv2.putText(vis_image, "MANA",
                                (bar['x'], bar['y'] - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

            # NOWE: Rysuj wykryte liczby WoW
            if 'wow_numbers' in results:
                wow_data = results['wow_numbers']

                # HP numbers - zielone
                for hp_info in wow_data.get('hp_mana_numbers', {}).get('hp_text', []):
                    cv2.rectangle(vis_image,
                                  (hp_info['x'], hp_info['y']),
                                  (hp_info['x'] + hp_info['width'], hp_info['y'] + hp_info['height']),
                                  (0, 255, 0), 2)
                    cv2.putText(vis_image, f"HP: {hp_info['text']}",
                                (hp_info['x'], hp_info['y'] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # Mana numbers - niebieskie
                for mana_info in wow_data.get('hp_mana_numbers', {}).get('mana_text', []):
                    cv2.rectangle(vis_image,
                                  (mana_info['x'], mana_info['y']),
                                  (mana_info['x'] + mana_info['width'], mana_info['y'] + mana_info['height']),
                                  (255, 0, 0), 2)
                    cv2.putText(vis_image, f"MANA: {mana_info['text']}",
                                (mana_info['x'], mana_info['y'] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

                # Debug regions - żółte
                for region in wow_data.get('debug_regions', []):
                    cv2.rectangle(vis_image,
                                  (region['x'], region['y']),
                                  (region['x'] + region['width'], region['y'] + region['height']),
                                  (0, 255, 255), 1)

            # Rysuj wykryty tekst (jak wcześniej)
            if 'text' in results:
                for text_info in results['text']:
                    cv2.rectangle(vis_image,
                                  (text_info['x'], text_info['y']),
                                  (text_info['x'] + text_info['width'], text_info['y'] + text_info['height']),
                                  (255, 255, 0), 1)

            return vis_image

        except Exception as e:
            print(f"Błąd podczas wizualizacji: {e}")
            return vis_image
    def extract_numbers_from_regions(self, image: np.ndarray, regions: List[Tuple[int, int, int, int]]) -> List[
        Dict[str, Any]]:
        """Wyciągnij tylko liczby z określonych regionów"""
        if not self.ocr_available:
            return []

        try:
            import pytesseract

            results = []
            number_config = '--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789%/'

            for i, (x, y, w, h) in enumerate(regions):
                roi = image[y:y + h, x:x + w]

                # Agresywny preprocessing dla liczb
                processed = self._preprocess_for_numbers(roi)

                try:
                    text = pytesseract.image_to_string(processed, config=number_config).strip()

                    if text and any(c.isdigit() for c in text):  # Tylko jeśli są cyfry
                        results.append({
                            'region_id': i,
                            'text': text,
                            'x': x, 'y': y, 'width': w, 'height': h,
                            'type': 'number'
                        })
                except Exception as e:
                    print(f"OCR error region {i}: {e}")

            return results
        except Exception as e:
            print(f"Number extraction error: {e}")
            return []

    def _preprocess_for_numbers(self, image: np.ndarray) -> np.ndarray:
        """Agresywny preprocessing dla liczb WoW"""
        # Konwertuj do skali szarości
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Zwiększ rozmiar dla lepszego OCR
        scale_factor = 3
        height, width = gray.shape
        resized = cv2.resize(gray, (width * scale_factor, height * scale_factor), interpolation=cv2.INTER_CUBIC)

        # Bardzo wysoki kontrast dla liczb
        contrast = cv2.convertScaleAbs(resized, alpha=3.0, beta=50)

        # Rozmycie + sharpening
        blurred = cv2.GaussianBlur(contrast, (3, 3), 0)
        sharpened = cv2.addWeighted(contrast, 1.5, blurred, -0.5, 0)

        # Progowanie adaptacyjne
        thresh = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        return thresh

    # DODAJ tę metodę do klasy VisionEngine w src/vision/vision_engine.py:

    def test_manual_ocr_region(self, roi: np.ndarray, x: int, y: int, w: int, h: int) -> Dict[str, str]:
        """Test różnych konfiguracji OCR na ręcznie wybranym regionie"""
        if not self.ocr_available:
            return {"error": "OCR niedostępny"}

        try:
            import pytesseract

            results = {}

            # Test różnych konfiguracji OCR
            configs = {
                "tylko_cyfry": "--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789",
                "cyfry_plus": "--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789/%",
                "standardowy": "--oem 3 --psm 6",
                "pojedyncze_słowo": "--oem 3 --psm 8",
                "pojedyncza_linia": "--oem 3 --psm 7"
            }

            # Test różnych preprocessingów
            preprocessings = {
                "surowy": roi,
                "wow_numbers": self._preprocess_for_wow_numbers(roi),
                "standardowy": self._preprocess_for_ocr(roi)
            }

            # Test kombinacji preprocessing + config
            for prep_name, processed_image in preprocessings.items():
                for config_name, config in configs.items():
                    try:
                        text = pytesseract.image_to_string(processed_image, config=config).strip()
                        key = f"{prep_name}_{config_name}"
                        results[key] = text if text else "(pusty)"

                    except Exception as e:
                        results[f"{prep_name}_{config_name}"] = f"(błąd: {str(e)[:20]})"

            # Dodatkowy test z bardzo dużym skalowaniem
            try:
                # 8x skalowanie dla bardzo małych liczb
                height, width = roi.shape[:2] if len(roi.shape) == 2 else roi.shape[:2]
                huge_scale = cv2.resize(roi, (width * 8, height * 8), interpolation=cv2.INTER_CUBIC)
                huge_processed = self._preprocess_for_wow_numbers(huge_scale)

                text = pytesseract.image_to_string(huge_processed, config=configs["cyfry_plus"]).strip()
                results["mega_scale_cyfry"] = text if text else "(pusty)"

            except Exception as e:
                results["mega_scale_cyfry"] = f"(błąd: {str(e)[:20]})"

            # Zapisz obrazy debug (opcjonalnie)
            try:
                import os
                debug_dir = "data/screenshots/debug_ocr"
                os.makedirs(debug_dir, exist_ok=True)

                timestamp = datetime.now().strftime('%H%M%S')

                # Zapisz oryginalny re# Manual Color Detection
                # color_frame = ttk.LabelFrame(vision_frame, text="Ręczny wybór kolorów", padding="5")
                # color_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
                #
                # # Color picker coordinates
                # ttk.Label(color_frame, text="Kliknij punkt aby pobrać kolor (x, y):").grid(row=0, column=0, sticky=tk.W)
                #
                # color_coords_frame = ttk.Frame(color_frame)
                # color_coords_frame.grid(row=1, column=0, sticky=tk.W)
                #
                # self.color_pick_x_var = tk.StringVar(value="150")
                # self.color_pick_y_var = tk.StringVar(value="70")
                #
                # ttk.Entry(color_coords_frame, textvariable=self.color_pick_x_var, width=8).grid(row=0, column=0)
                # ttk.Label(color_coords_frame, text=",").grid(row=0, column=1, padx=2)
                # ttk.Entry(color_coords_frame, textvariable=self.color_pick_y_var, width=8).grid(row=0, column=2)
                #
                # ttk.Button(color_coords_frame, text="Pobierz Kolor",
                #           command=self.pick_color_from_point).grid(row=0, column=3, padx=(5, 0))
                #
                # # Color tolerance
                # ttk.Label(color_frame, text="Tolerancja koloru (0-50):").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
                # self.color_tolerance_var = tk.StringVar(value="15")
                # ttk.Entry(color_frame, textvariable=self.color_tolerance_var, width=8).grid(row=3, column=0, sticky=tk.W)
                #
                # # Current color display
                # self.current_color_var = tk.StringVar(value="RGB: nie wybrano")
                # ttk.Label(color_frame, textvariable=self.current_color_var, foreground="blue").grid(row=4, column=0, sticky=tk.W, pady=(5, 0))
                #
                # self.current_hsv_var = tk.StringVar(value="HSV: nie wybrano")
                # ttk.Label(color_frame, textvariable=self.current_hsv_var, foreground="green").grid(row=5, column=0, sticky=tk.W)
                #
                # # Color region definition
                # ttk.Label(color_frame, text="Region do skanowania (x, y, w, h):").grid(row=6, column=0, sticky=tk.W, pady=(10, 0))
                #
                # color_region_frame = ttk.Frame(color_frame)
                # color_region_frame.grid(row=7, column=0, sticky=tk.W)
                #
                # self.color_region_x_var = tk.StringVar(value="100")
                # self.color_region_y_var = tk.StringVar(value="60")
                # self.color_region_w_var = tk.StringVar(value="200")
                # self.color_region_h_var = tk.StringVar(value="50")
                #
                # ttk.Entry(color_region_frame, textvariable=self.color_region_x_var, width=6).grid(row=0, column=0)
                # ttk.Label(color_region_frame, text=",").grid(row=0, column=1, padx=2)
                # ttk.Entry(color_region_frame, textvariable=self.color_region_y_var, width=6).grid(row=0, column=2)
                # ttk.Label(color_region_frame, text=",").grid(row=0, column=3, padx=2)
                # ttk.Entry(color_region_frame, textvariable=self.color_region_w_var, width=6).grid(row=0, column=4)
                # ttk.Label(color_region_frame, text=",").grid(row=0, column=5, padx=2)
                # ttk.Entry(color_region_frame, textvariable=self.color_region_h_var, width=6).grid(row=0, column=6)
                #
                # # Color test buttons
                # color_buttons_frame = ttk.Frame(color_frame)
                # color_buttons_frame.grid(row=8, column=0, sticky=tk.W, pady=(10, 0))
                #
                # ttk.Button(color_buttons_frame, text="Test Kolor w Regionie",
                #           command=self.test_color_in_region).grid(row=0, column=0)
                #
                # ttk.Button(color_buttons_frame, text="Zapisz jako HP",
                #           command=self.save_hp_color).grid(row=0, column=1, padx=(5, 0))
                #
                # ttk.Button(color_buttons_frame, text="Zapisz jako Mana",
                #           command=self.save_mana_color).grid(row=0, column=2, padx=(5, 0))
                #
                # ttk.Button(color_buttons_frame, text="Zapisz Niestandardowy",
                #           command=self.save_custom_color).grid(row=0, column=3, padx=(5, 0))
                #
                # # Saved colors display
                # ttk.Label(color_frame, text="Zapisane kolory:").grid(row=9, column=0, sticky=tk.W, pady=(10, 0))
                # self.saved_colors_var = tk.StringVar(value="HP: brak, Mana: brak")
                # ttk.Label(color_frame, textvariable=self.saved_colors_var, foreground="purple").grid(row=10, column=0, sticky=tk.W)
                #
                # # Test all saved
                # ttk.Button(color_frame, text="Test Wszystkich Zapisanych Kolorów",
                #           command=self.test_all_saved_colors).grid(row=11, column=0, pady=(10, 0), sticky=tk.W)gion
                cv2.imwrite(f"{debug_dir}/region_original_{timestamp}.png", roi)

                # Zapisz przetworzone wersje
                cv2.imwrite(f"{debug_dir}/region_wow_processed_{timestamp}.png",
                            self._preprocess_for_wow_numbers(roi))

            except Exception as e:
                results["debug_save"] = f"Debug save error: {e}"

            return results

        except Exception as e:
            return {"error": f"OCR test failed: {e}"}
    def detect_hp_mana_numbers(self, image: np.ndarray) -> Dict[str, Any]:
        """Wykryj liczby HP/Mana z obrazu"""
        # Znajdź paski HP/Mana
        color_results = self.detect_health_mana_bars(image)

        numbers = {}

        # Dla każdego paska, sprawdź region z liczbami (zwykle po prawej)
        for bar_type in ['health_bars', 'mana_bars']:
            numbers[bar_type] = []

            for bar in color_results[bar_type]:
                # Region z liczbami zwykle 20px w prawo od paska
                text_x = bar['x'] + bar['width'] + 5
                text_y = bar['y'] - 2
                text_w = 60  # Szerokość dla tekstu "1000/1000"
                text_h = bar['height'] + 4

                # Sprawdź czy region mieści się w obrazie
                if text_x + text_w < image.shape[1] and text_y + text_h < image.shape[0]:
                    number_regions = [(text_x, text_y, text_w, text_h)]
                    detected_numbers = self.extract_numbers_from_regions(image, number_regions)

                    if detected_numbers:
                        numbers[bar_type].extend(detected_numbers)

        return numbers
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.template_matcher = TemplateMatcher(config['paths']['templates'])

        # Sprawdź czy OCR jest dostępny
        self.ocr_available = False
        try:
            import pytesseract
            self.ocr_config = '--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789%'  # Tylko cyfry i %
            self.ocr_config_text = '--oem 3 --psm 6'  # Pełny tekst
            self.ocr_available = True
            print("✓ OCR (Tesseract) dostępny")
        except ImportError:
            print("⚠ OCR niedostępny - zainstaluj: pip install pytesseract")
        except Exception as e:
            print(f"⚠ OCR problem: {e}")

    def analyze_image(self, image: np.ndarray) -> Dict[str, Any]:
        """Kompletna analiza obrazu"""
        results = {
            'templates': self.template_matcher.find_all_templates(image),
            'colors': self.detect_health_mana_bars(image),
            'text': self.extract_text_regions(image) if self.ocr_available else [],
            'ui_elements': self.detect_ui_elements(image)
        }

        return results

    def detect_health_mana_bars(self, image: np.ndarray) -> Dict[str, Any]:
        """Wykryj paski HP/Mana po kolorach"""
        try:
            # Konwertuj do HSV dla lepszego wykrywania kolorów
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # Zakresy kolorów dla HP (czerwony) i Mana (niebieski)
            # HP - czerwony
            red_lower1 = np.array([0, 50, 50])
            red_upper1 = np.array([10, 255, 255])
            red_lower2 = np.array([170, 50, 50])
            red_upper2 = np.array([180, 255, 255])

            # Mana - niebieski
            blue_lower = np.array([100, 50, 50])
            blue_upper = np.array([130, 255, 255])

            # Maski kolorów
            mask_red1 = cv2.inRange(hsv, red_lower1, red_upper1)
            mask_red2 = cv2.inRange(hsv, red_lower2, red_upper2)
            mask_red = cv2.bitwise_or(mask_red1, mask_red2)

            mask_blue = cv2.inRange(hsv, blue_lower, blue_upper)

            # Znajdź kontury
            health_bars = self._find_bar_contours(mask_red, "health")
            mana_bars = self._find_bar_contours(mask_blue, "mana")

            return {
                'health_bars': health_bars,
                'mana_bars': mana_bars
            }

        except Exception as e:
            print(f"Błąd podczas wykrywania pasków HP/Mana: {e}")
            return {'health_bars': [], 'mana_bars': []}

    def _find_bar_contours(self, mask: np.ndarray, bar_type: str) -> List[Dict[str, Any]]:
        """Znajdź kontury pasków"""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bars = []
        for contour in contours:
            area = cv2.contourArea(contour)

            # Filtruj małe obszary
            if area < 100:
                continue

            # Pobierz prostokąt otaczający
            x, y, w, h = cv2.boundingRect(contour)

            # Sprawdź proporcje (paski są zwykle szerokie i niskie)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 2:  # Minimalna proporcja dla paska
                continue

            bar_info = {
                'type': bar_type,
                'x': int(x),
                'y': int(y),
                'width': int(w),
                'height': int(h),
                'area': int(area),
                'center_x': int(x + w // 2),
                'center_y': int(y + h // 2)
            }

            bars.append(bar_info)

        return bars

    def extract_text_regions(self, image: np.ndarray, regions: List[Tuple[int, int, int, int]] = None) -> List[
        Dict[str, Any]]:
        """Wyciągnij tekst z obrazu (OCR)"""
        if not self.ocr_available:
            return []

        try:
            import pytesseract

            # Jeśli nie podano regionów, przeanalizuj cały obraz
            if regions is None:
                regions = [(0, 0, image.shape[1], image.shape[0])]

            text_results = []

            for i, (x, y, w, h) in enumerate(regions):
                # Wytnij region
                roi = image[y:y + h, x:x + w]

                # Preprocessing dla OCR
                processed = self._preprocess_for_ocr(roi)

                # OCR
                try:
                    text = pytesseract.image_to_string(processed, config=self.ocr_config).strip()

                    if text:  # Tylko jeśli znaleziono tekst
                        text_info = {
                            'region_id': i,
                            'text': text,
                            'x': x,
                            'y': y,
                            'width': w,
                            'height': h,
                            'confidence': self._calculate_text_confidence(processed, text)
                        }
                        text_results.append(text_info)

                except Exception as ocr_error:
                    print(f"Błąd OCR dla regionu {i}: {ocr_error}")

            return text_results

        except Exception as e:
            print(f"Błąd podczas ekstrakcji tekstu: {e}")
            return []

    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """Preprocessing obrazu dla lepszego OCR"""
        # Konwertuj do skali szarości
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Zwiększ kontrast
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=20)

        # Rozmycie Gaussowskie
        gray = cv2.GaussianBlur(gray, (1, 1), 0)

        # Progowanie
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return thresh

    def _calculate_text_confidence(self, processed_image: np.ndarray, text: str) -> float:
        """Oblicz pewność rozpoznania tekstu"""
        try:
            # Prosta heurystyka - im więcej białych pikseli (tekst), tym lepiej
            white_pixels = np.sum(processed_image == 255)
            total_pixels = processed_image.size

            white_ratio = white_pixels / total_pixels

            # Bonus za długość tekstu
            text_bonus = min(len(text) / 10, 1.0)

            confidence = (white_ratio + text_bonus) / 2
            return min(confidence, 1.0)

        except:
            return 0.5  # Domyślna pewność

    def detect_ui_elements(self, image: np.ndarray) -> Dict[str, Any]:
        """Wykryj elementy interfejsu (przyciski, panele)"""
        try:
            # Konwertuj do skali szarości
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Wykryj krawędzie
            edges = cv2.Canny(gray, 50, 150)

            # Znajdź kontury
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            ui_elements = []

            for contour in contours:
                area = cv2.contourArea(contour)

                # Filtruj małe elementy
                if area < 500:
                    continue

                # Aproksymacja konturu
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)

                # Prostokąt otaczający
                x, y, w, h = cv2.boundingRect(contour)

                element_info = {
                    'type': 'ui_element',
                    'x': int(x),
                    'y': int(y),
                    'width': int(w),
                    'height': int(h),
                    'area': int(area),
                    'corners': len(approx),
                    'aspect_ratio': w / h if h > 0 else 0
                }

                # Klasyfikacja na podstawie kształtu
                if len(approx) == 4 and 0.8 <= element_info['aspect_ratio'] <= 1.2:
                    element_info['probable_type'] = 'button'
                elif element_info['aspect_ratio'] > 3:
                    element_info['probable_type'] = 'panel'
                else:
                    element_info['probable_type'] = 'unknown'

                ui_elements.append(element_info)

            return {'elements': ui_elements}

        except Exception as e:
            print(f"Błąd podczas wykrywania elementów UI: {e}")
            return {'elements': []}

    def create_template_from_region(self, image: np.ndarray, x: int, y: int,
                                    width: int, height: int, name: str,
                                    category: str = "ui", description: str = "") -> bool:
        """Utwórz wzorzec z regionu obrazu"""
        try:
            # Wytnij region
            template = image[y:y + height, x:x + width]

            # Zapisz wzorzec
            return self.template_matcher.save_template(
                template, name, description, category
            )

        except Exception as e:
            print(f"Błąd podczas tworzenia wzorca: {e}")
            return False

    def find_and_click_template(self, image: np.ndarray, template_name: str,
                                input_controller) -> bool:
        """Znajdź wzorzec i kliknij w niego"""
        matches = self.template_matcher.find_template(image, template_name)

        if matches:
            # Kliknij w pierwszy (najlepszy) wynik
            best_match = matches[0]
            success = input_controller.click(best_match['center_x'], best_match['center_y'])

            if success:
                print(
                    f"Kliknięto w wzorzec {template_name} na pozycji ({best_match['center_x']}, {best_match['center_y']})")

            return success
        else:
            print(f"Nie znaleziono wzorca {template_name}")
            return False

    def get_template_matcher(self) -> TemplateMatcher:
        """Pobierz template matcher"""
        return self.template_matcher

    def visualize_results(self, image: np.ndarray, results: Dict[str, Any]) -> np.ndarray:
        """Narysuj wyniki analizy na obrazie"""
        vis_image = image.copy()

        try:
            # Rysuj dopasowane wzorce
            if 'templates' in results:
                for template_name, matches in results['templates'].items():
                    for match in matches:
                        # Prostokąt wokół dopasowania
                        cv2.rectangle(vis_image,
                                      (match['x'], match['y']),
                                      (match['x'] + match['width'], match['y'] + match['height']),
                                      (0, 255, 0), 2)

                        # Etykieta
                        label = f"{template_name.split('/')[-1]}: {match['confidence']:.2f}"
                        cv2.putText(vis_image, label,
                                    (match['x'], match['y'] - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Rysuj paski HP/Mana
            if 'colors' in results:
                for bar in results['colors'].get('health_bars', []):
                    cv2.rectangle(vis_image,
                                  (bar['x'], bar['y']),
                                  (bar['x'] + bar['width'], bar['y'] + bar['height']),
                                  (0, 0, 255), 2)  # Czerwony dla HP
                    cv2.putText(vis_image, "HP",
                                (bar['x'], bar['y'] - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

                for bar in results['colors'].get('mana_bars', []):
                    cv2.rectangle(vis_image,
                                  (bar['x'], bar['y']),
                                  (bar['x'] + bar['width'], bar['y'] + bar['height']),
                                  (255, 0, 0), 2)  # Niebieski dla Mana
                    cv2.putText(vis_image, "MANA",
                                (bar['x'], bar['y'] - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

            # Rysuj wykryty tekst
            if 'text' in results:
                for text_info in results['text']:
                    cv2.rectangle(vis_image,
                                  (text_info['x'], text_info['y']),
                                  (text_info['x'] + text_info['width'], text_info['y'] + text_info['height']),
                                  (255, 255, 0), 1)  # Żółty dla tekstu

            return vis_image

        except Exception as e:
            print(f"Błąd podczas wizualizacji: {e}")
            return vis_image