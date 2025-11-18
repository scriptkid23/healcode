FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry==1.4.2

# Copy dependency files first (to leverage cache)
COPY pyproject.toml poetry.lock* ./

# Copy source code (so Poetry can install the local package /app/ai)
COPY . .

# Configure Poetry to install directly into the container (no venv) + install deps
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Default command
CMD ["bash"]