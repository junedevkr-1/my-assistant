import streamlit as st
from groq import Groq
import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

KST = timezone(timedelta(hours=9))
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DATA_FILE = "data.json"

def now_kst():
    return datetime.now(KST)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_day_label():
    days = ["월","화","수","목","금","토","일"]
    return days[now_kst().weekday()]

def get_notification():
    now = now_kst()
    h, m, wd = now.hour, now.minute, now.weekday()
    if h == 8 and 5 <= m <= 20:
        return ("go", "학교 잘 다녀오세요, 주인님")
    if wd in [0,2,4] and h == 15 and m <= 15:
        return ("back", "학교 다녀오셨습니까, 주인님")
    if wd in [1,3] and h == 16 and m <= 15:
        return ("back", "학교 다녀오셨습니까, 주인님")
    return None

@st.cache_data(ttl=600)
def get_weather_and_air(lat, lon):
    try:
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code"
            f"&timezone=Asia%2FSeoul"
        )
        req = urllib.request.Request(weather_url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            wd = json.loads(r.read().decode())

        air_url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality"
            f"?latitude={lat}&longitude={lon}"
            f"&current=pm10,pm2_5"
            f"&timezone=Asia%2FSeoul"
        )
        req2 = urllib.request.Request(air_url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req2, timeout=5) as r2:
            ad = json.loads(r2.read().decode())

        cur = wd["current"]
        air = ad["current"]

        wc = cur["weather_code"]
        if wc == 0:             desc, icon = "맑음", "☀️"
        elif wc in [1, 2]:      desc, icon = "구름 조금", "⛅"
        elif wc == 3:           desc, icon = "흐림", "☁️"
        elif wc in [45, 48]:    desc, icon = "안개", "🌫️"
        elif wc in [51,53,55,56,57]: desc, icon = "이슬비", "🌦️"
        elif wc in [61,63,65,66,67]: desc, icon = "비", "🌧️"
        elif wc in [71,73,75,77]:    desc, icon = "눈", "❄️"
        elif wc in [80,81,82]:  desc, icon = "소나기", "🌧️"
        elif wc in [85,86]:     desc, icon = "눈 소나기", "🌨️"
        elif wc in [95,96,99]:  desc, icon = "뇌우", "⛈️"
        else:                   desc, icon = "날씨 정보", "🌡️"

        pm25 = round(air.get("pm2_5") or 0)
        pm10 = round(air.get("pm10") or 0)

        def pm25_grade(v):
            if v <= 15:  return "좋음", "#4caf50"
            elif v <= 35: return "보통", "#ffb300"
            elif v <= 75: return "나쁨", "#ff6b35"
            else:         return "매우 나쁨", "#e53935"

        def pm10_grade(v):
            if v <= 30:   return "좋음", "#4caf50"
            elif v <= 80: return "보통", "#ffb300"
            elif v <= 150: return "나쁨", "#ff6b35"
            else:          return "매우 나쁨", "#e53935"

        pl, pc   = pm25_grade(pm25)
        p10l, p10c = pm10_grade(pm10)

        return {
            "icon": icon, "desc": desc,
            "temp": round(cur["temperature_2m"]),
            "feels": round(cur["apparent_temperature"]),
            "humid": cur["relative_humidity_2m"],
            "pm25": pm25, "pm25_level": pl, "pm25_color": pc,
            "pm10": pm10, "pm10_level": p10l, "pm10_color": p10c,
        }
    except:
        return None

def get_reply(messages, today_info):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=400,
        messages=[
            {"role": "system", "content": (
                "You are F.R.I.D.A.Y., Tony Stark's AI assistant.\n"
                "- Always address the user as '주인님'.\n"
                "- Reply ONLY in natural formal Korean (존댓말, pure Hangul).\n"
                "- Never use Russian, Chinese, or other languages.\n"
                "- Be concise, smart, helpful.\n"
                f"Today's data:\n{today_info}"
            )},
            *[{"role": m["role"], "content": m["content"]} for m in messages]
        ]
    )
    return response.choices[0].message.content

# ── 날짜 / 데이터 ────────────────────────────────────────
today = now_kst().strftime("%Y-%m-%d")
data = load_data()
if today not in data:
    data[today] = {"수면": 0, "공부": 0, "취미": 0}

