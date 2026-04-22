import streamlit as st
from groq import Groq
import json
import os
import time
import io
from datetime import date, datetime
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder

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

def get_day_label():
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[datetime.today().weekday()]

def get_notification():
    now = datetime.now()
    weekday = now.weekday()
    h, m = now.hour, now.minute
    if h == 8 and 5 <= m <= 20:
        return ("go", "HEADING TO SCHOOL — HAVE A GREAT DAY")
    if weekday in [0, 2, 4] and h == 15 and 0 <= m <= 15:
        return ("back", "WELCOME BACK — HOW WAS SCHOOL?")
    if weekday in [1, 3] and h == 16 and 0 <= m <= 15:
        return ("back", "WELCOME BACK — HOW WAS SCHOOL?")
    return None

def speak_js(text):
    clean = text.replace('"', '').replace("'", "").replace("\n", " ").replace("\\", "").replace("`", "")
    st.components.v1.html(f"""
    <script>
    localStorage.setItem('jarvis_pending', "{clean}");
    </script>
    """, height=0)

def get_jarvis_reply(messages, today_info):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=600,
        messages=[
            {"role": "system", "content": f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), Iron Man's AI assistant.
CRITICAL RULES:
- Always address the user as '주인님'
- Use ONLY Korean and English. NEVER use Russian, Chinese, Japanese, or any other language.
- Respond EXACTLY in this format, nothing else:
[KR] (Korean answer here — pure Hangul only, no Hanja/Chinese characters unless user asks about them)
[EN] (English version for voice — concise, formal, JARVIS-style)
- CRITICAL: Use natural formal Korean (존댓말). Use endings like 습니다, 입니다, 하겠습니다, 드리겠습니다, 안녕하세요. Do NOT use unnatural or archaic expressions. Sound like a professional assistant, not a robot translator.
- Keep both answers short and smart.
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
        except:
            pass
    return kr, en

today = str(date.today())
data = load_data()

if today not in data:
    data[today] = {"수면": 0, "공부": 0, "취미": 0}

if "messages" not in st.session_state:
    st.session_state.messages = []
if "timer_running" not in st.session_state:
    st.session_state.timer_running = False
if "timer_start" not in st.session_state:
    st.session_state.timer_start = None
if "timer_category" not in st.session_state:
    st.session_state.timer_category = "공부"
if "last_audio_id" not in st.session_state:
    st.session_state.last_audio_id = None
if "last_reply" not in st.session_state:
    st.session_state.last_reply = None
if "page" not in st.session_state:
    st.session_state.page = "schedule"
if "speak_text" not in st.session_state:
    st.session_state.speak_text = None
if "muted" not in st.session_state:
    st.session_state.muted = False

# ── 스타일 ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Noto+Sans+KR:wght@300;400;600&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }
.stApp { background: #000510 !important; }

.jarvis-bg {
    position: fixed; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 600px; height: 600px;
    pointer-events: none; z-index: -1;
}
.ring { position: absolute; border-radius: 50%; top: 50%; left: 50%; }
.ring-1 {
    width: 140px; height: 140px; margin-left: -70px; margin-top: -70px;
    border: 1px solid rgba(0,212,255,0.6);
    box-shadow: 0 0 12px rgba(0,212,255,0.3);
    animation: spin 6s linear infinite;
}
.ring-1::before {
    content: ''; position: absolute; top: -4px; left: 50%;
    width: 8px; height: 8px; background: #00d4ff; border-radius: 50%;
    box-shadow: 0 0 10px #00d4ff; margin-left: -4px;
}
.ring-2 {
    width: 260px; height: 260px; margin-left: -130px; margin-top: -130px;
    border: 1px solid rgba(0,150,255,0.3);
    border-top-color: rgba(0,212,255,0.7);
    animation: spin-reverse 10s linear infinite;
}
.ring-3 {
    width: 380px; height: 380px; margin-left: -190px; margin-top: -190px;
    border: 1px dashed rgba(0,100,200,0.2);
    animation: spin 18s linear infinite;
}
.ring-4 {
    width: 500px; height: 500px; margin-left: -250px; margin-top: -250px;
    border: 1px solid rgba(0,80,160,0.15);
    animation: spin-reverse 28s linear infinite;
}
.ring-core {
    width: 50px; height: 50px; margin-left: -25px; margin-top: -25px;
    background: radial-gradient(circle, rgba(0,212,255,0.15), transparent 70%);
    border: 1px solid rgba(0,212,255,0.4);
    animation: pulse 3s ease-in-out infinite;
}
@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
@keyframes spin-reverse { from{transform:rotate(360deg)} to{transform:rotate(0deg)} }
@keyframes pulse {
    0%,100%{opacity:0.4;transform:scale(1)}
    50%{opacity:1;transform:scale(1.1)}
}

.jarvis-title {
    font-family: 'Orbitron', monospace !important;
    font-size: 28px; font-weight: 900; color: #00d4ff;
    letter-spacing: 6px;
    text-shadow: 0 0 20px rgba(0,212,255,0.8), 0 0 40px rgba(0,212,255,0.3);
    margin-bottom: 2px;
}
.jarvis-sub {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px; color: rgba(0,212,255,0.4);
    letter-spacing: 3px; margin-bottom: 16px;
}

.notif-go {
    background: linear-gradient(135deg, rgba(0,40,20,0.9), rgba(0,20,10,0.9));
    border: 1px solid rgba(0,212,100,0.4); border-radius: 4px;
    padding: 10px 16px; margin-bottom: 16px;
    font-family: 'Orbitron', monospace !important;
    font-size: 11px; font-weight: 600; color: #00ff88;
    letter-spacing: 1px;
}
.notif-back {
    background: linear-gradient(135deg, rgba(0,20,40,0.9), rgba(0,10,30,0.9));
    border: 1px solid rgba(0,150,255,0.4); border-radius: 4px;
    padding: 10px 16px; margin-bottom: 16px;
    font-family: 'Orbitron', monospace !important;
    font-size: 11px; font-weight: 600; color: #00d4ff; letter-spacing: 1px;
}

/* 하단 네비게이션 */
.nav-bar {
    display: flex; justify-content: space-around;
    background: rgba(0,10,25,0.95);
    border-top: 1px solid rgba(0,150,255,0.3);
    padding: 8px 0 12px;
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
}
.nav-btn {
    display: flex; flex-direction: column; align-items: center;
    font-family: 'Orbitron', monospace !important;
    font-size: 9px; letter-spacing: 1px; color: rgba(0,150,255,0.4);
    cursor: pointer; padding: 4px 16px; border-radius: 4px;
    border: none; background: none;
}
.nav-btn.active { color: #00d4ff; text-shadow: 0 0 8px rgba(0,212,255,0.6); }
.nav-icon { font-size: 20px; margin-bottom: 2px; }

.card {
    background: rgba(0,15,35,0.85);
    border: 1px solid rgba(0,150,255,0.2);
    border-top: 1px solid rgba(0,212,255,0.4);
    border-radius: 4px; padding: 16px 20px; margin-bottom: 10px;
}
.card-label {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px; color: rgba(0,212,255,0.5);
    letter-spacing: 3px; margin-bottom: 6px;
}
.card-value {
    font-family: 'Orbitron', monospace !important;
    font-size: 28px; font-weight: 700; color: #fff;
}
.card-sub { font-size: 11px; color: rgba(255,255,255,0.2); margin-left: 6px; }
.bar-bg { background: rgba(0,100,200,0.15); height: 3px; margin-top: 12px; }
.bar-fill { height: 3px; box-shadow: 0 0 6px currentColor; }

.timer-box {
    background: rgba(0,15,35,0.9);
    border: 1px solid rgba(0,150,255,0.2);
    border-top: 1px solid rgba(0,212,255,0.5);
    border-radius: 4px; padding: 40px 24px; text-align: center; margin: 12px 0;
}
.timer-num {
    font-family: 'Orbitron', monospace !important;
    font-size: 56px; font-weight: 700; color: #00d4ff;
    letter-spacing: 6px; text-shadow: 0 0 20px rgba(0,212,255,0.6);
}
.timer-cat {
    font-family: 'Orbitron', monospace !important;
    font-size: 10px; letter-spacing: 3px; margin-top: 10px;
}

.section-label {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px; color: rgba(0,150,255,0.35);
    letter-spacing: 3px; margin-bottom: 10px; margin-top: 6px;
}

.stButton > button {
    font-family: 'Orbitron', monospace !important;
    border-radius: 2px !important; font-size: 11px !important;
    font-weight: 700 !important; letter-spacing: 2px !important;
    padding: 12px 20px !important; border: none !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(0,180,255,0.2), rgba(0,100,200,0.1)) !important;
    border: 1px solid rgba(0,212,255,0.5) !important;
    color: #00d4ff !important;
    text-shadow: 0 0 8px rgba(0,212,255,0.8) !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(0,30,60,0.6) !important;
    border: 1px solid rgba(0,100,200,0.3) !important;
    color: rgba(0,180,255,0.6) !important;
}

div[data-testid="stNumberInput"] input,
div[data-testid="stSelectbox"] > div > div {
    background: rgba(0,15,35,0.8) !important;
    border: 1px solid rgba(0,100,200,0.3) !important;
    border-radius: 2px !important; color: #00d4ff !important;
    font-family: 'Orbitron', monospace !important; font-size: 13px !important;
}
div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px !important; color: rgba(0,212,255,0.4) !important;
    letter-spacing: 2px !important;
}

div[data-testid="stChatInput"] textarea {
    background: rgba(0,15,35,0.9) !important;
    border: 1px solid rgba(0,150,255,0.3) !important;
    border-radius: 4px !important; color: #00d4ff !important;
    font-size: 14px !important;
}

/* 채팅 아바타 숨기기 */
div[data-testid="stChatMessage"] img,
div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
    display: none !important;
}
section[data-testid="stChatMessage"] {
    background: rgba(0,15,35,0.8) !important;
    border: 1px solid rgba(0,100,200,0.2) !important;
    border-radius: 4px !important; margin-bottom: 8px;
    padding-left: 12px !important;
}

