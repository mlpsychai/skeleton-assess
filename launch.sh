#!/usr/bin/env bash
# Launch the skeleton_assess front end
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Start the Flask server
echo "Starting skeleton_assess at http://localhost:5000"
python server.py
