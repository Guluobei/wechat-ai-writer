#!/bin/bash
# Setup script for guizang-social-card-skill dependency
# Run this after cloning the wechat-ai-writer repository

set -e

SKILL_DIR="/workspace/skills/guizang-social-card-skill"
REPO_DEPS_DIR="$(dirname "$0")/../deps/guizang-social-card-skill"

echo "Installing guizang-social-card-skill..."

# Create target directory
mkdir -p "$SKILL_DIR"

# Copy skill files to runtime location
cp -r "$REPO_DEPS_DIR"/* "$SKILL_DIR/"

# Install Node dependencies
cd "$SKILL_DIR"
npm install

# Install Playwright browsers
npx playwright install chromium

echo "guizang-social-card-skill installed successfully!"
echo "Verify: node -e \"require('playwright')\" && echo OK"
