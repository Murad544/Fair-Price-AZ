"""Fetch only Tap.az phone listings using the existing rate-limited client."""

from threading import Lock
import logging
import ssl
from urllib.error import HTTPError, URLError

from api.schemas import LISTING_URL, PhoneFeatures, UrlRequest
from model.pipeline import FEATURES
from processing.clean import classify
from scraper.parser import CategoryChanged, ListingUnavailable, parse_detail
from scraper.tap_az import Client

logger = logging.getLogger(__name__)

class LiveError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class ListingFetcher:
    def __init__(self, client=None):
        self.client = client or Client()
        self.lock = Lock()

    def fetch(self, url):
        # Validate here too: no alternate hosts, credentials, ports, or redirects.
        url = UrlRequest(url=url).url
        listing_id = LISTING_URL.fullmatch(url)[1]
        path = f"/elanlar/elektronika/telefonlar/{listing_id}"
        if not self.lock.acquire(blocking=False):
            raise LiveError(429, "Another listing lookup is running; try again shortly")
        try:
            try:
                self.client.check_robots()
                raw = parse_detail(self.client.request(path), listing_id)
            except (CategoryChanged, ListingUnavailable) as error:
                raise LiveError(404, "Phone listing is unavailable") from error
            except HTTPError as error:
                code = error.code
                error.close()
                if code in (404, 410):
                    raise LiveError(404, "Phone listing is unavailable") from error
                raise LiveError(503, "Tap.az is unavailable or limiting requests; try later") from error
            except TimeoutError as error:
                raise LiveError(504, "Tap.az lookup timed out") from error
            except URLError as error:
                logger.warning("Tap.az connection failed: %s", error.reason)
                if isinstance(error.reason, ssl.SSLCertVerificationError):
                    raise LiveError(502, "Could not verify Tap.az's TLS certificate") from error
                status = 504 if isinstance(error.reason, TimeoutError) else 502
                raise LiveError(status, "Could not reach Tap.az") from error
            except (ValueError, KeyError, TypeError, UnicodeError) as error:
                raise LiveError(502, "Tap.az listing could not be fetched or parsed") from error
            row = classify(raw)
            if row["quality_status"] != "candidate":
                raise LiveError(422, "Listing is outside supported scope or needs review: " +
                                ", ".join(row["exclusion_reasons"] + row["review_reasons"]))
            try:
                phone = PhoneFeatures(**{key: row.get(key) for key in FEATURES})
            except ValueError as error:
                raise LiveError(422, "Listing contains unsupported phone features") from error
            return listing_id, phone, row["price_azn"]
        finally:
            self.lock.release()
