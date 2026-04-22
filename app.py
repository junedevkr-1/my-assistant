import streamlit as st
from groq import Groq
import json
import os
import time
import io
import urllib.request
from datetime import date, datetime, timezone, timedelta
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder

KST = timezone(timedelta(hours=9))

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now_kst():
    return datetime.now(KST)

def get_day_label():
    days = ["월","화","수","목","금","토","일"]
    return days[now_kst().weekday()]

@st.cache_data(ttl=600)
def get_weather():
    try:
        url = "https://wttr.in/Seoul?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        cur = data["current_condition"][0]
        desc = cur["weatherDesc"][0]["value"]
        temp = cur["temp_C"]
        feels = cur["FeelsLikeC"]
        humid = cur["humidity"]
        icons = {
            "Sunny":"☀️","Clear":"🌙","Partly cloudy":"⛅","Overcast":"☁️",
            "Cloudy":"☁️","Mist":"🌫️","Fog":"🌫️","Rain":"🌧️",
            "Drizzle":"🌦️","Snow":"❄️","Thunderstorm":"⛈️","Blizzard":"🌨️"
        }
        icon = next((v for k,v in icons.items() if k.lower() in desc.lower()), "🌡️")
        return {"icon": icon, "desc": desc, "temp": temp, "feels": feels, "humid": humid}
    except:
        return None

def get_notification():
    now = now_kst()
    h, m, wd = now.hour, now.minute, now.weekday()
    if h == 8 and 5 <= m <= 20:
        return ("go", "HEADING TO SCHOOL — HAVE A GREAT DAY")
    if wd in [0,2,4] and h == 15 and m <= 15:
        return ("back", "WELCOME BACK — HOW WAS SCHOOL?")
    if wd in [1,3] and h == 16 and m <= 15:
        return ("back", "WELCOME BACK — HOW WAS SCHOOL?")
    return None

def speak_js(text):
    clean = text.replace('"','').replace("'",'').replace("\n"," ").replace("\\","").replace("`","")
    st.components.v1.html(f"""
    <script>
    (function(){{
        var t = "{clean}";
        try {{ localStorage.setItem('friday_pending', t); }} catch(e) {{}}
        try {{
            if (window.parent && window.parent.fridaySpeak) {{
                window.parent.fridaySpeak(t);
            }}
        }} catch(e) {{}}
    }})();
    </script>
    """, height=0)

def get_reply(messages, today_info):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=600,
        messages=[
            {"role": "system", "content": f"""You are F.R.I.D.A.Y. (Female Replacement Intelligent Digital Assistant Youth), Tony Stark's AI assistant.
RULES:
- Address the user as '주인님' always.
- Use ONLY Korean and English. Never Russian, Chinese, or other languages.
- Respond EXACTLY in this format:
[KR] (Korean answer — natural formal Korean 존댓말, pure Hangul, no Hanja unless asked)
[EN] (English version for voice — concise, smart, formal assistant tone)
- Keep answers short. Be witty and competent.
Today's data:\n{today_info}"""},
            *[{"role": m["role"], "content": m["content"]} for m in messages]
        ]
    )
    raw = response.choices[0].message.content
    kr, en = raw, raw
    if "[KR]" in raw and "[EN]" in raw:
        try:
            kr = raw.split("[KR]")[1].split("[EN]")[0].strip()
            en = raw.split("[EN]")[1].strip()
        except: pass
    return kr, en

today = now_kst().strftime("%Y-%m-%d")
data = load_data()
if today not in data:
    data[today] = {"수면": 0, "공부": 0, "취미": 0}

for key in ["messages","timer_running","timer_start","timer_category",
            "last_audio_id","last_reply","page","speak_text","muted","is_speaking"]:
    if key not in st.session_state:
        defaults = {"messages":[],"timer_running":False,"timer_start":None,
                    "timer_category":"공부","last_audio_id":None,"last_reply":None,
                    "page":"schedule","speak_text":None,"muted":False,"is_speaking":False}
        st.session_state[key] = defaults[key]

