from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from sklearn.ensemble import HistGradientBoostingRegressor
from evaluator.prediction_evaluator.feature_extractor import MarketFeatureExtractor
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot, PricePrediction

class GradientBoostingPredictor:
   def __init__(
      self,
      training_samples,
      gradient_boosting_features,
      model: Any | None,
      feature_extractor: MarketFeatureExtractor,
      horizon_ms: int,
      feature_names: Sequence[str] | None = None,
      clip_predictions: bool = True,
   ):
      if horizon_ms <= 0:
         raise ValueError("horizon_ms must be positive.")

      model = self.initialize_model(training_samples, gradient_boosting_features)

      if not hasattr(model, "predict"):
         raise TypeError("model must provide a predict(X) method.")

      self.model = model

      self.feature_extractor = feature_extractor
      self.horizon_ms = horizon_ms
      self.clip_predictions = clip_predictions

      self.feature_names = self._resolve_feature_names(model=model,
         provided_feature_names=feature_names)

      self._validate_model_metadata()

   def initialize_model(self, training_samples, GRADIENT_BOOSTING_FEATURES):
      model = HistGradientBoostingRegressor(
         learning_rate=0.05,
         max_iter=300,
         max_leaf_nodes=31,
         min_samples_leaf=50,
         l2_regularization=0.1,
         random_state=42,
      )
      X_train, y_train = training_samples
      model.fit(X_train, y_train)
      print("Training complete")
      print(model)

      model.predictor_feature_names_ = GRADIENT_BOOSTING_FEATURES
      model.horizon_ms_ = 1000

      return model

   # Clear historical state before processing a new market
   def reset(self):
      self.feature_extractor.reset()

   def update(self, snapshot: MarketSnapshot):
      extracted = self.feature_extractor.update(snapshot)
      if extracted is None:
         return None

      missing_features = extracted.features.missing(self.feature_names)

      if missing_features:
         # Not enough history or source data to create all features expected by this model
         return None

      feature_row = extracted.features.select_row(self.feature_names)
      predicted_change = float(self.model.predict(feature_row)[0])

      predicted_midpoint = extracted.current_midpoint + predicted_change

      if self.clip_predictions:
         predicted_midpoint = self.clip_midpoint(predicted_midpoint)

      return PricePrediction(
         prediction_timestamp=extracted.timestamp,
         horizon_ms=self.horizon_ms,
         predicted_midpoint=predicted_midpoint,
         current_midpoint=extracted.current_midpoint,
         predicted_change=predicted_change,
      )


   def _resolve_feature_names(self, model: Any, provided_feature_names: Sequence[str] | None) -> tuple[str, ...]:
      """
      Prefer feature metadata stored on the fitted model.
      Explicit feature_names are supported for models that do not carry custom training metadata.
      """
      if hasattr(model, "predictor_feature_names_"):
         model_feature_names = tuple(model.predictor_feature_names_)

         if (provided_feature_names is not None
               and tuple(provided_feature_names) != model_feature_names
         ):
               raise ValueError("Provided feature_names do not match model.predictor_feature_names_.")

         feature_names = model_feature_names

      elif provided_feature_names is not None:
         feature_names = tuple(provided_feature_names)

      else:
         raise ValueError("Feature names must be provided or stored on model.predictor_feature_names_.")

      if not feature_names:
         raise ValueError("At least one feature is required.")

      if len(set(feature_names)) != len(feature_names):
         raise ValueError("Feature names must be unique.")

      return feature_names
   
   def _validate_model_metadata(self) -> None:
      if hasattr(self.model, "horizon_ms_"):
         model_horizon = int(self.model.horizon_ms_)

         if model_horizon != self.horizon_ms:
               raise ValueError(f"Model was trained for horizon "
                  f"{model_horizon} ms, but predictor uses {self.horizon_ms} ms.")

      
      if hasattr(self.model, "n_features_in_"):
         expected_feature_count = int(self.model.n_features_in_)

         if expected_feature_count != len(self.feature_names):
               raise ValueError(
                  f"Model expects {expected_feature_count} features, but {len(self.feature_names)} "
                  f"feature names were provided.")

   def clip_midpoint(self, midpoint: float) -> float:
      return min(1.0, max(0.0, midpoint))