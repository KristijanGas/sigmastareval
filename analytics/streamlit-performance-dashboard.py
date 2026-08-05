import hashlib
import math
from dataclasses import asdict, is_dataclass
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    
REPO_ROOT = Path(__file__).resolve().parents[1]

from statistics import mean
from typing import Any, Callable, Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from analytics.aggregate_analyzer import AggregateAnalyzer
from analytics.graph_drawer import draw_graph
from analytics.performance_analyzer import PerformanceAnalyzer


APP_TITLE = "Bot Performance Analysis"
DEFAULT_ANALYSIS_DIRECTORY = "tmp/bitcoin-up-or-down"

# To install required modules: python -m pip install -r requirements-streamlit.txt
# Run command: streamlit run analytics/streamlit-performance-dashboard.py


def find_analysis_files(directory: Path) -> list[Path]:
   paths = []
   for path in Path(directory).glob("*.analysis.json"):
      paths.append(path)
   return paths

#Load and analyze one market. modified_time_ns is used as a part of the cache key
#  so editing the JSON invalidates only that market's cached analysis.
@st.cache_resource(show_spinner=False)
def load_market_analyzer(path_string: str, initial_balance: float, modified_time_ns: int,
) -> tuple[PerformanceAnalyzer, Any]:

   del modified_time_ns
   analyzer = PerformanceAnalyzer(initial_balance=initial_balance)
   analyzer.analytics_path = Path(path_string)
   result = analyzer.analyze()
   return analyzer, result


def market_record(path: Path, result: Any) -> dict[str, Any]:

   return {
      "market": result.market_name,
      "path": str(path),
      "final_cash": result.final_cash,
      "pnl": result.pnl,
      "roi": result.roi,
      "max_drawdown": result.max_drawdown,
      "trade_count": result.trade_count,
      "idle_time": result.idle_time,
      "profit_factor": result.profit_factor,
      "total_fees": result.total_fees_paid,
      "win_rate": result.winrate,
      "average_trade_profit": result.avg_trade_profit,
      "median_trade_profit": result.median_trade_profit,
      "largest_gain": result.largest_gain,
      "largest_loss": result.largest_loss,
      "time_before_expiration_min": result.time_before_exp_min,
      "fees_to_balance": result.fees_to_balance,
      "profit_lost_to_fees": result.profit_lost_to_fees,
      "fee_efficiency": result.fee_efficiency,
      "turnover": result.turnover,
      "traded_volume": result.total_traded_volume,
   }


def load_all_markets(paths: list[Path], initial_balance: float
) -> tuple[dict[str, PerformanceAnalyzer], dict[str, Any], pd.DataFrame, list[dict[str, str]]]:
   analyzers: dict[str, PerformanceAnalyzer] = {}
   results: dict[str, Any] = {}
   records: list[dict[str, Any]] = []
   errors: list[dict[str, str]] = []

   progress = st.progress(0, text="Analyzing markets...") if paths else None

   for index, path in enumerate(paths, start=1):
      try:
         analyzer, result = load_market_analyzer(
               str(path.resolve()),
               float(initial_balance),
               path.stat().st_mtime_ns,
         )
         market_name = result.market_name
         analyzers[market_name] = analyzer
         results[market_name] = result
         records.append(market_record(path, result))
      except Exception as exc:  # one malformed analysis file should not stop the app
         errors.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})

      if progress is not None:
         progress.progress(index / len(paths), text=f"Analyzed {index}/{len(paths)} markets")

   if progress is not None:
      progress.empty()

   frame = pd.DataFrame.from_records(records)
   if not frame.empty:
      frame = frame.sort_values("market", kind="stable").reset_index(drop=True)

   return analyzers, results, frame, errors





def build_aggregate_analyzer(results: dict[str, Any]) -> AggregateAnalyzer:
   aggregate = AggregateAnalyzer()
   for result in results.values():
      aggregate.add_result(result)
   return aggregate



def metric_card(label: str, value: Any, *, kind: str = "number", help_text: str | None = None) -> None:
   st.metric(label, display_value(value, kind=kind), help=help_text, border=True)

def display_value(value: Any, *, kind: str = "number") -> str:
   value = finite_or_none(value)
   if value is None:
      return "—"
   if kind == "currency":
      return f"${value:,.2f}"
   if kind == "percent":
      return f"{value:.2%}"
   if kind == "ratio":
      return f"{value:.2f}"
   if kind == "integer":
      return f"{int(value):,}"
   return f"{value:,.2f}"

