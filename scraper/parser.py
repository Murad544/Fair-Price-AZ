"""Parse the structured data embedded in public Tap.az HTML pages."""

import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser


class CategoryChanged(ValueError):
    """The requested listing now belongs to a different category."""


class ListingUnavailable(ValueError):
    """The requested listing has been removed or is otherwise unavailable."""


class NextDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def extract_ads(html):
    """Return ad objects, without retaining contact/user records in the cache."""
    parser = NextDataParser()
    parser.feed(html)
    if not parser.parts:
        raise ValueError("No __NEXT_DATA__ found; page may be blocked or changed.")
    payload = json.loads("".join(parser.parts))
    page_props = payload["props"]["pageProps"]
    if page_props.get("hasInitialMissingAd") is True:
        raise ListingUnavailable("Listing is unavailable")
    cache = page_props["apolloState"]
    return [v for v in cache.values() if isinstance(v, dict) and v.get("__typename") == "Ad"]


def normalize(ad):
    """Preserve source labels; leave unsupported features unknown."""
    path = ad.get("path", "")
    match = re.fullmatch(r"/elanlar/elektronika/telefonlar/(\d+)", path)
    if not match:
        raise ValueError("Not a phone-category listing path")
    props = {p["name"]: p.get("value") for p in ad.get("azProperties", ad.get("properties", []))}
    memory = re.fullmatch(r"(\d+)\s*(GB|TB)(?:\s*/\s*(\d+)\s*GB)?", props.get("Yaddaş") or "", re.I)
    label = ad.get("features", {}).get("adFeatures", {}).get("label")
    return {
        "listing_id": match[1],
        "url": "https://tap.az" + path,
        "title": ad.get("title"),
        "price_azn": ad.get("price"),
        "brand": props.get("Marka"),
        "model": props.get("Model"),
        "storage_gb": int(memory[1]) * (1024 if memory[2].upper() == "TB" else 1) if memory else None,
        "ram_gb": int(memory[3]) if memory and memory[3] else None,
        "condition": {"Bəli": "new", "Xeyr": "used"}.get(props.get("Yeni?")),
        "color": props.get("Rəng"),
        "city": ad.get("region"),
        "seller_type": "shop" if ad.get("shop") or label == "RETAILER" else None,
        "description": ad.get("body"),
        "photo_count": len(ad["photos"]) if isinstance(ad.get("photos"), list) else None,
        "year": None,
        "has_box": None,
        "has_warranty": None,
        "posted_date": None,
        "source_updated_at": ad.get("updatedAt"),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "raw_properties": props,
        "record_type": "detail" if "body" in ad else "index",
    }


def parse_index(html):
    """Collect unique category records; these may include accessories."""
    records = {}
    for ad in extract_ads(html):
        if re.fullmatch(r"/elanlar/elektronika/telefonlar/\d+", ad.get("path", "")):
            row = normalize(ad)
            records[row["listing_id"]] = row
    if not records:
        raise ValueError("No category listings found; inspect the page before continuing.")
    return list(records.values())


def parse_detail(html, listing_id):
    """Select only the requested ad, never a recommendation on the page."""
    ads = extract_ads(html)
    for ad in ads:
        if ad.get("path") == f"/elanlar/elektronika/telefonlar/{listing_id}":
            if "body" not in ad or "properties" not in ad:
                raise ValueError("Requested ad has no detail payload")
            return normalize(ad)
    for ad in ads:
        path = ad.get("path", "")
        if (str(ad.get("legacyResourceId")) == str(listing_id)
                and re.fullmatch(r"/elanlar/(?:[^/]+/)+" + re.escape(str(listing_id)), path)
                and not path.startswith("/elanlar/elektronika/telefonlar/")):
            raise CategoryChanged(f"Listing {listing_id} moved to {path}")
    raise ValueError(f"Listing {listing_id} not found in page")
