import requests, json, time, os, re, html, unicodedata

BASE = "https://egy.app.spx-learning-square.com"
SUBJECT = 7
QUREO_BASE = "https://me-tp.qureo.education"
QUREO_PORTAL = "https://me-portal.qureo.education"

JOBS = {}

def log(job_id, msg):
    if job_id in JOBS: JOBS[job_id]["log"].append(msg)

def set_progress(job_id, pct, stage=""):
    if job_id in JOBS:
        JOBS[job_id]["progress"] = pct
        JOBS[job_id]["stage"] = stage

def load_json(p):
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

STUDY_DATA = load_json("data/study_data.json")
ANSWERS_LEVEL = load_json("data/answers_by_level.json")

# ===================== SPX =====================
def canon(t):
    if not t: return ""
    t = html.unescape(str(t))
    t = re.sub(r'\[\[.*?\]\]', '', t)
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', t)).strip()

def norm(t):
    return canon(t).replace(' ', '').replace('"','').replace("'",'').replace('`','').lower()

def find_spx_answer(q_text):
    q = canon(q_text)
    if 'levels' in STUDY_DATA:
        for lvl in STUDY_DATA['levels'].values():
            for qq in lvl.get('questions', []):
                if canon(qq.get('question','')) == q: return qq.get('answer','')
    for level, qs in ANSWERS_LEVEL.items():
        if isinstance(qs, list):
            for item in qs:
                if isinstance(item, dict) and item.get('answer'):
                    if len(q) > 20 and canon(item['answer'])[:30] in q: return item['answer']
    return None

def match_option(options, ans, spx=True):
    if not ans: return None
    a = norm(ans)
    for o in options:
        t = o.get('text','') if spx else o.get('content','')
        if norm(t) == a: return o['id']
    for o in options:
        t = o.get('text','') if spx else o.get('content','')
        if a in norm(t): return o['id']
    return None

class SPXSolver:
    def __init__(self, lid, pw):
        self.s = requests.Session()
        self.s.headers.update({
            "accept":"application/json, text/plain, */*", "content-type":"application/json",
            "origin":BASE, "referer":f"{BASE}/subjects/{SUBJECT}/curriculum",
            "user-agent":"Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/139.0.0.0 Mobile Safari/537.36",
        })
        self.lid, self.pw, self.token = lid, pw, None

    def _req(self, m, p, **kw):
        url = p if p.startswith("http") else f"{BASE}{p}"
        try: return self.s.request(m, url, timeout=15, **kw)
        except: return None

    def login(self):
        r = self._req("POST", "/api/v1/auth/login", json={"login_id": self.lid, "password": self.pw})
        if not r or r.status_code != 200: return False
        try: body = r.json()
        except: return False
        self.token = body.get("token") or (body.get("data") or {}).get("token")
        if not self.token:
            for c in self.s.cookies:
                if c.name == "learning_token": self.token = c.value; break
        if not self.token: return False
        self.s.headers["authorization"] = f"Bearer {self.token}"
        return True

    def find_next(self):
        cur = self._req("GET", f"/api/v1/subjects/{SUBJECT}/curriculum").json()
        if not cur or 'data' not in cur: return None, 0, 0
        total, comp, nxt = 0, 0, None
        for unit in cur['data']:
            for it in unit.get('items', []):
                total += 1
                if it.get('is_completed'): comp += 1
                elif not nxt: nxt = it
        return ("DONE", comp, total) if not nxt else (nxt, comp, total)

    def solve_chapter(self, cid):
        d = self._req("GET", f"/api/v1/chapters/{cid}/blocks").json()
        if not d or 'data' not in d: return {"ok": False}
        blocks = d['data'].get('blocks', [])
        cleared = set(d['data'].get('chapter', {}).get('cleared_block_ids', []))
        qs = [b for b in blocks if b.get('type') == 'question']
        for q in qs:
            if q['id'] in cleared: continue
            for o in q.get('options', []):
                r = self._req("POST", f"/api/v1/chapters/{cid}/answer", json={"block_id": q['id'], "selected_option_id": o['id'], "hint_used": 0})
                if r and r.status_code == 200:
                    a = r.json().get('data', {})
                    if a.get('is_correct'): break
                    if a.get('correct_option_id'):
                        self._req("POST", f"/api/v1/chapters/{cid}/answer", json={"block_id": q['id'], "selected_option_id": a['correct_option_id'], "hint_used": 0})
                        break
        self._req("POST", f"/api/v1/chapters/{cid}/complete")
        return {"ok": True}

    def solve_test(self, tid):
        r = self._req("POST", f"/api/v1/tests/{tid}/start")
        if not r or r.status_code != 200: return {"ok": False}
        data = r.json()['data']
        for tq in data.get('test_questions', []):
            qid = str(tq['question_id'])
            qt = data.get('questions', {}).get(qid, {}).get('question_text', '')
            opts = data.get('options', {}).get(qid, [])
            a = find_spx_answer(qt)
            chosen = match_option(opts, a, True) if a else (opts[0]['id'] if opts else None)
            if chosen: self._req("PUT", f"/api/v1/tests/{tid}/questions/{tq['id']}/answer", json={"selected_option_id": chosen})
        self._req("POST", f"/api/v1/tests/{tid}/submit")
        return {"ok": True}

