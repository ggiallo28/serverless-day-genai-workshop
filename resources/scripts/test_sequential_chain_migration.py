#!/usr/bin/env python3
"""Validates the `LLMChain`+`SequentialChain` -> LCEL exercise solution already present in
notebook 3 (3_langchain_agents.ipynb) against live Amazon Bedrock.

Unlike the other migration scripts in this directory, this isn't new migration code: the
notebook already shows the legacy `langchain_classic.chains.LLMChain`/`SequentialChain`
Tree-of-Thoughts demo (cells `c2ea4b52`/`242131db` in solutions/3_langchain_agents.ipynb),
immediately followed by an exercise ("rewrite the above logic by using the `|` operator")
whose hidden solution / filled cell (`3636ad2a`/`13ecd06f`) already does exactly that. This
script just runs that existing solution verbatim against live Bedrock to prove it actually
works end to end -- this notebook has had real latent bugs found by review before, so
"already written" isn't the same as "verified".

Requires:
    - AWS credentials with `bedrock:Converse` (set `AWS_PROFILE`, or run somewhere that
      already has credentials, e.g. SageMaker Studio).
    - `AWS_REGION` (defaults to us-east-1, matching every other notebook in this workshop).

Usage:
    AWS_PROFILE=local.recube uv run --python <venv> resources/scripts/test_sequential_chain_migration.py -v
"""
import argparse
import json
import os
import sys

from langchain_aws import ChatBedrock
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CHAIN_CONFIG_PATH = os.path.join(REPO_ROOT, "resources", "config", "chain_config.json")


def load_prompts():
    """Same four PromptTemplates the notebook builds from resources/config/chain_config.json."""
    with open(CHAIN_CONFIG_PATH) as f:
        config = json.load(f)

    return {
        "step1": PromptTemplate(template=config["step1"]["prompt"], input_variables=["input", "perfect_factors"]),
        "step2": PromptTemplate(template=config["step2"]["prompt"], input_variables=["solutions"]),
        "step3": PromptTemplate(template=config["step3"]["prompt"], input_variables=["review"]),
        "step4": PromptTemplate(template=config["step4"]["prompt"], input_variables=["deepen_thought_process"]),
    }


# ---------------------------------------------------------------------------
# The notebook's existing LCEL solution (cell 13ecd06f in solutions), copied verbatim.
# ---------------------------------------------------------------------------

def build_overall_chain(model, prompts):
    llm = ChatBedrock(temperature=0, model=model, region=AWS_REGION)

    chain1 = prompts["step1"] | llm | {"solutions": StrOutputParser()}
    chain2 = prompts["step2"] | llm | {"review": StrOutputParser()}
    chain3 = prompts["step3"] | llm | {"deepen_thought_process": StrOutputParser()}
    chain4 = prompts["step4"] | llm | {"ranked_solutions": StrOutputParser()}

    return chain1 | chain2 | chain3 | chain4


def test_chain_of_thought_pipeline(verbose=False):
    prompts = load_prompts()
    overall_chain = build_overall_chain(MODEL_ID, prompts)

    params = {
        "input": "human colonization of Mars",
        "perfect_factors": "The distance between Earth and Mars is very large, making regular resupply difficult",
    }
    result = overall_chain.invoke(params)

    if verbose:
        print(f"    result keys: {list(result.keys())}")
        print(f"    ranked_solutions:\n{result['ranked_solutions']}")

    assert set(result.keys()) == {"ranked_solutions"}, (
        f"expected only the final step's output key to survive the pipe, got: {list(result.keys())}"
    )
    text = result["ranked_solutions"]
    assert isinstance(text, str) and len(text) > 50, f"expected a substantial ranked-solutions write-up, got: {text!r}"
    assert "mars" in text.lower() or "solution" in text.lower(), (
        f"expected the final answer to actually discuss the input problem, got: {text!r}"
    )


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

TESTS = [
    ("chain_of_thought_pipeline (LLMChain+SequentialChain -> LCEL pipe, existing notebook solution)", test_chain_of_thought_pipeline),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print each test's raw model output")
    args = parser.parse_args()

    print(f"Region: {AWS_REGION}  Model: {MODEL_ID}  Profile: {os.environ.get('AWS_PROFILE', '(default credential chain)')}")

    passed, failed = [], []
    for name, test_fn in TESTS:
        print(f"\n--- {name} ---")
        try:
            test_fn(verbose=args.verbose)
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
