"""
CULTURA Tool Schemas & Pydantic V2 Domain Models.
Defines foundational schemas for CulturalDomain, TimeSlot, TasteSeed,
CulturalEntity, AffinityScore, ItineraryItem, and ItineraryPlan, enforcing the
48-hour 8-slot schedule invariant and multi-domain diversity.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# 1. Enums
# ============================================================================

class CulturalDomain(str, Enum):
    """The 7 cultural domains recognized by CULTURA."""
    MUSIC = "music"
    DINING = "dining"
    ARTS = "arts"
    CINEMA = "cinema"
    NIGHTLIFE = "nightlife"
    LITERARY = "literary"
    FASHION = "fashion"

    @classmethod
    def normalize(cls, v: Union["CulturalDomain", str]) -> "CulturalDomain":
        """Normalizes common domain synonyms and user input strings to canonical enum."""
        if isinstance(v, cls):
            return v
        aliases: Dict[str, str] = {
            "music": "music",
            "audio": "music",
            "concert": "music",
            "film": "cinema",
            "films": "cinema",
            "movies": "cinema",
            "movie": "cinema",
            "cinema": "cinema",
            "dining": "dining",
            "food": "dining",
            "restaurant": "dining",
            "restaurants": "dining",
            "eats": "dining",
            "eat": "dining",
            "culinary": "dining",
            "arts": "arts",
            "art": "arts",
            "museum": "arts",
            "museums": "arts",
            "gallery": "arts",
            "galleries": "arts",
            "literary": "literary",
            "books": "literary",
            "book": "literary",
            "literature": "literary",
            "reading": "literary",
            "nightlife": "nightlife",
            "bars": "nightlife",
            "bar": "nightlife",
            "drinks": "nightlife",
            "cocktails": "nightlife",
            "pub": "nightlife",
            "clubs": "nightlife",
            "club": "nightlife",
            "fashion": "fashion",
            "style": "fashion",
            "design": "fashion",
            "shopping": "fashion",
            "apparel": "fashion",
        }
        clean = str(v).strip().lower()
        canonical = aliases.get(clean, clean)
        try:
            return cls(canonical)
        except ValueError:
            valid_domains = [d.value for d in cls]
            raise ValueError(
                f"Invalid cultural domain '{v}'. Supported domains: {', '.join(valid_domains)}"
            )


class TimeSlot(str, Enum):
    """The 4 diurnal time slots for each 24-hour cycle of an itinerary."""
    MORNING = "morning"       # 09:00 - 12:30
    AFTERNOON = "afternoon"   # 13:00 - 16:30
    EVENING = "evening"       # 17:00 - 20:30
    NIGHT = "night"           # 21:00 - 00:30

    @property
    def default_time_window(self) -> str:
        """Standard diurnal operating time window for this slot."""
        windows = {
            TimeSlot.MORNING: "09:00 - 12:30",
            TimeSlot.AFTERNOON: "13:00 - 16:30",
            TimeSlot.EVENING: "17:00 - 20:30",
            TimeSlot.NIGHT: "21:00 - 00:30",
        }
        return windows[self]


# ============================================================================
# 2. Core Cultural Domain Models
# ============================================================================

class TasteSeed(BaseModel):
    """User-supplied cultural preference or aesthetic anchor."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of artist, cuisine, vibe, venue, or concept (e.g. 'Coltrane', 'Brutalism')",
    )
    domain: CulturalDomain = Field(
        ...,
        description="Cultural domain category of the taste seed",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Relative preference weight [0.0 - 2.0]",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional user context, notes, or specific taste nuances",
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional aesthetic tags or stylistic markers",
    )

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Taste seed name cannot be blank or whitespace only")
        return s

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: Any) -> CulturalDomain:
        return CulturalDomain.normalize(v)


