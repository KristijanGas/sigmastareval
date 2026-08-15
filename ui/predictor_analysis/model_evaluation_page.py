from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st


from evaluator.prediction_evaluator.model_training_utils import PREDICTION_MODE_CALIBRATED, PREDICTION_MODE_RAW, TASK_BINARY_CLASSIFICATION, collect_market_paths, load_model_artifact
from evaluator.prediction_evaluator.prediction_evaluator import evaluate_saved_model
from evaluator.prediction_evaluator.training_targets import CRYPTO_CHANGE_TARGET, OUTCOME_PROBABILITY_TARGET
from evaluator.utils.utils import extract_timestamp
from ui.predictor_analysis.common import format_metric



st.title("Model Evaluation")
st.caption(
   "Load a saved model artifact, choose raw or calibrated probability output when available, "
   "then evaluate it on untouched markets."
)

TARGET_OPTIONS = {
   OUTCOME_PROBABILITY_TARGET.name: OUTCOME_PROBABILITY_TARGET,
   CRYPTO_CHANGE_TARGET.name: CRYPTO_CHANGE_TARGET,
}

def _dataset_dirs_from_text(value: str) -> list[str]:
   return [line.strip() for line in value.splitlines() if line.strip()]

def date_from_market_name(name):
   if not name:
      return None
   try:
      return datetime.fromtimestamp(extract_timestamp(filename=name)).date()
   except Exception:
      return None


with st.container(border=True):
   st.subheader("1. Saved model")
   model_directory = st.text_input("Saved-model directory", value="bot/trained_models")
   model_files = sorted(Path(model_directory).expanduser().glob("*.joblib")) if model_directory else []

   source = st.radio("Model source",["Select saved model", "Enter model path"], horizontal=True,)

   if source == "Select saved model":
      if model_files:
         selected_model = st.selectbox(
            "Saved model",
            model_files,
            format_func=lambda p: p.name,
         )
         model_path_text = str(selected_model)
      else:
         st.info("No .joblib files were found in that directory.")
         model_path_text = ""
   else:
      model_path_text = st.text_input("Model path", value="")


artifact = None
artifact_error = None
if model_path_text:
   try:
      artifact = load_model_artifact(model_path_text)
   except Exception as e:
      st.error(f"Could not load model: {e}")

prediction_mode = PREDICTION_MODE_RAW
if artifact is not None:
   with st.container(border=True):
      st.subheader("2. Model components")
      m1, m2, m3, m4 = st.columns(4)
      m1.metric("Task", artifact.get("task_type", "unknown"))
      m2.metric("Base estimator", artifact.get("base_estimator_type", "unknown"))
      m3.metric("Calibration", artifact.get("calibration_method", "none"))
      m4.metric("Calibrator", artifact.get("calibrator_type") or "None")

      feature_names = tuple(artifact.get("feature_names", ()))
      st.write("**Target:**", artifact.get("target_name", "unknown"))
      st.write("**Features:**", ", ".join(feature_names) if feature_names else "No feature metadata saved")
      st.write("**Horizon:**", f"{artifact.get('horizon_ms', 0)} ms")

      has_calibrator = bool(artifact.get("has_calibrator") and artifact.get("calibrator") is not None)
      if artifact.get("task_type") == TASK_BINARY_CLASSIFICATION:
         if has_calibrator:
               output_label = st.radio(
                  "Probability output used for the main evaluation metrics",
                  ["Calibrated probability", "Raw base-model probability"],
                  horizontal=True,
                  help=(
                     "Both are evaluated below. This control only chooses which one is treated as the main output "
                     "for the top metrics and probability-distribution plot."))
               if output_label == "Calibrated probability":
                  prediction_mode = PREDICTION_MODE_CALIBRATED
               else:
                  prediction_mode = PREDICTION_MODE_RAW

               st.info(
                  "This artifact contains two independently usable fitted components: the base predictor (classifier) and its "
                  "optional calibration layer. Selecting raw predictor does not require retraining.")
         else:
               prediction_mode = PREDICTION_MODE_RAW
               st.info("No calibrator is stored in this artifact. Evaluation will use only raw base-model probabilities.")

      split_ranges = artifact.get("split_ranges", {})
      if isinstance(split_ranges, dict):
         reserved_test = split_ranges.get("test", {})
      else: 
         reserved_test = {}

      if reserved_test:
         st.info(
               "Reserved test range from training: "
               f"{reserved_test.get('first') or 'unknown'} -> {reserved_test.get('last') or 'unknown'}")

      with st.expander("Full artifact metadata"):
         display_metadata = {
               k: v for k, v in artifact.items()
               if k not in {"base_estimator", "calibrator"}
         }
         st.json(display_metadata, expanded=False)


