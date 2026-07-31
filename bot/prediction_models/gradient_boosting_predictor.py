from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from sklearn.ensemble import HistGradientBoostingRegressor
from evaluator.prediction_evaluator.feature_extractor import ExtractedMarketState, MarketFeatureExtractor
from evaluator.prediction_evaluator.prediction_eval_dataclasses import MarketSnapshot, NumericPrediction
import joblib

class GradientBoostingPredictor:

   def __init__(
      self,
      training_samples,
      gradient_boosting_features,
      model: Any | None,
      feature_extractor: MarketFeatureExtractor,
      horizon_ms: int,
      target_name: str,
      feature_names: Sequence[str] | None = None,
      clip_predictions: bool = True,
      market_name: str = None,
      price_to_beat: float = None
   ):
      self.name="gradient_boosting_predictor"
      if horizon_ms <= 0:
         raise ValueError("horizon_ms must be positive.")
      self.horizon_ms = horizon_ms

      self.SUPPORTED_TARGETS = {
        "midpoint_change",
        "crypto_change",
        "normalized_crypto_trend",
      }

      if target_name not in self.SUPPORTED_TARGETS:
         raise ValueError(
               f"Unsupported target_name {target_name!r}. "
               f"Expected one of {sorted(self.SUPPORTED_TARGETS)}."
         )

      if model is None:
         print("model is None")
         if training_samples is None:
            raise ValueError("training_samples are required when model is None.")
         model = self.initialize_model(training_samples, gradient_boosting_features)

      if not hasattr(model, "predict"):
         raise TypeError("model must provide a predict(X) method.")

      self.model = model
      self.target_name = target_name
      self.feature_extractor = feature_extractor
      self.clip_predictions = clip_predictions
      self.crypto_price_stdev = {"bitcoin-up-or-down": 300, "ethereum-up-or-down": 10.4, "solana-up-or-down": 0.6, "xrp-up-or-down": 0.0068,
                                   "btc-updown-5m": 10, "eth-updown-5m": 10.4}

      self.feature_names = self._resolve_feature_names(model=model,
         provided_feature_names=feature_names)
      self.market_name = market_name

      self._validate_model_metadata()



   def initialize_model(self, training_samples, GRADIENT_BOOSTING_FEATURES):
      # model = HistGradientBoostingRegressor(
      #    learning_rate=0.05,
      #    max_iter=300,
      #    max_leaf_nodes=31,
      #    min_samples_leaf=50,
      #    l2_regularization=0.1,
      #    random_state=42,
      # )
      model = HistGradientBoostingRegressor(
         learning_rate=0.03,
         max_iter=1000,
         max_leaf_nodes=3,
         min_samples_leaf=100,
         l2_regularization=1.0,
         early_stopping=True,
         validation_fraction=0.15,
         n_iter_no_change=30,
         tol=1e-6,
         random_state=42,
      )
      X_train, y_train = training_samples
      model.fit(X_train, y_train)
      print("Training complete")
      print(model)

      model.predictor_feature_names_ = GRADIENT_BOOSTING_FEATURES
      model.horizon_ms_ = self.horizon_ms

      return model

   # Clear historical state before processing a new market
   def reset(self):
      self.feature_extractor.reset()

   def update(self, snapshot:MarketSnapshot):
      self.feature_extractor.update(snapshot)

   def make_prediction(self, snapshot: MarketSnapshot):
      extracted = self.feature_extractor.extract_market_features(snapshot)
      if extracted is None:
         #print("extracted is None")
         return None

      missing_features = extracted.features.missing(self.feature_names)

      if missing_features:
         #print("missing features")
         # Not enough history or source data to create all features expected by this model
         return None

      feature_row = extracted.features.select_row(self.feature_names)
      prediction = float(self.model.predict(feature_row)[0])

      if self.target_name == "midpoint_change":
         return self.create_midpoint_prediction(
               extracted=extracted,
               predicted_change=prediction,
         )

      # if self.target_name == "crypto_change":
      #    return self._create_crypto_change_prediction(
      #          extracted=extracted,
      #          predicted_change=prediction,
      #    )

      if self.target_name == "normalized_crypto_trend":
         return self.create_normalized_trend_prediction(
               extracted=extracted,
               predicted_crypto_change=prediction,
         )

   def predict(self, snapshot: MarketSnapshot):
      if self.model is None:
         return 0

      prediction = self.make_prediction(snapshot=snapshot)
      if prediction is None:
            predicted_trend = 0
            #print("none")
      else:
            predicted_trend = prediction.predicted_value
            #print(predicted_trend)
      return predicted_trend

   def update_and_predict(self, snapshot: MarketSnapshot):
      extracted = self.feature_extractor.update_and_extract(snapshot)
      if extracted is None:
         #print("extracted is None")
         return None

      missing_features = extracted.features.missing(self.feature_names)

      if missing_features:
         #print("missing features")
         # Not enough history or source data to create all features expected by this model
         return None

      feature_row = extracted.features.select_row(self.feature_names)
      prediction = float(self.model.predict(feature_row)[0])

      if self.target_name == "midpoint_change":
         return self.create_midpoint_prediction(
               extracted=extracted,
               predicted_change=prediction,
         )

      # if self.target_name == "crypto_change":
      #    return self._create_crypto_change_prediction(
      #          extracted=extracted,
      #          predicted_change=prediction,
      #    )

      if self.target_name == "normalized_crypto_trend":
         return self.create_normalized_trend_prediction(
               extracted=extracted,
               predicted_crypto_change=prediction,
         )
   


   def create_normalized_trend_prediction(
      self,
      extracted: ExtractedMarketState,
      predicted_crypto_change: float,
   ) -> NumericPrediction | None:
      current_crypto_price = extracted.current_crypto_price
      if current_crypto_price is None or current_crypto_price <= 0:
         return None

      volatility = self.crypto_price_stdev.get(self.market_name)
      #print(volatility) #make more generic later
      context={
         "current_crypto_price": current_crypto_price,
         "volatility": volatility,
         "predicted_crypto_change": predicted_crypto_change,
      }

      predicted_trend = predicted_crypto_change / volatility

      return NumericPrediction(
         prediction_timestamp=extracted.timestamp,
         horizon_ms=self.horizon_ms,
         predicted_value=predicted_trend,
         current_value=None,
         target=self.target_name,
         context=context,
      )
   
   def create_midpoint_prediction(self, extracted: ExtractedMarketState, predicted_change: float):
      predicted_midpoint = extracted.current_midpoint + predicted_change

      if self.clip_predictions:
         predicted_midpoint = self.clip_midpoint(predicted_midpoint)


      return NumericPrediction(
         prediction_timestamp=extracted.timestamp,
         horizon_ms=self.horizon_ms,
         predicted_value=predicted_midpoint,
         current_value=extracted.current_midpoint,
         target=self.target_name,
      )
   
   def update_past_crypto_values(self, crypto_value, current_timestamp, end_timestamp):
      return None


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
   

