from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import argparse
import gzip
import json
import re

def _coerce_number(value):
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return value
	if isinstance(value, str):
		try:
			if "." in value or "e" in value.lower():
				return float(value)
			return int(value)
		except ValueError:
			return value
	return value


def _series_from_points(points, value_key):
	timestamps = []
	values = []
	for index, point in enumerate(points or []):
		if isinstance(point, dict):
			timestamp = point.get("timestamp", index)
			value = point.get(value_key)
			if value is None and value_key != "price":
				value = point.get("price")
		else:
			timestamp = index
			value = point
		if value is None:
			continue
		timestamps.append(_timestamp_to_datetime(timestamp))
		values.append(_coerce_number(value))
	return timestamps, values


def _timestamp_to_datetime(timestamp):
    if timestamp is None:
        return None

    if isinstance(timestamp, datetime):
        return timestamp

    if isinstance(timestamp, (int, float)):
        if abs(timestamp) >= 1_000_000_000_000:
            return datetime.fromtimestamp(timestamp / 1000)
        return datetime.fromtimestamp(timestamp)

    if isinstance(timestamp, str):
        # unix timestamp stored as string
        try:
            return _timestamp_to_datetime(float(timestamp))
        except ValueError:
            pass

        # ISO8601
        try:
            return datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            pass

    raise ValueError(f"Unsupported timestamp: {timestamp!r}")


def _set_dynamic_ylim(axis, values):
	clean_values = []
	for value in values:
		coerced = _coerce_number(value)
		if isinstance(coerced, (int, float)) and not isinstance(coerced, bool):
			clean_values.append(float(coerced))
	if not clean_values:
		return
	minimum = min(clean_values)
	maximum = max(clean_values)
	span = maximum - minimum
	if span == 0:
		padding = max(abs(maximum) * 0.05, 1.0)
	else:
		padding = max(span * 0.15, abs((maximum + minimum) / 2) * 0.02)
	axis.set_ylim(minimum - padding, maximum + padding)


def _normalize_timestamp(value: Any):
	if value is None:
		return None
	if isinstance(value, (int, float)):
		return value
	return value


