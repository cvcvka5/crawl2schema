from typing import List, Callable, Dict
import requests
import sqlite3
from ..schema import CrawlerSchema
from selectolax.parser import HTMLParser
import time


class SyncHTTPCrawler:
    def __init__(self, session: requests.Session = None):
        self.session = requests.Session() if session is None else session
    
    def fetch(self, url: str, crawler_schema: CrawlerSchema, headers: Dict, *args, **kwargs) -> List[Dict]:
        response = self.session.get(url, *args, headers=headers, **kwargs)
        tree = HTMLParser(response.text)
        
        baseSelector = crawler_schema.get("baseSelector", "body")
        targetElements = crawler_schema.get("targetElements", [])
        
        baseElement = tree.css_first(baseSelector)
        
        captures = []
        for target_el in targetElements:
            target_selector = target_el["selector"]
            default_value = target_el.get("default", None)
            
            specific_captures = []
            for el in baseElement.css(target_selector):
                target_attribute = target_el.get("attribute", False)
                if target_attribute:
                    value = el.attributes.get(target_attribute, default_value)
                else:
                    value = el.text()
                
                value = target_el.get("type", str)(value)
                
                if target_el.get("formatter", False):
                    formatter = target_el["formatter"]
                    value = formatter(value)
                
                capture = { target_el["name"]: value }
                specific_captures.append(capture)
                
            captures.append(specific_captures)
            
        merged_captures = []
        for group in zip(*captures):
            merged = {}
            for data in group:
                for key, value in data.items():
                    merged[key] = value
            merged_captures.append(merged)
            
        return merged_captures        
    
    def paginated_fetch(
            self, base_url: str, start_page: int, end_page: int,
            crawler_schema: CrawlerSchema, headers: Dict = None, interval_s: int = 0,
            *args, **kwargs
        ) -> List[Dict]:
            if "{page}" not in base_url:
                raise ValueError("Base URL must include '{page}' placeholder. (EX: https://www.example.com?page={page})")
            
            result = []
            for page_index in range(start_page, end_page+1):
                url = base_url.format(page=page_index)
                result.extend(self.fetch(url=url, crawler_schema=crawler_schema, headers=headers, *args, **kwargs))
                time.sleep(interval_s)
            
            return result

        
    
class AsyncHTTPCrawler:
    def __init__(self):
        pass

__all__ = [ "SyncHTTPCrawler", "AsyncHTTPCrawler" ]