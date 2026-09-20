#!/bin/bash
# SageMaker Studio Lifecycle Configuration (JupyterLab app type).
# Runs automatically on space start: clones this repo and installs its dependencies
# (including bedrock-agentcore-starter-toolkit, which provides the `agentcore` CLI) so a
# fresh JupyterLab space is immediately ready to run the workshop notebooks.
#
# NOTE: JupyterLab lifecycle scripts have a 5-minute execution budget. Installing the full
# requirements.txt is the slowest step here -- if it ever times out, the fallback is just
# opening a terminal in Studio and running `make install` once by hand.
set -eux

LOG_FILE="/home/sagemaker-user/.workshop-lifecycle.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] workshop lifecycle script starting"

REPO_DIR="/home/sagemaker-user/serverless-day-genai-workshop"
REPO_URL="https://github.com/ggiallo28/serverless-day-genai-workshop.git"

if [ -d "$REPO_DIR/.git" ]; then
  echo "$REPO_DIR already exists, skipping clone"
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
pip install --no-build-isolation --force-reinstall -r requirements.txt

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] workshop lifecycle script done"
