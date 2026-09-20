# Amazon Bedrock GenAI Workshop

A hands-on, notebook-driven workshop covering Amazon Bedrock end to end: model basics and
prompt engineering, Retrieval-Augmented Generation (RAG), LangChain, and building agents on
**Amazon Bedrock AgentCore**. The running example throughout notebooks 2 and 4-6 is a
restaurant concierge ("The Bedrock Bistro") that answers menu/hours questions and takes
booking requests.

> ⚠️ **This workshop is not free.** Deploying the CloudFormation stacks, Lambda functions,
> and AgentCore harnesses in notebooks 2 and 4-6 incurs real AWS usage costs. Run
> `make teardown` (and `make studio-destroy` if you used `make studio-init`) when you're
> done — see [Cleaning up](#cleaning-up) below.

## Quickstart

### Recommended: SageMaker Studio (lowest setup friction)

```bash
make studio-init
```

This deploys `infra/sagemaker_studio_init_template.yaml`: a SageMaker Studio domain, user
profile, and JupyterLab space, with an execution role that already has every AWS permission
the notebooks need. Open the printed console URL, launch the JupyterLab space, and start at
`0_bedrock_basics.ipynb` — no local Python setup, no `.env` file to fill in by hand (Studio's
execution role supplies credentials automatically).

### Alternative: local Jupyter

```bash
make install   # installs everything in requirements.txt
make env       # creates a blank .env for your AWS credentials
make jupyter   # launches Jupyter Lab
```

Fill in `.env` with your AWS access key/secret/session token before running notebook 0.
Run `make help` to see every available command.

## Notebooks

| # | Notebook | Covers | When |
|---|---|---|---|
| 0 | `0_bedrock_basics.ipynb` | `boto3` setup, the current serverless model catalog (Amazon Nova, Claude 4.x via cross-Region inference profiles, Mistral) | Pre-work |
| 1 | `1_text_generation.ipynb` | Prompt engineering: summarization, Q&A, entity extraction | Pre-work |
| 2 | `2_bedrock_kb.ipynb` | Knowledge Bases / RAG, deployed via CloudFormation, with a choice of S3 Vectors (default, low-cost) or OpenSearch Serverless | Pre-work (ideally) |
| 3 | `3_text_generation_agents.ipynb` | LangChain: chains, memory, tools, a ReAct agent | Live |
| 4 | `4_agentcore_harness.ipynb` | Building the `restaurant_concierge` AgentCore Harness step by step: prompt-only → memory → inline tool → Gateway-backed Lambda tool → invoke overrides | Live |
| 5 | `5_agentcore_multi_agent.ipynb` | Agent-as-tool: a second, specialist harness (`restaurant_events_specialist`) that the primary harness consults for large-party/private-event requests | Live, optional |
| 6 | `6_agentcore_advanced.ipynb` | AgentCore platform deep dive: Gateway with semantic tool search, Memory strategies, Skills, Code Interpreter, Policy, Evaluations | Live, capstone |

Notebooks 0-1 (and ideally 2) are self-paced pre-work so live session time goes to notebooks
3-6. Notebook 5 is optional and time-permitting — notebook 6 only requires notebook 4.

`legacy/4_bedrock_agents.ipynb` and `legacy/5_multi_agents.ipynb` cover Amazon Bedrock Agents
(Classic), kept for reference since Classic remains usable for AWS accounts allowlisted for
it. They are not part of the main workshop flow and are not guaranteed to run on every
account.

## Repository structure

```
.
├── 0_bedrock_basics.ipynb ... 6_agentcore_advanced.ipynb   # the workshop notebooks
├── Makefile                       # make help for all commands
├── requirements.in / requirements.txt
├── src/                           # shared Python helpers imported by the notebooks
│   ├── utils.py
│   ├── cloudformation_utils.py
│   ├── langchain_utils.py
│   └── opensearch_utils.py
├── infra/                         # CloudFormation templates
│   ├── bedrock_rag_template.yaml            # notebook 2, OpenSearch Serverless variant
│   ├── bedrock_rag_s3vectors_template.yaml  # notebook 2, S3 Vectors variant (default)
│   ├── agentcore_harness_role_template.yaml # notebook 4, harness execution role
│   ├── sagemaker_studio_init_template.yaml  # `make studio-init`
│   └── legacy/bedrock_agent_template.yaml   # Bedrock Agents Classic template
├── lambdas/                       # Lambda function code for Gateway tools
│   ├── calc/
│   ├── restaurant/
│   └── restaurant_data/
├── data/                          # Knowledge Base source documents
│   ├── financials/
│   └── restaurant/
├── assets/images/                 # diagrams referenced by the notebooks
├── config/
│   ├── chain_config.json
│   └── skills/booking-ops/SKILL.md   # AgentCore Skill used in notebooks 4/6
├── scripts/cleanup_workshop.py    # `make teardown`
└── legacy/                        # Bedrock Agents Classic notebooks
```

## Cleaning up

Two separate teardown paths, since resources come from two different places:

```bash
make teardown-dry-run   # see what workshop AWS resources currently exist (free, read-only)
make teardown           # delete them (asks for confirmation first)
make studio-destroy     # separately tears down the SageMaker Studio environment, if you used studio-init
```

`make teardown` covers the AgentCore CLI projects from notebooks 4/5 (harness, memory,
gateway) and the CloudFormation stacks from notebooks 2 and 4 (and the legacy notebook 4, if
you ran it). It does **not** cover the Gateway/Lambda/IAM/Cognito demo resources that
notebook 6 creates directly via `boto3` — run that notebook's own **Cleanup** section (near
the end) for those.

## Dependencies

The workshop leads with the AgentCore Harness: model, tools, memory, and skills are declared
as configuration. `langchain-classic` provides the chains/prompts/output-parser APIs notebook
3 uses.

Only models callable through plain serverless `InvokeModel`/`Converse` are used — nothing
that requires a Bedrock Marketplace subscription, a SageMaker endpoint deployment, or
Provisioned Throughput. Text generation runs on Amazon Nova and Anthropic Claude 4.x (via
cross-Region inference profiles).

## Additional Resources

For detailed documentation, refer to:

- [Amazon Bedrock Documentation](https://aws.amazon.com/bedrock/)
- [Amazon Bedrock AgentCore Documentation](https://aws.amazon.com/bedrock/agentcore/)
- [AWS OpenSearch Documentation](https://docs.aws.amazon.com/opensearch/)
- [AWS Lambda Documentation](https://aws.amazon.com/lambda/)

---

Start exploring the repository to build robust AI/ML applications using Amazon Bedrock and AWS services! 🚀
