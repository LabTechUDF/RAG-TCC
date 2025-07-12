"""
Helper utilities for the Brazilian legal content scraper.
Includes logging setup, file operations, and data validation.
"""

import json
import csv
import logging
import os
import aiofiles
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path


def setup_logging(log_level: str = 'INFO') -> None:
    """
    Set up logging configuration for the scraper.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / 'scraping.log'),
            logging.StreamHandler()
        ]
    )
    
    # Set specific loggers
    logging.getLogger('playwright').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def load_theme_config(theme_name: str) -> Dict[str, Any]:
    """
    Load configuration for a specific theme.
    
    Args:
        theme_name: Name of the theme directory
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    config_path = Path(f'themes/{theme_name}/config.json')
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
        
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in config file {config_path}: {e}")


async def save_data_async(data: List[Dict[str, Any]], theme_name: str, 
                         filename: str, format_type: str = 'json') -> None:
    """
    Save scraped data asynchronously.
    
    Args:
        data: List of dictionaries containing scraped data
        theme_name: Name of the theme
        filename: Output filename (without extension)
        format_type: Output format ('json' or 'csv')
    """
    # Create data directory if it doesn't exist
    data_dir = Path(f'data/{theme_name}')
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Add timestamp to filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename_with_timestamp = f"{filename}_{timestamp}"
    
    if format_type.lower() == 'json':
        file_path = data_dir / f"{filename_with_timestamp}.json"
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
    
    elif format_type.lower() == 'csv':
        file_path = data_dir / f"{filename_with_timestamp}.csv"
        if data:
            fieldnames = data[0].keys()
            async with aiofiles.open(file_path, 'w', encoding='utf-8', newline='') as f:
                # Write header
                await f.write(','.join(fieldnames) + '\n')
                
                # Write data rows
                for item in data:
                    row = []
                    for field in fieldnames:
                        value = item.get(field, '')
                        # Handle nested data
                        if isinstance(value, (list, dict)):
                            value = json.dumps(value, ensure_ascii=False)
                        # Escape quotes and commas
                        value = str(value).replace('"', '""')
                        if ',' in value or '"' in value or '\n' in value:
                            value = f'"{value}"'
                        row.append(value)
                    await f.write(','.join(row) + '\n')
    
    logging.info(f"Data saved to {file_path}")


def validate_scraped_data(data: List[Dict[str, Any]], 
                         required_fields: List[str] = None) -> Dict[str, Any]:
    """
    Validate scraped data and return quality metrics.
    
    Args:
        data: List of scraped data dictionaries
        required_fields: List of required field names
        
    Returns:
        Dictionary with validation results and metrics
    """
    if not data:
        return {
            'is_valid': False,
            'total_items': 0,
            'empty_items': 0,
            'missing_fields': {},
            'quality_score': 0.0
        }
    
    required_fields = required_fields or ['title', 'date', 'link']
    
    metrics = {
        'total_items': len(data),
        'empty_items': 0,
        'missing_fields': {field: 0 for field in required_fields},
        'field_completeness': {},
        'quality_score': 0.0
    }
    
    for item in data:
        # Check if item is completely empty
        if not any(value for value in item.values() if value):
            metrics['empty_items'] += 1
            continue
            
        # Check required fields
        for field in required_fields:
            if not item.get(field):
                metrics['missing_fields'][field] += 1
    
    # Calculate field completeness
    for field in required_fields:
        complete_count = metrics['total_items'] - metrics['missing_fields'][field]
        metrics['field_completeness'][field] = complete_count / metrics['total_items'] if metrics['total_items'] > 0 else 0
    
    # Calculate overall quality score
    if metrics['total_items'] > 0:
        avg_completeness = sum(metrics['field_completeness'].values()) / len(required_fields)
        empty_ratio = metrics['empty_items'] / metrics['total_items']
        metrics['quality_score'] = avg_completeness * (1 - empty_ratio)
    
    metrics['is_valid'] = metrics['quality_score'] > 0.5  # 50% threshold
    
    return metrics


