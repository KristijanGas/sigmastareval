


# all knowing predictor, use for testing strategies with assumption of knowing all
import copy


class nostradamus:
    def __init__(self, data):
        self.data = copy.deepcopy(data)

        for entry in self.data["all_prices"]:
            if entry is not None:
                entry["timestamp"] = int(entry["timestamp"] * 1000)  # Convert to milliseconds
        
    def update_past_crypto_values(self, crypto_value, current_timestamp, end_timestamp):
        pass
    def predict_future_crypto_value(self, lookahead_time, current_timestamp, end_timestamp):
        future_timestamp = lookahead_time  + current_timestamp
        for entry in self.data["all_prices"]:
            if entry is not None and entry["timestamp"] >= future_timestamp:
                return float(entry["price"])
        return float(self.data["all_prices"][-1]["price"])
    
    def predict_trend(self, lookahead_time, current_timestamp, end_timestamp, stdev,current_price):
        future_timestamp = lookahead_time  + current_timestamp
        cnt_future = 0
        future_price = 0
        for entry in self.data["all_prices"]:
            if entry is not None and entry["timestamp"] >= future_timestamp:
                cnt_future += 1
                future_price += float(entry["price"])
            if cnt_future >= 3: # average over to smooth out
                break
        if cnt_future != 0:
            future_price /= cnt_future
        if future_price == 0:
            future_price = float(self.data["all_prices"][-1]["price"])
        difference = (future_price - current_price) / stdev
        return difference