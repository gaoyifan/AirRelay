FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.lock pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.lock

# Copy source code
COPY . .

# Create a non-root user
RUN useradd -m airrelay && \
    chown -R airrelay:airrelay /app

USER airrelay

# Run the application
CMD ["python", "-m", "src"] 