# Webex Token Keeper
*Store dynamic Webex OAuth tokens and make them accessible via a static key.*

------------------------------------------------------------------------------------------------------------------------

Personal Webex Teams access tokens expire in twelve (12) hours. Webex Teams OAuth access tokens expire in about fourteen
(14) days and are refreshable; however, generating OAuth tokens require a web service and human interaction.  You need
to create a static configuration that can access the Webex Teams APIs (CI/CD tools, backend automation, etc.).

> How can you programmatically obtain a Webex Teams API access token with a fixed configuration?

It takes a small web service.

## Simple Microservice Provides Programmatic Access to OAuth Generated Access Tokens

Webex Token Keeper (WTK) implements the Webex Teams Integration OAuth flow and stores the OAuth generated Access Token 
for future retrieval.  The Access Token is stored using a randomly generated key, which is provided to the user at the
end of the OAuth flow. WTK provides a simple REST API that provides programmatic access to the stored token.

WTK automatically refreshes the token when a stored token is requested via the REST API (if the token expires in less
than seven days).

## Features

* Python implementation of the Webex Teams Integration/OAuth process
* Store OAuth generated access tokens for programmatic retrieval
* REST API for retrieving and deleting stored access tokens
* OpenAPI (Swagger) interactive REST API docs
* Serverless (AWS Lambda) microservice
* Fully automated deployment via SAM template

## Tech Stack

* [FastAPI](https://fastapi.tiangolo.com/) Web Service
* [Pydantic](https://pydantic-docs.helpmanual.io/) Data Models
* [AWS API Gateway](https://aws.amazon.com/api-gateway/) w/Custom Domain Support
* [AWS Lambda](https://aws.amazon.com/lambda/) Serverless App
* [AWS DynamoDB](https://aws.amazon.com/dynamodb/) Database 
* [CloudFormation (SAM) Template](https://aws.amazon.com/cloudformation/) Parameterized and Fully-Automated Deployment

## Setup & Use

The Webex Token Keeper (WTK) app can be fully deployed by running the provided [deployment script](/script/deploy).
The setup script sources installation specific information from the shell environment.  You will need an AWS 
account and a functional local development environment.

**At a minimum, you will need to:**
1. [Install](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) and 
   [configure](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html#cli-quick-configuration)
   the AWS Command Line Interface (CLI)

2. [Install](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) 
   the AWS SAM CLI

3. Host your custom DNS domain in an AWS [Route53](https://aws.amazon.com/route53/) hosted zone

4. Provision a secure SSL certificate for your custom domain in AWS
   [Certificate Manager](https://aws.amazon.com/certificate-manager/)

### Environment Variables

The deployment script will look for the following *environment variables*.

```shell
$ cat .env
#!/usr/bin/env bash

# AWS Configuration Settings
export WTK_TABLE_NAME="webex-token-keeper"                                  # DynamoDB Table Name
export WTK_DOMAIN_NAME="your.custom.domain.com"                             # Custom DNS Domain Name
export WTK_HOSTED_ZONE_ID="XXXXXXXXXXXX"                                    # Route53 Hosted Zone
export WTK_CERTIFICATE_ARN="arn:aws:acm:us-east-1:x:certificate/x-x-x-x-x"  # Certificate ARN


# Webex Teams Integration Settings
### Provided when you you create your Webex Teams Integration App at https://developer.cisco.com
export WEBEX_TEAMS_CLIENT_ID="X"
export WEBEX_TEAMS_CLIENT_SECRET="X"
export WEBEX_TEAMS_REDIRECT_URI="https://${WTK_DOMAIN_NAME}/key"
export WEBEX_TEAMS_OAUTH_AUTHORIZATION_URL="https://api.ciscospark.com/v1/authorize?..."

$ source .env
```

### Run the Deployment Script

The deployment script will package the SAM application and source the parameter values from the above environment
variables.  If everything is setup correctly, you can provision the full serverless application (including the DynamoDB
table, API gateway, and custom domain name) by running the provided [deployment script](/script/deploy):

```shell
$ script/deploy
Building resource 'WebexTokenKeeper'
Running PythonPipBuilder:ResolveDependencies
Running PythonPipBuilder:CopySource

Build Succeeded
...
```

The SAM template is idempotent; you can push environment variable, template, or code changes by rerunning the deployment
script.
