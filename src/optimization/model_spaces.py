"""Bayesian-search spaces and fixed baseline models for the data-center digital twin."""
from __future__ import annotations

from sklearn.ensemble import (
    RandomForestRegressor, RandomForestClassifier,
    HistGradientBoostingRegressor, HistGradientBoostingClassifier,
    GradientBoostingRegressor, IsolationForest,
)
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REGRESSION_MODELS = {
    "random_forest_regressor",
    "hist_gradient_boosting_regressor",
    "ridge_regressor",
    "gradient_boosting_regressor",
}
CLASSIFICATION_MODELS = {
    "random_forest_classifier",
    "hist_gradient_boosting_classifier",
    "knn",
    "svm",
}
ANOMALY_MODELS = {"isolation_forest"}
ALL_MODELS = REGRESSION_MODELS | CLASSIFICATION_MODELS | ANOMALY_MODELS


def make_pipeline(estimator, scale: bool = False):
    steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale:
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", estimator))
    return Pipeline(steps)


def make_baseline_estimator(model_name: str, seed: int = 42):
    """Create a fixed, unoptimized baseline using sensible/original settings.

    The baseline and tuned model are fitted on the same train+validation rows
    and evaluated on the same untouched test rows.
    """
    if model_name == "random_forest_regressor":
        return make_pipeline(RandomForestRegressor(
            n_estimators=200, min_samples_leaf=2, n_jobs=-1, random_state=seed
        ))
    if model_name == "hist_gradient_boosting_regressor":
        return make_pipeline(HistGradientBoostingRegressor(
            max_iter=150, learning_rate=0.05, max_leaf_nodes=15,
            l2_regularization=1.0, random_state=seed
        ))
    if model_name == "ridge_regressor":
        return make_pipeline(Ridge(alpha=1.0), scale=True)
    if model_name == "gradient_boosting_regressor":
        return make_pipeline(GradientBoostingRegressor(
            n_estimators=80, learning_rate=0.05, max_depth=2,
            loss="squared_error", random_state=seed
        ))
    if model_name == "random_forest_classifier":
        return make_pipeline(RandomForestClassifier(
            n_estimators=200, class_weight="balanced", n_jobs=-1, random_state=seed
        ))
    if model_name == "hist_gradient_boosting_classifier":
        return make_pipeline(HistGradientBoostingClassifier(
            max_iter=150, learning_rate=0.1, max_leaf_nodes=31,
            class_weight="balanced", random_state=seed
        ))
    if model_name == "knn":
        return make_pipeline(KNeighborsClassifier(
            n_neighbors=5, weights="uniform", p=2
        ), scale=True)
    if model_name == "svm":
        return make_pipeline(SVC(
            C=1.0, kernel="rbf", gamma="scale", class_weight="balanced", random_state=seed
        ), scale=True)
    if model_name == "isolation_forest":
        return make_pipeline(IsolationForest(
            n_estimators=100, contamination="auto", random_state=seed, n_jobs=-1
        ))
    raise ValueError(f"Unknown model '{model_name}'. Choices: {sorted(ALL_MODELS)}")


def suggest_estimator(trial, model_name: str, seed: int = 42, n_train: int | None = None):
    """Return a sklearn pipeline/estimator with trial-suggested hyperparameters."""
    if model_name == "random_forest_regressor":
        estimator = RandomForestRegressor(
            n_estimators=trial.suggest_int("n_estimators", 100, 500, step=50),
            max_depth=trial.suggest_categorical("max_depth", [None, 5, 8, 12, 16, 24]),
            min_samples_split=trial.suggest_int("min_samples_split", 2, 20),
            min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10),
            max_features=trial.suggest_categorical("max_features", ["sqrt", "log2"]),
            n_jobs=-1, random_state=seed,
        )
        return make_pipeline(estimator)

    if model_name == "random_forest_classifier":
        estimator = RandomForestClassifier(
            n_estimators=trial.suggest_int("n_estimators", 100, 500, step=50),
            max_depth=trial.suggest_categorical("max_depth", [None, 5, 8, 12, 16, 24]),
            min_samples_split=trial.suggest_int("min_samples_split", 2, 20),
            min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10),
            max_features=trial.suggest_categorical("max_features", ["sqrt", "log2", 0.7]),
            class_weight="balanced", n_jobs=-1, random_state=seed,
        )
        return make_pipeline(estimator)

    if model_name == "hist_gradient_boosting_regressor":
        estimator = HistGradientBoostingRegressor(
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            max_iter=trial.suggest_int("max_iter", 80, 400, step=20),
            max_leaf_nodes=trial.suggest_int("max_leaf_nodes", 7, 63),
            l2_regularization=trial.suggest_float("l2_regularization", 1e-5, 10.0, log=True),
            min_samples_leaf=trial.suggest_int("min_samples_leaf", 5, 40),
            random_state=seed,
        )
        return make_pipeline(estimator)

    if model_name == "hist_gradient_boosting_classifier":
        estimator = HistGradientBoostingClassifier(
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            max_iter=trial.suggest_int("max_iter", 80, 400, step=20),
            max_leaf_nodes=trial.suggest_int("max_leaf_nodes", 7, 63),
            l2_regularization=trial.suggest_float("l2_regularization", 1e-5, 10.0, log=True),
            min_samples_leaf=trial.suggest_int("min_samples_leaf", 5, 40),
            class_weight="balanced", random_state=seed,
        )
        return make_pipeline(estimator)

    if model_name == "ridge_regressor":
        return make_pipeline(Ridge(alpha=trial.suggest_float("alpha", 1e-4, 1e3, log=True)), scale=True)

    if model_name == "gradient_boosting_regressor":
        estimator = GradientBoostingRegressor(
            n_estimators=trial.suggest_int("n_estimators", 50, 300, step=25),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            max_depth=trial.suggest_int("max_depth", 1, 5),
            min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 15),
            subsample=trial.suggest_float("subsample", 0.6, 1.0),
            loss=trial.suggest_categorical("loss", ["squared_error", "huber"]),
            random_state=seed,
        )
        return make_pipeline(estimator)

    if model_name == "knn":
        max_k = max(1, min(35, (n_train or 100) - 1))
        estimator = KNeighborsClassifier(
            n_neighbors=trial.suggest_int("n_neighbors", 1, max_k),
            weights=trial.suggest_categorical("weights", ["uniform", "distance"]),
            p=trial.suggest_int("p", 1, 2),
            leaf_size=trial.suggest_int("leaf_size", 15, 60),
        )
        return make_pipeline(estimator, scale=True)

    if model_name == "svm":
        estimator = SVC(
            C=trial.suggest_float("C", 1e-3, 1e3, log=True),
            kernel=trial.suggest_categorical("kernel", ["rbf", "linear"]),
            gamma=trial.suggest_categorical("gamma", ["scale", "auto"]),
            class_weight="balanced", random_state=seed,
        )
        return make_pipeline(estimator, scale=True)

    if model_name == "isolation_forest":
        estimator = IsolationForest(
            n_estimators=trial.suggest_int("n_estimators", 100, 400, step=50),
            max_samples=trial.suggest_categorical("max_samples", [0.5, 0.75, 1.0]),
            contamination=trial.suggest_float("contamination", 0.005, 0.2, log=True),
            max_features=trial.suggest_float("max_features", 0.5, 1.0),
            bootstrap=trial.suggest_categorical("bootstrap", [False, True]),
            random_state=seed, n_jobs=-1,
        )
        return make_pipeline(estimator)

    raise ValueError(f"Unknown model '{model_name}'. Choices: {sorted(ALL_MODELS)}")
