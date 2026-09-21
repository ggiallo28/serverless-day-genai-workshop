import datetime
import json
import os
import time
import uuid
from typing import Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
from IPython.display import Markdown, display

LAMBDA_EXECUTION_ROLE_POLICY = (
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)
LAMBDA_RUNTIME = "python3.12"
LAMBDA_HANDLER = "lambda_function_code.lambda_handler"
LAMBDA_PACKAGE_TYPE = "Zip"

IAM_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

# AgentCore Gateway IAM Role constants
# "Recube-Sandbox-Role-" prefix: the workshop's sandbox AWS account has an SCP that denies
# any action to a role whose ARN doesn't match arn:aws:iam:::role/Recube-Sandbox-Role* --
# without this prefix the role deploys fine but can't actually do anything.
GATEWAY_AGENTCORE_ROLE_NAME = "Recube-Sandbox-Role-GatewaySearchAgentCoreRole"
GATEWAY_AGENTCORE_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

GATEWAY_AGENTCORE_POLICY_NAME = "BedrockAgentPolicy"

# Cognito configuration constants
COGNITO_POOL_NAME = "MCPServerPool"
COGNITO_CLIENT_NAME = "MCPServerPoolClient"
COGNITO_PASSWORD_MIN_LENGTH = 8
COGNITO_DEFAULT_USERNAME = "testuser"
COGNITO_DEFAULT_TEMP_PASSWORD = "Temp123!"
COGNITO_DEFAULT_PASSWORD = "MyPassword123!"

COGNITO_AUTH_FLOWS = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]

COGNITO_PASSWORD_POLICY = {
    "PasswordPolicy": {"MinimumLength": COGNITO_PASSWORD_MIN_LENGTH}
}


def _format_error_message(error: ClientError) -> str:
    """Format error message from ClientError."""
    return f"{error.response['Error']['Code']}-{error.response['Error']['Message']}"


def _create_or_get_iam_role(iam_client, role_name: str) -> str:
    """Create IAM role or return existing role ARN."""
    try:
        print("Creating IAM role for lambda function")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(IAM_TRUST_POLICY),
            Description="IAM role to be assumed by lambda function",
        )
        role_arn = response["Role"]["Arn"]

        print("Attaching policy to the IAM role")
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=LAMBDA_EXECUTION_ROLE_POLICY,
        )

        print(f"Role '{role_name}' created successfully: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            print(f"IAM role {role_name} already exists. Using the same ARN {role_arn}")
            return role_arn
        else:
            raise error


def _create_or_get_lambda_function(
    lambda_client, function_name: str, role_arn: str, code: bytes
) -> str:
    """Create Lambda function or return existing function ARN."""
    try:
        print("Creating lambda function")
        response = lambda_client.create_function(
            FunctionName=function_name,
            Role=role_arn,
            Runtime=LAMBDA_RUNTIME,
            Handler=LAMBDA_HANDLER,
            Code={"ZipFile": code},
            Description="Lambda function example for Bedrock AgentCore Gateway",
            PackageType=LAMBDA_PACKAGE_TYPE,
        )
        return response["FunctionArn"]

    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceConflictException":
            response = lambda_client.get_function(FunctionName=function_name)
            lambda_arn = response["Configuration"]["FunctionArn"]
            print(
                f"AWS Lambda function {function_name} already exists. Using the same ARN {lambda_arn}"
            )
            return lambda_arn
        else:
            raise error


def create_gateway_lambda(
    lambda_function_code_path: str, lambda_function_name: str
) -> Dict[str, Union[str, int]]:
    """Create AWS Lambda function with IAM role for AgentCore Gateway.

    Args:
        lambda_function_code_path: Path to the Lambda function code zip file
        lambda_function_name: Name for the Lambda function

    Returns:
        Dictionary with 'lambda_function_arn' and 'exit_code' keys
    """
    session = boto3.Session()
    region = session.region_name

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    # "Recube-Sandbox-Role-" prefix: the workshop's sandbox AWS account has an SCP that
    # denies any action to a role whose ARN doesn't match
    # arn:aws:iam:::role/Recube-Sandbox-Role* -- without this prefix the role deploys fine
    # but can't actually do anything. Truncated to IAM's 64-char role name limit; the prefix
    # stays intact since it's at the front, so the SCP wildcard match still holds.
    role_name = f"Recube-Sandbox-Role-{lambda_function_name}"[:64]

    print("Reading code from zip file")
    with open(lambda_function_code_path, "rb") as f:
        lambda_function_code = f.read()

    try:
        role_arn = _create_or_get_iam_role(iam_client, role_name)
        time.sleep(20)
        try:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )
        except ClientError:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )

        return {"lambda_function_arn": lambda_arn, "exit_code": 0}

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Error: {error_message}")
        return {"lambda_function_arn": error_message, "exit_code": 1}
    except Exception as error:
        print(f"Unexpected error: {str(error)}")
        return {"lambda_function_arn": str(error), "exit_code": 1}