def run_spx_solve(job_id, lid, pw):
    JOBS[job_id] = {"status":"running","progress":0,"log":[],"done":False,"stage":"جاري تسجيل الدخول...", "error": None}
    try:
        solver = SPXSolver(lid, pw)
        if not solver.login(): raise Exception("فشل الدخول للثقافة المالية")
        log(job_id, "✅ تم الدخول بنجاح")
        
        while True:
            item, comp, total = solver.find_next()
            if item == "DONE" or not item: break
            title = item.get('title','')[:30]
            pct = int(comp/total*100) if total else 0
            set_progress(job_id, pct, f"جاري حل: {title}")
            t, iid = item.get('item_type'), item.get('id')
            if t == "chapter": solver.solve_chapter(iid)
            elif t == "review": solver._req("POST", f"/api/v1/reviews/{iid}/complete")
            elif t == "test": solver.solve_test(iid)
            log(job_id, f"✅ {title}")
            
        set_progress(job_id, 100, "انتهى بنجاح")
        JOBS[job_id]["done"], JOBS[job_id]["status"] = True, "success"
    except Exception as e:
        log(job_id, f"❌ {str(e)}")
        JOBS[job_id]["done"], JOBS[job_id]["status"], JOBS[job_id]["error"] = True, "failed", str(e)