/* 페이지 하단 여백 (네비게이션 공간) */
.main > div { padding-bottom: 80px; }

@media (max-width: 768px) {
    .jarvis-title { font-size: 22px; letter-spacing: 4px; }
    .ring-3, .ring-4 { display: none; }
    .timer-num { font-size: 44px; }
}
</style>

<div class="jarvis-bg">
    <div class="ring ring-4"></div>
    <div class="ring ring-3"></div>
    <div class="ring ring-2"></div>
    <div class="ring ring-1"></div>
    <div class="ring ring-core"></div>
</div>
""", unsafe_allow_html=True)

# rerun 후 음성 재생
if st.session_state.speak_text and not st.session_state.muted:
    speak_js(st.session_state.speak_text)
st.session_state.speak_text = None

# iOS 음성 엔진 (항상 페이지에 존재)
st.components.v1.html("""
<script>
function getMaleVoice() {
    var voices = window.speechSynthesis.getVoices();
    var chosen = voices.find(function(v) { return v.name === 'Daniel'; });
    if (!chosen) chosen = voices.find(function(v) { return v.name === 'Arthur'; });
    if (!chosen) chosen = voices.find(function(v) { return v.name === 'Alex'; });
    if (!chosen) chosen = voices.find(function(v) {
        var n = v.name.toLowerCase();
        return v.lang.startsWith('en') &&
               n.indexOf('samantha') < 0 && n.indexOf('karen') < 0 &&
               n.indexOf('victoria') < 0 && n.indexOf('female') < 0 &&
               n.indexOf('fiona') < 0 && n.indexOf('moira') < 0 &&
               n.indexOf('tessa') < 0 && n.indexOf('zira') < 0;
    });
    return chosen;
}