#Return a finite numeric value, otherwise None
def finite_or_none(value):
   if value is None:
      return None
   if isinstance(value, (int, float)):
      return value if math.isfinite(value) else None
   return None

def safe_mean(values):
   clean = [float(value) for value in values if finite_or_none(value) is not None]
   return mean(clean) if clean else None


def filtered_market_frame(frame: pd.DataFrame, *, key_prefix: str) -> pd.DataFrame:
   with st.expander("Filters", expanded=False):
      first, second, third = st.columns(3)
      with first:
         only_traded = st.checkbox("Only markets with trades", value=False, key=f"{key_prefix}_only_traded")
      with second:
         outcome = st.selectbox("Outcome", ["All", "Profitable", "Losing", "Flat"], key=f"{key_prefix}_outcome")
      with third:
         minimum_trades = st.number_input("Minimum trades", min_value=0, value=0, step=1, key=f"{key_prefix}_minimum_trades")

      roi_min = float(frame["roi"].min()) if not frame.empty else -1.0
      roi_max = float(frame["roi"].max()) if not frame.empty else 1.0
      selected_roi = st.slider(
         "ROI range",
         min_value=roi_min,
         max_value=roi_max,
         value=(roi_min, roi_max),
         key=f"{key_prefix}_roi_range",
      ) if roi_min < roi_max else (roi_min, roi_max)

   filtered = frame.copy()
   if only_traded:
      filtered = filtered[filtered["trade_count"] > 0]
   filtered = filtered[filtered["trade_count"] >= minimum_trades]
   filtered = filtered[filtered["roi"].between(*selected_roi)]

   if outcome == "Profitable":
      filtered = filtered[filtered["pnl"] > 0]
   elif outcome == "Losing":
      filtered = filtered[filtered["pnl"] < 0]
   elif outcome == "Flat":
      filtered = filtered[filtered["pnl"] == 0]

   return filtered.reset_index(drop=True)


def aggregate_metric_table(aggregate: AggregateAnalyzer) -> pd.DataFrame:
   rows = [
      {
         "Metric": "ROI",
         "Mean": aggregate.average_roi(),
         "Median": aggregate.median_roi(),
         "Std dev": aggregate.stdev_roi(),
         "Minimum": aggregate.min_roi(),
         "Maximum": aggregate.max_roi(),
         "Format": "percent",
      },
      {
         "Metric": "PnL",
         "Mean": aggregate.average_pnl(),
         "Median": aggregate.median_pnl(),
         "Std dev": aggregate.stdev_pnl(),
         "Minimum": aggregate.min_pnl(),
         "Maximum": aggregate.max_pnl(),
         "Format": "currency",
      },
      {
         "Metric": "Max drawdown",
         "Mean": aggregate.average_max_drawdown(),
         "Median": aggregate.median_max_drawdown(),
         "Std dev": aggregate.stdev_max_drawdown(),
         "Minimum": aggregate.minimal_max_drawdown(),
         "Maximum": aggregate.worst_drawdown(),
         "Format": "percent",
      },
      {
         "Metric": "Trades",
         "Mean": aggregate.average_trade_count(),
         "Median": aggregate.median_trade_count(),
         "Std dev": aggregate.stdev_trade_count(),
         "Minimum": aggregate.min_trade_count(),
         "Maximum": aggregate.max_trade_count(),
         "Format": "number",
      },
      {
         "Metric": "Idle time",
         "Mean": aggregate.average_idle_time(),
         "Median": aggregate.median_idle_time(),
         "Std dev": aggregate.stdev_idle_time(),
         "Minimum": aggregate.min_idle_time(),
         "Maximum": aggregate.max_idle_time(),
         "Format": "percent",
      },
      {
         "Metric": "Profit factor",
         "Mean": aggregate.average_profit_factor(),
         "Median": aggregate.median_profit_factor(),
         "Std dev": aggregate.stdev_profit_factor(),
         "Minimum": aggregate.min_profit_factor(),
         "Maximum": aggregate.max_profit_factor(),
         "Format": "ratio",
      },
   ]

   table = pd.DataFrame(rows)
   for column in ["Mean", "Median", "Std dev", "Minimum", "Maximum"]:
      table[column] = [
         display_value(value, kind=format_kind)
         for value, format_kind in zip(table[column], table["Format"])
      ]
   return table.drop(columns="Format")



