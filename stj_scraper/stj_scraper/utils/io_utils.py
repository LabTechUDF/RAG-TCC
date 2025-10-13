"""
Input/Output utilities for STJ scraper
"""
import json
from pathlib import Path
import logging


def ensure_directory(path):
    """Ensure directory exists"""
    Path(path).mkdir(parents=True, exist_ok=True)


def save_json(data, file_path):
    """Save data as JSON file"""
    ensure_directory(Path(file_path).parent)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(file_path):
    """Load data from JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.getLogger(__name__).warning(f"Failed to load JSON from {file_path}: {e}")
        return None


def append_jsonl(item, file_path):
    """Append item to JSONL file"""
    ensure_directory(Path(file_path).parent)
    
    with open(file_path, 'a', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False)
        f.write('\n')


def read_jsonl(file_path):
    """Read all items from JSONL file"""
    items = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.getLogger(__name__).warning(f"Failed to read JSONL from {file_path}: {e}")
    
    return items


def sanitize_filename(filename):
    """Sanitize filename for safe filesystem usage"""
    import re
    # Replace invalid characters with underscores
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove multiple consecutive underscores
    filename = re.sub(r'_+', '_', filename)
    # Trim underscores from ends
    filename = filename.strip('_')
    return filename