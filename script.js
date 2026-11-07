let token = localStorage.getItem('sonic_token') || null;
let username = localStorage.getItem('sonic_user') || null;
let platform = null, currentJob = null, isLoginMode = true;

async function api(path, method = 'GET', body = null) {
  const headers = {};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  if (body) headers['Content-Type'] = 'application/json';
  
  const r = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : null });
  const data = await r.json().catch(() => ({}));
  
  if (!r.ok) throw new Error(data.detail || 'حدث خطأ في الاتصال بالسيرفر');
  return data;
}

// جلب المتصلين والصدارة
async function loadPublicData() {
  try {
    const data = await api('/api/leaderboard');
    document.getElementById('onlineCount').textContent = data.online;
    
    const list = document.getElementById('leaderboardList');
    if (data.leaderboard.length === 0) {
      list.innerHTML = '<p style="text-align:center;color:#aaa;">لا يوجد بيانات بعد.</p>';
      return;
    }

    list.innerHTML = data.leaderboard.map((u, i) => `
      <div class="lb-row">
        <span class="lb-rank">${i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '#' + (i+1)}</span>
        <span class="lb-name">${u.username} ${u.online ? '🟢' : '⚪'}</span>
        <span class="lb-score">${u.total_solved} حل</span>
      </div>
    `).join('');
  } catch (e) { console.error(e); }
}

function toggleDashboard() {
  const db = document.getElementById('dashboardBox');
  db.classList.toggle('hidden');
  if (!db.classList.contains('hidden')) loadPublicData();
}

// تحديث العداد كل 15 ثانية
setInterval(() => { if (!document.getElementById('dashboardBox').classList.contains('hidden')) loadPublicData(); }, 15000);

function toggleAuth() {
  isLoginMode = !isLoginMode;
  document.getElementById('authTitle').textContent = isLoginMode ? 'تسجيل الدخول' : 'إنشاء حساب جديد';
  document.getElementById('authBtn').textContent = isLoginMode ? 'دخول' : 'تسجيل';
  document.getElementById('authSwitch').textContent = isLoginMode ? 'معندكش حساب؟ سجل دلوقتي' : 'عندك حساب؟ سجل دخول';
  document.getElementById('authError').textContent = '';
}

document.getElementById('authBtn').onclick = async () => {
  const u = document.getElementById('username').value.trim();
  const p = document.getElementById('password').value.trim();
  const err = document.getElementById('authError');
  err.textContent = '';
  
  if (!u || !p) { err.textContent = 'املأ كل الحقول'; return; }
  
  try {
    const d = await api(isLoginMode ? '/api/login' : '/api/register', 'POST', { username: u, password: p });
    token = d.token; username = d.username;
    localStorage.setItem('sonic_token', token);
    localStorage.setItem('sonic_user', username);
    loadUserPanel();
  } catch (e) {
    err.textContent = e.message;
  }
};

async function loadUserPanel() {
  try {
    const me = await api('/api/me');
    document.getElementById('authBox').classList.add('hidden');
    document.getElementById('userPanel').classList.remove('hidden');
    document.getElementById('welcomeName').textContent = me.username;
    
    const creditInfo = document.getElementById('creditInfo');
    if (me.is_vip) {
      creditInfo.textContent = '💎 VIP — فرص لا نهائية';
      creditInfo.style.color = '#00ff00';
    } else {
      creditInfo.textContent = `📊 رصيدك: ${me.credits} فرصة`;
      creditInfo.style.color = '#ff8899';
    }

    if (me.solved) {
      document.getElementById('dash_python').textContent = me.solved.python || 0;
      document.getElementById('dash_js').textContent = me.solved.js || 0;
      document.getElementById('dash_spx').textContent = me.solved.spx || 0;
    }
  } catch (e) {
    logout();
  }
}

function logout() {
  localStorage.removeItem('sonic_token');
  localStorage.removeItem('sonic_user');
  token = null; username = null;
  document.getElementById('userPanel').classList.add('hidden');
  document.getElementById('authBox').classList.remove('hidden');
  document.getElementById('password').value = '';
}

document.querySelectorAll('.btn-red[data-p]').forEach(b => {
  b.onclick = () => {
    platform = b.dataset.p;
    document.getElementById('platforms').classList.add('hidden');
    document.getElementById('loginBox').classList.remove('hidden');
    document.getElementById('selected').textContent = {
      js: '☕ JavaScript', python: '🐍 Python', spx: '💰 الثقافة المالية'
    }[platform];
  };
});

document.getElementById('startBtn').onclick = async () => {
  const lid = document.getElementById('login_id').value.trim();
  const pw = document.getElementById('password2').value.trim();
  if (!lid || !pw) return alert('املأ كود المنصة والباسورد');

  const btn = document.getElementById('startBtn');
  btn.disabled = true;
  btn.textContent = '⏳ جاري البدء...';

  try {
    const d = await api('/api/solve', 'POST', { platform, login_id: lid, password: pw });
    currentJob = d.job_id;
    document.getElementById('loginBox').classList.add('hidden');
    document.getElementById('progressBox').classList.remove('hidden');
    document.getElementById('log').innerHTML = '';
    document.getElementById('stage').textContent = 'جاري التجهيز...';
    document.getElementById('stage').style.color = '#ff8899';
    pollJob();
  } catch (e) {
    alert(e.message);
    btn.disabled = false;
    btn.textContent = '🚀 بدء الحل';
  }
};

async function pollJob() {
  if (!currentJob) return;
  try {
    const j = await api('/api/job/' + currentJob);
    document.getElementById('fill').style.width = j.progress + '%';
    document.getElementById('stage').textContent = `🎯 ${j.stage || ''}`;
    
    const logDiv = document.getElementById('log');
    logDiv.innerHTML = (j.log || []).map(l => `<div>${l}</div>`).join('');
    logDiv.scrollTop = logDiv.scrollHeight;
    
    if (!j.done) {
      setTimeout(pollJob, 1500);
    } else {
      const stageText = document.getElementById('stage');
      const btn = document.getElementById('startBtn');
      
      if (j.status === 'failed') {
        stageText.textContent = '❌ فشل الحل! (اقرأ التفاصيل)';
        stageText.style.color = '#ff3333';
      } else {
        stageText.textContent = '🎉 تم الانتهاء بنجاح!';
        stageText.style.color = '#00ff00';
      }
      
      setTimeout(() => {
        btn.disabled = false;
        btn.textContent = '🚀 بدء الحل';
      }, 3000);
      
      loadUserPanel();
    }
  } catch (e) { setTimeout(pollJob, 3000); }
}

if (token && username) { loadUserPanel(); }
// تحميل المتصلين لأول مرة
loadPublicData();