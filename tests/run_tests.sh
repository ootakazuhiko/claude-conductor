#!/bin/bash
cd $(dirname $0)/..
source venv/bin/activate

# Unit tests
echo "Running unit tests..."
python -m pytest tests/ -v --tb=short

# Coverage report
echo "Generating coverage report..."
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term