def _create_cognito_user_pool(cognito_client, pool_name: str) -> str:
    """Create Cognito User Pool and return pool ID."""
    print(f"Creating Cognito User Pool: {pool_name}")
    response = cognito_client.create_user_pool(
        PoolName=pool_name, Policies=COGNITO_PASSWORD_POLICY
    )
    pool_id = response["UserPool"]["Id"]
    print(f"User Pool created with ID: {pool_id}")
    return pool_id


def _create_cognito_app_client(cognito_client, pool_id: str, client_name: str) -> str:
    """Create Cognito App Client and return client ID."""
    print(f"Creating Cognito App Client: {client_name}")
    response = cognito_client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=client_name,
        GenerateSecret=False,
        ExplicitAuthFlows=COGNITO_AUTH_FLOWS,
    )
    client_id = response["UserPoolClient"]["ClientId"]
    print(f"App Client created with ID: {client_id}")
    return client_id


def _create_cognito_user(
    cognito_client,
    pool_id: str,
    username: str,
    temp_password: str,
    permanent_password: str,
) -> None:
    """Create Cognito user with temporary password and set permanent password."""
    print(f"Creating Cognito user: {username}")
    cognito_client.admin_create_user(
        UserPoolId=pool_id,
        Username=username,
        TemporaryPassword=temp_password,
        MessageAction="SUPPRESS",
    )

    print(f"Setting permanent password for user: {username}")
    cognito_client.admin_set_user_password(
        UserPoolId=pool_id,
        Username=username,
        Password=permanent_password,
        Permanent=True,
    )


def _authenticate_user(
    cognito_client, client_id: str, username: str, password: str
) -> str:
    """Authenticate user and return access token."""
    print(f"Authenticating user: {username}")
    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return auth_response["AuthenticationResult"]["AccessToken"]


def get_bearer_token(
    client_id: str, username: str, password: str, region: Optional[str] = None
) -> Optional[str]:
    """Get bearer token from existing Cognito User Pool.

    Args:
        client_id: Cognito App Client ID
        username: Username for authentication
        password: User password
        region: AWS region (if None, uses session default)

    Returns:
        Bearer token string or None if authentication fails
    """
    if not region:
        session = boto3.Session()
        region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        print(f"Authenticating user: {username}")
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        print(f"Bearer token obtained successfully")
        return bearer_token

    except ClientError as error:
        if error.response["Error"]["Code"] == "NotAuthorizedException":
            print(f"Authentication failed: Invalid credentials for user {username}")
        elif error.response["Error"]["Code"] == "UserNotFoundException":
            print(f"Authentication failed: User {username} not found")
        elif error.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Authentication failed: Client ID {client_id} not found")
        else:
            error_message = _format_error_message(error)
            print(f"Cognito Client Error: {error_message}")
        return None
    except Exception as error:
        print(f"Unexpected error getting bearer token: {str(error)}")
        return None


def create_gateway_iam_role(
    lambda_arns: List[str],
    role_name: str = GATEWAY_AGENTCORE_ROLE_NAME,
    policy_name: str = GATEWAY_AGENTCORE_POLICY_NAME,
) -> Optional[str]:
    """Create IAM role for AgentCore Gateway with Lambda invoke permissions.

    Args:
        lambda_arns: List of Lambda function ARNs to grant invoke permissions
        role_name: Name for the IAM role
        policy_name: Name for the inline policy

    Returns:
        Role ARN string or None if creation fails
    """
    session = boto3.Session()
    region = session.region_name

    iam_client = boto3.client("iam", region_name=region)

    try:
        # Create the IAM role
        print(f"Creating IAM role: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(GATEWAY_AGENTCORE_TRUST_POLICY),
            Description="IAM role for AgentCore Gateway to invoke Lambda functions",
        )
        role_arn = response["Role"]["Arn"]

        # Create the inline policy document
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeFunction",
                    "Effect": "Allow",
                    "Action": "lambda:InvokeFunction",
                    "Resource": lambda_arns,
                }
            ],
        }

        # Attach the inline policy
        print(f"Attaching policy: {policy_name}")
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )

        print(f"Gateway IAM role created successfully: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"IAM role {role_name} already exists. Retrieving existing role...")
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]

            # Update the policy if role exists
            try:
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "InvokeFunction",
                            "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": lambda_arns,
                        }
                    ],
                }

                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document),
                )
                print(f"Updated policy for existing role: {role_arn}")

            except ClientError as policy_error:
                print(
                    f"Warning: Could not update policy: {_format_error_message(policy_error)}"
                )

            return role_arn
        else:
            error_message = _format_error_message(error)
            print(f"Error creating IAM role: {error_message}")
            return None
    except Exception as error:
        print(f"Unexpected error creating IAM role: {str(error)}")
        return None