# ── 스타일 ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Noto+Sans+KR:wght@300;400;600&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }
.stApp { background: #0d0400 !important; }

/* ── FRIDAY 배경 링 ── */
.friday-bg {
    position: fixed; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 620px; height: 620px;
    pointer-events: none; z-index: -1;
}
.fr { position: absolute; border-radius: 50%; top: 50%; left: 50%; }

.fr-1 {
    width: 160px; height: 160px; margin-left: -80px; margin-top: -80px;
    border: 3px solid rgba(255,100,0,0.7);
    box-shadow: 0 0 16px rgba(255,100,0,0.5), inset 0 0 16px rgba(255,100,0,0.1);
    animation: fr-spin 5s linear infinite;
}
.fr-1::before {
    content:''; position:absolute; top:-6px; left:50%;
    width:10px; height:10px; background:#ff6400; border-radius:50%;
    box-shadow:0 0 12px #ff6400; margin-left:-5px;
}
.fr-2 {
    width: 260px; height: 260px; margin-left: -130px; margin-top: -130px;
    border: 2px solid transparent;
    border-top: 2px solid rgba(255,130,0,0.8);
    border-right: 2px solid rgba(255,80,0,0.4);
    animation: fr-spin-r 8s linear infinite;
}
.fr-3 {
    width: 360px; height: 360px; margin-left: -180px; margin-top: -180px;
    border: 2px dashed rgba(255,80,0,0.25);
    border-top-color: rgba(255,130,0,0.6);
    animation: fr-spin 15s linear infinite;
}
.fr-4 {
    width: 460px; height: 460px; margin-left: -230px; margin-top: -230px;
    border: 1px solid rgba(255,60,0,0.15);
    border-right-color: rgba(255,100,0,0.35);
    animation: fr-spin-r 25s linear infinite;
}
.fr-5 {
    width: 560px; height: 560px; margin-left: -280px; margin-top: -280px;
    border: 1px dashed rgba(255,50,0,0.1);
    animation: fr-spin 38s linear infinite;
}
.fr-teal {
    width: 300px; height: 300px; margin-left: -150px; margin-top: -150px;
    border: 2px solid transparent;
    border-top: 2px solid rgba(0,168,150,0.5);
    border-bottom: 2px solid rgba(0,168,150,0.3);
    animation: fr-spin-r 12s linear infinite;
}
.fr-core {
    width: 70px; height: 70px; margin-left: -35px; margin-top: -35px;
    background: radial-gradient(circle, rgba(255,100,0,0.12), transparent 70%);
    border: 2px solid rgba(255,100,0,0.5);
    box-shadow: 0 0 20px rgba(255,100,0,0.25);
    animation: fr-pulse 3s ease-in-out infinite;
}

/* 말할 때 링 빛남 */
.fr-speaking .fr-1 {
    border-color: rgba(255,150,0,1);
    box-shadow: 0 0 30px rgba(255,120,0,0.9), inset 0 0 20px rgba(255,100,0,0.3);
    animation: fr-spin 2s linear infinite;
}
.fr-speaking .fr-2 { border-top-color: rgba(255,180,0,1); animation-duration: 3s; }
.fr-speaking .fr-core {
    background: radial-gradient(circle, rgba(255,150,0,0.3), transparent 70%);
    border-color: rgba(255,150,0,0.9);
    box-shadow: 0 0 40px rgba(255,120,0,0.6);
    animation: fr-pulse 0.5s ease-in-out infinite;
}

@keyframes fr-spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
@keyframes fr-spin-r { from{transform:rotate(360deg)} to{transform:rotate(0deg)} }
@keyframes fr-pulse {
    0%,100%{opacity:0.5;transform:scale(1)}
    50%{opacity:1;transform:scale(1.15)}
}

/* ── 헤더 ── */
.fri-title {
    font-family:'Orbitron',monospace !important;
    font-size:30px; font-weight:900; color:#ff6400;
    letter-spacing:6px;
    text-shadow:0 0 20px rgba(255,100,0,0.9), 0 0 40px rgba(255,80,0,0.4);
    margin-bottom:2px;
}
.fri-sub {
    font-family:'Orbitron',monospace !important;
    font-size:9px; color:rgba(255,100,0,0.4);
    letter-spacing:3px; margin-bottom:16px;
}

/* ── 알림 ── */
.notif-go {
    background:linear-gradient(135deg,rgba(40,20,0,0.9),rgba(20,8,0,0.9));
    border:1px solid rgba(255,150,0,0.4); border-left:3px solid #ff9600;
    border-radius:3px; padding:10px 16px; margin-bottom:14px;
    font-family:'Orbitron',monospace !important; font-size:10px;
    font-weight:600; color:#ffb300; letter-spacing:1px;
}
.notif-back {
    background:linear-gradient(135deg,rgba(0,30,28,0.9),rgba(0,15,14,0.9));
    border:1px solid rgba(0,168,150,0.4); border-left:3px solid #00a896;
    border-radius:3px; padding:10px 16px; margin-bottom:14px;
    font-family:'Orbitron',monospace !important; font-size:10px;
    font-weight:600; color:#00d4be; letter-spacing:1px;
}
.silent-banner {
    background:rgba(30,0,0,0.8); border:1px solid rgba(255,50,50,0.3);
    border-left:3px solid rgba(255,80,80,0.6); border-radius:3px;
    padding:8px 16px; margin-bottom:10px;
    font-family:'Orbitron',monospace !important; font-size:9px;
    color:rgba(255,100,100,0.8); letter-spacing:2px;
}

/* ── 카드 ── */
.card {
    background:rgba(20,6,0,0.85);
    border:1px solid rgba(255,80,0,0.2);
    border-top:1px solid rgba(255,100,0,0.5);
    border-radius:3px; padding:16px 20px; margin-bottom:10px;
}
.card-label {
    font-family:'Orbitron',monospace !important; font-size:9px;
    color:rgba(255,100,0,0.5); letter-spacing:3px; margin-bottom:6px;
}
.card-value {
    font-family:'Orbitron',monospace !important; font-size:28px;
    font-weight:700; color:#fff;
    text-shadow:0 0 10px rgba(255,100,0,0.3);
}
.card-sub { font-size:11px; color:rgba(255,255,255,0.2); margin-left:6px; }
.bar-bg { background:rgba(255,80,0,0.1); height:3px; margin-top:12px; }
.bar-fill { height:3px; box-shadow:0 0 6px currentColor; }

/* ── 타이머 ── */
.timer-box {
    background:rgba(20,6,0,0.9);
    border:1px solid rgba(255,80,0,0.2);
    border-top:1px solid rgba(255,100,0,0.6);
    border-radius:3px; padding:40px 24px; text-align:center; margin:12px 0;
}
.timer-num {
    font-family:'Orbitron',monospace !important;
    font-size:56px; font-weight:700; color:#ff6400;
    letter-spacing:6px; text-shadow:0 0 20px rgba(255,100,0,0.7);
}
.timer-cat {
    font-family:'Orbitron',monospace !important;
    font-size:10px; letter-spacing:3px; margin-top:10px;
}

/* ── 섹션 라벨 ── */
.section-label {
    font-family:'Orbitron',monospace !important; font-size:9px;
    color:rgba(255,100,0,0.35); letter-spacing:3px;
    margin-bottom:10px; margin-top:6px;
}

/* ── 버튼 ── */
.stButton > button {
    font-family:'Orbitron',monospace !important;
    border-radius:2px !important; font-size:11px !important;
    font-weight:700 !important; letter-spacing:2px !important;
    padding:12px 20px !important; border:none !important;
}
.stButton > button[kind="primary"] {
    background:linear-gradient(135deg,rgba(255,100,0,0.2),rgba(180,60,0,0.1)) !important;
    border:1px solid rgba(255,100,0,0.6) !important;
    color:#ff6400 !important;
    text-shadow:0 0 8px rgba(255,100,0,0.8) !important;
}
.stButton > button[kind="secondary"] {
    background:rgba(30,10,0,0.6) !important;
    border:1px solid rgba(255,80,0,0.25) !important;
    color:rgba(255,120,0,0.5) !important;
}

/* ── 인풋 ── */
div[data-testid="stNumberInput"] input,
div[data-testid="stSelectbox"] > div > div {
    background:rgba(20,6,0,0.8) !important;
    border:1px solid rgba(255,80,0,0.3) !important;
    border-radius:2px !important; color:#ff8c42 !important;
    font-family:'Orbitron',monospace !important; font-size:13px !important;
}
div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label {
    font-family:'Orbitron',monospace !important; font-size:9px !important;
    color:rgba(255,100,0,0.4) !important; letter-spacing:2px !important;
}

/* ── 채팅 ── */
div[data-testid="stChatMessage"] img,
div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
    display:none !important;
}
section[data-testid="stChatMessage"] {
    background:rgba(20,6,0,0.85) !important;
    border:1px solid rgba(255,80,0,0.15) !important;
    border-radius:3px !important; margin-bottom:8px;
    padding-left:12px !important;
}
div[data-testid="stChatInput"] textarea {
    background:rgba(20,6,0,0.9) !important;
    border:1px solid rgba(255,80,0,0.35) !important;
    border-radius:3px !important; color:#ff8c42 !important; font-size:14px !important;
}

