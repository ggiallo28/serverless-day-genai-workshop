import boto3
import json
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth, RequestError
from time import sleep

SERVICE = "aoss"
AWS_REGION = "us-east-1"

INDEX_BODY = {
    "settings": {
        "index.knn": "true",
        "number_of_shards": 1,
        "knn.algo_param.ef_search": 512,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "vector": {
                "type": "knn_vector",
                "dimension": 256,
                "method": {
                    "name": "hnsw",
                    "engine": "faiss",
                    "space_type": "l2",
                },
            },
            "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text"},
            "AMAZON_BEDROCK_METADATA": {"type": "text"},
        }
    },
}


def get_opensearch_client(host: str, region: str = AWS_REGION, service: str = SERVICE) -> OpenSearch:
    """Build and return an OpenSearch client."""
    try:
        print(f"Initializing OpenSearch client for host: {host}, region: {region}")
        credentials = boto3.Session().get_credentials()
        awsauth = AWSV4SignerAuth(credentials, region, service)
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=300,
        )
        print("OpenSearch client initialized successfully.")
        return client
    except Exception as e:
        print(f"Error initializing OpenSearch client: {str(e)}")
        raise


def create_index(
    host: str, index_name: str, index_body: dict = INDEX_BODY, region: str = AWS_REGION
) -> None:
    """Create a vector index in OpenSearch Serverless."""
    try:
        client = get_opensearch_client(host, region)
        print(f"Creating index: {index_name}")
        response = client.indices.create(index=index_name, body=index_body)
        print("Index created successfully:")
        print(json.dumps(response, indent=2))
    except RequestError as e:
        if e.info.get("status") == 400 and "already exists" in str(e.error):
            print(f"Index {index_name} already exists. Skipping creation.")
        else:
            print(f"RequestError while creating index: {str(e)}")
            raise
    except Exception as e:
        print(f"An unexpected error occurred while creating the index: {str(e)}")
        raise
