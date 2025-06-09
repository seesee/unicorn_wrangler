#!/bin/bash
# Setup script for Unicorn Wrangler Pi (Unicorn HAT HD)

echo "================================================="
echo "  UnicornHD for Pi - Compatibility Setup Script"
echo "================================================="
echo ""
echo "WARNING:"
echo "This will install the Pimoroni Unicorn HAT HD compatibility layer"
echo "into the current directory."
echo ""
echo "You do NOT need this if you are installing on a:"
echo "  • Stellar Unicorn"
echo "  • Galactic Unicorn" 
echo "  • Cosmic Unicorn"
echo ""
echo "This compatibility layer is ONLY for the Unicorn HAT HD"
echo "(16x16 RGB LED matrix that plugs into Raspberry Pi GPIO)."
echo ""
read -p "Are you sure you'd like to proceed? (Y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Installation cancelled."
    echo ""
    echo "If you have a Stellar, Galactic, or Cosmic Unicorn,"
    echo "please use the MicroPython version in the board_client/ directory."
    exit 0
fi

echo ""
echo "Proceeding with Unicorn HAT HD setup..."
echo ""

# Check if we're in the right directory structure
if [ ! -d "../board_client" ]; then
    echo "ERROR: Cannot find ../board_client directory!"
    echo "Please make sure you're running this script from the board_client-uhd directory,"
    echo "alongside the main board_client project directory."
    echo ""
    echo "Expected structure:"
    echo "  unicorn_wrangler/"
    echo "  ├── board_client/          # MicroPython+Pico version"
    echo "  ├── board_client-uhd/      # Pi version (you are here)"
    echo "  └── server/                # Docker streaming service/utils for unicorns"
    exit 1
fi

# Create symlinks to original animations and uw modules
echo "Setting up symlinks to shared code..."

if [ ! -L "animations" ]; then
    if [ -d "animations" ]; then
        echo "WARNING: animations directory already exists (not a symlink)"
        read -p "Remove it and create symlink? (Y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf animations
        else
            echo "Skipping animations symlink creation"
        fi
    fi
    
    if [ ! -e "animations" ]; then
        ln -sf ../board_client/animations animations
        echo "✓ Created symlink to animations"
    fi
else
    echo "✓ Animations symlink already exists"
fi

# Create uw directory and selective symlinks
if [ -L "uw" ]; then
    rm uw
    echo "Removed old uw symlink"
fi
    
# Symlink files that don't import hardware
ln -sf ../../board_client/uw/logger.py uw/logger.py
ln -sf ../../board_client/uw/config.py uw/config.py
ln -sf ../../board_client/uw/time_service.py uw/time_service.py
ln -sf ../../board_client/uw/transitions.py uw/transitions.py
ln -sf ../../board_client/uw/animation_service.py uw/animation_service.py

# Create __init__.py for uw package if it doesn't exist
if [ ! -f "uw/__init__.py" ]; then
    touch uw/__init__.py
fi

echo "✓ UW compatibility layer ready"

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "WARNING: requirements.txt not found!"
    echo "Creating basic requirements.txt..."
    cat > requirements.txt << EOF
paho-mqtt>=1.6.0
Pillow>=8.0.0
unicornhathd>=1.0.0
numpy>=1.21.0
psutil>=5.8.0
EOF
    echo "✓ Created requirements.txt"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "✓ Dependencies installed successfully"
    else
        echo "⚠ Some dependencies may have failed to install"
        echo "You may need to install them manually or check your Python setup"
    fi
else
    echo "ERROR: pip3 not found!"
    echo "Please install pip3 first: sudo apt install python3-pip"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Setup complete!"
echo "=========================================="
echo ""
echo "Your Unicorn HAT HD is now ready to run Unicorn Wrangler animations!"
echo "NOTE: It will pretend to be a stellar unicorn, so configure appropriately."
echo ""
echo "Usage:"
echo "  python3 main.py                    # Run with default config"
echo "  python3 main.py --config myconf    # Run with custom config"
echo ""
echo "Make sure your config.json is set up with your MQTT broker details"
echo "if you want to use remote control features."
echo ""