class CulturalEntity(BaseModel):
    """Authentic cultural venue, creator, or landmark situated in a cultural hub."""
    id: str = Field(
        ...,
        min_length=1,
        description="Unique deterministic identifier (e.g. 'ent_blr_din_001')",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Official venue or entity name",
    )
    domain: CulturalDomain = Field(
        ...,
        description="Primary cultural domain",
    )
    hub: str = Field(
        ...,
        min_length=1,
        description="Cultural hub name (e.g. 'Bangalore', 'Tokyo', 'New York')",
    )
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS84 latitude coordinate",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS84 longitude coordinate",
    )
    vibe_tags: List[str] = Field(
        default_factory=list,
        description="Curated aesthetic, stylistic, and genre tags",
    )
    price_tier: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Relative cost tier: 1 ($), 2 ($$), 3 ($$$), 4 ($$$$)",
    )
    description: str = Field(
        default="",
        description="Editorial curator description of the venue and atmosphere",
    )
    city: Optional[str] = Field(
        default=None,
        description="City name",
    )
    country: Optional[str] = Field(
        default=None,
        description="Country name",
    )
    neighborhood: Optional[str] = Field(
        default=None,
        description="Neighborhood or district name",
    )
    address: Optional[str] = Field(
        default=None,
        description="Physical street address",
    )
    category: Optional[str] = Field(
        default=None,
        description="Specific sub-genre or category",
    )
    curator_note: Optional[str] = Field(
        default=None,
        description="Insider curator tip or cultural context",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extended attributes",
    )

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: Any) -> CulturalDomain:
        return CulturalDomain.normalize(v)

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        """Reconciles synonyms across catalog and external inputs."""
        if isinstance(data, dict):
            # Coordinate aliases
            if "lat" in data and "latitude" not in data:
                data["latitude"] = data["lat"]
            if "lon" in data and "longitude" not in data:
                data["longitude"] = data["lon"]
            elif "lng" in data and "longitude" not in data:
                data["longitude"] = data["lng"]

            # Tag aliases
            if "tags" in data and not data.get("vibe_tags"):
                data["vibe_tags"] = data["tags"]

            # Description aliases
            if "vibe" in data and not data.get("description"):
                data["description"] = data["vibe"]

            # Hub/City aliases
            if "city" in data and not data.get("hub"):
                data["hub"] = data["city"]
        return data

    @property
    def tags(self) -> List[str]:
        """Convenience property alias for vibe_tags."""
        return self.vibe_tags

    @property
    def lat(self) -> float:
        """Convenience property alias for latitude."""
        return self.latitude

    @property
    def lon(self) -> float:
        """Convenience property alias for longitude."""
        return self.longitude


