# 🏛️ STF Queue-Based Legal Content Scraper

A thread-safe web scraper for Brazilian Supreme Court (STF) legal decisions using **Scrapy**, **Playwright**, and **queue-based architecture**.

> **Status**: Production-ready STF scraper with concurrent queue processing for criminal law decisions.

## 🏗️ Clean Architecture

### **Queue-Based Processing**
- **STFQueueManager**: Thread-safe queue management with fcntl file locking
- **Sequential Processing**: Safe, one-at-a-time query processing
- **Concurrent Processing**: Multi-worker concurrent processing with race condition protection

### **Core Components**
- `stf_jurisprudencia` - STF legal decisions spider (production-ready)
- `simple_query_spider` - Query URL generator (creates query_links.json)
- **Thread-safe pipelines**: Article-based JSON writer, validation, deduplication

## 🚀 How to Run

### **Requirements**
- Python 3.12+
- Poetry

### **Setup**
```bash
# Install dependencies  
poetry install

# Install browser
poetry run playwright install chromium
```

### **Queue-Based Commands**
```bash
# Go to scraper directory
cd stf_scraper

# Sequential processing (safe, single-threaded)
python manage.py sequential

# Concurrent processing (3 workers by default)
python manage.py concurrent --workers 3

# Show current queue status  
python manage.py status

# Clean up queue files
python manage.py cleanup

# Show browser for debugging
python manage.py sequential --show-browser
```

### **Development Helper**
```bash
# Use development script
./scripts/dev.sh sequential
./scripts/dev.sh concurrent  
./scripts/dev.sh status
```

### **Output**D
Data organized by article number in `stf_scraper/data/stf_jurisprudencia/` with:
- **JSONL files**: Legal decisions by article (art_312/, art_323/, etc.)  
- **RTF files**: Original STF documents organized by article number
- **Thread-safe processing**: No duplicate queries or race conditions

## 📁 Clean Structure
```
stf_scraper/
├── manage.py                    # Clean queue-based CLI
├── stf_queue_manager.py        # Thread-safe queue processing
├── stf_scraper/
│   ├── spiders/
│   │   ├── stf_jurisprudencia.py    # Main STF spider
│   │   └── simple_query_spider.py   # Query generator
│   ├── items.py                # Data structure definitions
│   ├── pipelines.py           # Article-based processing
│   ├── middlewares.py         # Simplified middlewares  
│   └── settings.py            # Playwright configuration
├── data/                      # Organized scraped data
└── configs/
    └── queries.txt           # Source queries for processing
```

## 🎯 Key Features

✅ **Thread-Safe**: fcntl file locking prevents race conditions  
✅ **Queue-Based**: Clean separation between queue management and spider execution  
✅ **Concurrent**: Multi-worker processing with configurable worker count  
✅ **Production-Ready**: No development modes, clean production focus  
✅ **Organized Output**: Data organized by article number automatically  
✅ **Resume Support**: Can resume interrupted processing from queue state

## 📦 Archived data

The scraped data (TJDFT, Planalto legislation, STF, STJ monocratic decisions, juridico exports) and the FAISS index (`index.faiss` + `metadata.parquet`) are archived as one release, about 3.7 GB in two parts, in the private repository [danrleypereira/rag-tcc-archive](https://github.com/danrleypereira/rag-tcc-archive/releases/tag/all-2026-10-15). Restore: `sha256sum -c SHA256SUMS`, then `cat rag-tcc-all.tar.zst.part-* | zstd -dc | tar -x -C <repo root>` (see `RESTORE.md` in the release; the `juridico/` folder goes to `~/rag-tcc-exports/`).

Not archived, because it can be re-created: the STJ open-data SQLite (26 GB, download it again from STJ), the `.arrow` metadata cache (rebuilt on first start) and the Python/Node environments.
