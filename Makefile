# Variables
COMPOSE_DEV = docker compose
ARGS = $(filter-out $@,$(MAKECMDGOALS))

.PHONY: build up up-observability identity-network down lint format test test-frontend complexity logs stress restart restart-db nuke

# DEVELOPMENT COMMANDS (Default Stack)
build:
	@echo "🛠️  Building Development Docker images..."
	$(COMPOSE_DEV) build
	$(MAKE) up

up:
	@echo "🚀 Starting Development application stack..."
	@# Created as you, not by Docker as root, if CSV_SOURCE_DIR is unset.
	@mkdir -p var/csv/validated
	@$(MAKE) --no-print-directory identity-network
	$(COMPOSE_DEV) up -d
	@echo "✨ Dev Services are up!"
	@echo "FastAPI is running on http://localhost:8100"
	@echo "Reflex UI is running on http://localhost:3100"
	@echo "RabbitMQ Management UI is running on http://localhost:15673"

up-observability:
	@echo "📊 Starting the stack with Prometheus, Loki, Alloy, and Grafana..."
	@mkdir -p var/csv/validated
	@$(MAKE) --no-print-directory identity-network
	@# The app's processes push traces and metrics to Alloy (OTLP);
	@# a plain `make up` recreates them with telemetry off again.
	OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy:4318 $(COMPOSE_DEV) --profile observability up -d
	@echo "Grafana is running on http://localhost:3130"
	@echo "Prometheus is running on http://localhost:9091"

# Night Crawler's stack owns it (and Keycloak on it); external, so
# `down` leaves it be.
identity-network:
	@docker network inspect identity >/dev/null 2>&1 || docker network create identity

down:
	@echo "🛑 Stopping Development application stack..."
	@# The profile also stops the observability services, if running.
	$(COMPOSE_DEV) --profile observability down

lint:
	$(COMPOSE_DEV) exec web ruff check .

format:
	$(COMPOSE_DEV) exec web black .
	$(COMPOSE_DEV) exec web ruff check --fix .

test:
	@echo "🧪 Running test suite inside the web container..."
	@# Telemetry off, so tests never push spans to a running Alloy.
	$(COMPOSE_DEV) exec -e OTEL_EXPORTER_OTLP_ENDPOINT= web pytest -v --cov=backend/src/data_reaper --cov-report=term-missing

test-frontend:
	@echo "🧪 Running frontend tests inside a one-off frontend container..."
	$(COMPOSE_DEV) run --rm --no-deps frontend python -m pytest -q -p no:cacheprovider tests

complexity:
	@echo "📊 Running Cyclomatic Complexity analysis..."
	$(COMPOSE_DEV) exec web radon cc backend/src/data_reaper frontend/src -s -a -n B
	@echo "📈 Checking Maintainability Index..."
	$(COMPOSE_DEV) exec web radon mi backend/src/data_reaper -s
	@echo "🔍 Gathering Raw Code Metrics..."
	$(COMPOSE_DEV) exec web radon raw backend/src/data_reaper

logs:
	$(COMPOSE_DEV) logs -f $(ARGS)

stress:
	oha -z 1s -q 10000 http://localhost:8100/

restart: down up

restart-db:
	@echo "🗑️  Dropping and recreating the database..."
	$(COMPOSE_DEV) exec db sh -c 'mongosh --quiet -u "$$MONGO_INITDB_ROOT_USERNAME" -p "$$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin "$$MONGO_INITDB_DATABASE" --eval "db.dropDatabase()"'
	@echo "🔄 Restarting the web service to recreate indexes..."
	$(COMPOSE_DEV) restart web

nuke:
	@echo "⚠️  WARNING: Nuking the Dev stack. This will delete all databases and volumes!"
	$(COMPOSE_DEV) down --volumes --rmi all --remove-orphans
	@echo "✨ Clean slate achieved."

