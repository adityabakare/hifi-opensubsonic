.PHONY: env env-force up down logs

env: ## Generate .env from .env.example with random secrets
	@if [ -f .env ]; then \
		echo "⚠️  .env already exists. Run 'make env-force' to overwrite."; \
		exit 1; \
	fi
	@cp .env.example .env
	@JWT=$$(python3 -c "import secrets; print(secrets.token_hex(32))") && \
	 FERNET=$$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())") && \
	 DBPASS=$$(python3 -c "import secrets; print(secrets.token_urlsafe(16))") && \
	 sed -i.bak "s|JWT_SECRET=CHANGE_ME|JWT_SECRET=$$JWT|" .env && \
	 sed -i.bak "s|TOKEN_ENCRYPTION_KEY=CHANGE_ME|TOKEN_ENCRYPTION_KEY=$$FERNET|" .env && \
	 sed -i.bak "s|POSTGRES_PASSWORD=CHANGE_ME|POSTGRES_PASSWORD=$$DBPASS|" .env && \
	 rm -f .env.bak
	@echo "✅ .env generated with random secrets."

env-force: ## Regenerate .env (overwrites existing)
	@rm -f .env
	@$(MAKE) env

up: ## Start all services in background
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail service logs
	docker compose logs -f

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