def render_aggregate(frame: pd.DataFrame, results: dict[str, Any], initial_balance: float):
   aggregate = build_aggregate_analyzer(results)

   st.header("Aggregate analysis")

   total_fees = frame["total_fees"].sum()
   no_trade_rate = (frame["trade_count"] == 0).mean()
   first_row = st.columns(6)
   with first_row[0]:
      metric_card("Markets", len(frame), kind="integer")
   with first_row[1]:
      metric_card("Total PnL", aggregate.total_pnl(), kind="currency")
   with first_row[2]:
      metric_card("Geometric avg ROI", aggregate.average_roi(), kind="percent")
   with first_row[3]:
      metric_card("Profitable markets", aggregate.profitable_markets(), kind="percent")
   with first_row[4]:
      metric_card("Worst drawdown", aggregate.worst_drawdown(), kind="percent")
   with first_row[5]:
      metric_card("Total fees", total_fees, kind="currency")

   second_row = st.columns(5)
   with second_row[0]:
      metric_card("Median ROI", aggregate.median_roi(), kind="percent")
   with second_row[1]:
      metric_card("Median PnL", aggregate.median_pnl(), kind="currency")
   with second_row[2]:
      metric_card("Average trades", aggregate.average_trade_count())
   with second_row[3]:
      metric_card("Average win rate", safe_mean(frame["win_rate"]), kind="percent")
   with second_row[4]:
      metric_card("No-trade rate", no_trade_rate, kind="percent")

   
   # with third_row[0]:
   #    st.plotly_chart(
   #       gauge_chart(
   #          title="Profitable Markets", 
   #          value=(aggregate.profitable_markets()*100),
   #          minimum=0,
   #          maximum=100,
   #          suffix="%"),
            
   #       width="stretch",
   #       config={"displayModeBar": False})
      

   third_row = st.columns(2)
   with third_row[0]:
      profitable = int((frame["pnl"] > 0).sum())
      losing = int((frame["pnl"] < 0).sum())
      even = int((frame["pnl"] == 0).sum())
      st.plotly_chart(
         pie_chart(
            title="Market Outcomes",
            labels=["Profitable", "Losing", "Even"],
            values=[profitable, losing, even]
         )
      )

   with third_row[1]:
      st.plotly_chart(distribution_histogram(values=frame["roi"]*100, title="ROI Distribution"))
      
      
   overview_tab, markets_tab, daily_tab, diagnostics_tab= st.tabs(
      ["Overview", "Markets", "Daily", "Diagnostics"]
   )

   with overview_tab:
      display_mode = st.radio(
         "Main view",
         ["Distribution curve", "Market dataframe"],
         horizontal=True,
         label_visibility="collapsed",
      )
      if display_mode == "Distribution curve":
         st.plotly_chart(
               final_cash_distribution_figure(frame, initial_balance),
               width="stretch",
         )
      else:
         render_market_table(filtered_market_frame(frame, key_prefix="overview"), key_prefix="overview")

      st.subheader("Metric distributions")
      st.dataframe(
         aggregate_metric_table(aggregate),
         hide_index=True,
         width="stretch",
      )

   with markets_tab:
      filtered = filtered_market_frame(frame, key_prefix="markets")
      render_market_table(filtered, key_prefix="markets")

   with daily_tab:
      daily = daily_summary_frame(aggregate)
      if daily.empty:
         st.info("Daily summaries are unavailable. Check market filename date parsing.")
      else:
         daily = daily.sort_values("market_date")
         chart = make_subplots(specs=[[{"secondary_y": True}]])
         chart.add_trace(
               go.Bar(
                  x=daily["market_date"],
                  y=daily["total_pnl"],
                  name="Total PnL",
               ),
               secondary_y=False,
         )
         chart.add_trace(
               go.Scatter(
                  x=daily["market_date"],
                  y=daily["profitable_market_rate"],
                  mode="lines+markers",
                  name="Profitable rate",
               ),
               secondary_y=True,
         )
         chart.update_yaxes(title_text="Total PnL", secondary_y=False)
         chart.update_yaxes(title_text="Profitable rate", tickformat=".0%", secondary_y=True)
         chart.update_layout(legend_orientation="h", margin=dict(l=20, r=20, t=30, b=20))
         st.plotly_chart(chart, width="stretch")
         st.dataframe(
               daily,
               hide_index=True,
               width="stretch",
               column_config={
                  "market_date": st.column_config.DateColumn("Date"),
                  "total_pnl": st.column_config.NumberColumn("Total PnL", format="$%.2f"),
                  "average_pnl": st.column_config.NumberColumn("Average PnL", format="$%.2f"),
                  "average_roi": st.column_config.NumberColumn("Average ROI", format="percent"),
                  "median_roi": st.column_config.NumberColumn("Median ROI", format="percent"),
                  "profitable_market_rate": st.column_config.NumberColumn("Profitable", format="percent"),
                  "average_max_drawdown": st.column_config.NumberColumn("Average DD", format="percent"),
               },
         )

   with diagnostics_tab:
      x_metric = st.selectbox(
         "Horizontal metric",
         ["total_fees", "trade_count", "turnover", "max_drawdown", "idle_time"],
         format_func=lambda value: value.replace("_", " ").title(),
      )
      y_metric = st.selectbox(
         "Vertical metric",
         ["pnl", "roi", "win_rate", "average_trade_profit", "fee_efficiency"],
         format_func=lambda value: value.replace("_", " ").title(),
      )
      if x_metric == "trade_count":
         scatter_data = frame[["market", x_metric, y_metric]].dropna()
      else:
         scatter_data = frame[["market", x_metric, y_metric, "trade_count"]].dropna()

      if scatter_data.empty:
         st.info("No finite values are available for this metric pair.")
      else:
         figure = px.scatter(
               scatter_data,
               x=x_metric,
               y=y_metric,
               hover_name="market",
               size="trade_count",
               title=f"{y_metric.replace('_', ' ').title()} vs {x_metric.replace('_', ' ').title()}",
         )
         st.plotly_chart(figure, width="stretch")


