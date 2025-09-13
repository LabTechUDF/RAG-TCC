#!/usr/bin/env python3
"""
Test script to verify the 5-item limit functionality in STF spider
"""

class MockSpider:
    """Mock spider to test the item counting logic"""
    
    def __init__(self):
        self.items_extracted = 0
        self.max_items = 5
        self.logger = self
        
    def info(self, message):
        print(f"INFO: {message}")
        
    def create_item(self, item_data):
        """Simulate item creation"""
        # Increment the items counter (same as in real spider)
        self.items_extracted += 1
        self.info(f"✅ Created item {self.items_extracted}/{self.max_items}: {item_data.get('title', 'No title')}")
        return item_data
    
    def yield_item_with_limit_check(self, item_data):
        """Yield an item and check if we've reached the extraction limit"""
        item = self.create_item(item_data)
        
        # Check if we've reached the limit after creating the item
        if self.items_extracted >= self.max_items:
            self.info(f"🏁 Reached maximum items limit ({self.max_items}). Closing spider.")
            raise Exception(f"Reached maximum items limit: {self.max_items}")
        
        return item

def test_item_limit():
    """Test the 5-item limit functionality"""
    spider = MockSpider()
    
    print("Testing 5-item limit functionality:")
    print("=" * 50)
    
    try:
        # Process 7 mock items to test the limit
        for i in range(7):
            item_data = {
                'title': f"Test Item {i+1}",
                'case_number': f"TEST{i+1:03d}",
                'content': f"Mock content for item {i+1}",
                'item_index': i+1
            }
            
            print(f"\nProcessing item {i+1}...")
            
            # Check if we've reached the maximum before processing
            if spider.items_extracted >= spider.max_items:
                print(f"🛑 Reached maximum items limit ({spider.max_items}). Stopping spider.")
                break
            
            # Yield the item with limit check
            try:
                result_item = spider.yield_item_with_limit_check(item_data)
                print(f"✅ Successfully processed: {result_item['title']}")
            except Exception as e:
                print(f"🏁 Spider stopped: {e}")
                break
                
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    print(f"\nFinal count: {spider.items_extracted} items extracted")
    print("Test completed!")

if __name__ == "__main__":
    test_item_limit()
