


# all knowing predictor, use for testing strategies with assumption of knowing all
import copy


class nostradamus:
    def __init__(self, data):
        self.data = copy.deepcopy(data)
        self.last_up_orderbook_index = 0
        self.last_down_orderbook_index = 0
        self.price_to_beat = None
        self.last_midpoint = None
        # self.prev_midpoint_up = None     # used in case of multiple function calls in the same timestamp
        # self.prev_ts_midpoint_up = None  # used to identify multiple calls in the same timestamp
        # self.prev_midpoint_down = None
        # self.prev_ts_midpoint_down = None

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
        try:
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
        except Exception as e:
            print(f"Error in predict_trend: {e}")
            return 0.0
        return difference


    def predict_midpoint_up(self, lookahead_time, current_timestamp, current_midpoint):
        asset_index = 0
        future_timestamp = current_timestamp + lookahead_time   # requested timestamp for prediction
        clobs_list = self.data["all_clobs"]

        for i in range(self.last_up_orderbook_index, len(clobs_list)):
            clob_element_up = clobs_list[i][asset_index]
            timestamp = int(clob_element_up[1]["timestamp"])

            if timestamp >= future_timestamp + 1500:    # first found timestamp is too far from requested one
                self.last_up_orderbook_index += (i - self.last_up_orderbook_index)
                return None

            if timestamp >= future_timestamp:
                raw_book = clob_element_up[1]
                bids = raw_book.get("bids")
                asks = raw_book.get("asks")
                if not bids:
                    continue
                else:
                    best_bid_level = bids[-1]
                    best_bid = float(best_bid_level["price"])
                
                if not asks:
                    continue
                else:
                    best_ask_level = asks[-1]
                    best_ask = float(best_ask_level["price"])

                future_midpoint = (best_bid + best_ask) / 2
                # print(f"future timestamp:  {timestamp}"
                #       f"future midpoint: {future_midpoint}")
                self.last_up_orderbook_index += (i - self.last_up_orderbook_index)

                return future_midpoint - current_midpoint

        last_element = clobs_list[-1][asset_index]
        last_timestamp = int(last_element[1]["timestamp"])
        
        if last_timestamp - current_timestamp < lookahead_time:
            lookback_time = last_timestamp - current_timestamp
            last_midpoint = self.get_last_midpoint(clobs_list, last_timestamp, asset_index, lookback_time)
            if last_midpoint is not None and current_midpoint is not None:
                return last_midpoint - current_midpoint


    def predict_midpoint_down(self, lookahead_time, current_timestamp, current_midpoint):
        asset_index = 1
        future_timestamp = current_timestamp + lookahead_time   # requested timestamp for prediction
        clobs_list = self.data["all_clobs"]

        for i in range(self.last_down_orderbook_index, len(clobs_list)):
            clob_element_down = clobs_list[i][asset_index]
            timestamp = int(clob_element_down[1]["timestamp"])

            if timestamp >= future_timestamp + 1500:    # first found timestamp is too far from requested one
                self.last_down_orderbook_index += (i - self.last_down_orderbook_index)
                return None

            if timestamp >= future_timestamp:
                raw_book = clob_element_down[1]
                bids = raw_book.get("bids")
                asks = raw_book.get("asks")
                if not bids:
                    continue
                else:
                    best_bid_level = bids[-1]
                    best_bid = float(best_bid_level["price"])
                
                if not asks:
                    continue
                else:
                    best_ask_level = asks[-1]
                    best_ask = float(best_ask_level["price"])

                future_midpoint = (best_bid + best_ask) / 2
                # print(f"future timestamp:  {timestamp}"
                #       f"future midpoint: {future_midpoint}")
                self.last_down_orderbook_index += (i - self.last_down_orderbook_index)
                
                return future_midpoint - current_midpoint

        last_element = clobs_list[-1][asset_index]
        last_timestamp = int(last_element[1]["timestamp"])
        
        if last_timestamp - current_timestamp < lookahead_time:
            lookback_time = last_timestamp - current_timestamp
            last_midpoint = self.get_last_midpoint(clobs_list, last_timestamp, asset_index, lookback_time)
            if last_midpoint is not None and current_midpoint is not None:
                return last_midpoint - current_midpoint



    # used when time remaining is less than lookahead_time
    def get_last_midpoint(self, clobs_list, last_timestamp, asset_index, lookback_time):
        if self.last_midpoint is not None:
            return self.last_midpoint
        else:
            timestamp = int(clobs_list[-1][asset_index][1]["timestamp"])
            #print(timestamp)
            ind = 1

            while last_timestamp - timestamp < lookback_time: #search backwards to find last midpoint value which is not None
                clob_element = clobs_list[-ind][asset_index]
                raw_book = clob_element[1]
                timestamp = int(raw_book["timestamp"])
                
                bids = raw_book.get("bids")
                asks = raw_book.get("asks")

                if not bids:
                    ind += 1
                    continue
                else:
                    best_bid_level = bids[-1]
                    best_bid = float(best_bid_level["price"])
                
                if not asks:
                    ind += 1
                    continue
                else:
                    best_ask_level = asks[-1]
                    best_ask = float(best_ask_level["price"])

                last_midpoint = (best_bid + best_ask) / 2
                self.last_midpoint = last_midpoint

                return last_midpoint
    