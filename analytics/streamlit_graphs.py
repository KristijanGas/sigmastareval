from collections import defaultdict
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analytics.graph_drawer import _coerce_number, _normalize_timestamp, _series_from_points, _timestamp_to_datetime




def draw_replay_graph(analytics: dict) -> go.Figure:
    mid_prices = analytics.get("mid_prices", {}) or {}
    crypto_prices = analytics.get("crypto_prices", []) or []
    transactions = analytics.get("transactions", []) or []
    order_placements = analytics.get("order_placements", []) or []
    holdings_history = analytics.get("holdings_history", []) or []

    price_to_beat = _coerce_number(
        analytics.get("price_to_beat")
    )

    label_names = analytics.get("asset_labels", {}) or {}

    # ============================================================
    # Figure
    # ============================================================

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.46, 0.23, 0.31],
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": False}],
            [{"secondary_y": True}],
        ],
        subplot_titles=[
            "Asset prices, predictions and orders",
            "Crypto price relative to price to beat",
            "Holdings, cash and net worth",
        ],
    )

    # Plotly's standard qualitative colors.
    price_colors = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    action_colors = {
        "BID": "#1f77b4",
        "ASK": "#d62728",
    }

    # ============================================================
    # 1. Prediction-market midpoint prices
    # ============================================================

    for index, (asset_id, points) in enumerate(mid_prices.items()):
        timestamps, values = _series_from_points(
            points,
            value_key="mid_price",
        )

        if not timestamps:
            continue

        label = label_names.get(
            asset_id,
            f"{asset_id[:6]}…{asset_id[-4:]}",
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=values,
                mode="lines",
                name=f"{label} mid",
                line=dict(
                    color=price_colors[index % len(price_colors)],
                    width=2,
                ),
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Time: %{x}<br>"
                    "Mid: %{y:.4f}"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    # ============================================================
    # Predicted UP probability / midpoint
    # ============================================================

    (prediction_timestamps, up_prediction_values) = _series_from_points(
        analytics.get("past_crypto_predictions", []), value_key="up_prediction")

    if prediction_timestamps:
        fig.add_trace(
            go.Scatter(
                x=prediction_timestamps,
                y=up_prediction_values,
                mode="lines",
                name="Crypto prediction",
                line=dict(
                    color="#b30eff",
                    width=1.5,
                ),
                opacity=0.7,
                hovertemplate=(
                    "Prediction<br>"
                    "Time: %{x}<br>"
                    "Value: %{y:.4f}"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    # ============================================================
    # Order placements and executions
    # ============================================================

    placed_by_asset = defaultdict(
        lambda: {
            "BID": [],
            "ASK": [],
        }
    )

    executed_by_asset = defaultdict(
        lambda: {
            "BID": [],
            "ASK": [],
        }
    )

    for order in order_placements:
        asset_id = order.get("asset_id")
        action = order.get("order_action")
        timestamp = _normalize_timestamp(
            order.get("timestamp")
        )
        price = order.get("price")

        if (
            asset_id is None
            or action not in action_colors
            or timestamp is None
            or price is None
        ):
            continue

        placed_by_asset[asset_id][action].append(
            (
                _timestamp_to_datetime(timestamp),
                price,
            )
        )

    for transaction in transactions:
        asset_id = transaction.get("asset_id")
        action = transaction.get("order_action")
        timestamp = _normalize_timestamp(
            transaction.get("timestamp")
        )
        price = transaction.get("price")

        if (
            asset_id is None
            or action not in action_colors
            or timestamp is None
            or price is None
        ):
            continue

        executed_by_asset[asset_id][action].append(
            (
                _timestamp_to_datetime(timestamp),
                price,
            )
        )

    # ------------------------------------------------------------
    # Placed orders
    # ------------------------------------------------------------

    # for asset_id, styles in placed_by_asset.items():
    #     asset_label = label_names.get(
    #         asset_id,
    #         f"{asset_id[:6]}…{asset_id[-4:]}",
    #     )

    #     for action, points in styles.items():
    #         if not points:
    #             continue

    #         timestamps = [point[0] for point in points]
    #         prices = [point[1] for point in points]

    #         symbol = (
    #             "triangle-up"
    #             if action == "BID"
    #             else "triangle-down"
    #         )

    #         fig.add_trace(
    #             go.Scatter(
    #                 x=timestamps,
    #                 y=prices,
    #                 mode="markers",
    #                 name=f"{asset_label} {action} placed",
    #                 marker=dict(
    #                     symbol=symbol,
    #                     size=7,
    #                     color=action_colors[action],
    #                     opacity=0.30,
    #                 ),
    #                 hovertemplate=(
    #                     f"<b>{asset_label}</b><br>"
    #                     f"{action} placed<br>"
    #                     "Time: %{x}<br>"
    #                     "Price: %{y:.4f}"
    #                     "<extra></extra>"
    #                 ),
    #             ),
    #             row=1,
    #             col=1,
    #         )

    # ------------------------------------------------------------
    # Executed orders
    # ------------------------------------------------------------

    for asset_id, styles in executed_by_asset.items():
        asset_label = label_names.get(
            asset_id,
            f"{asset_id[:6]}…{asset_id[-4:]}",
        )

        for action, points in styles.items():
            if not points:
                continue

            timestamps = [point[0] for point in points]
            prices = [point[1] for point in points]

            symbol = (
                "triangle-up"
                if action == "BID"
                else "triangle-down"
            )

            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=prices,
                    mode="markers",
                    name=f"{asset_label} {action} placed/executed",
                    marker=dict(
                        symbol=symbol,
                        size=11,
                        color=action_colors[action],
                        opacity=0.95,
                        line=dict(
                            color="black",
                            width=1,
                        ),
                    ),
                    hovertemplate=(
                        f"<b>{asset_label}</b><br>"
                        f"{action} executed<br>"
                        "Time: %{x}<br>"
                        "Price: %{y:.4f}"
                        "<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )

    # ============================================================
    # 2. Crypto price relative to price to beat
    # ============================================================

    crypto_timestamps, crypto_values = _series_from_points(
        crypto_prices,
        value_key="price",
    )

    relative_crypto_values = []

    if (
        isinstance(price_to_beat, (int, float))
        and crypto_values
    ):
        relative_crypto_values = [
            value - price_to_beat
            for value in crypto_values
        ]

    elif crypto_values:
        relative_crypto_values = crypto_values

    if crypto_timestamps and relative_crypto_values:
        fig.add_trace(
            go.Scatter(
                x=crypto_timestamps,
                y=relative_crypto_values,
                mode="lines",
                name="Crypto price",
                line=dict(
                    color="#12db12",
                    width=2,
                ),
                fill="tozeroy",
                fillcolor="rgba(44,160,44,0.08)",
                hovertemplate=(
                    "Crypto price<br>"
                    "Time: %{x}<br>"
                    "Difference: %{y:.4f}"
                    "<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    # ============================================================
    # Filtered crypto / moving mean
    # ============================================================

    (filtered_timestamps, crypto_filtered) = _series_from_points(
        analytics.get("past_crypto_predictions", []), value_key="moving_mean")

    if (isinstance(price_to_beat, (int, float)) and crypto_filtered):
        relative_crypto_filtered = [value - price_to_beat
            for value in crypto_filtered]
    else:
        relative_crypto_filtered = crypto_filtered

    if filtered_timestamps and relative_crypto_filtered:
        fig.add_trace(
            go.Scatter(
                x=filtered_timestamps,
                y=relative_crypto_filtered,
                mode="lines",
                name="Crypto filtered",
                line=dict(
                    color="#b30eff",
                    width=1.5,
                ),
                opacity=0.7,
                hovertemplate=(
                    "Filtered crypto<br>"
                    "Time: %{x}<br>"
                    "Difference: %{y:.4f}"
                    "<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    # Price-to-beat line is zero because crypto values are relative.
    if isinstance(price_to_beat, (int, float)):
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="#8c564b",
            line_width=1.5,
            annotation_text="Price to beat",
            annotation_position="top left",
            row=2,
            col=1,
        )

    # ============================================================
    # 3. Holdings
    # ============================================================

    holdings_by_asset = defaultdict(list)

    for snapshot in holdings_history:
        timestamp = _normalize_timestamp(
            snapshot.get("timestamp")
        )

        holdings = snapshot.get("holdings", {}) or {}

        if timestamp is None:
            continue

        timestamp = _timestamp_to_datetime(timestamp)

        for asset_id, value in holdings.items():
            holdings_by_asset[asset_id].append(
                (timestamp, value)
            )

    for index, (asset_id, points) in enumerate(
        holdings_by_asset.items()
    ):
        if not points:
            continue

        timestamps = [point[0] for point in points]
        values = [point[1] for point in points]

        asset_label = label_names.get(
            asset_id,
            f"{asset_id[:6]}…{asset_id[-4:]}",
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=values,
                mode="lines",
                name=f"{asset_label} holdings",
                line=dict(
                    color=price_colors[index % len(price_colors)],
                    width=2,
                ),
                hovertemplate=(
                    f"<b>{asset_label}</b><br>"
                    "Time: %{x}<br>"
                    "Holdings: %{y:.4f}"
                    "<extra></extra>"
                ),
            ),
            row=3,
            col=1,
            secondary_y=False,
        )

    # ============================================================
    # Cash
    # ============================================================

    cash_timestamps = []
    cash_values = []

    if analytics.get("cash_history"):
        cash_points = analytics["cash_history"]

        for item in cash_points:
            timestamp = item.get("timestamp")
            cash = item.get("cash")

            if timestamp is None or cash is None:
                continue

            cash_timestamps.append(
                _timestamp_to_datetime(timestamp)
            )
            cash_values.append(cash)

    if cash_timestamps and cash_values:
        fig.add_trace(
            go.Scatter(
                x=cash_timestamps,
                y=cash_values,
                mode="lines",
                name="Cash",
                line=dict(
                    color="#444444",
                    width=1.5,
                    dash="dash",
                ),
                hovertemplate=(
                    "Cash<br>"
                    "Time: %{x}<br>"
                    "Cash: $%{y:.2f}"
                    "<extra></extra>"
                ),
            ),
            row=3,
            col=1,
            secondary_y=True,
        )

    # ============================================================
    # Net worth
    # ============================================================

    if (
        cash_timestamps
        and cash_values
        and holdings_by_asset
    ):
        net_worth = []

        # Calculating the most recent price independently for each asset/timestamp.
        price_indices = {
            asset_id: 0
            for asset_id in holdings_by_asset
        }

        for cash_index, (timestamp, cash) in enumerate(
            zip(cash_timestamps, cash_values)
        ):
            holdings_value = 0.0

            for asset_id, asset_points in holdings_by_asset.items():
                if not asset_points:
                    continue

                if cash_index >= len(asset_points):
                    shares = asset_points[-1][1]
                else:
                    shares = asset_points[cash_index][1]

                price_points = mid_prices.get(asset_id, [])

                if not price_points:
                    continue

                price_index = price_indices.get(asset_id, 0)
                latest_price = None

                while price_index < len(price_points):
                    price_point = price_points[price_index]

                    price_timestamp = _timestamp_to_datetime(
                        price_point.get("timestamp")
                    )

                    if price_timestamp <= timestamp:
                        latest_price = price_point.get(
                            "mid_price"
                        )
                        price_index += 1
                    else:
                        break

                # We moved one item past the latest valid point.
                price_indices[asset_id] = max(
                    price_index - 1,
                    0,
                )

                if latest_price is None:
                    current_index = price_indices[asset_id]

                    current_timestamp = _timestamp_to_datetime(
                        price_points[current_index].get(
                            "timestamp"
                        )
                    )

                    if current_timestamp <= timestamp:
                        latest_price = price_points[
                            current_index
                        ].get("mid_price")

                if latest_price is not None:
                    holdings_value += (
                        shares * latest_price
                    )

            net_worth.append(
                cash + holdings_value
            )

        fig.add_trace(
            go.Scatter(
                x=cash_timestamps,
                y=net_worth,
                mode="lines",
                name="Net worth",
                line=dict(
                    color="#b30eff",
                    width=2,
                ),
                hovertemplate=(
                    "Net worth<br>"
                    "Time: %{x}<br>"
                    "Value: $%{y:.2f}"
                    "<extra></extra>"
                ),
            ),
            row=3,
            col=1,
            secondary_y=True,
        )

    # ============================================================
    # Axes
    # ============================================================

    fig.update_yaxes(
        title_text="Asset price",
        range=[-0.02, 1.02],
        row=1,
        col=1,
        showgrid=True,
    )

    fig.update_yaxes(
        title_text="Crypto difference",
        row=2,
        col=1,
        showgrid=True,
    )

    fig.update_yaxes(
        title_text="Holdings",
        row=3,
        col=1,
        secondary_y=False,
        showgrid=True,
    )

    fig.update_yaxes(
        title_text="Cash / net worth",
        row=3,
        col=1,
        secondary_y=True,
        showgrid=False,
    )

    fig.update_xaxes(
        title_text="Timestamp",
        row=3,
        col=1,
    )

    # fig.update_xaxes(
    #     rangeslider_visible=True,
    #     row=3,
    #     col=1,
    # )

    # ============================================================
    # Layout
    # ============================================================

    fig.update_layout(
        title={
            "text": "Market replay",
            "x": 0.5,
        },
        height=1100,
        hovermode="x unified",
        legend=dict(
            orientation="v",
            yanchor="bottom",
            y=1.05,
            xanchor="left",
            x=0,
        ),
        margin=dict(
            l=60,
            r=60,
            t=200,
            b=60,
        ),
    )

    return fig



