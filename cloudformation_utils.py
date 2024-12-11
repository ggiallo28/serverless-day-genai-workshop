import boto3
import time
import yaml
from pygments import highlight, lexers, formatters

def load_template(file_path):
    """
    Load a CloudFormation template from a YAML file.

    Args:
        file_path (str): Path to the CloudFormation template file.

    Returns:
        str: The loaded CloudFormation template as a string.

    Raises:
        FileNotFoundError: If the file is not found.
        yaml.YAMLError: If there is an error in parsing the YAML.
        Exception: For any other unexpected errors.
    """
    try:
        with open(file_path, 'r') as template_file:
            template = template_file.read()
        print("CloudFormation template loaded successfully.")
        return template
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        raise
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise


def colorize_yaml(yaml_content):
    """
    Colorize YAML content for terminal output using Pygments.

    Args:
        yaml_content (str): The YAML content to colorize.

    Returns:
        str: Colorized YAML content for terminal output.
    """
    return highlight(
        yaml_content,
        lexers.YamlLexer(),
        formatters.TerminalFormatter()
    )

def get_cloudformation_client(region):
    """
    Initialize and return a CloudFormation client for the specified region.
    
    Args:
        region (str): The AWS region to use for the client.
        
    Returns:
        boto3.client: A CloudFormation client.
    """
    return boto3.client('cloudformation', region_name=region)


def create_stack(region, stack_name, template_body, parameters, capabilities=['CAPABILITY_NAMED_IAM']):
    """
    Create a CloudFormation stack.

    Args:
        region (str): The AWS region where the stack will be created.
        stack_name (str): Name of the CloudFormation stack to create.
        template_body (str): CloudFormation template in JSON or YAML format.
        parameters (list): List of parameter dictionaries for the template.
        capabilities (list): List of IAM capabilities (default: ['CAPABILITY_NAMED_IAM']).
    
    Returns:
        str: Stack ID of the created stack.
    """
    try:
        client = get_cloudformation_client(region)
        print(f"Creating stack: {stack_name} in region: {region}...")
        response = client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=parameters,
            Capabilities=capabilities
        )
        print(f"Stack creation initiated. Stack ID: {response['StackId']}")
        return response['StackId']
    except Exception as e:
        print(f"An error occurred while creating the stack: {e}")
        raise

def update_stack(region, stack_name, template_body, parameters, capabilities=['CAPABILITY_NAMED_IAM']):
    """
    Update a CloudFormation stack.

    Args:
        region (str): The AWS region where the stack exists.
        stack_name (str): Name of the CloudFormation stack to update.
        template_body (str): CloudFormation template in JSON or YAML format.
        parameters (list): List of parameter dictionaries for the template.
        capabilities (list): List of IAM capabilities (default: ['CAPABILITY_NAMED_IAM']).

    Returns:
        str: Stack ID of the updated stack.
    """
    try:
        client = get_cloudformation_client(region)
        print(f"Updating stack: {stack_name} in region: {region}...")
        response = client.update_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=parameters,
            Capabilities=capabilities
        )
        print(f"Stack update initiated. Stack ID: {response['StackId']}")
        return response['StackId']
    except client.exceptions.ClientError as e:
        if 'No updates are to be performed' in str(e):
            print("No changes detected. The stack is already up-to-date.")
        else:
            print(f"An error occurred during stack update: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

def update_parameters(parameters, key, value):
    """
    Update a list of CloudFormation parameters with a new key-value pair.

    Args:
        parameters (list): A list of parameter dictionaries, each containing 'ParameterKey' and 'ParameterValue'.
        key (str): The key of the parameter to update or add.
        value (str): The value to set for the parameter.

    Returns:
        list: The updated list of parameters.
    """
    for param in parameters:
        if param['ParameterKey'] == key:
            param['ParameterValue'] = value
            print(f"Updated parameter: {key} = {value}")
            return parameters

    parameters.append({'ParameterKey': key, 'ParameterValue': value})
    print(f"Added new parameter: {key} = {value}")
    return parameters

def wait_for_stack(region, stack_name, expected_status):
    """
    Wait for a CloudFormation stack to reach an expected status.

    Args:
        region (str): The AWS region where the stack exists.
        stack_name (str): Name of the CloudFormation stack.
        expected_status (str): The desired status to wait for (e.g., 'CREATE_COMPLETE').

    Raises:
        Exception: If the stack fails or encounters an unexpected status.
    """
    client = get_cloudformation_client(region)
    print(f"Waiting for stack {stack_name} to reach status: {expected_status} in region: {region}...")
    while True:
        try:
            response = client.describe_stacks(StackName=stack_name)
            stack_status = response['Stacks'][0]['StackStatus']
            print(f"Current stack status: {stack_status}. Waiting...")
            
            if stack_status == expected_status:
                print(f"Stack {stack_name} reached expected status: {expected_status}.")
                break
            elif stack_status in ['CREATE_FAILED', 'ROLLBACK_COMPLETE', 'DELETE_FAILED']:
                raise Exception(f"Stack operation failed with status: {stack_status}")
        except client.exceptions.ClientError as e:
            if 'does not exist' in str(e) and expected_status == 'DELETE_COMPLETE':
                print(f"Stack {stack_name} deleted successfully.")
                break
            elif 'does not exist' in str(e):
                raise Exception(f"Stack {stack_name} does not exist.")
            else:
                raise
        time.sleep(30)
