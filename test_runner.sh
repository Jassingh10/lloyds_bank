#!/bin/bash
set -e

echo "🚀 Starting test suite..."

# Install dependencies for the correct Python version
python3 -m pip install -r requirements.txt --quiet

echo "✅ Running pytest with coverage..."
python3 -m pytest

echo "🎯 All tests completed successfully."