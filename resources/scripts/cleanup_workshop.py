#!/usr/bin/env python3
"""Discover and tear down AWS resources created while running this workshop.

Covers what nothing else in the repo cleans up automatically:
  - The AgentCore CLI projects from notebooks 4/5 (RestaurantConcierge,
    RestaurantEvents) -- harness, memory, gateway, and their underlying
    AgentCore-managed CDK stack. Checked both at the repo root and under
    solutions/, since either notebook copy may have been the one actually run.
  - The CloudFormation stacks from notebooks 2 and 4 (and the legacy notebook 4,
    if you ran Bedrock Agents Classic) -- matched by the naming prefixes those
    notebooks actually use, since each run appends a random UUID.

Does NOT cover: the Gateway/Lambda/IAM/Cognito demo resources notebook 6 creates
directly via boto3 -- that notebook has its own "Cleanup" section at the end,
run those cells instead (this script tells you so at the end).

Does NOT cover: the SageMaker Studio environment from `make studio-init` --
use `make studio-destroy` for that.

Usage:
    python3 scripts/cleanup_workshop.py            # discover + ask before deleting
    python3 scripts/cleanup_workshop.py --yes       # discover + delete without asking
    python3 scripts/cleanup_workshop.py --dry-run   # discover only, never deletes
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"

STACK_PREFIXES = [
    "BedrockRAGStack-",              # notebook 2 (both OpenSearch and S3 Vectors variants)
    "agentcore-restaurant-harness-role-",  # notebook 4
    "BedrockAgentsStack-",           # legacy/4_bedrock_agents.ipynb, if it was ever run
]

AGENTCORE_PROJECTS = [
    "RestaurantConcierge",  # notebook 4
    "RestaurantEvents",     # notebook 5
]

ACTIVE_STACK_STATUSES = [
    "CREATE_COMPLETE", "UPDATE_COMPLETE", "ROLLBACK_COMPLETE",
    "CREATE_FAILED", "UPDATE_FAILED", "UPDATE_ROLLBACK_COMPLETE",
    "REVIEW_IN_PROGRESS",
]


def discover_stacks(cfn):
    matches = []
    paginator = cfn.get_paginator("list_stacks")
    for page in paginator.paginate(StackStatusFilter=ACTIVE_STACK_STATUSES):
        for stack in page["StackSummaries"]:
            name = stack["StackName"]
            if any(name.startswith(p) for p in STACK_PREFIXES):
                matches.append(name)
            elif name.startswith("AgentCore-") and name.endswith("-default"):
                # The AgentCore CLI's own CDK-managed stack for each project
                project = name[len("AgentCore-"):-len("-default")]
                if project in AGENTCORE_PROJECTS:
                    matches.append(name)
    return sorted(set(matches))


def discover_agentcore_projects(repo_root: Path):
    found = []
    for name in AGENTCORE_PROJECTS:
        for base in (repo_root, repo_root / "solutions"):
            project_dir = base / name
            if (project_dir / "agentcore").is_dir():
                found.append(project_dir)
    return found


def agentcore_cli_available() -> bool:
    return shutil.which("agentcore") is not None


def delete_agentcore_project(project_dir: Path, dry_run: bool):
    print(f"\n--- AgentCore project: {project_dir.name} ---")
    if not agentcore_cli_available():
        print("  `agentcore` CLI not found on PATH -- skipping `agentcore remove all`.")
        print("  Its resources may still exist; the matching AgentCore-*-default CFN "
              "stack below still gets deleted, but harness/memory/gateway records "
              "outside CloudFormation may need manual cleanup via the AWS console.")
    elif dry_run:
        print(f"  Would run: agentcore remove all --yes  (in {project_dir})")
    else:
        try:
            subprocess.run(
                ["agentcore", "remove", "all", "--yes"],
                cwd=project_dir,
                check=True,
                env={"AWS_REGION": REGION, "AWS_DEFAULT_REGION": REGION, **_os_environ()},
            )
        except subprocess.CalledProcessError as e:
            print(f"  `agentcore remove all` failed ({e}); continuing with stack/dir cleanup.")

    if dry_run:
        print(f"  Would remove local directory: {project_dir}")
    else:
        shutil.rmtree(project_dir, ignore_errors=True)
        print(f"  Removed local directory: {project_dir}")


def _os_environ():
    import os
    return dict(os.environ)


def delete_stack(cfn, stack_name: str, dry_run: bool):
    if dry_run:
        print(f"  Would delete stack: {stack_name}")
        return
    try:
        cfn.delete_stack(StackName=stack_name)
        print(f"  Delete requested for stack: {stack_name}")
    except ClientError as e:
        print(f"  Failed to delete stack {stack_name}: {e}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="Delete without asking for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Only discover and print, never delete")
    parser.add_argument("--region", default=REGION, help=f"AWS region (default: {REGION})")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    cfn = boto3.client("cloudformation", region_name=args.region)

    print(f"Scanning region {args.region} for workshop resources...\n")

    stacks = discover_stacks(cfn)
    projects = discover_agentcore_projects(repo_root)

    if not stacks and not projects:
        print("Nothing found. Either everything is already cleaned up, or nothing has "
              "been deployed from this account/region yet.")
        return

    print("Found:")
    for p in projects:
        print(f"  - AgentCore project (local): {p}")
    for s in stacks:
        print(f"  - CloudFormation stack: {s}")

    if not args.dry_run and not args.yes:
        confirm = input("\nDelete all of the above? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted -- nothing deleted.")
            return

    for project_dir in projects:
        delete_agentcore_project(project_dir, args.dry_run)

    print()
    for stack_name in stacks:
        delete_stack(cfn, stack_name, args.dry_run)

    print(
        "\nNote: this script does not touch the Gateway/Lambda/IAM/Cognito demo "
        "resources created directly inside 6_agentcore_advanced.ipynb -- run that "
        "notebook's own 'Cleanup' section (near the end) for those.\n"
        "It also does not touch the SageMaker Studio environment -- use "
        "`make studio-destroy` for that."
    )


if __name__ == "__main__":
    sys.exit(main())
