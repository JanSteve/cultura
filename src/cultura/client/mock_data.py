"""
CULTURA Offline Mock Catalog & Deterministic Affinity Engine.
Defines 82 authentic cultural venues across 8 hubs (Bangalore, Mumbai, New York,
London, Tokyo, Paris, Berlin, San Francisco) spanning 7 cultural domains.
Provides pre-indexed O(1) in-memory lookups and a deterministic taste graph
scoring engine combining domain compatibility, Jaccard tag similarity,
price disparity penalty, spatial proximity, and cryptographic hash jitter.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from cultura.agent.tools import (
    AffinityScore,
    CulturalDomain,
    CulturalEntity,
)


# ============================================================================
# 1. Cultural Hubs & Metadata
# ============================================================================

CULTURAL_HUBS: List[str] = [
    "Bangalore",
    "Mumbai",
    "New York",
    "London",
    "Tokyo",
    "Paris",
    "Berlin",
    "San Francisco",
]

SUPPORTED_HUBS: Set[str] = set(CULTURAL_HUBS)

CULTURAL_DOMAINS: List[str] = [
    "music",
    "dining",
    "arts",
    "cinema",
    "nightlife",
    "literary",
    "fashion",
]

HUB_METADATA: Dict[str, Dict[str, Any]] = {
    "Bangalore": {
        "city": "Bengaluru",
        "country": "India",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "timezone": "Asia/Kolkata",
        "currency": "INR",
        "description": "India's garden city and tech capital; an epicenter of South Indian culinary heritage, craft microbreweries, indie rock, and emerging contemporary art.",
    },
    "Mumbai": {
        "city": "Mumbai",
        "country": "India",
        "latitude": 18.9220,
        "longitude": 72.8347,
        "timezone": "Asia/Kolkata",
        "currency": "INR",
        "description": "The maximum city on the Arabian Sea; home to Art Deco architectural treasures, historic Parsi institutions, classical Indian performing arts, and Bollywood legacy.",
    },
    "New York": {
        "city": "New York",
        "country": "United States",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timezone": "America/New_York",
        "currency": "USD",
        "description": "Global cultural nexus celebrated for historic Greenwich Village jazz, Lower East Side indie venues, monumental museums, and 35mm repertory cinema.",
    },
    "London": {
        "city": "London",
        "country": "United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "timezone": "Europe/London",
        "currency": "GBP",
        "description": "Historic cultural metropolis spanning Soho jazz basements, Farringdon nose-to-tail gastronomy, brutalist arts powerhouses, and East London avant-garde fashion.",
    },
    "Tokyo": {
        "city": "Tokyo",
        "country": "Japan",
        "latitude": 35.6762,
        "longitude": 139.6503,
        "timezone": "Asia/Tokyo",
        "currency": "JPY",
        "description": "Hyper-modern sensory metropolis balancing tranquil Showa-era jazz kissas, smoky izakaya alleys, cutting-edge Tadao Ando design, and botanical cocktail alchemy.",
    },
    "Paris": {
        "city": "Paris",
        "country": "France",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "timezone": "Europe/Paris",
        "currency": "EUR",
        "description": "The City of Light; birthplace of the Nouvelle Vague, pioneering natural-wine neo-bistros, Latin Quarter literary salons, and world-leading modern art institutions.",
    },
    "Berlin": {
        "city": "Berlin",
        "country": "Germany",
        "latitude": 52.5200,
        "longitude": 13.4050,
        "timezone": "Europe/Berlin",
        "currency": "EUR",
        "description": "Counter-cultural European capital famed for monolithic industrial techno temples, converted WWII bunker art galleries, radically local dining, and silent cinema organ palaces.",
    },
    "San Francisco": {
        "city": "San Francisco",
        "country": "United States",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "timezone": "America/Los_Angeles",
        "currency": "USD",
        "description": "Bay Area cultural crucible uniting Beat generation literary rebellion, 1960s psychedelic rock halls, California farm-to-table culinary purity, and historic indie film houses.",
    },
}

HUB_ALIASES: Dict[str, str] = {
    "blr": "Bangalore",
    "bengaluru": "Bangalore",
    "bangalore": "Bangalore",
    "bom": "Mumbai",
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    "nyc": "New York",
    "new york city": "New York",
    "new york": "New York",
    "manhattan": "New York",
    "ldn": "London",
    "london": "London",
    "tyo": "Tokyo",
    "tokyo": "Tokyo",
    "par": "Paris",
    "paris": "Paris",
    "ber": "Berlin",
    "berlin": "Berlin",
    "sfo": "San Francisco",
    "sf": "San Francisco",
    "san francisco": "San Francisco",
}

DOMAIN_ALIASES: Dict[str, str] = {
    "music": "music",
    "audio": "music",
    "concert": "music",
    "dining": "dining",
    "food": "dining",
    "restaurant": "dining",
    "restaurants": "dining",
    "eat": "dining",
    "eats": "dining",
    "culinary": "dining",
    "arts": "arts",
    "art": "arts",
    "museum": "arts",
    "museums": "arts",
    "gallery": "arts",
    "galleries": "arts",
    "cinema": "cinema",
    "film": "cinema",
    "films": "cinema",
    "movies": "cinema",
    "movie": "cinema",
    "nightlife": "nightlife",
    "bars": "nightlife",
    "bar": "nightlife",
    "drinks": "nightlife",
    "cocktails": "nightlife",
    "pub": "nightlife",
    "clubs": "nightlife",
    "club": "nightlife",
    "literary": "literary",
    "books": "literary",
    "book": "literary",
    "literature": "literary",
    "reading": "literary",
    "fashion": "fashion",
    "style": "fashion",
    "design": "fashion",
    "shopping": "fashion",
    "apparel": "fashion",
}


# ============================================================================
# 2. Complete 82-Entity Authentic Mock Catalog
# ============================================================================

RAW_MOCK_ENTITIES: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------------
    # Bangalore (10 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_blr_din_001",
        "name": "Vidyarthi Bhavan",
        "domain": "dining",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Gandhi Bazaar, Basavanagudi",
        "category": "Heritage South Indian Tiffin",
        "latitude": 12.9438,
        "longitude": 77.5707,
        "price_tier": 1,
        "vibe_tags": ["heritage", "crisp-dosa", "filter-coffee", "nostalgic", "tiffin", "traditional", "historic"],
        "description": "Bustling 1943 morning breakfast cathedral celebrated for golden ghee-crisped masala dosas and filter coffee.",
    },
    {
        "id": "ent_blr_din_002",
        "name": "Mavalli Tiffin Room (MTR)",
        "domain": "dining",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Lalbagh Road",
        "category": "Heritage Vegetarian Thali",
        "latitude": 12.9554,
        "longitude": 77.5867,
        "price_tier": 2,
        "vibe_tags": ["historic-1924", "silver-thali", "rava-idli", "culinary-tradition", "pure-vegetarian"],
        "description": "Legendary culinary pilgrimage birthplace of the rava idli served in aristocratic silver services.",
    },
    {
        "id": "ent_blr_mus_001",
        "name": "Windmills Craftworks",
        "domain": "music",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Whitefield",
        "category": "Audiophile Jazz & Microbrewery",
        "latitude": 12.9822,
        "longitude": 77.7283,
        "price_tier": 3,
        "vibe_tags": ["audiophile", "jazz", "microbrew", "intimate-stage", "craft-beer", "books"],
        "description": "Acoustically immaculate library-inspired auditorium presenting world-class jazz musicians alongside master craft ales.",
    },
    {
        "id": "ent_blr_mus_002",
        "name": "Fandom at Gilly's Defined",
        "domain": "music",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Koramangala",
        "category": "Live Indie & Electronic Arena",
        "latitude": 12.9345,
        "longitude": 77.6205,
        "price_tier": 2,
        "vibe_tags": ["indie-rock", "live-music", "post-punk", "electronic", "sound-system"],
        "description": "High-energy independent music sanctuary championing homegrown Indian alternative bands and electronic producers.",
    },
    {
        "id": "ent_blr_art_001",
        "name": "National Gallery of Modern Art (NGMA)",
        "domain": "arts",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Palace Road, Vasanth Nagar",
        "category": "Modern Indian Masterpieces",
        "latitude": 12.9902,
        "longitude": 77.5886,
        "price_tier": 1,
        "vibe_tags": ["modern-art", "sculpture-garden", "colonial-manor", "amrita-sher-gil", "peaceful", "parallel-cinema"],
        "description": "Serene heritage mansion and reflecting pond housing seminal modern Indian artworks amidst century-old trees.",
    },
    {
        "id": "ent_blr_art_002",
        "name": "Bangalore International Centre (BIC)",
        "domain": "arts",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Domlur",
        "category": "Multidisciplinary Cultural Pavilion",
        "latitude": 12.9648,
        "longitude": 77.6402,
        "price_tier": 1,
        "vibe_tags": ["contemporary", "architecture", "intellectual", "exhibitions", "open-forum"],
        "description": "Award-winning exposed brick architectural pavilion fostering contemporary art retrospectives and cultural dialogues.",
    },
    {
        "id": "ent_blr_cin_001",
        "name": "Suchitra Film Society",
        "domain": "cinema",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Banashankari 2nd Stage",
        "category": "Historic Arthouse & Film Archives",
        "latitude": 12.9234,
        "longitude": 77.5682,
        "price_tier": 1,
        "vibe_tags": ["film-society", "parallel-cinema", "satyajit-ray", "retrospective", "cinephile"],
        "description": "Historic 1971 cinephile society dedicated to parallel cinema, auteur retrospectives, and deep film appreciation.",
    },
    {
        "id": "ent_blr_ngt_001",
        "name": "Pecos Classic Rock Pub",
        "domain": "nightlife",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Rest House Road, Brigade",
        "category": "Retro Rock Institution",
        "latitude": 12.9734,
        "longitude": 77.6074,
        "price_tier": 1,
        "vibe_tags": ["classic-rock", "draught-beer", "vintage-posters", "nostalgia", "unpretentious", "church-street"],
        "description": "Beloved 1989 counter-culture institution papered with retro rock posters, pouring draught stout over 70s vinyl anthems.",
    },
    {
        "id": "ent_blr_lit_001",
        "name": "Blossom Book House",
        "domain": "literary",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Church Street",
        "category": "Antiquarian Book Sanctuary",
        "latitude": 12.9752,
        "longitude": 77.6038,
        "price_tier": 1,
        "vibe_tags": ["second-hand", "rare-editions", "endless-shelves", "church-street", "bibliophile", "nostalgia"],
        "description": "Endless three-story labyrinth of yellowed paperbacks, philosophy treatises, and rare Indian literature.",
    },
    {
        "id": "ent_blr_fas_001",
        "name": "Cinnamon Concept Store",
        "domain": "fashion",
        "hub": "Bangalore",
        "city": "Bengaluru",
        "country": "India",
        "neighborhood": "Ulsoor / Gangadhar Chetty Rd",
        "category": "Artisanal Handloom & Design Pavilion",
        "latitude": 12.9815,
        "longitude": 77.6184,
        "price_tier": 3,
        "vibe_tags": ["artisanal-textiles", "colonial-bungalow", "slow-fashion", "contemporary-craft", "handloom"],
        "description": "Curated lifestyle sanctuary set in a restored 19th-century colonial bungalow showcasing avant-garde Indian handlooms and contemporary craft jewelry.",
    },

    # ------------------------------------------------------------------------
    # Mumbai (11 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_bom_din_001",
        "name": "Britannia & Co. Restaurant",
        "domain": "dining",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Ballard Estate",
        "category": "Heritage Parsi Cafe",
        "latitude": 18.9348,
        "longitude": 72.8398,
        "price_tier": 2,
        "vibe_tags": ["parsi-cuisine", "berry-pulao", "colonial-architecture", "heritage-1923", "nostalgic", "art-deco"],
        "description": "Time-capsule 1923 Renaissance-style dining room famous for aromatic Berry Pulao, caramel custard, and gentle eccentric charm.",
    },
    {
        "id": "ent_bom_din_002",
        "name": "The Bombay Canteen",
        "domain": "dining",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Lower Parel",
        "category": "Modern Regional Indian",
        "latitude": 18.9984,
        "longitude": 72.8306,
        "price_tier": 3,
        "vibe_tags": ["regional-indian", "craft-cocktails", "celebration", "innovative", "tasting-menu", "industrial-basement"],
        "description": "Jovial industrial bungalow reimagining forgotten regional Indian ingredients and indigenous craft spirits.",
    },
    {
        "id": "ent_bom_mus_001",
        "name": "National Centre for the Performing Arts (NCPA)",
        "domain": "music",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Nariman Point",
        "category": "Symphony & Classical Auditorium",
        "latitude": 18.9272,
        "longitude": 72.8208,
        "price_tier": 3,
        "vibe_tags": ["symphony", "indian-classical", "acoustics", "arabian-sea", "prestigious"],
        "description": "Prestigious ocean-facing performing arts complex celebrating Hindustani ragas, Western classical symphonies, and operatic recitals.",
    },
    {
        "id": "ent_bom_mus_002",
        "name": "antiSOCIAL Mumbai",
        "domain": "music",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Lower Parel",
        "category": "Underground Electronic & Warehouse",
        "latitude": 18.9951,
        "longitude": 72.8289,
        "price_tier": 2,
        "vibe_tags": ["underground", "electronic", "indie", "industrial-basement", "sub-bass", "innovative"],
        "description": "Moody subterranean concrete bunker delivering uncompromised cutting-edge electronic beats, modular techno, and live indie riffs.",
    },
    {
        "id": "ent_bom_art_001",
        "name": "Jehangir Art Gallery",
        "domain": "arts",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Kala Ghoda",
        "category": "Iconic Modern & Contemporary Gallery",
        "latitude": 18.9275,
        "longitude": 72.8318,
        "price_tier": 1,
        "vibe_tags": ["kala-ghoda", "indian-modernism", "historic-1952", "art-district", "public-art", "heritage-building"],
        "description": "The beating heart of Mumbai's art precinct since 1952, surrounded by pavement sketch artists and premier gallery halls.",
    },
    {
        "id": "ent_bom_art_002",
        "name": "Chemould Prescott Road",
        "domain": "arts",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Fort",
        "category": "Pioneering Conceptual Contemporary Art",
        "latitude": 18.9372,
        "longitude": 72.8344,
        "price_tier": 2,
        "vibe_tags": ["pioneering", "contemporary-art", "radical", "concept-space", "installations"],
        "description": "Trailblazing gallery championing India's most daring conceptual and political contemporary installations.",
    },
    {
        "id": "ent_bom_cin_001",
        "name": "Regal Cinema",
        "domain": "cinema",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Colaba Causeway",
        "category": "Art Deco Single-Screen Palace",
        "latitude": 18.9248,
        "longitude": 72.8322,
        "price_tier": 1,
        "vibe_tags": ["art-deco", "heritage-1933", "single-screen", "architectural-gem", "nostalgia", "colonial-architecture"],
        "description": "Colossal 1933 Art Deco palace with mirror-lined lobbies and grand mezzanine single-screen cinema heritage.",
    },
    {
        "id": "ent_bom_cin_002",
        "name": "Matterden CNC (Deepak Cinema)",
        "domain": "cinema",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Lower Parel",
        "category": "World Cinema & Arthouse Rep House",
        "latitude": 18.9972,
        "longitude": 72.8290,
        "price_tier": 2,
        "vibe_tags": ["world-cinema", "indie-film", "retrospectives", "arthouse", "classic-screenings"],
        "description": "Revitalized 1926 theater dedicated to European classics, indie retrospectives, and experimental Asian film.",
    },
    {
        "id": "ent_bom_ngt_001",
        "name": "Toto's Garage Pub",
        "domain": "nightlife",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Bandra West",
        "category": "Retro Mechanics & Rock Den",
        "latitude": 19.0601,
        "longitude": 72.8354,
        "price_tier": 2,
        "vibe_tags": ["classic-rock", "quirky", "bandra-spirit", "vw-beetle", "pub"],
        "description": "Beloved Bandra den suspended with mechanics' tools and an overhead VW Beetle serving chilled beers to classic rock tracks.",
    },
    {
        "id": "ent_bom_lit_001",
        "name": "Kitab Khana",
        "domain": "literary",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Fort / Flora Fountain",
        "category": "Heritage Multi-Lingual Book Haven",
        "latitude": 18.9322,
        "longitude": 72.8315,
        "price_tier": 1,
        "vibe_tags": ["heritage-building", "high-ceilings", "indie-bookshop", "vernacular-literature", "cafe", "kala-ghoda"],
        "description": "Housed in a 150-year-old heritage Somaiya Bhavan, featuring towering teak bookshelves, quiet reading nooks, and regional poetry.",
    },
    {
        "id": "ent_bom_fas_001",
        "name": "Le Mill Colaba",
        "domain": "fashion",
        "hub": "Mumbai",
        "city": "Mumbai",
        "country": "India",
        "neighborhood": "Colaba / P.J. Ramchandani Marg",
        "category": "Seaside Luxury Multi-Brand Concept Space",
        "latitude": 18.9214,
        "longitude": 72.8335,
        "price_tier": 4,
        "vibe_tags": ["luxury-concept", "avant-garde", "curated-fashion", "coastal-chic", "minimalist"],
        "description": "Multi-brand concept store set in a high-ceilinged seaside heritage warehouse blending international design pioneers with India's finest contemporary couturiers.",
    },

    # ------------------------------------------------------------------------
    # New York City (10 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_nyc_din_001",
        "name": "Via Carota",
        "domain": "dining",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "West Village",
        "category": "Rustic Italian Trattoria",
        "latitude": 40.7337,
        "longitude": -74.0039,
        "price_tier": 3,
        "vibe_tags": ["rustic-italian", "negroni", "west-village", "produce-driven", "intimate"],
        "description": "Warm, bustling brick-walled trattoria celebrated for pristine green salads, wild boar ragù, and timeless neighborhood elegance.",
    },
    {
        "id": "ent_nyc_din_002",
        "name": "Katz's Delicatessen",
        "domain": "dining",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "Lower East Side",
        "category": "Historic Jewish Pastrami Institution",
        "latitude": 40.7222,
        "longitude": -73.9874,
        "price_tier": 2,
        "vibe_tags": ["pastrami", "jewish-deli", "historic-1888", "ticket-counter", "iconic"],
        "description": "Hand-carved pastrami temple roaring with energy, neon signs, and 130 years of lower Manhattan immigrant soul.",
    },
    {
        "id": "ent_nyc_mus_001",
        "name": "Village Vanguard",
        "domain": "music",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "West Village",
        "category": "Sacred Historic Jazz Basement",
        "latitude": 40.7360,
        "longitude": -74.0016,
        "price_tier": 3,
        "vibe_tags": ["jazz", "sacred-ground", "coltrane", "intimate-basement", "acoustics", "intimate", "west-village", "repertory", "noir", "piano-jazz", "art-deco", "timeless"],
        "description": "The hallowed basement triangular room where Coltrane and Bill Evans cut legendary live albums; pure jazz reverence.",
    },
    {
        "id": "ent_nyc_mus_002",
        "name": "Bowery Ballroom",
        "domain": "music",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "Lower East Side",
        "category": "Premier Indie Rock Ballroom",
        "latitude": 40.7204,
        "longitude": -73.9939,
        "price_tier": 2,
        "vibe_tags": ["indie-rock", "sightlines", "bowery", "acoustic-perfection", "live-venue", "indie"],
        "description": "Acoustically flawless 1929 ballroom with sweeping brass mezzanines; the quintessential indie band rite of passage.",
    },
    {
        "id": "ent_nyc_art_001",
        "name": "The Whitney Museum of American Art",
        "domain": "arts",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "Meatpacking District",
        "category": "Modern & Contemporary American Art",
        "latitude": 40.7396,
        "longitude": -74.0089,
        "price_tier": 3,
        "vibe_tags": ["american-art", "edward-hopper", "renzo-piano", "hudson-views", "biennial", "modern-art"],
        "description": "Asymmetric steel-and-glass cantilever over the Hudson housing America's definitive 20th and 21st-century masterworks.",
    },
    {
        "id": "ent_nyc_cin_001",
        "name": "Film Forum",
        "domain": "cinema",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "Greenwich Village",
        "category": "35mm Repertory & World Classics",
        "latitude": 40.7282,
        "longitude": -74.0048,
        "price_tier": 2,
        "vibe_tags": ["35mm", "repertory", "noir", "foreign-classics", "cinephile", "intimate"],
        "description": "Non-profit three-screen cinematheque providing peerless curated 35mm noir festivals and world cinema premieres since 1970.",
    },
    {
        "id": "ent_nyc_cin_002",
        "name": "Metrograph",
        "domain": "cinema",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "Chinatown / LES",
        "category": "Curated Archival Cinema & Commissary",
        "latitude": 40.7142,
        "longitude": -73.9912,
        "price_tier": 2,
        "vibe_tags": ["stylish-repertory", "35mm-projection", "candy-shop", "commissary", "indie", "bowery"],
        "description": "Sleek, cinephile dream space with red carpet lounges, rare archival film prints, and classic bookstore commissary.",
    },
    {
        "id": "ent_nyc_ngt_001",
        "name": "Bemelmans Bar at The Carlyle",
        "domain": "nightlife",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "Upper East Side",
        "category": "Art Deco Piano Jazz Lounge",
        "latitude": 40.7744,
        "longitude": -73.9632,
        "price_tier": 4,
        "vibe_tags": ["ludwig-bemelmans", "classic-martini", "piano-jazz", "art-deco", "timeless"],
        "description": "Gold-leaf ceilings and whimsical hand-painted murals by Madeline illustrator Ludwig Bemelmans surrounding grand piano jazz.",
    },
    {
        "id": "ent_nyc_lit_001",
        "name": "Strand Book Store",
        "domain": "literary",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "East Village / Union Square",
        "category": "Historic 18 Miles of Books",
        "latitude": 40.7333,
        "longitude": -73.9908,
        "price_tier": 1,
        "vibe_tags": ["18-miles-of-books", "rare-book-room", "union-square", "literary-landmark", "first-editions"],
        "description": "Legendary 1927 literary landmark carrying over 2.5 million new, used, and rare volumes on historic Book Row.",
    },
    {
        "id": "ent_nyc_fas_001",
        "name": "Dover Street Market New York",
        "domain": "fashion",
        "hub": "New York",
        "city": "New York",
        "country": "United States",
        "neighborhood": "Murray Hill / Lexington Ave",
        "category": "Avant-Garde Architectural Concept Space",
        "latitude": 40.7441,
        "longitude": -73.9806,
        "price_tier": 4,
        "vibe_tags": ["rei-kawakubo", "avant-garde", "concept-store", "glass-elevator", "high-fashion"],
        "description": "Rei Kawakubo's seven-story temple of experimental fashion where museum-grade installations merge with luxury streetwear.",
    },

    # ------------------------------------------------------------------------
    # London (10 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_lon_din_001",
        "name": "St. JOHN Smithfield",
        "domain": "dining",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Farringdon / Smithfield",
        "category": "Nose-to-Tail British Gastronomy",
        "latitude": 51.5204,
        "longitude": -0.1009,
        "price_tier": 3,
        "vibe_tags": ["nose-to-tail", "fergus-henderson", "bone-marrow", "minimalist", "white-walls", "monumental", "writers-haunt", "bohemian-soho"],
        "description": "Pristine whitewashed former smokehouse that revolutionized British gastronomy with roasted bone marrow, parsley salad, and Eccles cakes.",
    },
    {
        "id": "ent_lon_din_002",
        "name": "Dishoom Shoreditch",
        "domain": "dining",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Shoreditch",
        "category": "Old Bombay Irani Cafe Verandah",
        "latitude": 51.5248,
        "longitude": -0.0768,
        "price_tier": 2,
        "vibe_tags": ["irani-cafe", "black-daal", "chai", "verandah", "nostalgic-bombay", "nostalgic", "intimate"],
        "description": "Atmospheric tribute to old Bombay Irani cafes with ceiling fans, sepia family portraits, and velvety 24-hour black daal.",
    },
    {
        "id": "ent_lon_mus_001",
        "name": "Ronnie Scott's Jazz Club",
        "domain": "music",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Soho",
        "category": "Legendary Soho Crimson Jazz Den",
        "latitude": 51.5133,
        "longitude": -0.1319,
        "price_tier": 3,
        "vibe_tags": ["soho-jazz", "historic-1959", "red-lamps", "intimate", "legends", "nostalgic"],
        "description": "Subterranean crimson-lamp sanctum in the belly of Soho where jazz nobility has held court since 1959.",
    },
    {
        "id": "ent_lon_mus_002",
        "name": "Fabric London",
        "domain": "music",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Farringdon",
        "category": "Subterranean Bodysonic Electronic Temple",
        "latitude": 51.5196,
        "longitude": -0.1018,
        "price_tier": 2,
        "vibe_tags": ["electronic", "techno", "bodysonic-dancefloor", "underground-institution"],
        "description": "Legendary subterranean brick vaults featuring vibrating bodysonic dancefloors and uncompromising global electronic lineups.",
    },
    {
        "id": "ent_lon_art_001",
        "name": "Tate Modern",
        "domain": "arts",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Bankside",
        "category": "Industrial Turbine Hall Modern Art",
        "latitude": 51.5076,
        "longitude": -0.0994,
        "price_tier": 1,
        "vibe_tags": ["turbine-hall", "rothko", "modern-art", "bankside-powerstation", "monumental", "minimalist"],
        "description": "Colossal converted industrial turbine hall over the Thames showcasing monumental contemporary sculptures and surrealist masters.",
    },
    {
        "id": "ent_lon_cin_001",
        "name": "BFI Southbank",
        "domain": "cinema",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Waterloo / South Bank",
        "category": "National Archival Cinematheque",
        "latitude": 51.5068,
        "longitude": -0.1165,
        "price_tier": 2,
        "vibe_tags": ["bfi", "archival", "retrospectives", "southbank", "70mm"],
        "description": "The epicentre of British cinephilia nestled beneath Waterloo Bridge with four state-of-the-art archival screening screens.",
    },
    {
        "id": "ent_lon_cin_002",
        "name": "Prince Charles Cinema",
        "domain": "cinema",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Leicester Square",
        "category": "Cult, 35mm & 70mm Independent House",
        "latitude": 51.5113,
        "longitude": -0.1303,
        "price_tier": 1,
        "vibe_tags": ["cult-cinema", "sing-a-long", "35mm", "marathons", "indie-spirit"],
        "description": "Beloved fiercely independent west end movie house famous for 70mm epics, cult classics, and quote-along marathons.",
    },
    {
        "id": "ent_lon_ngt_001",
        "name": "The French House",
        "domain": "nightlife",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Dean Street, Soho",
        "category": "Bohemian Soho Pastis Saloon",
        "latitude": 51.5134,
        "longitude": -0.1328,
        "price_tier": 2,
        "vibe_tags": ["bohemian-soho", "half-pints", "no-phones", "writers-haunt", "ricard"],
        "description": "Storied Soho refuge for poets, painters, and philosophers where mobile phones are banned and pastis flows by the half-pint.",
    },
    {
        "id": "ent_lon_lit_001",
        "name": "Daunt Books Marylebone",
        "domain": "literary",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Marylebone High Street",
        "category": "Edwardian Oak Travel Bookshop",
        "latitude": 51.5208,
        "longitude": -0.1508,
        "price_tier": 2,
        "vibe_tags": ["edwardian-oak", "travel-writing", "skylight", "galleries", "bibliophile"],
        "description": "Magnificent Edwardian bookshop with long oak galleries, stained glass, and skylights arranging literature geographically by country.",
    },
    {
        "id": "ent_lon_fas_001",
        "name": "LN-CC (Late Night Chameleon Cafe)",
        "domain": "fashion",
        "hub": "London",
        "city": "London",
        "country": "United Kingdom",
        "neighborhood": "Dalston, Hackney",
        "category": "Futuristic Installation & Archive Store",
        "latitude": 51.5482,
        "longitude": -0.0754,
        "price_tier": 4,
        "vibe_tags": ["futuristic-tunnel", "concept-store", "rare-vinyl", "archive-fashion", "east-london"],
        "description": "Hidden subterranean installation entered via an octagonal wooden space tunnel housing curated high fashion, a listening room, and rare art tomes.",
    },

    # ------------------------------------------------------------------------
    # Tokyo (10 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_tyo_din_001",
        "name": "Afuri Harajuku",
        "domain": "dining",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Harajuku",
        "category": "Yuzu-Infused Artisanal Ramen",
        "latitude": 35.6713,
        "longitude": 139.7042,
        "price_tier": 2,
        "vibe_tags": ["yuzu-shio", "ramen", "charcoal-pork", "clean-broth", "modern-tokyo", "avant-garde"],
        "description": "Sleek counter serving delicate chicken broth brightened with fragrant mountain yuzu citrus and charcoal-grilled chashu.",
    },
    {
        "id": "ent_tyo_din_002",
        "name": "Omoide Yokocho",
        "domain": "dining",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Shinjuku West",
        "category": "Post-War Charcoal Yakitori Alleys",
        "latitude": 35.6928,
        "longitude": 139.6997,
        "price_tier": 1,
        "vibe_tags": ["yakitori", "memory-lane", "lanterns", "izakaya", "showa-era"],
        "description": "Narrow, evocative post-war lantern-draped alley packed with tiny five-stool counters sizzling with tare-glazed yakitori.",
    },
    {
        "id": "ent_tyo_mus_001",
        "name": "Meikyoku Kissa Lion",
        "domain": "music",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Shibuya Dogenzaka",
        "category": "Historic 1926 Classical Audio Sanctuary",
        "latitude": 35.6592,
        "longitude": 139.6974,
        "price_tier": 1,
        "vibe_tags": ["classical-music", "kissa", "giant-custom-speakers", "whispering-only", "showa-1926", "minimalism", "design", "intimate", "botanical"],
        "description": "Quiet sanctuary built in 1926 with cathedral pew seating facing massive two-story bespoke horn speakers playing classical vinyl.",
    },
    {
        "id": "ent_tyo_mus_002",
        "name": "Shinjuku Pit Inn",
        "domain": "music",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Shinjuku",
        "category": "Avant-Garde & Free Jazz Incubator",
        "latitude": 35.6908,
        "longitude": 139.7073,
        "price_tier": 2,
        "vibe_tags": ["free-jazz", "pit-inn", "improvisation", "legendary-stage", "subterranean"],
        "description": "The hallowed basement incubator of Japanese free jazz and improvisational music since 1965.",
    },
    {
        "id": "ent_tyo_art_001",
        "name": "Mori Art Museum",
        "domain": "arts",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Roppongi Hills",
        "category": "Skyline Contemporary Art Museum",
        "latitude": 35.6605,
        "longitude": 139.7292,
        "price_tier": 3,
        "vibe_tags": ["contemporary-art", "53rd-floor", "roppongi", "global-artists", "skyline"],
        "description": "World-class contemporary art museum on the 53rd floor of Roppongi Hills tower pairing radical exhibits with panoramic Tokyo vistas.",
    },
    {
        "id": "ent_tyo_art_002",
        "name": "21_21 DESIGN SIGHT",
        "domain": "arts",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Tokyo Midtown, Akasaka",
        "category": "Tadao Ando Geometric Design Research",
        "latitude": 35.6669,
        "longitude": 139.7305,
        "price_tier": 2,
        "vibe_tags": ["tadao-ando", "issey-miyake", "design", "geometry", "minimalism"],
        "description": "Folded steel-plate geometric pavilion sculpted by Tadao Ando and Issey Miyake exploring forward-looking design philosophy.",
    },
    {
        "id": "ent_tyo_cin_001",
        "name": "Bunkamura Le Cinéma",
        "domain": "cinema",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Shibuya",
        "category": "European Auteur & Arthouse Cinema",
        "latitude": 35.6608,
        "longitude": 139.6958,
        "price_tier": 2,
        "vibe_tags": ["auteur-cinema", "french-films", "bunkamura", "plush-seating", "retrospectives"],
        "description": "Refined arthouse cinema dedicated to European auteur cinema, restored classics, and premier international festival winners.",
    },
    {
        "id": "ent_tyo_ngt_001",
        "name": "Bar BenFiddich",
        "domain": "nightlife",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Nishi-Shinjuku",
        "category": "Farm-to-Glass Botanical Herbology Altar",
        "latitude": 35.6917,
        "longitude": 139.6961,
        "price_tier": 4,
        "vibe_tags": ["botanical-cocktails", "absinthe", "mortar-and-pestle", "herbalist", "intimate", "botanical"],
        "description": "Apothecary-style cocktail den where master Hiroyasu Kayama crushes garden-grown wormwood, roots, and ancient spirits with a mortar and pestle.",
    },
    {
        "id": "ent_tyo_lit_001",
        "name": "Daikanyama T-Site (Tsutaya Books)",
        "domain": "literary",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Daikanyama",
        "category": "Architectural Design & Monograph Labyrinth",
        "latitude": 35.6492,
        "longitude": 139.6998,
        "price_tier": 2,
        "vibe_tags": ["architectural-lattice", "klein-dytham", "rare-art-books", "lounge", "tokyo-design"],
        "description": "Klein Dytham designed architectural masterpiece featuring interconnected pavilions of art, photography monographs, and vintage jazz vinyl.",
    },
    {
        "id": "ent_tyo_fas_001",
        "name": "Comme des Garçons Aoyama",
        "domain": "fashion",
        "hub": "Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "neighborhood": "Minami-Aoyama",
        "category": "Sculptural Glass Flagship of Asymmetry",
        "latitude": 35.6625,
        "longitude": 139.7153,
        "price_tier": 4,
        "vibe_tags": ["rei-kawakubo", "sculptural-glass", "flagship", "avant-garde", "tokyo-fashion", "modern-tokyo"],
        "description": "Sculptural curved glass facade housing the definitive international flagship for Rei Kawakubo's groundbreaking asymmetric creations.",
    },

    # ------------------------------------------------------------------------
    # Paris (11 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_par_din_001",
        "name": "Septime",
        "domain": "dining",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "11th Arr. (Charonne)",
        "category": "Pioneering Natural-Wine Neo-Bistro",
        "latitude": 48.8533,
        "longitude": 2.3807,
        "price_tier": 3,
        "vibe_tags": ["neo-bistro", "natural-wine", "seasonal", "michelin-star", "understated", "modern-art", "nouvelle-vague"],
        "description": "Bertrand Grébaut's acclaimed culinary beacon of stripped-back wood tables, exquisite hyper-seasonal produce, and vibrant biodynamic wines.",
    },
    {
        "id": "ent_par_din_002",
        "name": "Bouillon Chartier",
        "domain": "dining",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "9th Arr. (Montmartre)",
        "category": "Belle Époque 1896 Vaulted Grand Hall",
        "latitude": 48.8719,
        "longitude": 2.3432,
        "price_tier": 1,
        "vibe_tags": ["belle-epoque-1896", "grand-hall", "classic-french", "traditional", "historic"],
        "description": "Immense 1896 vaulted dining hall with mirrored walls where aproned waiters scribble orders directly onto paper tablecloths.",
    },
    {
        "id": "ent_par_mus_001",
        "name": "Duc des Lombards",
        "domain": "music",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "1st Arr. (Châtelet)",
        "category": "Historic Châtelet Modern Jazz Sanctum",
        "latitude": 48.8598,
        "longitude": 2.3481,
        "price_tier": 3,
        "vibe_tags": ["jazz-club", "chatelet", "intimate", "bebop", "blue-lights", "speakeasy", "cocktails"],
        "description": "Chic, acoustically pristine club at the corner of Rue des Lombards welcoming the international crème de la crème of modern jazz.",
    },
    {
        "id": "ent_par_mus_002",
        "name": "Rex Club",
        "domain": "music",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "2nd Arr. (Grands Boulevards)",
        "category": "Pioneering Subterranean Techno Temple",
        "latitude": 48.8706,
        "longitude": 2.3478,
        "price_tier": 2,
        "vibe_tags": ["techno", "house-music", "historic-basement", "parisian-electronic", "sub-bass"],
        "description": "Storied subterranean venue beneath the Grand Rex cinema that spearheaded French touch and global electronic dance culture.",
    },
    {
        "id": "ent_par_art_001",
        "name": "Centre Pompidou",
        "domain": "arts",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "4th Arr. (Beaubourg)",
        "category": "Radical Inside-Out Modern Art Landmark",
        "latitude": 48.8606,
        "longitude": 2.3522,
        "price_tier": 2,
        "vibe_tags": ["modern-art", "renzo-piano", "richard-rogers", "cubism", "surrealism", "seasonal"],
        "description": "Radical inside-out glass-and-color architectural masterpiece holding Europe's leading modern and contemporary collection.",
    },
    {
        "id": "ent_par_art_002",
        "name": "Palais de Tokyo",
        "domain": "arts",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "16th Arr. (Trocadéro)",
        "category": "Anti-Museum Raw Concrete Laboratory",
        "latitude": 48.8643,
        "longitude": 2.2969,
        "price_tier": 2,
        "vibe_tags": ["contemporary", "avant-garde", "raw-concrete", "late-night", "installations"],
        "description": "Monumental Art Deco palace stripped down to raw concrete, functioning as an energetic, late-night open laboratory for living creators.",
    },
    {
        "id": "ent_par_cin_001",
        "name": "Le Champo - Espace Jacques Tati",
        "domain": "cinema",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "5th Arr. (Quartier Latin)",
        "category": "Spiritual Birthplace of the French New Wave",
        "latitude": 48.8504,
        "longitude": 2.3437,
        "price_tier": 1,
        "vibe_tags": ["nouvelle-vague", "godard", "truffaut", "historic-1938", "latin-quarter", "understated"],
        "description": "Charming Latin Quarter rep theater where François Truffaut and Claude Chabrol practically lived during the dawn of the French New Wave.",
    },
    {
        "id": "ent_par_cin_002",
        "name": "Cinémathèque Française",
        "domain": "cinema",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "12th Arr. (Bercy)",
        "category": "Frank Gehry Architectural Cinephile Shrine",
        "latitude": 48.8373,
        "longitude": 2.3831,
        "price_tier": 2,
        "vibe_tags": ["cinematheque", "frank-gehry", "film-museum", "rare-prints", "cinema-history"],
        "description": "Frank Gehry undulating limestone pavilion preserving cinema history with rare master prints, props, and retrospectives.",
    },
    {
        "id": "ent_par_ngt_001",
        "name": "Le Syndicat",
        "domain": "nightlife",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "10th Arr. (Faubourg Saint-Denis)",
        "category": "Artisanal French Spirits Speakeasy",
        "latitude": 48.8724,
        "longitude": 2.3559,
        "price_tier": 3,
        "vibe_tags": ["french-spirits", "armagnac", "hip-hop", "speakeasy", "cocktails"],
        "description": "Discreet flyer-plastered facade opening into a gilded den committed to resurrecting forgotten French artisanal brandies and liqueurs.",
    },
    {
        "id": "ent_par_lit_001",
        "name": "Shakespeare and Company",
        "domain": "literary",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "5th Arr. (Latin Quarter / Seine)",
        "category": "Iconic Bohemian Literary Pilgrimage",
        "latitude": 48.8526,
        "longitude": 2.3471,
        "price_tier": 1,
        "vibe_tags": ["george-whitman", "tumbleweeds", "be-not-inhospitable", "seine", "literary-haven"],
        "description": "Iconic bohemian bookshop facing Notre-Dame where generations of writers have slept among crowded bookshelves and antique typewriters.",
    },
    {
        "id": "ent_par_fas_001",
        "name": "Merci Paris",
        "domain": "fashion",
        "hub": "Paris",
        "city": "Paris",
        "country": "France",
        "neighborhood": "3rd Arr. (Haut-Marais)",
        "category": "Courtyard Fabric Factory Concept Haven",
        "latitude": 48.8609,
        "longitude": 2.3664,
        "price_tier": 3,
        "vibe_tags": ["concept-store", "red-fiat", "haut-marais", "linen", "design-curation"],
        "description": "Housed in a sun-drenched former fabric factory with a courtyard red vintage Fiat, curating sustainable fashion and avant-garde homewares.",
    },

    # ------------------------------------------------------------------------
    # Berlin (10 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_ber_din_001",
        "name": "Nobelhart & Schmutzig",
        "domain": "dining",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Kreuzberg",
        "category": "Radically Local Baltic Counter Dining",
        "latitude": 52.5065,
        "longitude": 13.3912,
        "price_tier": 4,
        "vibe_tags": ["radically-local", "counter-dining", "berlin-baltic", "michelin-star", "curated-wine"],
        "description": "Intimate 28-seat counter championing hyper-local, vocally regional Baltic and Brandenburg produce without citrus, pepper, or olive oil.",
    },
    {
        "id": "ent_ber_din_002",
        "name": "Mustafa's Gemüse Kebap",
        "domain": "dining",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Kreuzberg (Mehringdamm)",
        "category": "Cult Street Food Döner Stand",
        "latitude": 52.4939,
        "longitude": 13.3880,
        "price_tier": 1,
        "vibe_tags": ["gemuese-kebap", "street-food", "roasted-veggies", "feta", "berlin-classic"],
        "description": "World-famous curb kiosk where food lovers queue patiently for warm flatbread crammed with spiced chicken, crisp roasted vegetables, and crumbled feta.",
    },
    {
        "id": "ent_ber_mus_001",
        "name": "Berghain / Panorama Bar",
        "domain": "music",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Friedrichshain",
        "category": "Industrial Combined-Heat Power Plant Techno",
        "latitude": 52.5111,
        "longitude": 13.4431,
        "price_tier": 2,
        "vibe_tags": ["industrial-techno", "power-plant", "funktion-one", "panorama-bar", "legendary", "brutalist", "contemporary-art", "radically-local", "counter-dining"],
        "description": "Monolithic former East Berlin combined-heat power station housing the world's most revered techno sound system and clubbing culture.",
    },
    {
        "id": "ent_ber_mus_002",
        "name": "Pierre Boulez Saal",
        "domain": "music",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Mitte",
        "category": "Frank Gehry Modular Elliptical Chamber Hall",
        "latitude": 52.5152,
        "longitude": 13.3973,
        "price_tier": 3,
        "vibe_tags": ["frank-gehry", "chamber-music", "barenboim", "intimate-oval", "acoustics"],
        "description": "Frank Gehry designed elliptical wooden chamber music hall where audience and musicians merge in unbroken 360-degree sonic communion.",
    },
    {
        "id": "ent_ber_art_001",
        "name": "Boros Collection (Bunker Berlin)",
        "domain": "arts",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Mitte",
        "category": "WWII Air Raid Concrete Bunker Contemporary Art",
        "latitude": 52.5238,
        "longitude": 13.3853,
        "price_tier": 3,
        "vibe_tags": ["wwii-bunker", "private-collection", "contemporary-art", "brutalist", "guided-only"],
        "description": "Indestructible 1942 concrete air raid bunker transformed into a breathtaking gallery space for contemporary room-sized installations.",
    },
    {
        "id": "ent_ber_art_002",
        "name": "KW Institute for Contemporary Art",
        "domain": "arts",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Mitte (Auguststraße)",
        "category": "Courtyard Margarine Factory Art Discourse",
        "latitude": 52.5273,
        "longitude": 13.3957,
        "price_tier": 1,
        "vibe_tags": ["progressive-art", "berlin-biennale", "courtyard", "conceptual", "experimental"],
        "description": "Former margarine factory in historical Mitte driving international contemporary art discourses and Berlin Biennale exhibitions.",
    },
    {
        "id": "ent_ber_cin_001",
        "name": "Babylon Kino",
        "domain": "cinema",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Rosa-Luxemburg-Platz",
        "category": "1929 New Objectivity Silent Film Organ Palace",
        "latitude": 52.5275,
        "longitude": 13.4118,
        "price_tier": 1,
        "vibe_tags": ["silent-cinema", "philipps-organ", "1929-palace", "orchestral", "mitte", "discreet"],
        "description": "Striking 1929 New Objectivity cinema housing Germany's only working silent movie theater pipe organ with live musical accompaniment.",
    },
    {
        "id": "ent_ber_ngt_001",
        "name": "Buck and Breck",
        "domain": "nightlife",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Mitte (Brunnenstraße)",
        "category": "Hidden Granite Table Minimalist Speakeasy",
        "latitude": 52.5332,
        "longitude": 13.4005,
        "price_tier": 3,
        "vibe_tags": ["speakeasy", "secret-buzzer", "center-table", "craft-cocktails", "discreet", "mitte"],
        "description": "Camouflaged behind an abandoned storefront; ring the bell to enter an intimate 14-seat dark room built around a single granite cocktail altar.",
    },
    {
        "id": "ent_ber_lit_001",
        "name": "Do You Read Me?!",
        "domain": "literary",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Mitte (Auguststraße)",
        "category": "Curated International Visual Culture Sanctuary",
        "latitude": 52.5278,
        "longitude": 13.3951,
        "price_tier": 2,
        "vibe_tags": ["indie-magazines", "art-books", "typography", "auguststrasse", "design-haven"],
        "description": "Influential graphic black-and-white sanctuary stocking curated international art publications, avant-garde journals, and literature.",
    },
    {
        "id": "ent_ber_fas_001",
        "name": "VooStore Berlin",
        "domain": "fashion",
        "hub": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "neighborhood": "Kreuzberg (Oranienstraße)",
        "category": "Courtyard Locksmith Streetwear & Design Space",
        "latitude": 52.5015,
        "longitude": 13.4182,
        "price_tier": 3,
        "vibe_tags": ["courtyard-locksmith", "concept-store", "companion-coffee", "designer-fashion", "kreuzberg"],
        "description": "Hidden down a graffiti-strewn Kreuzberg courtyard in a 260-square-meter former locksmith shop, uniting progressive streetwear with specialty coffee.",
    },

    # ------------------------------------------------------------------------
    # San Francisco (10 Entities)
    # ------------------------------------------------------------------------
    {
        "id": "ent_sfo_din_001",
        "name": "Zuni Café",
        "domain": "dining",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "Civic Center / Market St",
        "category": "Mesquite Brick-Oven California Pioneer",
        "latitude": 37.7735,
        "longitude": -122.4218,
        "price_tier": 3,
        "vibe_tags": ["roast-chicken", "brick-oven", "california-cuisine", "judy-rodgers", "iconic", "acoustics", "hayes-valley"],
        "description": "Luminous triangular dining sanctuary with grand piano and copper bar, revered for Judy Rodgers' mesquite-roasted chicken with warm bread salad.",
    },
    {
        "id": "ent_sfo_din_002",
        "name": "Tartine Manufactory",
        "domain": "dining",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "Mission District",
        "category": "Industrial Fermentation Country Bread Bakery",
        "latitude": 37.7615,
        "longitude": -122.4138,
        "price_tier": 2,
        "vibe_tags": ["sourdough", "artisan-bakery", "ceramics", "fermentation", "airy-industrial", "mission-district"],
        "description": "Sun-drenched industrial cathedral celebrating naturally fermented country sourdough breads, inventive pastries, and fresh coastal dining.",
    },
    {
        "id": "ent_sfo_mus_001",
        "name": "SFJAZZ Center",
        "domain": "music",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "Hayes Valley",
        "category": "Purpose-Built Steep Amphitheater Jazz Hall",
        "latitude": 37.7762,
        "longitude": -122.4217,
        "price_tier": 3,
        "vibe_tags": ["jazz-center", "acoustics", "hayes-valley", "robert-mailleur", "steep-amphitheater"],
        "description": "America's first standalone purpose-built jazz auditorium featuring steep amphitheater seating and pristine crystal-clear acoustics.",
    },
    {
        "id": "ent_sfo_mus_002",
        "name": "The Fillmore",
        "domain": "music",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "Fillmore District",
        "category": "Sacred 1960s Psychedelic Rock Ballroom",
        "latitude": 37.7841,
        "longitude": -122.4331,
        "price_tier": 2,
        "vibe_tags": ["psychedelic-rock", "concert-posters", "apples-tradition", "chandeliers", "historic", "beat-generation", "free-speech"],
        "description": "Hallowed ballroom where Hendrix, Joplin, and the Grateful Dead made history; complete with glittering chandeliers and free apples.",
    },
    {
        "id": "ent_sfo_art_001",
        "name": "SFMOMA",
        "domain": "arts",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "SoMa",
        "category": "Snøhetta Undulating Modern Art Complex",
        "latitude": 37.7857,
        "longitude": -122.4011,
        "price_tier": 3,
        "vibe_tags": ["snohetta-architecture", "living-wall", "matisse", "contemporary-art", "photography"],
        "description": "Striking Snøhetta-designed ten-story undulating white facade housing expansive modern masterworks, photography vaults, and a giant living wall.",
    },
    {
        "id": "ent_sfo_cin_001",
        "name": "Roxie Theater",
        "domain": "cinema",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "Mission District",
        "category": "Mission's 1909 Grassroots Non-Profit Cinema",
        "latitude": 37.7648,
        "longitude": -122.4199,
        "price_tier": 1,
        "vibe_tags": ["oldest-cinema", "indie-film", "1909", "mission-district", "community-nonprofit", "fermentation"],
        "description": "Beloved community non-profit cinema operating continuously since 1909, dedicated to daring documentaries, cult oddities, and grassroots indie premieres.",
    },
    {
        "id": "ent_sfo_cin_002",
        "name": "Castro Theatre",
        "domain": "cinema",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "The Castro",
        "category": "1922 Spanish Baroque Movie Palace",
        "latitude": 37.7621,
        "longitude": -122.4348,
        "price_tier": 2,
        "vibe_tags": ["wurlitzer-organ", "1922-palace", "castro", "sing-alongs", "spanish-baroque"],
        "description": "Timothy Pflueger's 1922 cathedral of film featuring a rising Mighty Wurlitzer pipe organ and exuberant sing-along events.",
    },
    {
        "id": "ent_sfo_ngt_001",
        "name": "Smuggler's Cove",
        "domain": "nightlife",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "Hayes Valley",
        "category": "Multi-Level Historical Rum & Tiki Sanctum",
        "latitude": 37.7794,
        "longitude": -122.4233,
        "price_tier": 2,
        "vibe_tags": ["tiki-temple", "vintage-rum", "nautical", "craft-cocktails", "martin-cate"],
        "description": "Pirate-ship wonderland boasting over 1,000 rare rums, nautical rigging, waterfall bars, and masterfully balanced historical tiki concoctions.",
    },
    {
        "id": "ent_sfo_lit_001",
        "name": "City Lights Booksellers & Publishers",
        "domain": "literary",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "North Beach",
        "category": "Beat Generation Free Speech Landmark",
        "latitude": 37.7976,
        "longitude": -122.4066,
        "price_tier": 1,
        "vibe_tags": ["beat-generation", "ferlinghetti", "ginsberg", "poetry-room", "free-speech"],
        "description": "Lawrence Ferlinghetti's landmark 1953 bookstore and publishing house that fought for free expression and sheltered Allen Ginsberg and Jack Kerouac.",
    },
    {
        "id": "ent_sfo_fas_001",
        "name": "Reliquary",
        "domain": "fashion",
        "hub": "San Francisco",
        "city": "San Francisco",
        "country": "United States",
        "neighborhood": "Hayes Valley",
        "category": "Cabinet-of-Curiosities Vintage Textiles",
        "latitude": 37.7766,
        "longitude": -122.4245,
        "price_tier": 3,
        "vibe_tags": ["vintage-textiles", "cabinet-of-curiosities", "antique-jewelry", "slow-fashion", "hayes-valley"],
        "description": "Intimate cabinet-of-curiosities boutique curating rare American denim, antique Victorian charms, folk embroidery, and heritage workwear.",
    },
]

# Hydrate raw dicts to CulturalEntity instances
MOCK_ENTITIES: List[CulturalEntity] = [
    CulturalEntity.model_validate(raw) for raw in RAW_MOCK_ENTITIES
]


# ============================================================================
# 3. In-Memory Indexes (Populated at module load)
# ============================================================================

ENTITIES_BY_ID: Dict[str, CulturalEntity] = {e.id: e for e in MOCK_ENTITIES}

ENTITIES_BY_HUB: Dict[str, List[CulturalEntity]] = {}
for e in MOCK_ENTITIES:
    ENTITIES_BY_HUB.setdefault(e.hub, []).append(e)

ENTITIES_BY_DOMAIN: Dict[CulturalDomain, List[CulturalEntity]] = {}
for e in MOCK_ENTITIES:
    ENTITIES_BY_DOMAIN.setdefault(e.domain, []).append(e)


# ============================================================================
# 4. Domain Compatibility Base Matrix
# ============================================================================

DOMAIN_COMPATIBILITY: Dict[Tuple[str, str], float] = {
    ("music", "nightlife"): 0.84,
    ("nightlife", "music"): 0.84,
    ("music", "cinema"): 0.80,
    ("cinema", "music"): 0.80,
    ("arts", "cinema"): 0.85,
    ("cinema", "arts"): 0.85,
    ("arts", "literary"): 0.83,
    ("literary", "arts"): 0.83,
    ("dining", "nightlife"): 0.82,
    ("nightlife", "dining"): 0.82,
    ("music", "dining"): 0.78,
    ("dining", "music"): 0.78,
    ("literary", "dining"): 0.77,
    ("dining", "literary"): 0.77,
    ("fashion", "arts"): 0.81,
    ("arts", "fashion"): 0.81,
    ("fashion", "nightlife"): 0.76,
    ("nightlife", "fashion"): 0.76,
    ("fashion", "dining"): 0.75,
    ("dining", "fashion"): 0.75,
}

DEFAULT_DOMAIN_COMPATIBILITY = 0.72


# ============================================================================
# 5. Curated High-Affinity Cross-Domain Pairings
# ============================================================================

CURATED_AFFINITIES: Dict[Tuple[str, str], Dict[str, Any]] = {
    # 1. New York: Village Vanguard (Music) -> Via Carota (Dining)
    ("ent_nyc_mus_001", "ent_nyc_din_001"): {
        "score": 0.94,
        "confidence": 0.95,
        "rationale": "Both cultivate an intimate, timeless Greenwich Village acoustic craft; lovers of classic modal jazz instinctively resonate with artisanal Italian simplicity.",
        "shared_tags": ["intimate", "west-village"],
    },
    # 2. New York: Village Vanguard (Music) -> Film Forum (Cinema)
    ("ent_nyc_mus_001", "ent_nyc_cin_001"): {
        "score": 0.96,
        "confidence": 0.98,
        "rationale": "Direct aesthetic symbiosis: mid-century jazz improvisation shares the gritty, high-contrast auteur rhythm of 35mm New York noir and French New Wave.",
        "shared_tags": ["repertory", "noir", "intimate"],
    },
    # 3. New York: Village Vanguard (Music) -> Bemelmans Bar (Nightlife)
    ("ent_nyc_mus_001", "ent_nyc_ngt_001"): {
        "score": 0.95,
        "confidence": 0.93,
        "rationale": "Shared reverence for golden-era Manhattan elegance, acoustic upright bass, and masterfully shaken classic dry martinis.",
        "shared_tags": ["piano-jazz", "timeless", "art-deco"],
    },
    # 4. New York: Bowery Ballroom (Music) -> Metrograph (Cinema)
    ("ent_nyc_mus_002", "ent_nyc_cin_002"): {
        "score": 0.92,
        "confidence": 0.94,
        "rationale": "Lower East Side independent vanguard: the acoustic energy of Bowery Ballroom pairs seamlessly with Metrograph's stylish 35mm cinema aesthetic.",
        "shared_tags": ["indie", "bowery"],
    },
    # 5. London: St. JOHN (Dining) -> Tate Modern (Arts)
    ("ent_lon_din_001", "ent_lon_art_001"): {
        "score": 0.91,
        "confidence": 0.92,
        "rationale": "Fergus Henderson's unadorned, industrial culinary honesty mirrors the raw, monumental concrete brutalism of the Bankside Turbine Hall.",
        "shared_tags": ["minimalist", "monumental"],
    },
    # 6. London: St. JOHN (Dining) -> The French House (Nightlife)
    ("ent_lon_din_001", "ent_lon_ngt_001"): {
        "score": 0.93,
        "confidence": 0.95,
        "rationale": "An unbroken thread of unpretentious Soho/Farringdon bohemian tradition, deep camaraderie, and appreciation for classic European hospitality.",
        "shared_tags": ["writers-haunt", "bohemian-soho"],
    },
    # 7. London: Ronnie Scott's (Music) -> Dishoom (Dining)
    ("ent_lon_mus_001", "ent_lon_din_002"): {
        "score": 0.88,
        "confidence": 0.90,
        "rationale": "Soho jazz soulfulness followed by velvety 24-hour black daal in Shoreditch evokes mid-century cosmopolitan London warmth.",
        "shared_tags": ["nostalgic", "intimate"],
    },
    # 8. Tokyo: Meikyoku Kissa Lion (Music) -> 21_21 DESIGN SIGHT (Arts)
    ("ent_tyo_mus_001", "ent_tyo_art_002"): {
        "score": 0.93,
        "confidence": 0.94,
        "rationale": "Both spaces treat focus and silence as architectural materials, valuing precision craftsmanship over ornamental distraction.",
        "shared_tags": ["minimalism", "design"],
    },
    # 9. Tokyo: Meikyoku Kissa Lion (Music) -> Bar BenFiddich (Nightlife)
    ("ent_tyo_mus_001", "ent_tyo_ngt_001"): {
        "score": 0.95,
        "confidence": 0.96,
        "rationale": "The contemplative reverence for vinyl audio matches Kayama-san's meditative, mortar-and-pestle cocktail alchemy in Shinjuku.",
        "shared_tags": ["intimate", "botanical"],
    },
    # 10. Tokyo: Afuri Harajuku (Dining) -> Comme des Garçons Aoyama (Fashion)
    ("ent_tyo_din_001", "ent_tyo_fas_001"): {
        "score": 0.90,
        "confidence": 0.92,
        "rationale": "Modern Tokyo clarity: the crisp, restrained citrus profiles of Afuri harmonize with the architectural avant-garde geometry of Kawakubo's Aoyama flagship.",
        "shared_tags": ["modern-tokyo", "avant-garde"],
    },
    # 11. Paris: Septime (Dining) -> Centre Pompidou (Arts)
    ("ent_par_din_001", "ent_par_art_001"): {
        "score": 0.90,
        "confidence": 0.92,
        "rationale": "Modernist reinvention: Septime strips dining to pure elemental flavors much like Beaubourg reveals the functional skeletal beauty of modern art.",
        "shared_tags": ["modern-art", "seasonal"],
    },
    # 12. Paris: Septime (Dining) -> Le Champo (Cinema)
    ("ent_par_din_001", "ent_par_cin_001"): {
        "score": 0.92,
        "confidence": 0.93,
        "rationale": "Shared Nouvelle Vague spirit: discarding rigid bourgeois convention in favor of raw natural spontaneity and auteur creativity.",
        "shared_tags": ["nouvelle-vague", "understated"],
    },
    # 13. Paris: Duc des Lombards (Music) -> Le Syndicat (Nightlife)
    ("ent_par_mus_001", "ent_par_ngt_001"): {
        "score": 0.89,
        "confidence": 0.91,
        "rationale": "Châtelet jazz virtuosity seamlessly blends into the hip-hop energy and artisanal French brandies of Faubourg Saint-Denis.",
        "shared_tags": ["speakeasy", "cocktails"],
    },
    # 14. Berlin: Berghain (Music) -> Boros Collection (Arts)
    ("ent_ber_mus_001", "ent_ber_art_001"): {
        "score": 0.97,
        "confidence": 0.98,
        "rationale": "Supreme industrial concrete symbiosis: monumental brutalist structures repurposed as uncompromising sanctuaries for cutting-edge contemporary culture.",
        "shared_tags": ["brutalist", "contemporary-art"],
    },
    # 15. Berlin: Berghain (Music) -> Nobelhart & Schmutzig (Dining)
    ("ent_ber_mus_001", "ent_ber_din_001"): {
        "score": 0.89,
        "confidence": 0.90,
        "rationale": "Radically uncompromising, rule-breaking Berlin identity that rejects mainstream commercial convenience in pursuit of unvarnished authenticity.",
        "shared_tags": ["radically-local", "counter-dining"],
    },
    # 16. Berlin: Babylon Kino (Cinema) -> Buck and Breck (Nightlife)
    ("ent_ber_cin_001", "ent_ber_ngt_001"): {
        "score": 0.91,
        "confidence": 0.93,
        "rationale": "Mitte nocturnal sophistication: 1929 silent film organ performance followed by intimate granite-table craft cocktails behind a discreet buzzer.",
        "shared_tags": ["mitte", "discreet"],
    },
    # 17. San Francisco: Zuni Café (Dining) -> SFJAZZ Center (Music)
    ("ent_sfo_din_001", "ent_sfo_mus_001"): {
        "score": 0.92,
        "confidence": 0.93,
        "rationale": "Civic Center creative kinship: Judy Rodgers' timeless acoustic dining harmony pairs naturally with the pristine wood acoustics of Hayes Valley jazz.",
        "shared_tags": ["acoustics", "hayes-valley"],
    },
    # 18. San Francisco: The Fillmore (Music) -> City Lights (Literary)
    ("ent_sfo_mus_002", "ent_sfo_lit_001"): {
        "score": 0.96,
        "confidence": 0.97,
        "rationale": "The soul of San Francisco counter-culture: Allen Ginsberg's beat poetry and psychedelic rock at the Fillmore are twin branches of the same revolution.",
        "shared_tags": ["beat-generation", "free-speech"],
    },
    # 19. San Francisco: Tartine Manufactory (Dining) -> Roxie Theater (Cinema)
    ("ent_sfo_din_002", "ent_sfo_cin_001"): {
        "score": 0.90,
        "confidence": 0.91,
        "rationale": "Mission District artisanal community heart: naturally fermented sourdough dinner transitioning into grassroots indie cinema on 16th Street.",
        "shared_tags": ["mission-district", "fermentation"],
    },
    # 20. Bangalore: Vidyarthi Bhavan (Dining) -> Windmills Craftworks (Music)
    ("ent_blr_din_001", "ent_blr_mus_001"): {
        "score": 0.88,
        "confidence": 0.89,
        "rationale": "Cross-era Bangalore pride: connecting historic Basavanagudi heritage craftsmanship with the modern cosmopolitan sophistication of Whitefield.",
        "shared_tags": ["heritage", "books"],
    },
    # 21. Bangalore: NGMA (Arts) -> Suchitra Film Society (Cinema)
    ("ent_blr_art_001", "ent_blr_cin_001"): {
        "score": 0.93,
        "confidence": 0.94,
        "rationale": "Pure parallel arts resonance: celebrating classical modern visual aesthetics alongside pioneering parallel Indian cinema.",
        "shared_tags": ["parallel-cinema", "satyajit-ray"],
    },
    # 22. Bangalore: Blossom Book House (Literary) -> Pecos (Nightlife)
    ("ent_blr_lit_001", "ent_blr_ngt_001"): {
        "score": 0.94,
        "confidence": 0.95,
        "rationale": "Church Street and Rest House Road counter-culture soul: browsing rare second-hand philosophy tomes before sharing draught stout over vintage classic rock.",
        "shared_tags": ["nostalgia", "second-hand", "church-street"],
    },
    # 23. Mumbai: Britannia & Co. (Dining) -> Regal Cinema (Cinema)
    ("ent_bom_din_001", "ent_bom_cin_001"): {
        "score": 0.95,
        "confidence": 0.96,
        "rationale": "South Bombay Art Deco and colonial heritage alignment: stepping between Ballard Estate's 1923 dining hall and Colaba's 1933 cinema palace.",
        "shared_tags": ["heritage-1933", "art-deco", "colonial-architecture"],
    },
    # 24. Mumbai: Jehangir Art Gallery (Arts) -> Kitab Khana (Literary)
    ("ent_bom_art_001", "ent_bom_lit_001"): {
        "score": 0.92,
        "confidence": 0.93,
        "rationale": "Kala Ghoda and Fort intellectual corridor: walking from premier contemporary Indian art halls into towering teak bookshelves of Somaiya Bhavan.",
        "shared_tags": ["kala-ghoda", "heritage-building"],
    },
    # 25. Mumbai: antiSOCIAL (Music) -> The Bombay Canteen (Dining)
    ("ent_bom_mus_002", "ent_bom_din_002"): {
        "score": 0.91,
        "confidence": 0.92,
        "rationale": "Lower Parel mill district creative revival: innovative regional Indian dining paired with subterranean modular electronic beats.",
        "shared_tags": ["industrial-basement", "innovative"],
    },
}


# ============================================================================
# 6. Helper Functions & Normalization
# ============================================================================

def normalize_hub(hub: Optional[str]) -> Optional[str]:
    """Returns canonical hub name or None."""
    if not hub:
        return None
    clean = hub.strip().lower()
    return HUB_ALIASES.get(clean, hub.strip().title() if hub.strip().title() in SUPPORTED_HUBS else None)


def normalize_domain(domain: Optional[Union[CulturalDomain, str]]) -> Optional[CulturalDomain]:
    """Returns canonical CulturalDomain enum or None."""
    if domain is None:
        return None
    if isinstance(domain, CulturalDomain):
        return domain
    clean = str(domain).strip().lower()
    if not clean:
        return None
    return CulturalDomain.normalize(clean)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two coordinates in km."""
    R = 6371.0  # Earth's mean radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