def _extract_function_name_from_arn(lambda_arn: str) -> str:
    """Extract function name from Lambda ARN.

    Args:
        lambda_arn: Lambda function ARN

    Returns:
        Function name extracted from ARN

    Example:
        arn:aws:lambda:us-east-1:123456789012:function:my-function -> my-function
    """
    # ARN format: arn:aws:lambda:region:account:function:function-name
    if lambda_arn.startswith("arn:aws:lambda:"):
        return lambda_arn.split(":")[-1]
    else:
        # If it's already a function name, return as is
        return lambda_arn


def delete_gateway_lambda(lambda_function_arn: str) -> bool:
    """Delete Lambda function and associated IAM role.

    Args:
        lambda_function_arn: ARN or name of the Lambda function to delete

    Returns:
        True if deletion successful, False otherwise
    """
    session = boto3.Session()
    region = session.region_name

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    # Extract function name from ARN
    lambda_function_name = _extract_function_name_from_arn(lambda_function_arn)
    role_name = f"Recube-Sandbox-Role-{lambda_function_name}"[:64]

    try:
        # Delete Lambda function (can use ARN or name)
        print(f"Deleting Lambda function: {lambda_function_name}")
        lambda_client.delete_function(FunctionName=lambda_function_arn)
        print(f"Lambda function {lambda_function_name} deleted successfully")

        # Delete IAM role and detach policies
        try:
            print(f"Detaching policies from IAM role: {role_name}")
            iam_client.detach_role_policy(
                RoleName=role_name,
                PolicyArn=LAMBDA_EXECUTION_ROLE_POLICY,
            )

            print(f"Deleting IAM role: {role_name}")
            iam_client.delete_role(RoleName=role_name)
            print(f"IAM role {role_name} deleted successfully")

        except ClientError as role_error:
            if role_error.response["Error"]["Code"] == "NoSuchEntity":
                print(f"IAM role {role_name} not found, skipping")
            else:
                print(
                    f"Warning: Could not delete IAM role: {_format_error_message(role_error)}"
                )

        return True

    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Lambda function {lambda_function_name} not found")
            return False
        else:
            error_message = _format_error_message(error)
            print(f"Error deleting Lambda function: {error_message}")
            return False
    except Exception as error:
        print(f"Unexpected error deleting Lambda function: {str(error)}")
        return False


def delete_gateway_iam_role(
    role_name: str = GATEWAY_AGENTCORE_ROLE_NAME,
    policy_name: str = GATEWAY_AGENTCORE_POLICY_NAME,
) -> bool:
    """Delete IAM role for AgentCore Gateway.

    Args:
        role_name: Name of the IAM role to delete
        policy_name: Name of the inline policy to delete

    Returns:
        True if deletion successful, False otherwise
    """
    session = boto3.Session()
    region = session.region_name

    iam_client = boto3.client("iam", region_name=region)

    try:
        # Delete inline policy first
        print(f"Deleting inline policy: {policy_name}")
        iam_client.delete_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
        )
        print(f"Inline policy {policy_name} deleted successfully")

        # Delete IAM role
        print(f"Deleting IAM role: {role_name}")
        iam_client.delete_role(RoleName=role_name)
        print(f"IAM role {role_name} deleted successfully")

        return True

    except ClientError as error:
        if error.response["Error"]["Code"] == "NoSuchEntity":
            print(f"IAM role {role_name} or policy {policy_name} not found")
            return False
        else:
            error_message = _format_error_message(error)
            print(f"Error deleting IAM role: {error_message}")
            return False
    except Exception as error:
        print(f"Unexpected error deleting IAM role: {str(error)}")
        return False


