#!/bin/bash
# SoundRadar Launcher Script

# Get directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "========================================="
echo "        SOUNDRADAR LOCAL SERVER          "
echo "========================================="

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install or update dependencies
echo "Verifying dependencies..."
pip install -q -r requirements.txt

# Initialize database
echo "Verifying database..."
python3 db.py

# Launch Flask app
echo ""
echo "Starting server..."
echo "Open your web browser and go to:"
echo "👉 http://127.0.0.1:5000"
echo ""
echo "Press Ctrl+C to terminate the server."
echo "========================================="

python3 app.py