def daily_summary_frame(aggregate: AggregateAnalyzer) -> pd.DataFrame:
   records = []
   for summary in safe_call(aggregate.get_daily_summaries) or []:
      record = asdict(summary) if is_dataclass(summary) else vars(summary)
      records.append(record)
   return pd.DataFrame(records)

# Call a metric function without letting one bad metric break the dashboard
def safe_call(function: Callable):
   try:
      return function()
   except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
      return None

# Support both dict-like and attribute-style Streamlit selection events
def selection_rows(event: Any) -> list[int]:
   
   if event is None:
      return []
   try:
      return list(event.selection.rows)
   except (AttributeError, TypeError):
      pass
   try:
      return list(event["selection"]["rows"])
   except (KeyError, TypeError):
      return []



def render_market_table(frame: pd.DataFrame, *, key_prefix: str) -> None:
   visible_columns = [
      "market",
      "final_cash",
      "pnl",
      "roi",
      "max_drawdown",
      "trade_count",
      "win_rate",
      "profit_factor",
      "total_fees",
      "turnover",
      "idle_time",
   ]

   table = frame[visible_columns].copy()
   event_key = f"{key_prefix}_market_table"
   market_names = table["market"].tolist()

   def handle_selection() -> None:
      event = st.session_state.get(event_key)
      rows = selection_rows(event)

      if not rows:
         return

      selected_row = rows[0]

      if selected_row >= len(market_names):
         return

      st.session_state.selected_market = market_names[selected_row]
      st.session_state.active_section = "Single market"

   st.caption("Select a row to open that market in the Single market section.")

   st.dataframe(
      table,
      key=event_key,
      on_select=handle_selection,
      selection_mode="single-row",
      hide_index=True,
      width="stretch",
      height=520,
      column_config={
         "market": st.column_config.TextColumn(
               "Market",
               width="large",
         ),
         "final_cash": st.column_config.NumberColumn(
               "Final cash",
               format="$%.2f",
         ),
         "pnl": st.column_config.NumberColumn(
               "PnL",
               format="$%.2f",
         ),
         "roi": st.column_config.NumberColumn(
               "ROI",
               format="percent",
         ),
         "max_drawdown": st.column_config.NumberColumn(
               "Max DD",
               format="percent",
         ),
         "trade_count": st.column_config.NumberColumn(
               "Trades",
               format="%d",
         ),
         "win_rate": st.column_config.NumberColumn(
               "Win rate",
               format="percent",
         ),
         "profit_factor": st.column_config.NumberColumn(
               "Profit factor",
               format="%.2f",
         ),
         "total_fees": st.column_config.NumberColumn(
               "Fees",
               format="$%.2f",
         ),
         "turnover": st.column_config.NumberColumn(
               "Turnover",
               format="%.2f",
         ),
         "idle_time": st.column_config.NumberColumn(
               "Idle time",
               format="percent",
         ),
      },
   )

