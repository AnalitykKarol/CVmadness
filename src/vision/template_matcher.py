import cv2
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import os
import json
from datetime import datetime


class TemplateMatcher:
    """Klasa do dopasowywania wzorców (template matching)"""

    def __init__(self, config: Dict[str, Any]):
        if isinstance(config, dict) and 'paths' in config and 'templates' in config['paths']:
            self.templates_dir = config['paths']['templates']
        else:
            self.templates_dir = "data/templates"
        self.templates = {}  # Załadowane wzorce
        self.template_info = {}  # Metadane wzorców

        # Utwórz folder jeśli nie istnieje
        os.makedirs(self.templates_dir, exist_ok=True)

        # Załaduj istniejące wzorce
        self.load_all_templates()

    def save_template(self, image: np.ndarray, name: str, description: str = "",
                      category: str = "general", confidence_threshold: float = 0.8) -> bool:
        """Zapisz wzorzec do pliku"""
        try:
            # Utwórz folder kategorii
            category_dir = os.path.join(self.templates_dir, category)
            os.makedirs(category_dir, exist_ok=True)

            # Zapisz obraz
            template_path = os.path.join(category_dir, f"{name}.png")
            cv2.imwrite(template_path, image)

            # Zapisz metadane
            metadata = {
                "name": name,
                "description": description,
                "category": category,
                "confidence_threshold": confidence_threshold,
                "created_at": datetime.now().isoformat(),
                "width": image.shape[1],
                "height": image.shape[0]
            }

            metadata_path = os.path.join(category_dir, f"{name}.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # Dodaj do pamięci
            template_key = f"{category}/{name}"
            self.templates[template_key] = image
            self.template_info[template_key] = metadata

            print(f"Zapisano wzorzec: {template_key}")
            return True

        except Exception as e:
            print(f"Błąd podczas zapisywania wzorca: {e}")
            return False

    def load_template(self, category: str, name: str) -> Optional[np.ndarray]:
        """Załaduj konkretny wzorzec"""
        try:
            template_path = os.path.join(self.templates_dir, category, f"{name}.png")
            metadata_path = os.path.join(self.templates_dir, category, f"{name}.json")

            if os.path.exists(template_path):
                template = cv2.imread(template_path)
                template_key = f"{category}/{name}"
                self.templates[template_key] = template

                # Załaduj metadane
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        self.template_info[template_key] = json.load(f)

                return template
            return None

        except Exception as e:
            print(f"Błąd podczas ładowania wzorca {category}/{name}: {e}")
            return None

    def load_all_templates(self):
        """Załaduj wszystkie wzorce z dysku"""
        try:
            for category in os.listdir(self.templates_dir):
                category_path = os.path.join(self.templates_dir, category)
                if os.path.isdir(category_path):
                    for file in os.listdir(category_path):
                        if file.endswith('.png'):
                            name = file[:-4]  # Usuń .png
                            self.load_template(category, name)

            print(f"Załadowano {len(self.templates)} wzorców")

        except Exception as e:
            print(f"Błąd podczas ładowania wzorców: {e}")

    def find_template(self, image: np.ndarray, template_name: str,
                      confidence_threshold: float = None) -> List[Dict[str, Any]]:
        """Znajdź wzorzec na obrazie"""
        if template_name not in self.templates:
            print(f"Wzorzec {template_name} nie znaleziony")
            return []

        template = self.templates[template_name]
        template_info = self.template_info.get(template_name, {})

        # Użyj progiem z metadanych lub podanym
        threshold = confidence_threshold or template_info.get('confidence_threshold', 0.8)

        return self._match_template(image, template, threshold, template_name)

    def find_all_templates(self, image: np.ndarray, category: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Znajdź wszystkie wzorce na obrazie"""
        results = {}

        for template_name in self.templates:
            # Filtruj po kategorii jeśli podana
            if category and not template_name.startswith(f"{category}/"):
                continue

            matches = self.find_template(image, template_name)
            if matches:
                results[template_name] = matches

        return results

    def _match_template(self, image: np.ndarray, template: np.ndarray,
                        threshold: float, template_name: str) -> List[Dict[str, Any]]:
        """Wykonaj dopasowanie wzorca"""
        try:
            # Konwertuj do skali szarości jeśli potrzeba
            if len(image.shape) == 3:
                gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray_image = image

            if len(template.shape) == 3:
                gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            else:
                gray_template = template

            # Dopasowanie wzorca
            result = cv2.matchTemplate(gray_image, gray_template, cv2.TM_CCOEFF_NORMED)

            # Znajdź wszystkie dopasowania powyżej progu
            locations = np.where(result >= threshold)
            matches = []

            template_h, template_w = gray_template.shape

            for pt in zip(*locations[::-1]):  # Zamień x,y
                confidence = float(result[pt[1], pt[0]])

                match_info = {
                    'template_name': template_name,
                    'confidence': confidence,
                    'x': int(pt[0]),
                    'y': int(pt[1]),
                    'width': template_w,
                    'height': template_h,
                    'center_x': int(pt[0] + template_w // 2),
                    'center_y': int(pt[1] + template_h // 2)
                }
                matches.append(match_info)

            # Usuń nakładające się dopasowania (Non-Maximum Suppression)
            if len(matches) > 1:
                matches = self._non_max_suppression(matches)

            return matches

        except Exception as e:
            print(f"Błąd podczas dopasowywania wzorca {template_name}: {e}")
            return []

    def _non_max_suppression(self, matches: List[Dict[str, Any]],
                             overlap_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Usuń nakładające się dopasowania"""
        if not matches:
            return []

        # Sortuj po pewności
        matches = sorted(matches, key=lambda x: x['confidence'], reverse=True)

        filtered_matches = []

        for match in matches:
            # Sprawdź czy nakłada się z już zaakceptowanymi
            overlaps = False

            for accepted_match in filtered_matches:
                if self._calculate_overlap(match, accepted_match) > overlap_threshold:
                    overlaps = True
                    break

            if not overlaps:
                filtered_matches.append(match)

        return filtered_matches

    def _calculate_overlap(self, match1: Dict[str, Any], match2: Dict[str, Any]) -> float:
        """Oblicz stopień nakładania się dwóch dopasowań"""
        x1_min, y1_min = match1['x'], match1['y']
        x1_max, y1_max = x1_min + match1['width'], y1_min + match1['height']

        x2_min, y2_min = match2['x'], match2['y']
        x2_max, y2_max = x2_min + match2['width'], y2_min + match2['height']

        # Obszar przecięcia
        intersection_x_min = max(x1_min, x2_min)
        intersection_y_min = max(y1_min, y2_min)
        intersection_x_max = min(x1_max, x2_max)
        intersection_y_max = min(y1_max, y2_max)

        if intersection_x_max <= intersection_x_min or intersection_y_max <= intersection_y_min:
            return 0.0

        intersection_area = (intersection_x_max - intersection_x_min) * (intersection_y_max - intersection_y_min)

        # Obszar unii
        area1 = match1['width'] * match1['height']
        area2 = match2['width'] * match2['height']
        union_area = area1 + area2 - intersection_area

        return intersection_area / union_area if union_area > 0 else 0.0

    def get_template_list(self) -> List[str]:
        """Pobierz listę dostępnych wzorców"""
        return list(self.templates.keys())

    def get_categories(self) -> List[str]:
        """Pobierz listę kategorii"""
        categories = set()
        for template_name in self.templates:
            if '/' in template_name:
                category = template_name.split('/')[0]
                categories.add(category)
        return sorted(list(categories))

    def delete_template(self, template_name: str) -> bool:
        """Usuń wzorzec"""
        try:
            if template_name in self.templates:
                category, name = template_name.split('/')

                # Usuń pliki
                template_path = os.path.join(self.templates_dir, category, f"{name}.png")
                metadata_path = os.path.join(self.templates_dir, category, f"{name}.json")

                if os.path.exists(template_path):
                    os.remove(template_path)
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)

                # Usuń z pamięci
                del self.templates[template_name]
                if template_name in self.template_info:
                    del self.template_info[template_name]

                print(f"Usunięto wzorzec: {template_name}")
                return True
            return False

        except Exception as e:
            print(f"Błąd podczas usuwania wzorca: {e}")
            return False
