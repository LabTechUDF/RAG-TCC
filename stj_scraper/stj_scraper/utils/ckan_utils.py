"""
CKAN API utilities for STJ dataset portal
"""
import requests
import re
from urllib.parse import urljoin, urlparse
import logging
from typing import List, Dict, Optional


class CKANPortalScraper:
    """Handle CKAN portal interactions for STJ dataset"""
    
    def __init__(self, base_url="https://dadosabertos.web.stj.jus.br", timeout=30):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
        # Set headers for identifiable academic research
        self.session.headers.update({
            'User-Agent': 'RAG-TCC/stj_scraper (Academic Research; Contact: tcc@udf.edu.br)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def get_dataset_resources_html(self, dataset_url: str) -> List[Dict]:
        """Extract resources from dataset HTML page"""
        resources = []
        
        try:
            self.logger.info(f"Fetching dataset page: {dataset_url}")
            response = self.session.get(dataset_url, timeout=self.timeout)
            response.raise_for_status()
            
            html_content = response.text
            
            # Extract resource items using robust regex patterns
            # Look for li elements with resource-item class
            resource_pattern = r'<li[^>]+class="[^"]*resource-item[^"]*"[^>]*data-id="([^"]+)"[^>]*>(.*?)</li>'
            resource_matches = re.findall(resource_pattern, html_content, re.DOTALL)
            
            for resource_id, resource_html in resource_matches:
                resource_info = self._extract_resource_info(resource_html, resource_id, dataset_url)
                if resource_info:  # This now filters out non-ZIP resources
                    resources.append(resource_info)
                    
            self.logger.info(f"Found {len(resources)} resources in dataset")
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch dataset page {dataset_url}: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing dataset page {dataset_url}: {e}")
            
        return resources
    
    def get_resource_download_url(self, resource_page_url: str) -> Optional[str]:
        """Get download URL from resource page"""
        try:
            self.logger.debug(f"Fetching resource page: {resource_page_url}")
            response = self.session.get(resource_page_url, timeout=self.timeout)
            response.raise_for_status()
            
            html_content = response.text
            
            # Look for download links with resource-url-analytics class
            download_patterns = [
                r'<a[^>]+class="[^"]*resource-url-analytics[^"]*"[^>]+href="([^"]+/download/[^"]+)"[^>]*>',
                r'<a[^>]+href="([^"]+/download/[^"]+)"[^>]*class="[^"]*resource-url-analytics[^"]*"[^>]*>',
                r'href="([^"]+/download/[^"]+)"[^>]*[^>]*>[\s]*Baixar',
            ]
            
            for pattern in download_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    download_url = matches[0]
                    # Ensure absolute URL
                    if download_url.startswith('/'):
                        download_url = urljoin(self.base_url, download_url)
                    
                    self.logger.debug(f"Found download URL: {download_url}")
                    return download_url
            
            self.logger.warning(f"No download URL found in resource page: {resource_page_url}")
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch resource page {resource_page_url}: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing resource page {resource_page_url}: {e}")
            
        return None
    
    def download_resource(self, download_url: str, output_path: str) -> bool:
        """Download resource file"""
        try:
            self.logger.info(f"Downloading resource: {download_url}")
            
            with self.session.get(download_url, stream=True, timeout=self.timeout) as response:
                response.raise_for_status()
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                self.logger.info(f"Downloaded to: {output_path}")
                return True
                
        except requests.RequestException as e:
            self.logger.error(f"Failed to download resource {download_url}: {e}")
        except Exception as e:
            self.logger.error(f"Error downloading resource {download_url}: {e}")
            
        return False
    
    def get_resource_via_api(self, resource_id: str) -> Optional[Dict]:
        """Try to get resource info via CKAN API (fallback)"""
        try:
            api_url = f"{self.base_url}/api/3/action/resource_show?id={resource_id}"
            
            self.logger.debug(f"Trying CKAN API: {api_url}")
            response = self.session.get(api_url, timeout=self.timeout)
            response.raise_for_status()
            
            api_data = response.json()
            
            if api_data.get('success') and api_data.get('result'):
                resource_data = api_data['result']
                return {
                    'resource_id': resource_data.get('id'),
                    'filename': resource_data.get('name'),
                    'download_url': resource_data.get('url'),
                    'format': resource_data.get('format'),
                    'size': resource_data.get('size'),
                    'created': resource_data.get('created'),
                    'last_modified': resource_data.get('last_modified'),
                }
            
        except requests.RequestException as e:
            self.logger.warning(f"CKAN API failed for resource {resource_id}: {e}")
        except Exception as e:
            self.logger.warning(f"CKAN API error for resource {resource_id}: {e}")
            
        return None
    
    def _extract_resource_info(self, resource_html: str, resource_id: str, dataset_url: str) -> Optional[Dict]:
        """Extract resource information from HTML snippet"""
        try:
            # Extract heading link and title
            heading_pattern = r'<a[^>]+class="[^"]*heading[^"]*"[^>]+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>'
            heading_match = re.search(heading_pattern, resource_html)
            
            if not heading_match:
                self.logger.warning(f"No heading found for resource {resource_id}")
                return None
            
            resource_href = heading_match.group(1)
            resource_title = heading_match.group(2)
            
            # Construct full resource page URL
            if resource_href.startswith('/'):
                resource_page_url = urljoin(self.base_url, resource_href)
            else:
                resource_page_url = resource_href
            
            # Check for ZIP format (strict validation)
            is_zip = resource_title.lower().endswith('.zip')
            
            # Only return ZIP resources for STJ dataset processing
            if not is_zip:
                self.logger.debug(f"Skipping non-ZIP resource: {resource_title}")
                return None
            
            return {
                'resource_id': resource_id,
                'filename': resource_title,
                'resource_page_url': resource_page_url,
                'dataset_url': dataset_url,
                'is_zip': is_zip,
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting resource info for {resource_id}: {e}")
            return None