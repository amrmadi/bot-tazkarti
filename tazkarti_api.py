import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tazkarti.com/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.tazkarti.com/",
    "Origin": "https://www.tazkarti.com",
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
        response = requests.get(url, headers=HEADERS, timeout=20)
        logger.info(f"Matches Status Code: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Matches endpoint returned: {response.status_code}")
            return []

        data = safe_json(response)

        if isinstance(data, dict):
            if "data" in data:
                return data["data"]
            if "matches" in data:
                return data["matches"]
            return []

        if isinstance(data, list):
            return data

        return []
    except Exception as e:
        logger.error(f"get_matches Error: {e}")
        return []

# ===== جلب الفرق من المباريات (بدل endpoint منفصل) =====
def get_epl_teams():
    try:
        matches = get_matches()
        if not matches:
            logger.warning("No matches returned, cannot extract teams")
            return []

        teams_dict = {}

        for m in matches:
            # الفريق الأول
            t1_id = m.get("teamId1")
            if t1_id and t1_id not in teams_dict:
                teams_dict[t1_id] = {
                    "id": t1_id,
                    "name": m.get("teamName1", ""),
                    "nameAr": m.get("teamNameAr1") or m.get("teamName1", ""),
                }

            # الفريق الثاني
            t2_id = m.get("teamId2")
            if t2_id and t2_id not in teams_dict:
                teams_dict[t2_id] = {
                    "id": t2_id,
                    "name": m.get("teamName2", ""),
                    "nameAr": m.get("teamNameAr2") or m.get("teamName2", ""),
                }

        teams = sorted(
            teams_dict.values(),
            key=lambda t: t.get("nameAr") or t.get("name") or ""
        )
        logger.info(f"Extracted {len(teams)} teams from matches")
        return teams

    except Exception as e:
        logger.error(f"get_epl_teams Error: {e}")
        return []

# ===== مباريات فريق معين =====
def get_matches_for_team(team_id):
    try:
        matches = get_matches()
        if not matches:
            return []

        return [
            m for m in matches
            if m.get("teamId1") == team_id or m.get("teamId2") == team_id
        ]
    except Exception as e:
        logger.error(f"get_matches_for_team Error: {e}")
        return []

# ===== مباريات التذاكر متاحة فيها =====
def get_available_matches_for_team(team_id):
    try:
        matches = get_matches_for_team(team_id)
        return [m for m in matches if m.get("matchStatus") == 1]
    except Exception as e:
        logger.error(f"get_available_matches_for_team Error: {e}")
        return []