# ============================================================================
# 7. Deterministic Affinity Engine
# ============================================================================

def calculate_affinity(
    source_entity: CulturalEntity,
    target_entity: CulturalEntity,
) -> Dict[str, Any]:
    """
    Computes deterministic affinity between source and target entities.
    Returns raw dict matching AffinityScore schema:
    - score: float [0.0, 1.0]
    - confidence: float [0.0, 1.0]
    - rationale: str
    - shared_tags: List[str]
    """
    # 1. Intra-entity identity
    if source_entity.id == target_entity.id:
        return {
            "entity_id": source_entity.id,
            "target_entity": target_entity,
            "score": 1.0,
            "confidence": 1.0,
            "rationale": f"Intra-entity self-resonance for {source_entity.name}.",
            "shared_tags": list(source_entity.vibe_tags),
        }

    # 2. Check curated pairings (bi-directional check)
    curated = CURATED_AFFINITIES.get((source_entity.id, target_entity.id))
    if curated is not None:
        return {
            "entity_id": source_entity.id,
            "target_entity": target_entity,
            "score": curated["score"],
            "confidence": curated["confidence"],
            "rationale": curated["rationale"],
            "shared_tags": list(curated.get("shared_tags", [])),
        }

    # 3. Deterministic Mathematical Synthesis
    src_tags = set(source_entity.vibe_tags)
    tgt_tags = set(target_entity.vibe_tags)
    shared_tags = sorted(list(src_tags.intersection(tgt_tags)))
    union_tags = src_tags.union(tgt_tags)

    # Jaccard tag similarity
    jaccard = len(shared_tags) / max(1, len(union_tags))
    tag_bonus = 0.25 * jaccard

    # Domain compatibility base
    domain_pair = (source_entity.domain.value, target_entity.domain.value)
    base_compatibility = DOMAIN_COMPATIBILITY.get(domain_pair, DEFAULT_DOMAIN_COMPATIBILITY)

    # Price disparity penalty
    price_penalty = 0.035 * abs(source_entity.price_tier - target_entity.price_tier)

    # Spatial modifier (only if same hub)
    spatial_mod = 0.0
    if source_entity.hub == target_entity.hub:
        dist_km = haversine_distance_km(
            source_entity.latitude, source_entity.longitude,
            target_entity.latitude, target_entity.longitude,
        )
        if dist_km <= 3.0:
            spatial_mod = 0.04
        elif dist_km <= 8.0:
            spatial_mod = 0.02
        elif dist_km <= 20.0:
            spatial_mod = 0.00
        else:
            spatial_mod = -0.04

    # Cryptographic hash jitter (strictly deterministic)
    key_str = f"{source_entity.id}:{target_entity.id}"
    digest = hashlib.sha256(key_str.encode("utf-8")).digest()
    hash_val = (int.from_bytes(digest[:4], "big") % 100) - 50
    hash_jitter = hash_val / 1000.0  # in [-0.050, +0.049]

    # Composite score
    raw_score = base_compatibility + tag_bonus - price_penalty + spatial_mod + hash_jitter
    final_score = round(min(0.99, max(0.15, raw_score)), 3)

    # Confidence calculation
    confidence = round(min(0.99, 0.75 + (0.24 * jaccard)), 2)

    # Human-readable rationale synthesis
    if shared_tags:
        tags_str = ", ".join(shared_tags)
        rationale = (
            f"Shared aesthetic resonance: Both {source_entity.name} and {target_entity.name} celebrate "
            f"{tags_str}, bridging {source_entity.domain.value} and {target_entity.domain.value} "
            f"through harmonious cultural sensibilities."
        )
    else:
        src_tag = source_entity.vibe_tags[0] if source_entity.vibe_tags else source_entity.domain.value
        tgt_tag = target_entity.vibe_tags[0] if target_entity.vibe_tags else target_entity.domain.value
        rationale = (
            f"Cross-domain cultural pairing: The {src_tag} character of {source_entity.name} naturally "
            f"transitions into the {tgt_tag} atmosphere of {target_entity.name} in {target_entity.hub}."
        )

    return {
        "entity_id": source_entity.id,
        "target_entity": target_entity,
        "score": final_score,
        "confidence": confidence,
        "rationale": rationale,
        "shared_tags": shared_tags,
    }