def delete_cognito_user_pool(
    pool_name: str = COGNITO_POOL_NAME,
    username: str = COGNITO_DEFAULT_USERNAME,
) -> bool:
    """Delete Cognito User Pool and associated resources.

    Args:
        pool_name: Name of the Cognito User Pool to delete
        username: Username to delete from the pool

    Returns:
        True if deletion successful, False otherwise
    """
    session = boto3.Session()
    region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        # Find the User Pool by name
        print(f"Finding User Pool: {pool_name}")
        response = cognito_client.list_user_pools(MaxResults=50)

        pool_id = None
        for pool in response["UserPools"]:
            if pool["Name"] == pool_name:
                pool_id = pool["Id"]
                break

        if not pool_id:
            print(f"User Pool {pool_name} not found")
            return False

        # Delete user first
        try:
            print(f"Deleting user: {username}")
            cognito_client.admin_delete_user(
                UserPoolId=pool_id,
                Username=username,
            )
            print(f"User {username} deleted successfully")
        except ClientError as user_error:
            if user_error.response["Error"]["Code"] == "UserNotFoundException":
                print(f"User {username} not found, skipping")
            else:
                print(
                    f"Warning: Could not delete user: {_format_error_message(user_error)}"
                )

        # Delete User Pool (this will also delete app clients)
        print(f"Deleting User Pool: {pool_name}")
        cognito_client.delete_user_pool(UserPoolId=pool_id)
        print(f"User Pool {pool_name} deleted successfully")

        return True

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Error deleting Cognito User Pool: {error_message}")
        return False
    except Exception as error:
        print(f"Unexpected error deleting Cognito User Pool: {str(error)}")
        return False


def get_harness_arn(project_dir: str, harness_name: str) -> str:
    """Read a deployed harness's data-plane ARN out of the agentcore CLI's local state file.

    Returns `harnessArn` -- the field used by the `bedrock-agentcore` boto3 client's
    `invoke_harness()` data-plane API. This is distinct from `agentRuntimeArn` (used by
    `agentcore run eval --runtime-arn`), which lives alongside it in the same state file
    but is not what `invoke_harness()` expects.

    Args:
        project_dir: The `agentcore create --project-name` directory for the harness.
        harness_name: The `agentcore create --name` of the harness.

    Returns:
        The harness's `harnessArn`.
    """
    state_path = f"{project_dir}/agentcore/.cli/deployed-state.json"
    with open(state_path) as f:
        state = json.load(f)
    harnesses = state["targets"]["default"]["resources"]["harnesses"]
    return harnesses[harness_name]["harnessArn"]


def parse_agentcore_stream(result) -> Dict[str, Union[str, None, Dict]]:
    """Parse the JSON-lines stdout of `agentcore invoke --json` into assistant text and any tool call.

    Args:
        result: A completed `subprocess.run(...)` result for an `agentcore invoke --json` call.

    Returns:
        Dict with `assistant_text`, `tool_name`, `tool_use_id`, and `tool_input` (parsed as
        JSON when possible).
    """
    tool_name = None
    tool_use_id = None
    tool_input = ""
    assistant_text = ""

    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "contentBlockDelta":
            delta = event.get("delta", {})

            if delta.get("type") == "text":
                assistant_text += delta.get("text", "")

            elif delta.get("type") == "toolUse":
                tool_input += delta.get("input", "")

        elif event.get("type") == "contentBlockStart":
            start = event.get("start", {})

            if start.get("type") == "toolUse":
                # A harness invocation can make several tool calls in one streamed response
                # (e.g. an auto-executed Gateway tool, then a client-side inline_function tool
                # that pauses the stream). Reset the buffer on each new tool call so we only
                # keep the *latest* one -- the one actually pending for the client.
                tool_name = start["toolUse"]["name"]
                tool_use_id = start["toolUse"]["toolUseId"]
                tool_input = ""

    parsed_tool_input = None

    if tool_input:
        try:
            parsed_tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            parsed_tool_input = tool_input

    return {
        "assistant_text": assistant_text,
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "tool_input": parsed_tool_input,
    }


