import time
from typing import List, Dict, Any, Union
from crawl2schema.crawler.schema import (
    BrowserCrawlerSchema,
    ScrollPaginationSchemaCount,
    ScrollPaginationSchemaElement,
    ScrollPaginationSchemaNoNewElements,
    URLPaginationSchema,
)
from crawl2schema.exceptions import RequestError
from selectolax.parser import HTMLParser
from playwright.sync_api import sync_playwright


class SyncBrowserCrawler:
    """
    A synchronous browser-based crawler using Playwright.
    Supports dynamic rendering, scroll-based pagination, and custom schemas.
    """

    def __init__(self, headless: bool = True):
        self.playwright = sync_playwright().start()
        browser = self.playwright.chromium.launch(headless=headless)
        self.context = browser.new_context()
        self.page = self.context.new_page()

    def fetch(self, url: str, schema: BrowserCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        try:
            # Navigate to initial URL
            self.page.goto(url, *args, **kwargs)

            # Handle URL pagination first
            if "url_pagination" in schema and schema["url_pagination"]:
                return self._handle_url_pagination(url, schema)

            # Handle scroll pagination
            elif "scroll_pagination" in schema and schema["scroll_pagination"]:
                self._handle_scroll_pagination(schema)

            # Extract after done
            return self._extract_data(schema)

        except Exception as e:
            raise RequestError(f"Failed to crawl {url}: {e}")

    # Scroll Pagination
    def _handle_scroll_pagination(
        self, schema: BrowserCrawlerSchema
    ):
        pagination = schema["scroll_pagination"]

        stop_condition = pagination.get("stop_condition", "count")
        scroll_delay = pagination.get("scroll_delay", 1.5)
        scroll_distance = pagination.get("scroll_distance", 1000)
        scroll_selector = pagination.get("scroll_selector", "window")
        base_selector = schema["base_selector"]

        # No-new-elements condition-specific
        retry_limit = pagination.get("retry_limit", 3)
        retry_scroll_distance = pagination.get("retry_scroll_distance", 0)

        total_scrolls = 0
        previous_count = 0
        retry_counter = 0

        while True:
            # Perform the scroll
            if scroll_selector == "window":
                self.page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            else:
                self.page.locator(scroll_selector).evaluate(
                    f"(el) => el.scrollBy(0, {scroll_distance})"
                )

            time.sleep(scroll_delay)
            total_scrolls += 1

            html = self.page.content()
            tree = HTMLParser(html)
            current_count = len(tree.css(base_selector))

            # Stop conditions
            if stop_condition == "count":
                max_scrolls = pagination.get("scroll_count", 5)
                if total_scrolls >= max_scrolls:
                    break

            elif stop_condition == "element":
                stop_selector = pagination.get("stop_selector")
                if stop_selector:
                    elements = self.page.locator(stop_selector)
                    if elements.count() > 0 and elements.first.is_visible():
                        break

            elif stop_condition == "no-new-elements":
                if current_count == previous_count:
                    retry_counter += 1
                    # Try additional scroll
                    if retry_scroll_distance > 0:
                        if scroll_selector == "window":
                            self.page.evaluate(f"window.scrollBy(0, {retry_scroll_distance})")
                        else:
                            self.page.locator(scroll_selector).evaluate(
                                f"(el) => el.scrollBy(0, {retry_scroll_distance})"
                            )
                    if retry_counter >= retry_limit:
                        break
                else:
                    retry_counter = 0
                    previous_count = current_count

    # URL Pagination
    def _handle_url_pagination(
        self, url: str, schema: BrowserCrawlerSchema
    ) -> List[Dict[str, Any]]:
        pagination: URLPaginationSchema = schema["url_pagination"]
        results = []

        start = pagination.get("start_page", 1)
        end = pagination.get("end_page", 1)
        placeholder = pagination.get("page_placeholder", "{page}")

        for i in range(start, end + 1):
            page_url = url.replace(placeholder, str(i))
            print(f"[BrowserCrawler] Fetching page {i}: {page_url}")
            self.page.goto(page_url, wait_until="networkidle")
            time.sleep(1.5)
            data = self._extract_data(schema)
            results.extend(data)

        return results

    # Data Extraction
    def _extract_data(self, schema: BrowserCrawlerSchema) -> List[Dict[str, Any]]:
        html = self.page.content()
        tree = HTMLParser(html)
        base_selector = schema.get("base_selector")

        if not base_selector:
            raise ValueError("Missing base_selector in schema")

        items = tree.css(base_selector)
        results = []

        for item in items:
            record = {}
            for field in schema.get("fields", []):
                value = None
                try:
                    el = item.css_first(field["selector"])
                    if not el:
                        value = field.get("default")
                    elif "attribute" in field:
                        value = el.attributes.get(field["attribute"], "")
                    else:
                        value = el.text()

                    # Apply preformatter -> convert to number if needed -> postformatter
                    if "preformatter" in field and callable(field["preformatter"]):
                        value = field["preformatter"](value)

                    if field.get("type") == "number":
                        try:
                            value = float(value)
                        except Exception:
                            pass

                    if "postformatter" in field and callable(field["postformatter"]):
                        value = field["postformatter"](value)
                except Exception as e:
                    raise RequestError(f"Failed to extract field {field['name']}: {e}")

                record[field["name"]] = value
            results.append(record)

        return results

    # Cleanup
    def close(self):
        self.context.close()
        self.playwright.stop()