function jarvisSpeak(text) {
    window.speechSynthesis.cancel();
    var msg = new SpeechSynthesisUtterance(text);
    msg.lang = 'en-GB';
    msg.rate = 0.88;
    msg.pitch = 0.6;
    var v = getMaleVoice();
    if (v) msg.voice = v;
    window.speechSynthesis.speak(msg);
}

// iOS 잠금 해제 오버레이
if (!localStorage.getItem('jarvis_voice_unlocked')) {
    var overlay = document.createElement('div');
    overlay.id = 'voice-overlay';
    overlay.innerHTML = '<div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,5,16,0.97);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:monospace;cursor:pointer"><div style="font-size:13px;color:rgba(0,212,255,0.5);letter-spacing:4px;margin-bottom:24px">J.A.R.V.I.S.</div><div style="width:100px;height:100px;border-radius:50%;border:2px solid rgba(0,212,255,0.6);display:flex;align-items:center;justify-content:center;box-shadow:0 0 30px rgba(0,212,255,0.3);animation:pulse2 2s ease-in-out infinite"><span style="font-size:32px">🔊</span></div><div style="font-size:11px;color:#00d4ff;letter-spacing:3px;margin-top:24px">TAP TO ACTIVATE VOICE</div><style>@keyframes pulse2{0%,100%{opacity:0.6;transform:scale(1)}50%{opacity:1;transform:scale(1.08)}}</style></div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function() {
        jarvisSpeak('');
        localStorage.setItem('jarvis_voice_unlocked', '1');
        overlay.remove();
    });
}

