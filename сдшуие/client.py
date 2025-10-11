# server.py
import os, json, time, pathlib, collections
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, abort, g

ADMIN_LOGIN = "praroditel"
ADMIN_PASS  = "Prarod"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me")

app = Flask(__name__)
app.secret_key = SESSION_SECRET
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=False, SESSION_COOKIE_NAME="sess", PERMANENT_SESSION_LIFETIME=60*60)

DATA_DIR = pathlib.Path("data"); DATA_DIR.mkdir(exist_ok=True)
BANS_PATH = DATA_DIR / "bans.json"
LOGS_PATH = DATA_DIR / "logs.json"
TOTALS_PATH = DATA_DIR / "totals.json"

def now_ts(): return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def load_json(path, default):
    if not path.exists(): return default
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def append_log(entry):
    logs = load_json(LOGS_PATH, [])
    logs.append(entry)
    if len(logs) > 10000:
        logs = logs[-10000:]
    save_json(LOGS_PATH, logs)

def increment_total(t):
    totals = load_json(TOTALS_PATH, {"inject":0,"key":0,"button":0,"konfetki":0,"admin":0,"misc":0})
    if t not in totals:
        t = "misc"
    totals[t] = totals.get(t, 0) + 1
    save_json(TOTALS_PATH, totals)

@app.before_request
def _ctx():
    g.logged_in = bool(session.get("logged_in"))
    g.is_admin  = bool(session.get("is_admin"))

def require_admin():
    if not g.logged_in or not g.is_admin:
        abort(403)

BASE = """
{% macro badge(text, color) -%}
<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-{{color}}-100 text-{{color}}-800">{{ text }}</span>
{%- endmacro %}
{% macro layout(title, body, toast=None) -%}
<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }}</title><script src="https://cdn.tailwindcss.com"></script>
</head><body class="bg-slate-50 text-slate-900">
<header class="border-b bg-white/80 backdrop-blur sticky top-0 z-10">
  <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
    <a href="{{ url_for('index') }}" class="font-bold text-lg">✨ Holdik Hub Panel</a>
    <nav class="flex items-center gap-2">
      {% if g.logged_in %}
        <a href="{{ url_for('admin_dashboard') }}" class="rounded-lg px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800">Админка</a>
        <a href="{{ url_for('admin_users') }}" class="rounded-lg px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800">Users</a>
        <a href="{{ url_for('admin_logs') }}" class="rounded-lg px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800">Логи</a>
        <a href="{{ url_for('logout') }}" class="rounded-lg px-3 py-1.5 hover:bg-slate-100">Выйти</a>
      {% else %}
        <a href="{{ url_for('login') }}" class="rounded-lg px-3 py-1.5 border border-slate-300 hover:bg-slate-100">Войти</a>
      {% endif %}
    </nav>
  </div>
</header>
{% if toast %}<div class="max-w-2xl mx-auto mt-4 px-4"><div class="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-emerald-800">{{ toast }}</div></div>{% endif %}
<main class="max-w-7xl mx-auto px-4 py-6">{{ body|safe }}</main>
<footer class="py-8 text-center text-sm text-slate-500">made by prarod😋</footer>
</body></html>{%- endmacro %}
"""

@app.get("/")
def index():
    tpl = BASE + """
    {% set body %}
    <div class="grid md:grid-cols-2 gap-6">
      <section class="bg-white rounded-2xl shadow-sm border p-6">
        <h1 class="text-2xl font-semibold mb-2">Панель Holdik Hub</h1>
        <p class="text-slate-600">Баны HWID + one-shot kick + сгруппированные логи.</p>
        {% if not g.logged_in %}
          <a href="{{ url_for('login') }}" class="mt-4 inline-flex rounded-xl px-5 py-3 border border-slate-300 bg-white hover:bg-slate-100">Войти</a>
        {% else %}
          <div class="mt-4 flex gap-3">
            <a href="{{ url_for('admin_dashboard') }}" class="inline-flex rounded-xl px-5 py-3 bg-slate-900 text-white hover:bg-slate-800">Админка</a>
            <a href="{{ url_for('admin_users') }}" class="inline-flex rounded-xl px-5 py-3 border hover:bg-slate-100">Users</a>
          </div>
        {% endif %}
      </section>
      <section class="bg-white rounded-2xl shadow-sm border p-6">
        <h2 class="text-xl font-semibold mb-2">API</h2>
        <ul class="list-disc pl-5 text-slate-700 space-y-2">
          <li>GET /api/check?hwid=...</li>
          <li>GET /api/should-kick?hwid=...</li>
          <li>POST /api/log</li>
          <li>GET /api/banlist.json</li>
          <li>GET /api/totals</li>
          <li>GET /ping</li>
        </ul>
      </section>
    </div>
    {% endset %} {{ layout('Главная', body) }}
    """
    return render_template_string(tpl)