def display_agentcore_result(result) -> Dict[str, Union[str, None, Dict]]:
    """Pretty-print an `agentcore invoke --json` result and return its parsed form.

    Args:
        result: A completed `subprocess.run(...)` result for an `agentcore invoke --json` call.

    Returns:
        The same dict returned by `parse_agentcore_stream`.
    """
    parsed = parse_agentcore_stream(result)

    print("=" * 100)
    print("ASSISTANT")
    print("=" * 100)

    if parsed["assistant_text"]:
        print(parsed["assistant_text"])
    else:
        print("No assistant text returned.")

    print("\n" + "=" * 100)
    print("TOOL CALL")
    print("=" * 100)

    if parsed["tool_name"]:
        print(f"Tool: {parsed['tool_name']}")
        print(f"Tool Use ID: {parsed['tool_use_id']}")

        print("\nInput:")

        if isinstance(parsed["tool_input"], dict):
            print(json.dumps(parsed["tool_input"], indent=2))
        else:
            print(parsed["tool_input"])
    else:
        print("No tool call detected.")

    return parsed


def save_booking_request(
    date: str,
    hour: str,
    guest_name: str,
    num_guests: int,
    restaurant_name: str = "The Bedrock Bistro",
    output_path: str = "resources/data/booking_requests.jsonl",
) -> Dict:
    """Validate and persist a restaurant booking request as one JSON line.

    This is the client-side executor for an AgentCore harness `inline_function` tool
    (e.g. notebook 4's `request_booking`): the harness never runs an inline_function
    tool itself -- it pauses and hands the tool call back to the client application,
    which is expected to run its own function (matching the tool's `inputSchema`
    fields) and, optionally, send a result back via `invoke_harness`.

    Args:
        date: Booking date, format YYYY-MM-DD.
        hour: Booking hour, format HH:MM.
        guest_name: Name of the guest for the reservation.
        num_guests: Number of guests for the booking.
        restaurant_name: Name of the restaurant handling the reservation.
        output_path: Where to append the booking record (JSON Lines). Created if
            missing. Callers running from a different working directory (e.g. a
            notebook under `solutions/`) should pass a path adjusted accordingly.

    Returns:
        Dict with 'ok', 'tool', 'message', and 'record' keys -- ready to send back
        as a harness tool result.

    Raises:
        ValueError: If date, hour, guest_name, or num_guests is missing.
    """
    if not (date and hour and guest_name and num_guests):
        raise ValueError("save_booking_request requires date, hour, guest_name, and num_guests")

    record = {
        "id": f"booking_{uuid.uuid4()}",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "restaurant_name": restaurant_name,
        "date": date,
        "hour": hour,
        "guest_name": guest_name,
        "num_guests": int(num_guests),
        "status": "requested",
    }

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    return {
        "ok": True,
        "tool": "request_booking",
        "message": f"Booking requested with id {record['id']}",
        "record": record,
    }


def setup_cognito_user_pool(
    pool_name: str = COGNITO_POOL_NAME,
    client_name: str = COGNITO_CLIENT_NAME,
    username: str = COGNITO_DEFAULT_USERNAME,
    temp_password: str = COGNITO_DEFAULT_TEMP_PASSWORD,
    permanent_password: str = COGNITO_DEFAULT_PASSWORD,
) -> Optional[Dict[str, str]]:
    """Set up Cognito User Pool with app client and test user.

    Args:
        pool_name: Name for the Cognito User Pool
        client_name: Name for the App Client
        username: Username for the test user
        temp_password: Temporary password for the test user
        permanent_password: Permanent password for the test user

    Returns:
        Dictionary with client_id and discovery_url or None if setup fails
    """
    session = boto3.Session()
    region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        pool_id = _create_cognito_user_pool(cognito_client, pool_name)
        client_id = _create_cognito_app_client(cognito_client, pool_id, client_name)

        _create_cognito_user(
            cognito_client, pool_id, username, temp_password, permanent_password
        )

        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"

        # Output the required values
        print(f"Pool ID: {pool_id}")
        print(f"Discovery URL: {discovery_url}")
        print(f"Client ID: {client_id}")

        return {
            "client_id": client_id,
            "discovery_url": discovery_url,
        }

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Cognito Client Error: {error_message}")
        return None
    except Exception as error:
        print(f"Unexpected error setting up Cognito: {str(error)}")
        return None


