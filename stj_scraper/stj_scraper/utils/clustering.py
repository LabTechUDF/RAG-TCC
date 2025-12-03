"""
Clustering utilities for organizing scraped decisions
"""
import random
from typing import List, Dict, Optional


class DecisionClusterer:
    """Handle clustering and organization of legal decisions"""
    
    def __init__(self, article_filter: Optional[List[str]] = None, cluster_order: str = 'article'):
        self.article_filter = set(article_filter) if article_filter else None
        self.cluster_order = cluster_order
        self.processed_articles = set()
    
    def should_include_article(self, cluster_name: str) -> bool:
        """Check if article should be included based on filter"""
        if not self.article_filter:
            return True
        
        # Extract article number from cluster_name (e.g., "art_179" -> "179")
        if cluster_name and cluster_name.startswith('art_'):
            article_num = cluster_name.replace('art_', '')
            return article_num in self.article_filter
        
        return False
    
    def get_cluster_path(self, cluster_name: str, zip_filename: str) -> str:
        """Generate logical cluster path for organization"""
        if not cluster_name:
            cluster_name = 'unknown'
        
        # Extract base filename without extension
        zip_base = zip_filename.replace('.zip', '') if zip_filename else 'unknown'
        
        # Create hierarchical path: data/clustered/CLUSTER/ZIP_PERIOD/
        return f"data/clustered/{cluster_name.upper()}/{zip_base}/"
    
    def organize_by_order(self, decisions: List[Dict]) -> List[Dict]:
        """Organize decisions based on cluster order"""
        if not decisions:
            return decisions
        
        if self.cluster_order == 'random':
            decisions_copy = decisions.copy()
            random.shuffle(decisions_copy)
            return decisions_copy
        
        elif self.cluster_order == 'article':
            # Sort by cluster_name (article), then by case number if available
            return sorted(decisions, key=lambda d: (
                d.get('cluster_name', 'zzz_unknown'),  # Sort unknown articles last
                d.get('case_number', '0')  # Secondary sort by case number
            ))
        
        # Default: return as-is
        return decisions
    
    def get_article_statistics(self, decisions: List[Dict]) -> Dict:
        """Get statistics about processed articles"""
        stats = {
            'total_decisions': len(decisions),
            'articles_found': {},
            'unique_articles': 0,
            'unknown_articles': 0
        }
        
        for decision in decisions:
            cluster_name = decision.get('cluster_name', 'unknown')
            
            if cluster_name == 'unknown' or not cluster_name:
                stats['unknown_articles'] += 1
            else:
                if cluster_name not in stats['articles_found']:
                    stats['articles_found'][cluster_name] = 0
                stats['articles_found'][cluster_name] += 1
        
        stats['unique_articles'] = len(stats['articles_found'])
        
        return stats
    
    def apply_article_filter_to_records(self, json_records: List[Dict]) -> List[Dict]:
        """Pre-filter JSON records based on article filter (if content analysis is possible)"""
        if not self.article_filter:
            return json_records
        
        # For now, return all records since we need TXT content to determine articles
        # Article filtering happens later during processing
        return json_records