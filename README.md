# Webex Token Keeper

_Store dynamic Webex OAuth tokens and make them accessible via a static key._

---

Webex Personal Access Tokens expire in twelve (12) hours. Webex Integration OAuth access tokens expire in about fourteen (14) days and may be refreshed; however, generating OAuth tokens requires a web service and human interaction. What if you need a static configuration that can access the Webex APIs (CI/CD tools, backend automation, etc.)?

> How can you programmatically obtain a Webex API access token with a fixed identifier?

It takes a small web service.

## Simple Microservice Provides Programmatic Access to OAuth Generated Access Tokens

Webex Token Keeper (WTK) implements the Webex Integration OAuth flow and stores the OAuth generated Access Token for future retrieval. The Access Token is stored using a randomly generated key, which is provided to the user at the end of the OAuth flow. WTK provides a simple REST API that provides programmatic access to the stored token.

WTK automatically refreshes the token when a stored token is requested via the REST API (if the token expires in less than seven days). Webex refresh tokens are valid for about ninety (90) days, so retrieve your token periodically to give WTK the chance to refresh it before the refresh token expires.

## Features

- Python implementation of the Webex Integration/OAuth process
- Store OAuth generated access tokens for programmatic retrieval
- REST API for retrieving and deleting stored access tokens
- OpenAPI (Swagger) interactive REST API docs
- Serverless (AWS Lambda) microservice
- Fully automated deployment via SAM template

## Tech Stack

- [FastAPI](https://fastapi.tiangolo.com/) Web Service
- [Webex Python SDK](https://github.com/WebexCommunity/WebexPythonSDK) OAuth token exchange and refresh
- [Pydantic](https://docs.pydantic.dev/) Data Models
- [AWS API Gateway](https://aws.amazon.com/api-gateway/) w/Custom Domain Support
- [AWS Lambda](https://aws.amazon.com/lambda/) Serverless App
- [AWS DynamoDB](https://aws.amazon.com/dynamodb/) Database
- [CloudFormation (SAM) Template](https://aws.amazon.com/cloudformation/) Parameterized and Fully-Automated Deployment

## Using the API

After you complete the OAuth flow on the start page, WTK shows your **user key**. Treat it like a password: anyone who has it can retrieve your access token.

```bash
# Retrieve the current access token (refreshed automatically when needed)
curl -s https://<your-domain>/api/token/<user-key> | jq -r .access_token

# Delete the stored token
curl -X DELETE https://<your-domain>/api/token/<user-key>
```

| Method   | Path               | Response                                                                 |
| -------- | ------------------ | ------------------------------------------------------------------------ |
| `GET`    | `/api/token/{key}` | `200` with `access_token`, `expires`, `refresh_token`, `refresh_token_expires` (UTC ISO-8601); `404` if the key is unknown |
| `DELETE` | `/api/token/{key}` | `200` when deleted; `404` if the key is unknown                          |

Interactive OpenAPI docs are served at `/docs`.

## Deploy Your Own

### Prerequisites

1. An AWS account with the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   installed and [configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

2. The [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)

3. A custom DNS domain hosted in an AWS [Route 53](https://aws.amazon.com/route53/) hosted zone

4. A certificate for your custom domain in AWS
   [Certificate Manager](https://aws.amazon.com/certificate-manager/) (in the same region as the API)

5. A [Webex Integration](https://developer.webex.com/docs/integrations) whose redirect URI is
   `https://<your-domain>/key`

6. Python 3.12+ and [Poetry](https://python-poetry.org/) 2.x

### Deploy

The [SAM template](template.yml) provisions everything: the DynamoDB table, Lambda function, API Gateway, and custom domain name. It takes these parameters:

| Parameter                               | Description                                                                 |
| --------------------------------------- | --------------------------------------------------------------------------- |
| `DomainName`                            | Custom domain name for the API (e.g. `wtk.example.com`)                     |
| `HostedZoneId`                          | Route 53 hosted zone ID for the domain                                      |
| `CertificateArn`                        | ACM certificate ARN for the domain                                          |
| `TableName`                             | DynamoDB table name (default: `webex-token-keeper`)                         |
| `WebexIntegrationClientId`              | Webex Integration client ID                                                 |
| `WebexIntegrationClientSecret`          | Webex Integration client secret                                             |
| `WebexIntegrationRedirectUri`           | `https://<your-domain>/key`                                                 |
| `WebexIntegrationRedirectUriUrlEncoded` | The redirect URI, URL-encoded (`https%3A%2F%2F<your-domain>%2Fkey`)         |
| `WebexIntegrationOauthAuthorizationUrl` | `https://webexapis.com/v1/authorize`                                        |
| `WebexIntegrationOauthScopes`           | Comma-separated OAuth scopes (e.g. `spark:all`)                             |

The first time, run a guided deployment to enter the parameters and save them to your own `samconfig.toml`:

```bash
poetry install
sam build && sam deploy --guided
```

After that, `make deploy` formats, lints, tests, builds, and deploys. The SAM template is idempotent; rerun `make deploy` to push parameter, template, or code changes.

> [!NOTE]
> The `samconfig.toml` in this repository is the maintainer's deployment configuration and is encrypted with [git-crypt](https://github.com/AGWA/git-crypt). Delete it (or overwrite it with `sam deploy --guided`) in your fork.

## Development

```bash
make setup    # install dependencies (poetry install)
make test     # run the test suite (pytest + moto; no AWS account needed)
make lint     # format and lint with ruff
make check    # non-mutating checks, the same as CI
make update   # update dependencies and regenerate src/requirements.txt
```

`src/requirements.txt` is what SAM packages into the Lambda function. It is generated from `poetry.lock` by `make update`; don't edit it by hand.

## License

[MIT](LICENSE)
