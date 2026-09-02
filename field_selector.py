from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


VALID_LEVELS = {"charter", "open-charter", "open"}


class SelectionError(ValueError):
    pass


def normalize_name(value: str) -> str:
    """Normalize casing/spacing only. Deliberately does not fuzzy-match drivers."""
    return " ".join(str(value).strip().casefold().split())


def normalize_number(value: Any) -> str:
    return str(value or "").strip().lstrip("#")


@dataclass(frozen=True)
class RosterDriver:
    car_number: str
    name: str
    charter_level: str
    cust_id: int | None = None

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "RosterDriver":
        level = str(row.get("charter_level", "")).strip().lower()
        if level not in VALID_LEVELS:
            raise SelectionError(f"Invalid charter_level for {row.get('name')}: {level}")
        cust_id = row.get("cust_id")
        return cls(
            car_number=normalize_number(row.get("car_number")),
            name=str(row.get("name", "")).strip(),
            charter_level=level,
            cust_id=int(cust_id) if cust_id not in (None, "") else None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "car_number": self.car_number,
            "name": self.name,
            "charter_level": self.charter_level,
            "cust_id": self.cust_id,
        }


def load_roster(path: str | Path) -> list[RosterDriver]:
    with Path(path).open(encoding="utf-8") as handle:
        rows = json.load(handle)
    return [RosterDriver.from_dict(row) for row in rows]


def validate_roster(rows: Any) -> list[RosterDriver]:
    if not isinstance(rows, list):
        raise SelectionError("Roster drivers must be provided as an array")
    if len(rows) > 200:
        raise SelectionError("Roster cannot contain more than 200 drivers")

    drivers = [RosterDriver.from_dict(row) for row in rows if isinstance(row, dict)]
    if len(drivers) != len(rows):
        raise SelectionError("Every roster entry must be an object")

    seen_names: set[str] = set()
    seen_numbers: set[str] = set()
    seen_ids: set[int] = set()
    for driver in drivers:
        if not driver.name:
            raise SelectionError("Every roster entry needs a driver name")
        if not driver.car_number:
            raise SelectionError(f"{driver.name} needs a car number")
        if driver.cust_id is not None and driver.cust_id <= 0:
            raise SelectionError(f"{driver.name} has an invalid iRacing customer ID")
        name_key = normalize_name(driver.name)
        if name_key in seen_names:
            raise SelectionError(f"Duplicate driver name: {driver.name}")
        if driver.car_number in seen_numbers:
            raise SelectionError(f"Duplicate car number: #{driver.car_number}")
        if driver.cust_id is not None and driver.cust_id in seen_ids:
            raise SelectionError(f"Duplicate iRacing customer ID: {driver.cust_id}")
        seen_names.add(name_key)
        seen_numbers.add(driver.car_number)
        if driver.cust_id is not None:
            seen_ids.add(driver.cust_id)
    return drivers


def save_roster(path: str | Path, rows: Any) -> list[RosterDriver]:
    drivers = validate_roster(rows)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump([driver.as_dict() for driver in drivers], output, indent=2)
            output.write("\n")
        os.replace(temp_name, destination)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return drivers


def _candidate_value(candidate: Any, key: str) -> Any:
    return candidate.get(key) if isinstance(candidate, dict) else None


