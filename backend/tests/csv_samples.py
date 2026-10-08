"""Validated CSV samples, named and quoted as Night Crawler writes them.

Imported by tests as `csv_samples` (pytest puts `backend/tests` on the
path for its root `conftest.py`).
"""

CRAWLER_ID = "c57f32ca-b70f-4f87-b93f-233f0f7b9efd"
PLACES_HEADER = (
    "item_id,name,address,location,categories,rating,review_count,"
    "price_range,source_url"
)


def file_name(execution_number: int, started: str = "20261005T100000Z") -> str:
    """A validated CSV's name, as Night Crawler writes it."""
    execution_id = f"00000000-0000-4000-8000-{execution_number:012d}"
    return f"{CRAWLER_ID}_{execution_id}_{started}.csv"


def place_line(item_id: str, name: str = "Arrabal", rating: str = "9.8") -> str:
    """One places CSV row, quoted like Night Crawler writes it."""
    return (
        f'{item_id},{name},"Carrer de Bretón, 18, Barcelona",'
        '"{""latitude"": 41.4, ""longitude"": 2.15}","[""Argentino""]",'
        f"{rating},45,3,https://www.thefork.es/restaurante/{item_id}"
    )


EVENTS_HEADER = (
    "item_id,name,start_date,end_date,timezone,all_day,venue,organizers,"
    "cost,price_min,price_max,source_url"
)


def event_line(item_id: str, name: str = "Coming In Hot", cost: str = "") -> str:
    """One events CSV row, quoted like Night Crawler writes it."""
    return (
        f"{item_id},{name},2026-10-05 19:30:00,2026-10-05 20:45:00,"
        'Europe/Madrid,False,The Clubhouse: Laietana,"[""Clarice Mottet""]",'
        f"{cost},,,https://thecomedyclubhouse.es/event/{item_id}/"
    )
