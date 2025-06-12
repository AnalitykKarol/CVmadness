import torch
import pickle
import io


def fix_model(input_path, output_path):
    """Fix pathlib conflict in saved model"""

    class FixedUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            # Fix pathlib conflicts
            if module == 'pathlib._local':
                module = 'pathlib'
            elif module == 'models.yolo':
                # Skip problematic imports
                import sys
                if 'models' not in sys.modules:
                    sys.modules['models'] = type(sys)('models')
                if 'models.yolo' not in sys.modules:
                    sys.modules['models.yolo'] = type(sys)('models.yolo')

            return super().find_class(module, name)

    # Load with fixed unpickler
    with open(input_path, 'rb') as f:
        buffer = io.BytesIO(f.read())

    try:
        # Try to load and re-save without problematic references
        checkpoint = torch.load(input_path, map_location='cpu', pickle_module=pickle)

        # Clean the checkpoint
        if 'model' in checkpoint:
            model_state = checkpoint['model']

            # Create clean checkpoint
            clean_checkpoint = {
                'model': model_state,
                'epoch': checkpoint.get('epoch', 0),
                'best_fitness': checkpoint.get('best_fitness', 0.0),
                'date': None,  # Remove problematic datetime objects
            }

            # Save cleaned model
            torch.save(clean_checkpoint, output_path)
            print(f"✅ Model fixed and saved to: {output_path}")
            return True

    except Exception as e:
        print(f"❌ Failed to fix model: {e}")
        return False


# Run the fix
input_model = r"E:\Work\fun\WowCV420\models\yolo_models\monsters.pt"
output_model = r"E:\Work\fun\WowCV420\models\yolo_models\monstersfix.pt"

if fix_model(input_model, output_model):
    print("Model fixed! Use monsters_fixed.pt instead")
else:
    print("Could not fix model - try retraining with current environment")