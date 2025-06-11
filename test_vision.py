#!/usr/bin/env python3
"""
Debug script dla Vision Engine
Uruchom: python test_vision.py
"""

import sys
import os
from pathlib import Path
# Fix Tesseract PATH
import os
try:
    import pytesseract
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break
except ImportError:
    pass
# Dodaj src do path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def test_basic_imports():
    """Test podstawowych importów"""
    print("=== TEST PODSTAWOWYCH IMPORTÓW ===")

    try:
        import cv2
        print(f"✓ OpenCV: {cv2.__version__}")
    except ImportError as e:
        print(f"✗ OpenCV: {e}")
        return False

    try:
        import numpy as np
        print(f"✓ NumPy: {np.__version__}")
    except ImportError as e:
        print(f"✗ NumPy: {e}")
        return False

    return True


def test_tesseract():
    """Test Tesseract OCR"""
    print("\n=== TEST TESSERACT OCR ===")

    try:
        import pytesseract
        print("✓ pytesseract zaimportowany")

        # Test czy tesseract executable jest dostępny
        version = pytesseract.get_tesseract_version()
        print(f"✓ Tesseract wersja: {version}")
        return True

    except ImportError:
        print("✗ pytesseract nie zainstalowany")
        print("  Zainstaluj: pip install pytesseract")
        return False
    except Exception as e:
        print(f"✗ Tesseract executable nie znaleziony: {e}")
        print("  Zainstaluj Tesseract OCR:")
        print("  Windows: winget install UB-Mannheim.TesseractOCR")
        return False


def test_vision_structure():
    """Test struktury folderów vision"""
    print("\n=== TEST STRUKTURY VISION ===")

    vision_path = src_path / "vision"

    required_files = [
        "__init__.py",
        "template_matcher.py",
        "vision_engine.py",
        "object_detector.py"
    ]

    all_exists = True

    for file in required_files:
        file_path = vision_path / file
        if file_path.exists():
            print(f"✓ {file}")

            # Sprawdź czy plik nie jest pusty (oprócz __init__.py)
            if file != "__init__.py":
                if file_path.stat().st_size == 0:
                    print(f"  ⚠ {file} jest pusty!")
                    all_exists = False
                else:
                    print(f"  📦 {file}: {file_path.stat().st_size} bajtów")
        else:
            print(f"✗ {file} - BRAKUJE")
            all_exists = False

    return all_exists


def test_template_matcher():
    """Test TemplateMatcher"""
    print("\n=== TEST TEMPLATE MATCHER ===")

    try:
        from vision.template_matcher import TemplateMatcher
        print("✓ TemplateMatcher zaimportowany")

        # Test inicjalizacji
        matcher = TemplateMatcher("data/templates")
        print("✓ TemplateMatcher zainicjalizowany")

        # Test podstawowych metod
        templates = matcher.get_template_list()
        categories = matcher.get_categories()

        print(f"✓ Templates: {len(templates)}")
        print(f"✓ Categories: {categories}")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Runtime error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vision_engine():
    """Test VisionEngine"""
    print("\n=== TEST VISION ENGINE ===")

    try:
        from vision.vision_engine import VisionEngine
        print("✓ VisionEngine zaimportowany")

        # Test config
        config = {
            'paths': {
                'templates': 'data/templates'
            }
        }

        engine = VisionEngine(config)
        print("✓ VisionEngine zainicjalizowany")
        print(f"✓ OCR dostępny: {engine.ocr_available}")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ Runtime error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_object_detector():
    """Test ObjectDetector"""
    print("\n=== TEST OBJECT DETECTOR ===")

    try:
        from vision.object_detector import BasicObjectDetector
        print("✓ BasicObjectDetector zaimportowany")

        detector = BasicObjectDetector()
        print("✓ BasicObjectDetector zainicjalizowany")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Runtime error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_integration():
    """Test pełnej integracji"""
    print("\n=== TEST PEŁNEJ INTEGRACJI ===")

    try:
        import cv2
        import numpy as np
        from vision.vision_engine import VisionEngine

        # Stwórz testowy obraz
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[25:75, 25:75] = [0, 255, 0]  # Zielony kwadrat

        config = {
            'paths': {
                'templates': 'data/templates'
            }
        }

        engine = VisionEngine(config)
        results = engine.analyze_image(test_image)

        print("✓ Analiza obrazu zakończona")
        print(f"  Templates: {len(results['templates'])}")
        print(f"  Health bars: {len(results['colors']['health_bars'])}")
        print(f"  Mana bars: {len(results['colors']['mana_bars'])}")
        print(f"  Text regions: {len(results['text'])}")
        print(f"  UI elements: {len(results['ui_elements']['elements'])}")

        return True

    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_paths():
    """Sprawdź ścieżki"""
    print("\n=== SPRAWDZENIE ŚCIEŻEK ===")

    print(f"Bieżący katalog: {os.getcwd()}")
    print(f"Python path: {sys.path[:3]}...")
    print(f"src path: {src_path}")
    print(f"src exists: {src_path.exists()}")

    if src_path.exists():
        vision_path = src_path / "vision"
        print(f"vision path: {vision_path}")
        print(f"vision exists: {vision_path.exists()}")

        if vision_path.exists():
            files = list(vision_path.glob("*.py"))
            print(f"Python files w vision: {[f.name for f in files]}")


def main():
    """Główna funkcja testowa"""
    print("🔍 VISION ENGINE DEBUG TOOL")
    print("=" * 50)

    tests = [
        ("Sprawdzenie ścieżek", check_paths),
        ("Podstawowe importy", test_basic_imports),
        ("Struktura Vision", test_vision_structure),
        ("Tesseract OCR", test_tesseract),
        ("Template Matcher", test_template_matcher),
        ("Vision Engine", test_vision_engine),
        ("Object Detector", test_object_detector),
        ("Pełna integracja", test_full_integration)
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n💥 CRASH w teście '{test_name}': {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False

    # Podsumowanie
    print("\n" + "=" * 50)
    print("📊 PODSUMOWANIE TESTÓW")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print(f"\nWynik: {passed}/{total} testów przeszło")

    if passed == total:
        print("🎉 Wszystko działa! Vision Engine jest gotowy.")
    else:
        print("⚠️  Niektóre testy nie przeszły. Sprawdź błędy powyżej.")

        # Sugestie napraw
        print("\n🔧 SUGESTIE NAPRAW:")

        if not results.get("Podstawowe importy", True):
            print("- Zainstaluj: pip install opencv-python numpy")

        if not results.get("Tesseract OCR", True):
            print("- Zainstaluj: pip install pytesseract")
            print("- Zainstaluj Tesseract: winget install UB-Mannheim.TesseractOCR")

        if not results.get("Struktura Vision", True):
            print("- Sprawdź czy wszystkie pliki .py są w src/vision/")
            print("- Sprawdź czy pliki nie są puste")


if __name__ == "__main__":
    main()