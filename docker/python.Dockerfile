FROM python:3.9-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.4.2

# Copy only dependency definition files first for better layer caching
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not use a virtual environment
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy the source code
COPY . .

# Set the default command to nothing but use CMD in docker-compose
CMD ["bash"] 