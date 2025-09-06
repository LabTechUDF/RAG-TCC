#!/bin/bash
# Brazilian Legal Scraper - Development Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Add Poetry to PATH
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

print_help() {
    echo -e "${BLUE}�️ STF Legal Scraper - Development Commands${NC}"
    echo "=================================================="
    echo ""
    echo "Usage: ./scripts/dev.sh <command>"
    echo ""
    echo "Available commands:"
    echo -e "  ${GREEN}install${NC}     Install dependencies with Poetry"
    echo -e "  ${GREEN}shell${NC}       Activate Poetry shell"
    echo -e "  ${GREEN}list${NC}        List available STF scrapers"
    echo -e "  ${GREEN}test${NC}        Run dry-run test for STF scrapers"
    echo -e "  ${GREEN}dev${NC}         Run scraper in development mode (5 items limit)"
    echo -e "  ${GREEN}prod${NC}        Run scraper in production mode (no limit)"
    echo -e "  ${GREEN}lint${NC}        Run code linting (black, isort, flake8)"
    echo -e "  ${GREEN}format${NC}      Format code with black and isort"
    echo -e "  ${GREEN}run${NC}         Run specific scraper (usage: ./dev.sh run <spider> [args])"
    echo -e "  ${GREEN}stats${NC}       Show scraping statistics"
    echo -e "  ${GREEN}clean${NC}       Clean data and cache files"
    echo ""
    echo "Examples:"
    echo "  ./scripts/dev.sh install"
    echo "  ./scripts/dev.sh dev stf_clipboard"
    echo "  ./scripts/dev.sh prod stf_clipboard"
    echo "  ./scripts/dev.sh run stf_legal"
    echo "  ./scripts/dev.sh run stf_legal -a query=\"homicídio doloso\""
    echo "  ./scripts/dev.sh test"
    echo "  ./scripts/dev.sh lint"
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
    
    list)
        echo -e "${BLUE}📚 Available STF scrapers:${NC}"
        cd stf_scraper && poetry run python manage.py list
        ;;
    
    test)
        echo -e "${BLUE}🧪 Running dry-run tests for STF scrapers...${NC}"
        cd stf_scraper && poetry run python manage.py run stf_legal --dry-run
        ;;
    
    dev)
        if [ -z "$2" ]; then
            echo -e "${RED}❌ Error: Please specify a spider name${NC}"
            echo "Usage: ./dev.sh dev <spider>"
            echo "Available spiders: stf_clipboard, stf_legal"
            exit 1
        fi
        
        echo -e "${BLUE}🚧 Running $2 spider in DEVELOPMENT mode (5 items limit)...${NC}"
        cd stf_scraper && poetry run scrapy crawl "$2" -a dev_mode=true
        echo -e "${GREEN}✅ Development run completed - check data/stf_clipboard/ for results${NC}"
        ;;
    
    prod)
        if [ -z "$2" ]; then
            echo -e "${RED}❌ Error: Please specify a spider name${NC}"
            echo "Usage: ./dev.sh prod <spider>"
            echo "Available spiders: stf_clipboard, stf_legal"
            exit 1
        fi
        
        echo -e "${BLUE}🚀 Running $2 spider in PRODUCTION mode (no limit)...${NC}"
        cd stf_scraper && poetry run scrapy crawl "$2"
        echo -e "${GREEN}✅ Production run completed - check data/ for results${NC}"
        ;;
    
    lint)
        echo -e "${BLUE}🔍 Running code linting...${NC}"
        poetry run flake8 stf_scraper/
        echo -e "${GREEN}✅ Linting completed${NC}"
        ;;
    
    format)
        echo -e "${BLUE}🎨 Formatting code...${NC}"
        poetry run black stf_scraper/
        poetry run isort stf_scraper/
        echo -e "${GREEN}✅ Code formatted${NC}"
        ;;
    
    run)
        if [ -z "$2" ]; then
            echo -e "${RED}❌ Error: Please specify a spider name${NC}"
            echo "Usage: ./dev.sh run <spider> [args]"
            echo "Available spiders: stf_clipboard, stf_legal"
            echo ""
            echo "Tip: Use './dev.sh dev <spider>' for development mode (5 items limit)"
            echo "     Use './dev.sh prod <spider>' for production mode (no limit)"
            exit 1
        fi
        
        echo -e "${BLUE}🚀 Running $2 spider with custom arguments...${NC}"
        cd stf_scraper && poetry run scrapy crawl "${@:2}"
        ;;
    
    stats)
        echo -e "${BLUE}📊 STF scraping statistics:${NC}"
        cd stf_scraper && poetry run python manage.py stats
        ;;
    
    clean)
        echo -e "${BLUE}🧹 Cleaning data and cache...${NC}"
        cd stf_scraper && poetry run python manage.py clean
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