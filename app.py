from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uuid, threading

from solver import run_spx_solve, run_qureo_solve, JOBS
from database import (
    hash_password, verify_password, create_user, get_user, 
    get_user_credits, update_credits, set_vip, set_banned, 
    is_banned, get_all_users_admin, get_stats,
    update_activity, increment_solved, get_online_count
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

ADMIN_PASSWORD = "SONIC_SECRET_2024"
SESSIONS = {}

class AuthReq(BaseModel):
    username: str
    password: str

class SolveReq(BaseModel):
    platform: str
    login_id: str
    password: str

class AdminReq(BaseModel):
    username: str
    amount: Optional[int] = 0

def auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401, "غير مصرح")
    tok = authorization.replace("Bearer ", "")
    if tok not in SESSIONS: raise HTTPException(401, "انتهت الجلسة")
    return SESSIONS[tok]

def admin_auth(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_PASSWORD: raise HTTPException(403, "غير مصرح")
    return True

@app.get("/")
def home(): return FileResponse("static/index.html")

@app.get("/admin-sonic-x")
def admin_page(): return FileResponse("static/admin.html")

@app.post("/api/register")
def register(req: AuthReq):
    if req.username.upper() == "SONIC10":
        raise HTTPException(403, "هذا الاسم مخصص لمالك الموقع فقط!")
    if len(req.password) < 6: 
        raise HTTPException(400, "الباسورد ضعيف (6 حروف على الأقل)")
    if not create_user(req.username, hash_password(req.password)):
        raise HTTPException(400, "الاسم محجوز")
    tok = str(uuid.uuid4()); SESSIONS[tok] = req.username
    return {"token": tok, "username": req.username}

@app.post("/api/login")
def login(req: AuthReq):
    if req.username.upper() == "SONIC10" and req.password == "SONIC10":
        tok = str(uuid.uuid4()); SESSIONS[tok] = "SONIC10"
        return {"token": tok, "username": "SONIC10"}

    user = get_user(req.username)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(401, "بيانات الدخول غلط")
    if user.get("banned") == "1": raise HTTPException(403, "محظور")
    tok = str(uuid.uuid4()); SESSIONS[tok] = req.username
    return {"token": tok, "username": req.username}

@app.get("/api/me")
def me(username: str = Depends(auth)):
    update_activity(username)
    c = get_user_credits(username)
    user = get_user(username)
    return {
        "username": username, 
        "credits": "max" if c == "max" else int(c), 
        "is_vip": c == "max",
        "solved": user.get("solved", {"python": 0, "js": 0, "spx": 0})
    }

@app.get("/api/leaderboard")
def leaderboard():
    # جلب كل المستخدمين وترتيبهم حسب إجمالي الحل
    users = get_all_users_admin()
    users.sort(key=lambda x: x["total_solved"], reverse=True)
    return {"leaderboard": users[:5], "online": get_online_count()}

@app.post("/api/solve")
def solve(req: SolveReq, username: str = Depends(auth)):
    update_activity(username)
    if is_banned(username): raise HTTPException(403, "محظور")
    c = get_user_credits(username)
    if c != "max" and int(c) <= 0: raise HTTPException(402, "لا يوجد فرص")
    
    jid = str(uuid.uuid4())
    if req.platform == "spx":
        threading.Thread(target=run_spx_solve, args=(jid, req.login_id, req.password), daemon=True).start()
    elif req.platform == "js":
        threading.Thread(target=run_qureo_solve, args=(jid, req.login_id, req.password, "javascript_ar", "data/javascript_final_db.json", "JavaScript"), daemon=True).start()
    elif req.platform == "python":
        threading.Thread(target=run_qureo_solve, args=(jid, req.login_id, req.password, "python_short_ar", "data/max.json", "Python"), daemon=True).start()
    else: raise HTTPException(400, "منصة غلط")
    
    if c != "max": update_credits(username, -1)
    increment_solved(username, req.platform)
    return {"job_id": jid}

@app.get("/api/job/{jid}")
def job(jid: str, username: str = Depends(auth)):
    update_activity(username)
    if jid not in JOBS: raise HTTPException(404, "غير موجود")
    return JOBS[jid]

@app.get("/api/admin/verify")
def verify_admin_api(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_PASSWORD: raise HTTPException(403, "غلط")
    return {"ok": True}

@app.get("/api/admin/list")
def list_users(_=Depends(admin_auth)):
    return {"users": get_all_users_admin(), "stats": get_stats()}

@app.post("/api/admin/vip")
def admin_vip(a: AdminReq, _=Depends(admin_auth)):
    if not set_vip(a.username, True): raise HTTPException(404)
    return {"ok": True}

@app.post("/api/admin/add")
def admin_add(a: AdminReq, _=Depends(admin_auth)):
    if not update_credits(a.username, a.amount): raise HTTPException(404)
    return {"ok": True}

@app.post("/api/admin/ban")
def admin_ban(a: AdminReq, _=Depends(admin_auth)):
    if not set_banned(a.username, True): raise HTTPException(404)
    return {"ok": True}

@app.post("/api/admin/unban")
def admin_unban(a: AdminReq, _=Depends(admin_auth)):
    if not set_banned(a.username, False): raise HTTPException(404)
    return {"ok": True}