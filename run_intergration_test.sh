#!/bin/bash
set -e

echo ":rocket: Starting integration test suite..."

# Detect the correct Python command (prefer python3)
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "❌ No Python interpreter found!"
    exit 1
fi

echo "🐍 Using $($PYTHON --version)"

# Install dependencies
$PYTHON -m pip install --upgrade pip --quiet
$PYTHON -m pip install -r requirements.txt --quiet

echo ":white_check_mark: Running pytest (integration tests)..."
$PYTHON -m pytest -m integration

echo ":dart: Integration tests completed successfully."