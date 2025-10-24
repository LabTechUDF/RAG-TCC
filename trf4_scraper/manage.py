#!/usr/bin/env python3
"""
Minimal manager to run TRF4 scraper similarly to STF's manager.

Usage:
  python3 trf4_scraper/manage.py sequential [--show-browser] [--query QUERY]

This script simply spawns a scrapy runspider call for the TRF4 spider.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_sequential(show_browser: bool, query: str):
    project_root = Path(__file__).parent.parent
    print("🎯 Running TRF4 Jurisprudencia (sequential)")
    if not query:
        print("❗ No query provided. Use --query to pass a search text.")
        return 1

    cmd = [
        'scrapy', 'runspider', 'trf4_scraper/spiders/trf4_jurisprudencia.py',
        '-a', f'query={query}',
        '-L', 'DEBUG'
    ]

    if show_browser:
        cmd.extend(['-s', 'PLAYWRIGHT_LAUNCH_OPTIONS={"headless": false}'])

    print(f"📋 Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project_root))
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='TRF4 scraper manager')
    subparsers = parser.add_subparsers(dest='command')

    seq = subparsers.add_parser('sequential')
    seq.add_argument('--show-browser', action='store_true')
    seq.add_argument('--query', type=str, default='')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == 'sequential':
        rc = run_sequential(show_browser=args.show_browser, query=args.query)
        sys.exit(rc)


if __name__ == '__main__':
    main()
