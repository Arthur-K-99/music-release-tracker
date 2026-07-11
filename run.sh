#!/bin/bash
# SoundRadar Launcher Script

# Get directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

echo "========================================="
echo "        SOUNDRADAR LOCAL SERVER          "
echo "========================================="

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies only when the requirements file changes
if [ ! -f ".venv/.requirements-installed" ] || [ "requirements.txt" -nt ".venv/.requirements-installed" ]; then
    echo "Installing dependencies..."
    python3 -m pip install -q -r requirements.txt
    touch .venv/.requirements-installed
else
    echo "Dependencies are current."
fi

# Initialize database
echo "Verifying database..."
python3 db.py

# Launch Flask app
echo ""
echo "Starting server..."
echo "Open your web browser and go to:"
echo "👉 http://127.0.0.1:${SOUNDRADAR_PORT:-5001}"
echo ""
echo "Press Ctrl+C to terminate the server."
echo "========================================="

python3 app.py
