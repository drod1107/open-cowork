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


async def test_remove_missing_returns_false(tmp_path):
    async def runner(task: str) -> None:
        pass

    sched = Scheduler(task_runner=runner, db_path=tmp_path / "jobs.db")
    sched.start()
    try:
        assert sched.remove("does-not-exist") is False
    finally:
        sched.shutdown()
