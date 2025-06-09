#!/bin/bash
# Unicorn Wrangler Desktop Simulator - Runner Script

# Activate venv
VENV_PATH="./venv/bin/activate"
if [ ! -f "$VENV_PATH" ]; then
    echo "ERROR: venv not found! Please run ./install.sh first."
    exit 1
fi

source "$VENV_PATH"

# Run main.py with all passed arguments
python3 main.py "$@"
