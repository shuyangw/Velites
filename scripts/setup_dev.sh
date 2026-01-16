#!/bin/bash
# Development environment setup script

set -e

echo "Setting up Velites development environment..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install pre-commit hooks
echo "Setting up pre-commit hooks..."
pip install pre-commit
pre-commit install

# Create necessary directories
mkdir -p output/signals logs

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env with your API keys"
fi

echo ""
echo "Setup complete! Activate the environment with:"
echo "  source venv/bin/activate"
echo ""
echo "Run the pipeline with:"
echo "  python -m velites.main"
