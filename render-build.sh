#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Fix for Render: Uninstall opencv-python (GUI) if installed by ultralytics, 
# and ensure opencv-python-headless is present.
if pip show opencv-python > /dev/null 2>&1; then
    echo "Removing opencv-python to avoid libGL errors..."
    pip uninstall -y opencv-python
fi

# Ensure headless is installed
pip install opencv-python-headless
