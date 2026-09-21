STUDIO_STACK_NAME ?= genai-workshop-studio
STUDIO_REGION ?= us-east-1
LCC_VERSION ?= v1

.DEFAULT_GOAL := help
.PHONY: help install lock env jupyter validate clean tree studio-init studio-update studio-url studio-destroy teardown teardown-dry-run

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-10s %s\n", $$1, $$2}'

tree: ## Show what's inside resources/ so you never have to dig for it by hand
	@echo "Notebooks (repo root): 0_bedrock_basics.ipynb ... 6_agentcore_advanced.ipynb"
	@echo ""
	@if command -v tree >/dev/null 2>&1; then \
		tree -I '__pycache__|*.zip' resources; \
	else \
		find resources -not -path '*__pycache__*' -not -name '*.zip' | sort | sed 's|[^/]*/|  |g'; \
	fi

install: ## Install/refresh all Python dependencies from requirements.txt
	uv pip install --no-build-isolation --force-reinstall -r requirements.txt

lock: ## Regenerate requirements.txt from requirements.in after editing it
	uv pip compile requirements.in -o requirements.txt

env: ## Create a blank .env file if one doesn't exist yet
	@test -f .env || printf '%s\n' \
		'AWS_ACCESS_KEY_ID=""' \
		'AWS_SECRET_ACCESS_KEY=""' \
		'AWS_SESSION_TOKEN=""' > .env
	@echo ".env is ready -- fill in your AWS credentials before running notebook 0."

jupyter: ## Launch Jupyter Lab in this repo
	jupyter lab

validate: ## Sanity-check every notebook parses as valid JSON (no AWS calls, free)
	@count=0; \
	for f in $$(find . -maxdepth 2 -name '*.ipynb' -not -path './.git/*'); do \
		python3 -c "import json; json.load(open('$$f'))" || exit 1; \
		count=$$((count + 1)); \
	done; \
	echo "$$count notebooks are valid JSON."

clean: ## Remove local caches and notebook checkpoints (safe, no AWS resources touched)
	find . -type d -name '__pycache__' -not -path './.git/*' -exec rm -rf {} +
	find . -type d -name '.ipynb_checkpoints' -not -path './.git/*' -exec rm -rf {} +

