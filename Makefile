SHELL := /bin/bash

TF ?= terraform
AWS ?= aws
INFRA_DIR := infra
SITE_DIR := site
SITE_CONFIG := $(SITE_DIR)/config.js
SITE_CONFIG_TEMPLATE := $(SITE_DIR)/config.template.js
SITE_CONFIG_RENDERER := ./scripts/render_site_config.sh
TF_APPLY_ARGS ?=
AWS_S3_SYNC_ARGS ?= --delete

.PHONY: help infra-init infra-plan infra-apply site-config site-sync deploy

help:
	@printf '%s\n' \
		'make infra-init   # terraform init を実行' \
		'make infra-plan   # terraform plan を実行' \
		'make infra-apply  # terraform apply を実行' \
		'make site-config  # site/config.js を再生成' \
		'make site-sync    # site/ を S3 に再配信' \
		'make deploy       # terraform apply 後に site 再配信まで実行'

infra-init:
	$(TF) -chdir=$(INFRA_DIR) init

infra-plan: infra-init
	$(TF) -chdir=$(INFRA_DIR) plan

infra-apply: infra-init
	$(TF) -chdir=$(INFRA_DIR) apply $(TF_APPLY_ARGS)

site-config: $(SITE_CONFIG_TEMPLATE) $(SITE_CONFIG_RENDERER)
	$(SITE_CONFIG_RENDERER) \
		"$$( $(TF) -chdir=$(INFRA_DIR) output -raw aws_region )" \
		"$$( $(TF) -chdir=$(INFRA_DIR) output -raw cognito_hosted_ui_domain )" \
		"$$( $(TF) -chdir=$(INFRA_DIR) output -raw cognito_user_pool_client_id )" \
		"$$( $(TF) -chdir=$(INFRA_DIR) output -raw cloudfront_domain_name )" \
		"$$( $(TF) -chdir=$(INFRA_DIR) output -raw documents_api_base_url )" \
		> $(SITE_CONFIG)

site-sync: site-config
	$(AWS) s3 sync $(SITE_DIR)/ "s3://$$( $(TF) -chdir=$(INFRA_DIR) output -raw site_bucket_name )" $(AWS_S3_SYNC_ARGS)

deploy: infra-apply site-sync
