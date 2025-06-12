# src/vision/vision_engine.py
import cv2
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime

from vision.template_matcher import TemplateMatcher
from .detectors.monster_detector import MonsterDetector

import os
import logging
import json
from pathlib import Path

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

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.template_matcher = TemplateMatcher(config)

        # Wczytaj zapisane lokalizacje OCR
        self.ocr_regions = self.load_ocr_regions()

        # Inicjalizacja OCR
        self.ocr_available = False
        self.ocr_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789/%'  # Zmieniono PSM na 7
        self.ocr_config_text = '--oem 3 --psm 6'  # Pełny tekst
        model_path = r"/models/yolo_models\monsters.pt"
        self.monster_detector = MonsterDetector(model_path, confidence_threshold=0.5)
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
                    logging.info(f"✓ Tesseract znaleziony: {path}")
                    self.ocr_available = True
                    break
            else:
                logging.warning("⚠ Tesseract nie znaleziony w standardowych lokalizacjach")

        except ImportError:
            logging.error("⚠ pytesseract nie zainstalowany - zainstaluj: pip install pytesseract")
        except Exception as e:
            logging.error(f"⚠ OCR problem: {e}")

        if self.ocr_available:
            logging.info("✓ OCR (Tesseract) skonfigurowany i gotowy do użycia")
    def detect_monsters(self, image):
        """Detect monsters in image"""
        return self.monster_detector.detect_monsters(image)
    def _preprocess_for_wow_numbers(self, image: np.ndarray) -> np.ndarray:
        """Optymalizowany preprocessing dla małych regionów z liczbami WoW"""
        try:
            # 1. Konwersja do skali szarości - standardowa metoda
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # 2. NAJPIERW zwiększ rozmiar - kluczowe dla małych regionów!
            scale = 6  # Większe skalowanie dla bardzo małych regionów
            height, width = gray.shape
            enlarged = cv2.resize(gray, (width * scale, height * scale),
                                  interpolation=cv2.INTER_CUBIC)

            # 3. Delikatna normalizacja (nie za agresywna)
            normalized = cv2.normalize(enlarged, None, 0, 255, cv2.NORM_MINMAX)

            # 4. Zmniejszony kontrast - dla białych liczb WoW
            alpha = 1.8  # Zmniejszono z 4.0
            beta = 40  # Zwiększono z 30
            contrast = cv2.convertScaleAbs(normalized, alpha=alpha, beta=beta)

            # 5. Bardzo delikatne rozmycie dla wygładzenia pikseli
            blurred = cv2.GaussianBlur(contrast, (3, 3), 0)

            # 6. Dla białego tekstu na ciemnym tle - użyj prostego threshold
            # Biały tekst WoW ma zwykle wysokie wartości (200+)
            _, thresh = cv2.threshold(blurred, 180, 255, cv2.THRESH_BINARY)

            # 7. Minimalna morfologia - tylko jeśli potrzebna
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            # 8. Dodaj białe obramowanie dla lepszego OCR
            bordered = cv2.copyMakeBorder(cleaned, 15, 15, 15, 15,
                                          cv2.BORDER_CONSTANT, value=0)

            return bordered

        except Exception as e:
            logging.error(f"Błąd podczas przetwarzania obrazu: {e}")
            return image

    def test_manual_ocr_region(self, image: np.ndarray, x: int, y: int, w: int, h: int) -> Dict[str, str]:
        """Test OCR w ręcznie wybranym regionie - KOMPATYBILNOŚĆ z auto-detekcją"""
        if not self.ocr_available:
            logging.error("OCR nie jest dostępny")
            return {'error': 'OCR nie jest dostępny'}

        # === PEŁNA WALIDACJA ===
        if image is None:
            logging.error("test_manual_ocr_region: Otrzymano None jako obraz")
            return {'error': 'Image is None'}

        if image.size == 0:
            logging.error("test_manual_ocr_region: Otrzymano pusty obraz")
            return {'error': 'Image is empty'}

        # Sprawdź rozmiary obrazu
        try:
            img_height, img_width = image.shape[:2]
        except Exception as e:
            logging.error(f"test_manual_ocr_region: Nie można odczytać kształtu obrazu: {e}")
            return {'error': f'Cannot read image shape: {e}'}

        logging.info(f"test_manual_ocr_region: Obraz {img_width}x{img_height}, region ({x},{y},{w},{h})")

        # === AUTO-DETEKCJA: CZY TO PEŁNY OBRAZ CZY WYCIĘTY REGION ===
        expected_region_size = w * h
        image_size = img_width * img_height

        # Jeśli obraz jest mały i podobny do rozmiaru regionu, to prawdopodobnie już wycięty
        if img_width <= w + 10 and img_height <= h + 10:
            logging.info(f"test_manual_ocr_region: Wykryto już wycięty region. Używam całego obrazu.")
            roi = image  # Użyj całego obrazu jako ROI
        else:
            # Normalny tryb - wytnij region z większego obrazu
            # Sprawdź czy region mieści się w obrazie
            if x < 0 or y < 0:
                logging.error(f"test_manual_ocr_region: Negatywne współrzędne: ({x},{y})")
                return {'error': f'Negative coordinates: ({x},{y})'}

            if w <= 0 or h <= 0:
                logging.error(f"test_manual_ocr_region: Nieprawidłowy rozmiar regionu: {w}x{h}")
                return {'error': f'Invalid region size: {w}x{h}'}

            if x + w > img_width or y + h > img_height:
                logging.error(
                    f"test_manual_ocr_region: Region wykracza poza obraz. Region: ({x},{y},{w},{h}), Obraz: {img_width}x{img_height}")
                return {
                    'error': f'Region outside image bounds. Region: ({x},{y},{w},{h}), Image: {img_width}x{img_height}'}

            # Wytnij region z dodatkowymi sprawdzeniami
            try:
                roi = image[y:y + h, x:x + w]
            except Exception as e:
                logging.error(f"test_manual_ocr_region: Błąd podczas wycinania regionu: {e}")
                return {'error': f'Error cutting region: {e}'}

        if roi is None:
            logging.error("test_manual_ocr_region: ROI jest None")
            return {'error': 'ROI is None'}

        if roi.size == 0:
            logging.error("test_manual_ocr_region: ROI jest pusty")
            return {'error': 'ROI is empty'}

        logging.info(f"test_manual_ocr_region: ROI rozmiar: {roi.shape}")

        try:
            import pytesseract

            # Przetwórz obraz z dodatkową walidacją
            try:
                processed = self._preprocess_for_wow_numbers_safe(roi)
            except Exception as e:
                logging.error(f"test_manual_ocr_region: Błąd podczas preprocessingu: {e}")
                return {'error': f'Preprocessing error: {e}'}

            if processed is None:
                logging.error("test_manual_ocr_region: Processed image jest None")
                return {'error': 'Processed image is None'}

            if processed.size == 0:
                logging.error("test_manual_ocr_region: Processed image jest pusty")
                return {'error': 'Processed image is empty'}

            # Testuj różne konfiguracje OCR
            results = {}

            # Test 1: Tylko cyfry i /
            try:
                text = pytesseract.image_to_string(processed, config=self.ocr_config).strip()
                results['numbers_only'] = text
                logging.info(f"OCR (numbers_only): '{text}'")
            except Exception as e:
                logging.error(f"Błąd OCR (numbers_only): {e}")
                results['numbers_only'] = f"Error: {e}"

            # Test 2: Pełny tekst
            try:
                text = pytesseract.image_to_string(processed, config=self.ocr_config_text).strip()
                results['full_text'] = text
                logging.info(f"OCR (full_text): '{text}'")
            except Exception as e:
                logging.error(f"Błąd OCR (full_text): {e}")
                results['full_text'] = f"Error: {e}"

            # Test 3: Bez konfiguracji
            try:
                text = pytesseract.image_to_string(processed).strip()
                results['default'] = text
                logging.info(f"OCR (default): '{text}'")
            except Exception as e:
                logging.error(f"Błąd OCR (default): {e}")
                results['default'] = f"Error: {e}"

            return results

        except Exception as e:
            logging.error(f"test_manual_ocr_region: Ogólny błąd: {e}")
            return {'error': str(e)}

    def _preprocess_for_wow_numbers_safe(self, image: np.ndarray) -> np.ndarray:
        """Bezpieczny preprocessing z pełną walidacją i obsługą kolorowych teł"""
        try:
            # Sprawdź czy obraz nie jest pusty
            if image is None:
                logging.error("_preprocess_for_wow_numbers_safe: Input image is None")
                return np.zeros((50, 50), dtype=np.uint8)

            if image.size == 0:
                logging.error("_preprocess_for_wow_numbers_safe: Input image is empty")
                return np.zeros((50, 50), dtype=np.uint8)

            # Sprawdź minimalny rozmiar
            if len(image.shape) < 2:
                logging.error(f"_preprocess_for_wow_numbers_safe: Invalid image shape: {image.shape}")
                return np.zeros((50, 50), dtype=np.uint8)

            if image.shape[0] < 1 or image.shape[1] < 1:
                logging.error(f"_preprocess_for_wow_numbers_safe: Image too small: {image.shape}")
                return np.zeros((50, 50), dtype=np.uint8)

            # === ULEPSZONA KONWERSJA DO SKALI SZAROŚCI ===
            try:
                if len(image.shape) == 3:
                    if image.shape[2] == 0:
                        logging.error("_preprocess_for_wow_numbers_safe: Image has 0 channels")
                        return np.zeros((50, 50), dtype=np.uint8)

                    # Spróbuj różne metody konwersji dla różnych teł
                    # Metoda 1: Standardowa BGR->GRAY
                    gray_standard = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                    # Metoda 2: Używaj kanału z najwyższym kontrastem
                    b, g, r = cv2.split(image)

                    # Sprawdź który kanał ma najwyższy kontrast (dla białego tekstu)
                    contrast_b = np.std(b)
                    contrast_g = np.std(g)
                    contrast_r = np.std(r)

                    logging.info(f"Kontrast kanałów - B: {contrast_b:.2f}, G: {contrast_g:.2f}, R: {contrast_r:.2f}")

                    # Wybierz kanał z najwyższym kontrastem
                    if contrast_r >= contrast_g and contrast_r >= contrast_b:
                        gray = r
                        logging.info("Używam kanału czerwonego")
                    elif contrast_g >= contrast_b:
                        gray = g
                        logging.info("Używam kanału zielonego")
                    else:
                        gray = b
                        logging.info("Używam kanału niebieskiego")

                    # Porównaj z standardową konwersją i wybierz lepszą
                    if np.std(gray_standard) > np.std(gray):
                        gray = gray_standard
                        logging.info("Używam standardowej konwersji BGR->GRAY")

                else:
                    gray = image.copy()
            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Color conversion failed: {e}")
                return np.zeros((50, 50), dtype=np.uint8)

            if gray is None or gray.size == 0:
                logging.error("_preprocess_for_wow_numbers_safe: Gray conversion resulted in empty image")
                return np.zeros((50, 50), dtype=np.uint8)

            # 2. Zwiększ rozmiar z walidacją
            try:
                scale = 6
                height, width = gray.shape
                new_width = max(width * scale, 30)  # Minimum 30px
                new_height = max(height * scale, 10)  # Minimum 10px

                enlarged = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Resize failed: {e}")
                enlarged = gray

            if enlarged is None or enlarged.size == 0:
                logging.error("_preprocess_for_wow_numbers_safe: Resize resulted in empty image")
                return gray

            # 3. Normalizacja z walidacją
            try:
                normalized = cv2.normalize(enlarged, None, 0, 255, cv2.NORM_MINMAX)
            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Normalization failed: {e}")
                normalized = enlarged

            # 4. Dynamiczny kontrast na podstawie histogramu
            try:
                # Sprawdź czy obraz jest ciemny czy jasny
                mean_intensity = np.mean(normalized)
                logging.info(f"Średnia intensywność: {mean_intensity:.2f}")

                if mean_intensity < 128:  # Ciemny obraz (tekst jasny na ciemnym tle)
                    alpha = 2.5  # Większy kontrast dla ciemnych obrazów
                    beta = 60
                else:  # Jasny obraz
                    alpha = 1.5
                    beta = 20

                contrast = cv2.convertScaleAbs(normalized, alpha=alpha, beta=beta)
            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Contrast adjustment failed: {e}")
                contrast = normalized

            # 5. Rozmycie z walidacją
            try:
                blurred = cv2.GaussianBlur(contrast, (3, 3), 0)
            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Blur failed: {e}")
                blurred = contrast

            # 6. Adaptacyjny threshold zamiast stałego
            try:
                # Spróbuj kilka metod threshold
                _, thresh1 = cv2.threshold(blurred, 180, 255, cv2.THRESH_BINARY)
                _, thresh2 = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                thresh3 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

                # Wybierz threshold z najlepszym kontrastem
                std1 = np.std(thresh1)
                std2 = np.std(thresh2)
                std3 = np.std(thresh3)

                logging.info(f"Threshold std - Fixed: {std1:.2f}, OTSU: {std2:.2f}, Adaptive: {std3:.2f}")

                if std2 >= std1 and std2 >= std3:
                    thresh = thresh2
                    logging.info("Używam OTSU threshold")
                elif std3 >= std1:
                    thresh = thresh3
                    logging.info("Używam Adaptive threshold")
                else:
                    thresh = thresh1
                    logging.info("Używam Fixed threshold")

            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Threshold failed: {e}")
                thresh = blurred

            # 7. Morfologia z walidacją
            try:
                kernel = np.ones((2, 2), np.uint8)
                cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Morphology failed: {e}")
                cleaned = thresh

            # 8. Border z walidacją
            try:
                bordered = cv2.copyMakeBorder(cleaned, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=0)
            except Exception as e:
                logging.error(f"_preprocess_for_wow_numbers_safe: Border failed: {e}")
                bordered = cleaned

            return bordered

        except Exception as e:
            logging.error(f"_preprocess_for_wow_numbers_safe: Critical error: {e}")
            return np.zeros((50, 50), dtype=np.uint8)

    # === NOWE FUNKCJE KTÓRE UŻYWAJĄ test_manual_ocr_region ===

    def get_hp_mana_values_like_test(self, image: np.ndarray) -> Dict[str, Any]:
        """Pobierz HP/Mana DOKŁADNIE tak samo jak test_manual_ocr_region - ULEPSZONE"""
        if not self.ocr_available:
            return {'hp': None, 'mana': None, 'error': 'OCR niedostępny'}

        # Użyj DOKŁADNIE tych samych regionów co w test
        hp_region = self.config['ocr_regions']['hp_region']  # [270, 125, 50, 29]
        mana_region = self.config['ocr_regions']['mana_region']  # [270, 147, 50, 29]

        results = {'hp': None, 'mana': None, 'debug': {}}

        # === PRZETWARZAJ ZAWSZE OBA REGIONY NIEZALEŻNIE ===

        # HP - z pełną izolacją błędów
        logging.info("=== ROZPOCZYNAM PRZETWARZANIE HP ===")
        try:
            x, y, w, h = hp_region
            logging.info(f"HP region: ({x},{y},{w},{h})")

            hp_ocr_result = self.test_manual_ocr_region(image.copy(), x, y, w, h)  # .copy() dla bezpieczeństwa
            logging.info(f"HP OCR result: {hp_ocr_result}")

            if 'error' not in hp_ocr_result:
                # Spróbuj wyciągnąć wartość z tekstu
                for key, text in hp_ocr_result.items():
                    if text and isinstance(text, str) and not text.startswith('Error:'):
                        hp_value = self._parse_percentage_or_number(text)
                        if hp_value is not None:
                            results['hp'] = hp_value
                            results['debug']['hp_source'] = f"{key}: {text}"
                            logging.info(f"HP wartość znaleziona: {hp_value} z '{text}'")
                            break

                if results['hp'] is None:
                    logging.warning("HP: Nie udało się sparsować żadnej wartości")
                    results['debug']['hp_error'] = 'Nie udało się sparsować'
            else:
                logging.error(f"HP: OCR error - {hp_ocr_result.get('error', 'Unknown')}")
                results['debug']['hp_error'] = hp_ocr_result.get('error', 'OCR failed')

        except Exception as e:
            logging.error(f"HP: Exception podczas przetwarzania - {e}")
            results['debug']['hp_error'] = f'Exception: {e}'

        # === PRZERWA MIĘDZY REGIONAMI ===
        import time
        time.sleep(0.1)  # Mała przerwa żeby nie było konfliktów

        # MANA - z pełną izolacją błędów
        logging.info("=== ROZPOCZYNAM PRZETWARZANIE MANA ===")
        try:
            x, y, w, h = mana_region
            logging.info(f"Mana region: ({x},{y},{w},{h})")

            mana_ocr_result = self.test_manual_ocr_region(image.copy(), x, y, w, h)  # .copy() dla bezpieczeństwa
            logging.info(f"Mana OCR result: {mana_ocr_result}")

            if 'error' not in mana_ocr_result:
                # Spróbuj wyciągnąć wartość z tekstu
                for key, text in mana_ocr_result.items():
                    if text and isinstance(text, str) and not text.startswith('Error:'):
                        mana_value = self._parse_percentage_or_number(text)
                        if mana_value is not None:
                            results['mana'] = mana_value
                            results['debug']['mana_source'] = f"{key}: {text}"
                            logging.info(f"Mana wartość znaleziona: {mana_value} z '{text}'")
                            break

                if results['mana'] is None:
                    logging.warning("Mana: Nie udało się sparsować żadnej wartości")
                    results['debug']['mana_error'] = 'Nie udało się sparsować'
            else:
                logging.error(f"Mana: OCR error - {mana_ocr_result.get('error', 'Unknown')}")
                results['debug']['mana_error'] = mana_ocr_result.get('error', 'OCR failed')

        except Exception as e:
            logging.error(f"Mana: Exception podczas przetwarzania - {e}")
            results['debug']['mana_error'] = f'Exception: {e}'

        # === PODSUMOWANIE ===
        logging.info(f"=== WYNIKI KOŃCOWE: HP={results['hp']}, Mana={results['mana']} ===")

        return results

    def _parse_percentage_or_number(self, text: str) -> Optional[float]:
        """Parsuj tekst do wartości procentowej lub liczbowej"""
        if not text:
            return None

        try:
            # Usuń białe znaki
            text = text.strip()

            # Format "100%"
            if '%' in text:
                number_part = text.replace('%', '').strip()
                if number_part.isdigit():
                    return float(number_part)

            # Format "1000/1000" -> oblicz procent
            if '/' in text:
                parts = text.split('/')
                if len(parts) == 2:
                    try:
                        current = float(parts[0].strip())
                        maximum = float(parts[1].strip())
                        if maximum > 0:
                            return (current / maximum) * 100
                    except:
                        pass

            # Pojedyncza liczba
            if text.isdigit():
                return float(text)

            return None

        except Exception as e:
            logging.error(f"Błąd parsowania '{text}': {e}")
            return None

    # ALIASY dla kompatybilności wstecznej
    def extract_hp_mana_values(self, image: np.ndarray) -> Dict[str, Any]:
        """Alias dla get_hp_mana_values_like_test - używa dokładnie tej samej metody co test"""
        return self.get_hp_mana_values_like_test(image)

    def get_hp_percentage(self, image: np.ndarray) -> Optional[float]:
        """Pobierz tylko HP jako procent"""
        result = self.get_hp_mana_values_like_test(image)
        return result.get('hp')

    def get_mana_percentage(self, image: np.ndarray) -> Optional[float]:
        """Pobierz tylko Mana jako procent"""
        result = self.get_hp_mana_values_like_test(image)
        return result.get('mana')

    def debug_compare_methods(self, image: np.ndarray):
        """Porównaj wyniki test_manual_ocr_region vs extract_hp_mana_values"""
        print("=== PORÓWNANIE METOD ===")

        hp_region = self.config['ocr_regions']['hp_region']
        mana_region = self.config['ocr_regions']['mana_region']

        print(f"Obraz: {image.shape if image is not None else 'None'}")
        print(f"HP region: {hp_region}")
        print(f"Mana region: {mana_region}")

        # Test metoda
        print("\n--- TEST METHOD ---")
        x, y, w, h = hp_region
        hp_test = self.test_manual_ocr_region(image, x, y, w, h)
        print(f"HP test: {hp_test}")

        x, y, w, h = mana_region
        mana_test = self.test_manual_ocr_region(image, x, y, w, h)
        print(f"Mana test: {mana_test}")

        # Nowa metoda
        print("\n--- NEW METHOD ---")
        new_result = self.get_hp_mana_values_like_test(image)
        print(f"New result: {new_result}")

    # === RESZTA STARYCH FUNKCJI ===

    def _extract_numbers_from_text(self, text: str) -> List[int]:
        """Wyciągnij liczby z tekstu OCR"""
        try:
            # Usuń wszystkie znaki oprócz cyfr i /
            cleaned = ''.join(c for c in text if c.isdigit() or c == '/')

            if '/' in cleaned:
                # Format "1000/1000"
                parts = cleaned.split('/')
                if len(parts) == 2 and parts[0] and parts[1]:
                    current, max_val = map(int, parts)
                    return [current, max_val]
            else:
                # Pojedyncza liczba
                return [int(cleaned)] if cleaned else []
        except Exception as e:
            logging.error(f"Błąd podczas wyciągania liczb z tekstu '{text}': {e}")
            return []

    def extract_wow_hp_mana_text(self, image: np.ndarray) -> Dict[str, Any]:
        """Stara funkcja - używa już nowej metody"""
        return self.get_hp_mana_values_like_test(image)

    def detect_wow_ui_numbers(self, image: np.ndarray) -> Dict[str, Any]:
        """Kompletna detekcja liczb w WoW UI"""
        results = {
            'hp_mana_numbers': self.extract_wow_hp_mana_text(image),
            'general_numbers': [],
            'debug_regions': []
        }

        # Dodaj debug regiony z ustawień
        hp_region = self.config['ocr_regions']['hp_region']
        mana_region = self.config['ocr_regions']['mana_region']

        results['debug_regions'] = [
            {
                'id': 0,
                'x': hp_region[0], 'y': hp_region[1],
                'width': hp_region[2], 'height': hp_region[3],
                'purpose': 'hp_region'
            },
            {
                'id': 1,
                'x': mana_region[0], 'y': mana_region[1],
                'width': mana_region[2], 'height': mana_region[3],
                'purpose': 'mana_region'
            }
        ]

        return results

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

    def visualize_results(self, image: np.ndarray, results: Dict[str, Any]) -> np.ndarray:
        """Narysuj wyniki analizy na obrazie"""
        vis_image = image.copy()

        try:
            # Rysuj dopasowane wzorce
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

            # Rysuj paski HP/Mana
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

            # Rysuj wykryty tekst
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

    def save_ocr_regions(self, regions: Dict[str, Tuple[int, int, int, int]]) -> bool:
        """Zapisz lokalizacje regionów OCR do pliku"""
        try:
            regions_file = Path(self.config['paths']['data']) / 'ocr_regions.json'
            with open(regions_file, 'w') as f:
                json.dump(regions, f, indent=4)
            logging.info(f"Zapisano lokalizacje OCR do {regions_file}")
            return True
        except Exception as e:
            logging.error(f"Błąd podczas zapisywania lokalizacji OCR: {e}")
            return False

    def load_ocr_regions(self) -> Dict[str, Tuple[int, int, int, int]]:
        """Wczytaj lokalizacje regionów OCR z pliku"""
        try:
            regions_file = Path(self.config['paths']['data']) / 'ocr_regions.json'
            if regions_file.exists():
                with open(regions_file, 'r') as f:
                    regions = json.load(f)
                logging.info(f"Wczytano lokalizacje OCR z {regions_file}")
                return regions
            return {}
        except Exception as e:
            logging.error(f"Błąd podczas wczytywania lokalizacji OCR: {e}")
            return {}