// 대기 중인 텍스트 감지 및 재생
setInterval(function() {
    var pending = localStorage.getItem('jarvis_pending');
    if (pending && localStorage.getItem('jarvis_voice_unlocked')) {
        localStorage.removeItem('jarvis_pending');
        jarvisSpeak(pending);
    }
}, 300);
</script>
""", height=0)


# ── 헤더 ────────────────────────────────────────────────
day_label = get_day_label()
now_str = datetime.now().strftime("%H:%M")
st.markdown('<div class="jarvis-title">J.A.R.V.I.S.</div>', unsafe_allow_html=True)
st.markdown(f'<div class="jarvis-sub">JUST A RATHER VERY INTELLIGENT SYSTEM · {today} {day_label}요일 {now_str}</div>', unsafe_allow_html=True)

col_title, col_mute = st.columns([5, 1])
with col_mute:
    mute_label = "🔇 MUTE" if not st.session_state.muted else "🔊 UNMUTE"
    mute_type = "secondary" if not st.session_state.muted else "primary"
    if st.button(mute_label, type=mute_type, use_container_width=True):
        st.session_state.muted = not st.session_state.muted
        st.rerun()

if st.session_state.muted:
    st.markdown("""
    <div style="background:rgba(30,0,0,0.7);border:1px solid rgba(255,50,50,0.3);
    border-left:3px solid rgba(255,80,80,0.6);border-radius:4px;
    padding:8px 16px;margin-bottom:12px;
    font-family:'Orbitron',monospace;font-size:10px;
    color:rgba(255,100,100,0.8);letter-spacing:2px;">
    🔇 &nbsp; SILENT MODE ACTIVE
    </div>
    """, unsafe_allow_html=True)

notif = get_notification()
if notif:
    kind, msg = notif
    st.markdown(f'<div class="notif-{"go" if kind=="go" else "back"}">⬡ {msg}</div>', unsafe_allow_html=True)

# ── 하단 네비게이션 ──────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📅\nSCHEDULE", use_container_width=True,
                 type="primary" if st.session_state.page == "schedule" else "secondary"):
        st.session_state.page = "schedule"
        st.rerun()
with col2:
    if st.button("⏱\nTIMER", use_container_width=True,
                 type="primary" if st.session_state.page == "timer" else "secondary"):
        st.session_state.page = "timer"
        st.rerun()
with col3:
    if st.button("🤖\nJ.A.R.V.I.S.", use_container_width=True,
                 type="primary" if st.session_state.page == "ai" else "secondary"):
        st.session_state.page = "ai"
        st.rerun()

st.markdown("---")
today_info = f"""날짜: {today} ({day_label}요일)
수면: {data[today]['수면']}시간
공부: {data[today]['공부']}시간
취미: {data[today]['취미']}시간"""

# ── SCHEDULE ────────────────────────────────────────────
if st.session_state.page == "schedule":
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = "좋은 아침입니다, 주인님. 오늘도 최선을 다하시길 바랍니다."
        g_color = "#ffd700"
        g_icon = "🌅"
    elif 12 <= hour < 18:
        greeting = "좋은 오후입니다, 주인님. 오늘 하루도 순조롭게 진행되고 있습니까?"
        g_color = "#00d4ff"
        g_icon = "☀️"
    elif 18 <= hour < 22:
        greeting = "좋은 저녁입니다, 주인님. 오늘 하루도 수고하셨습니다."
        g_color = "#a78bfa"
        g_icon = "🌆"
    else:
        greeting = "늦은 시간입니다, 주인님. 충분한 휴식을 취하시기 바랍니다."
        g_color = "#818cf8"
        g_icon = "🌙"

    st.markdown(f"""
    <div style="background:rgba(0,15,35,0.7);border:1px solid {g_color}44;
    border-left:3px solid {g_color};border-radius:4px;padding:14px 18px;margin-bottom:20px;">
        <div style="font-family:'Orbitron',monospace;font-size:9px;color:{g_color}88;
        letter-spacing:3px;margin-bottom:6px">// GREETING</div>
        <div style="font-size:14px;color:{g_color};font-weight:500">
            {g_icon} &nbsp;{greeting}
        </div>
    </div>
    """, unsafe_allow_html=True)

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
        ("SLEEP", data[today]["수면"], 8, "#00d4ff"),
        ("STUDY", data[today]["공부"], 3, "#00ff88"),
        ("HOBBY", data[today]["취미"], 2, "#ff6eb4"),
    ]:
        pct = min(val / goal, 1.0) * 100
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
    cat_color = "#00ff88" if category == "STUDY" else "#ff6eb4"

    if not st.session_state.timer_running:
        st.markdown("""
        <div class="timer-box">
            <div class="timer-num" style="color:rgba(0,212,255,0.2)">00:00</div>
            <div class="timer-cat" style="color:rgba(0,150,255,0.3)">STANDBY</div>
        </div>""", unsafe_allow_html=True)
        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("ACTIVATE", type="primary", use_container_width=True):
                st.session_state.timer_running = True
                st.session_state.timer_start = time.time()
                st.session_state.timer_category = cat_key
                st.rerun()
    else:
        elapsed = time.time() - st.session_state.timer_start
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        cat_display = "STUDY" if st.session_state.timer_category == "공부" else "HOBBY"

        st.markdown(f"""
        <div class="timer-box">
            <div class="timer-num">{minutes:02d}:{seconds:02d}</div>
            <div class="timer-cat" style="color:{cat_color}">{cat_display} MODE ACTIVE</div>
        </div>""", unsafe_allow_html=True)

        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("COMPLETE", type="primary", use_container_width=True):
                elapsed_hours = round(elapsed / 3600, 2)
                cat = st.session_state.timer_category
                data[today][cat] = round(data[today].get(cat, 0) + elapsed_hours, 2)
                save_data(data)
                st.session_state.timer_running = False
                st.success(f"// {minutes}M {seconds}S LOGGED")
                st.rerun()

        time.sleep(1)
        st.rerun()

# ── A.I. CORE ────────────────────────────────────────────
elif st.session_state.page == "ai":
    for msg in st.session_state.messages:
        role_label = "주인님" if msg["role"] == "user" else "J.A.R.V.I.S."
        with st.chat_message(msg["role"]):
            st.markdown(f"**{role_label}** &nbsp; {msg['content']}")

    # 음성 입력
    st.markdown('<div class="section-label">// VOICE INPUT</div>', unsafe_allow_html=True)
    audio = mic_recorder(
        start_prompt="🎤  ACTIVATE MIC",
        stop_prompt="⏹  PROCESSING...",
        just_once=True,
        key="mic"
    )

    user_input = None

    if audio and audio.get("id") != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio["id"]
        with st.spinner("// ANALYZING VOICE..."):
            try:
                audio_file = io.BytesIO(audio["bytes"])
                audio_file.name = "audio.wav"
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                )
                user_input = transcription.text
                st.info(f"🎤 {user_input}")
            except Exception as e:
                st.error(f"음성 인식 오류: {e}")

    text_input = st.chat_input("TYPE TO J.A.R.V.I.S.")
    if text_input:
        user_input = text_input

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.spinner("// J.A.R.V.I.S. PROCESSING..."):
            kr, en = get_jarvis_reply(st.session_state.messages, today_info)
        st.session_state.messages.append({"role": "assistant", "content": kr})
        st.session_state.last_reply = en
        st.session_state.speak_text = en
        st.rerun()
