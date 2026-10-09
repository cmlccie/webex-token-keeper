"""Shared fixtures: a moto-backed DynamoDB table and the wtk app client."""

import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

TABLE_NAME = "webex-token-keeper-test"

os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION_NAME": "us-east-1",
        "WTK_TABLE_NAME": TABLE_NAME,
        "WEBEX_INTEGRATION_CLIENT_ID": "client-id",
        "WEBEX_INTEGRATION_CLIENT_SECRET": "client-secret",
        "WEBEX_INTEGRATION_REDIRECT_URI": "https://wtk.example.com/key",
        "WEBEX_INTEGRATION_OAUTH_AUTHORIZATION_URL": (
            "https://webexapis.com/v1/authorize?client_id=client-id"
        ),
    }
)


@pytest.fixture
def aws():
    """Mock AWS and create an empty token table for each test."""
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[{"AttributeName": "user_key", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "user_key", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def wtk(aws):
    """The wtk module (imported after the environment is configured)."""
    import wtk

    return wtk


@pytest.fixture
def client(wtk):
    """A test client for the wtk FastAPI app."""
    return TestClient(wtk.app, follow_redirects=False)
