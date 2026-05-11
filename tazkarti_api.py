```python
import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tazkarti.com/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


# ===== قراءة JSON بشكل آمن =====
def safe_json(response):
    try:
        return response.json()

    except Exception as e:

        logger.error(f"JSON Decode Error: {e}")

        try:
            logger.error(f"Response Text: {response.text[:500]}")
        except:
            pass

        return []


# ===== جلب المباريات =====
def get_matches():

    try:

        url = f"{BASE_URL}/matches"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        logger.info(f"Matches Status Code: {response.status_code}")

        if response.status_code != 200:
            return []

        data = safe_json(response)

        # لو object
        if isinstance(data, dict):

            if "data" in data:
                return data["data"]

            if "matches" in data:
                return data["matches"]

            return []

        # لو list
        if isinstance(data, list):
            return data

        return []

    except Exception as e:

        logger.error(f"get_matches Error: {e}")

        return []


# ===== جلب الفرق =====
def get_epl_teams():

    try:

        url = f"{BASE_URL}/teams"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        logger.info(f"Teams Status Code: {response.status_code}")

        if response.status_code != 200:
            return []

        data = safe_json(response)

        # لو object
        if isinstance(data, dict):

            if "data" in data:
                return data["data"]

            if "teams" in data:
                return data["teams"]

            return []

        # لو list
        if isinstance(data, list):
            return data

        return []

    except Exception as e:

        logger.error(f"get_epl_teams Error: {e}")

        return []


# ===== مباريات فريق =====
def get_matches_for_team(team_id):

    try:

        matches = get_matches()

        if not matches:
            return []

        filtered_matches = []

        for match in matches:

            team1 = match.get("teamId1")
            team2 = match.get("teamId2")

            if team1 == team_id or team2 == team_id:
                filtered_matches.append(match)

        return filtered_matches

    except Exception as e:

        logger.error(f"get_matches_for_team Error: {e}")

        return []
```