/* ── 인사 카드 ── */
.greet-card {
    border-radius:3px; padding:14px 18px; margin-bottom:18px;
}

.main > div { padding-bottom:20px; }

@media (max-width:768px) {
    .fri-title { font-size:22px; letter-spacing:4px; }
    .fr-4, .fr-5 { display:none; }
    .timer-num { font-size:44px; }
}
</style>
""", unsafe_allow_html=True)

# ── FRIDAY 배경 ──────────────────────────────────────────
speaking_class = "fr-speaking" if st.session_state.is_speaking else ""
st.markdown(f"""
<div class="friday-bg {speaking_class}">
    <div class="fr fr-5"></div>
    <div class="fr fr-4"></div>
    <div class="fr fr-teal"></div>
    <div class="fr fr-3"></div>
    <div class="fr fr-2"></div>
    <div class="fr fr-1"></div>
    <div class="fr fr-core"></div>
</div>
""", unsafe_allow_html=True)

# ── iOS 음성 엔진 (항상 존재) ────────────────────────────
st.components.v1.html("""
<script>
function getMaleVoice() {
    var voices = window.speechSynthesis.getVoices();
    var names = ['Daniel','Arthur','Alex','Gordon','Oliver'];
    for (var n of names) {
        var v = voices.find(function(v){ return v.name === n; });
        if (v) return v;
    }
    var bad = ['samantha','karen','victoria','female','fiona','moira','tessa','zira'];
    return voices.find(function(v){
        if (!v.lang.startsWith('en')) return false;
        var n = v.name.toLowerCase();
        for (var b of bad) { if (n.indexOf(b) >= 0) return false; }
        return true;
    });
}