def draw_graph(analytics: dict, output_path: str | Path | None = None, show: bool = False):
	mid_prices = analytics.get("mid_prices", {}) or {}
	crypto_prices = analytics.get("crypto_prices", []) or []
	transactions = analytics.get("transactions", []) or []
	order_placements = analytics.get("order_placements", []) or []
	holdings_history = analytics.get("holdings_history", []) or []
	price_to_beat = _coerce_number(analytics.get("price_to_beat"))
	label_names = analytics.get("asset_labels", {}) or {}
	#print(len(crypto_prices), "crypto price points")

	fig, (ax_prices, ax_crypto, ax_holdings) = plt.subplots(
		3,
		1,
		figsize=(16, 11),
		sharex=True,
		gridspec_kw={"height_ratios": [2.2, 1.1, 1.4]},
		constrained_layout=True,
	)

	price_colors = plt.cm.tab10.colors
	action_colors = {"BID": "#1f77b4", "ASK": "#d62728"}

	price_handles = []
	for index, (asset_id, points) in enumerate(mid_prices.items()):
		timestamps, values = _series_from_points(points, value_key="mid_price")
		if not timestamps:
			continue
		color = price_colors[index % len(price_colors)]
		line, = ax_prices.plot(
			timestamps,
			values,
			color=color,
			linewidth=1.8,
			label=f"{label_names.get(asset_id, f"{asset_id[:6]}…{asset_id[-4:]}")} mid",
		)
		price_handles.append(line)

	prediction_timestamps, up_prediction_values = _series_from_points(analytics.get("past_crypto_predictions", []), value_key="up_prediction")
	up_prediction_values_relative = [value for value in up_prediction_values]
	ax_prices.plot(
		prediction_timestamps,
		up_prediction_values_relative,
		color="#ff0ef36c",
		linewidth=1.2,
		label="crypto prediction",
	)

	placed_by_asset = defaultdict(lambda: {"BID": [], "ASK": []})
	executed_by_asset = defaultdict(lambda: {"BID": [], "ASK": []})

	for order in order_placements:
		asset_id = order.get("asset_id")
		action = order.get("order_action")
		timestamp = _normalize_timestamp(order.get("timestamp"))
		price = order.get("price")
		if asset_id is None or action not in action_colors or timestamp is None or price is None:
			continue
		placed_by_asset[asset_id][action].append((_timestamp_to_datetime(timestamp), price))

	for transaction in transactions:
		asset_id = transaction.get("asset_id")
		action = transaction.get("order_action")
		timestamp = _normalize_timestamp(transaction.get("timestamp"))
		price = transaction.get("price")
		if asset_id is None or action not in action_colors or timestamp is None or price is None:
			continue
		executed_by_asset[asset_id][action].append((_timestamp_to_datetime(timestamp), price))

	for styles in placed_by_asset.values():
		for action, points in styles.items():
			if not points:
				continue
			timestamps = [point[0] for point in points]
			prices = [point[1] for point in points]
			marker = "^" if action == "BID" else "v"
			ax_prices.scatter(
				timestamps,
				prices,
				color=action_colors[action],
				marker=marker,
				s=34,
				alpha=0.3,
				edgecolors="none",
			)

	for styles in executed_by_asset.values():
		for action, points in styles.items():
			if not points:
				continue
			timestamps = [point[0] for point in points]
			prices = [point[1] for point in points]
			marker = "^" if action == "BID" else "v"
			ax_prices.scatter(
				timestamps,
				prices,
				color=action_colors[action],
				marker=marker,
				s=70,
				alpha=0.9,
				edgecolors="black",
				linewidths=0.4,
			)

	ax_prices.set_ylim(-0.02, 1.02)
	ax_prices.yaxis.set_major_locator(MaxNLocator(nbins=6, prune="both"))
	ax_prices.set_ylabel("Asset price")
	ax_prices.set_title("Market replay: prices, orders, and holdings")
	ax_prices.grid(True, alpha=0.18)
	crypto_timestamps, crypto_values = _series_from_points(crypto_prices, value_key="price")
	relative_crypto_values = [value - price_to_beat for value in crypto_values]
	prediction_timestamps, crypto_filtered = _series_from_points(analytics.get("past_crypto_predictions", []), value_key="moving_mean")
	relative_crypto_filtered = [value - price_to_beat for value in crypto_filtered]

	if crypto_timestamps and crypto_values:
		
		ax_crypto.plot(
			crypto_timestamps,
			relative_crypto_values,
			color="#12db12ff",
			linewidth=1.8,
			label="crypto price",
		)
		ax_crypto.fill_between(crypto_timestamps, relative_crypto_values, color="#2ca02c", alpha=0.1)

		ax_crypto.plot(
			prediction_timestamps,
			relative_crypto_filtered,
			color="#ff0ef36c",
			linewidth=1.2,
			label="crypto prediction",
		)

	#_set_dynamic_ylim(ax_crypto, up_prediction_values_relative + relative_crypto_values)
	if isinstance(price_to_beat, (int, float)):
		ax_crypto.axhline(
			0,
			color="#8c564b",
			linestyle="--",
			linewidth=1.6,
			label="price to beat",
		)
	ax_crypto.set_ylabel("Crypto value")
	ax_crypto.yaxis.set_major_locator(MaxNLocator(nbins=5, prune="both"))
	ax_crypto.grid(True, alpha=0.18)

	holdings_by_asset = defaultdict(list)
	for snapshot in holdings_history:
		timestamp = _normalize_timestamp(snapshot.get("timestamp"))
		holdings = snapshot.get("holdings", {}) or {}
		if timestamp is None:
			continue
		timestamp = _timestamp_to_datetime(timestamp)
		for asset_id, value in holdings.items():
			holdings_by_asset[asset_id].append((timestamp, value))

	for index, (asset_id, points) in enumerate(holdings_by_asset.items()):
		if not points:
			continue
		timestamps = [point[0] for point in points]
		values = [point[1] for point in points]
		ax_holdings.plot(
			timestamps,
			values,
			linewidth=1.8,
			color=price_colors[index % len(price_colors)],
			label=label_names.get(asset_id, f"{asset_id[:6]}…{asset_id[-4:]}")
		)

	if analytics.get("cash_history"):
		cash_points = analytics["cash_history"]
		cash_timestamps = [_timestamp_to_datetime(item.get("timestamp")) for item in cash_points if item.get("timestamp") is not None]
		cash_values = [item.get("cash") for item in cash_points if item.get("cash") is not None]
		if cash_timestamps and cash_values:
			ax_holdings_twin = ax_holdings.twinx()
			ax_holdings_twin.plot(
				cash_timestamps,
				cash_values,
				color="#444444",
				linestyle="--",
				linewidth=1.2,
				alpha=0.8,
				label="cash",
			)
			ax_holdings_twin.set_ylabel("Cash")
			ax_holdings_twin.tick_params(axis="y", labelcolor="#444444")

			net_worth = []
			last_ind = 0
			cash_ind = 0
			for timestamp, value in zip(cash_timestamps, cash_values):
				holdings_values = 0
				
				for asset_id in holdings_by_asset:
					asset_points = holdings_by_asset[asset_id]
					holdings_value = 0.0
					for i in range(last_ind,len(mid_prices.get(asset_id, []))):
						#print(asset_points[i][0], timestamp, asset_points[i][0] <= timestamp)
						if _timestamp_to_datetime(mid_prices.get(asset_id)[i].get("timestamp", 0.0)) <= timestamp:
							#print(mid_prices.get(asset_id)[i].get("mid_price", 0.0), i)
							holdings_value = asset_points[cash_ind][1] * mid_prices.get(asset_id)[i].get("mid_price", 0.0)
							last_ind = i
						else:
							holdings_values += holdings_value
							break
				cash_ind+=1
				net_worth.append(holdings_values + value)
			ax_holdings_twin.plot(
				cash_timestamps,
				net_worth,
				color="#b30eff",
				linestyle="-",
				linewidth=1.4,
				alpha=0.9,
				label="net worth",
			)

	ax_holdings.set_ylabel("Holdings")
	ax_holdings.yaxis.set_major_locator(MaxNLocator(nbins=5, prune="both"))
	ax_holdings.set_xlabel("Timestamp")
	ax_holdings.grid(True, alpha=0.18)

	price_legend = [
		plt.Line2D([0], [0], color=action_colors["BID"], marker="^", linestyle="None", label="Bid placed/executed"),
		plt.Line2D([0], [0], color=action_colors["ASK"], marker="v", linestyle="None", label="Ask placed/executed"),
	]
	handles = price_handles + price_legend
	if handles:
		ax_prices.legend(handles=handles, loc="upper left", fontsize=9, ncol=2)
	if crypto_timestamps and crypto_values:
		ax_crypto.legend(loc="upper left")
	if holdings_by_asset:
		ax_holdings.legend(loc="upper left", ncol=2, fontsize=9)

	locator = mdates.AutoDateLocator()
	formatter = mdates.ConciseDateFormatter(locator)
	for axis in (ax_prices, ax_crypto, ax_holdings):
		axis.xaxis.set_major_locator(locator)
		axis.xaxis.set_major_formatter(formatter)
	fig.autofmt_xdate()

	output_path = Path(output_path) if output_path is not None else Path("analytics_graph.png")
	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=180, bbox_inches="tight")

	if show:
		plt.show()

	plt.close(fig)
	return output_path


