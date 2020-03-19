"""Webex Token Keeper - AWS Serverless Application."""

from fastapi import FastAPI
from mangum import Mangum


app = FastAPI()


@app.get("/")
def home():
    return {"Hello": "World!"}


handler = Mangum(app)