def format_qa_answer_with_references(result: Dict) -> str:
    """Format a LangChain RetrievalQA `invoke()` result into an answer plus a
    deduplicated reference list.

    Pulls the S3 source URI, page number, and relevance score out of each source
    document's metadata -- the fields the `AmazonKnowledgeBasesRetriever` copies over
    from the Bedrock Knowledge Base Retrieve API.

    Args:
        result: The dict returned by `qa.invoke({"query": question})`, where `qa` is a
            RetrievalQA chain built with `return_source_documents=True`.

    Returns:
        A string formatted as "Response:\\n<answer>\\n\\nReferences:\\n1. <reference>...".
    """
    answer_text = result["result"]

    references = []
    for doc in result["source_documents"]:
        metadata = doc.metadata
        source_uri = metadata.get("location", {}).get("s3Location", {}).get("uri", "Unknown source")
        source_name = os.path.basename(source_uri)

        page = metadata.get("source_metadata", {}).get("x-amz-bedrock-kb-document-page-number")
        reference = f"{source_name}, page {int(page)}" if page is not None else source_name

        score = metadata.get("score")
        if score is not None:
            reference += f" -- score: {score:.3f}"

        if reference not in references:
            references.append(reference)

    lines = [f"Response:\n{answer_text}", "", "References:"]
    lines += [f"{i}. {reference}" for i, reference in enumerate(references, start=1)]
    return "\n".join(lines)


def render_model_output(text: str, label: str = "BEDROCK MODEL OUTPUT") -> None:
    """Pretty-print a Bedrock text response inside BEGIN/END delimiter banners,
    rendering the text itself as Markdown.

    Args:
        text: The generated text to display (e.g. the string returned by an
            `invoke_model` helper, or a value pulled out of the parsed response body).
        label: Text shown in the banners, useful when displaying more than one
            response in the same notebook cell.
    """
    delimiter = "=" * 100
    print(f"\n{delimiter}")
    print(f"BEGIN {label}")
    print(f"{delimiter}\n")

    display(Markdown(text))

    print(f"\n{delimiter}")
    print(f"END {label}")
    print(f"{delimiter}\n")


def extract_tools_from_search_response(search_response: Dict) -> List[Dict]:
    """Parse the tool list out of an ``x_amz_bedrock_agentcore_search`` MCP response.

    Gateway's search response shape is inconsistent: the tool list is usually at
    ``response["result"]["structuredContent"]["tools"]``, but some Gateways instead
    return it as JSON-encoded text inside ``response["result"]["content"]``. This
    handles both.

    Args:
        search_response: The raw JSON-RPC response from calling the built-in
            ``x_amz_bedrock_agentcore_search`` tool (e.g. via ``invoke_gateway_tool``).

    Returns:
        The list of matching tool dicts.

    Raises:
        ValueError: If no tool list could be found in either response shape.
    """
    result = search_response["result"]

    if "structuredContent" in result:
        return result["structuredContent"]["tools"]

    for content in result.get("content", []):
        if content.get("type") == "text":
            try:
                parsed = json.loads(content["text"])
                if "tools" in parsed:
                    return parsed["tools"]
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No tools found in Gateway search response: {search_response}")


def get_memory_id_from_deployed_state(project_dir: str = "RestaurantConcierge") -> str:
    """Read the first memory ID out of a harness's ``deployed-state.json``.

    Args:
        project_dir: Harness project directory (e.g. "RestaurantConcierge"), as passed
            to `agentcore` CLI commands.

    Returns:
        The `memoryId` of the first memory resource recorded in the deployed state.
    """
    state_path = f"{project_dir}/agentcore/.cli/deployed-state.json"
    with open(state_path) as f:
        state = json.load(f)
    memories = state["targets"]["default"]["resources"]["memories"]
    return list(memories.values())[0]["memoryId"]


def delete_gateway_targets(agentcore_client, gateway_id: str) -> None:
    """Delete every target attached to a Gateway, pacing calls to avoid throttling.

    Args:
        agentcore_client: A boto3 `bedrock-agentcore-control` client.
        gateway_id: Identifier of the Gateway whose targets should be deleted.
    """
    response = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
    for target in response["items"]:
        print(f"Deleting target {target['name']} ({target['targetId']})")
        agentcore_client.delete_gateway_target(
            gatewayIdentifier=gateway_id, targetId=target["targetId"]
        )
        time.sleep(20)


def safe_delete(func, **kwargs) -> bool:
    """Call a boto3 delete method, swallowing "already gone" errors.

    Args:
        func: A bound boto3 client method to call (e.g. `agentcore_client.delete_gateway`).
        **kwargs: Keyword arguments passed through to `func`.

    Returns:
        True if the call succeeded, False if it raised (including not-found errors,
        which are treated as already-cleaned-up rather than failures).
    """
    try:
        func(**kwargs)
        return True
    except Exception as error:
        if "NotFound" not in str(error) and "NoSuchEntity" not in str(error):
            print(f"Error during cleanup: {error}")
        return False