window.fridaySpeak = function(text) {
    window.speechSynthesis.cancel();
    var msg = new SpeechSynthesisUtterance(text);
    msg.lang = 'en-GB'; msg.rate = 0.88; msg.pitch = 0.6;
    if (window.speechSynthesis.getVoices().length === 0) {
        window.speechSynthesis.onvoiceschanged = function() {
            var v = getMaleVoice(); if (v) msg.voice = v;
            window.speechSynthesis.speak(msg);
        };
    } else {
        var v = getMaleVoice(); if (v) msg.voice = v;
        window.speechSynthesis.speak(msg);
    }
};

// iOS 활성화 오버레이
if (!localStorage.getItem('friday_unlocked')) {
    var ov = document.createElement('div');
    ov.innerHTML = '<div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(13,4,0,0.97);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer"><div style="font-family:monospace;font-size:12px;color:rgba(255,100,0,0.5);letter-spacing:4px;margin-bottom:28px">F.R.I.D.A.Y.</div><div style="width:110px;height:110px;border-radius:50%;border:3px solid rgba(255,100,0,0.7);display:flex;align-items:center;justify-content:center;box-shadow:0 0 30px rgba(255,100,0,0.4);animation:fp 2s ease-in-out infinite"><span style="font-size:36px">🔊</span></div><div style="font-family:monospace;font-size:10px;color:#ff6400;letter-spacing:3px;margin-top:24px">TAP TO ACTIVATE VOICE</div><style>@keyframes fp{0%,100%{opacity:0.6;transform:scale(1)}50%{opacity:1;transform:scale(1.08)}}</style></div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', function(){
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(''));
        localStorage.setItem('friday_unlocked','1');
        ov.remove();
    });
}

