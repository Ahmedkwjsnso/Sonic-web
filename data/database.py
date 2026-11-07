import hashlib
import time

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

MEMORY_DB = {
    "users": {},
    "stats": {"total_users": 0, "success": 0, "failed": 0}
}

def init_owner_account():
    owner_user = "SONIC10"
    if owner_user not in MEMORY_DB["users"]:
        MEMORY_DB["users"][owner_user] = {
            "password": hash_password("SONIC10"),
            "credits": "max",
            "vip": "1",
            "banned": "0",
            "last_seen": time.time(),
            "solved": {"python": 0, "js": 0, "spx": 0}
        }
init_owner_account()

def create_user(username: str, password_hash: str) -> bool:
    if username in MEMORY_DB["users"]: return False
    
    MEMORY_DB["users"][username] = {
        "password": password_hash,
        "credits": "3", # 3 فرص للجميع
        "vip": "0",
        "banned": "0",
        "last_seen": time.time(),
        "solved": {"python": 0, "js": 0, "spx": 0}
    }
    MEMORY_DB["stats"]["total_users"] += 1
    return True

def get_user(username: str) -> dict: return MEMORY_DB["users"].get(username)

def get_user_credits(username: str) -> str:
    user = get_user(username)
    if not user: return "0"
    if user.get("vip") == "1": return "max"
    return user.get("credits", "0")

def update_credits(username: str, amount: int):
    if username not in MEMORY_DB["users"]: return False
    if MEMORY_DB["users"][username].get("vip") == "1": return True
    current = int(MEMORY_DB["users"][username]["credits"])
    MEMORY_DB["users"][username]["credits"] = str(max(0, current + amount))
    return True

def set_vip(username: str, is_vip: bool):
    if username not in MEMORY_DB["users"]: return False
    MEMORY_DB["users"][username]["vip"] = "1" if is_vip else "0"
    return True

def set_banned(username: str, is_banned: bool):
    if username not in MEMORY_DB["users"]: return False
    MEMORY_DB["users"][username]["banned"] = "1" if is_banned else "0"
    return True

def is_banned(username: str) -> bool:
    user = get_user(username)
    return user.get("banned") == "1" if user else False

def update_activity(username: str):
    if username in MEMORY_DB["users"]:
        MEMORY_DB["users"][username]["last_seen"] = time.time()

def increment_solved(username: str, platform: str):
    if username in MEMORY_DB["users"]:
        if "solved" not in MEMORY_DB["users"][username]:
            MEMORY_DB["users"][username]["solved"] = {"python": 0, "js": 0, "spx": 0}
        MEMORY_DB["users"][username]["solved"][platform] = MEMORY_DB["users"][username]["solved"].get(platform, 0) + 1

def get_all_users_admin() -> list:
    users_list = []
    now = time.time()
    for uname, udata in MEMORY_DB["users"].items():
        is_online = (now - udata.get("last_seen", 0)) < 300 
        users_list.append({
            "username": uname,
            "credits": "VIP" if udata.get("vip") == "1" else udata.get("credits", "0"),
            "banned": udata.get("banned") == "1",
            "online": is_online,
            "solved_python": udata.get("solved", {}).get("python", 0),
            "solved_js": udata.get("solved", {}).get("js", 0),
            "solved_spx": udata.get("solved", {}).get("spx", 0),
            "total_solved": sum(udata.get("solved", {}).values())
        })
    return users_list

def get_online_count() -> int:
    now = time.time()
    count = 0
    for udata in MEMORY_DB["users"].values():
        if (now - udata.get("last_seen", 0)) < 300:
            count += 1
    return count

def get_stats() -> dict:
    return {
        "users": MEMORY_DB["stats"]["total_users"],
        "success": MEMORY_DB["stats"]["success"],
        "failed": MEMORY_DB["stats"]["failed"]
    }