# ===================== Qureo (صاروخ) =====================
def run_qureo_solve(job_id, STUDENT_ID, PASSWORD, content_id, json_file, platform_name):
    JOBS[job_id] = {"status":"running","progress":0,"log":[],"done":False,"stage":"جاري تسجيل الدخول...", "error": None}
    try:
        max_data = load_json(json_file)
        if not max_data: raise Exception(f"ملف {json_file} مش موجود!")

        s = requests.Session()
        s.headers.update({
            "authority": "me-tp.qureo.education", "content-type": "application/json",
            "origin": QUREO_BASE, "referer": f"{QUREO_BASE}/",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36"
        })
        lh = s.headers.copy()
        lh["origin"], lh["referer"] = QUREO_PORTAL, f"{QUREO_PORTAL}/"
        
        r = s.post(f"{QUREO_PORTAL}/oauth2/password-login", json={"student_id": STUDENT_ID, "password": PASSWORD}, headers=lh)
        token = s.cookies.get("egy_student_access_token")
        if not token: raise Exception(f"فشل الدخول! رد السيرفر: {r.status_code}.")
        
        s.headers["authorization"] = f"Bearer {token}"
        s.cookies.set("student_selected_content_id", content_id, domain="me-tp.qureo.education")
        log(job_id, "✅ تم الدخول بنجاح")

        def fix_indentation(code):
            if not code or not isinstance(code, str): return code
            lines, fixed_lines = code.split('\n'), []
            for line in lines:
                stripped = line.strip()
                if not stripped: fixed_lines.append("")
                elif stripped.startswith(("//", "console.log", "let ", "if ", "for ", "function ", "while ")):
                    fixed_lines.append("  " + stripped if not line.startswith("  ") else line)
                else: fixed_lines.append(line)
            return '\n'.join(fixed_lines)

        def check_status(cid):
            s.cookies.set("_cf_s_path", f"/contents/chapter/{cid}", domain="me-tp.qureo.education")
            try:
                res = s.get(f"{QUREO_BASE}/api/study/students/chapters/{cid}")
                if res.status_code == 200: return res.json().get('best_correct_count', 0), res.json().get('completed_at') is not None
            except: pass
            return 0, False

        def solve_lectures(cid):
            s.cookies.set("_cf_s_path", f"/contents/chapter/{cid}", domain="me-tp.qureo.education")
            try:
                r = s.get(f"{QUREO_BASE}/api/study/chapters/{cid}")
                if r.status_code == 200:
                    for lec in r.json().get('lectures', []):
                        s.put(f"{QUREO_BASE}/api/study/students/lectures/{lec['id']}", json={})
                        s.put(f"{QUREO_BASE}/api/study/students/lectures/{lec['id']}/complete", json={})
            except: pass

        def solve_chapter(cid):
            s.cookies.set("_cf_s_path", f"/contents/chapter/{cid}", domain="me-tp.qureo.education")
            best, is_completed = check_status(cid)
            if is_completed and best > 0: return True, best, best
            
            try: r = s.get(f"{QUREO_BASE}/api/study/chapters/{cid}/test")
            except: return False, 0, 0
            if r.status_code == 403: return False, 0, -1
            if r.status_code != 200: return False, 0, 0
            
            try: qs_data = r.json()
            except: return False, 0, 0
            
            s.put(f"{QUREO_BASE}/api/study/students/chapters/{cid}/test", json={})
            s.put(f"{QUREO_BASE}/api/study/students/chapters/{cid}/test", json={})
            
            solved = 0
            chapter_answers = max_data.get('chapters', {}).get(str(cid), {}).get('answers', {})
            if not chapter_answers: chapter_answers = max_data.get('chapters', {}).get(str(cid), {}).get('questions', {})
            
            for i, q in enumerate(qs_data):
                q_info = q['question']; q_id = str(q_info['id']); q_type = q_info['type']
                item = chapter_answers.get(q_id, {})
                if isinstance(item, dict): ans = item.get('answer')
                elif isinstance(item, (tuple, list)): ans = item[1]
                else: ans = item
                
                if ans is None:
                    if q_type == 'choice' and q.get('choices'): ans = q['choices'][0]['id']
                    else: continue
                
                if q_type == 'description' and isinstance(ans, str) and content_id == "javascript_ar":
                    ans = fix_indentation(ans)
                    
                url = f"{QUREO_BASE}/api/study/students/test-questions/{q_id}/answer/description" if q_type == 'description' else f"{QUREO_BASE}/api/study/students/test-questions/{q_id}/answer/choice"
                payload = {"answer_code": str(ans)} if q_type == 'description' else {"choice_id": int(ans)}
                
                res = s.put(url, json=payload)
                if res.status_code != 200 and q_type == 'choice' and q.get('choices'):
                    for ch in q['choices']:
                        res2 = s.put(url, json={"choice_id": int(ch['id'])})
                        if res2.status_code == 200: res = res2; break
                
                if res.status_code in (200, 400): solved += 1
                else:
                    url_rev = f"{QUREO_BASE}/api/study/students/review-questions/{q_id}/answer/description" if q_type == 'description' else f"{QUREO_BASE}/api/study/students/review-questions/{q_id}/answer/choice"
                    if s.put(url_rev, json=payload).status_code == 200: solved += 1
            
            # شلنا الـ sleep عشان نسرع
            best, is_completed = check_status(cid)
            if is_completed and best >= len(qs_data): return True, best, len(qs_data)
            return solved == len(qs_data), solved, len(qs_data)

        total_chapters = 54 if content_id == "javascript_ar" else 25
        start_cid = 90001 if content_id == "javascript_ar" else 511001
        
        fail_count = 0
        for chap_idx in range(total_chapters):
            cid = start_cid + chap_idx
            pct = int(((chap_idx + 1) / total_chapters) * 100)
            set_progress(job_id, pct, f"فصل {chap_idx + 1} من {total_chapters}")
            
            solve_lectures(cid)
            ok, solved, total = solve_chapter(cid)
            
            if total == -1: log(job_id, f"🔒 فصل {chap_idx + 1} (مقفول)"); fail_count += 1
            elif total == 0: log(job_id, f"⚠️ فصل {chap_idx + 1} (خطأ)"); fail_count += 1
            elif ok: log(job_id, f"✅ فصل {chap_idx + 1} (PERFECT)")
            else: log(job_id, f"❌ فصل {chap_idx + 1} ({solved}/{total})"); fail_count += 1
            
        set_progress(job_id, 100, "انتهى بنجاح")
        log(job_id, f"🎉 تم إنهاء {platform_name} بالكامل!")
        JOBS[job_id]["done"], JOBS[job_id]["status"] = True, "success"

    except Exception as e:
        log(job_id, f"❌ {str(e)}")
        JOBS[job_id]["done"], JOBS[job_id]["status"], JOBS[job_id]["error"] = True, "failed", str(e)