with st.container(border=True):
   st.subheader("3. Test data")
   dataset_text = st.text_area(
      "Dataset directories",
      value="datasets/bitcoin-up-or-down/",
      help="One directory per line.")
   dataset_dirs = _dataset_dirs_from_text(dataset_text)

   default_end = date.today()
   default_start = default_end - timedelta(days=7)

   if artifact is not None:
      reserved = artifact.get("split_ranges", {}).get("test", {})
      if reserved:
         inferred_start = date_from_market_name(reserved.get("first"))
         inferred_end = date_from_market_name(reserved.get("last"))
      else:
         inferred_start = inferred_end = None

      if inferred_start and inferred_end:
         default_start, default_end = inferred_start, inferred_end

   selected_dates = st.date_input(
      "Test market date range",
      value=(default_start, default_end),
      key="model_eval_dates",
   )
   if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
      start_date, end_date = selected_dates
   else:
      start_date = end_date = selected_dates


with st.expander("Advanced evaluation settings"):
   override_sampling = st.checkbox("Override saved sample interval / target delay", value=False)
   if override_sampling:
      eval_sample_interval_ms = st.number_input("Evaluation sample interval (ms)", min_value=0, value=5000, step=1000)
      eval_no_delay = st.checkbox("No maximum target delay", value=True)
      if eval_no_delay:
         eval_max_target_delay_ms = None
      else:
         eval_max_target_delay_ms = st.number_input(
         "Maximum target delay (ms)", min_value=0, value=1000, step=100)
   else:
      eval_sample_interval_ms = None
      eval_max_target_delay_ms = None


configuration_error = None
test_paths = []
try:
   if artifact is None:
      raise ValueError("Select a valid saved model.")
   if not dataset_dirs:
      raise ValueError("Enter at least one dataset directory.")
   if start_date > end_date:
      raise ValueError("Start date must be before or equal to end date.")
   test_paths = collect_market_paths(dataset_dirs, start_date, end_date)
   if not test_paths:
      raise ValueError("No matching test markets were found.")
except Exception as exc:
   configuration_error = str(exc)


if configuration_error:
   st.warning(configuration_error)
else:
   st.write(f"**Selected test markets:** {len(test_paths)}")
   st.caption(f"{test_paths[0].name} -> {test_paths[-1].name}")
    

start_evaluation = st.button(
   "Start evaluation",
   type="primary",
   disabled=configuration_error is not None,
   width="stretch",
)

if start_evaluation:
   status = st.status("Evaluating model…", expanded=True)

   def progress(message: str) -> None:
      status.write(message)


   # 
   if override_sampling:
      if eval_sample_interval_ms > 0:
         sample_interval_ms_override = int(eval_sample_interval_ms)
      else:
         sample_interval_ms_override = None
      max_target_delay_ms_override = eval_max_target_delay_ms
   else:
      sample_interval_ms_override = max_target_delay_ms_override = None


   try:
      result = evaluate_saved_model(
         model_path=model_path_text,
         test_paths=test_paths,
         prediction_mode=prediction_mode,
         progress=progress,
         sample_interval_ms_override=sample_interval_ms_override,
         max_target_delay_ms_override=max_target_delay_ms_override,
      )
      status.update(label="Evaluation complete", state="complete", expanded=False)
      st.session_state["last_model_evaluation_result"] = result
   except Exception as exc:
      status.update(label="Evaluation failed", state="error", expanded=True)
      st.exception(exc)



result = st.session_state.get("last_model_evaluation_result")
if result is not None:
   st.divider()
   st.subheader("Evaluation results")
   st.caption(
      f"{result.sample_count:,} evaluation samples · {result.model_path.name} · "
      f"main output: {result.selected_prediction_mode}"
   )

   metric_cols = st.columns(max(1, len(result.metrics)))
   for col, (name, value) in zip(metric_cols, result.metrics.items()):
      col.metric(name, format_metric(value))

   if (
      result.task_type == TASK_BINARY_CLASSIFICATION
      and result.has_calibration
      and result.raw_metrics is not None
      and result.calibrated_metrics is not None
   ):
      st.subheader("Raw vs calibrated probability metrics")
      rows = []
      metric_names = list(dict.fromkeys([*result.raw_metrics, *result.calibrated_metrics]))
      for metric_name in metric_names:
         rows.append(
               {
                  "Metric": metric_name,
                  "Raw base model": result.raw_metrics.get(metric_name),
                  "Calibrated": result.calibrated_metrics.get(metric_name),
               }
         )
      st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
      st.caption(
         "Both outputs come from the same saved artifact. If using this test result to choose raw vs calibrated, "
         "the test set has become part of model selection; reserve another untouched period if you need a strict final benchmark."
      )

   for title, figure in result.figures.items():
      st.subheader(title)
      st.pyplot(figure, width="stretch")

   with st.expander("Prediction sample"):
      preview_data = {
         "actual": result.y_true[:200],
         "selected_prediction": result.predictions[:200],
      }
      if result.raw_predictions is not None:
         preview_data["raw_probability"] = result.raw_predictions[:200]
      if result.calibrated_predictions is not None:
         preview_data["calibrated_probability"] = result.calibrated_predictions[:200]
      st.dataframe(pd.DataFrame(preview_data), hide_index=True, width="stretch")