import asyncio
from datetime import datetime, timedelta

import pytest

from backend.scheduler import Scheduler


pytestmark = pytest.mark.asyncio


async def test_add_and_remove(tmp_path):
    ran: list[str] = []

    async def runner(task: str) -> None:
        ran.append(task)

    sched = Scheduler(task_runner=runner, db_path=tmp_path / "jobs.db")
    sched.start()
    try:
        job = sched.add("test task", "0 0 * * *", job_id="j1")
        assert job.id == "j1"
        assert job.description == "test task"
        listed = sched.list()
        assert any(j.id == "j1" for j in listed)
        assert sched.remove("j1") is True
        assert not any(j.id == "j1" for j in sched.list())
    finally:
        sched.shutdown()


async def test_cron_string_roundtrips_unchanged(tmp_path):
    """Regression: schedules used to come back with mangled cron fields
    (e.g. '0 9 * * *' returned as '* * 9 0 0')."""

    async def runner(task: str) -> None:
        pass

    sched = Scheduler(task_runner=runner, db_path=tmp_path / "jobs.db")
    sched.start()
    try:
        sched.add("morning ping", "0 9 * * *", job_id="morning")
        sched.add("every 5 min", "*/5 * * * *", job_id="every5")
        listed = {j.id: j.cron for j in sched.list()}
        assert listed["morning"] == "0 9 * * *"
        assert listed["every5"] == "*/5 * * * *"
    finally:
        sched.shutdown()


async def test_remove_missing_returns_false(tmp_path):
    async def runner(task: str) -> None:
        pass

    sched = Scheduler(task_runner=runner, db_path=tmp_path / "jobs.db")
    sched.start()
    try:
        assert sched.remove("does-not-exist") is False
    finally:
        sched.shutdown()
