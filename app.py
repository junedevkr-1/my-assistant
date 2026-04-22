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

def speak(text):
    clean = text.replace('"', '').replace("'", "").replace("\n", " ")
    st.components.v1.html(f"""
    <script>
        var msg = new SpeechSynthesisUtterance("{clean}");
        msg.lang = 'ko-KR';
        msg.rate = 0.95;
        msg.pitch = 0.85;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(msg);
    </script>
    """, height=0)

def get_jarvis_reply(messages, today_info):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=500,
        messages=[
            {"role": "system", "content": f"""당신은 J.A.R.V.I.S. (Just A Rather Very Intelligent System)입니다.
아이언맨의 AI 비서이며, 사용자를 항상 '주인님'이라고 부릅니다.
냉철하고 유머가 약간 있으며, 매우 유능하고 격식체로 말합니다.
한국어로 짧고 스마트하게 답변하세요.
중요: 한자(漢字)는 절대 사용하지 마세요. 순수 한글로만 답변하세요.
단, 주인님이 한자, 사자성어, 한자 공부에 대해 직접 물어볼 때는 한자를 보여줘도 됩니다.
오늘 스케줄 데이터:\n{today_info}"""},
            *[{"role": m["role"], "content": m["content"]} for m in messages]
        ]
    )
    return response.choices[0].message.content

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
if "reply_to_speak" not in st.session_state:
    st.session_state.reply_to_speak = None

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Noto+Sans+KR:wght@300;400;600&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }

