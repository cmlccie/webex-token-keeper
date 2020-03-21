"""Webex Token Keeper - AWS Serverless Application."""

import os
import uuid
from pathlib import Path

import boto3
import webexteamssdk
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from mangum import Mangum
from pydantic import BaseModel
from starlette.responses import RedirectResponse


# Module Metadata
__title__ = "Webex Token Keeper"
__description__ = "Store dynamic Webex OAuth tokens and make them " \
                  "accessible via a static key."
__version__ = "0.1"
__author__ = "Chris Lunsford"
__author_email__ = "chris@cmlccie.com"


# Constants
AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME")

WTK_TABLE_NAME = os.environ.get("WTK_TABLE_NAME")

WEBEX_TEAMS_CLIENT_ID = os.environ.get("WEBEX_TEAMS_CLIENT_ID")
WEBEX_TEAMS_CLIENT_SECRET = os.environ.get("WEBEX_TEAMS_CLIENT_SECRET")
WEBEX_TEAMS_REDIRECT_URI = os.environ.get("WEBEX_TEAMS_REDIRECT_URI")
WEBEX_TEAMS_OAUTH_AUTHORIZATION_URL = os.environ.get(
    "WEBEX_TEAMS_OAUTH_AUTHORIZATION_URL"
)

SEVEN_DAYS = 7 * 24 * 60 * 60   # Seven Days in Seconds


# Module Variables
here = Path(__file__).parent.resolve().absolute()

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION_NAME)
table = dynamodb.Table(WTK_TABLE_NAME)

app = FastAPI(
    title=__title__,
    description=__description__,
    version=__version__,
)
templates = Jinja2Templates(directory=here/"templates")

teams_api = webexteamssdk.WebexTeamsAPI("<<no token needed for integration>>")


# Helper Functions
def request_access_token(code: str) -> webexteamssdk.AccessToken:
    """Request an access token from Webex Teams.

    Exchange an OAuth code for a refreshable access token.
    """
    return teams_api.access_tokens.get(
        client_id=WEBEX_TEAMS_CLIENT_ID,
        client_secret=WEBEX_TEAMS_CLIENT_SECRET,
        code=code,
        redirect_uri=WEBEX_TEAMS_REDIRECT_URI,
    )


def refresh_access_token(
    token: webexteamssdk.AccessToken,
) -> webexteamssdk.AccessToken:
    """Refresh a Webex Teams access token."""
    return teams_api.access_tokens.refresh(
        client_id=WEBEX_TEAMS_CLIENT_ID,
        client_secret=WEBEX_TEAMS_CLIENT_SECRET,
        refresh_token=token.refresh_token,
    )


def store_access_token(user_key: str, token: webexteamssdk.AccessToken):
    """Store an access token in DynamoDB."""
    table.put_item(
        Item={
            "user_key": user_key,
            "token": token.to_dict(),
        }
    )


def get_access_token(user_key: str) -> webexteamssdk.AccessToken:
    """Get an access token from DynamoDB; by user_key."""
    try:
        response = table.get_item(Key={'user_key': user_key})
    except ClientError:
        raise HTTPException(status_code=404, detail="Key not found.")
    else:
        token_data = response["Item"]["token"]
        token = webexteamssdk.AccessToken(token_data)

    return token


def delete_access_token(user_key: str):
    """Delete an access token from DynamoDB; by user_key."""
    try:
        response = table.get_item(Key={'user_key': user_key})
    except ClientError:
        raise HTTPException(status_code=404, detail="Key not found.")
    else:
        token_data = response["Item"]["token"]
        token = webexteamssdk.AccessToken(token_data)

    return token


# Data Models
class AccessToken(BaseModel):
    """A Webex Teams access token object."""
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_token_expires_in: int

    class Config:
        orm_mode = True


# Endpoints
@app.get("/", tags=["Pages"])
def start(request: Request):
    """The Webex Token Keeper start page."""
    return templates.TemplateResponse("start.html", {"request": request})


@app.get("/authorize", tags=["Pages"])
def authorize():
    """Redirect authorization requests to the Webex Teams OAuth flow."""
    user_key = uuid.uuid4()
    return RedirectResponse(
        f"{WEBEX_TEAMS_OAUTH_AUTHORIZATION_URL}&state={user_key}"
    )


@app.get("/key", tags=["Pages"])
def get_key(request: Request, state: str, code: str):
    """Final redirect page of the OAuth flow.

    Request and store the access token.  Provide the user with the key and
    API URI they will use to retrieve their access token.
    """
    user_key = state

    # Request an access token
    token = request_access_token(code)

    # Store the access token
    table.put_item(
        Item={
            "user_key": user_key,
            "token": token.to_dict(),
        }
    )

    # Provide the information to the user
    return templates.TemplateResponse(
        "key.html",
        {
            "request": request,
            "user_key": user_key,
            "token_uri": f"/api/token/{user_key}",
            "token": token,
        },
    )


@app.get(
    "/api/token/{key}",
    tags=["API Endpoints"],
    response_model=AccessToken,
)
def get_token(key: str):
    """Retrieve the access token for the provided key; refreshing as needed."""
    # Retrieve the stored access token
    try:
        token = get_access_token(key)
    except ClientError:
        raise HTTPException(status_code=404, detail="Key not found.")

    # Check token expiration and refresh if needed
    if token.expires_in < SEVEN_DAYS:
        token = refresh_access_token(token)
        store_access_token(key, token)

    return AccessToken.from_orm(token)


@app.delete("/api/token/{key}", tags=["API Endpoints"])
def delete_token(key: str):
    """Delete an access token; by key ID."""
    try:
        delete_access_token(key)
    except ClientError:
        raise HTTPException(status_code=404, detail="Key not found.")


# AWS Lambda Handler
handler = Mangum(app)
