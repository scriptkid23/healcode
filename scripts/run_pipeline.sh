#!/bin/bash
# Script to run the entire AI refactoring pipeline

set -e  # Exit on error

# Default variables
REPO_PATH=${1:-"./example_repo"}
ZOEKT_PORT=6070
SEARCH_PORT=8000
ZOEKT_INDEX_PATH="$HOME/.zoekt"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== AI Refactoring Pipeline ===${NC}"
echo -e "${YELLOW}Repository path: ${REPO_PATH}${NC}"

# Check if repository exists
if [ ! -d "$REPO_PATH" ]; then
    echo -e "${YELLOW}Repository directory does not exist. Creating example repo...${NC}"
    mkdir -p "$REPO_PATH"
    # Initialize a test Git repository if needed
    if [ ! -d "$REPO_PATH/.git" ]; then
        echo "Initializing Git repository..."
        cd "$REPO_PATH"
        git init
        echo "x = None" > test.py
        echo "if x == None:" >> test.py
        echo "    print('x is none')" >> test.py
        git add test.py
        git config --local user.email "test@example.com"
        git config --local user.name "Test User"
        git commit -m "Initial commit with test file"
        cd - > /dev/null
    fi
fi

# Check if Zoekt is installed
if ! command -v zoekt-webserver &> /dev/null; then
    echo -e "${YELLOW}Zoekt not found. Please install it first using scripts/install_zoekt.sh${NC}"
    exit 1
fi

# 1. Run indexer first to ensure the repository is indexed
echo -e "${GREEN}Step 1: Indexing the repository...${NC}"
poetry run indexer --repo-path "$REPO_PATH"

# 2. Start Zoekt webserver in the background
echo -e "${GREEN}Step 2: Starting Zoekt webserver...${NC}"
ZOEKT_PID=$(ps -ef | grep zoekt-webserver | grep -v grep | awk '{print $2}')
if [ -n "$ZOEKT_PID" ]; then
    echo "Zoekt webserver is already running with PID $ZOEKT_PID"
else
    zoekt-webserver -listen ":$ZOEKT_PORT" -index "$ZOEKT_INDEX_PATH" -rpc &
    ZOEKT_PID=$!
    echo "Zoekt webserver started with PID $ZOEKT_PID"
    # Wait a moment for the server to start
    sleep 2
fi

# 3. Start search proxy in the background
echo -e "${GREEN}Step 3: Starting search proxy...${NC}"
PROXY_PID=$(ps -ef | grep "python.*search-proxy" | grep -v grep | awk '{print $2}')
if [ -n "$PROXY_PID" ]; then
    echo "Search proxy is already running with PID $PROXY_PID"
else
    poetry run search-proxy --port "$SEARCH_PORT" --zoekt-url "http://localhost:$ZOEKT_PORT" &
    PROXY_PID=$!
    echo "Search proxy started with PID $PROXY_PID"
    # Wait a moment for the server to start
    sleep 2
fi

# 4. Run AI engine to find and apply refactorings
echo -e "${GREEN}Step 4: Running AI engine...${NC}"
poetry run ai-engine --repo-path "$REPO_PATH" --search-url "http://localhost:$SEARCH_PORT"

# 5. Create PR with changes
echo -e "${GREEN}Step 5: Creating PR with changes...${NC}"
poetry run pr-creator --repo-path "$REPO_PATH" --branch-name "ai-refactoring/none-comparison-fix" --commit-message "Refactor: Replace == None with is None"

echo -e "${GREEN}Pipeline completed successfully!${NC}"
echo "You can review the changes in the repository: $REPO_PATH"
echo "The changes are available in branch: ai-refactoring/none-comparison-fix"

# Trap to kill background processes when script exits
trap 'kill $ZOEKT_PID $PROXY_PID 2>/dev/null' EXIT

# Keep the script running to maintain the background processes
echo -e "${YELLOW}Press Ctrl+C to stop the servers and exit${NC}"
wait 