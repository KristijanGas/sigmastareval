from __future__ import annotations

import math
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluator.passive_dashboard_store import (
    DEFAULT_CAPACITY,
    DEFAULT_CONTROL_NAME,
    DEFAULT_SAMPLES_NAME,
    DashboardSession,
    PassiveDashboardStore,
)
from ui.passive_trading.live_plot_component import render_live_plots


RUNTIME_DIR = REPO_ROOT / "runtime"
ENGINE_PATH = REPO_ROOT / "evaluator" / "passive_trading_engine.py"
REFRESH_SECONDS = 1.0
MAX_CHART_POINTS = 40_000


# These values are tiny and stay in Streamlit session state. The actual plotted
# history lives in the browser-side Plotly component; unlike the old version,
# Python no longer keeps/concatenates a growing Pandas DataFrame every second.
_CHART_STATE_KEY = "passive_dashboard_chart_state"
_FORCE_BOOTSTRAP_KEY = "passive_dashboard_force_chart_bootstrap"


def _attach_store() -> PassiveDashboardStore | None:
    return PassiveDashboardStore.attach_or_none(
        control_name=DEFAULT_CONTROL_NAME,
        samples_name=DEFAULT_SAMPLES_NAME,
    )


def _get_current_session() -> DashboardSession | None:
    store = _attach_store()
    if store is None:
        return None
    try:
        return store.get_session()
    finally:
        store.close()


def _start_engine(
    *,
    bot_path: str,
    market_slug: str,
    market_binance: str,
    market_type: str,
    starting_cash: float,
) -> int:
    existing = _attach_store()
    if existing is not None:
        try:
            active_session = existing.get_fresh_active_session(stale_after_seconds=8.0)
            if active_session is not None:
                raise RuntimeError(
                    f"Passive session {active_session.id} is already {active_session.status}."
                )
        finally:
            existing.close()

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    session_id = int(time.time_ns() // 1_000)
    log_path = RUNTIME_DIR / f"passive_trading_session_{session_id}.log"

    # Streamlit creates the blocks first so the new process can attach to a
    # fully initialized session immediately.
    store = PassiveDashboardStore.create_session(
        bot_path=bot_path,
        market_slug=market_slug,
        market_binance=market_binance,
        market_type=market_type,
        session_id=session_id,
        log_path=str(log_path),
        capacity=DEFAULT_CAPACITY,
        control_name=DEFAULT_CONTROL_NAME,
        samples_name=DEFAULT_SAMPLES_NAME,
    )

    command = [
        sys.executable,
        str(ENGINE_PATH),
        bot_path,
        market_slug,
        market_binance,
        market_type,
        "--dashboard-control-name",
        DEFAULT_CONTROL_NAME,
        "--dashboard-samples-name",
        DEFAULT_SAMPLES_NAME,
        "--session-id",
        str(session_id),
        "--starting-cash",
        str(starting_cash),
    ]

    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
    except Exception as exc:
        store.finish_session(
            session_id,
            status="failed",
            error=f"Could not start engine: {type(exc).__name__}: {exc}",
        )
        store.close()
        raise

    store.close()
    return session_id


def _request_stop(session_id: int) -> None:
    store = _attach_store()
    if store is None:
        return
    try:
        store.request_stop(session_id)
    finally:
        store.close()


def _status_label(session: DashboardSession) -> str:
    if session.status in {"starting", "running", "stopping"} and not PassiveDashboardStore.is_fresh(session, 8.0):
        return "stale / process may have exited"
    return session.status


def _read_log_tail(session: DashboardSession, max_lines: int = 80) -> str | None:
    if not session.log_path:
        return None
    path = Path(session.log_path)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:])
    except OSError:
        return None


