from datetime import date, datetime, time, timedelta
from typing import Any

import requests
from waste_collection_schedule import Collection, Icons  # type: ignore[attr-defined]
from waste_collection_schedule.exceptions import (
    SourceArgAmbiguousWithSuggestions,
    SourceArgumentNotFound,
    SourceArgumentNotFoundWithSuggestions,
    SourceArgumentRequiredWithSuggestions,
)

TITLE = "Municipium"
DESCRIPTION = "Source for some Italian municipalities using the Municipium app platform. Uses the API called by the app, which is public but not documented."
URL = "https://www.municipiumapp.it/"
COUNTRY = "it"

SOURCE_CODEOWNERS = ["@edo2313"]

TEST_CASES = {
    "Bussolengo - Zona A": {
        "municipality": "Bussolengo",
        "zone": "Utenza Pubblica - Zona A",
    },
    "Bussolengo Zona B with province": {
        "municipality": "Bussolengo",
        "province": "VR",
        "zone": "Zona B",
    },
    "Valdisotto (single calendar, auto zone)": {
        "municipality": "Valdisotto",
    },
}

ICON_MAP = {
    "umido": Icons.BIO_KITCHEN,
    "organico": Icons.BIO_KITCHEN,
    "carta": Icons.PAPER,
    "cartone": Icons.PAPER,
    "plastica": Icons.PLASTIC_PACKAGING,
    "lattine": Icons.PLASTIC_PACKAGING,
    "vetro": Icons.GLASS,
    "secco": Icons.GENERAL_WASTE,
    "indifferenziat": Icons.GENERAL_WASTE,
    "verde": Icons.GARDEN,
    "ingombrant": Icons.BULKY,
}

HOW_TO_GET_ARGUMENTS_DESCRIPTION = {
    "en": "Enter the name of your municipality as it appears in the Municipium app. "
    "If several municipalities share the same name, also set `province` (name or two-letter code). "
    "If your municipality has more than one collection calendar, leave `zone` empty on the first "
    "attempt: the error message will list the available calendars to choose from.",
    "it": "Inserisci il nome del tuo comune come appare nell'app Municipium. "
    "Se più comuni hanno lo stesso nome, imposta anche `province` (nome o sigla). "
    "Se il tuo comune ha più di un calendario di raccolta, lascia `zone` vuoto al primo "
    "tentativo: il messaggio di errore elencherà i calendari disponibili tra cui scegliere.",
}

PARAM_TRANSLATIONS = {
    "en": {
        "municipality": "Municipality",
        "province": "Province (optional)",
        "zone": "Zone / calendar (optional)",
    },
    "it": {
        "municipality": "Comune",
        "province": "Provincia (opzionale)",
        "zone": "Zona / calendario (opzionale)",
    },
}

PARAM_DESCRIPTIONS = {
    "en": {
        "municipality": "Name of the municipality (e.g. Bussolengo).",
        "province": "Province name or two-letter code (e.g. Verona or VR). Only needed to disambiguate municipalities with the same name.",
        "zone": "Name of the collection calendar/zone (e.g. Utenza Pubblica - Zona A). Can be omitted if the municipality has a single calendar.",
    },
    "it": {
        "municipality": "Nome del comune (es. Bussolengo).",
        "province": "Nome o sigla della provincia (es. Verona o VR). Necessaria solo per distinguere comuni con lo stesso nome.",
        "zone": "Nome del calendario/zona di raccolta (es. Utenza Pubblica - Zona A). Può essere omesso se il comune ha un solo calendario.",
    },
}

CLOUD_API_URL = "https://cloud.municipiumapp.it/api/v2"

# The API rejects requests with default python User-Agents (403)
HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- BEGIN MUNICIPALITIES (auto-generated) ---
# Municipalities that publish at least one waste collection calendar on Municipium.
# Regenerate with: python custom_components/waste_collection_schedule/waste_collection_schedule/wizard/municipiumapp_it.py
MUNICIPALITIES: list[str] = []
# --- END MUNICIPALITIES ---


def EXTRA_INFO():
    return [
        {"title": m, "country": "it", "default_params": {"municipality": m}}
        for m in MUNICIPALITIES
    ]


