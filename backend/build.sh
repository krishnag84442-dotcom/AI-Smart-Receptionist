#!/bin/bash
# Build script for deployment environments without Rust toolchain
set -e

echo "Installing Python dependencies..."
pip install --upgrade pip

# Force use of pre-compiled wheels to avoid Rust compilation
pip install --only-binary=all -r requirements.txt

echo "Dependencies installed successfully!"
