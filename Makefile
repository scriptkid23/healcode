.PHONY: setup install-zoekt index start-zoekt start-proxy run-ai run-pr run stop clean

# Default repository path
REPO_PATH ?= ./example_repo

# Default ports
ZOEKT_PORT ?= 6070
SEARCH_PORT ?= 8000

# Setup the project
setup:
	@echo "Setting up AI Refactoring project..."
	@poetry install
	@mkdir -p $(REPO_PATH)
	@if [ ! -d "$(REPO_PATH)/.git" ]; then \
		echo "Initializing Git repository in $(REPO_PATH)..."; \
		cd $(REPO_PATH) && git init && \
		echo "x = None" > test.py && \
		echo "if x == None:" >> test.py && \
		echo "    print('x is none')" >> test.py && \
		git add test.py && \
		git config --local user.email "test@example.com" && \
		git config --local user.name "Test User" && \
		git commit -m "Initial commit with test file"; \
	fi

# Install Zoekt from source
install-zoekt:
	@echo "Installing Zoekt..."
	@bash scripts/install_zoekt.sh

# Index the repository with Zoekt
index:
	@echo "Indexing repository $(REPO_PATH)..."
	@poetry run indexer --repo-path $(REPO_PATH)

# Start Zoekt webserver
start-zoekt:
	@echo "Starting Zoekt webserver on port $(ZOEKT_PORT)..."
	@zoekt-webserver -listen :$(ZOEKT_PORT) -index $(HOME)/.zoekt -rpc &
	@echo "Zoekt webserver started! Access at http://localhost:$(ZOEKT_PORT)"

# Start search proxy
start-proxy:
	@echo "Starting search proxy on port $(SEARCH_PORT)..."
	@poetry run search-proxy --port $(SEARCH_PORT) --zoekt-url http://localhost:$(ZOEKT_PORT) &
	@echo "Search proxy started! API available at http://localhost:$(SEARCH_PORT)"

# Run AI engine
run-ai:
	@echo "Running AI engine to find and apply refactorings..."
	@poetry run ai-engine --repo-path $(REPO_PATH) --search-url http://localhost:$(SEARCH_PORT)

# Run PR creator
run-pr:
	@echo "Creating PR with changes..."
	@poetry run pr-creator --repo-path $(REPO_PATH) --branch-name "ai-refactoring/none-comparison-fix" --commit-message "Refactor: Replace == None with is None"

# Run the full pipeline
run:
	@bash scripts/run_pipeline.sh $(REPO_PATH)

# Start services with Docker Compose
docker-start:
	@echo "Starting services with Docker Compose..."
	@docker-compose up -d zoekt search-proxy
	@echo "Services started! Zoekt UI available at http://localhost:$(ZOEKT_PORT)"

# Run the entire pipeline with Docker Compose
docker-run:
	@echo "Running the full pipeline with Docker Compose..."
	@docker-compose up --build

# Stop all Docker Compose services
docker-stop:
	@echo "Stopping Docker Compose services..."
	@docker-compose down

# Clean up generated files
clean:
	@echo "Cleaning up..."
	@rm -rf ./.zoekt-index
	@echo "Clean complete!"

# Display help information
help:
	@echo "AI Refactoring Makefile commands:"
	@echo "  make setup         - Set up the project (install dependencies and create test repo)"
	@echo "  make install-zoekt - Install Zoekt from source"
	@echo "  make index         - Index the repository with Zoekt"
	@echo "  make start-zoekt   - Start Zoekt webserver"
	@echo "  make start-proxy   - Start search proxy"
	@echo "  make run-ai        - Run AI engine"
	@echo "  make run-pr        - Run PR creator"
	@echo "  make run           - Run the full pipeline"
	@echo "  make docker-start  - Start services with Docker Compose"
	@echo "  make docker-run    - Run the entire pipeline with Docker Compose"
	@echo "  make docker-stop   - Stop Docker Compose services"
	@echo "  make clean         - Clean up generated files"
	@echo "  make help          - Display this help information" 