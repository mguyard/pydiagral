"""Regression tests for transport failures, secret-safe errors and notifications.

Public API tests mock ``_request`` as usual. Tests of ``_request`` itself use a
minimal response/session double so HTTP parsing can be checked without network
access or patching aiohttp's implementation.
"""

import logging
import traceback
from types import SimpleNamespace, TracebackType
from typing import Any, Self
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from pydiagral.api import DiagralAPI
from pydiagral.constants import REDACTED
from pydiagral.exceptions import (
    AuthenticationError,
    ClientError,
    DiagralAPIError,
    ModelValidationError,
    ServerError,
    ValidationError,
)
from pydiagral.models import ApiKeyWithSecret, WebHookNotification


class Response:
    """Supply the asynchronous response context consumed by ``_request``."""

    def __init__(
        self, status: int = 200, payload: Any = None, error: Exception | None = None
    ) -> None:
        """Set the HTTP status and simulated JSON response."""
        self.status = status
        self.json = AsyncMock(return_value=payload, side_effect=error)

    async def __aenter__(self) -> Self:
        """Enter the response context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        """Keep exceptions raised while handling the response visible."""
        return False


@pytest.fixture
def api() -> DiagralAPI:
    """Create a client with synthetic credentials and no network session."""
    return DiagralAPI(
        "audit@example.com",
        "private-password",
        "fake-serial",
        "private-api-key",
        "private-secret-key",
        "1234",
    )


def install_response(
    api: DiagralAPI,
    status: int = 200,
    payload: Any = None,
    error: Exception | None = None,
) -> Response:
    """Provide a response without constructing a real HTTP connection."""
    response = Response(status, payload, error)
    api.session = SimpleNamespace(request=Mock(return_value=response))
    return response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (422, ValidationError),
        (500, ServerError),
        (502, ServerError),
        (503, ServerError),
        (504, ServerError),
        (400, DiagralAPIError),
        (404, DiagralAPIError),
        (429, DiagralAPIError),
    ],
)
async def test_http_status_determines_error_even_with_non_json_body(
    api: DiagralAPI, status: int, exception: type[DiagralAPIError]
) -> None:
    """Recognize proxy HTML errors without masking their HTTP status."""
    response = install_response(
        api, status, error=aiohttp.ContentTypeError(None, (), message="HTML")
    )
    with pytest.raises(exception) as caught:
        await api._request("GET", "fake")  # noqa: SLF001 - exercise the transport boundary.
    assert caught.value.status_code == status
    assert "Diagral" in str(caught.value)
    assert f"(HTTP {status})" in str(caught.value)
    if status in (401, 403, 422) or status >= 500:
        response.json.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [204, 205])
async def test_empty_success_does_not_parse_json(api: DiagralAPI, status: int) -> None:
    """Accept successful responses with no body."""
    response = install_response(api, status, error=AssertionError("No body"))
    assert await api._request("DELETE", "fake") == ({}, status)  # noqa: SLF001
    response.json.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], None, "text"])
async def test_success_requires_valid_object(api: DiagralAPI, payload: Any) -> None:
    """Reject JSON responses which cannot be mapped to API models."""
    install_response(api, 200, payload)
    with pytest.raises(ValidationError) as caught:
        await api._request("GET", "fake")  # noqa: SLF001
    assert caught.value.status_code == 200
    assert "Diagral" in str(caught.value)
    assert "(HTTP 200)" in str(caught.value)


@pytest.mark.asyncio
async def test_success_rejects_malformed_json(api: DiagralAPI) -> None:
    """Report invalid JSON separately from HTTP and network failures."""
    install_response(api, 200, error=ValueError("invalid JSON"))
    with pytest.raises(ValidationError) as caught:
        await api._request("GET", "fake")  # noqa: SLF001
    assert caught.value.status_code == 200
    assert "Diagral" in str(caught.value)
    assert "(HTTP 200)" in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [aiohttp.ClientConnectionError("offline"), TimeoutError()]
)
async def test_network_and_timeout_are_not_authentication_errors_or_retried(
    api: DiagralAPI, error: Exception
) -> None:
    """Classify transport failure without repeating a command."""
    request = Mock(side_effect=error)
    api.session = SimpleNamespace(request=request)
    with pytest.raises(ClientError):
        await api._request("POST", "fake-command")  # noqa: SLF001
    request.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ServerError("offline", 503), ClientError("timeout")])
async def test_login_preserves_transient_error_category(
    api: DiagralAPI, error: DiagralAPIError
) -> None:
    """Do not turn a cloud outage into an invalid-credentials error."""
    api.session = SimpleNamespace()
    with (
        patch.object(api, "_request", new=AsyncMock(side_effect=error)),
        pytest.raises(type(error)) as caught,
    ):
        await api.login()
    assert caught.value is error


@pytest.mark.asyncio
async def test_no_anomalies_and_subscription_conflict_are_preserved(
    api: DiagralAPI,
) -> None:
    """Preserve recognized protocol details while removing private suffixes."""
    install_response(api, 404, {"detail": "No anomalies found for private-serial"})
    assert await api.get_anomalies() == {}
    install_response(
        api, 400, {"detail": "Subscription already exists for private-serial"}
    )
    with pytest.raises(DiagralAPIError, match="subscription already exists"):
        await api.register_webhook("https://example.com/hook", subscribe_to_state=True)


@pytest.mark.parametrize(
    ("detail", "missing_subscription"),
    [
        ("No subscription found for private-serial", True),
        ("Unknown endpoint for private-serial", False),
    ],
    ids=["missing-subscription", "unrelated-404"],
)
async def test_get_webhook_preserves_missing_subscription_without_private_detail(
    api: DiagralAPI, detail: str, missing_subscription: bool
) -> None:
    """Keep HA's no-subscription signal through the real HTTP error handler."""
    install_response(api, 404, {"detail": detail})
    with pytest.raises(DiagralAPIError) as caught:
        await api.get_webhook()
    message = str(caught.value)
    assert ("No subscription found for" in message) is missing_subscription
    assert caught.value.status_code == 404
    assert "Diagral" in message
    assert "(HTTP 404)" in message
    assert "private-serial" not in message
    assert "private-api-key" not in message
    api.session.request.assert_called_once()
    method, url = api.session.request.call_args.args
    assert method == "GET"
    assert url.endswith("/webhooks/fake-serial/subscription")


