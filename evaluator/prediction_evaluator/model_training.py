


'''
File used for model training related logic, model specific helpers and dataclasses.
'''

from evaluator.prediction_evaluator.training_targets import OUTCOME_PROBABILITY_TARGET, TrainingTarget


ARTIFACT_VERSION = 2
TASK_REGRESSION = "regression"
TASK_BINARY_CLASSIFICATION = "binary_classification"
PREDICTION_MODE_RAW = "raw"
PREDICTION_MODE_CALIBRATED = "calibrated"





def get_task_type(target: TrainingTarget) -> str:
    if target.name == OUTCOME_PROBABILITY_TARGET.name:
        return TASK_BINARY_CLASSIFICATION
    return TASK_REGRESSION


