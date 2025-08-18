FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Cài Poetry
RUN pip install poetry==1.4.2

# Copy file dependency trước (để tận dụng cache)
COPY pyproject.toml poetry.lock* ./

# Copy source code vào (để Poetry install được cả local package /app/ai)
COPY . .

# Cấu hình Poetry để cài thẳng vào container (không tạo venv) + install deps
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Default command
CMD ["bash"]