@app.route("/login", methods=["GET","POST"])
def login():
    toast=None
    if request.method=="POST":
        if (request.form.get("login") or "").strip()==ADMIN_LOGIN and (request.form.get("password") or "").strip()==ADMIN_PASS:
            session.clear(); session["logged_in"]=True; session["is_admin"]=True
            return redirect(url_for("admin_dashboard"))
        toast="Неверный логин или пароль."
    tpl = BASE + """
    {% set body %}
    <div class="max-w-md mx-auto bg-white rounded-2xl shadow-sm border p-6">
      <h1 class="text-2xl font-semibold mb-4">Вход</h1>
      <form method="post" class="space-y-3">
        <input name="login" placeholder="Логин" class="w-full px-3 py-2 border rounded-lg">
        <input name="password" type="password" placeholder="Пароль" class="w-full px-3 py-2 border rounded-lg">
        <button class="w-full rounded-lg px-4 py-2 bg-slate-900 text-white hover:bg-slate-800">Войти</button>
      </form>
    </div>
    {% endset %} {{ layout('Вход', body, toast) }}
    """
    return render_template_string(tpl, toast=toast)

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.get("/admin")
def admin_dashboard():
    require_admin()
    data = load_json(BANS_PATH, {"bans": {}, "kick_once": {}})
    bans = data.get("bans", {})
    totals = load_json(TOTALS_PATH, {"inject":0,"key":0,"button":0,"konfetki":0,"admin":0,"misc":0})
    tpl = BASE + """
    {% set body %}
    <div class="grid xl:grid-cols-2 gap-6">
      <section class="bg-white rounded-2xl shadow-sm border p-6 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-semibold">HWID Ban / Kick</h2> {{ badge('online', 'emerald') }}
        </div>
        <form action="{{ url_for('admin_ban_add') }}" method="post" class="grid md:grid-cols-3 gap-2">
          <input name="hwid" placeholder="HWID..." class="px-3 py-2 border rounded-lg">
          <input name="reason" placeholder="Причина (опц.)" class="px-3 py-2 border rounded-lg">
          <button class="px-4 py-2 rounded-lg bg-rose-600 text-white hover:bg-rose-700">Добавить бан</button>
        </form>
        <form action="{{ url_for('admin_ban_del') }}" method="post" class="grid md:grid-cols-3 gap-2">
          <input name="hwid" placeholder="HWID..." class="px-3 py-2 border rounded-lg">
          <div></div>
          <button class="px-4 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-800">Снять бан</button>
        </form>
        <form action="{{ url_for('admin_kick_once') }}" method="post" class="grid md:grid-cols-3 gap-2">
          <input name="hwid" placeholder="HWID..." class="px-3 py-2 border rounded-lg">
          <input name="reason" placeholder="Причина kick (опц.)" class="px-3 py-2 border rounded-lg">
          <button class="px-4 py-2 rounded-lg bg-orange-600 text-white hover:bg-orange-700">Кикнуть (one-shot)</button>
        </form>
        <div class="overflow-hidden rounded-xl border">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50"><tr class="text-left"><th class="py-2 px-3">HWID</th><th class="py-2 px-3">Причина</th><th class="py-2 px-3">Добавлен</th></tr></thead>
            <tbody>
              {% for hwid,info in bans.items() %}
              <tr class="border-t hover:bg-slate-50">
                <td class="py-2 px-3 font-mono text-[12px]">{{ hwid }}</td>
                <td class="py-2 px-3">{{ info.get('reason','') }}</td>
                <td class="py-2 px-3 text-slate-500">{{ info.get('ts','') }}</td>
              </tr>
              {% endfor %}
              {% if not bans %}<tr><td colspan="3" class="py-6 px-3 text-center text-slate-500">Пока пусто</td></tr>{% endif %}
            </tbody>
          </table>
        </div>
      </section>
      <section class="bg-white rounded-2xl shadow-sm border p-6">
        <h2 class="text-xl font-semibold mb-2">Шорткаты / Totals</h2>
        <div class="grid sm:grid-cols-2 gap-3">
          <a href="{{ url_for('admin_logs') }}?type=inject"   class="rounded-xl border p-4 hover:bg-slate-50 flex items-center justify-between"><div>Инжект логи</div> {{ badge('👾','violet') }}</a>
          <a href="{{ url_for('admin_logs') }}?type=key"      class="rounded-xl border p-4 hover:bg-slate-50 flex items-center justify-between"><div>Кей логи</div>     {{ badge('🔑','amber') }}</a>
          <a href="{{ url_for('admin_logs') }}?type=button"   class="rounded-xl border p-4 hover:bg-slate-50 flex items-center justify-between"><div>Кнопки</div>       {{ badge('🖱️','slate') }}</a>
          <a href="{{ url_for('admin_logs') }}?type=konfetki" class="rounded-xl border p-4 hover:bg-slate-50 flex items-center justify-between"><div>Конфетки</div>     {{ badge('🍬','pink') }}</a>
        </div>
        <div class="mt-4 space-y-1">
          <div class="text-sm">inject: <strong>{{ totals.inject }}</strong></div>
          <div class="text-sm">key: <strong>{{ totals.key }}</strong></div>
          <div class="text-sm">button: <strong>{{ totals.button }}</strong></div>
          <div class="text-sm">konfetki: <strong>{{ totals.konfetki }}</strong></div>
        </div>
      </section>
    </div>
    {% endset %} {{ layout('Админка', body) }}
    """
    return render_template_string(tpl, bans=bans, totals=totals)

