# STF Multi-Threading Guide

## Overview

The STF scraper now uses an **external multi-threading approach** via `manage.py` that splits queries across multiple independent spider processes. This approach is more reliable and performant than the previous internal parallel processing.

## Key Features

### 🚀 External Multi-Threading
- **Multiple Processes**: Each thread runs as a separate subprocess
- **Query Splitting**: Automatically divides queries across threads
- **Result Merging**: Combines results from all threads
- **Fault Tolerance**: Failed threads don't affect successful ones

### 🔧 Simple Usage

```bash
# Run with 5 threads (recommended)
python manage.py run-stf-multithreaded --threads 5

# Run with 3 threads in development mode (limited data)
python manage.py run-stf-multithreaded --threads 3 --dry-run

# Show browser windows for debugging
python manage.py run-stf-multithreaded --threads 3 --show-browser
```

### 📊 Development vs Production Mode

**Development Mode** (`--dry-run`):
- Limited data extraction for testing
- Enhanced logging output
- No permanent data saving
- Faster execution for verification

**Production Mode** (default):
- Full data extraction and saving
- Complete RTF file downloads
- Organized results by article number
- Optimized for maximum data collection

## How It Works

### 1. Query Splitting
The system automatically divides your queries into equal chunks:
```
10 queries with 5 threads:
- Thread 1: Articles 312, 323 (2 queries)
- Thread 2: Articles 345, 179 (2 queries)
- Thread 3: Articles 330, 325 (2 queries)
- Thread 4: Articles 346, 319-A (2 queries)
- Thread 5: Articles 205, 244 (2 queries)
```

### 2. Parallel Execution
Each thread runs independently:
- Separate temporary directories
- Individual query files
- Independent subprocess execution
- No resource conflicts

### 3. Result Merging
After completion, results are automatically merged:
- Data organized by article number
- RTF files properly categorized
- JSONL files combined
- Temporary files cleaned up

## Output Structure

```
data/
├── stf_jurisprudencia/
│   ├── art_312/
│   │   └── art_312_stf_jurisprudencia_20250914_025410.jsonl
│   ├── art_323/
│   │   └── art_323_stf_jurisprudencia_20250914_025410.jsonl
│   └── art_346/
│       └── art_346_stf_jurisprudencia_20250914_025410.jsonl
└── rtf_files/
    ├── 312/
    │   ├── 312_despacho123456_20250914_025216.rtf
    │   └── 312_despacho123457_20250914_025217.rtf
    ├── 323/
    │   └── 323_despacho318695_20250914_025216.rtf
    └── 346/
        └── 346_despacho349777_20250914_025154.rtf
```

## Performance Benefits

| Aspect | Single Thread | Multi-Threading (5 threads) |
|--------|-------------|----------------------------|
| Processing Time | ~5 minutes | ~1 minute |
| CPU Utilization | ~20% | ~80% |
| Reliability | Good | Excellent (fault isolation) |
| Debugging | Simple | Individual thread logs |

## Testing

Use the test script to verify everything works:

```bash
python test_multithreading.py
```

This will:
- ✅ Verify multi-threading command is available
- ✅ Check query data file exists
- ✅ Run a quick test in development mode
- ✅ Validate manage.py configuration

## Troubleshooting

### Common Issues

**1. "No query file found"**
- Run `python manage.py run simple_query_spider` first to generate queries

**2. Memory issues**
- Reduce thread count: `--threads 3`
- Monitor with `htop` during execution

**3. Slow performance**
- Check network connectivity
- Consider reducing thread count for stability
- Use `--dry-run` for faster testing

### Best Practices

1. **Start with Development Mode**: Always test with `--dry-run` first
2. **Optimal Thread Count**: Use 3-5 threads for best performance/stability balance
3. **Monitor Resources**: Keep an eye on memory and CPU usage
4. **Regular Cleanup**: Remove old data files periodically

## Migration from Old Parallel Spider

The old internal parallel spider has been completely removed. The new external multi-threading approach:
- ✅ More reliable (no browser context issues)
- ✅ Better performance (true parallelism)
- ✅ Simpler debugging (separate processes)
- ✅ Fault tolerant (isolated failures)
- ✅ Easier to maintain

Simply replace:
```bash
# Old approach (removed)
python manage.py run stf_jurisprudencia_parallel

# New approach
python manage.py run-stf-multithreaded --threads 5
```

## Files Removed

The following files were removed as part of the cleanup:
- `stf_jurisprudencia_parallel.py` - Old internal parallel spider
- `settings_parallel.py` - Parallel-specific settings
- `monitor_parallel.py` - Parallel monitoring script
- `PARALLEL_SPIDER_GUIDE.md` - Old documentation
- `configs/stf_jurisprudencia_parallel/` - Old config directory

The multi-threading approach maintains full compatibility with existing data formats while providing significant improvements in reliability and performance.