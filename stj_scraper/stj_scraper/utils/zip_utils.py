"""
ZIP file utilities for STJ dataset processing
"""
import zipfile
import json
import tempfile
import shutil
from pathlib import Path
import logging
import io
from typing import List, Dict, Tuple, Optional


class ZipProcessor:
    """Handle ZIP file processing for STJ dataset"""
    
    def __init__(self, temp_dir=None):
        self.logger = logging.getLogger(__name__)
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
    def extract_json_manifests(self, zip_path: str) -> List[Dict]:
        """Extract all JSON manifest files from ZIP"""
        manifests = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if file_info.filename.lower().endswith('.json'):
                        self.logger.debug(f"Found JSON manifest: {file_info.filename}")
                        
                        with zip_ref.open(file_info) as json_file:
                            # Handle large JSON files with streaming if needed
                            if file_info.file_size > 50 * 1024 * 1024:  # 50MB
                                manifest = self._stream_json(json_file)
                            else:
                                manifest = json.load(json_file)
                            
                            manifests.append({
                                'data': manifest,
                                'filename': file_info.filename,
                                'size': file_info.file_size
                            })
                            
        except zipfile.BadZipFile as e:
            self.logger.error(f"Bad ZIP file {zip_path}: {e}")
        except Exception as e:
            self.logger.error(f"Error extracting manifests from {zip_path}: {e}")
            
        return manifests
    
    def find_txt_file(self, zip_path: str, seq_documento: str) -> Optional[Tuple[str, str]]:
        """Find TXT file in ZIP by seqDocumento"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Try exact match first
                for file_info in zip_ref.filelist:
                    if file_info.filename.lower().endswith('.txt'):
                        filename_base = Path(file_info.filename).stem
                        
                        # Try exact match
                        if filename_base == seq_documento:
                            with zip_ref.open(file_info) as txt_file:
                                content = txt_file.read().decode('utf-8', errors='ignore')
                                return content, file_info.filename
                        
                        # Try with zero padding (common in datasets)
                        if filename_base.lstrip('0') == seq_documento:
                            with zip_ref.open(file_info) as txt_file:
                                content = txt_file.read().decode('utf-8', errors='ignore')
                                return content, file_info.filename
                
        except zipfile.BadZipFile as e:
            self.logger.error(f"Bad ZIP file {zip_path}: {e}")
        except Exception as e:
            self.logger.error(f"Error finding TXT file for {seq_documento} in {zip_path}: {e}")
            
        return None
    
    def extract_to_temp(self, zip_path: str, resource_id: str) -> Optional[str]:
        """Extract ZIP to temporary directory"""
        temp_extract_dir = Path(self.temp_dir) / f"stj_extract_{resource_id}"
        
        try:
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            
            temp_extract_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
                
            self.logger.info(f"Extracted ZIP to: {temp_extract_dir}")
            return str(temp_extract_dir)
            
        except Exception as e:
            self.logger.error(f"Error extracting ZIP {zip_path}: {e}")
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            return None
    
    def cleanup_temp(self, temp_path: str):
        """Clean up temporary extraction directory"""
        try:
            if Path(temp_path).exists():
                shutil.rmtree(temp_path)
                self.logger.debug(f"Cleaned up temp directory: {temp_path}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temp directory {temp_path}: {e}")
    
    def _stream_json(self, json_file):
        """Stream large JSON files using ijson"""
        try:
            import ijson
            
            # For large JSON files, try to parse as array
            items = []
            parser = ijson.items(json_file, 'item')
            for item in parser:
                items.append(item)
            return items
            
        except ImportError:
            self.logger.warning("ijson not available, falling back to standard JSON parsing")
            return json.load(json_file)
        except Exception as e:
            self.logger.warning(f"Streaming JSON failed, falling back to standard parsing: {e}")
            json_file.seek(0)  # Reset file pointer
            return json.load(json_file)
    
    def list_zip_contents(self, zip_path: str) -> List[Dict]:
        """List contents of ZIP file for debugging"""
        contents = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    contents.append({
                        'filename': file_info.filename,
                        'size': file_info.file_size,
                        'compressed_size': file_info.compress_size,
                        'type': 'JSON' if file_info.filename.lower().endswith('.json') else
                               'TXT' if file_info.filename.lower().endswith('.txt') else 'OTHER'
                    })
                    
        except Exception as e:
            self.logger.error(f"Error listing ZIP contents {zip_path}: {e}")
            
        return contents