@app.post("/admin/ban/add")
def admin_ban_add():
    require_admin()
    hwid = (request.form.get("hwid") or "").strip()
    reason = (request.form.get("reason") or "").strip() or "Banned by admin"
    if hwid:
        data = load_json(BANS_PATH, {"bans": {}, "kick_once": {}})
        data["bans"][hwid]={"reason":reason,"ts":now_ts()}
        save_json(BANS_PATH, data)
        append_log({"ts":now_ts(),"type":"admin","event":"ban_add","hwid":hwid,"extra":{"reason":reason}})
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/ban/del")
def admin_ban_del():
    require_admin()
    hwid = (request.form.get("hwid") or "").strip()
    data = load_json(BANS_PATH, {"bans": {}, "kick_once": {}})
    if hwid in data.get("bans", {}):
        data["bans"].pop(hwid, None); save_json(BANS_PATH, data)
        append_log({"ts":now_ts(),"type":"admin","event":"ban_del","hwid":hwid})
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/kick")
def admin_kick_once():
    require_admin()
    hwid = (request.form.get("hwid") or "").strip()
    reason = (request.form.get("reason") or "").strip() or "Kicked"
    if hwid:
        data = load_json(BANS_PATH, {"bans": {}, "kick_once": {}})
        data.setdefault("kick_once", {})[hwid]={"reason":reason,"ts":now_ts()}
        save_json(BANS_PATH, data)
        append_log({"ts":now_ts(),"type":"admin","event":"kick_once","hwid":hwid,"extra":{"reason":reason}})
    return redirect(url_for("admin_dashboard"))

def aggregate_by_hwid():
    logs = load_json(LOGS_PATH, [])
    agg={}
    for L in logs:
        hwid = (L.get("hwid") or "").strip()
        if not hwid: continue
        a = agg.setdefault(hwid, {"hwid":hwid,"player":L.get("player"),"userId":L.get("userId"),"first":L.get("ts"),"last":L.get("ts"),"counts":collections.Counter(),"injectTotal":None})
        a["player"]=L.get("player") or a["player"]; a["userId"]=L.get("userId") or a["userId"]; a["last"]=L.get("ts") or a["last"]
        a["counts"][L.get("type","misc")] += 1
        if L.get("type")=="inject" and L.get("extra",{}).get("injectTotal"):
            a["injectTotal"]=L["extra"]["injectTotal"]
    return agg

