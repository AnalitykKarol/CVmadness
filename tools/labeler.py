import cv2
import os
import random
import shutil
from pathlib import Path
from typing import List, Tuple

# Stałe
IMG_DIR = Path("../src/data/screenshots")
LABEL_DIR = Path("../src/data/labels")
TRAIN_DIR = Path("../src/data/train")
VAL_DIR = Path("../src/data/val")
VAL_SPLIT = 0.2  # 20% danych do walidacji

# Tworzenie katalogów
for dir_path in [LABEL_DIR, TRAIN_DIR / "images", TRAIN_DIR / "labels",
                 VAL_DIR / "images", VAL_DIR / "labels"]:
    dir_path.mkdir(parents=True, exist_ok=True)

labels = ["mob", "hp_bar", "mana_bar", "loot"]
current_annotations = []
drawing = False
bbox = []
img = None


def draw_bbox(event, x, y, flags, param):
    global bbox, drawing, img
    if event == cv2.EVENT_LBUTTONDOWN:
        bbox = [(x, y)]
        drawing = True
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        img2 = img.copy()
        draw_existing_annotations(img2)
        cv2.rectangle(img2, bbox[0], (x, y), (0, 255, 0), 2)
        cv2.imshow("Label", img2)
    elif event == cv2.EVENT_LBUTTONUP:
        bbox.append((x, y))
        drawing = False
        cv2.rectangle(img, bbox[0], bbox[1], (0, 255, 0), 2)
        draw_existing_annotations(img)
        cv2.imshow("Label", img)


def draw_existing_annotations(image):
    for label, (x0, y0), (x1, y1) in current_annotations:
        cv2.rectangle(image, (x0, y0), (x1, y1), (255, 0, 0), 2)
        cv2.putText(image, label, (x0, y0 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)


def load_existing_annotations(img_path: Path) -> List[Tuple]:
    global current_annotations
    label_path = LABEL_DIR / (img_path.stem + ".txt")
    if not label_path.exists():
        return []

    h, w, _ = cv2.imread(str(img_path)).shape
    annotations = []

    with open(label_path) as f:
        for line in f.readlines():
            cid, cx, cy, bw, bh = map(float, line.strip().split())
            x = int((cx - bw / 2) * w)
            y = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w)
            y2 = int((cy + bh / 2) * h)
            annotations.append((labels[int(cid)], (x, y), (x2, y2)))
    return annotations


def label_image(img_path: Path) -> List[Tuple]:
    global img, bbox, drawing, current_annotations
    img = cv2.imread(str(img_path))
    current_annotations = load_existing_annotations(img_path)

    cv2.imshow("Label", img)
    cv2.setMouseCallback("Label", draw_bbox)
    draw_existing_annotations(img)
    cv2.imshow("Label", img)

    bbox = []
    drawing = False

    while True:
        k = cv2.waitKey(0)
        if k == 27:  # ESC
            break
        elif k == ord('s') and len(bbox) == 2:
            print("\nDostępne klasy:")
            for idx, name in enumerate(labels):
                print(f"{idx}: {name}")

            while True:
                try:
                    idx = int(input("Podaj numer klasy: ").strip())
                    if 0 <= idx < len(labels):
                        current_annotations.append((labels[idx], bbox[0], bbox[1]))
                        bbox = []
                        img_copy = img.copy()
                        draw_existing_annotations(img_copy)
                        cv2.imshow("Label", img_copy)
                        break
                    print("Numer klasy poza zakresem.")
                except ValueError:
                    print("Wprowadź poprawny numer.")
        elif k == ord('u') and current_annotations:  # Cofnij ostatnią anotację
            current_annotations.pop()
            img_copy = img.copy()
            draw_existing_annotations(img_copy)
            cv2.imshow("Label", img_copy)

    cv2.destroyAllWindows()
    return current_annotations


def save_annotations(img_path: Path, annots: List[Tuple]):
    h, w, _ = cv2.imread(str(img_path)).shape
    out_lines = []

    for label, (x0, y0), (x1, y1) in annots:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        bw, bh = abs(x1 - x0), abs(y1 - y0)
        cid = labels.index(label)
        out_lines.append(f"{cid} {cx / w:.6f} {cy / h:.6f} {bw / w:.6f} {bh / h:.6f}")

    with open(LABEL_DIR / (img_path.stem + ".txt"), "w") as f:
        f.write("\n".join(out_lines))


def split_dataset():
    all_images = list(IMG_DIR.glob("*.png"))
    random.shuffle(all_images)

    val_size = int(len(all_images) * VAL_SPLIT)
    val_images = all_images[:val_size]
    train_images = all_images[val_size:]

    # Kopiowanie plików do odpowiednich katalogów
    for img_path in train_images:
        label_path = LABEL_DIR / (img_path.stem + ".txt")
        if label_path.exists():
            shutil.copy2(img_path, TRAIN_DIR / "images" / img_path.name)
            shutil.copy2(label_path, TRAIN_DIR / "labels" / label_path.name)

    for img_path in val_images:
        label_path = LABEL_DIR / (img_path.stem + ".txt")
        if label_path.exists():
            shutil.copy2(img_path, VAL_DIR / "images" / img_path.name)
            shutil.copy2(label_path, VAL_DIR / "labels" / label_path.name)


def main():
    for img_path in IMG_DIR.glob("*.png"):
        print(f"\nOznaczasz: {img_path}")
        print("Sterowanie:")
        print("- LPM + przeciągnięcie: rysowanie prostokąta")
        print("- s: zapisz anotację")
        print("- u: cofnij ostatnią anotację")
        print("- ESC: zakończ etykietowanie obrazu")

        annots = label_image(img_path)
        if annots:
            save_annotations(img_path, annots)
            print(f"Zapisano: {LABEL_DIR / (img_path.stem + '.txt')}")
        print("---")

    print("\nTworzenie zbiorów treningowego i walidacyjnego...")
    split_dataset()
    print("Gotowe!")


if __name__ == "__main__":
    main()