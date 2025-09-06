#!/bin/bash
"""
Script to run the STF spider in different modes
Usage: 
  ./run_spider_with_limit.sh dev    # Development mode (5 items limit)
  ./run_spider_with_limit.sh prod   # Production mode (no limit)
  ./run_spider_with_limit.sh [number]  # Custom limit using Scrapy setting
"""

MODE=${1:-prod}

echo "🕷️  STF Spider Runner"
echo "================================================="

cd /home/workstation/git/RAG-TCC/stf_scraper

case $MODE in
    "dev"|"development")
        echo "🚧 Running in DEVELOPMENT mode (5 items limit)..."
        scrapy crawl stf_jurisprudencia \
            -a dev_mode=true \
            -s LOG_LEVEL=INFO \
            -L INFO
        ;;
    "prod"|"production")
        echo "🚀 Running in PRODUCTION mode (no limit)..."
        scrapy crawl stf_jurisprudencia \
            -s LOG_LEVEL=INFO \
            -L INFO
        ;;
    [0-9]*)
        echo "⚙️  Running with custom limit of $MODE items..."
        scrapy crawl stf_jurisprudencia \
            -s CLOSESPIDER_ITEMCOUNT=$MODE \
            -s LOG_LEVEL=INFO \
            -L INFO
        ;;
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Usage:"
        echo "  $0 dev     # Development mode (5 items)"
        echo "  $0 prod    # Production mode (no limit)"
        echo "  $0 [num]   # Custom limit"
        exit 1
        ;;
esac

echo "================================================="
echo "✅ Spider run completed!"
echo "📁 Check the data/stf_jurisprudencia/ directory for results"