def final_cash_distribution_figure(frame: pd.DataFrame, initial_balance: float) -> go.Figure:
   ordered = frame.sort_values("final_cash").reset_index(drop=True).copy()
   if len(ordered) == 1:
      ordered["percentile"] = 100.0
   else:
      ordered["percentile"] = ordered.index / (len(ordered) - 1) * 100.0

   figure = make_subplots(specs=[[{"secondary_y": True}]])
   figure.add_trace(
      go.Scatter(
         x=ordered["percentile"],
         y=ordered["final_cash"],
         customdata=ordered[["market", "pnl", "roi"]],
         mode="lines+markers",
         name="Final cash",
         hovertemplate=(
               "%{customdata[0]}<br>"
               "Percentile: %{x:.1f}%<br>"
               "Final cash: $%{y:.2f}<br>"
               "PnL: $%{customdata[1]:.2f}<br>"
               "ROI: %{customdata[2]:.2%}<extra></extra>"
         ),
      ),
      secondary_y=False,
   )
   figure.add_trace(
      go.Scatter(
         x=ordered["percentile"],
         y=ordered["total_fees"],
         customdata=ordered[["market"]],
         mode="lines",
         name="Fees",
         opacity=0.65,
         hovertemplate="%{customdata[0]}<br>Fees: $%{y:.2f}<extra></extra>",
         line=dict(color="#9E1111")
      ),
      secondary_y=True,
   )
   figure.add_hline(
      y=initial_balance,
      line_dash="dash",
      annotation_text="Initial balance",
      secondary_y=False,
   )
   figure.update_layout(
      title="Final cash distribution",
      xaxis_title="Market percentile",
      hovermode="x unified",
      legend_orientation="h",
      legend_y=1.10,
      margin=dict(l=20, r=20, t=70, b=20),
   )
   figure.update_yaxes(title_text="Final cash", secondary_y=False)
   figure.update_yaxes(title_text="Total fees", secondary_y=True)
   return figure