.stApp { background: #000510 !important; }

.jarvis-bg {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 700px;
    height: 700px;
    pointer-events: none;
    z-index: 0;
}
.ring {
    position: absolute;
    border-radius: 50%;
    top: 50%;
    left: 50%;
}
.ring-1 {
    width: 160px; height: 160px;
    margin-left: -80px; margin-top: -80px;
    border: 1px solid rgba(0,212,255,0.6);
    box-shadow: 0 0 12px rgba(0,212,255,0.4), inset 0 0 12px rgba(0,212,255,0.1);
    animation: spin 6s linear infinite;
}
.ring-1::before {
    content: '';
    position: absolute;
    top: -4px; left: 50%;
    width: 8px; height: 8px;
    background: #00d4ff;
    border-radius: 50%;
    box-shadow: 0 0 10px #00d4ff;
    margin-left: -4px;
}
.ring-2 {
    width: 280px; height: 280px;
    margin-left: -140px; margin-top: -140px;
    border: 1px solid rgba(0,150,255,0.35);
    border-top-color: rgba(0,212,255,0.7);
    animation: spin-reverse 10s linear infinite;
}
.ring-2::before {
    content: '';
    position: absolute;
    top: -3px; left: 50%;
    width: 6px; height: 6px;
    background: #0096ff;
    border-radius: 50%;
    box-shadow: 0 0 8px #0096ff;
    margin-left: -3px;
}
.ring-3 {
    width: 400px; height: 400px;
    margin-left: -200px; margin-top: -200px;
    border: 1px dashed rgba(0,100,200,0.25);
    border-top-color: rgba(0,180,255,0.5);
    animation: spin 18s linear infinite;
}
.ring-4 {
    width: 520px; height: 520px;
    margin-left: -260px; margin-top: -260px;
    border: 1px solid rgba(0,80,160,0.2);
    border-right-color: rgba(0,150,255,0.4);
    animation: spin-reverse 28s linear infinite;
}
.ring-5 {
    width: 640px; height: 640px;
    margin-left: -320px; margin-top: -320px;
    border: 1px dashed rgba(0,60,120,0.15);
    animation: spin 40s linear infinite;
}
.ring-core {
    width: 60px; height: 60px;
    margin-left: -30px; margin-top: -30px;
    background: radial-gradient(circle, rgba(0,212,255,0.15), transparent 70%);
    border: 1px solid rgba(0,212,255,0.4);
    box-shadow: 0 0 20px rgba(0,212,255,0.2);
    animation: pulse 3s ease-in-out infinite;
}
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes spin-reverse { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
@keyframes pulse {
    0%, 100% { opacity: 0.4; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.1); }
}

.glow-bg {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(0,100,200,0.06) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
}

.notif-go {
    background: linear-gradient(135deg, rgba(0,40,20,0.9), rgba(0,20,10,0.9));
    border: 1px solid rgba(0,212,100,0.4);
    border-radius: 4px;
    padding: 12px 20px;
    margin-bottom: 20px;
    font-family: 'Orbitron', monospace !important;
    font-size: 12px;
    font-weight: 600;
    color: #00ff88;
    letter-spacing: 2px;
    text-shadow: 0 0 10px rgba(0,255,136,0.5);
}
.notif-back {
    background: linear-gradient(135deg, rgba(0,20,40,0.9), rgba(0,10,30,0.9));
    border: 1px solid rgba(0,150,255,0.4);
    border-radius: 4px;
    padding: 12px 20px;
    margin-bottom: 20px;
    font-family: 'Orbitron', monospace !important;
    font-size: 12px;
    font-weight: 600;
    color: #00d4ff;
    letter-spacing: 2px;
    text-shadow: 0 0 10px rgba(0,212,255,0.5);
}

.jarvis-title {
    font-family: 'Orbitron', monospace !important;
    font-size: 36px;
    font-weight: 900;
    color: #00d4ff;
    letter-spacing: 8px;
    text-shadow: 0 0 20px rgba(0,212,255,0.8), 0 0 40px rgba(0,212,255,0.4);
    margin-bottom: 4px;
}
.jarvis-sub {
    font-family: 'Orbitron', monospace !important;
    font-size: 10px;
    color: rgba(0,212,255,0.4);
    letter-spacing: 4px;
    margin-bottom: 28px;
}

.card {
    background: rgba(0,15,35,0.8);
    border: 1px solid rgba(0,150,255,0.2);
    border-top: 1px solid rgba(0,212,255,0.4);
    border-radius: 4px;
    padding: 20px 24px;
    margin-bottom: 12px;
    backdrop-filter: blur(10px);
}
.card-label {
    font-family: 'Orbitron', monospace !important;
    font-size: 10px;
    color: rgba(0,212,255,0.5);
    letter-spacing: 3px;
    margin-bottom: 8px;
}
.card-value {
    font-family: 'Orbitron', monospace !important;
    font-size: 32px;
    font-weight: 700;
    color: #fff;
    text-shadow: 0 0 10px rgba(0,212,255,0.3);
}
.card-sub { font-size: 12px; color: rgba(255,255,255,0.2); margin-left: 8px; }
.bar-bg { background: rgba(0,100,200,0.15); border-radius: 0; height: 3px; margin-top: 14px; }
.bar-fill { height: 3px; box-shadow: 0 0 8px currentColor; }

.timer-box {
    background: rgba(0,15,35,0.9);
    border: 1px solid rgba(0,150,255,0.2);
    border-top: 1px solid rgba(0,212,255,0.5);
    border-radius: 4px;
    padding: 48px 32px;
    text-align: center;
    margin: 16px 0;
}
.timer-num {
    font-family: 'Orbitron', monospace !important;
    font-size: 64px;
    font-weight: 700;
    color: #00d4ff;
    letter-spacing: 8px;
    text-shadow: 0 0 20px rgba(0,212,255,0.6);
}
.timer-cat {
    font-family: 'Orbitron', monospace !important;
    font-size: 11px;
    letter-spacing: 4px;
    margin-top: 12px;
}

div[data-testid="stTabs"] > div > div > button {
    font-family: 'Orbitron', monospace !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    color: rgba(0,150,255,0.4) !important;
    letter-spacing: 2px !important;
}
div[data-testid="stTabs"] > div > div > button[aria-selected="true"] {
    color: #00d4ff !important;
    text-shadow: 0 0 8px rgba(0,212,255,0.6) !important;
}
div[data-testid="stTabs"] > div > div {
    border-bottom: 1px solid rgba(0,100,200,0.3) !important;
}

.stButton > button {
    font-family: 'Orbitron', monospace !important;
    border-radius: 2px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 3px !important;
    padding: 12px 28px !important;
    border: none !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(0,180,255,0.2), rgba(0,100,200,0.1)) !important;
    border: 1px solid rgba(0,212,255,0.5) !important;
    color: #00d4ff !important;
    text-shadow: 0 0 8px rgba(0,212,255,0.8) !important;
    box-shadow: 0 0 15px rgba(0,150,255,0.2) !important;
}

