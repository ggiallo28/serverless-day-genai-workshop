STUDIO_STACK_NAME ?= genai-workshop-studio
STUDIO_REGION ?= us-east-1

.DEFAULT_GOAL := help
.PHONY: help install lock env jupyter validate clean studio-init studio-url studio-destroy teardown teardown-dry-run

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-10s %s\n", $$1, $$2}'

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
	aws cloudformation deploy \
		--template-file infra/sagemaker_studio_init_template.yaml \
		--stack-name $(STUDIO_STACK_NAME) \
		--region $(STUDIO_REGION) \
		--capabilities CAPABILITY_NAMED_IAM \
		--parameter-overrides VpcId=$$vpc_id SubnetIds=$$subnet_ids
	@$(MAKE) studio-url

studio-url: ## Print the console URL and role ARN for the deployed Studio environment
	@aws cloudformation describe-stacks --stack-name $(STUDIO_STACK_NAME) --region $(STUDIO_REGION) \
		--query 'Stacks[0].Outputs' --output table

studio-destroy: ## Tear down the SageMaker Studio environment (destructive -- confirms first)
	@echo "This deletes the Studio domain/user/space/role in stack $(STUDIO_STACK_NAME) ($(STUDIO_REGION))."
	@read -p "Type 'yes' to continue: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		aws cloudformation delete-stack --stack-name $(STUDIO_STACK_NAME) --region $(STUDIO_REGION); \
		echo "Delete requested -- check the CloudFormation console for progress."; \
	else \
		echo "Aborted."; \
	fi

teardown-dry-run: ## Show what workshop AWS resources exist right now, without deleting anything
	python3 scripts/cleanup_workshop.py --dry-run

teardown: ## Find and delete every AWS resource created by running notebooks 2/4/5 (destructive -- asks before deleting)
	python3 scripts/cleanup_workshop.py
