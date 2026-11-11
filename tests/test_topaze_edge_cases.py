"""Reject ambiguous protocol answers and finish cleanup during cancellation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from pydiagral.exceptions import (
    AuthenticationError,
    ClientError,
    DiagralAPIError,
    ValidationError,
)

from .test_topaze_api import client, responses
from .test_topaze_command_confirmation import make_api


@pytest.mark.parametrize(
    ("answers", "error", "last_endpoint"),
    [
        ([{"sessionId": None}], AuthenticationError, "authenticate/login"),
        (
            [{"sessionId": "own-login"}, {"systems": None}, {"status": "OK"}],
            ValidationError,
            "authenticate/logout",
        ),
        (
            [{"sessionId": "own-login"}, {"systems": [None]}, {"status": "OK"}],
            ValidationError,
            "authenticate/logout",
        ),
        (
            [
                {"sessionId": "own-login"},
                {"systems": [{"id": 1, "role": 1}]},
                {"transmitterId": "1234567890", "centralId": None},
                {"status": "OK"},
            ],
            ValidationError,
            "authenticate/logout",
        ),
    ],
    ids=["no-login-token", "no-systems-list", "invalid-system", "no-central-id"],
)
async def test_bad_session_metadata_never_connects(answers, error, last_endpoint):
    """Malformed identity metadata cannot reach the central connection step."""
    api = client()
    api._topaze_call = AsyncMock(side_effect=answers)  # noqa: SLF001
    with pytest.raises(error):
        async with api._topaze_session():  # noqa: SLF001
            pytest.fail("Malformed metadata must not create a connection")
    endpoints = [call.args[1] for call in api._topaze_call.call_args_list]  # noqa: SLF001
    assert "authenticate/connect" not in endpoints
    assert endpoints[-1] == last_endpoint


async def test_disconnect_failure_preserves_original_error_and_attempts_logout(caplog):
    """A cleanup failure must neither hide the read error nor expose its body."""
    api = client()
    answers = responses()
    answers[-2] = ClientError("synthetic-private-server-reply")
    api._topaze_call = AsyncMock(side_effect=answers)  # noqa: SLF001
    with pytest.raises(ValidationError, match="Original read failure"):
        async with api._topaze_session():  # noqa: SLF001
            raise ValidationError("Original read failure")
    assert api._topaze_call.call_args_list[-1].args[1] == "authenticate/logout"  # noqa: SLF001
    assert "ClientError" in caplog.text
    assert "synthetic-private-server-reply" not in caplog.text


async def test_cancellation_during_cleanup_keeps_lock_until_owned_session_closes():
    """A second operation cannot open a session while cancelled cleanup is pending."""
    api = client()
    started, release = asyncio.Event(), asyncio.Event()
    answers = iter(responses())

    async def answer(_method, endpoint, **_kwargs):
        response = next(answers)
        if endpoint == "authenticate/disconnect":
            started.set()
            await release.wait()
        return response

    api._topaze_call = AsyncMock(side_effect=answer)  # noqa: SLF001

    async def operation():
        async with api._topaze_session():  # noqa: SLF001
            pass

    task = asyncio.create_task(operation())
    try:
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert api._topaze_lock.locked()  # noqa: SLF001
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert api._topaze_call.call_args_list[-1].args[1] == "authenticate/logout"  # noqa: SLF001
    assert not api._topaze_lock.locked()  # noqa: SLF001


def _inventory_context():
    return SimpleNamespace(
        token="synthetic-token",
        ttm="synthetic-ttm",
        config={"id": 1, "centralId": "central", "transmitterId": "box"},
        connected={"versions": {"box": "1.0"}},
    )


async def test_inventory_rejection_is_not_treated_as_empty_acknowledgement():
    """Only successful empty acknowledgements permit polling a read job."""
    api = client()
    api._topaze_call = AsyncMock(  # noqa: SLF001
        side_effect=ValidationError("Rejected request", status_code=422)
    )
    with pytest.raises(ValidationError, match="Rejected request"):
        await api._read_inventory(_inventory_context())  # noqa: SLF001
    api._topaze_call.assert_awaited_once()  # noqa: SLF001


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        ({"status": "request_status_done", "response": "{"}, ValidationError),
        ({"status": "request_status_done", "response": []}, ValidationError),
        ({"status": "request_status_failed"}, DiagralAPIError),
    ],
    ids=["invalid-json", "invalid-object", "failed-job"],
)
async def test_invalid_inventory_completion_never_becomes_configuration(reply, error):
    """A valid job acknowledgement does not certify the final payload."""
    api = client()
    api._topaze_call = AsyncMock(side_effect=[{}, reply])  # noqa: SLF001
    with (
        patch("pydiagral.topaze_api.asyncio.sleep", AsyncMock()),
        pytest.raises(error),
    ):
        await api._read_inventory(_inventory_context())  # noqa: SLF001
    assert api._topaze_call.await_count == 2  # noqa: SLF001


async def test_pending_inventory_job_is_polled_until_completed():
    """An unfinished read can complete without submitting a second job."""
    api = client()
    api._topaze_call = AsyncMock(  # noqa: SLF001
        side_effect=[
            {},
            {"status": "request_status_pending"},
            {"status": "request_status_done", "response": {"example": {}}},
        ]
    )
    with patch("pydiagral.topaze_api.asyncio.sleep", AsyncMock()):
        assert await api._read_inventory(_inventory_context()) == {"example": {}}  # noqa: SLF001
    assert [call.args[0] for call in api._topaze_call.call_args_list] == [  # noqa: SLF001
        "POST",
        "GET",
        "GET",
    ]


async def test_rejected_command_is_not_replayed_or_confirmed_with_status():
    """A negative acknowledgement must remain a failed single command."""
    api = make_api([{"commandStatus": "CMD_REJECTED"}])
    with pytest.raises(DiagralAPIError, match="not confirmed"):
        await api.stop_system()
    api._topaze_call.assert_awaited_once()  # noqa: SLF001
