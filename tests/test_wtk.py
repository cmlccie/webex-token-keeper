"""Tests for the Webex Token Keeper service."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def webex_token(access_token="access", refresh_token="refresh"):
    """A stand-in for a webexpythonsdk AccessToken."""
    return SimpleNamespace(
        access_token=access_token,
        expires_in=int(timedelta(days=14).total_seconds()),
        refresh_token=refresh_token,
        refresh_token_expires_in=int(timedelta(days=90).total_seconds()),
    )


def make_token(wtk, expires_in: timedelta):
    now = datetime.now(UTC)
    return wtk.AccessToken(
        access_token="stored",
        expires=now + expires_in,
        refresh_token="stored-refresh",
        refresh_token_expires=now + timedelta(days=90),
    )


# Data model
def test_naive_timestamps_are_treated_as_utc(wtk):
    token = wtk.AccessToken(
        access_token="a",
        expires="2025-01-01T00:00:00",
        refresh_token="r",
        refresh_token_expires="2025-03-01T00:00:00.123456",
    )
    assert token.expires == datetime(2025, 1, 1, tzinfo=UTC)
    assert token.refresh_token_expires.tzinfo is UTC


def test_store_and_get_round_trip(wtk):
    token = make_token(wtk, timedelta(days=10))
    wtk.store_access_token("key", token)
    assert wtk.get_access_token("key") == token


def test_get_missing_token_returns_none(wtk):
    assert wtk.get_access_token("missing") is None


# Pages
def test_start_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/authorize"' in response.text


def test_authorize_redirects_to_webex_with_state(client, wtk):
    response = client.get("/authorize")
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith(wtk.WEBEX_INTEGRATION_OAUTH_AUTHORIZATION_URL)
    assert "&state=" in location


def test_key_page_exchanges_code_and_stores_token(client, wtk):
    with patch.object(
        wtk.webex_api.access_tokens, "get", return_value=webex_token()
    ) as get:
        response = client.get("/key", params={"state": "user-key", "code": "abc"})

    assert response.status_code == 200
    assert "user-key" in response.text
    assert "/api/token/user-key" in response.text
    get.assert_called_once_with(
        client_id="client-id",
        client_secret="client-secret",
        code="abc",
        redirect_uri="https://wtk.example.com/key",
    )
    assert wtk.get_access_token("user-key").access_token == "access"


# API
def test_get_token(client, wtk):
    token = make_token(wtk, timedelta(days=10))
    wtk.store_access_token("key", token)

    with patch.object(wtk.webex_api.access_tokens, "refresh") as refresh:
        response = client.get("/api/token/key")

    assert response.status_code == 200
    assert wtk.AccessToken(**response.json()) == token
    refresh.assert_not_called()


@pytest.mark.parametrize("expires_in", [timedelta(days=6), timedelta(days=-1)])
def test_get_token_refreshes_expiring_token(client, wtk, expires_in):
    wtk.store_access_token("key", make_token(wtk, expires_in))

    with patch.object(
        wtk.webex_api.access_tokens,
        "refresh",
        return_value=webex_token("new-access", "new-refresh"),
    ) as refresh:
        response = client.get("/api/token/key")

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access"
    refresh.assert_called_once_with(
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="stored-refresh",
    )
    assert wtk.get_access_token("key").access_token == "new-access"


def test_get_token_with_legacy_naive_timestamps(client, wtk):
    """Tokens stored by earlier versions have naive (UTC) ISO timestamps."""
    expires = datetime.now(UTC) + timedelta(days=10)
    wtk.table.put_item(
        Item={
            "user_key": "legacy",
            "token": {
                "access_token": "legacy",
                "expires": expires.replace(tzinfo=None).isoformat(),
                "refresh_token": "legacy-refresh",
                "refresh_token_expires": (
                    (expires + timedelta(days=80)).replace(tzinfo=None).isoformat()
                ),
            },
        }
    )

    response = client.get("/api/token/legacy")

    assert response.status_code == 200
    assert response.json()["access_token"] == "legacy"


def test_get_missing_token_returns_404(client):
    response = client.get("/api/token/missing")
    assert response.status_code == 404


def test_delete_token(client, wtk):
    wtk.store_access_token("key", make_token(wtk, timedelta(days=10)))

    response = client.delete("/api/token/key")

    assert response.status_code == 200
    assert wtk.get_access_token("key") is None


def test_delete_missing_token_returns_404(client):
    response = client.delete("/api/token/missing")
    assert response.status_code == 404


def test_lambda_handler_serves_api_gateway_events(wtk):
    event = {
        "resource": "/",
        "path": "/",
        "httpMethod": "GET",
        "headers": {"Host": "wtk.example.com"},
        "multiValueHeaders": {"Host": ["wtk.example.com"]},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": None,
        "stageVariables": None,
        "requestContext": {
            "resourcePath": "/",
            "httpMethod": "GET",
            "path": "/Prod/",
            "stage": "Prod",
            "identity": {"sourceIp": "127.0.0.1"},
        },
        "body": None,
        "isBase64Encoded": False,
    }
    context = SimpleNamespace(aws_request_id="test")

    response = wtk.handler(event, context)

    assert response["statusCode"] == 200
    assert "Webex Token Keeper" in response["body"]
