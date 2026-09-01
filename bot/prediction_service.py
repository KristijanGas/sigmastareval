from typing import Any
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    
REPO_ROOT = Path(__file__).resolve().parents[1]

from bot.prediction_models.gradient_boosting_predictor import initialize_gradient_boosting_predictor
from bot.prediction_models.prediction_targets import PredictionTarget



class PredictionService:

    def __init__(self, selected_prediction_targets: list[PredictionTarget], market_name: str):
        self.SUPPORTED_TARGETS = {
        PredictionTarget.MIDPOINT_CHANGE,
        PredictionTarget.NORMALIZED_CRYPTO_TREND,
        PredictionTarget.OUTCOME_PROBABILITY,
        }

        self.validate_target_names(selected_prediction_targets)
        self.selected_prediction_targets = [PredictionTarget(target) for target in selected_prediction_targets]
        self.market_name = market_name      # used for choosing the appropriate model depending on a market
        self.prediction_models: dict[PredictionTarget, Any] = {}
        self.load_selected_predictors()


    def load_selected_predictors(self):
        for target in self.selected_prediction_targets:
            predictor = initialize_gradient_boosting_predictor(prediction_target=target, market_name=self.market_name)
            if predictor is not None:
                self.prediction_models[target] = predictor



    def validate_target_names(self, selected_prediction_targets):
        for target in selected_prediction_targets:
            if target not in self.SUPPORTED_TARGETS:
                raise ValueError(f"Unsupported target {target}. "
                    f"Expected supported targets: {sorted(self.SUPPORTED_TARGETS)}."
                )


    def update(self, snapshot):
        for predictor in self.prediction_models.values():
            predictor.update(snapshot)

    def reset(self):
        for predictor in self.prediction_models.values():
            predictor.reset()


    def predict_outcome_probability(self, snapshot):
        prediction_target = PredictionTarget.OUTCOME_PROBABILITY
        if prediction_target not in self.selected_prediction_targets:
            raise KeyError("Prediction service was not initialized with outcome probability model. Can't use this function.")

        predictor = self.prediction_models[prediction_target]
        up_win_probability = predictor.predict(snapshot)
        return up_win_probability


    def predict_normalized_crypto_trend(self, snapshot):
        prediction_target = PredictionTarget.NORMALIZED_CRYPTO_TREND
        if prediction_target not in self.selected_prediction_targets:
            raise KeyError("Prediction service was not initialized with normalized crypto trend model. Can't use this function.")

        predictor = self.prediction_models[prediction_target]
        predicted_trend = predictor.predict(snapshot)
        return predicted_trend



# selected_prediction_targets = [PredictionTarget.MIDPOINT_CHANGE, "normalized_crypto_trend", "outcome_probability"]

# ps = PredictionService(
#                 market_name="bitcoin-up-or-down",
#                 selected_prediction_targets=selected_prediction_targets,
#             )
