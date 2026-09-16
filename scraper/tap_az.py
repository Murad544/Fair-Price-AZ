"""Small HTTP client for the public HTML and read-only listing query."""

import json
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
from urllib.robotparser import RobotFileParser

BASE = "https://tap.az"
CATEGORY_ID = "Z2lkOi8vdGFwL0NhdGVnb3J5LzYxOQ"
QUERY = """
query GetAdSearch($first: Int, $after: String, $source: SourceEnum!, $filters: AdFilterInput) {
  adSearch(source: $source, filters: $filters) {
    ads(first: $first, after: $after) {
      nodes { path }
      pageInfo { endCursor hasNextPage }
    }
  }
}
"""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"Unexpected HTTP redirect ({code}); inspect before continuing")


class Client:
    def __init__(self, user_agent="FairPriceAZ/0.2 (research prototype)", delay=3, ssl_context=None):
        if delay < 3:
            raise ValueError("Request delay must be at least 3 seconds")
        self.user_agent = user_agent
        self.delay = delay
        self.last_request = None
        self.opener = build_opener(NoRedirects(), HTTPSHandler(context=ssl_context))
        self.robots = None

    def request(self, path, payload=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Expected a relative Tap.az path")
        url = BASE + path
        if self.robots is not None and not self.robots.can_fetch(self.user_agent, url):
            raise ValueError(f"robots.txt disallows {path}")
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"User-Agent": self.user_agent}
        if body is not None:
            headers["Content-Type"] = "application/json"
        self.last_request = time.monotonic()
        with self.opener.open(Request(url, data=body, headers=headers), timeout=30) as response:
            return response.read().decode("utf-8")

    def check_robots(self):
        text = self.request("/robots.txt")
        if "user-agent:" not in text.lower():
            raise ValueError("Unrecognized robots.txt response")
        self.robots = RobotFileParser()
        self.robots.parse(text.splitlines())
        self.delay = max(self.delay, self.robots.crawl_delay(self.user_agent) or 0)

    def page(self, cursor=None):
        response = json.loads(self.request("/graphql", {
            "query": QUERY,
            "variables": {"first": 24, "after": cursor, "source": "DESKTOP",
                          "filters": {"categoryId": CATEGORY_ID}},
        }))
        if response.get("errors"):
            raise ValueError(f"Listing query failed: {response['errors']}")
        connection = response["data"]["adSearch"]["ads"]
        info = connection["pageInfo"]
        if not isinstance(info.get("hasNextPage"), bool):
            raise ValueError("Missing pagination status")
        next_cursor = info.get("endCursor")
        if info["hasNextPage"] and (not next_cursor or next_cursor == cursor):
            raise ValueError("Pagination cursor failed to advance")
        return connection["nodes"], next_cursor, info["hasNextPage"]