def compute_deterministic_affinities(
    source_entity: CulturalEntity,
    target_domain: CulturalDomain,
    hub: Optional[str] = None,
    limit: int = 5,
) -> List[AffinityScore]:
    """
    Computes deterministic cross-domain affinities from source_entity to candidates
    in target_domain, optionally filtered by hub, sorted descending by score.
    """
    if limit <= 0:
        raise ValueError("limit must be greater than 0")

    # Get candidates in target domain
    candidates = ENTITIES_BY_DOMAIN.get(target_domain, [])
    if hub:
        canonical_hub = normalize_hub(hub)
        if canonical_hub:
            candidates = [c for c in candidates if c.hub == canonical_hub]

    # Compute affinities
    scored: List[AffinityScore] = []
    for cand in candidates:
        if cand.id == source_entity.id:
            continue
        aff_dict = calculate_affinity(source_entity, cand)
        scored.append(AffinityScore.model_validate(aff_dict))

    # Sort descending by score, tie-breaker target entity id
    scored.sort(key=lambda x: (-x.score, x.target_entity.id))
    return scored[:limit]


# ============================================================================
# 8. Entity Search & Retrieval API
# ============================================================================

def find_mock_entities(
    query: str,
    domain: Optional[CulturalDomain] = None,
    hub: Optional[str] = None,
    limit: int = 10,
) -> List[CulturalEntity]:
    """
    Performs tokenized, case-insensitive substring and tag matching across mock catalog.
    """
    if limit <= 0:
        raise ValueError("limit must be greater than 0")

    query_clean = query.strip().lower()
    if not query_clean:
        return []

    tokens = query_clean.split()
    matched: List[Tuple[int, CulturalEntity]] = []

    for entity in MOCK_ENTITIES:
        # Hub filter
        if hub:
            canonical_hub = normalize_hub(hub)
            if canonical_hub and entity.hub != canonical_hub:
                continue

        # Domain filter
        if domain and entity.domain != domain:
            continue

        # Text matching
        name_lower = entity.name.lower()
        desc_lower = entity.description.lower()
        cat_lower = (entity.category or "").lower()
        neigh_lower = (entity.neighborhood or "").lower()
        tags_lower = [t.lower() for t in entity.vibe_tags]

        score = 0
        all_tokens_matched = True

        for token in tokens:
            token_matched = False
            if token == name_lower:
                score += 50
                token_matched = True
            elif token in name_lower:
                score += 25
                token_matched = True

            if any(token == t for t in tags_lower):
                score += 20
                token_matched = True
            elif any(token in t for t in tags_lower):
                score += 10
                token_matched = True

            if token in neigh_lower:
                score += 10
                token_matched = True
            if token in cat_lower:
                score += 8
                token_matched = True
            if token in desc_lower:
                score += 5
                token_matched = True

            if not token_matched:
                all_tokens_matched = False
                break

        if all_tokens_matched and score > 0:
            matched.append((score, entity))

    # Sort descending by score, tie-breaker by entity name
    matched.sort(key=lambda x: (-x[0], x[1].name))
    return [entity for _, entity in matched[:limit]]