def _render_session_header(
    session: DashboardSession,
    *,
    sample_count: int,
    latest_timestamp: float | None,
) -> None:
    cols = st.columns(5)
    cols[0].metric("Status", _status_label(session))
    cols[1].metric("Session", str(session.id))
    cols[2].metric("Current market", session.current_market_name or "Waiting...")
    cols[3].metric("Samples", f"{sample_count:,}")

    elapsed_end = latest_timestamp if latest_timestamp is not None else time.time()
    if session.stopped_at is not None:
        elapsed_end = min(float(elapsed_end), session.stopped_at)
    elapsed_seconds = max(0.0, float(elapsed_end) - session.started_at)
    hours, remainder = divmod(int(elapsed_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    cols[4].metric("Elapsed", f"{hours:02d}:{minutes:02d}:{seconds:02d}")


def _chart_state_for(session_id: int) -> dict[str, int]:
    state = st.session_state.get(_CHART_STATE_KEY)
    if not isinstance(state, dict) or state.get("session_id") != session_id:
        state = {
            "session_id": session_id,
            "last_read_id": 0,
            "sample_step": 1,
        }
        st.session_state[_CHART_STATE_KEY] = state
    return state


def _read_chart_update(
    store: PassiveDashboardStore,
    session: DashboardSession,
    *,
    force_bootstrap: bool,
) -> tuple[list[dict], bool, int, dict | None]:
    """Read either a full downsampled snapshot or only newly plottable rows.

    The downsampling step is aligned to record IDs. It only changes when the
    total number of samples crosses another MAX_CHART_POINTS boundary, so most
    refreshes are tiny ``Plotly.extendTraces`` updates. When the step changes,
    the component receives a replacement snapshot and restores any user zoom.
    """
    chart_state = _chart_state_for(session.id)
    write_count = store.get_write_count(session.id)
    sample_step = max(1, math.ceil(write_count / MAX_CHART_POINTS))

    reset = (
        force_bootstrap
        or chart_state["last_read_id"] == 0
        or chart_state["sample_step"] != sample_step
    )

    after_id = 0 if reset else int(chart_state["last_read_id"])
    rows = store.get_samples_since(
        session.id,
        after_id=after_id,
        step=sample_step,
    )

    # Advance by the raw write count, not the final plotted ID. With step > 1
    # there can be unsampled IDs at the end and we should not reconsider them
    # on every subsequent refresh.
    chart_state["last_read_id"] = write_count
    chart_state["sample_step"] = sample_step
    st.session_state[_CHART_STATE_KEY] = chart_state

    latest = store.get_latest_sample(session.id)
    return rows, reset, write_count, latest


def _render_live_dashboard(session_id: int) -> None:
    store = _attach_store()
    if store is None:
        st.warning("No shared-memory passive dashboard is available.")
        return

    try:
        session = store.get_session(session_id)
        if session is None:
            st.warning("The selected passive session is no longer available in shared memory.")
            return

        force_bootstrap = bool(st.session_state.pop(_FORCE_BOOTSTRAP_KEY, False))
        rows, reset, sample_count, latest = _read_chart_update(
            store,
            session,
            force_bootstrap=force_bootstrap,
        )
    finally:
        store.close()

    latest_timestamp = None if latest is None else latest.get("timestamp")
    _render_session_header(
        session,
        sample_count=sample_count,
        latest_timestamp=latest_timestamp,
    )

    if latest is None:
        if session.status == "failed":
            st.error(session.error or "Passive trading failed before the first dashboard sample.")
        else:
            st.info("Waiting for the first live sample...")
        log_tail = _read_log_tail(session)
        if log_tail:
            with st.expander("Engine log"):
                st.code(log_tail)
        return

    stats = st.columns(4)
    stats[0].metric("Cash", f"{latest['cash']:.4f}" if latest.get("cash") is not None else "—")
    stats[1].metric("UP shares", f"{latest['up_shares']:.4f}" if latest.get("up_shares") is not None else "—")
    stats[2].metric("DOWN shares", f"{latest['down_shares']:.4f}" if latest.get("down_shares") is not None else "—")
    stats[3].metric("Net worth", f"{latest['net']:.4f}" if latest.get("net") is not None else "—")

    render_live_plots(
        session_id=session.id,
        market_binance=session.market_binance,
        rows=rows,
        started_at=session.started_at,
        reset=reset,
    )

    if sample_count > MAX_CHART_POINTS:
        step = max(1, math.ceil(sample_count / MAX_CHART_POINTS))
        st.caption(
            f"Live session has {sample_count:,} samples. The charts keep about "
            f"{MAX_CHART_POINTS:,} points by plotting one of every {step} samples; "
            "the underlying shared-memory session remains at full sampling resolution."
        )

    if session.status == "failed" or _status_label(session).startswith("stale"):
        if session.error:
            st.error(session.error)
        log_tail = _read_log_tail(session)
        if log_tail:
            with st.expander("Engine log"):
                st.code(log_tail)


_live_fragment = st.fragment(run_every=REFRESH_SECONDS)(_render_live_dashboard)


def render_live_passive_trading_page() -> None:
    st.title("Live Passive Trading")
    st.caption(
        "The passive engine runs in a separate Python process and publishes dashboard telemetry through multiprocessing.shared_memory. The live Plotly component appends new points in-place, so chart interaction does not block trading or recreate the graphs every second."
    )

    current_session = _get_current_session()
    active = current_session is not None and PassiveDashboardStore.is_fresh(current_session, 8.0)

    with st.expander("Start passive simulation", expanded=not active):
        with st.form("start-passive-simulation"):
            bot_path = st.text_input("Bot path", value="bot/k_strategy.py")
            market_slug = st.text_input("Market slug", value="bitcoin-up-or-down")
            market_binance = st.text_input("Binance symbol", value="BTCUSDT")
            market_type = st.selectbox("Market type", ["hourly", "5m"])
            starting_cash = st.number_input("Starting cash", min_value=0.0, value=100.0, step=10.0)
            start_clicked = st.form_submit_button(
                "Start passive trading",
                type="primary",
                disabled=active,
            )

        if start_clicked:
            if not bot_path.strip() or not market_slug.strip() or not market_binance.strip():
                st.error("Bot path, market slug, and Binance symbol are required.")
            else:
                try:
                    session_id = _start_engine(
                        bot_path=bot_path.strip(),
                        market_slug=market_slug.strip(),
                        market_binance=market_binance.strip(),
                        market_type=market_type,
                        starting_cash=float(starting_cash),
                    )
                    st.session_state["passive_dashboard_selected_session"] = session_id
                    st.session_state.pop(_CHART_STATE_KEY, None)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    current_session = _get_current_session()
    if current_session is None:
        st.info("No passive shared-memory session yet. Start one above.")
        return

    control_left, control_right = st.columns([4, 1])
    with control_left:
        st.text_input(
            "Session",
            value=f"#{current_session.id} · {current_session.market_slug} · {current_session.market_type} · {current_session.status}",
            disabled=True,
        )

    with control_right:
        can_stop = (
            current_session.status in {"starting", "running"}
            and PassiveDashboardStore.is_fresh(current_session, stale_after_seconds=8.0)
        )
        if st.button("Stop", disabled=not can_stop, width="stretch"):
            _request_stop(current_session.id)
            st.rerun()

    if current_session.status in {"stopped", "failed"}:
        st.caption(
            "Shared memory keeps only the current/most recent live session. Starting a new run replaces this buffer; durable evaluation history should continue to come from your normal evaluator output files."
        )

    # This outer function runs on a normal page/full rerun but not on the
    # fragment's one-second auto-reruns. Force one full component snapshot here
    # so navigating away and back cannot leave a newly mounted browser component
    # with only incremental points.
    st.session_state[_FORCE_BOOTSTRAP_KEY] = True
    _live_fragment(current_session.id)


render_live_passive_trading_page()