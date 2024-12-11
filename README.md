# Amazon Bedrock RAG and Agent Application

> **⚠️ Disclaimer: This workshop is not free and may incur **AWS usage costs**. The estimated cost of completing this workshop is approximately **$10 USD**. Please monitor your AWS account billing dashboard to track expenses and avoid unexpected charges.** 

---

## Repository Overview

This repository demonstrates the implementation of a Retrieval-Augmented Generation (RAG) system and a Bedrock Agent for natural language processing and automation. The application utilizes **Amazon Bedrock**, **OpenSearch Serverless**, and **AWS Lambda** to deliver scalable solutions for question answering and restaurant booking workflows.

---

## Repository Structure

```
.
├── 0_bedrock_basics.ipynb       # Introduction to Bedrock fundamentals
├── 1_text_generation.ipynb      # Text generation with Bedrock models
├── 2_bedrock_kb.ipynb           # Knowledge base integration
├── 3_lanhchain_agents.ipynb     # LLM agents and tool usage
├── 4_bedrock_agents.ipynb       # Advanced Bedrock agent workflows
├── 5_multi_agents.ipynb         # Multi-agent system implementation
├── bedrock_agent_template.yaml  # CloudFormation template for Bedrock Agent
├── bedrock_rag_template.yaml    # CloudFormation template for RAG system
├── chain_config.json            # Configuration for multi-step prompts
├── cloudformation_utils.py      # CloudFormation stack utilities
├── langchain_utils.py           # LangChain tool and agent utilities
├── opensearch_utils.py          # OpenSearch Serverless utilities
├── requirements.txt             # Python dependencies
├── images/                      # Image assets
├── kb_financials/               # Knowledge base for financial domain
├── kb_restaurant/               # Knowledge base for restaurant domain
└── README.md                    # Project documentation
```

---

## Overview

The project is divided into two primary components:

### 1. Retrieval-Augmented Generation (RAG) System
Enables efficient knowledge retrieval for user queries by combining Bedrock's capabilities with OpenSearch Serverless.

### 2. Bedrock Agent for Restaurant Bookings
Automates restaurant booking tasks, integrating Bedrock with AWS Lambda and DynamoDB for workflow management.

---

## Data Flow

The system follows this general workflow:

1. **Document Upload**: Files are uploaded to an S3 bucket.
2. **Knowledge Base Ingestion**: Bedrock ingests documents from S3 and indexes them in OpenSearch Serverless.
3. **Query Processing**: User queries are handled by Bedrock Retrieve API or the Bedrock Agent.
4. **Restaurant Booking**: Bedrock Agent triggers AWS Lambda for booking operations, interacting with DynamoDB.

---

## Infrastructure Components

### RAG System (`bedrock_rag_template.yaml`)
- **S3 Bucket**: Stores documents for the knowledge base.
- **IAM Role**: Provides permissions for Bedrock and OpenSearch access.
- **OpenSearch Serverless Collection**: Supports vector storage and search.
- **Bedrock Knowledge Base**: Manages and searches documents.
- **Bedrock Data Source**: Ingests documents into the knowledge base.

### Bedrock Agent (`bedrock_agent_template.yaml`)
- **DynamoDB Table**: Stores restaurant booking data.
- **IAM Policy**: Grants Bedrock Agent necessary permissions.
- **Lambda Function**: Executes booking operations (create, retrieve, delete).
- **Bedrock Agent**: Orchestrates booking workflows.

---

## Getting Started

### Prerequisites
1. AWS CLI configured with necessary permissions.
2. Python 3.8+ installed on your system.
3. Required Python packages installed.

### Installation
1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure AWS credentials:
   - Create a `.env` file with your AWS credentials:
     ```
     AWS_ACCESS_KEY_ID=<your_access_key>
     AWS_SECRET_ACCESS_KEY=<your_secret_key>
     AWS_REGION=<your_region>
     ```

---

## Workshop Modules

### 1. Bedrock Basics (`0_bedrock_basics.ipynb`)
- Explore foundational Bedrock concepts.
- Work with Amazon Bedrock models for text generation.

### 2. Text Generation (`1_text_generation.ipynb`)
- Use prompt engineering techniques for tasks like summarization, question answering, and entity extraction.
- Compare various foundation models.

### 3. Knowledge Base Integration (`2_bedrock_kb.ipynb`)
- Build Retrieval-Augmented Generation (RAG) applications.
- Configure OpenSearch Serverless and Bedrock Knowledge Bases.

### 4. LangChain Agents (`3_lanhchain_agents.ipynb`)
- Implement tools and reasoning frameworks.
- Experiment with Chain of Thought (CoT) and Tree of Thoughts (ToT).

### 5. Bedrock Agents (`4_bedrock_agents.ipynb`)
- Develop Bedrock Agent workflows for automation.
- Integrate memory and advanced tool usage.

### 6. Multi-Agent Systems (`5_multi_agents.ipynb`)
- Design and build collaborative agent workflows.
- Implement real-world scenarios such as restaurant booking.

---

## Troubleshooting

### Common Issues
1. **Stack Creation Failure**:
   - Check AWS CloudFormation events for errors.
   - Ensure unique S3 bucket names.
   - Confirm IAM role permissions.

2. **OpenSearch Connectivity**:
   - Validate network and data access policies.
   - Use `opensearch_utils.py` for connectivity checks.

3. **Bedrock Agent Errors**:
   - Verify Lambda function permissions.
   - Check CloudWatch logs for error details.

### Debugging Tips
- Enable debug logging for Lambda functions by setting `LOG_LEVEL=DEBUG`.
- Test OpenSearch connection with `opensearch_utils.py`.
- Validate Bedrock API permissions:
  ```bash
  aws bedrock list-knowledge-bases --region <your_region>
  ```

---

## Additional Resources

For detailed documentation, refer to:

- [Amazon Bedrock Documentation](https://aws.amazon.com/bedrock/)
- [AWS OpenSearch Documentation](https://docs.aws.amazon.com/opensearch/)
- [AWS Lambda Documentation](https://aws.amazon.com/lambda/)

---

Start exploring the repository to build robust AI/ML applications using Amazon Bedrock and AWS services! 🚀

