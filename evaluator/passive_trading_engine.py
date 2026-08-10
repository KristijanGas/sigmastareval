from __future__ import annotations

import argparse
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from data.data_interface import parse_time_name_5m, parse_time_name_hourly
from data_provider.live_provider import live_provider
from evaluator.passive_dashboard_store import (
    DEFAULT_CAPACITY,
    DEFAULT_CONTROL_NAME,
    DEFAULT_SAMPLES_NAME,
    PassiveDashboardStore,
)
from evaluator.passive_market_simulator import passive_market_simulator
from evaluator.replay_engine import load_bot


class PassiveTradingEngine:
    def __init__(
        self,
        bot_path: str,
        market_slug: str,
        market_binance: str,
        market_type: str,
        *,
        dashboard_control_name: str = DEFAULT_CONTROL_NAME,
        dashboard_samples_name: str = DEFAULT_SAMPLES_NAME,
        dashboard_capacity: int = DEFAULT_CAPACITY,
        session_id: int | None = None,
        sample_interval_s: float = 0.25,
        starting_cash: float = 100.0,
    ):
        self.bot_path = bot_path
        self.bot = load_bot(bot_path)
        self.market_slug = market_slug
        self.market_binance = market_binance
        self.market_type = market_type
        self.sample_interval_s = sample_interval_s
        self.old_time_name = None

        self.stop_event = threading.Event()
        self.thread_error: str | None = None

        # When started from Streamlit, the page creates the shared-memory
        # session first and the engine attaches to it. Direct CLI launches can
        # create the segment themselves.
        if session_id is not None:
            self.dashboard_store = PassiveDashboardStore.attach(
                control_name=dashboard_control_name,
                samples_name=dashboard_samples_name,
            )
            if self.dashboard_store.get_session(session_id) is None:
                raise ValueError(f"Dashboard session {session_id} does not exist")
        else:
            existing = PassiveDashboardStore.attach_or_none(
                control_name=dashboard_control_name,
                samples_name=dashboard_samples_name,
            )
            if existing is not None:
                active = existing.get_fresh_active_session(stale_after_seconds=8.0)
                existing.close()
                if active is not None:
                    raise RuntimeError(
                        f"Passive session {active.id} is already {active.status}."
                    )
            self.dashboard_store = PassiveDashboardStore.create_session(
                bot_path=bot_path,
                market_slug=market_slug,
                market_binance=market_binance,
                market_type=market_type,
                capacity=dashboard_capacity,
                control_name=dashboard_control_name,
                samples_name=dashboard_samples_name,
            )
            session_id = self.dashboard_store.get_session().id

        self.session_id = int(session_id)
        self.market = passive_market_simulator(None, starting_cash, market_slug, self.bot)
        self.live_provider = live_provider(
            self.market_slug,
            self.market_binance,
            self.market_type,
            self.market,
        )

    def run_forever(self) -> None:
        failed = False
        try:
            self.dashboard_store.mark_running(self.session_id, os.getpid())
            self._start_threads()

            while not self.stop_event.wait(0.25):
                self.dashboard_store.heartbeat(self.session_id)
                if self.dashboard_store.stop_requested(self.session_id):
                    self.stop_event.set()

            if self.thread_error:
                failed = True
                raise RuntimeError(self.thread_error)

        except KeyboardInterrupt:
            self.stop_event.set()
        except Exception as exc:
            failed = True
            self.dashboard_store.finish_session(
                self.session_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        finally:
            if not failed:
                self.dashboard_store.finish_session(self.session_id, status="stopped")
            self.dashboard_store.close()

    def _start_threads(self) -> None:
        self.live_thread = threading.Thread(
            target=self._thread_guard,
            args=("live provider", self.live_provider.run),
            daemon=True,
            name="passive-live-provider",
        )
        self.live_thread.start()

        self._wait_for_metadata()
        if self.stop_event.is_set():
            return

        self.market.data_provider = self.live_provider

        self.market_thread = threading.Thread(
            target=self._thread_guard,
            args=("market simulator", self.market.run, self.market_type),
            daemon=True,
            name="passive-market-simulator",
        )
        self.market_thread.start()

        self.bot_thread = threading.Thread(
            target=self._thread_guard,
            args=("bot", self.run_bot),
            daemon=True,
            name="passive-bot",
        )
        self.bot_thread.start()

        self.dashboard_thread = threading.Thread(
            target=self._dashboard_sample_loop,
            daemon=True,
            name="passive-dashboard-sampler",
        )
        self.dashboard_thread.start()

    def _thread_guard(self, name: str, target, *args) -> None:
        try:
            target(*args)
        except Exception as exc:
            self.thread_error = f"{name} thread failed: {type(exc).__name__}: {exc}"
            self.stop_event.set()

    def _wait_for_metadata(self) -> None:
        last_heartbeat = 0.0
        while not self.stop_event.is_set():
            if getattr(self.live_provider, "metadata", None) is not None:
                return

            now = time.monotonic()
            if now - last_heartbeat >= 1.0:
                self.dashboard_store.heartbeat(self.session_id)
                last_heartbeat = now

            if self.dashboard_store.stop_requested(self.session_id):
                self.stop_event.set()
                return
            time.sleep(0.01)

    def run_bot(self) -> None:
        self.bot.market = self.market
        self.bot.data_provider = self.live_provider

        while not self.stop_event.is_set():
            if self.market_type == "hourly":
                time_name = parse_time_name_hourly()["hourly_name"]
            elif self.market_type == "5m":
                time_name = parse_time_name_5m()
            else:
                raise ValueError(f"Unsupported market_type: {self.market_type}")

            if self.old_time_name is None or time_name != self.old_time_name:
                self.bot.first_run_setup()
                self.old_time_name = time_name

            expected_market_name = f"{self.market_slug}-{time_name}"
            if (
                self.live_provider.current_market_name is not None
                and self.live_provider.current_market_name == expected_market_name
            ):
                ran_correctly = self.bot.run()
                # Keep a tiny yield so this loop cannot monopolize the GIL.
                time.sleep(0.0001)
                if not ran_correctly:
                    time.sleep(0.1)
            else:
                time.sleep(0.001)

    def _dashboard_sample_loop(self) -> None:
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                sample = self._collect_dashboard_sample()
                if sample is not None:
                    self.dashboard_store.add_sample(self.session_id, sample)
            except Exception as exc:
                # Market rollover can briefly make provider fields unavailable.
                print(f"dashboard sampling error: {type(exc).__name__}: {exc}")

            elapsed = time.monotonic() - started
            self.stop_event.wait(max(0.0, self.sample_interval_s - elapsed))

    def _collect_dashboard_sample(self) -> dict[str, Any] | None:
        asset_ids = self.live_provider.get_market_asset_ids()
        if not asset_ids or len(asset_ids) < 2:
            return None

        strike = self.live_provider.get_price_to_beat()
        crypto_value = self.live_provider.get_crypto_value()
        crypto_mean_value = self.live_provider.get_moving_mean()

        up_price = self.live_provider.get_best_bid(asset_ids[0])
        down_price = self.live_provider.get_best_bid(asset_ids[1])
        up_fair = self.live_provider.get_fair_value_up()
        down_fair = self.live_provider.get_fair_value_down()

        cash = self.live_provider.get_user_cash()
        holdings = self.live_provider.get_user_holdings() or {}
        up_shares = holdings.get(asset_ids[0], 0)
        down_shares = holdings.get(asset_ids[1], 0)

        net = (
            cash
            + (0 if up_price is None else up_shares * up_price)
            + (0 if down_price is None else down_shares * down_price)
        )

        crypto = None
        if strike is not None and crypto_value is not None:
            crypto = crypto_value - strike

        crypto_mean = None
        if strike is not None and crypto_mean_value is not None:
            crypto_mean = crypto_mean_value - strike

        return {
            "timestamp": time.time(),
            "market_name": self.live_provider.current_market_name,
            "crypto": self._finite_or_none(crypto),
            "crypto_mean": self._finite_or_none(crypto_mean),
            "up": self._finite_or_none(up_price),
            "down": self._finite_or_none(down_price),
            "up_fair": self._finite_or_none(up_fair),
            "down_fair": self._finite_or_none(down_fair),
            "cash": self._finite_or_none(cash),
            "net": self._finite_or_none(net),
            "up_shares": self._finite_or_none(up_shares),
            "down_shares": self._finite_or_none(down_shares),
        }

    @staticmethod
    def _finite_or_none(value: Any) -> float | None:
        if value is None:
            return None
        value = float(value)
        return value if math.isfinite(value) else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run passive trading with shared-memory dashboard IPC")
    parser.add_argument("bot_path")
    parser.add_argument("market_slug")
    parser.add_argument("market_binance")
    parser.add_argument("market_type", choices=["hourly", "5m"])
    parser.add_argument("--dashboard-control-name", default=DEFAULT_CONTROL_NAME)
    parser.add_argument("--dashboard-samples-name", default=DEFAULT_SAMPLES_NAME)
    parser.add_argument("--dashboard-capacity", type=int, default=DEFAULT_CAPACITY)
    parser.add_argument("--session-id", type=int, default=None)
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--starting-cash", type=float, default=100.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = PassiveTradingEngine(
        args.bot_path,
        args.market_slug,
        args.market_binance,
        args.market_type,
        dashboard_control_name=args.dashboard_control_name,
        dashboard_samples_name=args.dashboard_samples_name,
        dashboard_capacity=args.dashboard_capacity,
        session_id=args.session_id,
        sample_interval_s=args.sample_interval,
        starting_cash=args.starting_cash,
    )
    engine.run_forever()


if __name__ == "__main__":
    main()