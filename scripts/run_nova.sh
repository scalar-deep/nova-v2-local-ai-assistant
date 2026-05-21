#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if [ ! -d "venv08" ]; then
  echo "Missing venv08."
  echo "Run:"
  echo "python3 -m venv venv08"
  echo "source venv08/bin/activate"
  echo "pip install -r requirements-pi.txt"
  exit 1
fi

source venv08/bin/activate
PYTHONUNBUFFERED=1 python orchestrator.py
