from __future__ import annotations

import time
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Any

import numpy as np


DEFAULT_CONTROL_NAME = "bot_evaluator_passive_dashboard_control"
DEFAULT_SAMPLES_NAME = "bot_evaluator_passive_dashboard_samples"
DEFAULT_CAPACITY = 400_000  # ~27.8 hours at one sample every 0.25 s

CONTROL_DTYPE = np.dtype(
    [
        ("version", "<i8"),
        ("session_id", "<i8"),
        ("started_at", "<f8"),
        ("stopped_at", "<f8"),
        ("heartbeat_at", "<f8"),
        ("pid", "<i8"),
        ("write_count", "<i8"),
        ("capacity", "<i8"),
        ("stop_requested", "u1"),
        ("status", "S16"),
        ("bot_path", "S512"),
        ("market_slug", "S256"),
        ("market_binance", "S64"),
        ("market_type", "S16"),
        ("log_path", "S512"),
        ("error", "S1024"),
        ("current_market_name", "S512"),
    ],
    align=True,
)

SAMPLE_DTYPE = np.dtype(
    [
        ("id", "<i8"),
        ("timestamp", "<f8"),
        ("crypto", "<f8"),
        ("crypto_mean", "<f8"),
        ("up", "<f8"),
        ("down", "<f8"),
        ("up_fair", "<f8"),
        ("down_fair", "<f8"),
        ("cash", "<f8"),
        ("net", "<f8"),
        ("up_shares", "<f8"),
        ("down_shares", "<f8"),
    ],
    align=True,
)


@dataclass(frozen=True)
class DashboardSession:
    id: int
    started_at: float
    stopped_at: float | None
    heartbeat_at: float | None
    status: str
    stop_requested: bool
    pid: int | None
    bot_path: str
    market_slug: str
    market_binance: str
    market_type: str
    log_path: str | None
    error: str | None
    current_market_name: str | None