studio-init: ## Deploy a ready-to-go SageMaker Studio (JupyterLab) for this workshop -- creates real AWS resources
	@vpc_id="$(VPC_ID)"; \
	subnet_ids="$(SUBNET_IDS)"; \
	if [ -z "$$vpc_id" ]; then \
		vpc_id=$$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
			--query 'Vpcs[0].VpcId' --output text --region $(STUDIO_REGION)); \
	fi; \
	if [ "$$vpc_id" = "None" ] || [ -z "$$vpc_id" ]; then \
		echo "No default VPC found in $(STUDIO_REGION), and no VPC_ID was given."; \
		echo ""; \
		echo "List every VPC in this account/region and pick one (any VPC with at least"; \
		echo "one public subnet works fine for this workshop):"; \
		echo "  aws ec2 describe-vpcs --region $(STUDIO_REGION) --query 'Vpcs[].{Id:VpcId,Default:IsDefault,Name:Tags[?Key==\`Name\`]|[0].Value}' --output table"; \
		echo ""; \
		echo "Then list the subnets inside the VPC you picked:"; \
		echo "  aws ec2 describe-subnets --region $(STUDIO_REGION) --filters Name=vpc-id,Values=<VPC_ID> --query 'Subnets[].SubnetId' --output text"; \
		echo ""; \
		echo "Then re-run with both set explicitly, e.g.:"; \
		echo "  make studio-init VPC_ID=vpc-xxxxxxxx SUBNET_IDS=subnet-aaaa,subnet-bbbb"; \
		exit 1; \
	fi; \
	if [ -z "$$subnet_ids" ]; then \
		subnet_ids=$$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$$vpc_id \
			--query 'Subnets[].SubnetId' --output text --region $(STUDIO_REGION) | tr '\t' ','); \
	fi; \
	echo "Using VPC $$vpc_id, subnets $$subnet_ids"; \
	if [ -n "$(SKIP_LIFECYCLE)" ]; then \
		echo "SKIP_LIFECYCLE set -- not attaching a Lifecycle Configuration this deploy"; \
		echo "(the $(STUDIO_STACK_NAME)-lifecycle stack, if it already exists, is left untouched -- only this deploy omits the reference)."; \
		lcc_arn=""; \
	else \
		echo "Deploying $(STUDIO_STACK_NAME)-lifecycle (Studio Lifecycle Configuration $(LCC_VERSION): clones the repo + runs"; \
		echo "'pip install -r requirements.txt', including the agentcore CLI, on space start)..."; \
		aws cloudformation deploy \
			--template-file resources/infra/sagemaker_studio_lifecycle_template.yaml \
			--stack-name $(STUDIO_STACK_NAME)-lifecycle \
			--region $(STUDIO_REGION) \
			--no-fail-on-empty-changeset \
			--parameter-overrides LifecycleConfigName=$(STUDIO_STACK_NAME)-lifecycle ScriptVersion=$(LCC_VERSION); \
		lcc_arn=$$(aws cloudformation describe-stacks --stack-name $(STUDIO_STACK_NAME)-lifecycle --region $(STUDIO_REGION) \
			--query "Stacks[0].Outputs[?OutputKey=='LifecycleConfigArn'].OutputValue" --output text); \
		if [ -z "$$lcc_arn" ] || [ "$$lcc_arn" = "None" ]; then \
			echo "Could not read LifecycleConfigArn back from the $(STUDIO_STACK_NAME)-lifecycle stack --"; \
			echo "check its status: aws cloudformation describe-stacks --stack-name $(STUDIO_STACK_NAME)-lifecycle --region $(STUDIO_REGION)"; \
			exit 1; \
		fi; \
		echo "(edited resources/scripts/studio_lifecycle_config.sh? Keep it in sync with the embedded copy in"; \
		echo "resources/infra/sagemaker_studio_lifecycle_template.yaml, then re-run with LCC_VERSION=v2 (or higher) --"; \
		echo "LCC content is immutable in the AWS API, so bumping the version forces a clean replacement instead"; \
		echo "of a failed in-place update.)"; \
	fi; \
	echo "LifecycleConfigArn: $${lcc_arn:-<none>}"; \
	aws cloudformation deploy \
		--template-file resources/infra/sagemaker_studio_init_template.yaml \
		--stack-name $(STUDIO_STACK_NAME) \
		--region $(STUDIO_REGION) \
		--capabilities CAPABILITY_NAMED_IAM \
		--no-fail-on-empty-changeset \
		--parameter-overrides VpcId=$$vpc_id SubnetIds=$$subnet_ids LifecycleConfigArn=$$lcc_arn
	@$(MAKE) studio-url

studio-update: studio-init ## Alias for studio-init -- safe to re-run any time to push template/role changes to the existing stack

studio-url: ## Print the console URL and role ARN for the deployed Studio environment
	@aws cloudformation describe-stacks --stack-name $(STUDIO_STACK_NAME) --region $(STUDIO_REGION) \
		--query 'Stacks[0].Outputs' --output table

studio-destroy: ## Tear down the SageMaker Studio environment (destructive -- confirms first)
	@echo "This deletes the Studio domain/user/space/role in stack $(STUDIO_STACK_NAME) ($(STUDIO_REGION)),"
	@echo "plus its $(STUDIO_STACK_NAME)-lifecycle Lifecycle Configuration stack."
	@read -p "Type 'yes' to continue: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		aws cloudformation delete-stack --stack-name $(STUDIO_STACK_NAME) --region $(STUDIO_REGION); \
		aws cloudformation wait stack-delete-complete --stack-name $(STUDIO_STACK_NAME) --region $(STUDIO_REGION) 2>/dev/null || true; \
		aws cloudformation delete-stack --stack-name $(STUDIO_STACK_NAME)-lifecycle --region $(STUDIO_REGION); \
		echo "Delete requested -- check the CloudFormation console for progress."; \
	else \
		echo "Aborted."; \
	fi

teardown-dry-run: ## Show what workshop AWS resources exist right now, without deleting anything
	python3 resources/scripts/cleanup_workshop.py --dry-run

teardown: ## Find and delete every AWS resource created by running notebooks 2/4/5 (destructive -- asks before deleting)
	python3 resources/scripts/cleanup_workshop.py