# ── 세션 초기화 ──────────────────────────────────────────
for key, default in [
    ("messages", []), ("timer_running", False),
    ("timer_start", None), ("timer_category", "공부"),
    ("page", "schedule"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# 타이머: URL 쿼리 파라미터에서 복원 (세션이 끊겨도 유지)
if not st.session_state.timer_running:
    ts = st.query_params.get("ts")
    tc = st.query_params.get("tc")
    if ts and tc:
        try:
            st.session_state.timer_running = True
            st.session_state.timer_start = float(ts)
            st.session_state.timer_category = tc
        except:
            pass

# ── 위치 (GPS) ───────────────────────────────────────────
lat = st.query_params.get("lat", "35.2281")
lon = st.query_params.get("lon", "128.6811")

if "lat" not in st.query_params:
    st.components.v1.html("""
    <script>
    (function() {
        function redirect(lat, lon) {
            var url = new URL(window.parent.location.href);
            url.searchParams.set('lat', lat);
            url.searchParams.set('lon', lon);
            window.parent.location.href = url.toString();
        }
        var cLat, cLon;
        try { cLat = localStorage.getItem('u_lat'); cLon = localStorage.getItem('u_lon'); } catch(e) {}
        if (cLat && cLon) {
            redirect(cLat, cLon);
        } else if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(p) {
                    var la = p.coords.latitude.toFixed(4);
                    var lo = p.coords.longitude.toFixed(4);
                    try { localStorage.setItem('u_lat', la); localStorage.setItem('u_lon', lo); } catch(e) {}
                    redirect(la, lo);
                },
                function() { redirect('35.2281', '128.6811'); },
                {timeout: 8000}
            );
        } else {
            redirect('35.2281', '128.6811');
        }
    })();
    </script>
    """, height=0)

# ── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;900&family=Noto+Sans+KR:wght@300;400;600&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; box-sizing: border-box; }
.stApp { background: #1c0e00 !important; }
.block-container { padding-top: 20px !important; }

.fri-title {
    font-family: 'Orbitron', monospace !important;
    font-size: 26px; font-weight: 900; color: #ff8c00;
    letter-spacing: 5px;
    text-shadow: 0 0 14px rgba(255,140,0,0.5);
    margin-bottom: 2px;
}
.fri-sub {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px; color: rgba(255,140,0,0.35); letter-spacing: 2px;
}

.card {
    background: rgba(255,120,0,0.07);
    border: 1px solid rgba(255,120,0,0.18);
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
}
.card-label {
    font-family: 'Orbitron', monospace !important;
    font-size: 10px; color: rgba(255,160,0,0.45);
    letter-spacing: 2px; margin-bottom: 6px;
}
.card-value {
    font-family: 'Orbitron', monospace !important;
    font-size: 26px; font-weight: 700; color: #fff;
}
.card-sub { font-size: 11px; color: rgba(255,255,255,0.22); margin-left: 6px; }
.bar-bg { background: rgba(255,100,0,0.12); height: 5px; border-radius: 3px; margin-top: 10px; }
.bar-fill { height: 5px; border-radius: 3px; }

.timer-box {
    background: rgba(255,120,0,0.06);
    border: 1px solid rgba(255,120,0,0.22);
    border-radius: 12px; padding: 44px 24px; text-align: center; margin: 12px 0;
}
.timer-num {
    font-family: 'Orbitron', monospace !important;
    font-size: 62px; font-weight: 900; color: #ff8c00;
    letter-spacing: 4px; text-shadow: 0 0 18px rgba(255,140,0,0.4);
}
.timer-cat {
    font-family: 'Orbitron', monospace !important;
    font-size: 10px; letter-spacing: 3px; margin-top: 10px;
    color: rgba(255,160,0,0.5);
}

.notif-go {
    background: rgba(255,180,0,0.1); border-left: 3px solid #ffb300;
    border-radius: 8px; padding: 10px 16px; margin-bottom: 14px;
    color: #ffb300; font-size: 13px;
}
.notif-back {
    background: rgba(0,200,180,0.08); border-left: 3px solid #00c8b4;
    border-radius: 8px; padding: 10px 16px; margin-bottom: 14px;
    color: #00c8b4; font-size: 13px;
}

.section-label {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px; color: rgba(255,140,0,0.3);
    letter-spacing: 3px; margin: 10px 0 8px;
}

.stButton > button {
    border-radius: 8px !important; font-size: 12px !important; font-weight: 600 !important;
    transition: all 0.15s !important;
}
.stButton > button[kind="primary"] {
    background: rgba(255,140,0,0.15) !important;
    border: 1px solid rgba(255,140,0,0.55) !important;
    color: #ff8c00 !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(255,100,0,0.04) !important;
    border: 1px solid rgba(255,100,0,0.14) !important;
    color: rgba(255,160,0,0.4) !important;
}

div[data-testid="stNumberInput"] input,
div[data-testid="stSelectbox"] > div > div {
    background: rgba(255,80,0,0.07) !important;
    border: 1px solid rgba(255,100,0,0.25) !important;
    border-radius: 8px !important; color: #ffaa60 !important; font-size: 14px !important;
}

div[data-testid="stChatMessage"] img,
div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] { display: none !important; }
section[data-testid="stChatMessage"] {
    background: rgba(255,100,0,0.05) !important;
    border: 1px solid rgba(255,100,0,0.13) !important;
    border-radius: 10px !important; margin-bottom: 8px;
}
div[data-testid="stChatInput"] textarea {
    background: rgba(255,80,0,0.07) !important;
    border: 1px solid rgba(255,100,0,0.3) !important;
    border-radius: 8px !important; color: #ffaa60 !important;
}

hr { border-color: rgba(255,100,0,0.15) !important; }

@media (max-width: 768px) {
    .fri-title { font-size: 20px; }
    .timer-num { font-size: 50px; }
}
</style>
""", unsafe_allow_html=True)

# ── 헤더 ────────────────────────────────────────────────
day_label = get_day_label()
now_str = now_kst().strftime("%H:%M")

st.markdown(f"""
<div style="padding:4px 0 14px;border-bottom:1px solid rgba(255,120,0,0.18);margin-bottom:14px">
    <div class="fri-title">F.R.I.D.A.Y.</div>
    <div class="fri-sub">{today} &nbsp;{day_label}요일 &nbsp;{now_str} KST</div>
</div>""", unsafe_allow_html=True)

notif = get_notification()
if notif:
    kind, msg_text = notif
    css_class = "notif-go" if kind == "go" else "notif-back"
    icon = "🏫" if kind == "go" else "🏠"
    st.markdown(f'<div class="{css_class}">{icon}&nbsp; {msg_text}</div>', unsafe_allow_html=True)

# ── 네비게이션 ───────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📅  스케줄", use_container_width=True,
                 type="primary" if st.session_state.page == "schedule" else "secondary"):
        st.session_state.page = "schedule"; st.rerun()
with c2:
    if st.button("⏱  타이머", use_container_width=True,
                 type="primary" if st.session_state.page == "timer" else "secondary"):
        st.session_state.page = "timer"; st.rerun()
with c3:
    if st.button("🤖  FRIDAY", use_container_width=True,
                 type="primary" if st.session_state.page == "ai" else "secondary"):
        st.session_state.page = "ai"; st.rerun()

st.markdown("---")
today_info = (f"날짜:{today}({day_label}요일) "
              f"수면:{data[today]['수면']}h 공부:{data[today]['공부']}h 취미:{data[today]['취미']}h")

# ════════════════════════════════════════════════════════
# SCHEDULE
# ════════════════════════════════════════════════════════
if st.session_state.page == "schedule":
    hour = now_kst().hour
    if 5 <= hour < 12:
        greeting, g_color, g_icon = "좋은 아침입니다, 주인님.", "#ffb300", "🌅"
    elif 12 <= hour < 18:
        greeting, g_color, g_icon = "좋은 오후입니다, 주인님.", "#ff8c00", "☀️"
    elif 18 <= hour < 22:
        greeting, g_color, g_icon = "좋은 저녁입니다, 주인님.", "#00c8b4", "🌆"
    else:
        greeting, g_color, g_icon = "늦은 시간입니다, 주인님. 충분히 쉬세요.", "#ff8c00", "🌙"

    st.markdown(f"""
    <div style="background:rgba(255,140,0,0.08);border:1px solid {g_color}30;
    border-left:3px solid {g_color};border-radius:10px;padding:14px 18px;margin-bottom:14px">
        <div style="font-size:14px;color:{g_color}">{g_icon}&nbsp; {greeting}</div>
    </div>""", unsafe_allow_html=True)

    # 날씨 + 미세먼지
    weather = get_weather_and_air(float(lat), float(lon))
    if weather:
        st.markdown(f"""
        <div class="card" style="margin-bottom:14px">
            <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px">
                <div style="font-size:38px;line-height:1">{weather['icon']}</div>
                <div>
                    <div class="card-label">현재 날씨</div>
                    <div style="font-family:'Orbitron',monospace;font-size:26px;font-weight:900;color:#ff8c00">
                        {weather['temp']}°C
                        <span style="font-size:12px;color:rgba(255,180,80,0.5);font-weight:400">
                        &nbsp;체감 {weather['feels']}°C</span>
                    </div>
                    <div style="font-size:12px;color:rgba(255,255,255,0.35);margin-top:2px">
                        {weather['desc']} &nbsp;·&nbsp; 습도 {weather['humid']}%
                    </div>
                </div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
                <div style="background:{weather['pm25_color']}20;border:1px solid {weather['pm25_color']}55;
                border-radius:20px;padding:5px 13px;font-size:12px;color:{weather['pm25_color']}">
                    🌫️ 미세먼지 PM2.5 &nbsp;<b>{weather['pm25']} µg/m³</b> &nbsp;
                    <b>{weather['pm25_level']}</b>
                </div>
                <div style="background:{weather['pm10_color']}20;border:1px solid {weather['pm10_color']}55;
                border-radius:20px;padding:5px 13px;font-size:12px;color:{weather['pm10_color']}">
                    💨 초미세먼지 PM10 &nbsp;<b>{weather['pm10']} µg/m³</b> &nbsp;
                    <b>{weather['pm10_level']}</b>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">// 기록 입력</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        sleep_h = st.number_input("수면 (H)", 0.0, 12.0, float(data[today]["수면"]), 0.5)
    with col2:
        study_h = st.number_input("공부 (H)", 0.0, 12.0, float(data[today]["공부"]), 0.5)
    hobby_h = st.number_input("취미 (H)", 0.0, 12.0, float(data[today]["취미"]), 0.5)

    if st.button("저장", type="primary"):
        data[today] = {"수면": sleep_h, "공부": study_h, "취미": hobby_h}
        save_data(data)
        st.success("저장되었습니다.")

    st.markdown('<div class="section-label" style="margin-top:18px">// 오늘 현황</div>', unsafe_allow_html=True)
    for label, val, goal, color in [
        ("수면", data[today]["수면"], 8, "#ff8c00"),
        ("공부", data[today]["공부"], 3, "#ffb300"),
        ("취미", data[today]["취미"], 2, "#00c8b4"),
    ]:
        pct = min(val / goal, 1.0) * 100
        st.markdown(f"""
        <div class="card">
            <div class="card-label">{label}</div>
            <div><span class="card-value">{val}</span>
            <span class="card-sub">/ 목표 {goal}H</span></div>
            <div class="bar-bg">
                <div class="bar-fill" style="width:{pct:.0f}%;background:{color}"></div>
            </div>
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# TIMER
# ════════════════════════════════════════════════════════
elif st.session_state.page == "timer":
    if not st.session_state.timer_running:
        category = st.selectbox("모드 선택", ["공부", "취미"])
        cat_key = category

        st.markdown("""<div class="timer-box">
            <div class="timer-num" style="color:rgba(255,140,0,0.2)">00:00</div>
            <div class="timer-cat">대기 중</div>
        </div>""", unsafe_allow_html=True)

        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("시작", type="primary", use_container_width=True):
                ts_now = int(time.time())
                st.session_state.timer_running = True
                st.session_state.timer_start = float(ts_now)
                st.session_state.timer_category = cat_key
                st.query_params["ts"] = str(ts_now)
                st.query_params["tc"] = cat_key
                st.rerun()
    else:
        elapsed = time.time() - st.session_state.timer_start
        minutes, seconds = int(elapsed // 60), int(elapsed % 60)
        cat = st.session_state.timer_category
        cat_color = "#ffb300" if cat == "공부" else "#00c8b4"

        st.markdown(f"""<div class="timer-box">
            <div class="timer-num">{minutes:02d}:{seconds:02d}</div>
            <div class="timer-cat" style="color:{cat_color}">{cat} 타이머 진행 중</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style="background:rgba(255,200,0,0.08);border:1px solid rgba(255,200,0,0.2);
        border-radius:8px;padding:10px 16px;font-size:12px;color:rgba(255,200,0,0.6);
        text-align:center;margin-bottom:12px">
            화면을 꺼도 타이머는 계속 실행됩니다
        </div>""", unsafe_allow_html=True)

        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("완료", type="primary", use_container_width=True):
                data[today][cat] = round(data[today].get(cat, 0) + elapsed / 3600, 2)
                save_data(data)
                st.session_state.timer_running = False
                st.session_state.timer_start = None
                if "ts" in st.query_params:
                    del st.query_params["ts"]
                if "tc" in st.query_params:
                    del st.query_params["tc"]
                st.success(f"{minutes}분 {seconds}초 기록 완료")
                st.rerun()

        time.sleep(1)
        st.rerun()

# ════════════════════════════════════════════════════════
# AI CORE
# ════════════════════════════════════════════════════════
elif st.session_state.page == "ai":
    for msg in st.session_state.messages:
        role_label = "주인님" if msg["role"] == "user" else "F.R.I.D.A.Y."
        with st.chat_message(msg["role"]):
            st.markdown(f"**{role_label}** &nbsp; {msg['content']}")

    text_input = st.chat_input("F.R.I.D.A.Y.에게 말하기")
    if text_input:
        st.session_state.messages.append({"role": "user", "content": text_input})
        with st.spinner("처리 중..."):
            reply = get_reply(st.session_state.messages, today_info)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()
