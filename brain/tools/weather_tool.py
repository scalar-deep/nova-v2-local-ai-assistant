"""
Weather tool - fetches weather from OpenWeatherMap.
"""

import httpx
from typing import Optional
import os


class WeatherTool:
    """Fetches weather data from OpenWeatherMap."""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenWeatherMap API key required")
        
        self.client = httpx.Client(timeout=10.0)
    
    def get_weather(self, location: str) -> str:
        """
        Get weather for a location.
        
        Args:
            location: City name (e.g., "London", "New York")
        
        Returns:
            Natural language weather description
        """
        try:
            response = self.client.get(
                self.BASE_URL,
                params={
                    "q": location,
                    "appid": self.api_key,
                    "units": "metric"  # Celsius
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract weather info
            temp = round(data["main"]["temp"])
            feels_like = round(data["main"]["feels_like"])
            description = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            city = data["name"]
            
            # Format for speech
            return (
                f"In {city}, it's currently {temp} degrees Celsius "
                f"with {description}. "
                f"It feels like {feels_like} degrees, "
                f"and humidity is {humidity} percent."
            )
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"I couldn't find weather data for {location}."
            raise
        except Exception as e:
            return f"Sorry, I couldn't get the weather right now. {str(e)}"
