"""Run: .venv/bin/python -m uvicorn api.main:app --reload"""

from contextlib import asynccontextmanager
import logging
import os
import ssl
from pathlib import Path

import certifi
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from api.live import ListingFetcher, LiveError
from api.predict import Predictor
from api.schemas import HealthResponse, ListingPredictionResponse, PredictRequest, PredictionResponse, UrlRequest
from scraper.tap_az import Client

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def create_app(model_path=None):
    @asynccontextmanager
    async def lifespan(app):
        path = Path(model_path or os.environ.get("FAIR_PRICE_MODEL_PATH", ROOT / "model/artifacts/pipeline.joblib"))
        # Fail startup rather than accepting requests with a missing/broken model.
        app.state.predictor = Predictor(path)
        context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or certifi.where())
        app.state.fetcher = ListingFetcher(Client(user_agent=os.environ.get(
            "FAIR_PRICE_USER_AGENT", "FairPriceAZ/0.2 (research prototype)"), ssl_context=context))
        yield
        del app.state.predictor
        del app.state.fetcher

    app = FastAPI(title="Fair Price AZ API", version="0.1.0", lifespan=lifespan,
                  description="Predict smartphone asking prices in AZN for used and new phones.")
    origins = [value.strip() for value in os.environ.get(
        "FAIR_PRICE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])

    def predict(request, phone, actual_price):
        try:
            return request.app.state.predictor.predict(phone, actual_price)
        except Exception as error:
            logger.exception("Model prediction failed")
            raise HTTPException(503, "Prediction is temporarily unavailable") from error

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request):
        return HealthResponse(status="ok", model_version=request.app.state.predictor.version)

    @app.post("/predict", response_model=PredictionResponse)
    def predict_phone(body: PredictRequest, request: Request):
        return predict(request, body, body.actual_price_azn)

    @app.post("/predict-from-url", response_model=ListingPredictionResponse)
    def predict_url(body: UrlRequest, request: Request):
        try:
            listing_id, phone, price = request.app.state.fetcher.fetch(body.url)
        except LiveError as error:
            headers = {"Retry-After": "3"} if error.status_code == 429 else None
            raise HTTPException(error.status_code, str(error), headers=headers) from error
        result = predict(request, phone, price)
        return ListingPredictionResponse(**result.model_dump(), listing_id=listing_id,
                                         url=body.url, features=phone)

    return app


app = create_app()
