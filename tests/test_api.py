"""Offline API tests: no live marketplace traffic or production model writes."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient
import joblib
import pandas as pd

from api.live import ListingFetcher, LiveError
from api.main import create_app
from model.pipeline import build_pipeline, features

URL = "https://tap.az/elanlar/elektronika/telefonlar/123"
PHONE = dict(brand="Apple", model="iPhone 13", condition="used", storage_gb=128)


def listing_html(condition="Xeyr", brand="Apple iPhone", description="A phone"):
    ad = dict(__typename="Ad", path="/elanlar/elektronika/telefonlar/123", price=600, body=description,
              properties=[{"name":k,"value":v} for k,v in {
                  "Marka":brand, "Model":"13", "Yeni?":condition, "Yaddaş":"128GB"}.items()])
    payload = {"props":{"pageProps":{"apolloState":{"ad":ad}}}}
    return '<script id="__NEXT_DATA__">' + json.dumps(payload) + '</script>'


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "pipeline.joblib"
        frame = pd.DataFrame([PHONE, dict(PHONE, condition="new")] * 10)
        pipeline = build_pipeline(n_estimators=10).fit(features(frame), [500, 800] * 10)
        joblib.dump(pipeline, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.app = create_app(self.path)
        self.client = TestClient(self.app).__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_saved_pipeline_parity_and_health(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["model_version"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        for condition in ("used", "new"):
            phone = dict(PHONE, condition=condition)
            expected = joblib.load(self.path).predict(features(pd.DataFrame([phone])))[0]
            result = self.client.post("/predict", json=phone)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["predicted_price_azn"], round(expected, 2))
            self.assertIsNone(result.json()["verdict"])

    def test_verdicts_and_aliases(self):
        for condition in ("used", "new"):
            phone = dict(PHONE, condition=condition)
            price = self.client.post("/predict", json=phone).json()["predicted_price_azn"]
            result = self.client.post("/predict", json=dict(phone, actual_price_azn=price * 1.1)).json()
            self.assertEqual(result["verdict"], "Fair price" if condition=="used" else "Overpriced by 10%")
        alias = self.client.post("/predict", json=dict(PHONE, brand=" Apple iPhone ", model="13"))
        normal = self.client.post("/predict", json=PHONE)
        self.assertEqual(alias.json(), normal.json())

    def test_invalid_inputs_are_rejected(self):
        for change in ({"condition":"unknown"}, {"brand":" "}, {"storage_gb":True}, {"ram_gb":-1},
                       {"photo_count":-1}, {"actual_price_azn":0}, {"actual_price_azn":"nan"},
                       {"seller_type":"retailer"}, {"price_azn":500}):
            response = self.client.post("/predict", json=dict(PHONE, **change))
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.post("/predict", json={}).status_code, 422)

    def test_url_validation_blocks_other_destinations(self):
        with patch.object(self.app.state.fetcher, "fetch") as fetch:
            for url in ("http://127.0.0.1/", "https://tap.az.evil.com/elanlar/elektronika/telefonlar/123",
                        "https://tap.az@evil.com/elanlar/elektronika/telefonlar/123", URL+"?url=http://localhost",
                        URL+"#fragment", URL.replace("tap.az", "tap.az:443"), URL.replace("telefonlar", "cars")):
                self.assertEqual(self.client.post("/predict-from-url", json={"url":url}).status_code, 422)
            fetch.assert_not_called()

    def test_url_lookup_parses_cleans_and_predicts(self):
        upstream = Mock()
        upstream.request.return_value = listing_html()
        self.app.state.fetcher = ListingFetcher(upstream)
        response = self.client.post("/predict-from-url", json={"url":URL+"/"})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["features"]["brand"], "Apple")
        self.assertEqual(result["features"]["model"], "iPhone 13")
        self.assertEqual(result["actual_price_azn"], 600)
        self.assertNotIn("description", result)
        upstream.check_robots.assert_called_once()
        upstream.request.assert_called_once_with("/elanlar/elektronika/telefonlar/123")

    def test_ambiguous_and_excluded_listings_are_rejected(self):
        upstream = Mock()
        self.app.state.fetcher = ListingFetcher(upstream)
        for html in (listing_html(condition="Unknown"), listing_html(brand="Aksesuarlar"),
                     listing_html(condition="Bəli", description="Az işlənib")):
            upstream.request.return_value = html
            self.assertEqual(self.client.post("/predict-from-url", json={"url":URL}).status_code, 422)

    def test_upstream_errors_and_busy_lookup(self):
        upstream = Mock()
        self.app.state.fetcher = ListingFetcher(upstream)
        for error, expected in ((HTTPError(URL,404,"missing",{},None),404),
                                (HTTPError(URL,429,"limited",{},None),503),
                                (URLError("offline"),502), (TimeoutError(),504),
                                (ValueError("redirect"),502)):
            upstream.request.side_effect = error
            self.assertEqual(self.client.post("/predict-from-url", json={"url":URL}).status_code, expected)
        with self.app.state.fetcher.lock:
            result = self.client.post("/predict-from-url", json={"url":URL})
            self.assertEqual(result.status_code, 429)
            self.assertEqual(result.headers["retry-after"], "3")

    def test_model_loads_once_and_missing_model_fails_startup(self):
        with patch("api.predict.joblib.load", wraps=joblib.load) as load:
            with TestClient(create_app(self.path)) as client:
                client.post("/predict", json=PHONE)
                client.post("/predict", json=PHONE)
            self.assertEqual(load.call_count, 1)
        with self.assertRaises(FileNotFoundError):
            with TestClient(create_app(self.path.parent / "missing.joblib")):
                pass

    def test_docs_and_local_frontend_cors(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertIn("/predict-from-url",self.client.get("/openapi.json").json()["paths"])
        response = self.client.options("/predict", headers={"Origin":"http://localhost:5173",
                     "Access-Control-Request-Method":"POST", "Access-Control-Request-Headers":"content-type"})
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_api_configures_verified_tls_without_system_ca_file(self):
        import ssl
        from urllib.request import HTTPSHandler
        handler = next(h for h in self.app.state.fetcher.client.opener.handlers if isinstance(h, HTTPSHandler))
        self.assertTrue(handler._context.check_hostname)
        self.assertEqual(handler._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreater(handler._context.cert_store_stats()['x509_ca'], 0)

    def test_certificate_error_is_distinguished_from_connectivity(self):
        import ssl
        upstream = Mock()
        upstream.request.side_effect = URLError(ssl.SSLCertVerificationError('certificate verify failed'))
        self.app.state.fetcher = ListingFetcher(upstream)
        with self.assertLogs('api.live', level='WARNING') as logs:
            result = self.client.post('/predict-from-url', json={'url':URL})
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json()['detail'], "Could not verify Tap.az's TLS certificate")
        self.assertIn('certificate verify failed', logs.output[0])

    def test_upstream_http_status_and_stage_are_preserved(self):
        for stage in ('robots.txt', 'listing'):
            for code in (403, 429, 500, 404):
                with self.subTest(stage=stage, code=code):
                    upstream = Mock()
                    method = upstream.check_robots if stage == 'robots.txt' else upstream.request
                    method.side_effect = HTTPError(URL, code, 'upstream failure', {}, None)
                    self.app.state.fetcher = ListingFetcher(upstream)
                    with self.assertLogs('api.live', level='WARNING') as logs:
                        response = self.client.post('/predict-from-url', json={'url': URL})
                    if code == 404 and stage == 'listing':
                        self.assertEqual(response.status_code, 404)
                    else:
                        self.assertEqual(response.status_code, 503)
                        self.assertIn(f'HTTP {code}', response.json()['detail'])
                    self.assertIn(f'Tap.az HTTP {code} while fetching {stage}', logs.output[0])
                    if stage == 'robots.txt':
                        upstream.request.assert_not_called()