@pytest.mark.asyncio
async def test_secrets_do_not_appear_in_debug_logs_or_error_messages(
    api: DiagralAPI, caplog: pytest.LogCaptureFixture
) -> None:
    """Exclude credentials, payloads and URLs from diagnostics."""
    caplog.set_level(logging.DEBUG, logger="pydiagral")
    install_response(api, 200, {"access_token": "private-bearer-token"})
    await api.login()
    ApiKeyWithSecret.from_dict(
        {"api_key": "private-new-key", "secret_key": "private-new-secret"}
    )
    install_response(api, 400, {"detail": "private-password private-new-secret"})
    with pytest.raises(DiagralAPIError) as caught:
        await api._request(  # noqa: SLF001
            "DELETE",
            "users/systems/fake-serial/api_keys/private-url-key",
            headers={"X-PIN-CODE": "1234", "Authorization": "private-bearer-token"},
            log_endpoint=f"users/systems/fake-serial/api_keys/{REDACTED}",
        )
    output = caplog.text + str(caught.value)
    for secret in (
        "private-password",
        "private-api-key",
        "private-secret-key",
        "private-bearer-token",
        "private-new-key",
        "private-new-secret",
        "private-url-key",
        "1234",
    ):
        assert secret not in output
    assert "audit@example.com" in caplog.text
    assert "**REDACTED**" in caplog.text


@pytest.mark.asyncio
async def test_webhook_callback_url_is_redacted(
    api: DiagralAPI, caplog: pytest.LogCaptureFixture
) -> None:
    """Keep the callback's capability secret in redacted request/model logs."""
    caplog.set_level(logging.DEBUG, logger="pydiagral")
    callback_url = "https://example.com/api/webhook/private-callback-token"
    install_response(api, 200, {})
    await api._request(  # noqa: SLF001
        "POST", "webhooks/fake-serial/subscription", json={"webhook_url": callback_url}
    )
    assert callback_url not in caplog.text
    assert "private-callback-token" not in caplog.text
    assert f"https://example.com/{REDACTED}" in caplog.text
    assert "webhooks/fake-serial/subscription" in caplog.text
    assert "**REDACTED**" in caplog.text


