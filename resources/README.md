# `resources/`

Everything the workshop notebooks load, deploy, or import, kept out of the repo root so the
notebooks themselves stay the first thing you see. Every notebook adds `resources/src` to its
`sys.path` and references paths under here directly — you never have to open this folder
manually to run the workshop. Use `make tree` from the repo root to browse it.

```
resources/
├── src/                       # shared Python helpers imported by the notebooks
│   ├── utils.py
│   ├── cloudformation_utils.py
│   ├── langchain_utils.py
│   └── opensearch_utils.py
├── infra/                     # CloudFormation templates
│   ├── bedrock_rag_template.yaml            # notebook 2, OpenSearch Serverless variant
│   ├── bedrock_rag_s3vectors_template.yaml  # notebook 2, S3 Vectors variant (default)
│   ├── agentcore_harness_role_template.yaml # notebook 4, harness execution role
│   ├── sagemaker_studio_init_template.yaml  # `make studio-init`
│   └── legacy/bedrock_agent_template.yaml   # Bedrock Agents Classic template
├── lambdas/                   # Lambda function code for Gateway tools
│   ├── calc/
│   ├── restaurant/
│   └── restaurant_data/
├── data/                      # Knowledge Base source documents
│   ├── financials/
│   └── restaurant/
├── assets/images/             # diagrams referenced by the notebooks
├── config/
│   ├── chain_config.json
│   └── skills/booking-ops/SKILL.md   # AgentCore Skill used in notebooks 4/6
├── scripts/cleanup_workshop.py       # `make teardown`
└── legacy/                           # Bedrock Agents Classic notebooks
```