@app.get("/admin/users")
def admin_users():
    require_admin()
    agg = aggregate_by_hwid(); rows = sorted(agg.values(), key=lambda x: x["last"] or "", reverse=True)
    tpl = BASE + """
    {% set body %}
    <div class="bg-white rounded-2xl shadow-sm border p-6">
      <div class="flex items-center justify-between mb-3"><h2 class="text-xl font-semibold">Users (HWID stack)</h2><a href="{{ url_for('admin_logs') }}" class="rounded-lg px-3 py-1.5 border hover:bg-slate-50">К логам</a></div>
      <div class="overflow-auto rounded-xl border">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50"><tr class="text-left"><th class="py-2 px-3">HWID</th><th class="py-2 px-3">Player</th><th class="py-2 px-3">Injects</th><th class="py-2 px-3">Keys</th><th class="py-2 px-3">Buttons</th><th class="py-2 px-3">Last</th><th class="py-2 px-3"></th></tr></thead>
          <tbody>
            {% for r in rows %}
            <tr class="border-t hover:bg-slate-50">
              <td class="py-2 px-3 font-mono text-[12px]">{{ r.hwid }}</td>
              <td class="py-2 px-3">{{ r.player or '-' }}</td>
              <td class="py-2 px-3">{{ r.counts.get('inject',0) }}</td>
              <td class="py-2 px-3">{{ r.counts.get('key',0) }}</td>
              <td class="py-2 px-3">{{ r.counts.get('button',0) }}</td>
              <td class="py-2 px-3 text-slate-500">{{ r.last }}</td>
              <td class="py-2 px-3"><a class="px-3 py-1.5 rounded-lg border hover:bg-slate-100" href="{{ url_for('admin_user_detail', hwid=r.hwid) }}">Открыть</a></td>
            </tr>
            {% endfor %}
            {% if not rows %}<tr><td class="py-6 px-3 text-center text-slate-500" colspan="7">Пусто</td></tr>{% endif %}
          </tbody>
        </table>
      </div>
    </div>
    {% endset %} {{ layout('Users', body) }}
    """
    return render_template_string(tpl, rows=rows)

@app.get("/admin/user/<hwid>")
def admin_user_detail(hwid):
    require_admin()
    logs = [L for L in load_json(LOGS_PATH, []) if (L.get("hwid") or "")==hwid]
    tpl = BASE + """
    {% set body %}
    <div class="bg-white rounded-2xl shadow-sm border p-6">
      <div class="flex items-center justify-between mb-4"><h2 class="text-xl font-semibold">User logs</h2><a href="{{ url_for('admin_users') }}" class="rounded-lg px-3 py-1.5 border hover:bg-slate-50">← Back</a></div>
      <div class="space-y-3">{% for L in logs|reverse %}
        <div class="rounded-xl border p-3"><div class="text-xs text-slate-500">{{ L.ts }} | {{ L.type }}</div><pre class="text-xs overflow-x-auto mt-2">{{ L|tojson(indent=2) }}</pre></div>
      {% endfor %}{% if not logs %}<div class="text-slate-500 text-center py-12">Пусто</div>{% endif %}</div>
    </div>
    {% endset %} {{ layout('User', body) }}
    """
    return render_template_string(tpl, logs=logs)