def render_single_market(
   analyzers: dict[str, PerformanceAnalyzer],
   results: dict[str, Any],
   frame: pd.DataFrame,
) -> None:
   st.header("Single-market analysis")

   market_names = frame["market"].tolist()
   if not market_names:
      st.info("No markets are available.")
      return

   if st.session_state.get("selected_market") not in market_names:
      st.session_state.selected_market = market_names[0]

   selected_market = st.selectbox(
      "Market",
      market_names,
      key="selected_market",
   )
   analyzer = analyzers[selected_market]
   result = results[selected_market]
   record = frame.loc[frame["market"] == selected_market].iloc[0]

   first_row = st.columns(6)
   with first_row[0]:
      metric_card("Final cash", result.final_cash, kind="currency")
   with first_row[1]:
      metric_card("PnL", result.pnl, kind="currency")
   with first_row[2]:
      metric_card("ROI", result.roi, kind="percent")
   with first_row[3]:
      metric_card("Max drawdown", result.max_drawdown, kind="percent")
   with first_row[4]:
      metric_card("Trades", result.trade_count, kind="integer")
   with first_row[5]:
      metric_card("Fees", result.total_fees_paid, kind="currency")

   overview_tab, replay_tab, equity_tab, trades_tab, = st.tabs(
      ["Overview", "Replay", "Equity & risk", "Trades",]
   )

   with overview_tab:
      left, middle, right = st.columns(3)
      with left:
         st.subheader("Trade performance")
         metric_card("Win rate", record["win_rate"], kind="percent")
         metric_card("Average trade PnL", record["average_trade_profit"], kind="currency")
         metric_card("Median trade PnL", record["median_trade_profit"], kind="currency")
         metric_card("Largest gain", record["largest_gain"], kind="currency")
         metric_card("Largest loss", record["largest_loss"], kind="currency")
      with middle:
         st.subheader("Fees and activity")
         metric_card("Profit factor", record["profit_factor"], kind="ratio")
         metric_card("Turnover", record["turnover"], kind="ratio")
         metric_card("Traded volume", record["traded_volume"], kind="currency")
         metric_card("Fee efficiency", record["fee_efficiency"], kind="ratio")
         metric_card("Fees / balance", record["fees_to_balance"], kind="percent")
      with right:
         st.subheader("Timing and exposure")
         metric_card("Idle time", record["idle_time"], kind="percent")
         metric_card("Avg entry before expiry", record["time_before_expiration_min"], kind="number")
         #metric_card("Premature exit rate", record["premature_exit_rate"], kind="percent")
         #metric_card("False entry rate", record["false_entry_rate"], kind="percent")

   with replay_tab:
      render_replay_image(analyzer, selected_market)

   with equity_tab:
      equity = equity_frame(analyzer)
      if equity.empty:
         st.info("No equity points are available.")
      else:
         figure = go.Figure()
         figure.add_trace(go.Scatter(x=equity["time"], y=equity["equity"], name="Equity"))
         figure.add_trace(go.Scatter(x=equity["time"], y=equity["cash"], name="Cash"))
         figure.add_trace(
               go.Scatter(x=equity["time"], y=equity["position_value"], name="Position value")
         )
         figure.update_layout(
               title="Equity breakdown",
               hovermode="x unified",
               legend_orientation="h",
               margin=dict(l=20, r=20, t=60, b=20),
         )
         st.plotly_chart(figure, width="stretch")

         drawdown_figure = go.Figure(
               go.Scatter(
                  x=equity["time"],
                  y=equity["drawdown"],
                  fill="tozeroy",
                  name="Drawdown",
               )
         )
         drawdown_figure.update_yaxes(tickformat=".0%")
         drawdown_figure.update_layout(
               title="Drawdown over time",
               margin=dict(l=20, r=20, t=60, b=20),
         )
         st.plotly_chart(drawdown_figure, width="stretch")

   with trades_tab:
      trades = closed_trades_frame(analyzer)
      if trades.empty:
         st.info("This market has no closed trades.")
      else:
         bar = px.bar(
               trades.reset_index(names="trade_number"),
               x="trade_number",
               y="profit",
               hover_data=["asset_id", "quantity", "entry_price", "exit_price", "fees", "closed_by"],
               title="PnL by closed trade",
         )
         bar.add_hline(y=0)
         st.plotly_chart(bar, width="stretch")

         table_columns = [
               column
               for column in [
                  "asset_id",
                  "entry_time",
                  "exit_time",
                  "quantity",
                  "entry_price",
                  "exit_price",
                  "gross_profit",
                  "fees",
                  "profit",
                  "closed_by",
               ]
               if column in trades.columns
         ]
         st.dataframe(
               trades[table_columns],
               hide_index=True,
               width="stretch",
               column_config={
                  "entry_price": st.column_config.NumberColumn(format="%.4f"),
                  "exit_price": st.column_config.NumberColumn(format="%.4f"),
                  "gross_profit": st.column_config.NumberColumn(format="$%.2f"),
                  "fees": st.column_config.NumberColumn(format="$%.2f"),
                  "profit": st.column_config.NumberColumn(format="$%.2f"),
               },
         )

def closed_trades_frame(analyzer: PerformanceAnalyzer) -> pd.DataFrame:
   frame = pd.DataFrame(analyzer.closed_trades)
   if frame.empty:
      return frame
   if "entry_timestamp" in frame:
      frame["entry_time"] = pd.to_datetime(frame["entry_timestamp"], unit="ms", errors="coerce")
   if "exit_timestamp" in frame:
      frame["exit_time"] = pd.to_datetime(frame["exit_timestamp"], unit="ms", errors="coerce")
   return frame


def equity_frame(analyzer: PerformanceAnalyzer) -> pd.DataFrame:
   rows = [
      {
         "timestamp": point.timestamp,
         "cash": point.cash,
         "position_value": point.position_value,
         "equity": point.equity,
      }
      for point in analyzer.equity_curve
   ]
   frame = pd.DataFrame(rows)
   if frame.empty:
      return frame
   frame["time"] = pd.to_datetime(frame["timestamp"], unit="ms")
   peak = frame["equity"].cummax()
   frame["drawdown"] = (peak - frame["equity"]) / peak.replace(0, pd.NA)
   return frame



