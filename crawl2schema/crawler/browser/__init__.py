import time
from typing import List, Dict, Any
from crawl2schema.crawler.schema import SyncBrowserCrawlerSchema, URLPaginationSchema
from crawl2schema.exceptions import RequestError, CrawlerError, FormatterError, ParseError
from selectolax.parser import HTMLParser
from playwright.sync_api import sync_playwright, BrowserContext


class SyncBrowserCrawler:
    """
    Synchronous browser-based crawler using Playwright.
    Supports dynamic rendering, scroll-based pagination, URL-following,
    nested schemas, list subfields, and full field extraction with formatters.
    """

    def __init__(self, context: BrowserContext = None):
        if context is None:
            self.playwright = sync_playwright().start()
            browser = self.playwright.chromium.launch(headless=True)
            self.context = browser.new_context()
        else:
            self.context = context
        self.page = self.context.new_page()

    def fetch(self, url: str, schema: SyncBrowserCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        on_pageload = schema.get("on_pageload")
        if "url_pagination" in schema and schema["url_pagination"]:
            return self._handle_url_pagination(url, schema=schema, *args, **kwargs)

        try:
            self.page.goto(url, *args, **kwargs)
            if on_pageload and callable(on_pageload):
                on_pageload(self.page)

            wait_for_selector = schema.get("wait_for_selector")
            if wait_for_selector:
                self.page.wait_for_selector(**wait_for_selector)
        except Exception as e:
            raise RequestError(f"Failed to crawl {url}: {e}")

        if "scroll_pagination" in schema and schema["scroll_pagination"]:
            self._handle_scroll_pagination(schema)
        elif "button_pagination" in schema and schema["button_pagination"]:
            self._handle_button_pagination(schema)

        return self._extract_data(schema)

    def _handle_scroll_pagination(self, schema: SyncBrowserCrawlerSchema):
        # Scroll-based pagination handling (same as previous)
        pagination = schema["scroll_pagination"]
        stop_condition = pagination.get("stop_condition", "count")
        scroll_delay = pagination.get("scroll_delay", 1.5)
        scroll_distance = pagination.get("scroll_distance", 1000)
        scroll_selector = pagination.get("scroll_selector", "window")
        base_selector = schema["base_selector"]
        retry_limit = pagination.get("retry_limit", 3)
        retry_scroll_distance = pagination.get("retry_scroll_distance", 0)
        scroll_horizontal = pagination.get("scroll_horizontal", False)
        on_scroll = schema.get("on_scroll")

        total_scrolls = 0
        previous_count = 0
        retry_counter = 0

        while True:
            if scroll_selector == "window":
                if scroll_horizontal:
                    self.page.evaluate(f"window.scrollBy({scroll_distance}, 0)")
                else:
                    self.page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            else:
                if scroll_horizontal:
                    self.page.locator(scroll_selector).evaluate(f"(el) => el.scrollBy({scroll_distance}, 0)")
                else:
                    self.page.locator(scroll_selector).evaluate(f"(el) => el.scrollBy(0, {scroll_distance})")

            if on_scroll and callable(on_scroll):
                on_scroll(self.page)

            time.sleep(scroll_delay)
            total_scrolls += 1

            html = self.page.content()
            tree = HTMLParser(html)
            current_count = len(tree.css(base_selector))

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
                    if retry_scroll_distance != 0:
                        if scroll_selector == "window":
                            if scroll_horizontal:
                                self.page.evaluate(f"window.scrollBy({retry_scroll_distance}, 0)")
                            else:
                                self.page.evaluate(f"window.scrollBy(0, {retry_scroll_distance})")
                        else:
                            if scroll_horizontal:
                                self.page.locator(scroll_selector).evaluate(
                                    f"(el) => el.scrollBy({retry_scroll_distance}, 0)"
                                )
                            else:
                                self.page.locator(scroll_selector).evaluate(
                                    f"(el) => el.scrollBy(0, {retry_scroll_distance})"
                                )
                    if retry_counter >= retry_limit:
                        break
                else:
                    retry_counter = 0
                    previous_count = current_count

    def _handle_url_pagination(self, url: str, schema: SyncBrowserCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        pagination: URLPaginationSchema = schema["url_pagination"]
        results: List[Dict[str, Any]] = []

        start = pagination.get("start_page", 1)
        end = pagination.get("end_page", 1)
        placeholder = pagination.get("page_placeholder", "{page}")
        wait_for_selector = schema.get("wait_for_selector")
        on_pageload = schema.get("on_pageload")

        for i in range(start, end + 1):
            page_url = url.replace(placeholder, str(i))
            self.page.goto(page_url, *args, **kwargs)

            if on_pageload and callable(on_pageload):
                on_pageload(self.page)

            if wait_for_selector:
                self.page.wait_for_selector(**wait_for_selector)

            time.sleep(1.5)
            results.extend(self._extract_data(schema))

        return results

    def _handle_button_pagination(self, schema: SyncBrowserCrawlerSchema):
        # Button pagination handling (same as previous)
        pagination = schema.get("button_pagination")
        if not pagination:
            return

        scroll_distance = pagination.get("scroll_distance", 0)
        cycle_delay = pagination.get("cycle_delay", 1.5)
        retry_delay = pagination.get("retry_delay", 2)
        scroll_selector = pagination.get("scroll_selector", "window")
        retry_limit = pagination.get("retry_limit", 3)
        retry_scroll_distance = pagination.get("retry_scroll_distance", 0)
        scroll_horizontal = pagination.get("scroll_horizontal", False)
        stop_condition = pagination.get("stop_condition", "no-button")
        button_selector = pagination.get("button_selector")
        base_selector = schema.get("base_selector")
        total_scrolls = 0
        retry_counter = 0
        total_clicks = 0
        max_clicks = pagination.get("click_count", 5) if stop_condition == "count" else None
        stop_selector = pagination.get("stop_selector") if stop_condition == "element" else None
        on_scroll = schema.get("on_scroll")

        while True:
            if scroll_distance != 0:
                if scroll_selector == "window":
                    if scroll_horizontal:
                        self.page.evaluate(f"window.scrollBy({scroll_distance}, 0)")
                    else:
                        self.page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                else:
                    if scroll_horizontal:
                        self.page.locator(scroll_selector).evaluate(f"(el) => el.scrollBy({scroll_distance}, 0)")
                    else:
                        self.page.locator(scroll_selector).evaluate(f"(el) => el.scrollBy(0, {scroll_distance})")

                if on_scroll and callable(on_scroll):
                    on_scroll(self.page)

                time.sleep(cycle_delay)
                total_scrolls += 1

            button = self.page.locator(button_selector)
            if button.count() == 0 or not button.first.is_visible():
                if retry_counter < retry_limit:
                    retry_counter += 1
                    if retry_scroll_distance != 0:
                        if scroll_selector == "window":
                            if scroll_horizontal:
                                self.page.evaluate(f"window.scrollBy({retry_scroll_distance}, 0)")
                            else:
                                self.page.evaluate(f"window.scrollBy(0, {retry_scroll_distance})")
                        else:
                            if scroll_horizontal:
                                self.page.locator(scroll_selector).evaluate(
                                    f"(el) => el.scrollBy({retry_scroll_distance}, 0)"
                                )
                            else:
                                self.page.locator(scroll_selector).evaluate(
                                    f"(el) => el.scrollBy(0, {retry_scroll_distance})"
                                )

                    time.sleep(retry_delay)
                    continue
                elif stop_condition == "no-button":
                    break
                else:
                    raise CrawlerError("Button to load more dynamic content not detected.")

            button.first.click()
            total_clicks += 1
            time.sleep(cycle_delay)

            html = self.page.content()
            tree = HTMLParser(html)

            if stop_condition == "count" and total_clicks >= max_clicks:
                break
            elif stop_condition == "element" and stop_selector:
                stop_elements = self.page.locator(stop_selector)
                if stop_elements.count() > 0 and stop_elements.first.is_visible():
                    break
            if "scroll_count" in pagination and total_scrolls >= pagination["scroll_count"]:
                break
            elif "stop_selector" in pagination and pagination["stop_selector"]:
                if self.page.locator(pagination["stop_selector"]).count() > 0:
                    break

    def _extract_data(self, schema: SyncBrowserCrawlerSchema) -> List[Dict[str, Any]]:
        html = self.page.content()
        tree = HTMLParser(html)
        base_selector = schema.get("base_selector")
        if not base_selector:
            raise ValueError("Missing base_selector in schema")

        items = tree.css(base_selector)
        results = []

        for item in items:
            record: Dict[str, Any] = {}
            for field in schema.get("fields", []):
                try:
                    if field.get("type") == "list":
                        record[field["name"]] = self._extract_list_field(item, field)
                        continue

                    raw = field.get("default")
                    value = raw
                    el = item.css_first(field["selector"]) if "selector" in field else None
                    if el:
                        raw = el.attributes.get(field.get("attribute"), raw) if "attribute" in field else el.text()

                    if field.get("preformatter") and callable(field["preformatter"]):
                        raw = field["preformatter"](raw)

                    value = self._cast_type(raw, field.get("type", "text"))
                    if field.get("postformatter") and callable(field["postformatter"]):
                        value = field["postformatter"](value)

                except Exception as e:
                    raise CrawlerError(f"Failed to extract field {field.get('name')}: {e}")

                try:
                    if "url_follow_schema" in field:
                        if isinstance(value, str) and value:
                            nested_page = self.context.new_page()
                            nested_crawler = SyncBrowserCrawler.__new__(SyncBrowserCrawler)
                            nested_crawler.context = self.context
                            nested_crawler.page = nested_page
                            if hasattr(self, "playwright"):
                                nested_crawler.playwright = self.playwright
                            nested_data = nested_crawler.fetch(value, field["url_follow_schema"])
                            nested_page.close()

                            record[field["name"]] = {}
                            if isinstance(nested_data, list) and len(nested_data) == 1:
                                record[field["name"]] = nested_data[0]
                            elif isinstance(nested_data, list):
                                for nd in nested_data:
                                    record[field["name"]].update(nd)
                            else:
                                record[field["name"]] = nested_data
                        else:
                            record[field["name"]] = field.get("default")
                    else:
                        record[field["name"]] = value
                except Exception as e:
                    raise CrawlerError(f"Failed to extract field {field.get('name')}: {e}")

            results.append(record)

        return results

    def _extract_list_field(self, parent, field):
        values: List[Any] = []
        list_subfields = field.get("list_subfields")
        selector = field["selector"]
        attr = field.get("attribute")
        default = field.get("default")
        type_ = field.get("type", "text")
        preformatter = field.get("preformatter")
        postformatter = field.get("postformatter")
        list_formatter = field.get("list_formatter")

        for el in parent.css(selector):
            if list_subfields:
                obj: Dict[str, Any] = {}
                for sub in list_subfields:
                    sub_el = el.css_first(sub["selector"]) if el else None
                    subraw = sub.get("default")
                    if sub_el:
                        subraw = sub_el.attributes.get(sub.get("attribute"), subraw) if "attribute" in sub else sub_el.text()
                    if sub.get("preformatter") and callable(sub["preformatter"]):
                        subraw = sub["preformatter"](subraw)
                    subval = self._cast_type(subraw, sub.get("type", "text"))
                    if sub.get("postformatter") and callable(sub["postformatter"]):
                        subval = sub["postformatter"](subval)

                    if "url_follow_schema" in sub:
                        if isinstance(subval, str) and subval:
                            nested_page = self.context.new_page()
                            nested_crawler = SyncBrowserCrawler.__new__(SyncBrowserCrawler)
                            nested_crawler.context = self.context
                            nested_crawler.page = nested_page
                            if hasattr(self, "playwright"):
                                nested_crawler.playwright = self.playwright
                            nested_data = nested_crawler.fetch(subval, sub["url_follow_schema"])
                            nested_page.close()
                            if isinstance(nested_data, list) and len(nested_data) == 1:
                                obj[sub["name"]] = nested_data[0]
                            elif isinstance(nested_data, list):
                                obj[sub["name"]] = {}
                                for nd in nested_data:
                                    obj[sub["name"]].update(nd)
                            else:
                                obj[sub["name"]] = nested_data
                        else:
                            obj[sub["name"]] = sub.get("default")
                    else:
                        obj[sub["name"]] = subval
                values.append(obj)
            else:
                raw = el.attributes.get(attr, default) if attr else el.text()
                if preformatter and raw != default:
                    raw = preformatter(raw)
                val = self._cast_type(raw, type_) if raw != default else default
                if postformatter and val != default:
                    val = postformatter(val)
                values.append(val)

        if list_formatter and callable(list_formatter):
            values = list_formatter(values)

        return values

    def _cast_type(self, value, type_: str):
        try:
            if type_ == "number":
                value = float(value)
                if value.is_integer():
                    value = int(value)
            elif type_ == "json":
                import json
                value = json.loads(value)
            else:
                value = str(value)
            return value
        except Exception as e:
            raise FormatterError(f"Failed to cast '{value}' to {type_}: {e}") from e

    def close(self):
        self.context.close()
        if hasattr(self, "playwright"):
            self.playwright.stop()
