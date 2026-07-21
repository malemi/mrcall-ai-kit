#!/usr/bin/env python3
"""Client library for the watchdog daemon.

Provides a Python API for the orchestrator to communicate with the watchdog daemon
via the filesystem (task state files and kill log).

Standalone module with zero Octopus imports — only stdlib + httpx.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Defaults
DEFAULT_LOG_DIR = Path.home() / ".opencode/watchdog"
DEFAULT_DB_PATH = Path.home() / ".local/share/opencode/opencode.db"
SESSION_ALIVE_THRESHOLD_S = 60


@dataclass
class KillEvent:
    """Represents a killed worker event from the kill log."""

    ts: datetime
    task_id: str
    session_id: str
    reason: str  # "timeout" | "budget"
    elapsed_s: float
    cost: float


@dataclass
class TaskConfig:
    """Represents a registered task configuration."""

    task_id: str
    timeout_s: float
    budget_usd: float
    created_at: datetime


@dataclass
class WorkerStatus:
    """Represents the status of a worker session."""

    session_id: str
    agent: str
    model: str
    cost: float
    elapsed_s: float
    is_alive: bool  # True if time_updated is recent (< 60s ago)


class WatchdogClient:
    """Client for interacting with the watchdog daemon via filesystem."""

    def __init__(self, log_dir: Path | str = DEFAULT_LOG_DIR) -> None:
        """Initialize the watchdog client.

        Args:
            log_dir: Directory for task state files and kill log.
        """
        self.log_dir = Path(log_dir)
        self.db_path = DEFAULT_DB_PATH

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse an ISO 8601 timestamp string to datetime."""
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)

    def register_task(
        self, task_id: str, timeout_s: float = 120, budget_usd: float = 2.0
    ) -> Path:
        """Register a task with the watchdog.

        Creates a task state file at ~/.opencode/watchdog/{task_id}.json.

        Args:
            task_id: Unique identifier for the task.
            timeout_s: Timeout in seconds (default: 120).
            budget_usd: Budget in USD (default: 2.0).

        Returns:
            Path to the created task state file.

        Raises:
            FileExistsError: If task is already registered with different config.
        """
        self.log_dir.mkdir(parents=True, exist_ok=True)
        task_file = self.log_dir / f"{task_id}.json"

        config = {
            "timeout_s": timeout_s,
            "budget_usd": budget_usd,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        if task_file.exists():
            with open(task_file) as f:
                existing = json.load(f)
            if (
                existing.get("timeout_s") == timeout_s
                and existing.get("budget_usd") == budget_usd
            ):
                return task_file
            raise FileExistsError(f"Task {task_id} already registered with different config")

        with open(task_file, "w") as f:
            json.dump(config, f, indent=2)

        logging.info(f"Registered task {task_id} (timeout={timeout_s}s, budget=${budget_usd})")
        return task_file

    def deregister_task(self, task_id: str) -> bool:
        """Deregister a task from the watchdog.

        Removes the task state file.

        Args:
            task_id: Unique identifier for the task.

        Returns:
            True if file existed and was removed, False if not found.
        """
        task_file = self.log_dir / f"{task_id}.json"

        if not task_file.exists():
            return False

        task_file.unlink()
        logging.info(f"Deregistered task {task_id}")
        return True

    def check_kills(self, since: datetime | None = None) -> list[KillEvent]:
        """Check for killed workers.

        Reads the kill log and returns list of KillEvent instances.

        Args:
            since: If provided, only return kills after this timestamp.

        Returns:
            List of KillEvent instances.
        """
        kill_log_path = self.log_dir / "kills.jsonl"

        if not kill_log_path.exists():
            return []

        kills: list[KillEvent] = []

        with open(kill_log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    ts = self._parse_timestamp(entry["ts"])

                    if since is not None and ts <= since:
                        continue

                    kill = KillEvent(
                        ts=ts,
                        task_id=entry["task_id"],
                        session_id=entry["session_id"],
                        reason=entry["reason"],
                        elapsed_s=entry["elapsed_s"],
                        cost=entry["cost"],
                    )
                    kills.append(kill)
                except (json.JSONDecodeError, KeyError) as e:
                    logging.warning(f"Skipping malformed kill log entry: {e}")

        return kills

    def get_active_tasks(self) -> list[TaskConfig]:
        """List all active tasks.

        Scans the log directory for task state files.

        Returns:
            List of TaskConfig instances.
        """
        if not self.log_dir.exists():
            return []

        tasks: list[TaskConfig] = []

        for task_file in self.log_dir.glob("*.json"):
            if task_file.name == "kills.jsonl":
                continue

            try:
                with open(task_file) as f:
                    config = json.load(f)

                task = TaskConfig(
                    task_id=task_file.stem,
                    timeout_s=config.get("timeout_s", 120),
                    budget_usd=config.get("budget_usd", 2.0),
                    created_at=self._parse_timestamp(config["created_at"]),
                )
                tasks.append(task)
            except (json.JSONDecodeError, KeyError) as e:
                logging.warning(f"Skipping malformed task config {task_file}: {e}")

        return tasks

    def get_worker_status(self, task_id: str) -> WorkerStatus | None:
        """Get the status of a worker session for a task.

        Queries the SQLite database to find the most recently created child
        session for the task (matched by timing: session created after task registered).

        Args:
            task_id: Unique identifier for the task.

        Returns:
            WorkerStatus instance if found, None otherwise.
        """
        task_file = self.log_dir / f"{task_id}.json"

        if not task_file.exists():
            return None

        with open(task_file) as f:
            config = json.load(f)

        task_created_at = self._parse_timestamp(config["created_at"])
        task_created_ms = int(task_created_at.timestamp() * 1000)

        if not self.db_path.exists():
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, parent_id, agent, model, cost, time_created, time_updated
                FROM session
                WHERE parent_id IS NOT NULL AND time_created > ?
                ORDER BY time_created DESC
                LIMIT 1
                """,
                (task_created_ms,),
            )

            row = cursor.fetchone()
            conn.close()

            if row is None:
                return None

            session_id = row["id"]
            agent = row["agent"] or "unknown"
            model_str = row["model"] or "{}"
            cost = row["cost"] or 0.0
            time_created = row["time_created"]
            time_updated = row["time_updated"]

            try:
                model_info = json.loads(model_str) if model_str else {}
                model = model_info.get("id", "unknown") if isinstance(model_info, dict) else model_str
            except json.JSONDecodeError:
                model = model_str

            current_time_s = time.time()
            created_s = time_created / 1000.0 if time_created else current_time_s
            updated_s = time_updated / 1000.0 if time_updated else current_time_s
            elapsed_s = current_time_s - created_s
            is_alive = (current_time_s - updated_s) < SESSION_ALIVE_THRESHOLD_S

            return WorkerStatus(
                session_id=session_id,
                agent=agent,
                model=model,
                cost=cost,
                elapsed_s=elapsed_s,
                is_alive=is_alive,
            )

        except sqlite3.Error as e:
            logging.error(f"SQLite error querying worker status: {e}")
            return None


def register(task_id: str, timeout_s: float = 120, budget_usd: float = 2.0) -> Path:
    """Register a task with the watchdog.

    Convenience wrapper around WatchdogClient.

    Args:
        task_id: Unique identifier for the task.
        timeout_s: Timeout in seconds (default: 120).
        budget_usd: Budget in USD (default: 2.0).

    Returns:
        Path to the created task state file.
    """
    return WatchdogClient().register_task(task_id, timeout_s, budget_usd)


def deregister(task_id: str) -> bool:
    """Deregister a task from the watchdog.

    Convenience wrapper around WatchdogClient.

    Args:
        task_id: Unique identifier for the task.

    Returns:
        True if file existed and was removed, False if not found.
    """
    return WatchdogClient().deregister_task(task_id)


def check_kills(since: datetime | None = None) -> list[KillEvent]:
    """Check for killed workers.

    Convenience wrapper around WatchdogClient.

    Args:
        since: If provided, only return kills after this timestamp.

    Returns:
        List of KillEvent instances.
    """
    return WatchdogClient().check_kills(since)
