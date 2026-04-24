"""Scheduler backed by APScheduler + SQLite.

Jobs live in `backend/db/sessions.db` via SQLAlchemyJobStore so they survive
restarts. Because that store pickles jobs, the target callable must be
resolvable at import time. We therefore expose a module-level
`run_scheduled_task` coroutine that looks the runner up on a module-level
registry at fire time; the `Scheduler` class just manages registration.

A job carries its own natural-language description as its only argument.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

DB_PATH = Path(__file__).parent / "db" / "sessions.db"
DB_PATH.parent.mkdir(exist_ok=True)


TaskRunner = Callable[[str], Awaitable[None]]


@dataclass
class ScheduledJob:
    id: str
    description: str
    cron: str
    next_run: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "cron": self.cron,
            "next_run": self.next_run,
        }


# Module-level state so pickled jobs can find the active runner at fire time.
_RUNNERS: dict[str, TaskRunner] = {}
_LOG: dict[str, list[dict[str, Any]]] = {}


def register_runner(scheduler_id: str, runner: TaskRunner) -> None:
    _RUNNERS[scheduler_id] = runner


def unregister_runner(scheduler_id: str) -> None:
    _RUNNERS.pop(scheduler_id, None)


async def run_scheduled_task(scheduler_id: str, description: str) -> None:
    """Top-level coroutine referenced by persisted APScheduler jobs."""
    runner = _RUNNERS.get(scheduler_id)
    log_entries = _LOG.setdefault(scheduler_id, [])
    log_entries.append(
        {"ts": datetime.utcnow().isoformat(), "event": "start", "description": description}
    )
    if runner is None:
        log_entries.append({"ts": datetime.utcnow().isoformat(), "event": "no-runner"})
        return
    try:
        await runner(description)
        log_entries.append({"ts": datetime.utcnow().isoformat(), "event": "ok"})
    except Exception as exc:  # pragma: no cover - defensive
        log_entries.append(
            {"ts": datetime.utcnow().isoformat(), "event": "error", "error": str(exc)}
        )


class Scheduler:
    """Thin async wrapper around APScheduler."""

    _next_id = 0

    def __init__(
        self,
        *,
        task_runner: TaskRunner,
        db_path: Path | str | None = None,
    ) -> None:
        Scheduler._next_id += 1
        self.id = f"sched-{Scheduler._next_id}"
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        jobstores = {
            "default": SQLAlchemyJobStore(url=f"sqlite:///{self._db_path}"),
        }
        self._scheduler = AsyncIOScheduler(jobstores=jobstores)
        register_runner(self.id, task_runner)

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        unregister_runner(self.id)

    # -------------------------------------------------------------- CRUD
    def add(self, description: str, cron: str, *, job_id: str | None = None) -> ScheduledJob:
        trigger = CronTrigger.from_crontab(cron)
        job = self._scheduler.add_job(
            run_scheduled_task,
            trigger=trigger,
            args=[self.id, description],
            id=job_id,
            replace_existing=True,
        )
        return self._to_scheduled(job, description, cron)

    def remove(self, job_id: str) -> bool:
        try:
            self._scheduler.remove_job(job_id)
            return True
        except Exception:
            return False

    def list(self) -> list[ScheduledJob]:
        out: list[ScheduledJob] = []
        for job in self._scheduler.get_jobs():
            description = job.args[1] if len(job.args) > 1 else ""
            cron = _cron_of(job)
            out.append(self._to_scheduled(job, description, cron))
        return out

    def logs(self, job_id: str | None = None) -> list[dict[str, Any]]:
        return list(_LOG.get(self.id, []))

    # -------------------------------------------------------------- internals
    def _to_scheduled(self, job: Any, description: str, cron: str) -> ScheduledJob:
        nxt = getattr(job, "next_run_time", None)
        return ScheduledJob(
            id=job.id,
            description=description,
            cron=cron,
            next_run=nxt.isoformat() if nxt else None,
        )


def _cron_of(job: Any) -> str:
    trig = getattr(job, "trigger", None)
    if trig is None:
        return ""
    fields = getattr(trig, "fields", None) or []
    parts = [str(f) for f in fields[-5:]]
    return " ".join(parts) or str(trig)


async def default_task_runner(description: str) -> None:
    """Placeholder runner used until the FastAPI lifespan installs one."""
    await asyncio.sleep(0)
    print(f"[scheduler] fired task with no runner installed: {description}")