# Aliases for spec compatibility
search_mock_entities = find_mock_entities


def get_mock_entity(entity_id: str) -> Optional[CulturalEntity]:
    """O(1) dictionary retrieval of an entity by ID."""
    if not entity_id or not entity_id.strip():
        return None
    return ENTITIES_BY_ID.get(entity_id.strip())


def get_mock_hub_entities(
    hub: str,
    domain: Optional[Union[CulturalDomain, str]] = None,
    limit: int = 50,
) -> List[CulturalEntity]:
    """Lists entities in a designated cultural hub, optionally filtered by domain."""
    canonical_hub = normalize_hub(hub)
    if not canonical_hub or canonical_hub not in SUPPORTED_HUBS:
        return []

    entities = ENTITIES_BY_HUB.get(canonical_hub, [])
    resolved_domain = normalize_domain(domain)
    if resolved_domain:
        entities = [e for e in entities if e.domain == resolved_domain]

    return entities[:limit]


def get_mock_cross_domain_affinities(
    entity_id: str,
    target_domain: Union[CulturalDomain, str],
    hub: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Returns raw affinity dicts for spec miner compatibility."""
    source_entity = get_mock_entity(entity_id)
    if source_entity is None:
        return []
    resolved_domain = normalize_domain(target_domain)
    if resolved_domain is None:
        return []
    affinities = compute_deterministic_affinities(
        source_entity=source_entity,
        target_domain=resolved_domain,
        hub=hub,
        limit=limit,
    )
    return [a.model_dump() for a in affinities]
