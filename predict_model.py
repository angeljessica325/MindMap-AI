
import joblib
import pandas as pd
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "models"

model = joblib.load(MODEL_DIR / "decision_tree_model.pkl")
features = joblib.load(MODEL_DIR / "features.pkl")
label_encoder = joblib.load(MODEL_DIR / "label_encoder.pkl")


def predict_performance(student_data):
    """
    student_data must contain all four model features.
    """

    missing = [f for f in features if f not in student_data]

    if missing:
        raise ValueError(f"Missing features: {missing}")

    # Preserve the exact training feature order.
    input_data = pd.DataFrame(
        [[student_data[f] for f in features]],
        columns=features
    )

    prediction = model.predict(input_data)[0]
    predicted_label = label_encoder.inverse_transform(
        [int(prediction)]
    )[0]

    return str(predicted_label)


if __name__ == "__main__":
    sample_student = {
        "raisedhands": 10,
        "VisITedResources": 10,
        "AnnouncementsView": 5,
        "Discussion": 20
    }

    result = predict_performance(sample_student)
    print("Predicted performance:", result)
