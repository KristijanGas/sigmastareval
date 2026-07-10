


# all knowing predictor, use for testing strategies with assumption of knowing all
class nostradamus:
    def __init__(self, data):
        self.data = data
    def update_past_crypto_values(self, crypto_value, current_timestamp, end_timestamp):
        pass
    def predict_future_crypto_value(self, lookahead_time, current_timestamp, end_timestamp):
        future_timestamp = lookahead_time  + current_timestamp
        for entry in self.data["all_prices"]:
            if int(entry["timestamp"] * 1000) >= future_timestamp:
                return float(entry["price"])
        return float(self.data["all_prices"][-1]["price"])