class Source:
    def __init__(
        self,
        municipality: str,
        province: str | None = None,
        zone: str | None = None,
    ):
        self._municipality = municipality.strip()
        self._province = province.strip() if province else None
        self._zone = zone.strip() if zone else None
        self._subdomain: str | None = None
        self._calendar_id: int | None = None

    def _get(self, url: str, **kwargs: Any) -> Any:
        response = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def _resolve_municipality(self) -> int:
        municipalities = self._get(f"{CLOUD_API_URL}/municipalities")

        matches = [
            m
            for m in municipalities
            if m["name"].casefold() == self._municipality.casefold()
        ]
        if self._province:
            province = self._province.casefold()
            matches = [
                m
                for m in matches
                if province
                in (
                    (m.get("province_name") or "").casefold(),
                    (m.get("province_initials") or "").casefold(),
                )
            ]

        if not matches:
            similar = [
                f"{m['name']} ({m.get('province_initials') or m.get('province_name')})"
                for m in municipalities
                if self._municipality.casefold() in m["name"].casefold()
            ]
            raise SourceArgumentNotFoundWithSuggestions(
                "municipality",
                self._municipality,
                similar,
            )
        if len(matches) > 1:
            provinces = [
                f"{m.get('province_name')} ({m.get('province_initials')})"
                for m in matches
            ]
            if self._province is None:
                raise SourceArgumentRequiredWithSuggestions(
                    "province",
                    "Multiple municipalities share this name.",
                    provinces,
                )
            raise SourceArgAmbiguousWithSuggestions(
                "province",
                self._province,
                provinces,
            )
        return matches[0]["id"]

    def _resolve_subdomain(self, municipality_id: int) -> str:
        details = self._get(
            f"{CLOUD_API_URL}/municipalities/show_mobile/{municipality_id}"
        )
        if not details.get("enable_garbage_calendar"):
            raise SourceArgumentNotFound(
                "municipality",
                self._municipality,
                "This municipality does not publish a waste collection calendar on Municipium.",
            )
        return details["subdomain"]

    def _resolve_calendar_id(self, subdomain: str) -> int:
        calendars = self._get(f"https://{subdomain}/api/v2/calendars")
        if not calendars:
            raise SourceArgumentNotFound(
                "municipality",
                self._municipality,
                "This municipality does not publish any waste collection calendar on Municipium.",
            )

        calendar_names = [c["name"].strip() for c in calendars]

        if self._zone is None:
            if len(calendars) == 1:
                return calendars[0]["id"]
            raise SourceArgumentRequiredWithSuggestions(
                "zone",
                "The municipality has multiple collection calendars.",
                calendar_names,
            )

        zone = self._zone.casefold()
        matches = [c for c in calendars if c["name"].strip().casefold() == zone]
        if not matches:
            matches = [c for c in calendars if zone in c["name"].casefold()]

        if not matches:
            raise SourceArgumentNotFoundWithSuggestions(
                "zone",
                self._zone,
                calendar_names,
            )
        if len(matches) > 1:
            raise SourceArgAmbiguousWithSuggestions(
                "zone",
                self._zone,
                [c["name"].strip() for c in matches],
            )
        return matches[0]["id"]

    def _resolve(self) -> None:
        municipality_id = self._resolve_municipality()
        self._subdomain = self._resolve_subdomain(municipality_id)
        self._calendar_id = self._resolve_calendar_id(self._subdomain)

    def fetch(self) -> list[Collection]:
        if self._calendar_id is None or self._subdomain is None:
            self._resolve()

        start = datetime.combine(date.today(), time.min)
        end = start + timedelta(days=365)
        events = self._get(
            f"https://{self._subdomain}/api/v2/calendars/{self._calendar_id}",
            params={"start": int(start.timestamp()), "end": int(end.timestamp())},
        )

        entries = []
        for event in events:
            waste_type = event["title"].strip()
            icon = None
            for keyword, icon_candidate in ICON_MAP.items():
                if keyword in waste_type.casefold():
                    icon = icon_candidate
                    break
            entries.append(
                Collection(
                    date=date.fromisoformat(event["start"][:10]),
                    t=waste_type,
                    icon=icon,
                )
            )
        return entries