@pytest.mark.asyncio
async def test_ephemeral_keys_are_cleared_after_success() -> None:
    """Remove deleted temporary keys from both the result and client memory."""
    api = DiagralAPI("audit@example.com", "password", "serial", pincode="1234")
    api.session = SimpleNamespace()
    with patch.object(
        api,
        "_request",
        new=AsyncMock(
            side_effect=[
                ({"access_token": "token"}, 200),
                ({"api_key": "key", "secret_key": "secret"}, 200),
                ({"api_keys": [{"api_key": "key"}]}, 200),
                ({}, 200),
                ({}, 204),
            ]
        ),
    ):
        result = await api.try_connection(ephemeral=True)
    assert result.result
    assert result.keys is None
    assert api._DiagralAPI__apikey is None  # noqa: SLF001 - verify secret cleanup.
    assert api._DiagralAPI__secret_key is None  # noqa: SLF001


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_error", [None, ClientError("cleanup unavailable")])
async def test_ephemeral_cleanup_preserves_original_connection_failure(
    cleanup_error: DiagralAPIError | None,
) -> None:
    """Attempt temporary-key deletion without masking the failed status read."""
    api = DiagralAPI("audit@example.com", "password", "serial", pincode="1234")
    api.session = SimpleNamespace()
    original_error = ServerError("status unavailable", 503)
    with (
        patch.object(
            api,
            "_request",
            new=AsyncMock(
                side_effect=[
                    ({"access_token": "token"}, 200),
                    ({"api_key": "key", "secret_key": "secret"}, 200),
                    ({"api_keys": [{"api_key": "key"}]}, 200),
                    original_error,
                    cleanup_error or ({}, 204),
                ]
            ),
        ) as request,
        pytest.raises(ServerError) as caught,
    ):
        await api.try_connection(ephemeral=True)
    assert caught.value is original_error
    assert request.await_count == 5
    assert request.call_args.args[0] == "DELETE"
    if cleanup_error is None:
        assert api._DiagralAPI__apikey is None  # noqa: SLF001 - verify successful deletion.
        assert api._DiagralAPI__secret_key is None  # noqa: SLF001


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ServerError("offline", 503), ClientError("timeout")])
async def test_key_creation_preserves_transient_error_category(
    api: DiagralAPI, error: DiagralAPIError
) -> None:
    """Keep cloud/transport failures distinguishable from a rejected API key."""
    api.session = SimpleNamespace()
    with (
        patch.object(
            api,
            "_request",
            new=AsyncMock(
                side_effect=[
                    ({"access_token": "token"}, 200),
                    error,
                ]
            ),
        ),
        pytest.raises(type(error)) as caught,
    ):
        await api.set_apikey()
    assert caught.value is error


@pytest.mark.asyncio
async def test_transport_exception_traceback_does_not_expose_private_url(
    api: DiagralAPI,
) -> None:
    """Suppress transport exception context which can contain secret URLs."""
    api.session = SimpleNamespace(
        request=Mock(side_effect=aiohttp.ClientConnectionError("private-url-key"))
    )
    with pytest.raises(ClientError) as caught:
        await api._request("DELETE", "fake")  # noqa: SLF001
    rendered = "".join(traceback.format_exception(caught.value))
    assert "private-url-key" not in rendered


@pytest.fixture
def notification() -> dict[str, Any]:
    """Supply the required notification fields with no optional objects."""
    return {
        "transmitter_id": "fake-serial",
        "alarm_code": "3401",
        "date_time": "2026-10-22T10:00:00Z",
    }


@pytest.mark.parametrize(
    "additional", [{}, {"detail": None, "user": None, "group_index": None}]
)
def test_optional_fields_can_be_absent_or_null(
    notification: dict[str, Any], additional: dict[str, Any]
) -> None:
    """Accept notifications with absent or explicitly null optional data."""
    data = WebHookNotification.from_dict({**notification, **additional})
    assert data.alarm_type == "STATUS"
    assert data.detail.device_type is None
    assert data.detail.device_index is None
    assert data.user is None
    assert data.group_index is None


def test_numeric_indexes_and_unknown_code_are_preserved(
    notification: dict[str, Any],
) -> None:
    """Normalize numeric indexes while preserving unknown event codes."""
    data = WebHookNotification.from_dict(
        {
            **notification,
            "alarm_code": 9999,
            "group_index": 2,
            "detail": {"device_index": 3},
        }
    )
    assert (
        data.alarm_type,
        data.alarm_code,
        data.group_index,
        data.detail.device_index,
    ) == (
        "UNKNOWN",
        "9999",
        "2",
        "3",
    )


@pytest.mark.parametrize(
    "replacement",
    [
        {"transmitter_id": None},
        {"alarm_code": None},
        {"alarm_code": True},
        {"alarm_code": "wrong"},
        {"alarm_code": "²"},
        {"alarm_code": "1" * 5000},
        {"date_time": None},
        {"date_time": "not-a-date"},
        {"detail": []},
        {"user": "bad"},
        {"group_index": []},
        {"detail": {"device_index": {}}},
        {"user": {"username": []}},
    ],
)
def test_invalid_notification_field_raises_value_error(
    notification: dict[str, Any], replacement: dict[str, Any]
) -> None:
    """Reject malformed fields with a consistent, safe validation error."""
    with pytest.raises(ModelValidationError) as caught:
        WebHookNotification.from_dict({**notification, **replacement})
    assert isinstance(caught.value, ValueError)


@pytest.mark.parametrize("payload", [None, [], "bad", {}])
def test_invalid_notification_raises_value_error(payload: Any) -> None:
    """Reject non-object or incomplete notifications predictably."""
    with pytest.raises(ModelValidationError) as caught:
        WebHookNotification.from_dict(payload)
    assert isinstance(caught.value, ValueError)


def test_invalid_notification_date_does_not_expose_payload(
    notification: dict[str, Any],
) -> None:
    """Keep the parser's raw input out of a logged validation traceback."""
    payload = {**notification, "date_time": "private-value"}
    with pytest.raises(ModelValidationError) as caught:
        WebHookNotification.from_dict(payload)
    assert "private-value" not in "".join(traceback.format_exception(caught.value))