if __name__ == "__main__":

	parser = argparse.ArgumentParser(description="Draw replay analytics graphs")
	parser.add_argument(
		"analytics_json",
		help="Path to an analytics JSON or live-run JSON.GZ file",
	)
	parser.add_argument(
		"--output",
		default="analytics_graph.png",
		help="Output image path",
	)
	parser.add_argument(
		"--show",
		action="store_true",
		help="Display the plot interactively",
	)
	args = parser.parse_args()

	input_path = Path(args.analytics_json)

	if input_path.suffixes[-2:] == [".json", ".gz"]:
		with gzip.open(input_path, "rt", encoding="utf-8") as handle:
			analytics = json.load(handle)
		#print(analytics)
		# Find the matching backtester analysis file
		market = input_path.parent.name
		analysis_dir = Path("tmp") / market

		# Remove the .json.gz suffix
		stem = input_path.name[:-len(".json.gz")]

		# Remove an optional trailing "_<32 hex chars>" hash
		stem = re.sub(r"_[0-9a-fA-F]{32}$", "", stem)

		analysis_path = analysis_dir / f"{stem}.analysis.json"
		print(analysis_path)
		print(analytics["holdings_history"])
		if not analysis_path.exists():
			print("Could not find same replay engine analysis file")
		else:
			with analysis_path.open("r", encoding="utf-8") as handle:
				base_analytics = json.load(handle)

			# Override base analytics with whatever exists in the live run
			base_analytics.update(analytics)
			analytics = base_analytics

	else:
		# Standard backtester analytics file
		with input_path.open("r", encoding="utf-8") as handle:
			analytics = json.load(handle)

	result = draw_graph(
	analytics,
	output_path=args.output,
	show=args.show,
	)
	print(result)