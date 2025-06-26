# Claris - Intelligent Code Improvement System

**Claris empowers developers by detecting bugs, suggesting improvements, and applying smart fixes automatically, all while maintaining the spirit of your code.**

## 🌟 Overview

Claris is an advanced AI-powered code improvement system that automatically analyzes your codebase, detects potential issues, and creates pull requests with intelligent fixes and enhancements. Built with a robust Git plugin architecture, Claris seamlessly integrates into your development workflow to maintain code quality without disrupting your coding flow.

## ✨ Key Features

### 🤖 **AI-Powered Code Analysis**
- Intelligent bug detection and code smell identification
- Context-aware code improvements using advanced AI models (GPT-4/CodeLlama)
- Maintains your code's original style and intent

### 🔧 **Automated Code Fixing**
- ESLint integration for automated code formatting
- Smart refactoring suggestions
- Automatic application of best practices

### 🔄 **Seamless Git Integration**
- Multi-provider Git support (GitHub, GitLab, Bitbucket)
- Automated pull request creation
- Branch management and conflict resolution
- Webhook integration for real-time triggers

### 🔍 **Advanced Code Search**
- Zoekt-powered code search engine
- Fast semantic code discovery
- Context-aware code analysis

### 🔐 **Enterprise-Grade Security**
- Secure credential management with encryption
- Role-based access control (RBAC)
- Audit logging and compliance support

## 🏗️ Architecture

Claris follows a modern microservices architecture with the following core components:

```
┌─────────────────────────────────────────────────┐
│                API Layer                        │
├─────────────────────────────────────────────────┤
│              Business Logic Layer               │
├─────────────────────────────────────────────────┤
│               Data Access Layer                 │
├─────────────────────────────────────────────────┤
│              Infrastructure Layer               │
└─────────────────────────────────────────────────┘
```

### Core Components

- **Git Operations Engine**: Advanced Git operations with GitPython integration
- **AI Processing Engine**: Code analysis and improvement generation
- **Search Engine**: Zoekt-powered code search and indexing
- **Webhook Processor**: Real-time Git provider event handling
- **Credentials Manager**: Secure credential storage and management
- **Build Trigger System**: Automated CI/CD pipeline integration

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Poetry (for dependency management)
- Docker & Docker Compose
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd claris
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start the services:**
   ```bash
   docker-compose up -d
   ```

5. **Run the API server:**
   ```bash
   poetry run uvicorn gitplugin.api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### First Steps

1. **Create credentials for your Git provider:**
   ```bash
   curl --location 'http://localhost:8000/credentials' \
   --header 'Content-Type: application/json' \
   --data '{
       "name": "my-github",
       "type": "token",
       "token": "your_github_token"
   }'
   ```

2. **Set up a repository:**
   ```bash
   curl --location 'http://localhost:8000/git/setup' \
   --header 'Content-Type: application/json' \
   --data '{
       "repo_url": "https://github.com/your-org/your-repo.git",
       "credential_name": "my-github",
       "workspace_path": "./workspace"
   }'
   ```

3. **Check repository status:**
   ```bash
   curl 'http://localhost:8000/git/status?workspace_path=./workspace'
   ```

## 📖 API Documentation

### Health Check
```bash
GET /health
```

### Credentials Management
```bash
POST /credentials          # Create credential
GET /credentials           # List credentials
DELETE /credentials/{name} # Delete credential
```

### Git Operations
```bash
POST /git/setup           # Setup repository
POST /git/pull            # Pull changes
POST /git/commit          # Commit changes
POST /git/push            # Push changes
GET /git/status           # Get repository status
POST /git/branch/create   # Create branch
POST /git/branch/switch   # Switch branch
```

### Advanced Workflows
```bash
POST /git/workflow/complete  # Complete Git workflow (branch + commit + PR)
POST /git/pull-request       # Create pull request
```

## 🔧 Configuration

### Environment Variables

```bash
# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/claris

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your_secret_key_here

# AI Service Configuration
OPENAI_API_KEY=your_openai_api_key
AI_MODEL=gpt-4

# Git Configuration
DEFAULT_BRANCH=main
WORKSPACE_BASE_PATH=./workspaces
```

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  claris-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/claris
    depends_on:
      - postgres
      - redis
```

## 🔄 Workflow

### Automatic Code Improvement Process

1. **Code Detection**: Monitor repositories for changes via webhooks or polling
2. **Code Analysis**: Use Zoekt search to find relevant code context
3. **AI Processing**: Analyze code and generate improvements using AI models
4. **Code Formatting**: Apply ESLint fixes and formatting
5. **Git Operations**: Create branch, commit changes, and push to remote
6. **Pull Request**: Automatically create PR with improvements

### Request Processing Flow

```mermaid
flowchart TD
    START([Start]) --> REQ["Receive API request"]
    REQ --> SEARCH["Zoekt Search<br/>Find related code"]
    SEARCH --> AIPROCESS["AI Processing<br/>Generate improvements"]
    AIPROCESS --> ESLINT["ESLint --fix<br/>Format code"]
    ESLINT --> BRANCH["Create new Git branch"]
    BRANCH --> COMMIT["Commit changes"]
    COMMIT --> PUSH["Push to remote"]
    PUSH --> CREATEPR["Create Pull Request"]
    CREATEPR --> SUCCESS["Return PR URL"]
```

## 🔧 Development

### Project Structure

```
claris/
├── gitplugin/              # Main Python package
│   ├── api/               # FastAPI application
│   │   ├── main.py        # API entry point
│   │   ├── middleware.py  # Custom middleware
│   │   └── routes/        # API route modules
│   ├── core/              # Core business logic
│   │   ├── credentials.py # Credential management
│   │   ├── git_operations.py # Git operations
│   │   └── workspace.py   # Workspace management
├── architecture/          # System architecture docs
├── docker/               # Docker configurations
├── scripts/              # Utility scripts
└── tests/               # Test suite
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=gitplugin

# Run specific test file
poetry run pytest tests/test_git_operations.py
```

### Code Quality

```bash
# Format code
poetry run black gitplugin/

# Lint code
poetry run flake8 gitplugin/

# Type checking
poetry run mypy gitplugin/
```

## 🔒 Security

### Authentication & Authorization
- API key-based authentication
- Role-based access control (RBAC)
- Secure credential storage with encryption

### Data Protection
- Encryption at rest for sensitive data
- TLS/SSL for data in transit
- Audit logging for compliance

### Network Security
- IP whitelisting for webhooks
- Rate limiting
- DDoS protection

## 📊 Monitoring

### Health Checks
- `/health` - System health status
- `/ready` - Readiness probe for Kubernetes
- Component-level health monitoring

### Metrics
- Build trigger metrics
- Git operation performance
- Webhook processing statistics
- AI processing latency

### Logging
- Structured logging with JSON format
- Audit trail for security events
- Performance monitoring

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [Full Documentation](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-org/claris/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/claris/discussions)

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [GitPython](https://gitpython.readthedocs.io/)
- Search powered by [Zoekt](https://github.com/google/zoekt)
- AI integration with OpenAI GPT models

---

**Claris** - Making your code crystal clear, one commit at a time! 💎✨
