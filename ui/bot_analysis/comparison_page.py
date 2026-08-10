import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from evaluator.utils.utils import sort_paths_chronologically


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.performance_analyzer import PerformanceAnalyzer
from analytics.streamlit_graphs import draw_replay_graph
from ui.bot_analysis.analysis_page import find_analysis_files, load_all_markets



APP_TITLE = "Run Comparison"
DEFAULT_ANALYSIS_DIRECTORY = "tmp/bitcoin-up-or-down"
DEFAULT_ANALYSIS_DIRECTORY_B = "live_runs/passive/bitcoin-up-or-down"


METRIC_SPECS = [
    ("final_cash", "Final cash", "currency"),
    ("pnl", "PnL", "currency"),
    ("roi", "ROI", "percent"),
    ("max_drawdown", "Max drawdown", "percent"),
    ("trade_count", "Trades", "integer"),
    ("win_rate", "Win rate", "percent"),
    ("profit_factor", "Profit factor", "ratio"),
    ("total_fees", "Total fees", "currency"),
    ("average_trade_profit", "Average trade PnL", "currency"),
    ("median_trade_profit", "Median trade PnL", "currency"),
    ("largest_gain", "Largest gain", "currency"),
    ("largest_loss", "Largest loss", "currency"),
    ("turnover", "Turnover", "ratio"),
    ("traded_volume", "Traded volume", "currency"),
    ("idle_time", "Idle time", "percent"),
    ("fees_to_balance", "Fees / initial balance", "percent"),
    ("fee_efficiency", "Fee efficiency", "ratio"),
    ("time_before_expiration_min", "Avg entry before expiry", "number"),
]


def number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_value(value: Any, kind: str) -> str:
    value = number_or_none(value)
    if value is None:
        return "—"
    if kind == "currency":
        return f"${value:,.2f}"
    if kind == "percent":
        return f"{value:.2%}"
    if kind == "integer":
        return f"{int(round(value)):,}"
    if kind == "ratio":
        return f"{value:.3f}"
    return f"{value:,.2f}"


def format_difference(value: Any, kind: str) -> str:
    value = number_or_none(value)
    if value is None:
        return "—"
    if kind == "currency":
        sign = "+" if value >= 0 else "-"
        return f"{sign}${abs(value):,.2f}"
    if kind == "percent":
        # Inputs are stored as fractions, so this displays percentage-point difference.
        return f"{value:+.2%}"
    if kind == "integer":
        return f"{int(round(value)):+,}"
    if kind == "ratio":
        return f"{value:+.3f}"
    return f"{value:+,.2f}"


def timestamp_to_datetime(value: Any):
    if value is None:
        return pd.NaT

    if isinstance(value, (int, float)):
        unit = "ms" if abs(value) >= 1_000_000_000_000 else "s"
        return pd.to_datetime(value, unit=unit, errors="coerce")

    return pd.to_datetime(value, errors="coerce", utc=False)


def selected_record(frame: pd.DataFrame, market_name: str) -> pd.Series:
    return frame.loc[frame["market"] == market_name].iloc[0]


@dataclass
class RunComparator:
    analyzer_a: PerformanceAnalyzer
    analyzer_b: PerformanceAnalyzer
    record_a: pd.Series
    record_b: pd.Series
    name_a: str
    name_b: str

    def metric_table(self) -> pd.DataFrame:
        rows = []
        for key, label, kind in METRIC_SPECS:
            a = number_or_none(self.record_a.get(key))
            b = number_or_none(self.record_b.get(key))
            difference = None if a is None or b is None else a - b
            rows.append(
                {
                    "Metric": label,
                    "Run A": format_value(a, kind),
                    "Run B": format_value(b, kind),
                    "A - B": format_difference(difference, kind),
                }
            )
        return pd.DataFrame(rows)




def midpoint_frame(analyzer: PerformanceAnalyzer) -> pd.DataFrame:
    analyzer.load_data()
    data = analyzer.data or {}
    labels = data.get("asset_labels", {}) or {}
    rows = []

    for asset_id, points in (data.get("mid_prices", {}) or {}).items():
        label = labels.get(asset_id, asset_id)
        for point in points or []:
            timestamp = point.get("timestamp")
            price = number_or_none(point.get("mid_price"))
            if timestamp is None or price is None:
                continue
            rows.append(
                {
                    "timestamp": timestamp,
                    "time": timestamp_to_datetime(timestamp),
                    "asset": label,
                    "mid_price": price,
                }
            )

    del analyzer.data
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["asset", "timestamp"], kind="stable")
    return frame


