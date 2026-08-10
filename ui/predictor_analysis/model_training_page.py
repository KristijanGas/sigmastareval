from __future__ import annotations

from datetime import date, datetime, timedelta


import pandas as pd
import streamlit as st

from evaluator.prediction_evaluator.model_training import (
    TASK_BINARY_CLASSIFICATION,
    build_validation_signature,
    get_task_type,
    validate_model_configuration,
)
from evaluator.prediction_evaluator.model_training_utils import DatasetSplit, collect_market_paths, split_paths_chronologically
from evaluator.prediction_evaluator.training_targets import CRYPTO_CHANGE_TARGET, OUTCOME_PROBABILITY_TARGET, TrainingTarget


st.title("Model Training")
st.caption(
    "Validate candidate configurations first. Only a validated configuration can be refitted on train + validation, "
    "optionally calibrated, and saved as the final model artifact."
)

# other features can be included too in the Additional feature names window
KNOWN_FEATURES = (
    "current_midpoint",
    "spread",
    "imbalance_top_1",
    "imbalance_top_3",
    "imbalance_top_5",
    "bid_volume_top_5",
    "ask_volume_top_5",
    "binance_return_1000",
    "binance_return_3000",
    "binance_return_10000",
    "binance_return_30000",
    "binance_return_volatility_10000",
    "binance_return_volatility_15000",
    "binance_return_volatility_20000",
    "binance_range_position_5000",
    "binance_range_position_15000",
    "binance_range_position_30000",
    "relative_distance_to_price_to_beat",
    "seconds_remaining",
)

TARGET_OPTIONS = {
    "Outcome probability (UP/DOWN)": OUTCOME_PROBABILITY_TARGET,
    "Crypto change": CRYPTO_CHANGE_TARGET,
}


def _dataset_dirs_from_text(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]

