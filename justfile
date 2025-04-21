# AirRelay project justfile
# https://just.systems/

# Set default shell
set shell := ["bash", "-c"]

# Default recipe to show help
default:
    @just --list

# Run the application
run:
    python -m src

# Set up development environment
setup:
    python -m pip install -e ".[dev]"

# Format code using autoflake, black and isort
fmt:
    python -m autoflake --remove-all-unused-imports --remove-unused-variables --recursive --in-place src tests
    python -m black src tests
    python -m isort src tests

# Run mypy type checking
typecheck:
    python -m mypy src

# Run tests
test:
    python -m pytest

# Run a complete check (formatting, type checking, tests)
check: fmt typecheck test

# Build Docker image
docker-build:
    docker build -t air-relay .

# Generate self-signed certificates for TLS if they don't exist
generate-certs:
    #!/bin/bash
    mkdir -p certs
    if [ ! -f "certs/server.key" ] || [ ! -f "certs/server.crt" ]; then
        echo "Generating self-signed certificates..."
        openssl req -x509 -newkey rsa:2048 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj "/CN=localhost"
        echo "Certificates generated successfully."
    fi

# Start services with Docker Compose
docker-up: generate-certs
    docker-compose up -d --build

# Stop Docker Compose services
docker-down:
    docker-compose down

docker-debug: docker-up
    docker compose logs -f

# Initialize MQTT broker configuration
init-mqtt:
    mkdir -p mosquitto/config
    mkdir -p mosquitto/data
    mkdir -p mosquitto/log
    echo "listener 8883" > mosquitto/config/mosquitto.conf
    echo "allow_anonymous true" >> mosquitto/config/mosquitto.conf
    echo "protocol websockets" >> mosquitto/config/mosquitto.conf

# Create a new .env file from example
init-env:
    cp .env.example .env

# Clean up Python cache files
clean:
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name "*.pyd" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    find . -type d -name "*.egg" -exec rm -rf {} +
    find . -type d -name .pytest_cache -exec rm -rf {} +
    find . -type d -name .coverage -exec rm -rf {} +
    find . -type d -name htmlcov -exec rm -rf {} +
    find . -type d -name .mypy_cache -exec rm -rf {} +
    rm -rf build/
    rm -rf dist/

# Build Python package
build:
    python -m build

# Install the package in development mode
dev-install:
    pip install -e . 


# Update dependencies
update-deps:
    rye lock --update-all
    rye sync
