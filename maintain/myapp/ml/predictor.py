
"""
Predictive maintenance model predictor.
Loads the trained AI4I RandomForest pipeline and predicts
machine failure from five sensor features.
"""

import os
import time

import joblib
import pandas as pd
from django.conf import settings


MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "myapp",
    "ml",
    "failure_model.pkl",
)

_bundle = None


def _load_bundle():
    global _bundle

    if _bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Trained model not found: {MODEL_PATH}"
            )

        _bundle = joblib.load(MODEL_PATH)

    return _bundle


def get_risk_level(probability, warning=0.30, high_risk=0.70):
    """Convert failure probability into a risk band."""

    if probability >= high_risk:
        return "High Risk"

    if probability >= warning:
        return "Warning"

    return "Normal"


def get_recommended_action(risk_level):
    """Return a suggested action for the risk band."""

    return {
        "High Risk": (
            "Schedule a maintenance inspection promptly. "
            "Review the machine before deciding whether "
            "it should continue operating."
        ),
        "Warning": (
            "Monitor the machine closely and plan a "
            "preventive inspection."
        ),
        "Normal": (
            "Continue routine monitoring and maintenance."
        ),
    }.get(risk_level, "Continue routine monitoring.")


def get_top_factors(features_dict=None, top_n=3):
    """Return the model's highest feature importances."""

    bundle = _load_bundle()
    model = bundle.get("model")
    feature_order = bundle.get("features", [])

    # First, try reading importances directly from the model.
    importances = getattr(model, "feature_importances_", None)

    # If the model is a pipeline, check its final estimator.
    if importances is None and hasattr(model, "steps"):
        final_estimator = model.steps[-1][1]
        importances = getattr(
            final_estimator,
            "feature_importances_",
            None,
        )

    # Fall back to importances saved in the bundle.
    if importances is None:
        importances = bundle.get(
            "feature_importances",
            bundle.get("importances"),
        )

    if importances is None:
        return "Feature importance data unavailable."

    # Convert dictionary or array into ranked pairs.
    if isinstance(importances, dict):
        ranked = list(importances.items())
    else:
        ranked = list(zip(feature_order, importances))

    ranked.sort(key=lambda item: item[1], reverse=True)

    return ", ".join(
        f"{name} ({float(score):.3f})"
        for name, score in ranked[:top_n]
    )

def predict_failure(
    features_dict,
    warning=0.30,
    high_risk=0.70,
):
    """
    Expected features_dict:
    {
        "Air temperature [K]": 300.0,
        "Process temperature [K]": 310.0,
        "Rotational speed [rpm]": 1500,
        "Torque [Nm]": 40.0,
        "Tool wear [min]": 100,
    }
    """

    started = time.time()

    bundle = _load_bundle()
    model = bundle["model"]
    feature_order = bundle["features"]
    version = bundle.get("version", "unknown")

    # Validate and order the input features.
    missing = [
        name for name in feature_order
        if name not in features_dict
    ]

    if missing:
        raise ValueError(
            f"Missing required features: {missing}"
        )

    row = pd.DataFrame(
        [[float(features_dict[name]) for name in feature_order]],
        columns=feature_order,
    )

    probability = float(
        model.predict_proba(row)[0][1]
    )

    risk_level = get_risk_level(
        probability,
        warning,
        high_risk,
    )

    return {
        "failure_probability": round(probability, 4),
        "risk_level": risk_level,
        "predicted_failure": risk_level == "High Risk",
        "recommended_action": get_recommended_action(
            risk_level
        ),
        "top_factors": get_top_factors(features_dict),
        "model_version": version,
        "processing_time_ms": int(
            (time.time() - started) * 1000
        ),
    }