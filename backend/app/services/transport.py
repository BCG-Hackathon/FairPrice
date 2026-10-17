"""Transport cost estimates from a village kiosk to a market.

`EstimatedTransport` uses straight-line distance x road factor. An Azure Maps
route-based provider can implement the same `TransportProvider` protocol later.
"""

import math
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings
from app.models import Kiosk, Market

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class TransportEstimate:
    distance_km: float
    cost_ugx_per_kg: float
    method: str


class TransportProvider(Protocol):
    def estimate(self, origin: Kiosk, market: Market) -> TransportEstimate: ...


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class EstimatedTransport:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def estimate(self, origin: Kiosk, market: Market) -> TransportEstimate:
        s = self._settings
        road_km = haversine_km(origin.latitude, origin.longitude, market.latitude, market.longitude) * s.road_factor
        cost = road_km * s.transport_ugx_per_kg_km
        if market.country != origin.country:
            cost += s.cross_border_ugx_per_kg
        return TransportEstimate(
            distance_km=round(road_km, 1),
            cost_ugx_per_kg=round(cost, 1),
            method="distance_estimate",
        )