div[data-testid="stNumberInput"] input,
div[data-testid="stSelectbox"] > div > div {
    background: rgba(0,15,35,0.8) !important;
    border: 1px solid rgba(0,100,200,0.3) !important;
    border-radius: 2px !important;
    color: #00d4ff !important;
    font-family: 'Orbitron', monospace !important;
    font-size: 13px !important;
}
div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label {
    font-family: 'Orbitron', monospace !important;
    font-size: 10px !important;
    color: rgba(0,212,255,0.4) !important;
    letter-spacing: 2px !important;
}

section[data-testid="stChatMessage"] {
    background: rgba(0,15,35,0.8) !important;
    border: 1px solid rgba(0,100,200,0.2) !important;
    border-radius: 4px !important;
    margin-bottom: 8px;
}
div[data-testid="stChatInput"] textarea {
    background: rgba(0,15,35,0.9) !important;
    border: 1px solid rgba(0,150,255,0.3) !important;
    border-radius: 4px !important;
    color: #00d4ff !important;
    font-family: 'Orbitron', monospace !important;
    font-size: 12px !important;
}

.section-label {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px;
    color: rgba(0,150,255,0.35);
    letter-spacing: 3px;
    margin-bottom: 12px;
    margin-top: 8px;
}

.voice-hint {
    font-family: 'Orbitron', monospace !important;
    font-size: 9px;
    color: rgba(0,212,255,0.3);
    letter-spacing: 2px;
    text-align: center;
    margin-top: 8px;
}

/* ── 모바일 최적화 ── */
@media (max-width: 768px) {
    .jarvis-title { font-size: 24px; letter-spacing: 4px; }
    .jarvis-sub { font-size: 8px; letter-spacing: 2px; }
    .jarvis-bg { width: 350px; height: 350px; }
    .ring-4, .ring-5 { display: none; }
    .ring-3 { width: 280px; height: 280px; margin-left: -140px; margin-top: -140px; }
    .timer-num { font-size: 48px; letter-spacing: 4px; }
    .card-value { font-size: 24px; }
    .card { padding: 16px; }
    .stButton > button { font-size: 11px !important; padding: 14px 20px !important; }
    div[data-testid="stTabs"] > div > div > button { font-size: 9px !important; letter-spacing: 1px !important; }
    section[data-testid="stChatMessage"] p { font-size: 14px !important; }
}
</style>

<div class="glow-bg"></div>
<div class="jarvis-bg">
    <div class="ring ring-5"></div>
    <div class="ring ring-4"></div>
    <div class="ring ring-3"></div>
    <div class="ring ring-2"></div>
    <div class="ring ring-1"></div>
    <div class="ring ring-core"></div>
</div>
""", unsafe_allow_html=True)

# ── 헤더 ────────────────────────────────────────────────
day_label = get_day_label()
now_str = datetime.now().strftime("%H:%M:%S")
st.markdown('<div class="jarvis-title">J.A.R.V.I.S.</div>', unsafe_allow_html=True)
st.markdown(f'<div class="jarvis-sub">JUST A RATHER VERY INTELLIGENT SYSTEM &nbsp;·&nbsp; {today} {day_label}요일 {now_str}</div>', unsafe_allow_html=True)

# 앱 열고 닫을 때 자비스 반응
st.components.v1.html("""
<script>
function jarvisSay(text) {
    window.speechSynthesis.cancel();
    var msg = new SpeechSynthesisUtterance(text);
    msg.lang = 'ko-KR';
    msg.rate = 0.95;
    msg.pitch = 0.85;
    window.speechSynthesis.speak(msg);
}