def build_midpoint_comparison_figure(comparator: RunComparator) -> go.Figure:
    a = midpoint_frame(comparator.analyzer_a)
    b = midpoint_frame(comparator.analyzer_b)

    figure = go.Figure()

    for asset in sorted(set(a.get("asset", [])) | set(b.get("asset", []))):
        a_asset = a[a["asset"] == asset] if not a.empty else pd.DataFrame()
        b_asset = b[b["asset"] == asset] if not b.empty else pd.DataFrame()

        if not a_asset.empty:
            figure.add_trace(
                go.Scatter(
                    x=a_asset["time"],
                    y=a_asset["mid_price"],
                    mode="lines",
                    name=f"A · {asset}",
                )
            )

        if not b_asset.empty:
            figure.add_trace(
                go.Scatter(
                    x=b_asset["time"],
                    y=b_asset["mid_price"],
                    mode="lines",
                    name=f"B · {asset}",
                    line=dict(dash="dash"),
                )
            )

    figure.update_layout(
        #title="Market midpoint comparison",
        title={
            "text": "Market midpoint comparison",
            "x": 0.4,
        },
        height=520,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06),
        margin=dict(l=30, r=30, t=100, b=30),
        uirevision=f"mid|{comparator.name_a}|{comparator.name_b}",
    )
    figure.update_yaxes(title_text="Mid price", range=[-0.02, 1.02])
    figure.update_xaxes(title_text="Timestamp", rangeslider_visible=True)
    return figure


def render_summary(comparator: RunComparator) -> None:
    st.subheader("Metric comparison")
    st.caption("Differences are Run A minus Run B.")
    st.dataframe(
        comparator.metric_table(),
        hide_index=True,
        width="stretch",
    )

    comparator.analyzer_a.load_data()

    left, right = st.columns(2)
    with left:
        st.subheader("Run A metadata")
        st.json(
            {
                "market": comparator.name_a,
                "resolution": (comparator.analyzer_a.data or {}).get("resolution"),
                "price_to_beat": (comparator.analyzer_a.data or {}).get("price_to_beat"),
                "transactions": len((comparator.analyzer_a.data or {}).get("transactions", []) or []),
                "source": str(comparator.analyzer_a.analytics_path),
            },
            expanded=False,
        )
    del comparator.analyzer_a.data

    comparator.analyzer_b.load_data()
    with right:
        st.subheader("Run B metadata")
        st.json(
            {
                "market": comparator.name_b,
                "resolution": (comparator.analyzer_b.data or {}).get("resolution"),
                "price_to_beat": (comparator.analyzer_b.data or {}).get("price_to_beat"),
                "transactions": len((comparator.analyzer_b.data or {}).get("transactions", []) or []),
                "source": str(comparator.analyzer_b.analytics_path),
            },
            expanded=False,
        )
    del comparator.analyzer_b.data



def render_replays(comparator: RunComparator) -> None:
    st.caption(
        "These are the existing per-run replay figures. For synchronized zooming, use the Equity and Market data tabs."
    )

    comparator.analyzer_a.load_data()
    left, right = st.columns(2)
    with left:
        st.subheader("Run A")
        try:
            st.plotly_chart(
                draw_replay_graph(comparator.analyzer_a.data),
                width="stretch",
                config={"scrollZoom": True, "displaylogo": False},
                key="comparison_replay_a",
            )
        except Exception as exc:
            st.error(f"Run A replay failed: {type(exc).__name__}: {exc}")

    del comparator.analyzer_a.data

    comparator.analyzer_b.load_data()
    with right:
        st.subheader("Run B")
        try:
            st.plotly_chart(
                draw_replay_graph(comparator.analyzer_b.data),
                width="stretch",
                config={"scrollZoom": True, "displaylogo": False},
                key="comparison_replay_b",
            )
        except Exception as exc:
            st.error(f"Run B replay failed: {type(exc).__name__}: {exc}")
    del comparator.analyzer_b.data


