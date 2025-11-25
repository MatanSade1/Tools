#!/bin/bash

# Script to install Homebrew and Node.js on macOS

set -e

echo "========================================="
echo "Installing Homebrew and Node.js"
echo "========================================="
echo ""

# Check if Homebrew is already installed
if command -v brew &> /dev/null; then
    echo "✓ Homebrew is already installed"
else
    echo "Installing Homebrew..."
    echo "This will require your administrator password."
    echo ""
    
    # Install Homebrew
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [ -f "/opt/homebrew/bin/brew" ]; then
        echo ""
        echo "Adding Homebrew to PATH for Apple Silicon Mac..."
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/opt/homebrew/bin/brew shellenv)"
    # Add Homebrew to PATH for Intel Macs
    elif [ -f "/usr/local/bin/brew" ]; then
        echo ""
        echo "Adding Homebrew to PATH for Intel Mac..."
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    echo "✓ Homebrew installed successfully"
fi

# Verify Homebrew is accessible
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew is not accessible. Please restart your terminal or run:"
    if [ -f "/opt/homebrew/bin/brew" ]; then
        echo '  eval "$(/opt/homebrew/bin/brew shellenv)"'
    else
        echo '  eval "$(/usr/local/bin/brew shellenv)"'
    fi
    exit 1
fi

echo ""
echo "Updating Homebrew..."
brew update

echo ""
echo "Installing Node.js..."
brew install node

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Node.js version:"
node --version
echo ""
echo "npm version:"
npm --version
echo ""
echo "If 'brew' command is not found in new terminal windows,"
echo "restart your terminal or run:"
if [ -f "/opt/homebrew/bin/brew" ]; then
    echo '  eval "$(/opt/homebrew/bin/brew shellenv)"'
else
    echo '  eval "$(/usr/local/bin/brew shellenv)"'
fi