class AffinityScore(BaseModel):
    """Quantified cultural resonance between a source entity/seed and a candidate venue."""
    entity_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of source entity or taste anchor",
    )
    target_entity: CulturalEntity = Field(
        ...,
        description="Resolved candidate cultural entity",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized taste affinity score [0.0 - 1.0]",
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Statistical confidence metric [0.0 - 1.0]",
    )
    rationale: str = Field(
        ...,
        min_length=1,
        description="Explainable AI cultural rationale connecting source and target",
    )
    shared_tags: List[str] = Field(
        default_factory=list,
        description="Overlapping cultural and aesthetic tags",
    )
    target_domain: Optional[CulturalDomain] = Field(
        default=None,
        description="Target domain of the affinity recommendation",
    )
    taste_cluster: Optional[str] = Field(
        default=None,
        description="Identified aesthetic cluster (e.g. 'Avant-Garde Modernism')",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "source_entity_id" in data and "entity_id" not in data:
                data["entity_id"] = data["source_entity_id"]
            if "source_seed" in data and "entity_id" not in data:
                data["entity_id"] = data["source_seed"]
            if "reasoning" in data and "rationale" not in data:
                data["rationale"] = data["reasoning"]
            if "taste_overlap_tags" in data and "shared_tags" not in data:
                data["shared_tags"] = data["taste_overlap_tags"]
        return data

    @model_validator(mode="after")
    def set_target_domain(self) -> "AffinityScore":
        if self.target_domain is None and self.target_entity:
            self.target_domain = self.target_entity.domain
        return self

    @property
    def source_entity_id(self) -> str:
        """Alias for entity_id."""
        return self.entity_id

    @property
    def reasoning(self) -> str:
        """Alias for rationale."""
        return self.rationale


# ============================================================================
# 3. Schedule & Itinerary Models
# ============================================================================

class ItineraryItem(BaseModel):
    """An individual scheduled cultural block in the 48-hour itinerary."""
    day: int = Field(
        ...,
        ge=1,
        le=2,
        description="Day of itinerary: 1 or 2",
    )
    slot: TimeSlot = Field(
        ...,
        description="Diurnal time slot: morning, afternoon, evening, night",
    )
    time_window: str = Field(
        default="",
        description="Scheduled time window, e.g. '09:00 - 12:30'",
    )
    entity: CulturalEntity = Field(
        ...,
        description="Selected cultural entity/venue",
    )
    affinity_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Match score to user taste profile [0.0 - 1.0]",
    )
    curator_notes: str = Field(
        default="",
        description="Contextual explanation and curator tips for the visit",
    )
    transit_from_previous_min: int = Field(
        default=0,
        ge=0,
        description="Transit travel time from prior venue in minutes",
    )
    transit_note: Optional[str] = Field(
        default=None,
        description="Transit guidance or route suggestion",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "day_number" in data and "day" not in data:
                data["day"] = data["day_number"]
            if "time_slot" in data and "slot" not in data:
                data["slot"] = data["time_slot"]
            if "rationale" in data and not data.get("curator_notes"):
                data["curator_notes"] = data["rationale"]
            if "curator_tip" in data and not data.get("curator_notes"):
                data["curator_notes"] = data["curator_tip"]
            if "transit_notes" in data and not data.get("transit_note"):
                data["transit_note"] = data["transit_notes"]
        return data

    @model_validator(mode="after")
    def populate_defaults(self) -> "ItineraryItem":
        if not self.time_window:
            self.time_window = self.slot.default_time_window
        return self

    @property
    def curator_tip(self) -> str:
        return self.curator_notes

    @property
    def start_time(self) -> str:
        return self.time_window.split(" - ")[0] if " - " in self.time_window else ""

    @property
    def end_time(self) -> str:
        return self.time_window.split(" - ")[1] if " - " in self.time_window else ""


class ItineraryPlan(BaseModel):
    """
    Complete synthesized 48-hour cultural itinerary.
    Strictly enforces the 48-Hour 8-Slot Schedule Invariant:
    - Exactly 8 items (Day 1: 4 slots, Day 2: 4 slots)
    - Zero duplicate venues across the plan
    - Proper chronological sequence
    """
    city_hub: str = Field(
        ...,
        min_length=1,
        description="Destination cultural hub (e.g. 'Bangalore')",
    )
    taste_seeds: List[TasteSeed] = Field(
        ...,
        min_length=1,
        description="User taste seeds driving the plan",
    )
    items: List[ItineraryItem] = Field(
        ...,
        min_length=8,
        max_length=8,
        description="Chronological schedule of cultural items (exactly 8)",
    )
    cultural_coherence_score: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Overall cultural taste graph synergy rating [0.0 - 1.0]",
    )
    domain_diversity_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Cross-domain entropy score [0.0 - 1.0]",
    )
    transit_efficiency_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Spatial transit efficiency score [0.0 - 1.0]",
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC creation timestamp string",
    )
    react_steps_count: int = Field(
        default=0,
        ge=0,
        description="Number of ReAct planning iterations executed",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Executive narrative summary of the curated 48-hour journey",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional itinerary metadata",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "city" in data and "city_hub" not in data:
                data["city_hub"] = data["city"]
            elif "hub" in data and "city_hub" not in data:
                data["city_hub"] = data["hub"]
            if "user_seeds" in data and "taste_seeds" not in data:
                data["taste_seeds"] = data["user_seeds"]
            elif "seeds" in data and "taste_seeds" not in data:
                data["taste_seeds"] = data["seeds"]
            if "coherence_score" in data and "cultural_coherence_score" not in data:
                data["cultural_coherence_score"] = data["coherence_score"]
            if "diversity_score" in data and "domain_diversity_score" not in data:
                data["domain_diversity_score"] = data["diversity_score"]
        return data

    @model_validator(mode="after")
    def validate_schedule_invariant(self) -> "ItineraryPlan":
        """
        Enforces Feature 6 Schedule Invariant:
        1. Exactly 8 items across 2 days.
        2. Sequence: Day 1 (Morning, Afternoon, Evening, Night) -> Day 2 (Morning, Afternoon, Evening, Night).
        3. Zero duplicate venue IDs.
        4. Cross-domain diversity check (at least 3 unique domains).
        """
        if len(self.items) != 8:
            raise ValueError(
                f"ItineraryPlan must contain exactly 8 items (4 per day for 2 days), got {len(self.items)}"
            )

        expected_sequence = [
            (1, TimeSlot.MORNING),
            (1, TimeSlot.AFTERNOON),
            (1, TimeSlot.EVENING),
            (1, TimeSlot.NIGHT),
            (2, TimeSlot.MORNING),
            (2, TimeSlot.AFTERNOON),
            (2, TimeSlot.EVENING),
            (2, TimeSlot.NIGHT),
        ]
        actual_sequence = [(item.day, item.slot) for item in self.items]
        if actual_sequence != expected_sequence:
            raise ValueError(
                f"Invalid itinerary schedule sequence: expected {expected_sequence}, got {actual_sequence}"
            )

        # Zero duplicate venues
        entity_ids = [item.entity.id for item in self.items]
        if len(set(entity_ids)) != 8:
            duplicates = [eid for eid in entity_ids if entity_ids.count(eid) > 1]
            raise ValueError(
                f"Duplicate cultural entities detected in itinerary: {set(duplicates)}. "
                f"Every slot must feature a unique venue."
            )

        # Domain diversity invariant
        unique_domains = {item.entity.domain for item in self.items}
        if len(unique_domains) < 3:
            raise ValueError(
                f"Itinerary lacks cultural breadth: found only {len(unique_domains)} unique domain(s) ({unique_domains}). "
                f"A culturally coherent 48-hour plan must span at least 3 distinct domains."
            )

        return self

    @property
    def city(self) -> str:
        return self.city_hub

    @property
    def coherence_score(self) -> float:
        return self.cultural_coherence_score


# ============================================================================
# 4. Agentic ReAct Tool Input Schemas & Spatial Helpers
# ============================================================================

class SearchEntitiesInput(BaseModel):
    """Tool input arguments for search_entities."""
    query: str = Field(..., description="Search query string (name, tag, or aesthetic)")
    domain: Optional[CulturalDomain] = Field(default=None, description="Optional domain filter")
    hub: Optional[str] = Field(default=None, description="Optional cultural hub filter")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum items to return")

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: Any) -> Optional[CulturalDomain]:
        return CulturalDomain.normalize(v) if v else None


