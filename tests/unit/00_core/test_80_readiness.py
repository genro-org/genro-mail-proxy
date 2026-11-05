# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0

"""Unit tests for MailProxy.check_readiness (backs the /readyz probe)."""

from __future__ import annotations

import pytest
from src.mail_proxy.core import MailProxy


@pytest.mark.asyncio
async def test_not_ready_before_start(tmp_path):
    proxy = MailProxy(db_path=str(tmp_path / "test.db"), test_mode=True)
    await proxy.init()
    try:
        result = await proxy.check_readiness()
        assert result["ready"] is False
        assert result["checks"]["smtp_dispatch"] == "not started"
        assert result["checks"]["database"] == "ok"
    finally:
        await proxy.db.adapter.close()


@pytest.mark.asyncio
async def test_ready_after_start(tmp_path):
    proxy = MailProxy(db_path=str(tmp_path / "test.db"), test_mode=True)
    await proxy.start()
    try:
        result = await proxy.check_readiness()
        assert result["ready"] is True, result
        assert set(result["checks"]) == {"shutdown", "smtp_dispatch", "client_report", "database"}
    finally:
        await proxy.stop()


@pytest.mark.asyncio
async def test_not_ready_after_stop(tmp_path):
    proxy = MailProxy(db_path=str(tmp_path / "test.db"), test_mode=True)
    await proxy.start()
    await proxy.stop()
    result = await proxy.check_readiness()
    assert result["ready"] is False
    assert result["checks"]["shutdown"] == "in progress"
    assert result["checks"]["smtp_dispatch"] == "stopped"


@pytest.mark.asyncio
async def test_database_failure_reported(tmp_path, monkeypatch):
    proxy = MailProxy(db_path=str(tmp_path / "test.db"), test_mode=True)
    await proxy.start()
    try:
        async def boom(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(proxy.db, "fetch_one", boom)
        result = await proxy.check_readiness()
        assert result["ready"] is False
        assert result["checks"]["database"] == "error: RuntimeError"
    finally:
        monkeypatch.undo()
        await proxy.stop()
