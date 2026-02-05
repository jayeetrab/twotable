#!/bin/bash
set -e

echo "=========================================="
echo "Installing Python dependencies..."
echo "=========================================="

# Upgrade pip/setuptools/wheel first
pip install --upgrade pip setuptools wheel

# Install requirements with no-cache (cleaner)
pip install --no-cache-dir -r requirements.txt

echo "=========================================="
echo "Build completed successfully!"
echo "=========================================="