def _candidate_label(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate.strip()
    return str(_candidate_value(candidate, "name") or _candidate_value(candidate, "display_name") or "").strip()


def _match_candidate(candidate: Any, roster: list[RosterDriver]) -> tuple[RosterDriver | None, str | None]:
    if isinstance(candidate, str):
        candidate = {"name": candidate}

    cust_id = _candidate_value(candidate, "cust_id")
    if cust_id not in (None, ""):
        matches = [driver for driver in roster if driver.cust_id == int(cust_id)]
        if len(matches) == 1:
            return matches[0], None

    name = _candidate_label(candidate)
    name_matches = [driver for driver in roster if normalize_name(driver.name) == normalize_name(name)] if name else []
    if len(name_matches) == 1:
        return name_matches[0], None

    number = normalize_number(_candidate_value(candidate, "car_number"))
    if number:
        number_matches = [driver for driver in roster if driver.car_number == number]
        if len(number_matches) == 1:
            return number_matches[0], None

    if len(name_matches) > 1:
        return None, f"Ambiguous roster name: {name}"
    return None, f"No exact roster match: {name or '#'+number}"


def select_field(
    candidates: Iterable[Any],
    roster: list[RosterDriver],
    open_charter_spots: int | None,
    open_spots: int,
    field_size: int | None = None,
) -> dict[str, Any]:
    if (open_charter_spots is not None and not 0 <= open_charter_spots <= 100) or not 0 <= open_spots <= 100:
        raise SelectionError("Spot counts must be between 0 and 100")
    if field_size is not None and not 1 <= field_size <= 100:
        raise SelectionError("Total field size must be between 1 and 100")

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()

    for rank, candidate in enumerate(candidates, start=1):
        driver, error = _match_candidate(candidate, roster)
        if not driver:
            unmatched.append({"qualifying_rank": rank, "input": _candidate_label(candidate), "error": error})
            continue
        identity = ("cust_id", driver.cust_id) if driver.cust_id is not None else ("name", normalize_name(driver.name))
        if identity in seen:
            unmatched.append({"qualifying_rank": rank, "input": _candidate_label(candidate), "error": "Duplicate driver"})
            continue
        seen.add(identity)
        live_values = {}
        if isinstance(candidate, dict) and "best_lap_time" in candidate:
            live_values["best_lap_time"] = candidate.get("best_lap_time")
        matched.append({**driver.as_dict(), **live_values, "qualifying_rank": rank})

    charter = [row for row in matched if row["charter_level"] == "charter"]
    guaranteed_open_charter_spots = open_charter_spots or 0
    configured_total = len(charter) + guaranteed_open_charter_spots + open_spots
    if field_size is not None and configured_total > field_size:
        raise SelectionError(
            f"Configuration exceeds the {field_size}-driver field: "
            f"{len(charter)} present Charters + {guaranteed_open_charter_spots} "
            f"guaranteed Open-Charter + {open_spots} final spots = {configured_total}"
        )
    open_charter = [row for row in matched if row["charter_level"] == "open-charter"]
    protected = open_charter[:guaranteed_open_charter_spots]
    protected_names = {normalize_name(row["name"]) for row in protected}
    remaining = [
        row for row in matched
        if row["charter_level"] == "open"
        or (row["charter_level"] == "open-charter" and normalize_name(row["name"]) not in protected_names)
    ]
    # Keep the track's Open-Charter guarantee fixed. Missing Charter positions
    # enlarge the final pool shared by remaining Open-Charter and Open drivers.
    final_pool_spots = (
        field_size - len(charter) - len(protected)
        if field_size is not None
        else open_spots
    )
    open_qualifiers = remaining[:final_pool_spots]
    open_names = {normalize_name(row["name"]) for row in open_qualifiers}

    rows: list[dict[str, Any]] = []
    for row in matched:
        key = normalize_name(row["name"])
        if row["charter_level"] == "charter":
            result, reason = "IN", "Charter locked"
        elif key in protected_names:
            result, reason = "IN", "Open-Charter position"
        elif key in open_names:
            result, reason = "IN", "Open position"
        else:
            result, reason = "DNQ", "Outside available positions"
        rows.append({**row, "result": result, "reason": reason})

    in_field = sum(row["result"] == "IN" for row in rows)
    open_charter_rows = [row for row in rows if row["charter_level"] == "open-charter"]
    open_rows = [row for row in rows if row["charter_level"] == "open"]
    open_charter_final_pool = sum(row["charter_level"] == "open-charter" for row in open_qualifiers)
    open_final_pool = sum(row["charter_level"] == "open" for row in open_qualifiers)
    entered_charter_names = {normalize_name(row["name"]) for row in charter}
    missing_charters = [
        driver.as_dict()
        for driver in roster
        if driver.charter_level == "charter" and normalize_name(driver.name) not in entered_charter_names
    ]
    return {
        "rules": {
            "field_size": field_size,
            "open_charter_spots": guaranteed_open_charter_spots,
            "base_open_spots": open_spots,
            "actual_open_spots": final_pool_spots,
        },
        "summary": {
            "entered": len(matched),
            "field_size": field_size,
            "in_field": in_field,
            "unfilled_spots": max(0, field_size - in_field) if field_size is not None else 0,
            "dnq": sum(row["result"] == "DNQ" for row in rows),
            "unmatched": len(unmatched),
            "charter_locked": len(charter),
            "missing_charters": len(missing_charters),
            "open_charter_selected": len(protected),
            "open_selected": len(open_qualifiers),
            "open_charter_configured": sum(driver.charter_level == "open-charter" for driver in roster),
            "open_charter_entered": len(open_charter_rows),
            "open_charter_in": sum(row["result"] == "IN" for row in open_charter_rows),
            "open_charter_dnq": sum(row["result"] == "DNQ" for row in open_charter_rows),
            "open_charter_via_final_pool": open_charter_final_pool,
            "open_configured": sum(driver.charter_level == "open" for driver in roster),
            "open_entered": len(open_rows),
            "open_in": sum(row["result"] == "IN" for row in open_rows),
            "open_dnq": sum(row["result"] == "DNQ" for row in open_rows),
            "open_via_final_pool": open_final_pool,
            "added_vacancy_spots": max(0, final_pool_spots - open_spots),
        },
        "drivers": rows,
        "unmatched": unmatched,
        "missing_charters": missing_charters,
    }