// 대기 텍스트 감지
setInterval(function(){
    try {
        var t = localStorage.getItem('friday_pending');
        if (t && localStorage.getItem('friday_unlocked')) {
            localStorage.removeItem('friday_pending');
            window.fridaySpeak(t);
        }
    } catch(e){}
}, 300);
</script>
""", height=0)

# rerun 후 음성 재생
if st.session_state.speak_text and not st.session_state.muted:
    speak_js(st.session_state.speak_text)
    st.session_state.is_speaking = True
else:
    st.session_state.is_speaking = False
st.session_state.speak_text = None

# ── 헤더 ────────────────────────────────────────────────
day_label = get_day_label()
now_str = now_kst().strftime("%H:%M")

col_title, col_mute = st.columns([5,1])
with col_title:
    st.markdown('<div class="fri-title">F.R.I.D.A.Y.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="fri-sub">FEMALE REPLACEMENT INTELLIGENT DIGITAL ASSISTANT YOUTH · {today} {day_label}요일 {now_str}</div>', unsafe_allow_html=True)
with col_mute:
    mute_label = "🔇" if not st.session_state.muted else "🔊"
    if st.button(mute_label, type="secondary" if not st.session_state.muted else "primary", use_container_width=True):
        st.session_state.muted = not st.session_state.muted
        st.rerun()

if st.session_state.muted:
    st.markdown('<div class="silent-banner">🔇 &nbsp; SILENT MODE ACTIVE</div>', unsafe_allow_html=True)

notif = get_notification()
if notif:
    kind, msg = notif
    st.markdown(f'<div class="notif-{"go" if kind=="go" else "back"}">⬡ &nbsp;{msg}</div>', unsafe_allow_html=True)

# ── 네비게이션 ───────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📅  SCHEDULE", use_container_width=True,
                 type="primary" if st.session_state.page=="schedule" else "secondary"):
        st.session_state.page = "schedule"; st.rerun()
with col2:
    if st.button("⏱  TIMER", use_container_width=True,
                 type="primary" if st.session_state.page=="timer" else "secondary"):
        st.session_state.page = "timer"; st.rerun()
with col3:
    if st.button("🤖  F.R.I.D.A.Y.", use_container_width=True,
                 type="primary" if st.session_state.page=="ai" else "secondary"):
        st.session_state.page = "ai"; st.rerun()

st.markdown("---")
today_info = f"날짜:{today}({day_label}요일) 수면:{data[today]['수면']}h 공부:{data[today]['공부']}h 취미:{data[today]['취미']}h"

# ── SCHEDULE ────────────────────────────────────────────
if st.session_state.page == "schedule":
    hour = now_kst().hour
    if 5 <= hour < 12:
        greeting, g_color, g_icon = "좋은 아침입니다, 주인님. 오늘도 최선을 다하시길 바랍니다.", "#ffb300", "🌅"
    elif 12 <= hour < 18:
        greeting, g_color, g_icon = "좋은 오후입니다, 주인님. 오늘 하루도 순조롭게 진행되고 있습니까?", "#ff6400", "☀️"
    elif 18 <= hour < 22:
        greeting, g_color, g_icon = "좋은 저녁입니다, 주인님. 오늘 하루도 수고하셨습니다.", "#00a896", "🌆"
    else:
        greeting, g_color, g_icon = "늦은 시간입니다, 주인님. 충분한 휴식을 취하시기 바랍니다.", "#ff6400", "🌙"

    st.markdown(f"""
    <div style="background:rgba(20,6,0,0.8);border:1px solid {g_color}44;
    border-left:3px solid {g_color};border-radius:3px;padding:14px 18px;margin-bottom:18px">
        <div style="font-family:'Orbitron',monospace;font-size:9px;color:{g_color}88;
        letter-spacing:3px;margin-bottom:6px">// GREETING</div>
        <div style="font-size:14px;color:{g_color};font-weight:500">{g_icon}&nbsp; {greeting}</div>
    </div>""", unsafe_allow_html=True)

    weather = get_weather()
    if weather:
        st.markdown(f"""
        <div style="background:rgba(20,6,0,0.8);border:1px solid rgba(255,80,0,0.2);
        border-top:1px solid rgba(255,100,0,0.4);border-radius:3px;
        padding:12px 18px;margin-bottom:14px;display:flex;align-items:center;gap:16px">
            <div style="font-size:32px;line-height:1">{weather['icon']}</div>
            <div>
                <div style="font-family:'Orbitron',monospace;font-size:9px;
                color:rgba(255,100,0,0.4);letter-spacing:3px;margin-bottom:4px">// SEOUL WEATHER</div>
                <div style="font-family:'Orbitron',monospace;font-size:22px;
                font-weight:700;color:#ff6400">{weather['temp']}°C
                <span style="font-size:11px;color:rgba(255,180,80,0.6);font-weight:400">
                &nbsp; FEELS {weather['feels']}°C</span></div>
                <div style="font-size:11px;color:rgba(255,255,255,0.35);margin-top:2px">
                {weather['desc']} &nbsp;·&nbsp; 습도 {weather['humid']}%</div>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">// INPUT LOG</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        sleep_h = st.number_input("SLEEP (H)", 0.0, 12.0, float(data[today]["수면"]), 0.5)
    with col2:
        study_h = st.number_input("STUDY (H)", 0.0, 12.0, float(data[today]["공부"]), 0.5)
    hobby_h = st.number_input("HOBBY (H)", 0.0, 12.0, float(data[today]["취미"]), 0.5)

    if st.button("SAVE", type="primary"):
        data[today] = {"수면": sleep_h, "공부": study_h, "취미": hobby_h}
        save_data(data)
        st.success("// DATA SAVED")

    st.markdown('<div class="section-label" style="margin-top:20px">// STATUS</div>', unsafe_allow_html=True)
    for label, val, goal, color in [
        ("SLEEP", data[today]["수면"], 8, "#ff6400"),
        ("STUDY", data[today]["공부"], 3, "#ffb300"),
        ("HOBBY", data[today]["취미"], 2, "#00a896"),
    ]:
        pct = min(val/goal, 1.0)*100
        st.markdown(f"""
        <div class="card">
            <div class="card-label">{label}</div>
            <div><span class="card-value">{val}</span>
            <span class="card-sub">/ TARGET {goal}H</span></div>
            <div class="bar-bg">
                <div class="bar-fill" style="width:{pct:.0f}%;background:{color};color:{color}"></div>
            </div>
        </div>""", unsafe_allow_html=True)

