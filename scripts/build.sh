#!/bin/bash
# PPTMaker Build Script
# Usage: ./scripts/build.sh

set -e

echo "=== PPTMaker Build Script ==="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Paths
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DIST_DIR="$PROJECT_ROOT/dist"

echo -e "${GREEN}[1/4] Cleaning dist directory...${NC}"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

echo -e "${GREEN}[2/4] Building frontend...${NC}"
cd "$FRONTEND_DIR"
npm run build

echo -e "${GREEN}[3/4] Copying backend files...${NC}"
cp -r "$BACKEND_DIR/app" "$DIST_DIR/"
cp "$BACKEND_DIR/pyproject.toml" "$DIST_DIR/"
cp "$BACKEND_DIR/.env.example" "$DIST_DIR/.env" 2>/dev/null || true
cp -r "$FRONTEND_DIR/dist" "$DIST_DIR/frontend"

echo -e "${GREEN}[4/4] Creating deployment package...${NC}"
cd "$DIST_DIR"
echo -e "${YELLOW}Deployment files prepared in: $DIST_DIR${NC}"
echo ""
echo "Contents:"
ls -la "$DIST_DIR"

echo ""
echo -e "${GREEN}Build completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Copy dist/ contents to your server"
echo "  2. Set up environment variables in .env"
echo "  3. Install dependencies: pip install -e ."
echo "  4. Run: gunicorn app.main:app --host 0.0.0.0 --port 8000"
