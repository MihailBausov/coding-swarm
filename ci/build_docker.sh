#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${1:-coding-swarm:latest}"
echo "🐳 Building Docker image: ${IMAGE_NAME}..."

docker build -t "$IMAGE_NAME" .
echo "✅ Build complete!"
