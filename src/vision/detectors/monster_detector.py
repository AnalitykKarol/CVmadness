# vision/detectors/monster_detector.py
import cv2
import numpy as np
from pathlib import Path
import logging
from typing import List, Dict, Tuple

try:
    from ultralytics import YOLO

    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logging.warning("ultralytics not available - monster detection disabled")


class MonsterDetector:
    def __init__(self, model_path: str, confidence_threshold: float = 0.2):
        model_path = r"E:\Work\fun\WowCV420\models\yolo_models\monsters.pt"
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.class_names = []

        if not self.model_path.exists():
            print(f"❌ Model file not found: {model_path}")
            return

        try:
            print(f"🔄 Loading model via yolov5 package: {self.model_path}")

            # Użyj yolov5 package zamiast torch hub
            import yolov5
            self.model = yolov5.load(str(self.model_path))
            self.model.conf = self.confidence_threshold

            if hasattr(self.model, 'names'):
                self.class_names = list(self.model.names.values())

            print(f"✅ Model loaded via yolov5 package!")
            print(f"📋 Classes: {self.class_names}")

        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            self.model = None

    def is_available(self) -> bool:
        """Check if detector is available"""
        return self.model is not None and ULTRALYTICS_AVAILABLE

    def detect_monsters(self, image: np.ndarray) -> List[Dict]:
        """
        Detect monsters in image

        Args:
            image: BGR image from OpenCV

        Returns:
            List of detected monsters with format:
            {
                'class_name': str,
                'class_id': int,
                'confidence': float,
                'bbox': [x1, y1, x2, y2],
                'center': [x, y],
                'area': int
            }
        """
        if not self.is_available():
            print("❌ Monster detector not available!")
            return []

        try:
            print(f"🔍 Running YOLO on image {image.shape}")

            # Convert BGR to RGB for YOLO
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Run inference with confidence threshold
            results = self.model(rgb_image, conf=self.confidence_threshold, verbose=False)
            print(f"📊 YOLO results: {len(results)} result objects")

            monsters = []

            # Process results (ultralytics format)
            for result in results:
                if result.boxes is not None and len(result.boxes) > 0:
                    print(f"📦 Found {len(result.boxes)} detections")

                    for box in result.boxes:
                        # Get confidence
                        confidence = float(box.conf[0])
                        print(f"🎯 Detection confidence: {confidence:.3f}")

                        # Get class info
                        class_id = int(box.cls[0])
                        class_name = self.class_names[class_id] if class_id < len(
                            self.class_names) else f"class_{class_id}"
                        print(f"✅ DETECTED: {class_name} (confidence: {confidence:.3f})")

                        # Get bounding box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        bbox = [int(x1), int(y1), int(x2), int(y2)]

                        # Calculate center and area
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        area = int((x2 - x1) * (y2 - y1))

                        monster = {
                            'class_name': class_name,
                            'class_id': class_id,
                            'confidence': confidence,
                            'bbox': bbox,
                            'center': [center_x, center_y],
                            'area': area
                        }

                        monsters.append(monster)
                else:
                    print("📦 No detections found")

            print(f"🏁 Final monster count: {len(monsters)}")
            return monsters

        except Exception as e:
            print(f"💥 Monster detection FAILED: {e}")
            logging.error(f"Monster detection failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def find_nearest_monster(self, monsters: List[Dict], point: Tuple[int, int]) -> Dict:
        """Find monster nearest to given point"""
        if not monsters:
            return None

        min_distance = float('inf')
        nearest_monster = None

        px, py = point
        for monster in monsters:
            mx, my = monster['center']
            distance = ((mx - px) ** 2 + (my - py) ** 2) ** 0.5

            if distance < min_distance:
                min_distance = distance
                nearest_monster = monster

        return nearest_monster

    def find_largest_monster(self, monsters: List[Dict]) -> Dict:
        """Find largest monster by area"""
        if not monsters:
            return None

        return max(monsters, key=lambda m: m['area'])

    def filter_by_class(self, monsters: List[Dict], class_names: List[str]) -> List[Dict]:
        """Filter monsters by class names"""
        return [m for m in monsters if m['class_name'] in class_names]

    def draw_detections(self, image: np.ndarray, monsters: List[Dict]) -> np.ndarray:
        """Draw monster detections on image"""
        vis_image = image.copy()

        for monster in monsters:
            x1, y1, x2, y2 = monster['bbox']
            class_name = monster['class_name']
            confidence = monster['confidence']

            # Colors for different classes
            colors = {
                'orc': (0, 255, 0),  # Green
                'skeleton': (255, 255, 0),  # Yellow
                'dragon': (0, 0, 255),  # Red
                'goblin': (255, 0, 255),  # Magenta
                'mob': (0, 255, 255),  # Cyan
                'enemy': (255, 128, 0),  # Orange
            }
            color = colors.get(class_name.lower(), (0, 255, 255))  # Default cyan

            # Draw bounding box
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)

            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

            # Background for text
            cv2.rectangle(vis_image,
                          (x1, y1 - label_size[1] - 10),
                          (x1 + label_size[0], y1),
                          color, -1)

            # Text
            cv2.putText(vis_image, label,
                        (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 0, 0), 2)

            # Draw center point
            center_x, center_y = monster['center']
            cv2.circle(vis_image, (center_x, center_y), 5, color, -1)

        return vis_image

    def get_detection_summary(self, monsters: List[Dict]) -> str:
        """Get summary text of detections"""
        if not monsters:
            return "No monsters detected"

        class_counts = {}
        for monster in monsters:
            class_name = monster['class_name']
            class_counts[class_name] = class_counts.get(class_name, 0) + 1

        summary = f"Detected {len(monsters)} monsters: "
        class_summaries = [f"{count}x {name}" for name, count in class_counts.items()]
        summary += ", ".join(class_summaries)

        return summary