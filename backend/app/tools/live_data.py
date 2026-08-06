"""Frino OS - Live Data Tools (Weather, Gold, Location-aware)"""
from __future__ import annotations
from typing import Dict
import httpx

from app.tools.registry import BaseTool, ToolCategory, ToolResult


class WeatherTool(BaseTool):
    def __init__(self):
        super().__init__(
            "weather",
            "Get current weather for a location",
            ToolCategory.BROWSER,
            requires_confirmation=False
        )

    async def execute(self, location: str = "", **params) -> ToolResult:
        try:
            if not location:
                location = await self._detect_location()
            data = await self._get_weather(location)
            return ToolResult(success=True, output=data)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    async def _detect_location(self) -> str:
        """Detect user's city from IP."""
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://ip-api.com/json/", timeout=5.0)
            data = resp.json()
            return data.get("city", "Chennai")

    async def _get_weather(self, location: str) -> Dict:
        """Get weather from wttr.in (free, no API key)."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://wttr.in/{location}?format=j1",
                timeout=10.0
            )
            data = resp.json()
            current = data["current_condition"][0]
            return {
                "location": location,
                "temperature_c": current["temp_C"],
                "temperature_f": current["temp_F"],
                "feels_like_c": current["FeelsLikeC"],
                "description": current["weatherDesc"][0]["value"],
                "humidity": current["humidity"],
                "wind_kmph": current["windspeedKmph"],
                "wind_dir": current["winddir16Point"],
                "uv_index": current.get("uvIndex", "N/A"),
            }


class GoldPriceTool(BaseTool):
    def __init__(self):
        super().__init__(
            "gold_price",
            "Get current gold price",
            ToolCategory.BROWSER,
            requires_confirmation=False
        )

    async def execute(self, country: str = "india", **params) -> ToolResult:
        try:
            data = await self._get_gold_price(country)
            return ToolResult(success=True, output=data)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    async def _get_gold_price(self, country: str) -> Dict:
        """Get gold price from multiple free sources."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            usd_per_oz = 0

            # Source 1: metals.live API
            try:
                resp = await client.get(
                    "https://api.metals.live/v1/spot/gold",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list):
                        usd_per_oz = data[0].get("price", 0)
            except Exception:
                pass

            # Source 2: goldprice.org
            if not usd_per_oz:
                try:
                    resp = await client.get(
                        "https://data-asg.goldprice.org/dbXRates/USD",
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        usd_per_oz = data.get("items", [{}])[0].get("xauPrice", 0)
                except Exception:
                    pass

            if not usd_per_oz:
                return {"error": "gold_api_failed"}

            usd_per_gram = usd_per_oz / 31.1035
            inr_rate = await self._get_inr_rate(client)
            inr_per_gram = usd_per_gram * inr_rate
            inr_per_10g = inr_per_gram * 10

            return {
                "usd_per_oz": round(usd_per_oz, 2),
                "usd_per_gram": round(usd_per_gram, 2),
                "inr_per_gram": round(inr_per_gram, 2),
                "inr_per_10g": round(inr_per_10g, 2),
                "inr_rate": round(inr_rate, 2),
            }

    async def _get_inr_rate(self, client: httpx.AsyncClient) -> float:
        """Get USD to INR exchange rate."""
        try:
            resp = await client.get(
                "https://open.er-api.com/v6/latest/USD",
                timeout=5.0
            )
            data = resp.json()
            return data["rates"].get("INR", 83.5)
        except Exception:
            return 83.5


class LocationTool(BaseTool):
    def __init__(self):
        super().__init__(
            "location",
            "Detect user's current location from IP",
            ToolCategory.BROWSER,
            requires_confirmation=False
        )

    async def execute(self, **params) -> ToolResult:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://ip-api.com/json/", timeout=5.0)
                data = resp.json()
                return ToolResult(success=True, output={
                    "city": data.get("city", "Unknown"),
                    "region": data.get("regionName", ""),
                    "country": data.get("country", ""),
                    "timezone": data.get("timezone", ""),
                })
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
