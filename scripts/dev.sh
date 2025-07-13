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
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

print_help() {
    echo -e "${BLUE}🇧🇷 Brazilian Legal Scraper - Development Commands${NC}"
    echo "=================================================="
    echo ""
    echo "Usage: ./scripts/dev.sh <command>"
    echo ""
    echo "Available commands:"
    echo -e "  ${GREEN}install${NC}     Install dependencies with Poetry"
    echo -e "  ${GREEN}shell${NC}       Activate Poetry shell"
    echo -e "  ${GREEN}list${NC}        List available scrapers"
    echo -e "  ${GREEN}test${NC}        Run dry-run test for all scrapers"
    echo -e "  ${GREEN}lint${NC}        Run code linting (black, isort, flake8)"
    echo -e "  ${GREEN}format${NC}      Format code with black and isort"
    echo -e "  ${GREEN}run${NC}         Run specific scraper (usage: ./dev.sh run <spider> [args])"
    echo -e "  ${GREEN}stats${NC}       Show scraping statistics"
    echo -e "  ${GREEN}clean${NC}       Clean data and cache files"
    echo ""
    echo "Examples:"
    echo "  ./scripts/dev.sh install"
    echo "  ./scripts/dev.sh run jurisprudencia --dry-run"
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
        echo -e "${BLUE}📚 Available scrapers:${NC}"
        cd legal_scraper && poetry run python manage.py list
        ;;
    
    test)
        echo -e "${BLUE}🧪 Running dry-run tests for all scrapers...${NC}"
        cd legal_scraper && poetry run python manage.py run-all --dry-run --max-pages 1
        ;;
    
    lint)
        echo -e "${BLUE}🔍 Running code linting...${NC}"
        poetry run flake8 legal_scraper/
        echo -e "${GREEN}✅ Linting completed${NC}"
        ;;
    
    format)
        echo -e "${BLUE}🎨 Formatting code...${NC}"
        poetry run black legal_scraper/
        poetry run isort legal_scraper/
        echo -e "${GREEN}✅ Code formatted${NC}"
        ;;
    
    run)
        if [ -z "$2" ]; then
            echo -e "${RED}❌ Error: Please specify a spider name${NC}"
            echo "Usage: ./dev.sh run <spider> [args]"
            echo "Available spiders: jurisprudencia, sumulas_stf, normativas_stj, direito_penal, tribunais_estaduais"
            exit 1
        fi
        
        echo -e "${BLUE}🚀 Running $2 spider...${NC}"
        cd legal_scraper && poetry run python manage.py run "${@:2}"
        ;;
    
    stats)
        echo -e "${BLUE}📊 Scraping statistics:${NC}"
        cd legal_scraper && poetry run python manage.py stats
        ;;
    
    clean)
        echo -e "${BLUE}🧹 Cleaning data and cache...${NC}"
        cd legal_scraper && poetry run python manage.py clean
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