def create_scraping_report(theme_name: str, start_time: datetime, 
                          end_time: datetime, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a comprehensive scraping report.
    
    Args:
        theme_name: Name of the theme that was scraped
        start_time: When scraping started
        end_time: When scraping ended
        metrics: Validation metrics from validate_scraped_data
        
    Returns:
        Dictionary with complete scraping report
    """
    duration = end_time - start_time
    
    report = {
        'theme': theme_name,
        'scraping_session': {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'duration_formatted': str(duration)
        },
        'data_quality': metrics,
        'status': 'SUCCESS' if metrics['is_valid'] else 'FAILED',
        'recommendations': []
    }
    
    # Add recommendations based on metrics
    if metrics['quality_score'] < 0.3:
        report['recommendations'].append('Data quality is very low. Check selectors and parsing logic.')
    elif metrics['quality_score'] < 0.7:
        report['recommendations'].append('Data quality could be improved. Review missing fields.')
    
    if metrics['empty_items'] > metrics['total_items'] * 0.1:
        report['recommendations'].append('High number of empty items. Check item selectors.')
    
    for field, missing_count in metrics['missing_fields'].items():
        if missing_count > metrics['total_items'] * 0.2:
            report['recommendations'].append(f'Field "{field}" is missing in many items. Review selector.')
    
    return report


async def save_scraping_report(report: Dict[str, Any], theme_name: str) -> None:
    """
    Save scraping report to file.
    
    Args:
        report: Scraping report dictionary
        theme_name: Name of the theme
    """
    # Create reports directory
    reports_dir = Path(f'data/{theme_name}/reports')
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = reports_dir / f'scraping_report_{timestamp}.json'
    
    async with aiofiles.open(report_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(report, ensure_ascii=False, indent=2))
    
    logging.info(f"Scraping report saved to {report_path}")


def normalize_url(url: str, base_url: str = None) -> str:
    """
    Normalize URL to ensure it's absolute.
    
    Args:
        url: URL to normalize
        base_url: Base URL for relative URLs
        
    Returns:
        Normalized absolute URL
    """
    if not url:
        return ""
        
    url = url.strip()
    
    # Already absolute URL
    if url.startswith(('http://', 'https://')):
        return url
        
    # Protocol-relative URL
    if url.startswith('//'):
        return f'https:{url}'
        
    # Relative URL
    if base_url:
        if url.startswith('/'):
            # Root-relative
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        else:
            # Relative to current path
            from urllib.parse import urljoin
            return urljoin(base_url, url)
    
    return url


def clean_filename(filename: str) -> str:
    """
    Clean filename to be filesystem-safe.
    
    Args:
        filename: Original filename
        
    Returns:
        Cleaned filename safe for filesystem
    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename.strip()


def get_theme_list() -> List[str]:
    """
    Get list of available themes.
    
    Returns:
        List of theme names
    """
    themes_dir = Path('themes')
    if not themes_dir.exists():
        return []
        
    themes = []
    for item in themes_dir.iterdir():
        if item.is_dir() and (item / 'config.json').exists():
            themes.append(item.name)
    
    return sorted(themes)


def print_scraping_summary(report: Dict[str, Any]) -> None:
    """
    Print a formatted summary of the scraping session.
    
    Args:
        report: Scraping report dictionary
    """
    print("\n" + "="*60)
    print(f"SCRAPING SUMMARY - {report['theme'].upper()}")
    print("="*60)
    print(f"Status: {report['status']}")
    print(f"Duration: {report['scraping_session']['duration_formatted']}")
    print(f"Items Scraped: {report['data_quality']['total_items']}")
    print(f"Quality Score: {report['data_quality']['quality_score']:.2%}")
    
    if report['data_quality']['missing_fields']:
        print("\nMissing Fields:")
        for field, count in report['data_quality']['missing_fields'].items():
            percentage = (count / report['data_quality']['total_items']) * 100
            print(f"  {field}: {count} ({percentage:.1f}%)")
    
    if report['recommendations']:
        print("\nRecommendations:")
        for rec in report['recommendations']:
            print(f"  • {rec}")
    
    print("="*60) 