import requests
import json
import time
from typing import Optional, List, Dict

BASE_URL = "https://tazkarti.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://tazkarti.com/",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

EPL_TEAM_IDS = {
    77, 79, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180,
    181, 182, 183, 184, 185, 186, 223, 224, 290, 291, 310,
}


def get_epl_teams() -> List[Dict]:
    all_teams = get_teams()
    return [t for t in all_teams if t["id"] in EPL_TEAM_IDS and t.get("teamStatus") == 1 and not t.get("isDeleted")]


def get_matches():
    r = requests.get(
        f"{BASE_URL}/data/matches-list-json.json",
        headers=HEADERS,
        timeout=15,
    )
    content = r.content.decode("utf-8-sig")
    return json.loads(content)


def get_teams():
    r = requests.get(
        f"{BASE_URL}/booksprt/teams/getTeams",
        headers=HEADERS,
        timeout=15,
    )
    return r.json()


def get_stadiums():
    r = requests.get(
        f"{BASE_URL}/booksprt/stadiums/getStadiums",
        headers=HEADERS,
        timeout=15,
    )
    return r.json()


def get_rounds():
    r = requests.get(
        f"{BASE_URL}/booksprt/rounds/getRounds",
        headers=HEADERS,
        timeout=15,
    )
    return r.json()


def get_team_groups():
    r = requests.get(
        f"{BASE_URL}/booksprt/teamGroups/getTeamGroups",
        headers=HEADERS,
        timeout=15,
    )
    return r.json()


def get_matches_for_team(team_id: int):
    matches = get_matches()
    return [
        m
        for m in matches
        if m.get("teamId1") == team_id or m.get("teamId2") == team_id
    ]


def _get_ticket_price_url(match_id: int) -> str:
    return f"{BASE_URL}/data/TicketPrice-AvailableSeats-{match_id}.json?_{int(time.time() * 1000)}"


def get_ticket_prices(match_id: int) -> Optional[dict]:
    try:
        r = requests.get(
            _get_ticket_price_url(match_id),
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            content = r.content.decode("utf-8-sig")
            return json.loads(content)
    except Exception:
        pass
    return None


def get_fan_queues(match_id: int) -> Optional[dict]:
    try:
        r = requests.get(
            f"{BASE_URL}/data/fanQueuesMatch-list-json.json?_{int(time.time() * 1000)}",
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            content = r.content.decode("utf-8-sig")
            return json.loads(content)
    except Exception:
        pass
    return None
