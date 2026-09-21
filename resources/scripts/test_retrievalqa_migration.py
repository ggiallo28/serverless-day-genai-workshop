#!/usr/bin/env python3
"""Validates the `RetrievalQA` -> plain-LCEL migration for notebook 2
(2_knowledge_bases_rag.ipynb) against live Amazon Bedrock, before that code gets copied
into the actual notebook cells.

`RetrievalQA.from_chain_type(llm=..., chain_type="stuff", retriever=..., \
return_source_documents=True, chain_type_kwargs={"prompt": claude_prompt})` lives in
`langchain_classic.chains` -- LangChain's now-legacy pre-LCEL chain abstraction. It's
replaced here with an explicit LCEL pipeline (`prompt | llm | StrOutputParser()`) wrapped
in a small function that reproduces the exact output shape the rest of the notebook
depends on: `{"result": <answer str>, "source_documents": [Document, ...]}` -- notably,
`resources/src/utils.py::format_qa_answer_with_references()` reads exactly this shape, so
this script also proves that helper still works unmodified against the new chain's output.

The retriever itself (`AmazonKnowledgeBasesRetriever`) is unaffected by this migration --
only the chain wrapping around it changes -- so this test stands in a fake retriever
returning Documents shaped like real Bedrock Knowledge Base results (same metadata keys
`AmazonKnowledgeBasesRetriever` copies over: `location.s3Location.uri`,
`source_metadata.x-amz-bedrock-kb-document-page-number`, `score`), rather than requiring a
deployed Knowledge Base.

Requires:
    - AWS credentials with `bedrock:Converse` (set `AWS_PROFILE`, or run somewhere that
      already has credentials, e.g. SageMaker Studio).
    - `AWS_REGION` (defaults to us-east-1, matching every other notebook in this workshop).

Usage:
    AWS_PROFILE=local.recube uv run --python <venv> resources/scripts/test_retrievalqa_migration.py -v
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from langchain_aws import ChatBedrockConverse
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from utils import format_qa_answer_with_references

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

PROMPT_TEMPLATE = """
Human: You are a financial advisor AI system, and provides answers to questions by using fact based and statistical information when possible.
Use the following pieces of information to provide a concise answer to the question enclosed in <question> tags.
If you don't know the answer, just say that you don't know, don't try to make up an answer.

<context>
{context}
</context>

<question>
{question}
</question>

The response should be specific and use statistics or numbers when possible.

Assistant:"""

CLAUDE_PROMPT = PromptTemplate(template=PROMPT_TEMPLATE, input_variables=["context", "question"])


# ---------------------------------------------------------------------------
# A stand-in for AmazonKnowledgeBasesRetriever -- same Document/metadata shape
# a real deployed Knowledge Base would return, so no live KB is needed to test
# the migrated chain's composition and output format.
# ---------------------------------------------------------------------------

class FakeKnowledgeBaseRetriever:
    def invoke(self, query: str):
        return [
            Document(
                page_content=(
                    "The fund's primary risks are market volatility (annualized standard "
                    "deviation of 18.4%), currency exposure to the EUR/USD pair, and "
                    "concentration risk since the top 10 holdings represent 42% of the "
                    "portfolio."
                ),
                metadata={
                    "location": {"s3Location": {"uri": "s3://demo-bucket/financials/prospectus.pdf"}},
                    "source_metadata": {"x-amz-bedrock-kb-document-page-number": 7},
                    "score": 0.91,
                },
            ),
            Document(
                page_content=(
                    "Liquidity risk is limited: the fund can meet redemption requests "
                    "within 3 business days under normal market conditions."
                ),
                metadata={
                    "location": {"s3Location": {"uri": "s3://demo-bucket/financials/prospectus.pdf"}},
                    "source_metadata": {"x-amz-bedrock-kb-document-page-number": 9},
                    "score": 0.77,
                },
            ),
        ]


def build_model() -> ChatBedrockConverse:
    return ChatBedrockConverse(temperature=0.0, model=MODEL_ID, region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Migration: RetrievalQA.from_chain_type(...) -> explicit LCEL
# ---------------------------------------------------------------------------

def format_docs(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def build_qa(model, retriever):
    """Returns a callable matching RetrievalQA's `invoke({"query": ...})` -> dict contract."""
    answer_chain = CLAUDE_PROMPT | model | StrOutputParser()

    def qa_invoke(inputs):
        question = inputs["query"]
        docs = retriever.invoke(question)
        result = answer_chain.invoke({"context": format_docs(docs), "question": question})
        return {"result": result, "source_documents": docs}

    return qa_invoke


def test_qa_answers_from_context(model, verbose=False):
    qa = build_qa(model, FakeKnowledgeBaseRetriever())
    result = qa({"query": "What are the main risks associated with this investment?"})

    if verbose:
        print(f"    result: {result['result']!r}")

    assert isinstance(result, dict), f"expected a dict, got {type(result)}"
    assert set(result.keys()) == {"result", "source_documents"}, f"unexpected keys: {result.keys()}"
    assert isinstance(result["result"], str) and result["result"], "expected a non-empty string answer"
    assert len(result["source_documents"]) == 2, "expected both fake source documents to pass through"

    text = result["result"].lower()
    assert "volatility" in text or "liquidity" in text or "concentration" in text, (
        f"expected the answer to be grounded in the fake context (volatility/liquidity/"
        f"concentration), got: {result['result']!r}"
    )


def test_format_qa_answer_with_references(model, verbose=False):
    qa = build_qa(model, FakeKnowledgeBaseRetriever())
    result = qa({"query": "What are the main risks associated with this investment?"})

    formatted = format_qa_answer_with_references(result)
    if verbose:
        print(f"    formatted:\n{formatted}")

    assert formatted.startswith("Response:\n"), "expected the formatted output to start with 'Response:'"
    assert "References:" in formatted, "expected a References section"
    assert "prospectus.pdf, page 7" in formatted, "expected page 7 reference to be extracted"
    assert "prospectus.pdf, page 9" in formatted, "expected page 9 reference to be extracted"
    assert "score: 0.910" in formatted, "expected the score to be formatted to 3 decimals"


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

TESTS = [
    ("qa_answers_from_context (RetrievalQA -> LCEL: grounded answer + shape)", test_qa_answers_from_context),
    ("format_qa_answer_with_references (unchanged helper against new chain's output)", test_format_qa_answer_with_references),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print each test's raw model output")
    args = parser.parse_args()

    print(f"Region: {AWS_REGION}  Model: {MODEL_ID}  Profile: {os.environ.get('AWS_PROFILE', '(default credential chain)')}")
    model = build_model()

    passed, failed = [], []
    for name, test_fn in TESTS:
        print(f"\n--- {name} ---")
        try:
            test_fn(model, verbose=args.verbose)
        except Exception as error:
            print(f"  FAIL: {error}")
            failed.append((name, error))
        else:
            print("  PASS")
            passed.append(name)

    print(f"\n{'=' * 70}\n{len(passed)} passed, {len(failed)} failed\n{'=' * 70}")
    if failed:
        for name, error in failed:
            print(f"FAILED: {name}\n  {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