# ── TIMER ────────────────────────────────────────────────
elif st.session_state.page == "timer":
    category = st.selectbox("SELECT MODE", ["STUDY", "HOBBY"])
    cat_key = "공부" if category == "STUDY" else "취미"
    cat_color = "#ffb300" if category == "STUDY" else "#00a896"

    if not st.session_state.timer_running:
        st.markdown("""<div class="timer-box">
            <div class="timer-num" style="color:rgba(255,100,0,0.2)">00:00</div>
            <div class="timer-cat" style="color:rgba(255,80,0,0.3)">STANDBY</div>
        </div>""", unsafe_allow_html=True)
        col_c = st.columns([1,2,1])[1]
        with col_c:
            if st.button("ACTIVATE", type="primary", use_container_width=True):
                st.session_state.timer_running = True
                st.session_state.timer_start = time.time()
                st.session_state.timer_category = cat_key
                st.rerun()
    else:
        elapsed = time.time() - st.session_state.timer_start
        minutes, seconds = int(elapsed//60), int(elapsed%60)
        cat_display = "STUDY" if st.session_state.timer_category == "공부" else "HOBBY"
        st.markdown(f"""<div class="timer-box">
            <div class="timer-num">{minutes:02d}:{seconds:02d}</div>
            <div class="timer-cat" style="color:{cat_color}">{cat_display} MODE ACTIVE</div>
        </div>""", unsafe_allow_html=True)
        col_c = st.columns([1,2,1])[1]
        with col_c:
            if st.button("COMPLETE", type="primary", use_container_width=True):
                data[today][cat_key] = round(data[today].get(cat_key,0) + elapsed/3600, 2)
                save_data(data)
                st.session_state.timer_running = False
                st.success(f"// {minutes}M {seconds}S LOGGED")
                st.rerun()
        time.sleep(1)
        st.rerun()

# ── A.I. CORE ────────────────────────────────────────────
elif st.session_state.page == "ai":
    for msg in st.session_state.messages:
        role_label = "주인님" if msg["role"] == "user" else "F.R.I.D.A.Y."
        with st.chat_message(msg["role"]):
            st.markdown(f"**{role_label}** &nbsp; {msg['content']}")

    st.markdown('<div class="section-label">// VOICE INPUT</div>', unsafe_allow_html=True)
    audio = mic_recorder(start_prompt="🎤  ACTIVATE MIC", stop_prompt="⏹  PROCESSING...",
                         just_once=True, key="mic")

    user_input = None
    if audio and audio.get("id") != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio["id"]
        with st.spinner("// ANALYZING VOICE..."):
            try:
                af = io.BytesIO(audio["bytes"]); af.name = "audio.wav"
                t = client.audio.transcriptions.create(file=af, model="whisper-large-v3")
                user_input = t.text
                st.info(f"🎤 {user_input}")
            except Exception as e:
                st.error(f"오류: {e}")

    text_input = st.chat_input("SPEAK TO F.R.I.D.A.Y.")
    if text_input:
        user_input = text_input

    if user_input:
        st.session_state.messages.append({"role":"user","content":user_input})
        with st.spinner("// F.R.I.D.A.Y. PROCESSING..."):
            kr, en = get_reply(st.session_state.messages, today_info)
        st.session_state.messages.append({"role":"assistant","content":kr})
        st.session_state.last_reply = en
        st.session_state.speak_text = en
        st.rerun()
