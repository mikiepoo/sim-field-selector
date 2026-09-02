from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable


SESSION_STATES = {
    0: "invalid",
    1: "get-in-car",
    2: "warmup",
    3: "parade-laps",
    4: "racing",
    5: "checkered",
    6: "cooldown",
}


class LiveIRacingReader:
    """Small, thread-safe adapter around iRacing's local shared-memory SDK."""

    def __init__(self, sdk_factory: Callable[[], Any] | None = None):
        self._lock = threading.Lock()
        self._sdk = None
        self._import_error = None
        if sdk_factory is not None:
            self._sdk_factory = sdk_factory
        else:
            try:
                import irsdk

                self._sdk_factory = irsdk.IRSDK
            except (ImportError, OSError) as exc:
                self._sdk_factory = None
                self._import_error = str(exc)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._sdk_factory is None:
                return self._offline(
                    "pyirsdk is not installed or could not load",
                    detail=self._import_error,
                    sdk_available=False,
                )

            if self._sdk is None:
                self._sdk = self._sdk_factory()

            try:
                if not getattr(self._sdk, "is_initialized", False) and not self._sdk.startup():
                    return self._offline("Waiting for the iRacing simulator")
                if not self._sdk.is_connected:
                    self._sdk.shutdown()
                    return self._offline("iRacing is open, but no active simulator session is connected")

                self._sdk.freeze_var_buffer_latest()
                return self._connected_snapshot()
            except (OSError, RuntimeError, TypeError, ValueError, KeyError, IndexError) as exc:
                if self._sdk and getattr(self._sdk, "is_initialized", False):
                    self._sdk.shutdown()
                return self._offline("Unable to read iRacing shared memory", detail=str(exc))

    def _offline(self, message: str, detail: str | None = None, sdk_available: bool = True) -> dict[str, Any]:
        return {
            "connected": False,
            "sdk_available": sdk_available,
            "message": message,
            "detail": detail,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "drivers": [],
        }

    def _connected_snapshot(self) -> dict[str, Any]:
        driver_info = self._sdk["DriverInfo"] or {}
        driver_rows = driver_info.get("Drivers") or []
        drivers_by_idx: dict[int, dict[str, Any]] = {}
        for driver in driver_rows:
            car_idx = self._as_int(driver.get("CarIdx"), -1)
            user_id = self._as_int(driver.get("UserID"), 0)
            is_ai = bool(driver.get("CarIsAI"))
            if (
                car_idx < 0
                or (user_id <= 0 and not is_ai)
                or driver.get("CarIsPaceCar")
                or driver.get("IsSpectator")
            ):
                continue
            drivers_by_idx[car_idx] = driver

        session_num = self._as_int(self._sdk["SessionNum"], -1)
        session_info = self._sdk["SessionInfo"] or {}
        sessions = session_info.get("Sessions") or []
        current_session = next(
            (row for row in sessions if self._as_int(row.get("SessionNum"), -999) == session_num),
            {},
        )
        session_name = str(current_session.get("SessionName") or current_session.get("SessionType") or "Unknown")

        qualify_info = self._sdk["QualifyResultsInfo"] or {}
        results = qualify_info.get("Results") or []
        if not results and "qual" in session_name.lower():
            results = current_session.get("ResultsPositions") or []

        ordered_results = sorted(enumerate(results), key=lambda item: self._result_sort_key(item[1], item[0]))
        candidates: list[dict[str, Any]] = []
        used_car_indexes: set[int] = set()
        for _, result in ordered_results:
            car_idx = self._as_int(result.get("CarIdx"), -1)
            driver = drivers_by_idx.get(car_idx)
            if not driver:
                continue
            used_car_indexes.add(car_idx)
            fastest_time = self._as_float(result.get("FastestTime"), -1.0)
            candidates.append(self._candidate(driver, fastest_time))

        # Registered drivers without a time stay at the bottom of the live list.
        for car_idx, driver in drivers_by_idx.items():
            if car_idx not in used_car_indexes:
                candidates.append(self._candidate(driver, -1.0))

        state_number = self._as_int(self._sdk["SessionState"], 0)
        weekend = self._sdk["WeekendInfo"] or {}
        session_time = self._as_float(self._sdk["SessionTime"], -1.0)
        session_time_remaining = self._as_float(self._sdk["SessionTimeRemain"], -1.0)
        qualifying_is_current = "qual" in session_name.lower()
        qualifying_final = bool(results) and not qualifying_is_current
        return {
            "connected": True,
            "sdk_available": True,
            "message": "Live iRacing session connected",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "subsession_id": weekend.get("SubSessionID"),
            "track_id": weekend.get("TrackID"),
            "session_num": session_num,
            "session_name": session_name,
            "session_state": SESSION_STATES.get(state_number, f"unknown-{state_number}"),
            "session_time": session_time if session_time >= 0 else None,
            "session_time_remaining": session_time_remaining if session_time_remaining >= 0 else None,
            "track_name": weekend.get("TrackDisplayName") or weekend.get("TrackName"),
            "track_config": weekend.get("TrackConfigName"),
            "qualifying_source": "QualifyResultsInfo" if qualify_info.get("Results") else "current session",
            "provisional": not qualifying_final and state_number not in (5, 6),
            "drivers": candidates,
        }

    @staticmethod
    def _candidate(driver: dict[str, Any], fastest_time: float) -> dict[str, Any]:
        return {
            # AI cars do not have stable member IDs. Let the selector use their
            # exact roster name and number instead of treating every AI as the
            # same customer.
            "cust_id": None if driver.get("CarIsAI") else driver.get("UserID"),
            "name": driver.get("UserName") or driver.get("AbbrevName"),
            "car_number": driver.get("CarNumber"),
            "best_lap_time": fastest_time if fastest_time > 0 else None,
        }

    @classmethod
    def _result_sort_key(cls, result: dict[str, Any], original_index: int) -> tuple[Any, ...]:
        fastest_time = cls._as_float(result.get("FastestTime"), -1.0)
        position = cls._as_int(result.get("Position"), original_index)
        return (fastest_time <= 0, position if position >= 0 else original_index, fastest_time if fastest_time > 0 else float("inf"))

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