def initialize_predictor(lookahead_time, market_name):
   GRADIENT_BOOSTING_FEATURES = (
      "binance_return_1000",
      "binance_return_3000",
      #"binance_range_position_5000",
      #"binance_range_position_30000",
      #"binance_return_volatility_10000",
      #"binance_return_volatility_20000",
      #"binance_relative_high_distance_5000",
      #"binance_relative_low_distance_5000",
      #"binance_range_position_7000"
      #"binance_return_5000",
      #"binance_acceleration_1s_5s",
   )  

   #model = joblib.load("bot/models/trend_model.joblib")
   model = get_model(market_name=market_name)
   #print(model)
   predictor = GradientBoostingPredictor(
      model=model,
      feature_extractor=MarketFeatureExtractor(binance_lookbacks_ms=(1000,3000)),
      horizon_ms=lookahead_time,
      target_name="normalized_crypto_trend",
      gradient_boosting_features=GRADIENT_BOOSTING_FEATURES,
      training_samples=None,
      market_name=market_name,
   )
   return predictor

def get_model(market_name):
   if market_name == "bitcoin-up-or-down":
      model = joblib.load("bot/trained_models/trend_model_btc_2.joblib")
      print("bitcoin model loaded")
   elif market_name == "ethereum-up-or-down":
      model = joblib.load("bot/trained_models/trend_model_eth_2.joblib")
      print("ethereum model loaded")
   elif market_name == "solana-up-or-down":
      model = joblib.load("bot/trained_models/trend_model_sol_2.joblib")
      print("solana model loaded")
   elif market_name == "xrp-up-or-down":
      model = joblib.load("bot/trained_models/trend_model_xrp_2.joblib")
      print("xrp model loaded")
   else:
      model = None

   #(model)
   #print(market_name)
   return model

#vidjeti je li se koristi pravi model