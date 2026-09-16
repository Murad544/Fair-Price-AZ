"""Validated public request and response contracts."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=1, max_length=120)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
Price = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
LISTING_URL = re.compile(r"https://tap\.az/elanlar/elektronika/telefonlar/([0-9]{1,20})/?")


class PhoneFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    brand: Name
    model: Name
    condition: Literal["used", "new"]
    storage_gb: PositiveInt | None = None
    ram_gb: PositiveInt | None = None
    photo_count: Annotated[int, Field(strict=True, ge=0)] | None = None
    city: Name | None = None
    seller_type: Literal["shop", "private"] | None = None

    @model_validator(mode="after")
    def normalize_apple(self):
        # Match the cleaned training labels for the source's Apple iPhone brand.
        if self.brand.casefold() in ("apple iphone", "apple"):
            self.brand = "Apple"
            if not self.model.casefold().startswith("iphone"):
                self.model = "iPhone " + self.model
        return self


class PredictRequest(PhoneFeatures):
    actual_price_azn: Price | None = None


class UrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    url: Annotated[str, Field(max_length=200)]

    @field_validator("url")
    @classmethod
    def listing_url(cls, value):
        if not LISTING_URL.fullmatch(value):
            raise ValueError("Use an HTTPS tap.az phone listing URL without query parameters or fragments")
        return value.rstrip("/")


class PredictionResponse(BaseModel):
    predicted_price_azn: Price
    currency: Literal["AZN"] = "AZN"
    condition: Literal["used", "new"]
    actual_price_azn: Price | None = None
    difference_pct: float | None = None
    verdict: str | None = None
    model_version: str


class ListingPredictionResponse(PredictionResponse):
    listing_id: str
    url: str
    features: PhoneFeatures


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_version: str