class GetCrossDomainAffinitiesInput(BaseModel):
    """Tool input arguments for get_cross_domain_affinities."""
    entity_id: str = Field(..., description="Source entity ID to find affinities from")
    target_domain: CulturalDomain = Field(..., description="Target domain to find matches in")
    hub: Optional[str] = Field(default=None, description="Target destination hub filter")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum recommendations to return")

    @field_validator("target_domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: Any) -> CulturalDomain:
        return CulturalDomain.normalize(v)


class GetEntityInput(BaseModel):
    """Tool input arguments for get_entity."""
    entity_id: str = Field(..., description="Unique entity identifier to look up")


class GetHubEntitiesInput(BaseModel):
    """Tool input arguments for get_hub_entities."""
    hub: str = Field(..., description="Cultural hub name (e.g. 'Bangalore', 'Tokyo')")
    domain: Optional[CulturalDomain] = Field(default=None, description="Optional domain filter")

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: Any) -> Optional[CulturalDomain]:
        return CulturalDomain.normalize(v) if v else None


class TransitEvaluationInput(BaseModel):
    """Tool input arguments for transit time evaluation."""
    from_latitude: float = Field(..., ge=-90.0, le=90.0)
    from_longitude: float = Field(..., ge=-180.0, le=180.0)
    to_latitude: float = Field(..., ge=-90.0, le=90.0)
    to_longitude: float = Field(..., ge=-180.0, le=180.0)
    speed_kmh: float = Field(default=25.0, ge=5.0, le=100.0, description="Average urban travel speed (km/h)")


def haversine_transit_minutes(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    speed_kmh: float = 25.0,
) -> int:
    """
    Computes accurate urban transit time in minutes between two WGS84 coordinates using
    the Haversine formula with a minimum dwell/transit baseline of 5 minutes.
    """
    R = 6371.0  # Earth's mean radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    dist_km = R * c

    minutes = int(math.ceil((dist_km / speed_kmh) * 60.0))
    return max(5, minutes)
