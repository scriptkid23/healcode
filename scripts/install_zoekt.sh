#!/bin/bash
# Script to install Zoekt from source

set -e  # Exit on error

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "Go is not installed. Please install Go 1.17+ first."
    echo "Visit https://go.dev/doc/install for installation instructions."
    exit 1
fi

# Print Go version
go version

# Set GOPATH if not already set
if [ -z "$GOPATH" ]; then
    export GOPATH=$HOME/go
    echo "GOPATH not set, using default: $GOPATH"
    # Add the following to your shell configuration file (.bashrc, .zshrc, etc.)
    echo "Consider adding 'export GOPATH=\$HOME/go' to your shell configuration."
fi

# Ensure GOBIN is in PATH
if [[ ":$PATH:" != *":$GOPATH/bin:"* ]]; then
    export PATH=$PATH:$GOPATH/bin
    echo "Added $GOPATH/bin to PATH temporarily."
    echo "Consider adding 'export PATH=\$PATH:\$GOPATH/bin' to your shell configuration."
fi

echo "Installing Zoekt..."

# Install zoekt-git-index - tool to create indices from a Git repository
go install github.com/sourcegraph/zoekt/cmd/zoekt-git-index@latest

# Install zoekt-webserver - web interface and API server
go install github.com/sourcegraph/zoekt/cmd/zoekt-webserver@latest

# Verify installation
if command -v zoekt-git-index &> /dev/null && command -v zoekt-webserver &> /dev/null; then
    echo "Zoekt installation successful!"
    echo "zoekt-git-index: $(which zoekt-git-index)"
    echo "zoekt-webserver: $(which zoekt-webserver)"
    
    # Print usage instructions
    echo ""
    echo "Usage instructions:"
    echo "1. Index a Git repository:"
    echo "   zoekt-git-index /path/to/repo"
    echo ""
    echo "2. Start the web server:"
    echo "   zoekt-webserver -listen :6070 -index $HOME/.zoekt -rpc"
    echo ""
    echo "3. Access the web interface at http://localhost:6070"
    echo "   Or use the API at http://localhost:6070/search/api/search?q=your_query"
else
    echo "Installation failed. Please check for errors above."
    exit 1
fi 