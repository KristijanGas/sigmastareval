


from collections import deque

import numpy as np


class polynomial_predictor:
    
    def __init__(self, degree=2):
        self.polynomial_degree = degree
        self.past_crypto_values = deque()
        self.past_crypto_rel_timestamps = deque()
        self.past_window_size = 30 * 1000  # 30 seconds
        self.price_to_beat = None  # This will be set externally when the predictor is used

    def predict_future_crypto_value(self, future_timestamp):
        if len(self.past_crypto_rel_timestamps) < 10:
            return None
        scaled_timestamps = []
        relative_crypto_values = []
        for x in self.past_crypto_rel_timestamps:
            scaled_timestamps.append(round((x - self.past_crypto_rel_timestamps[0]) / 1000.0, 6))  # Scale timestamps to seconds
        future_timestamp = (future_timestamp - self.past_crypto_rel_timestamps[0]) / 1000.0  # Scale future difference to seconds
        future_timestamp = round(future_timestamp, 6)
        for y in self.past_crypto_values:
            relative_crypto_values.append(round(y - self.price_to_beat, 6))
        #print(f"Scaled timestamps: {scaled_timestamps}, Relative crypto values: {relative_crypto_values}")

        coefficients = np.polyfit(scaled_timestamps, relative_crypto_values, self.polynomial_degree)
        prediction = np.polyval(coefficients, future_timestamp)
        #print(f"Predicted future crypto value at timestamp {future_timestamp}: {prediction}")

        return prediction
    
    def update_past_crypto_values(self, crypto_value, current_timestamp, end_timestamp):
        current_timestamp_rel = (current_timestamp - end_timestamp) # Convert to seconds
        #print(f"Current timestamp: {current_timestamp}, Past crypto timestamps: {list(self.past_crypto_rel_timestamps)}, Past crypto values: {list(self.past_crypto_values)}")
        self.past_crypto_rel_timestamps.append(current_timestamp_rel)
        self.past_crypto_values.append(crypto_value)
        # Remove old values outside the past window size
        #print(len(self.past_crypto_rel_timestamps), len(self.past_crypto_values))
        while self.past_crypto_rel_timestamps and (current_timestamp_rel - self.past_window_size) > self.past_crypto_rel_timestamps[0]:
            self.past_crypto_rel_timestamps.popleft()
            self.past_crypto_values.popleft()