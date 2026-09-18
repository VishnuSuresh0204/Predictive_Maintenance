
"""
train_model.py

Trains a Random Forest model using the AI4I 2020 dataset.

Dataset:
    myapp/ml/ai4i2020.csv

Output:
    myapp/ml/failure_model.pkl

Run from the Django project root:
    python myapp/ml/train_model.py
"""

import os

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(BASE_DIR, "ai4i2020.csv")
MODEL_PATH = os.path.join(BASE_DIR, "failure_model.pkl")

FEATURE_ORDER = [
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]

TARGET = "Machine failure"

MODEL_VERSION = "ai4i_rf_v1"
RANDOM_STATE = 42


# ============================================================
# 2. LOAD DATASET
# ============================================================

def load_data():

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    print(f"Loading AI4I dataset:\n{DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    required_columns = FEATURE_ORDER + [TARGET]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    # Select only the required features and target
    df = df[required_columns].copy()

    # Convert values to numeric
    for column in required_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # Remove missing and infinite values
    df = df.replace(
        [float("inf"), float("-inf")],
        float("nan"),
    )

    df = df.dropna().copy()

    # Validate target
    if not df[TARGET].isin([0, 1]).all():
        raise ValueError(
            "Machine failure must contain only 0 and 1."
        )

    if df.empty:
        raise ValueError(
            "No usable rows remain after cleaning."
        )

    if df[TARGET].nunique() != 2:
        raise ValueError(
            "Dataset must contain both failure classes."
        )

    print(f"Dataset loaded: {len(df)} rows")

    return df


# ============================================================
# 3. TRAIN AND EVALUATE
# ============================================================

def main():

    df = load_data()

    X = df[FEATURE_ORDER]
    y = df[TARGET].astype(int)

    print("\n========== DATASET SUMMARY ==========")

    print(f"Total records: {len(df)}")
    print(f"No failure:   {(y == 0).sum()}")
    print(f"Failure:      {(y == 1).sum()}")
    print(f"Failure rate: {y.mean():.2%}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    # Model pipeline
    pipeline = Pipeline([
        ("scaler", StandardScaler()),

        ("classifier", RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ])

    print("\n========== MODEL TRAINING ==========")

    pipeline.fit(X_train, y_train)

    print("Training completed.")

    # Predictions
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    # Evaluation
    print("\n========== EVALUATION ==========")

    print(
        f"Accuracy: {accuracy_score(y_test, y_pred):.4f}"
    )

    print("\nClassification report:")

    print(
        classification_report(
            y_test,
            y_pred,
            labels=[0, 1],
            target_names=["No Failure", "Failure"],
            digits=4,
            zero_division=0,
        )
    )

    print("Confusion matrix:")

    print(
        confusion_matrix(
            y_test,
            y_pred,
            labels=[0, 1],
        )
    )

    print(
        f"ROC-AUC: {roc_auc_score(y_test, y_proba):.4f}"
    )

    print(
        "PR-AUC:  "
        f"{average_precision_score(y_test, y_proba):.4f}"
    )

    # Cross-validation
    min_class_count = int(y.value_counts().min())
    n_splits = min(5, min_class_count)

    if n_splits >= 2:

        cv = StratifiedKFold(
            n_splits=n_splits,
            shuffle=True,
            random_state=RANDOM_STATE,
        )

        cv_scores = cross_val_score(
            pipeline,
            X,
            y,
            cv=cv,
            scoring="f1",
            n_jobs=-1,
        )

        print(
            f"\n{n_splits}-fold CV F1: "
            f"{cv_scores.mean():.4f} "
            f"(+/- {cv_scores.std():.4f})"
        )

    # Feature importance
    print("\n========== FEATURE IMPORTANCE ==========")

    classifier = pipeline.named_steps["classifier"]

    importances = classifier.feature_importances_

    importance_dict = dict(
        zip(
            FEATURE_ORDER,
            importances.round(4).tolist(),
        )
    )

    for name, value in sorted(
        importance_dict.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"{name}: {value:.4f}")

    # ========================================================
    # 4. SAVE MODEL
    # ========================================================

    model_bundle = {
        "model": pipeline,
        "features": FEATURE_ORDER,
        "version": MODEL_VERSION,
        "importances": importance_dict,
    }

    joblib.dump(
        model_bundle,
        MODEL_PATH,
    )

    print("\n========== MODEL SAVED ==========")

    print(f"Model location:\n{MODEL_PATH}")
    print(f"Model version: {MODEL_VERSION}")

    # ========================================================
    # 5. SAMPLE PREDICTION
    # ========================================================

    print("\n========== SAMPLE PREDICTION ==========")

    sample = pd.DataFrame(
        [[
            298.1,  # Air temperature [K]
            308.6,  # Process temperature [K]
            1500,   # Rotational speed [rpm]
            40.0,   # Torque [Nm]
            100,    # Tool wear [min]
        ]],
        columns=FEATURE_ORDER,
    )

    probability = pipeline.predict_proba(sample)[0][1]

    prediction = int(probability >= 0.5)

    print(f"Failure probability: {probability:.2%}")
    print(f"Predicted failure: {prediction}")

    if prediction == 1:
        print("Result: Failure predicted")
    else:
        print("Result: No failure predicted")


if __name__ == "__main__":
    main()