#!/bin/bash
# Unicorn Wrangler Desktop Simulator - Install Script (with venv)

set -e

echo "=============================================="
echo " Unicorn Wrangler Desktop Simulator - SETUP"
echo "=============================================="
echo ""

# Check for board_client directory
if [ ! -d "../board_client" ]; then
    echo "ERROR: Cannot find ../board_client directory!"
    echo "Please run this script from the board_client-sim directory,"
    echo "alongside the main board_client project directory."
    exit 1
fi

# Symlink animations
if [ ! -L "animations" ]; then
    if [ -d "animations" ]; then
        echo "WARNING: animations directory exists (not a symlink)"
        read -p "Remove and create symlink? (Y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf animations
        else
            echo "Skipping animations symlink"
        fi
    fi
    if [ ! -e "animations" ]; then
        ln -sf ../board_client/animations animations
        echo "✓ Created symlink to animations"
    fi
else
    echo "✓ Animations symlink already exists"
fi

# Symlink uw
if [ ! -L "uw" ]; then
    if [ -d "uw" ]; then
        echo "WARNING: uw directory exists (not a symlink)"
        read -p "Remove and create symlink? (Y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf uw
        else
            echo "Skipping uw symlink"
        fi
    fi
    if [ ! -e "uw" ]; then
        ln -sf ../board_client/uw uw
        echo "✓ Created symlink to uw"
    fi
else
    echo "✓ uw symlink already exists"
fi

# Create requirements.txt
if [ ! -f "requirements.txt" ]; then
    echo "Creating requirements.txt..."
    cat > requirements.txt << EOF
Pillow>=8.0.0
pygame>=2.0.0
paho-mqtt>=2.1.0
EOF
    echo "✓ Created requirements.txt"
fi

# Create Python venv
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment in ./venv ..."
    python3 -m venv venv
    echo "✓ venv created"
else
    echo "✓ venv already exists"
fi

# Activate venv and install dependencies
echo ""
echo "Activating venv and installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo ""
echo "=========================================="
echo "✓ Setup complete!"
echo "=========================================="
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "Or use the provided run.sh helper script:"
echo "  ./run.sh [--model galactic|stellar|cosmic] [other args]"
echo ""
echo "Usage examples:"
echo "  ./run.sh                # Simulate Cosmic Unicorn (default)"
echo "  ./run.sh --model galactic   # Simulate Galactic Unicorn"
echo "  ./run.sh --model stellar    # Simulate Stellar Unicorn"
echo ""
echo "Enjoy your simulated Unicorn Wrangler!"
echo ""
