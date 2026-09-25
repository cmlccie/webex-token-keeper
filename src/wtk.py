"""Webex Token Keeper - AWS Serverless Application."""

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3
import webexpythonsdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from mangum import Mangum
from pydantic import BaseModel, field_validator
from starlette.responses import RedirectResponse

# Module Metadata
__title__ = "Webex Token Keeper"
__description__ = (
    "Store dynamic Webex OAuth tokens and make them accessible via a static key."
)
__version__ = "0.3"
__author__ = "Chris Lunsford"
__author_email__ = "cm@lunsford.io"
__copyright__ = "Copyright (c) 2020-2026 Chris Lunsford."
__license__ = "MIT"


# Constants
LOG_LEVEL = logging.INFO

AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME")

WTK_TABLE_NAME = os.environ.get("WTK_TABLE_NAME")

WEBEX_INTEGRATION_CLIENT_ID = os.environ.get("WEBEX_INTEGRATION_CLIENT_ID")
WEBEX_INTEGRATION_CLIENT_SECRET = os.environ.get("WEBEX_INTEGRATION_CLIENT_SECRET")
WEBEX_INTEGRATION_REDIRECT_URI = os.environ.get("WEBEX_INTEGRATION_REDIRECT_URI")
WEBEX_INTEGRATION_OAUTH_AUTHORIZATION_URL = os.environ.get(
    "WEBEX_INTEGRATION_OAUTH_AUTHORIZATION_URL"
)

REFRESH_THRESHOLD = timedelta(days=7)


# Module Variables
logger = logging.getLogger(__name__)
logging.getLogger().setLevel(LOG_LEVEL)

here = Path(__file__).parent.resolve().absolute()

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION_NAME)
table = dynamodb.Table(WTK_TABLE_NAME)

app = FastAPI(
    title=__title__,
    description=__description__,
    version=__version__,
)
templates = Jinja2Templates(directory=here / "templates")

webex_api = webexpythonsdk.WebexAPI("<<no token needed for integration>>")


# Data Models
class AccessToken(BaseModel):
    """OAuth generated Access Token; with UTC token expiration timestamps."""

    access_token: str
    expires: datetime
    refresh_token: str
    refresh_token_expires: datetime

    @field_validator("expires", "refresh_token_expires")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        """Treat naive timestamps (stored by earlier versions) as UTC."""
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    @classmethod
    def from_webex_access_token(cls, token: webexpythonsdk.AccessToken):
        """Create a new Access Token from a Webex AccessToken object."""
        now = datetime.now(UTC)
        return cls(
            access_token=token.access_token,
            expires=now + timedelta(seconds=token.expires_in),
            refresh_token=token.refresh_token,
            refresh_token_expires=(
                now + timedelta(seconds=token.refresh_token_expires_in)
            ),
        )


# Helper Functions
def request_access_token(code: str) -> AccessToken:
    """Request an access token from Webex.

    Exchange an OAuth code for an access token.
    """
    logger.info("Requesting an access token")
    webex_token = webex_api.access_tokens.get(
        client_id=WEBEX_INTEGRATION_CLIENT_ID,
        client_secret=WEBEX_INTEGRATION_CLIENT_SECRET,
        code=code,
        redirect_uri=WEBEX_INTEGRATION_REDIRECT_URI,
    )

    return AccessToken.from_webex_access_token(webex_token)


def refresh_access_token(token: AccessToken) -> AccessToken:
    """Refresh a Webex access token."""
    logger.info("Refreshing an access token")
    logger.debug(
        f"Token expires {token.expires.isoformat()}; "
        f"refresh token expires {token.refresh_token_expires.isoformat()}"
    )
    webex_token = webex_api.access_tokens.refresh(
        client_id=WEBEX_INTEGRATION_CLIENT_ID,
        client_secret=WEBEX_INTEGRATION_CLIENT_SECRET,
        refresh_token=token.refresh_token,
    )

    new_token = AccessToken.from_webex_access_token(webex_token)
    logger.debug(f"Refreshed token expires {new_token.expires.isoformat()}")

    return new_token


def store_access_token(user_key: str, token: AccessToken):
    """Store an access token in DynamoDB."""
    logger.info("Storing an access token in DynamoDB")
    table.put_item(
        Item={
            "user_key": user_key,
            # DynamoDB doesn't support datetimes; store JSON-serializable data
            "token": token.model_dump(mode="json"),
        }
    )


def get_access_token(user_key: str) -> AccessToken | None:
    """Get an access token from DynamoDB; by user_key."""
    logger.info("Getting an access token from DynamoDB")
    response = table.get_item(Key={"user_key": user_key})
    item = response.get("Item")
    return AccessToken(**item["token"]) if item else None


def delete_access_token(user_key: str) -> bool:
    """Delete an access token from DynamoDB; by user_key.

    Returns True if a token was deleted, False if the key was not found.
    """
    logger.info("Deleting an access token from DynamoDB")
    response = table.delete_item(Key={"user_key": user_key}, ReturnValues="ALL_OLD")
    return "Attributes" in response


# Endpoints
@app.get("/", tags=["Pages"])
def start_page(request: Request):
    """The Webex Token Keeper start page."""
    logger.info("Serving start page")
    return templates.TemplateResponse(request, "start.html")


@app.get("/authorize", tags=["Pages"])
def authorization_redirect():
    """Redirect authorization requests to the Webex OAuth flow."""
    logger.info("Redirecting to Webex OAuth flow")
    user_key = uuid.uuid4()
    return RedirectResponse(
        f"{WEBEX_INTEGRATION_OAUTH_AUTHORIZATION_URL}&state={user_key}"
    )


@app.get("/key", tags=["Pages"])
def key_page(request: Request, state: str, code: str):
    """Success page at the end of the OAuth flow."""
    logger.info("Serving key page")
    user_key = state

    # Request an access token
    token = request_access_token(code)

    # Store the access token
    store_access_token(user_key, token)

    # Provide the information to the user
    return templates.TemplateResponse(
        request,
        "key.html",
        {
            "user_key": user_key,
            "token_uri": f"/api/token/{user_key}",
            "token": token.model_dump_json(indent=2),
        },
    )


@app.get(
    "/api/token/{key}",
    tags=["API Endpoints"],
    response_model=AccessToken,
)
def get_token(key: str):
    """Retrieve the access token for the provided key; refreshing as needed."""
    logger.info("Serving API request to retrieve an access token")
    token = get_access_token(key)
    if token is None:
        raise HTTPException(status_code=404, detail="Key not found.")

    # Check token expiration and refresh if needed
    if (token.expires - datetime.now(UTC)) < REFRESH_THRESHOLD:
        token = refresh_access_token(token)
        store_access_token(key, token)

    return token


@app.delete("/api/token/{key}", tags=["API Endpoints"])
def delete_token(key: str):
    """Delete an access token; by key ID."""
    logger.info("Serving API request to delete an access token")
    if not delete_access_token(key):
        raise HTTPException(status_code=404, detail="Key not found.")


# AWS Lambda Handler
handler = Mangum(app)
