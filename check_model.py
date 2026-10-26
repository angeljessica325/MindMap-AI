
import joblib
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "models"

try:
    model = joblib.load(MODEL_DIR / "decision_tree_model.pkl")
    features = joblib.load(MODEL_DIR / "features.pkl")
    label_encoder = joblib.load(MODEL_DIR / "label_encoder.pkl")

    print("\nMODEL LOADED SUCCESSFULLY!")
    print("Model type:", type(model).__name__)
    print("Features:", features)
    print("Classes:", label_encoder.classes_)

except Exception as e:
    print("\nMODEL LOADING FAILED")
    print("Error type:", type(e).__name__)
    print("Error:", e)