class PassiveDashboardStore:
    """Single-writer/shared-reader dashboard transport backed by shared memory.

    One control block contains lifecycle/configuration data and one fixed-size
    NumPy ring buffer contains numeric dashboard samples. The passive engine is
    the only sample writer; Streamlit is a reader and can set stop_requested.
    """

    def __init__(
        self,
        *,
        control_name: str = DEFAULT_CONTROL_NAME,
        samples_name: str = DEFAULT_SAMPLES_NAME,
        create: bool = False,
        capacity: int = DEFAULT_CAPACITY,
    ):
        self.control_name = control_name
        self.samples_name = samples_name
        self._owner = create
        self._closed = False

        if create:
            if capacity <= 0:
                raise ValueError("capacity must be positive")
            self.control_shm = shared_memory.SharedMemory(
                name=control_name,
                create=True,
                size=CONTROL_DTYPE.itemsize,
            )
            try:
                self.samples_shm = shared_memory.SharedMemory(
                    name=samples_name,
                    create=True,
                    size=capacity * SAMPLE_DTYPE.itemsize,
                )
            except Exception:
                self.control_shm.close()
                self.control_shm.unlink()
                raise

            self.control = np.ndarray((1,), dtype=CONTROL_DTYPE, buffer=self.control_shm.buf)
            self.samples = np.ndarray((capacity,), dtype=SAMPLE_DTYPE, buffer=self.samples_shm.buf)
            self.control.fill(0)
            self.samples.fill(0)
            self.control[0]["capacity"] = capacity
        else:
            self.control_shm = shared_memory.SharedMemory(name=control_name, create=False)
            try:
                self.control = np.ndarray((1,), dtype=CONTROL_DTYPE, buffer=self.control_shm.buf)
                capacity = int(self.control[0]["capacity"])
                if capacity <= 0:
                    raise RuntimeError("Shared dashboard control block is not initialized")
                self.samples_shm = shared_memory.SharedMemory(name=samples_name, create=False)
            except Exception:
                # The owner can replace stale blocks while Streamlit is trying
                # to attach. Do not leak the already-open control handle if the
                # second block disappears during that small race window.
                self.control_shm.close()
                raise
            self.samples = np.ndarray((capacity,), dtype=SAMPLE_DTYPE, buffer=self.samples_shm.buf)

    @classmethod
    def create_session(
        cls,
        *,
        bot_path: str,
        market_slug: str,
        market_binance: str,
        market_type: str,
        session_id: int | None = None,
        log_path: str | None = None,
        capacity: int = DEFAULT_CAPACITY,
        control_name: str = DEFAULT_CONTROL_NAME,
        samples_name: str = DEFAULT_SAMPLES_NAME,
    ) -> "PassiveDashboardStore":
        cls.unlink_existing(control_name=control_name, samples_name=samples_name)
        store = cls(
            control_name=control_name,
            samples_name=samples_name,
            create=True,
            capacity=capacity,
        )
        now = time.time()
        session_id = int(session_id if session_id is not None else time.time_ns() // 1_000)
        store._write_control(
            session_id=session_id,
            started_at=now,
            stopped_at=0.0,
            heartbeat_at=now,
            pid=0,
            write_count=0,
            stop_requested=0,
            status="starting",
            bot_path=bot_path,
            market_slug=market_slug,
            market_binance=market_binance,
            market_type=market_type,
            log_path=log_path or "",
            error="",
            current_market_name="",
        )
        return store

    @classmethod
    def attach(
        cls,
        *,
        control_name: str = DEFAULT_CONTROL_NAME,
        samples_name: str = DEFAULT_SAMPLES_NAME,
    ) -> "PassiveDashboardStore":
        return cls(control_name=control_name, samples_name=samples_name, create=False)

    @classmethod
    def attach_or_none(
        cls,
        *,
        control_name: str = DEFAULT_CONTROL_NAME,
        samples_name: str = DEFAULT_SAMPLES_NAME,
    ) -> "PassiveDashboardStore | None":
        try:
            return cls.attach(control_name=control_name, samples_name=samples_name)
        except (FileNotFoundError, RuntimeError):
            return None

    @staticmethod
    def unlink_existing(
        *,
        control_name: str = DEFAULT_CONTROL_NAME,
        samples_name: str = DEFAULT_SAMPLES_NAME,
    ) -> None:
        for name in (control_name, samples_name):
            try:
                shm = shared_memory.SharedMemory(name=name, create=False)
            except FileNotFoundError:
                continue
            try:
                shm.close()
            finally:
                try:
                    shm.unlink()
                except FileNotFoundError:
                    pass

    @property
    def capacity(self) -> int:
        return len(self.samples)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.samples_shm.close()
        self.control_shm.close()

    def unlink(self) -> None:
        for shm in (self.samples_shm, self.control_shm):
            try:
                shm.unlink()
            except FileNotFoundError:
                pass

    def mark_running(self, session_id: int, pid: int) -> None:
        self._require_session(session_id)
        self._write_control(
            status="running",
            pid=int(pid),
            heartbeat_at=time.time(),
            error="",
        )

    def heartbeat(self, session_id: int) -> None:
        self._require_session(session_id)
        self._write_control(heartbeat_at=time.time())

    def request_stop(self, session_id: int) -> None:
        session = self.get_session(session_id)
        if session is None:
            return
        status = "stopping" if session.status in {"starting", "running"} else session.status
        self._write_control(stop_requested=1, status=status)

    def stop_requested(self, session_id: int) -> bool:
        session = self.get_session(session_id)
        return bool(session and session.stop_requested)

    def finish_session(
        self,
        session_id: int,
        *,
        status: str = "stopped",
        error: str | None = None,
    ) -> None:
        self._require_session(session_id)
        now = time.time()
        self._write_control(
            status=status,
            stopped_at=now,
            heartbeat_at=now,
            error=error or "",
        )

    def set_log_path(self, session_id: int, log_path: str) -> None:
        self._require_session(session_id)
        self._write_control(log_path=log_path)

    def set_current_market_name(self, session_id: int, market_name: str | None) -> None:
        self._require_session(session_id)
        self._write_control(current_market_name=market_name or "")

    def add_sample(self, session_id: int, sample: dict[str, Any]) -> int:
        self._require_session(session_id)

        # Only the passive engine calls this method. The record id is committed
        # last, then write_count is advanced in the control block.
        write_count = int(self.control[0]["write_count"])
        next_id = write_count + 1
        index = write_count % self.capacity
        record = self.samples[index]
        record["id"] = 0
        record["timestamp"] = self._float_or_nan(sample.get("timestamp"))
        for field in (
            "crypto",
            "crypto_mean",
            "up",
            "down",
            "up_fair",
            "down_fair",
            "cash",
            "net",
            "up_shares",
            "down_shares",
        ):
            record[field] = self._float_or_nan(sample.get(field))
        record["id"] = next_id

        self._write_control(
            write_count=next_id,
            heartbeat_at=time.time(),
            current_market_name=sample.get("market_name") or "",
        )
        return next_id

    def get_session(self, session_id: int | None = None) -> DashboardSession | None:
        snapshot = self._read_control_snapshot()
        if snapshot is None or int(snapshot["session_id"]) <= 0:
            return None
        if session_id is not None and int(snapshot["session_id"]) != int(session_id):
            return None

        return DashboardSession(
            id=int(snapshot["session_id"]),
            started_at=float(snapshot["started_at"]),
            stopped_at=self._zero_to_none_float(snapshot["stopped_at"]),
            heartbeat_at=self._zero_to_none_float(snapshot["heartbeat_at"]),
            status=self._decode(snapshot["status"]),
            stop_requested=bool(snapshot["stop_requested"]),
            pid=self._zero_to_none_int(snapshot["pid"]),
            bot_path=self._decode(snapshot["bot_path"]),
            market_slug=self._decode(snapshot["market_slug"]),
            market_binance=self._decode(snapshot["market_binance"]),
            market_type=self._decode(snapshot["market_type"]),
            log_path=self._decode(snapshot["log_path"]) or None,
            error=self._decode(snapshot["error"]) or None,
            current_market_name=self._decode(snapshot["current_market_name"]) or None,
        )

    def get_latest_session(self) -> DashboardSession | None:
        return self.get_session()

    def get_fresh_active_session(self, stale_after_seconds: float = 8.0) -> DashboardSession | None:
        session = self.get_session()
        if session is not None and self.is_fresh(session, stale_after_seconds):
            return session
        return None

    def get_recent_sessions(self, limit: int = 20) -> list[DashboardSession]:
        session = self.get_session()
        return [] if session is None or limit <= 0 else [session]

    def get_write_count(self, session_id: int) -> int:
        """Return the total number of samples written in this session."""
        self._require_session(session_id)
        snapshot = self._read_control_snapshot()
        return 0 if snapshot is None else int(snapshot["write_count"])

    def get_samples_since(
        self,
        session_id: int,
        after_id: int = 0,
        *,
        step: int = 1,
    ) -> list[dict[str, Any]]:
        """Read committed samples newer than ``after_id``.

        ``step`` is aligned to global sample IDs (1, 1+step, ...). This lets
        the live dashboard read a downsampled snapshot directly from shared
        memory instead of first materializing hundreds of thousands of rows.
        """
        self._require_session(session_id)
        if step <= 0:
            raise ValueError("step must be positive")

        snapshot = self._read_control_snapshot()
        if snapshot is None:
            return []

        write_count = int(snapshot["write_count"])
        if write_count <= 0:
            return []

        earliest_id = max(1, write_count - self.capacity + 1)
        first_id = max(int(after_id) + 1, earliest_id)
        if first_id > write_count:
            return []

        # Align to IDs 1, 1+step, 1+2*step, ... so an incremental read uses
        # exactly the same downsampling grid as a later full/bootstrap read.
        remainder = (first_id - 1) % step
        if remainder:
            first_id += step - remainder
        if first_id > write_count:
            return []

        rows: list[dict[str, Any]] = []
        for record_id in range(first_id, write_count + 1, step):
            index = (record_id - 1) % self.capacity
            id_before = int(self.samples[index]["id"])
            if id_before != record_id:
                continue
            record = self.samples[index].copy()
            id_after = int(self.samples[index]["id"])
            # A slot can be overwritten when the ring wraps. Verify the commit
            # ID both before and after copying so Streamlit never plots a torn
            # record whose numeric fields changed mid-copy.
            if id_after != record_id or int(record["id"]) != record_id:
                continue
            rows.append(self._sample_to_dict(record))
        return rows

    def get_latest_sample(self, session_id: int) -> dict[str, Any] | None:
        """Return the newest fully committed sample, if one exists."""
        self._require_session(session_id)
        snapshot = self._read_control_snapshot()
        if snapshot is None:
            return None

        write_count = int(snapshot["write_count"])
        if write_count <= 0:
            return None

        index = (write_count - 1) % self.capacity
        id_before = int(self.samples[index]["id"])
        if id_before != write_count:
            return None
        record = self.samples[index].copy()
        id_after = int(self.samples[index]["id"])
        if id_after != write_count or int(record["id"]) != write_count:
            return None
        return self._sample_to_dict(record)

    def get_sample_count(self, session_id: int) -> int:
        self._require_session(session_id)
        snapshot = self._read_control_snapshot()
        if snapshot is None:
            return 0
        return min(int(snapshot["write_count"]), self.capacity)

    @staticmethod
    def is_fresh(session: DashboardSession, stale_after_seconds: float = 5.0) -> bool:
        if session.status not in {"starting", "running", "stopping"}:
            return False
        reference = session.heartbeat_at or session.started_at
        return (time.time() - reference) <= stale_after_seconds

    def _require_session(self, session_id: int) -> None:
        current = int(self.control[0]["session_id"])
        if current != int(session_id):
            raise ValueError(f"Dashboard session {session_id} is not the active shared-memory session")

    def _write_control(self, **values: Any) -> None:
        record = self.control[0]
        version = int(record["version"])
        if version % 2:
            version += 1
        record["version"] = version + 1  # odd = write in progress

        for key, value in values.items():
            if key not in CONTROL_DTYPE.names:
                raise KeyError(key)
            if CONTROL_DTYPE.fields[key][0].kind == "S":
                record[key] = self._encode(value, CONTROL_DTYPE.fields[key][0].itemsize)
            else:
                record[key] = value

        record["version"] = version + 2  # even = stable

    def _read_control_snapshot(self) -> np.void | None:
        for _ in range(50):
            version_before = int(self.control[0]["version"])
            if version_before % 2:
                time.sleep(0)
                continue
            snapshot = self.control[0].copy()
            version_after = int(self.control[0]["version"])
            if version_before == version_after and version_after % 2 == 0:
                return snapshot
        return None

    @staticmethod
    def _sample_to_dict(record: np.void) -> dict[str, Any]:
        result: dict[str, Any] = {"id": int(record["id"])}
        for field in SAMPLE_DTYPE.names:
            if field == "id":
                continue
            value = float(record[field])
            result[field] = None if np.isnan(value) else value
        return result

    @staticmethod
    def _float_or_nan(value: Any) -> float:
        if value is None:
            return float("nan")
        value = float(value)
        return value if np.isfinite(value) else float("nan")

    @staticmethod
    def _encode(value: Any, max_bytes: int) -> bytes:
        return str(value or "").encode("utf-8")[: max(0, max_bytes - 1)]

    @staticmethod
    def _decode(value: Any) -> str:
        raw = bytes(value)
        return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")

    @staticmethod
    def _zero_to_none_float(value: Any) -> float | None:
        value = float(value)
        return None if value == 0.0 else value

    @staticmethod
    def _zero_to_none_int(value: Any) -> int | None:
        value = int(value)
        return None if value == 0 else value