@app.get("/admin/logs")
def admin_logs():
    require_admin()
    q = (request.args.get("q") or "").lower().strip()
    t = (request.args.get("type") or "").strip()
    logs = load_json(LOGS_PATH, [])
    if t:
        logs = [L for L in logs if L.get("type")==t]
    if q:
        logs = [L for L in logs if q in json.dumps(L, ensure_ascii=False).lower()]
    tabs = [("","Все"),("admin","Админ"),("inject","Инжект"),("button","Кнопки"),("key","Кей"),("konfetki","Конфетки")]
    tpl = BASE + """
    {% set body %}
    <div class="bg-white rounded-2xl shadow-sm border p-6">
      <div class="flex flex-wrap items-center gap-2 mb-4">
        {% for code,name in tabs %}
          <a href="{{ url_for('admin_logs') }}{% if code %}?type={{code}}{% endif %}"
             class="px-3 py-1.5 rounded-lg border {% if request.args.get('type','')==code %}bg-slate-900 text-white{% else %}hover:bg-slate-50{% endif %}">{{ name }}</a>
        {% endfor %}
        <form class="ml-auto flex gap-2" method="get">
          {% if request.args.get('type') %}<input type="hidden" name="type" value="{{ request.args.get('type') }}">{% endif %}
          <input name="q" value="{{ request.args.get('q','') }}" placeholder="поиск..." class="px-3 py-2 border rounded-lg w-64">
          <a href="{{ url_for('admin_logs_clear') }}" class="px-3 py-2 rounded-lg bg-rose-600 text-white hover:bg-rose-700" onclick="return confirm('Очистить логи?')">Очистить</a>
        </form>
      </div>
      <div class="space-y-3">
        {% for L in logs|reverse %}
          <div class="rounded-xl border p-3">
            <div class="text-xs text-slate-500">{{ L.ts }} | {{ L.type }}</div>
            <pre class="text-xs overflow-x-auto mt-2">{{ L|tojson(indent=2) }}</pre>
          </div>
        {% endfor %}
        {% if not logs %}<div class="text-slate-500 text-center py-12">Пусто</div>{% endif %}
      </div>
    </div>
    {% endset %} {{ layout('Логи', body) }}
    """
    return render_template_string(tpl, tabs=tabs, logs=logs)

@app.get("/admin/logs/clear")
def admin_logs_clear():
    require_admin(); save_json(LOGS_PATH, []); return redirect(url_for('admin_logs'))

# ===== API =====
@app.get("/ping")
def ping(): return jsonify({"ok": True, "time": now_ts()})

@app.get("/api/banlist.json")
def api_banlist(): return jsonify(load_json(BANS_PATH, {"bans": {}, "kick_once": {}}))

@app.get("/api/check")
def api_check():
    hwid = (request.args.get("hwid") or "").strip()
    info = load_json(BANS_PATH, {"bans": {}, "kick_once": {}}).get("bans", {}).get(hwid)
    return jsonify({"banned": bool(info), "reason": (info or {}).get("reason","")})

@app.get("/api/should-kick")
def api_should_kick():
    hwid = (request.args.get("hwid") or "").strip()
    data = load_json(BANS_PATH, {"bans": {}, "kick_once": {}})
    payload = data.get("kick_once", {}).pop(hwid, None)
    if payload:
        save_json(BANS_PATH, data)
        return jsonify({"kick": True, "reason": payload.get("reason","Kicked")})
    return jsonify({"kick": False})

@app.post("/api/log")
def api_log():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception as e:
        return jsonify({"ok": False, "error": f"bad json: {e}"}), 400
    if not isinstance(payload, dict):
        payload={"raw":str(payload)}
    t = str(payload.get("type","misc")).lower()
    if t not in ("admin","inject","button","key","konfetki","misc"):
        t="misc"
    entry = {"ts": now_ts(), **payload, "type": t}
    append_log(entry)
    increment_total(t)
    return jsonify({"ok": True, "type": t})

@app.get("/api/totals")
def api_totals():
    return jsonify(load_json(TOTALS_PATH, {"inject":0,"key":0,"button":0,"konfetki":0,"admin":0,"misc":0}))

@app.errorhandler(403)
def forbidden(_e):
    tpl = BASE + """
    {% set body %}
    <div class="bg-white rounded-2xl shadow-sm border p-8 text-center">
      <div class="text-2xl font-semibold mb-2">Доступ запрещён</div>
      <p class="text-slate-600">Авторизуйся, бро.</p>
      <div class="mt-6"><a href="/login" class="rounded-xl px-4 py-2 border hover:bg-slate-100">На страницу входа</a></div>
    </div>
    {% endset %} {{ layout('403', body) }}
    """
    return render_template_string(tpl), 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
