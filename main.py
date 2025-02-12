import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import time
import logging
import os
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import hashlib
import urllib3
import warnings
from abc import ABC, abstractmethod

# SSL-Warnungen unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', '.*Unverified HTTPS request.*')

@dataclass
class WeatherMeasurement:
    timestamp: str
    value: float
    unit: str
    parameter_type: str
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "unit": self.unit,
            "formatted": f"{self.value}{self.unit}"
        }

@dataclass
class WeatherForecast:
    date: str
    temperatures: Dict[str, float]
    humidity: Optional[float]
    precipitation: Dict[str, Any]
    wind: Dict[str, Any]
    conditions: str
    
    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "temperature": {
                "max": self.temperatures.get("max"),
                "min": self.temperatures.get("min"),
                "unit": "°C"
            },
            "humidity": {
                "value": self.humidity,
                "unit": "%"
            } if self.humidity else None,
            "precipitation": self.precipitation,
            "wind": self.wind,
            "conditions": self.conditions
        }

class WeatherData:
    def __init__(self, station_name: str, station_id: str):
        self.station = {
            "id": station_id,
            "name": station_name,
            "metadata": {}
        }
        self.measurements = {
            "temperature": [],
            "humidity": [],
            "precipitation": [],
            "radiation": [],
            "leaf_wetness": []
        }
        self.forecasts = {
            "hourly": [],
            "daily": []
        }
        self.warnings = []
        self.station_charts = {}
        self.last_updated = None

    def add_station_metadata(self, metadata: dict):
        self.station["metadata"].update(metadata)

    def add_measurement(self, measurement: WeatherMeasurement):
        category = self._get_measurement_category(measurement.parameter_type)
        if category:
            self.measurements[category].append(measurement.to_dict())

    def add_forecast(self, forecast_type: str, forecast: WeatherForecast):
        if forecast_type in self.forecasts:
            self.forecasts[forecast_type].append(forecast.to_dict())

    def _get_measurement_category(self, param_type: str) -> Optional[str]:
        mappings = {
            "Temperatur": "temperature",
            "Luftfeuchte": "humidity",
            "Niederschlag": "precipitation",
            "Globalstrahlung": "radiation",
            "Blattnässe": "leaf_wetness"
        }
        return next((v for k, v in mappings.items() if k.lower() in param_type.lower()), None)

    def to_json(self) -> dict:
        """Konvertiert die Daten in ein webapp-freundliches JSON-Format"""
        return {
            "meta": {
                "station": self.station,
                "last_updated": self.last_updated,
                "data_timerange": {
                    "start": min(m["timestamp"] for measurements in self.measurements.values() 
                               for m in measurements) if any(self.measurements.values()) else None,
                    "end": max(m["timestamp"] for measurements in self.measurements.values() 
                             for m in measurements) if any(self.measurements.values()) else None
                }
            },
            "current": {
                category: sorted(measurements, key=lambda x: x["timestamp"])[-1] 
                if measurements else None
                for category, measurements in self.measurements.items()
            },
            "historical": {
                category: sorted(measurements, key=lambda x: x["timestamp"])
                for category, measurements in self.measurements.items()
            },
            "forecast": self.forecasts,
            "warnings": self.warnings,
            "visualizations": self.station_charts
        }

class BaseDataCollector(ABC):
    def __init__(self, session: requests.Session):
        self.session = session

    @abstractmethod
    def collect(self, weather_data: WeatherData) -> None:
        pass

class CurrentDataCollector(BaseDataCollector):
    def __init__(self, session: requests.Session, base_url: str, params: dict):
        super().__init__(session)
        self.base_url = base_url
        self.default_params = params

    def collect(self, weather_data: WeatherData) -> None:
        """Sammelt aktuelle und historische Messwerte"""
        for position in range(1, 73):  # 72 Stunden Historie
            params = self.default_params.copy()
            params["sp"] = str(position)
            
            try:
                response = self.session.post(self.base_url, data=params)
                response.raise_for_status()
                self._parse_measurements(response.text, weather_data)
                time.sleep(1)  # Höflichkeitspause
            except Exception as e:
                logging.error(f"Fehler bei Position {position}: {e}")

    def _parse_measurements(self, html: str, weather_data: WeatherData) -> None:
        """Parsed die Messwerte aus der HTML-Antwort"""
        soup = BeautifulSoup(html, 'html.parser')
        timestamps = self._extract_timestamps(soup)
        
        for row in soup.find_all('tr', style='background-color:#EAEAEA'):
            param_cell = row.find('td', style=lambda x: x and 'text-align:left' in x)
            if not param_cell:
                continue

            param_name = param_cell.text.strip()
            if not param_name or 'geändert' in param_name.lower():
                continue

            for i, cell in enumerate(row.find_all('td', class_='view')):
                if i >= len(timestamps):
                    break
                    
                val_div = cell.find('div', class_='val')
                unit_div = cell.find('div', class_='unit')
                
                if val_div:
                    try:
                        value = float(val_div.text.strip().replace(',', '.'))
                        unit = unit_div.text.strip() if unit_div else ""
                        
                        measurement = WeatherMeasurement(
                            timestamp=timestamps[i],
                            value=value,
                            unit=unit,
                            parameter_type=param_name
                        )
                        weather_data.add_measurement(measurement)
                    except (ValueError, TypeError):
                        continue

    def _extract_timestamps(self, soup: BeautifulSoup) -> List[str]:
        """Extrahiert die Zeitstempel aus der Tabelle"""
        timestamps = []
        for th in soup.find_all('td', style=lambda x: x and 'background-color:#EEFFFF' in x):
            text = th.text.strip()
            if text and 'Uhr' in text:
                date = text.split('\n')[-1].strip()
                day, month = date.split(',')[1].strip().split('.')[:2]
                hour = date.split('Uhr')[0].strip()
                timestamps.append(f"{day}.02.2025 - {hour} Uhr")
        return timestamps

