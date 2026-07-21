#!/usr/bin/env python3
"""Watchdog daemon for OpenCode task delegation system.

Monitors worker LLM sessions and kills hung ones based on timeout or budget violations.
Uses SSE for real-time events, SQLite as fallback, and HTTP abort endpoint for termination.

Standalone script with zero Octopus imports — only stdlib + httpx.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

# Defaults
DEFAULT_TIMEOUT_S = 120
DEFAULT_BUDGET_USD = 5.0
POLL_INTERVAL_S = 30
CHECK_INTERVAL_S = 60

# Paths
DEFAULT_DB_PATH = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_LOG_DIR = Path.home() / ".opencode/watchdog"
DEFAULT_BASE_URL = "http://127.0.0.1:4096"


@dataclass
class WorkerInfo:
    """Information about a tracked worker session."""

    session_id: str
    parent_id: str
    agent: str
    model: str
    start_time_s: float
    timeout_s: float = DEFAULT_TIMEOUT_S
    budget_usd: float = DEFAULT_BUDGET_USD
    cost_usd: float = 0.0
    last_updated_s: float = field(default_factory=time.time)


class WorkerRegistry:
    """In-memory registry of active worker sessions."""

    def __init__(self) -> None:
        self._workers: dict[str, WorkerInfo] = {}
        self._lock = threading.Lock()

    def register(
        self,
        session_id: str,
        parent_id: str,
        agent: str,
        model: str,
        start_time_s: float,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        budget_usd: float = DEFAULT_BUDGET_USD,
    ) -> None:
        """Register a new worker session."""
        with self._lock:
            if session_id not in self._workers:
                self._workers[session_id] = WorkerInfo(
                    session_id=session_id,
                    parent_id=parent_id,
                    agent=agent,
                    model=model,
                    start_time_s=start_time_s,
                    timeout_s=timeout_s,
                    budget_usd=budget_usd,
                )
                logging.info(f"Registered worker {session_id} (parent={parent_id})")

    def update_cost(self, session_id: str, cost_usd: float) -> None:
        """Update the cost for a worker session."""
        with self._lock:
            if session_id in self._workers:
                self._workers[session_id].cost_usd = cost_usd
                self._workers[session_id].last_updated_s = time.time()

    def deregister(self, session_id: str) -> None:
        """Remove a worker session from the registry."""
        with self._lock:
            if session_id in self._workers:
                del self._workers[session_id]
                logging.info(f"Deregistered worker {session_id}")

    def check_violations(self) -> list[WorkerInfo]:
        """Return list of workers that exceeded timeout OR budget."""
        violations: list[WorkerInfo] = []
        current_time = time.time()

        with self._lock:
            for worker in self._workers.values():
                elapsed = current_time - worker.start_time_s
                if elapsed > worker.timeout_s:
                    violations.append(worker)
                    logging.warning(
                        f"Worker {worker.session_id} exceeded timeout: "
                        f"{elapsed:.1f}s > {worker.timeout_s}s"
                    )
                elif worker.cost_usd > worker.budget_usd:
                    violations.append(worker)
                    logging.warning(
                        f"Worker {worker.session_id} exceeded budget: "
                        f"${worker.cost_usd:.2f} > ${worker.budget_usd:.2f}"
                    )

        return violations

    def get_all(self) -> list[WorkerInfo]:
        """Return all active workers."""
        with self._lock:
            return list(self._workers.values())

    def contains(self, session_id: str) -> bool:
        """Check if a session is in the registry."""
        with self._lock:
            return session_id in self._workers


class SSEListener:
    """Listens to OpenCode SSE events for session lifecycle changes."""

    def __init__(
        self,
        registry: WorkerRegistry,
        base_url: str = DEFAULT_BASE_URL,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
        default_budget_usd: float = DEFAULT_BUDGET_USD,
        on_deregister: Callable[[str], None] | None = None,
    ) -> None:
        self.registry = registry
        self.base_url = base_url
        self.default_timeout_s = default_timeout_s
        self.default_budget_usd = default_budget_usd
        self.on_deregister = on_deregister
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the SSE listener in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("SSE listener started")

    def stop(self) -> None:
        """Stop the SSE listener."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logging.info("SSE listener stopped")

    def _run(self) -> None:
        """Main SSE listening loop."""
        event_url = f"{self.base_url}/event"

        while self._running:
            try:
                with httpx.stream("GET", event_url, timeout=None) as response:
                    if response.status_code != 200:
                        logging.error(f"SSE connection failed: {response.status_code}")
                        time.sleep(5)
                        continue

                    logging.info(f"Connected to SSE stream at {event_url}")

                    for line in response.iter_lines():
                        if not self._running:
                            break

                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue

                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            self._process_event(data_str)

            except httpx.ConnectError as e:
                logging.warning(f"SSE connection error: {e}. Retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                logging.error(f"SSE listener error: {e}. Retrying in 5s...")
                time.sleep(5)

    def _process_event(self, data_str: str) -> None:
        """Process a single SSE event."""
        try:
            event = json.loads(data_str)
            event_type = event.get("type", "")
            properties = event.get("properties", {})
            session_info = properties.get("info", {})

            if not session_info:
                return

            session_id = session_info.get("id", "")
            parent_id = session_info.get("parentID")

            if not session_id:
                return

            if event_type == "session.created":
                if parent_id:
                    agent = session_info.get("agent", "unknown")
                    model_info = session_info.get("model", {})
                    model = model_info.get("id", "unknown") if isinstance(model_info, dict) else str(model_info)
                    time_created = session_info.get("timeCreated", 0)
                    start_time_s = time_created / 1000.0 if time_created else time.time()

                    self.registry.register(
                        session_id=session_id,
                        parent_id=parent_id,
                        agent=agent,
                        model=model,
                        start_time_s=start_time_s,
                        timeout_s=self.default_timeout_s,
                        budget_usd=self.default_budget_usd,
                    )

            elif event_type == "session.updated":
                cost = session_info.get("cost", 0.0)
                if cost and self.registry.contains(session_id):
                    self.registry.update_cost(session_id, float(cost))

            elif event_type == "session.deleted":
                if self.on_deregister:
                    self.on_deregister(session_id)
                else:
                    self.registry.deregister(session_id)

        except json.JSONDecodeError as e:
            logging.debug(f"Failed to parse SSE event: {e}")
        except Exception as e:
            logging.error(f"Error processing SSE event: {e}")


class DBPoller:
    """Polls SQLite database for session state as fallback."""

    def __init__(
        self,
        registry: WorkerRegistry,
        db_path: Path | str,
        poll_interval_s: float = POLL_INTERVAL_S,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
        default_budget_usd: float = DEFAULT_BUDGET_USD,
        on_deregister: Callable[[str], None] | None = None,
    ) -> None:
        self.registry = registry
        self.db_path = Path(db_path)
        self.poll_interval_s = poll_interval_s
        self.default_timeout_s = default_timeout_s
        self.default_budget_usd = default_budget_usd
        self.on_deregister = on_deregister
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_poll_time_ms = 0

    def start(self) -> None:
        """Start the DB poller in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info(f"DB poller started (interval={self.poll_interval_s}s)")

    def stop(self) -> None:
        """Stop the DB poller."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logging.info("DB poller stopped")

    def _run(self) -> None:
        """Main DB polling loop."""
        while self._running:
            try:
                self._poll()
            except Exception as e:
                logging.error(f"DB poller error: {e}")

            time.sleep(self.poll_interval_s)

    def _poll(self) -> None:
        """Poll the database for session updates."""
        if not self.db_path.exists():
            logging.debug(f"Database not found: {self.db_path}")
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Only query sessions updated in the last hour (likely still running)
            one_hour_ago_ms = int((time.time() - 3600) * 1000)
            cursor.execute(
                """
                SELECT id, parent_id, agent, model, cost, time_created, time_updated
                FROM session
                WHERE parent_id IS NOT NULL AND time_updated > ?
                """,
                (one_hour_ago_ms,),
            )

            rows = cursor.fetchall()
            current_time_ms = int(time.time() * 1000)

            seen_ids: set[str] = set()

            for row in rows:
                session_id = row["id"]
                parent_id = row["parent_id"]
                agent = row["agent"] or "unknown"
                model_str = row["model"] or "{}"
                cost = row["cost"] or 0.0
                time_created = row["time_created"]
                time_updated = row["time_updated"]

                seen_ids.add(session_id)

                if not self.registry.contains(session_id):
                    # New worker found in DB
                    start_time_s = time_created / 1000.0 if time_created else time.time()

                    try:
                        model_info = json.loads(model_str) if model_str else {}
                        model = model_info.get("id", "unknown") if isinstance(model_info, dict) else model_str
                    except json.JSONDecodeError:
                        model = model_str

                    self.registry.register(
                        session_id=session_id,
                        parent_id=parent_id,
                        agent=agent,
                        model=model,
                        start_time_s=start_time_s,
                        timeout_s=self.default_timeout_s,
                        budget_usd=self.default_budget_usd,
                    )

                # Always update cost from DB
                self.registry.update_cost(session_id, float(cost))

                # Update last poll time
                if time_updated > self._last_poll_time_ms:
                    self._last_poll_time_ms = time_updated

            # Deregister workers no longer in DB (that were previously tracked)
            for worker in self.registry.get_all():
                if worker.session_id not in seen_ids:
                    # Check if it's been a while since last update
                    if time.time() - worker.last_updated_s > self.poll_interval_s * 2:
                        if self.on_deregister:
                            self.on_deregister(worker.session_id)
                        else:
                            self.registry.deregister(worker.session_id)

            conn.close()

        except sqlite3.Error as e:
            logging.error(f"SQLite error: {e}")


class WatchdogDaemon:
    """Main watchdog daemon that coordinates registry, SSE, and DB polling."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        db_path: Path | str = DEFAULT_DB_PATH,
        log_dir: Path | str = DEFAULT_LOG_DIR,
        poll_interval_s: float = POLL_INTERVAL_S,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
        default_budget_usd: float = DEFAULT_BUDGET_USD,
        parent_session_id: str | None = None,
    ) -> None:
        self.base_url = base_url
        self.db_path = Path(db_path)
        self.log_dir = Path(log_dir)
        self.poll_interval_s = poll_interval_s
        self.default_timeout_s = default_timeout_s
        self.default_budget_usd = default_budget_usd
        self.parent_session_id = parent_session_id
        self.check_interval_s = CHECK_INTERVAL_S

        self.registry = WorkerRegistry()
        self.sse_listener = SSEListener(
            registry=self.registry,
            base_url=base_url,
            default_timeout_s=default_timeout_s,
            default_budget_usd=default_budget_usd,
            on_deregister=self.deregister_session,
        )
        self.db_poller = DBPoller(
            registry=self.registry,
            db_path=db_path,
            poll_interval_s=poll_interval_s,
            default_timeout_s=default_timeout_s,
            default_budget_usd=default_budget_usd,
            on_deregister=self.deregister_session,
        )

        self._running = False
        self._thread: threading.Thread | None = None
        self._http_client: httpx.Client | None = None
        self._killed_sessions: set[str] = set()
        self._pid_file: Path | None = None

    def start(self) -> None:
        """Start the watchdog daemon."""
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # PID lock — prevent multiple instances
        self._pid_file = self.log_dir / "watchdog.pid"
        if self._pid_file.exists():
            try:
                old_pid = int(self._pid_file.read_text().strip())
                os.kill(old_pid, 0)  # Check if process exists
                logging.error(f"Another watchdog instance is running (PID {old_pid}). Exiting.")
                sys.exit(1)
            except (ProcessLookupError, ValueError):
                pass  # Old process dead or invalid PID file — safe to continue
        self._pid_file.write_text(str(os.getpid()))

        # Load previously killed sessions from kill log
        self._load_killed_sessions()

        self._running = True
        self._http_client = httpx.Client(base_url=self.base_url, timeout=10.0)

        # Load task configs
        self.load_task_configs()

        # Start background threads
        self.sse_listener.start()
        self.db_poller.start()

        # Start main loop
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        logging.info("Watchdog started")

    def stop(self) -> None:
        """Stop the watchdog daemon."""
        self._running = False

        self.sse_listener.stop()
        self.db_poller.stop()

        if self._thread:
            self._thread.join(timeout=10)

        if self._http_client:
            self._http_client.close()

        # Remove PID file
        if self._pid_file and self._pid_file.exists():
            try:
                self._pid_file.unlink()
            except OSError:
                pass

        logging.info("Watchdog stopped")

    def _load_killed_sessions(self) -> None:
        """Load previously killed session IDs from the kill log to prevent re-killing."""
        kill_log_path = self.log_dir / "kills.jsonl"
        if not kill_log_path.exists():
            return

        try:
            with open(kill_log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    session_id = entry.get("session_id", "")
                    if session_id:
                        self._killed_sessions.add(session_id)
            logging.info(f"Loaded {len(self._killed_sessions)} previously killed sessions")
        except Exception as e:
            logging.error(f"Failed to load kill log: {e}")

    def _run(self) -> None:
        """Main watchdog loop."""
        while self._running:
            try:
                self._check_and_kill()
            except Exception as e:
                logging.error(f"Watchdog loop error: {e}")

            time.sleep(self.check_interval_s)

    def _check_and_kill(self) -> None:
        """Check for violations and kill offending workers."""
        violations = self.registry.check_violations()

        for worker in violations:
            # Skip workers that don't belong to our parent session
            if self.parent_session_id and worker.parent_id != self.parent_session_id:
                continue

            # Skip workers we've already killed this cycle
            if worker.session_id in self._killed_sessions:
                continue

            reason = self._get_violation_reason(worker)
            elapsed = time.time() - worker.start_time_s

            success = self.abort_session(worker.session_id)

            self._log_kill(
                session_id=worker.session_id,
                reason=reason,
                elapsed_s=elapsed,
                cost=worker.cost_usd,
            )

            # Mark as killed to prevent duplicate logs
            self._killed_sessions.add(worker.session_id)

            if success:
                self.registry.deregister(worker.session_id)

    def deregister_session(self, session_id: str) -> None:
        """Deregister a session. Does NOT clear killed status — once killed, always killed."""
        self.registry.deregister(session_id)

    def _get_violation_reason(self, worker: WorkerInfo) -> str:
        """Determine the violation reason for a worker."""
        elapsed = time.time() - worker.start_time_s
        if elapsed > worker.timeout_s:
            return "timeout"
        elif worker.cost_usd > worker.budget_usd:
            return "budget"
        return "unknown"

    def abort_session(self, session_id: str) -> bool:
        """Abort a session via HTTP POST."""
        if not self._http_client:
            logging.error("HTTP client not initialized")
            return False

        try:
            response = self._http_client.post(f"/session/{session_id}/abort")
            if response.status_code == 200:
                logging.info(f"Successfully aborted session {session_id}")
                return True
            else:
                logging.error(
                    f"Failed to abort session {session_id}: {response.status_code}"
                )
                return False
        except httpx.ConnectError as e:
            logging.error(f"Cannot connect to abort endpoint: {e}")
            return False
        except Exception as e:
            logging.error(f"Error aborting session {session_id}: {e}")
            return False

    def _log_kill(self, session_id: str, reason: str, elapsed_s: float, cost: float) -> None:
        """Log a kill event to kills.jsonl."""
        kill_log_path = self.log_dir / "kills.jsonl"

        # Try to find task_id from parent session
        task_id = "unknown"
        for worker in self.registry.get_all():
            if worker.session_id == session_id:
                # Use parent_id as task_id proxy
                task_id = worker.parent_id or "unknown"
                break

        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "session_id": session_id,
            "reason": reason,
            "elapsed_s": round(elapsed_s, 1),
            "cost": round(cost, 2),
        }

        try:
            with open(kill_log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
            logging.info(f"Logged kill: {session_id} ({reason})")
        except Exception as e:
            logging.error(f"Failed to write kill log: {e}")

    def load_task_configs(self) -> None:
        """Load task configuration files from log directory."""
        config_dir = self.log_dir
        if not config_dir.exists():
            return

        for config_file in config_dir.glob("*.json"):
            if config_file.name == "kills.jsonl":
                continue

            try:
                with open(config_file) as f:
                    config = json.load(f)

                task_id = config_file.stem
                timeout_s = config.get("timeout_s", self.default_timeout_s)
                budget_usd = config.get("budget_usd", self.default_budget_usd)

                logging.info(
                    f"Loaded task config {task_id}: timeout={timeout_s}s, budget=${budget_usd}"
                )

            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in {config_file}: {e}")
            except Exception as e:
                logging.error(f"Error loading config {config_file}: {e}")


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    """Configure logging for the watchdog daemon."""
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    # File handler
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "watchdog.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Root logger
    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler],
    )


def main() -> None:
    """CLI entry point for the watchdog daemon."""
    parser = argparse.ArgumentParser(
        description="Watchdog daemon for OpenCode task delegation system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --default-timeout 300 --default-budget 10.0
  %(prog)s --poll-interval 30 --log-dir /tmp/watchdog
  %(prog)s --base-url http://localhost:4096 --db-path ~/.local/share/opencode/opencode.db
        """,
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL_S,
        help=f"Database polling interval in seconds (default: {POLL_INTERVAL_S})",
    )

    parser.add_argument(
        "--default-timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"Default timeout in seconds (default: {DEFAULT_TIMEOUT_S})",
    )

    parser.add_argument(
        "--default-budget",
        type=float,
        default=DEFAULT_BUDGET_USD,
        help=f"Default budget in USD (default: {DEFAULT_BUDGET_USD})",
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"OpenCode API base URL (default: {DEFAULT_BASE_URL})",
    )

    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help=f"Directory for logs and task configs (default: {DEFAULT_LOG_DIR})",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--parent-session-id",
        type=str,
        default=None,
        help="Only monitor workers for this parent session ID (default: all)",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(args.log_dir, log_level)

    # Create daemon
    daemon = WatchdogDaemon(
        base_url=args.base_url,
        db_path=args.db_path,
        log_dir=args.log_dir,
        poll_interval_s=args.poll_interval,
        default_timeout_s=args.default_timeout,
        default_budget_usd=args.default_budget,
        parent_session_id=args.parent_session_id,
    )

    # Signal handling for graceful shutdown
    shutdown_event = threading.Event()

    def signal_handler(signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        logging.info(f"Received {sig_name}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start daemon
    daemon.start()

    # Wait for shutdown signal
    shutdown_event.wait()

    # Stop daemon
    daemon.stop()
    logging.info("Watchdog daemon terminated")


if __name__ == "__main__":
    main()