def render_errors(label: str, errors: list[dict[str, str]]) -> None:
    if not errors:
        return
    with st.expander(f"{label}: skipped files ({len(errors)})", expanded=False):
        st.dataframe(pd.DataFrame(errors), hide_index=True, width="stretch")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Compare any two analyzed market runs. Run A is treated as the left/reference side of A - B differences.")

    with st.sidebar:
        st.header("Run comparison data")
        directory_a_text = st.text_input(
            "Run A analysis directory",
            DEFAULT_ANALYSIS_DIRECTORY,
            key="comparison_directory_a",
        )
        directory_b_text = st.text_input(
            "Run B analysis directory",
            DEFAULT_ANALYSIS_DIRECTORY_B,
            key="comparison_directory_b",
        )
        initial_balance = st.number_input(
            "Initial balance",
            min_value=0.01,
            value=100.0,
            step=10.0,
            key="comparison_initial_balance",
        )
        transaction_tolerance_ms = st.number_input(
            "Transaction match tolerance (ms)",
            min_value=0,
            value=2000,
            step=100,
            key="comparison_transaction_tolerance",
            help="Transactions are paired by asset + action, then nearest timestamp within this tolerance.",
        )
        equity_tolerance_ms = st.number_input(
            "Equity alignment tolerance (ms)",
            min_value=0,
            value=2000,
            step=100,
            key="comparison_equity_tolerance",
            help="Run B equity points are aligned to the nearest Run A timestamp within this tolerance.",
        )

    directory_a = Path(directory_a_text).expanduser()
    directory_b = Path(directory_b_text).expanduser()

    for label, directory in (("Run A", directory_a), ("Run B", directory_b)):
        if not directory.exists() or not directory.is_dir():
            st.error(f"{label} analysis directory does not exist: {directory}")
            st.stop()

    paths_a = find_analysis_files(directory_a)
    paths_b = find_analysis_files(directory_b)

    if not paths_a:
        st.warning(f"No *.json files found for Run A under {directory_a}")
        st.stop()
    if not paths_b:
        st.warning(f"No *.json files found for Run B under {directory_b}")
        st.stop()


    names_a = sort_paths_chronologically(paths_a)
    names_b = sort_paths_chronologically(paths_b)
    names_a.reverse()
    names_b.reverse()

    if "comparison_pair" not in st.session_state:
        st.session_state.comparison_pair = None

    if st.session_state.get("comparison_market_a") not in names_a:
        st.session_state.comparison_market_a = names_a[0]

    # Render the two run selectors side by side.

    with st.form("comparison_form"):
        selector_left, selector_button, selector_right = st.columns([5, 1, 5])

        with selector_left:
            market_a = st.selectbox(
                "Run A",
                names_a,
                key="comparison_market_a",
            )
            st.caption(f"Source A: {directory_a}")

        # If the same market exists in Run B, use it as the initial comparison target.
        if st.session_state.get("comparison_market_b") not in names_b:
            st.session_state.comparison_market_b = market_a if market_a in names_b else names_b[0]

        # def select_matching_b() -> None:
        #     selected_a = st.session_state.get("comparison_market_a")
        #     if selected_a in names_b:
        #         st.session_state.comparison_market_b = selected_a

        # with selector_button:
        #     st.write("")
        #     st.write("")
        #     st.button(
        #         "Match B",
        #         on_click=select_matching_b,
        #         disabled=market_a not in names_b,
        #         help="Select the Run B item with the same market name as Run A.",
        #         width="stretch",
        #     )

        with selector_right:
            market_b = st.selectbox(
                "Run B",
                names_b,
                key="comparison_market_b",
            )
            st.caption(f"Source B: {directory_b}")

        path_a = [Path(market_a)]
        path_b = [Path(market_b)]

        submitted = st.form_submit_button(
            "Start comparison",
            type="primary",
            width="content",
        )


    if submitted:
        st.session_state.comparison_pair = (
            market_a,
            market_b,
        )

    if st.session_state.comparison_pair is None:
        st.info("Choose Run A and Run B, then click Start comparison.")
        return


    analyzers_a, results_a, frame_a, errors_a = load_all_markets(path_a, initial_balance)
    analyzers_b, results_b, frame_b, errors_b = load_all_markets(path_b, initial_balance)



    render_errors("Run A", errors_a)
    render_errors("Run B", errors_b)

    market_a_name = list(results_a)[0]
    # print("market_a_name:")
    # print(market_a_name)

    market_b_name = list(results_b)[0]
    # print("market_b_name:")
    # print(market_b_name)

    analyzer_a = analyzers_a[market_a_name]
    analyzer_b = analyzers_b[market_b_name]
    record_a = selected_record(frame_a, market_a_name)
    record_b = selected_record(frame_b, market_b_name)

    comparator = RunComparator(
        analyzer_a=analyzer_a,
        analyzer_b=analyzer_b,
        record_a=record_a,
        record_b=record_b,
        name_a=market_a_name,
        name_b=market_b_name,
    )


    bar = st.progress(0, text="Preparing summary")
    
    summary_tab, market_tab, replays_tab = st.tabs(
        ["Summary", "Market data", "Replays"]
    )

    with summary_tab:
        render_summary(comparator)


    bar.progress(1/3, text="Preparing market data...")
    with market_tab:
        midpoint_figure = build_midpoint_comparison_figure(comparator)
        if not midpoint_figure.data:
            st.info("No midpoint history is available for either run.")
        else:
            st.plotly_chart(
                midpoint_figure,
                width="stretch",
                config={"scrollZoom": True, "displaylogo": False},
                key="comparison_midpoint_chart",
            )

    bar.progress(2/3, text="Preparing replay graphs...")
    with replays_tab:
        render_replays(comparator)

    bar.progress(3/3, text="Loading complete")
    bar.empty()
            


if __name__ == "__main__":
    main()