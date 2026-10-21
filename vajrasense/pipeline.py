"""
Machine learning pipeline module for वज्रSense (VajraSense).
Constructs scikit-learn preprocessing and nowcasting classification pipelines,
enforces temporal time-series splitting (zero lookahead leakage),
and computes meteorologically grounded evaluation metrics on CPU.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from vajrasense.config import (
    DATA_PROCESSED_DIR,
    ENGINEERED_DATA_FILENAME,
    MODELS_DIR,
)
from vajrasense.feature_engineering import AtmosphericFeatureEngineer

logger = logging.getLogger("vajrasense.pipeline")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [VajraSense:Pipeline] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class NowcastingPipeline:
    """
    Scikit-learn pipeline for convective storm and lightning nowcasting.
    Ensures CPU-friendly, leak-free temporal modeling and evaluation.
    """

    def __init__(
        self,
        target_column: str = "target_nowcast_1h",
        model_type: str = "hist_gb",
        random_state: int = 42,
    ):
        self.target_column = target_column
        self.model_type = model_type
        self.random_state = random_state
        self.feature_names: List[str] = []
        self.pipeline: Optional[Pipeline] = None
        self.evaluation_results: Dict[str, Any] = {}

    def prepare_data(
        self,
        df: Optional[pd.DataFrame] = None,
        input_csv_path: Optional[Path] = None,
        train_ratio: float = 0.8,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """
        Splits data chronologically (preserving temporal arrow of time).
        Avoids random shuffling to prevent data leakage in time-series nowcasting.
        """
        if df is None:
            if input_csv_path is None:
                input_csv_path = DATA_PROCESSED_DIR / ENGINEERED_DATA_FILENAME
            logger.info(f"Loading engineered dataset from: {input_csv_path}")
            df = pd.read_csv(input_csv_path)

        df = df.sort_values("time").reset_index(drop=True)

        if self.target_column not in df.columns:
            raise KeyError(f"Target column '{self.target_column}' not found in dataset.")

        # Candidate feature columns
        available_features = [
            col for col in AtmosphericFeatureEngineer.get_feature_column_names()
            if col in df.columns
        ]
        self.feature_names = available_features

        X = df[available_features].copy()
        y = df[self.target_column].astype(int)

        # Chronological Split
        split_idx = int(len(df) * train_ratio)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        time_train_start = df["time"].iloc[0]
        time_train_end = df["time"].iloc[split_idx - 1]
        time_test_start = df["time"].iloc[split_idx]
        time_test_end = df["time"].iloc[-1]

        logger.info(
            f"Chronological Split: Train [{time_train_start} to {time_train_end}] ({len(X_train):,} samples) | "
            f"Test [{time_test_start} to {time_test_end}] ({len(X_test):,} samples)"
        )
        logger.info(
            f"Target Balance -> Train Positive Rate: {y_train.mean():.2%} | Test Positive Rate: {y_test.mean():.2%}"
        )

        return X_train, X_test, y_train, y_test

    def build_pipeline(self) -> Pipeline:
        """
        Constructs a Scikit-learn Pipeline with robust scaling and
        CPU-optimized classifier.
        """
        # Preprocessor for numerical features
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", RobustScaler()),
            ]
        )

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, self.feature_names),
            ],
            remainder="drop",
        )

        # Classifier selection (CPU-only friendly)
        if self.model_type == "hist_gb":
            # Fast, modern histogram-based gradient boosting (similar to LightGBM, CPU parallelized)
            classifier = HistGradientBoostingClassifier(
                max_iter=100,
                learning_rate=0.08,
                max_depth=6,
                class_weight="balanced",
                random_state=self.random_state,
            )
        elif self.model_type == "random_forest":
            classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                class_weight="balanced",
                n_jobs=-1,
                random_state=self.random_state,
            )
        elif self.model_type == "logistic_regression":
            classifier = LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=self.random_state,
            )
        else:
            raise ValueError(f"Unsupported model_type: '{self.model_type}'")

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", classifier),
            ]
        )
        return self.pipeline

    def train_and_evaluate(
        self,
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        y_test: pd.Series,
    ) -> Dict[str, Any]:
        """
        Trains the nowcasting pipeline and evaluates performance with metrics
        tailored for class-imbalanced rare weather events.
        """
        if self.pipeline is None:
            self.build_pipeline()

        logger.info(f"Training nowcasting model ({self.model_type}) on CPU...")
        self.pipeline.fit(X_train, y_train)

        # Predictions
        y_pred = self.pipeline.predict(X_test)
        y_prob = self.pipeline.predict_proba(X_test)[:, 1]

        # Calculate metrics
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()

        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        roc_auc = roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else float("nan")
        pr_auc = average_precision_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else float("nan")
        brier = brier_score_loss(y_test, y_prob)

        # Critical Success Index (CSI / Threat Score) used in operational meteorology
        # CSI = TP / (TP + FP + FN)
        csi = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0

        # False Alarm Ratio (FAR)
        # FAR = FP / (TP + FP)
        far = fp / (tp + fp) if (tp + fp) > 0 else 0.0

        self.evaluation_results = {
            "model_type": self.model_type,
            "target": self.target_column,
            "test_sample_count": len(y_test),
            "test_event_count": int(y_test.sum()),
            "confusion_matrix": {"TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)},
            "precision": float(precision),
            "recall_pod": float(recall),  # Probability of Detection
            "f1_score": float(f1),
            "csi_threat_score": float(csi),
            "false_alarm_ratio": float(far),
            "roc_auc": float(roc_auc),
            "pr_auc": float(pr_auc),
            "brier_score": float(brier),
            "classification_report": classification_report(y_test, y_pred, zero_division=0, output_dict=True),
        }

        logger.info("=== Meteorological Evaluation Report ===")
        logger.info(f"Probability of Detection (Recall / POD): {recall:.2%}")
        logger.info(f"Precision (PPV): {precision:.2%}")
        logger.info(f"Critical Success Index (CSI Threat Score): {csi:.3f}")
        logger.info(f"False Alarm Ratio (FAR): {far:.2%}")
        logger.info(f"PR-AUC (Average Precision): {pr_auc:.3f}")
        logger.info(f"ROC-AUC: {roc_auc:.3f}")
        logger.info(f"Brier Score (Calibrated Prob Error): {brier:.4f}")

        return self.evaluation_results

    def save_pipeline(self, output_path: Optional[Path] = None) -> Path:
        """
        Serializes the trained pipeline object to disk using joblib.
        """
        if self.pipeline is None:
            raise RuntimeError("Pipeline has not been trained yet.")

        if output_path is None:
            output_path = MODELS_DIR / f"vajrasense_{self.model_type}_{self.target_column}.joblib"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        bundle = {
            "pipeline": self.pipeline,
            "feature_names": self.feature_names,
            "target_column": self.target_column,
            "model_type": self.model_type,
            "evaluation_results": self.evaluation_results,
        }
        joblib.dump(bundle, output_path)
        logger.info(f"Saved trained nowcasting pipeline to: {output_path.resolve()}")
        return output_path

    @classmethod
    def load_pipeline(cls, model_path: Path) -> "NowcastingPipeline":
        """
        Loads a serialized pipeline bundle from disk.
        """
        bundle = joblib.load(model_path)
        instance = cls(
            target_column=bundle["target_column"],
            model_type=bundle["model_type"],
        )
        instance.pipeline = bundle["pipeline"]
        instance.feature_names = bundle["feature_names"]
        instance.evaluation_results = bundle.get("evaluation_results", {})
        return instance
