# AI Refactoring System Structure

ai-refactoring/
├── pyproject.toml         # Poetry project definition and dependencies
├── README.md              # Project documentation
├── Makefile               # Convenience commands for running the system
├── docker-compose.yml     # Container configuration for all services
├── ai_refactoring/        # Main Python package
│   ├── __init__.py
│   ├── pull_daemon.py     # Git repository synchronization
│   ├── indexer.py         # Zoekt indexing management
│   ├── search_proxy.py    # REST API for code search
│   ├── ai_engine.py       # Refactoring logic
│   ├── pr_creator.py      # Creates branches and PRs
│   └── utils/             # Shared utilities
│       ├── __init__.py
│       ├── config.py      # Configuration management
│       └── logging.py     # Logging setup
├── scripts/
│   ├── install_zoekt.sh   # Script to build Zoekt from source
│   └── run_pipeline.sh    # Script to run the entire pipeline
└── tests/                 # Test suite
    ├── __init__.py
    ├── test_pull_daemon.py
    ├── test_indexer.py
    ├── test_search_proxy.py
    ├── test_ai_engine.py
    └── test_pr_creator.py
``` 