def parse_int_tuple(value: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in value.replace("\n", ",").split(","):
        part = part.strip()
        if part:
            values.append(int(part))
    return tuple(values)


def experiment_row(result, target, feature_names, estimator_params):
    row = {
        "Validated": result.validated_at,   #time of validation
        "Target": target.name,
        "Features": ", ".join(feature_names),
        "Feature count": len(feature_names),
        "Learning rate": estimator_params["learning_rate"],
        "Max leaf nodes": estimator_params["max_leaf_nodes"],
        "Min samples leaf": estimator_params["min_samples_leaf"],
        "L2": estimator_params["l2_regularization"],
        "Requested max iter": estimator_params["max_iter"],
        "Selected max iter": result.selected_max_iter,
        "Signature": result.configuration_signature,
    }
    row.update(result.validation_metrics)  #metrics computed after validation
    return row

def format_metric(value):
    return "N/A" if value is None else f"{value:.6g}"


st.session_state.setdefault("validated_model_configs", {})
st.session_state.setdefault("validation_experiments", [])


with st.container(border=True):
    st.subheader("1. Data")
    dataset_text = st.text_area(
        "Dataset directories",
        value="datasets/bitcoin-up-or-down/",
        help="One directory per line. Each directory is scanned for .gz market files.",
    )
    dataset_dirs = _dataset_dirs_from_text(dataset_text)

    default_end = date.today()
    default_start = default_end - timedelta(days=30)
    selected_dates = st.date_input(
        "Overall market date range",
        value=(default_start, default_end),
    )

    if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
    else:
        start_date = end_date = selected_dates

    c1, c2 = st.columns(2)
    train_pct = c1.number_input("Train %", min_value=10.0, max_value=90.0, value=60.0, step=5.0)
    validation_pct = c2.number_input("Validation %", min_value=5.0, max_value=50.0, value=15.0, step=5.0)

with st.container(border=True):
    st.subheader("2. Prediction target")
    target_label = st.selectbox("Target", list(TARGET_OPTIONS))
    target = TARGET_OPTIONS[target_label]
    task_type = get_task_type(target)
    is_classifier = (task_type == TASK_BINARY_CLASSIFICATION)

    if is_classifier:
        calibration_pct = st.number_input(
            "Calibration %",
            min_value=0.0,
            max_value=40.0,
            value=10.0,
            step=5.0,
            help="Kept completely separate from base-estimator training and validation.",
        )
    else:
        calibration_pct = 0.0
        st.metric("Calibration %", "0%")

    used_pct = train_pct + validation_pct + calibration_pct
    test_pct = 100.0 - used_pct
    st.write(f"**Reserved test:** {test_pct:.1f}%")
    if test_pct <= 0:
        st.error("Train + validation + calibration must total less than 100%.")

    horizon_ms = st.number_input(
        "Prediction horizon (ms)",
        min_value=0,
        value=0 if is_classifier else 3000,
        step=1000,
        disabled=is_classifier, #change later, horizon might be needed for some other classifier
        help="Outcome probability predicts final resolution, so its horizon is normally 0.",
    )

    sample_interval_ms = st.number_input(
        "Minimum sample interval (ms)",
        min_value=0,
        value=5000,
        step=1000,
        help="Reduces the number of highly dependent rows from each market.",
    )

    no_delay_limit = st.checkbox(
        "No maximum target delay",
        value=is_classifier,
        help="Normally enabled for final-outcome targets.",
    )
    max_target_delay_ms = None if no_delay_limit else st.number_input(
        "Maximum target delay (ms)", min_value=0, value=1000, step=100
    )

with st.container(border=True):
    st.subheader("3. Features")
    selected_features = st.multiselect(
        "Model features",
        options=KNOWN_FEATURES,
        default=["current_midpoint", "bid_volume_top_5", "ask_volume_top_5"],
    )

    custom_features_text = st.text_area(
        "Additional feature names",
        value="",
        help="Optional. One feature per line for extractor features not listed above.",
    )
    custom_features = [x.strip() for x in custom_features_text.splitlines() if x.strip()]
    feature_names = tuple(dict.fromkeys([*selected_features, *custom_features])) #dict to preserve order and remove duplicates

    col1, col2 = st.columns(2)
    binance_lookbacks_text = col1.text_input(
        "Binance lookbacks (ms)", value="1000, 10000, 30000"
    )
    crypto_range_windows_text = col2.text_input(
        "Crypto range windows (ms)", value="5000, 15000, 30000"
    )

with st.container(border=True):
    st.subheader("4. Gradient boosting parameters")
    p1, p2, p3 = st.columns(3)
    learning_rate = p1.number_input(
        "Learning rate", min_value=0.001, max_value=1.0, value=0.03, step=0.01, format="%.3f"
    )
    max_iter = p2.number_input("Maximum iterations", min_value=10, value=1000, step=50)
    max_leaf_nodes = p3.number_input("Max leaf nodes", min_value=2, value=3, step=1)

    p4, p5, p6 = st.columns(3)
    min_samples_leaf = p4.number_input("Min samples per leaf", min_value=1, value=100, step=10)
    l2_regularization = p5.number_input("L2 regularization", min_value=0.0, value=1.0, step=0.1)
    random_state = p6.number_input("Random state", min_value=0, value=42, step=1)

    early_stopping = st.checkbox(
        "Use validation markets for early stopping",
        value=True,
        help=(
            "When supported by your sklearn version, the candidate model receives the explicit chronological validation "
            "samples as X_val/y_val. The final refit then uses the selected iteration count and disables early stopping."
        ),
    )
    e1, e2 = st.columns(2)
    n_iter_no_change = e1.number_input("Iterations without improvement", min_value=1, value=30, step=5)
    tol = e2.number_input("Tolerance", min_value=0.0, value=1e-6, format="%.8f")

estimator_params = {
    "learning_rate": float(learning_rate),
    "max_iter": int(max_iter),
    "max_leaf_nodes": int(max_leaf_nodes),
    "min_samples_leaf": int(min_samples_leaf),
    "l2_regularization": float(l2_regularization),
    "early_stopping": bool(early_stopping),
    "n_iter_no_change": int(n_iter_no_change),
    "tol": float(tol),
    "random_state": int(random_state),
}

with st.container(border=True):
    st.subheader("5. Calibration")
    if is_classifier:
        calibration_method_label = st.selectbox(
            "Calibration method",
            ["Sigmoid", "Isotonic", "None"],
            help=(
                "This choice does not affect base-model validation. The final base estimator is saved independently, "
                "so raw probabilities remain available even when a calibrator is fitted."
            ),
        )
        calibration_method = calibration_method_label.lower()
        if calibration_method == "none" and calibration_pct > 0:
            st.info("Calibration is disabled. The calibration split will remain reserved but unused.")
        elif calibration_method != "none" and calibration_pct == 0:
            st.warning("Choose a non-zero calibration split to fit the selected calibrator.")
    else:
        calibration_method = "none"
        st.info("Calibration is only used for probability/classification models.")

with st.container(border=True):
    st.subheader("6. Save final model")
    s1, s2 = st.columns([2, 1])
    model_name = s1.text_input("Model name", value=f"{target.name}_model")
    model_directory = s2.text_input("Saved-model directory", value="bot/trained_models")


configuration_error = None
paths = []
split = None
extractor_config = None
current_signature = None

try:
    if not dataset_dirs:
        raise ValueError("Enter at least one dataset directory.")
    if start_date > end_date:
        raise ValueError("Start date must be before or equal to end date.")
    if test_pct <= 0:
        raise ValueError("No test data is left after the requested split.")
    if not feature_names:
        raise ValueError("Select at least one feature.")
    if is_classifier and calibration_method != "none" and calibration_pct <= 0:
        raise ValueError("Calibration is enabled but Calibration % is 0.")

    extractor_config = {
        "binance_lookbacks_ms": parse_int_tuple(binance_lookbacks_text),
        "crypto_range_windows_ms": parse_int_tuple(crypto_range_windows_text),
    }

    paths = collect_market_paths(dataset_dirs, start_date, end_date)
    if len(paths) < 4:
        raise ValueError(f"Only {len(paths)} matching markets were found; at least 4 are required.")

    split = split_paths_chronologically(
        paths,
        train_fraction=train_pct / 100.0,
        validation_fraction=validation_pct / 100.0,
        calibration_fraction=calibration_pct / 100.0,
    )

    current_signature = build_validation_signature(
        split=split,
        target=target,
        feature_names=feature_names,
        feature_extractor_config=extractor_config,
        horizon_ms=int(horizon_ms),
        max_target_delay_ms=max_target_delay_ms,
        sample_interval_ms=int(sample_interval_ms) if sample_interval_ms > 0 else None,
        estimator_params=estimator_params,
    )
except Exception as exc:
    configuration_error = str(exc)


st.subheader("Split preview")
if configuration_error:
    st.warning(configuration_error)
else:
    preview = pd.DataFrame(
        [
            {"Split": "Train", "Markets": len(split.train_paths)},
            {"Split": "Validation", "Markets": len(split.validation_paths)},
            {"Split": "Calibration", "Markets": len(split.calibration_paths)},
            {"Split": "Reserved test", "Markets": len(split.test_paths)},
        ]
    )
    st.dataframe(preview, hide_index=True, width="stretch")
    st.caption("Splits are chronological and use whole market files. Validation does not open calibration or test markets."
               "Files for testing are reserved and testing has to be started manually in Model Evaluation page to reduce possible overfitting.")


st.subheader("7. Validate configuration")
validate_clicked = st.button(
    "Validate configuration",
    type="primary",
    disabled=configuration_error is not None,
    width="content",
)

if validate_clicked:
    status = st.status("Validating candidate configuration…", expanded=True)

    def validation_progress(message: str) -> None:
        status.write(message)

    try:
        validation_result = validate_model_configuration(
            split=split,
            target=target,
            feature_names=feature_names,
            feature_extractor_config=extractor_config,
            horizon_ms=int(horizon_ms),
            max_target_delay_ms=max_target_delay_ms,
            sample_interval_ms=int(sample_interval_ms) if sample_interval_ms > 0 else None,
            estimator_params=estimator_params,
            progress=validation_progress,
        )
        st.session_state["validated_model_configs"][validation_result.configuration_signature] = validation_result
        st.session_state["validation_experiments"].append(
            experiment_row(validation_result, target, feature_names, estimator_params)
        )
        st.session_state["last_validation_signature"] = validation_result.configuration_signature
        status.update(label="Validation complete", state="complete", expanded=False)
    except Exception as exc:
        status.update(label="Validation failed", state="error", expanded=True)
        st.exception(exc)



# used to display results of last completed validation
current_validation = (
    st.session_state["validated_model_configs"].get(current_signature)
    if current_signature is not None
    else None
)

if current_validation is not None:
    st.success("The current base-model configuration has been validated.")
    metric_cols = st.columns(max(1, len(current_validation.validation_metrics)))
    for col, (name, value) in zip(metric_cols, current_validation.validation_metrics.items()):
        col.metric(name, format_metric(value))
    st.caption(
        f"Selected boosting iterations: {current_validation.selected_max_iter} · "
        f"Early stopping: {current_validation.early_stopping_source} · "
        f"Signature: {current_validation.configuration_signature}"
    )
else:
    st.info("Validate the current base-model configuration before final training is enabled.") #if no models were validated before


experiments = st.session_state.get("validation_experiments", [])
if experiments:
    st.subheader("Validation experiments")
    st.dataframe(pd.DataFrame(experiments), hide_index=True, width="stretch")
    if st.button("Clear validation history"):
        st.session_state["validation_experiments"] = []
        st.session_state["validated_model_configs"] = {}
        st.rerun()

st.subheader("8. Train & save final model (not implemented yet)")
st.caption(
    "The final base estimator is refitted on train + validation using the iteration count selected above. "
    "Calibration is then fitted separately, and both objects (base and calibrated) are stored in the same artifact."
)

train_final_clicked = st.button(
    "Train & save final model",
    type="primary",
    disabled=(configuration_error is not None or current_validation is None),
    width="content",
)