def render_replay_image(analyzer: PerformanceAnalyzer, market_name: str) -> None:
   path = Path(analyzer.analytics_path)
   cache_key = hashlib.sha1(
      f"{path.resolve()}:{path.stat().st_mtime_ns}".encode("utf-8")).hexdigest()[:16]
   output_path = Path(".streamlit_cache") / f"replay_{cache_key}.png"

   try:
      if not output_path.exists():
         draw_graph(analyzer.data, output_path=output_path, show=False)
      st.image(str(output_path), caption=market_name, width="stretch")
   except Exception as exc:
      st.error(f"Replay graph failed: {type(exc).__name__}: {exc}")


def gauge_chart(
   title: str,
   value: float,
   minimum: float,
   maximum: float,
   color: str = "#2E75B6",
   suffix: str = "",
) -> go.Figure:
   value = max(minimum, min(value, maximum))

   figure = go.Figure(
      go.Indicator(
         mode="gauge+number",
         value=value,
         title={
               "text": title,
               "font": {"size": 20},
         },
         number={
               "suffix": suffix,
               "font": {"size": 26},
         },
         gauge={
               "axis": {
                  "range": [minimum, maximum],
                  "tickwidth": 1,
               },
               "bar": {
                  "color": color,
                  "thickness": 0.7,
               },
               "bgcolor": "white",
               "borderwidth": 0,
               "steps": [
                  {
                     "range": [minimum, maximum],
                     "color": "#E6E6E6",
                  }
               ],
         },
      )
   )

   figure.update_layout(
      height=280,
      margin=dict(l=25, r=25, t=55, b=10),
   )

   return figure

def pie_chart(title: str, labels: list[str], values: list[float]) -> go.Figure:
   figure = go.Figure(
      go.Pie(
         labels=labels,
         values=values,
         marker={"colors": ["#46783E", "#CF3D3D", "#3B3D66"]},
         hole=0.55,
         textinfo="label+percent",
         hovertemplate=(
               "%{label}<br>"
               "Markets: %{value}<br>"
               "Share: %{percent}"
               "<extra></extra>"
         ),
      )
   )

   figure.update_layout(
      title=title,
      height=300,
      showlegend=True,
      margin=dict(l=20, r=20, t=60, b=20),
   )

   return figure


def distribution_histogram(values, title) -> go.Figure:
   figure = go.Figure(
      go.Histogram(
         x=values,
         xbins=dict(start=-20,end=40,size=2),
         marker=dict(color="#3B3D66")
      )
   )

   figure.update_layout(
      title=title,
      height=300,
      margin=dict(l=20, r=20, t=60, b=20),
      bargap=0.05
   )
   return figure



def main() -> None:
   st.set_page_config(page_title=APP_TITLE, layout="wide")
   st.title(APP_TITLE)

   with st.sidebar:
      st.header("Data source")
      directory_text = st.text_input("Analysis directory", DEFAULT_ANALYSIS_DIRECTORY)
      initial_balance = st.number_input(
         "Initial balance",
         min_value=0.01,
         value=100.0,
         step=10.0,
      )
      if st.button("Refresh analyses", width="stretch"):
         load_market_analyzer.clear()
         st.rerun()

   directory = Path(directory_text).expanduser()
   if not directory.exists() or not directory.is_dir():
      st.error(f"Analysis directory does not exist: {directory}")
      st.stop()

   paths = find_analysis_files(directory)
   if not paths:
      st.warning(f"No *.analysis.json files found under {directory}")
      st.stop()

   analyzers, results, frame, errors = load_all_markets(paths, initial_balance)

   if errors:
      with st.expander(f"Skipped files ({len(errors)})", expanded=False):
         st.dataframe(pd.DataFrame(errors), hide_index=True, width="stretch")

   if frame.empty:
      st.error("No analysis files could be processed.")
      st.stop()

   if "active_section" not in st.session_state:
      st.session_state.active_section = "Aggregate"
   if "selected_market" not in st.session_state:   
      st.session_state.selected_market = frame.iloc[0]["market"]

   active_section = st.segmented_control(
      "Analysis section",
      ["Aggregate", "Single market"],
      key="active_section",
      label_visibility="collapsed",
   )

   if active_section == "Single market":
      render_single_market(analyzers, results, frame)
      pass
   else:
      render_aggregate(frame, results, initial_balance)

if __name__ == "__main__":
   main()


