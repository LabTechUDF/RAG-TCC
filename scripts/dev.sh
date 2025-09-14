#!/bin/bash
# STF Queue-Based Scraper - Development Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_help() {
    echo -e "${BLUE}🔧 STF Queue-Based Scraper - Development Commands${NC}"
    echo "=================================================="
    echo ""
    echo "Usage: ./scripts/dev.sh <command>"
    echo ""
    echo "Available commands:"
    echo -e "  ${GREEN}install${NC}        Install dependencies with Poetry"
    echo -e "  ${GREEN}shell${NC}          Activate Poetry shell"
    echo -e "  ${GREEN}sequential${NC}     Run sequential queue processing"
    echo -e "  ${GREEN}concurrent${NC}     Run concurrent queue processing (3 workers)"
    echo -e "  ${GREEN}status${NC}         Show current queue status"
    echo -e "  ${GREEN}cleanup${NC}        Clean up queue files"
    echo -e "  ${GREEN}format${NC}         Format code with black and isort"
    echo -e "  ${GREEN}clean${NC}          Clean data and cache files"
    echo ""
    echo "Examples:"
    echo "  ./scripts/dev.sh install"
    echo "  ./scripts/dev.sh sequential"
    echo "  ./scripts/dev.sh concurrent"
    echo "  ./scripts/dev.sh status"
    echo "  ./scripts/dev.sh cleanup"
}

case "$1" in
    install)
        echo -e "${BLUE}📦 Installing dependencies with Poetry...${NC}"
        poetry install
        echo -e "${GREEN}✅ Dependencies installed${NC}"
        
        echo -e "${BLUE}🎭 Installing Playwright browsers...${NC}"
        poetry run playwright install chromium
        echo -e "${GREEN}✅ Playwright browsers installed${NC}"
        ;;
    
    shell)
        echo -e "${BLUE}🐚 Activating Poetry shell...${NC}"
        poetry shell
        ;;
    
    sequential)
        echo -e "${BLUE}🎯 Running sequential queue processing...${NC}"
        cd stf_scraper && python manage.py sequential
        ;;
    
    concurrent)
        echo -e "${BLUE}🎯 Running concurrent queue processing...${NC}"
        cd stf_scraper && python manage.py concurrent --workers 3
        ;;
    
    status)
        echo -e "${BLUE}📊 Checking queue status...${NC}"
        cd stf_scraper && python manage.py status
        ;;
    
    cleanup)
        echo -e "${BLUE}🧹 Cleaning up queue files...${NC}"
        cd stf_scraper && python manage.py cleanup
        ;;
    
    format)
        echo -e "${BLUE}🎨 Formatting code...${NC}"
        poetry run black .
        poetry run isort .
        echo -e "${GREEN}✅ Code formatted${NC}"
        ;;
    
    clean)
        echo -e "${BLUE}🧹 Cleaning data and cache files...${NC}"
        find . -name "*.pyc" -delete
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        echo -e "${GREEN}✅ Cleanup completed${NC}"
        ;;
    
    help|--help|-h|"")
        print_help
        ;;
    
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        print_help
        exit 1
        ;;
esac