document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        jarvisSay("잠시 자리를 비우시는군요, 주인님. 시스템을 유지하겠습니다.");
    } else {
        jarvisSay("다시 돌아오셨군요, 주인님. 무엇을 도와드릴까요?");
    }
});
</script>
""", height=0)

# 음성 재생 — rerun 이후 첫 렌더에서 실행
if st.session_state.reply_to_speak:
    speak(st.session_state.reply_to_speak)
    st.session_state.reply_to_speak = None

notif = get_notification()
if notif:
    kind, msg = notif
    css_class = "notif-go" if kind == "go" else "notif-back"
    st.markdown(f'<div class="{css_class}">⬡ &nbsp;{msg}</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["  SCHEDULE  ", "  TIMER  ", "  A.I. CORE  "])

# ── 탭 1 ────────────────────────────────────────────────
with tab1:
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
        st.success("// DATA SAVED SUCCESSFULLY")

    st.markdown('<div class="section-label" style="margin-top:24px">// STATUS</div>', unsafe_allow_html=True)

    for label, val, goal, color in [
        ("SLEEP", data[today]["수면"], 8, "#00d4ff"),
        ("STUDY", data[today]["공부"], 3, "#00ff88"),
        ("HOBBY", data[today]["취미"], 2, "#ff6eb4"),
    ]:
        pct = min(val / goal, 1.0) * 100
        st.markdown(f"""
        <div class="card">
            <div class="card-label">{label}</div>
            <div>
                <span class="card-value">{val}</span>
                <span class="card-sub">/ TARGET {goal}H</span>
            </div>
            <div class="bar-bg">
                <div class="bar-fill" style="width:{pct:.0f}%;background:{color};color:{color}"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── 탭 2 ────────────────────────────────────────────────
with tab2:
    category = st.selectbox("SELECT MODE", ["STUDY", "HOBBY"])
    cat_key = "공부" if category == "STUDY" else "취미"
    cat_color = "#00ff88" if category == "STUDY" else "#ff6eb4"

    if not st.session_state.timer_running:
        st.markdown(f"""
        <div class="timer-box">
            <div class="timer-num" style="color:rgba(0,212,255,0.2)">00:00</div>
            <div class="timer-cat" style="color:rgba(0,150,255,0.3)">STANDBY</div>
        </div>
        """, unsafe_allow_html=True)
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
        </div>
        """, unsafe_allow_html=True)

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

# ── 탭 3: A.I. CORE ─────────────────────────────────────
with tab3:
    today_info = f"""날짜: {today} ({day_label}요일)
수면: {data[today]['수면']}시간
공부: {data[today]['공부']}시간
취미: {data[today]['취미']}시간"""

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ── 음성 입력 ──
    st.markdown('<div class="section-label">// VOICE INPUT</div>', unsafe_allow_html=True)
    audio = mic_recorder(
        start_prompt="🎤  ACTIVATE MIC",
        stop_prompt="⏹  PROCESSING...",
        just_once=True,
        key="mic"
    )
    st.markdown('<div class="voice-hint">PRESS TO SPEAK — RELEASE TO SEND</div>', unsafe_allow_html=True)

    user_input = None

    # 음성 처리
    if audio and audio.get("id") != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio["id"]
        with st.spinner("// ANALYZING VOICE INPUT..."):
            try:
                audio_file = io.BytesIO(audio["bytes"])
                audio_file.name = "audio.wav"
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                )
                user_input = transcription.text
                st.info(f"🎤 인식됨: {user_input}")
            except Exception as e:
                st.error(f"음성 인식 오류: {e}")

    # 텍스트 입력
    text_input = st.chat_input("TYPE TO J.A.R.V.I.S.")
    if text_input:
        user_input = text_input

    # ── JARVIS 응답 ──
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("// J.A.R.V.I.S. PROCESSING..."):
            reply = get_jarvis_reply(st.session_state.messages, today_info)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.reply_to_speak = reply
        st.rerun()