class ForecastDataCollector(BaseDataCollector):
    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.forecast_url = "https://dlr-web-daten1.aspdienste.de/cgi-bin/wetterprog_meteo.pl"
        self.chart_url = "https://dlr-web-daten1.aspdienste.de/cgi-bin/wfma/wfma_client.pl"

    def collect(self, weather_data: WeatherData) -> None:
        """Sammelt Vorhersagedaten und Charts"""
        self._collect_forecasts(weather_data)
        self._collect_charts(weather_data)

    def _collect_forecasts(self, weather_data: WeatherData) -> None:
        """Sammelt detaillierte Wettervorhersagen"""
        params = {
            "c": "02",
            "sid": "161",
            "tid": "1,2,46,44,99,3,4,25,26,5,99,7,6,8,29,31,99,9,10,11,12,13,99,14,99,24,47",
            "d": "6"
        }
        
        try:
            response = self.session.get(self.forecast_url, params=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for table in soup.find_all('table', class_=['vorhersage', 'forecast']):
                forecast = self._parse_forecast_table(table)
                if forecast:
                    weather_data.add_forecast('daily', forecast)
                    
        except Exception as e:
            logging.error(f"Fehler beim Abrufen der Vorhersage: {e}")

    def _parse_forecast_table(self, table) -> Optional[WeatherForecast]:
        """Parsed eine einzelne Vorhersage-Tabelle"""
        data = {
            "date": None,
            "temperatures": {},
            "humidity": None,
            "precipitation": {},
            "wind": {},
            "conditions": None
        }
        
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
                
            key = cells[0].text.strip().lower()
            value = cells[1].text.strip()
            
            if "datum" in key:
                data["date"] = value
            elif "temperatur" in key:
                if "max" in key:
                    data["temperatures"]["max"] = self._extract_number(value)
                elif "min" in key:
                    data["temperatures"]["min"] = self._extract_number(value)
            elif "niederschlag" in key:
                data["precipitation"][key] = value
            elif "wind" in key:
                data["wind"][key] = value
            elif "wetter" in key:
                data["conditions"] = value
                
        if data["date"]:  # Nur vollständige Vorhersagen zurückgeben
            return WeatherForecast(**data)
        return None

    def _collect_charts(self, weather_data: WeatherData) -> None:
        """Sammelt Diagramm-URLs"""
        params = {
            "cid": "02",
            "sid": "161",
            "days": "4"
        }
        
        try:
            response = self.session.get(self.chart_url, params=params)
            if response.status_code == 200:
                weather_data.station_charts["temperature_history"] = response.url
        except Exception as e:
            logging.error(f"Fehler beim Abrufen der Charts: {e}")

    def _extract_number(self, text: str) -> Optional[float]:
        """Extrahiert Zahlenwerte aus Text"""
        try:
            return float(re.search(r'-?\d+(?:,\d+)?', text.replace(',', '.')).group())
        except (AttributeError, ValueError):
            return None

class WeatherStation:
    def __init__(self, config: dict):
        self.config = config
        self.session = self._setup_session()
        self.weather_data = WeatherData("Diefenbach", "161")
        self.collectors = self._setup_collectors()

    def _setup_session(self) -> requests.Session:
        """Initialisiert die Session"""
        session = requests.Session()
        session.verify = False
        session.proxies.clear()
        os.environ['NO_PROXY'] = '*'
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
        })
        return session

    def _setup_collectors(self) -> List[BaseDataCollector]:
        """Initialisiert die Datensammler"""
        return [
            CurrentDataCollector(self.session, self.config["base_url"], self.config["default_params"]),
            ForecastDataCollector(self.session)
        ]

    def update(self) -> bool:
        """Aktualisiert alle Wetterdaten"""
        try:
            for collector in self.collectors:
                collector.collect(self.weather_data)
            
            self.weather_data.last_updated = datetime.now().strftime("%d.%m.%Y - %H:%M")
            
            with open(self.config["output_file"], 'w', encoding='utf-8') as f:
                json.dump(self.weather_data.to_json(), f, ensure_ascii=False, indent=2)
            
            logging.info(f"Daten erfolgreich aktualisiert ({self.weather_data.last_updated})")
            return True
            
        except Exception as e:
            logging.error(f"Fehler beim Update: {e}")
            return False

    def run(self):
        """Hauptschleife"""
        logging.info("Starte Wetterstation-Monitor...")
        while True:
            try:
                self.update()
                time.sleep(self.config["check_interval"])
            except Exception as e:
                logging.error(f"Fehler in der Hauptschleife: {e}")
                time.sleep(60)

def main():
    config = {
        "base_url": "https://dlr-web-daten1.aspdienste.de/cgi-bin/wetterakt.pl",
        "check_interval": 300,  # 5 Minuten
        "output_file": "weather_data.json",
        "default_params": {
            "c": "02",
            "sid": "161",
            "tid": "1,4,99,5,99,10,11,99,15,16,99,18,21",
            "ts": "8"
        }
    }
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('weather_station.log'),
            logging.StreamHandler()
        ]
    )
    
    station = WeatherStation(config)
    station.run()

if __name__ == "__main__":
    main()