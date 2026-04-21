import streamlit as st
from groq import Groq
import json
import os
import time
from datetime import date, datetime
from dotenv import load_dotenv

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
        return ("go", "👋 학교 잘 다녀오세요!")
    if weekday in [0, 2, 4] and h == 15 and 0 <= m <= 15:
        return ("back", "🏠 학교 잘 다녀오셨나요?")
    if weekday in [1, 3] and h == 16 and 0 <= m <= 15:
        return ("back", "🏠 학교 잘 다녀오셨나요?")
    return None

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

# ── 스타일 ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;600;700&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }

.stApp { background: #09090f; }

.notif-go {
    background: linear-gradient(135deg, #1a3a2a, #0d2a1a);
    border: 1px solid #2d6a4f;
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 16px;
    font-weight: 600;
    color: #6ee7b7;
}

.notif-back {
    background: linear-gradient(135deg, #2a1a3a, #1a0d2a);
    border: 1px solid #6d3a9a;
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 16px;
    font-weight: 600;
    color: #c084fc;
}

.app-title {
    font-size: 32px;
    font-weight: 700;
    background: linear-gradient(135deg, #a78bfa, #818cf8, #6ee7b7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 2px;
}

.app-date {
    font-size: 13px;
    color: #444;
    margin-bottom: 28px;
    font-weight: 400;
}

.card {
    background: #111118;
    border: 1px solid #1e1e2e;
    border-radius: 18px;
    padding: 22px 24px;
    margin-bottom: 14px;
}

.card-label {
    font-size: 13px;
    color: #555;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.card-value {
    font-size: 36px;
    font-weight: 700;
    color: #fff;
    line-height: 1;
    margin-bottom: 16px;
}

.card-sub {
    font-size: 13px;
    color: #444;
    font-weight: 400;
}

.bar-bg {
    background: #1e1e2e;
    border-radius: 999px;
    height: 6px;
    margin-top: 12px;
}

.bar-fill {
    height: 6px;
    border-radius: 999px;
}

.timer-box {
    background: #111118;
    border: 1px solid #1e1e2e;
    border-radius: 24px;
    padding: 48px 32px;
    text-align: center;
    margin: 16px 0;
}

.timer-num {
    font-size: 72px;
    font-weight: 700;
    letter-spacing: 6px;
    color: #fff;
    line-height: 1;
}

.timer-cat {
    font-size: 13px;
    color: #a78bfa;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 12px;
}

div[data-testid="stTabs"] > div > div > button {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #444 !important;
    letter-spacing: 0.3px;
}
div[data-testid="stTabs"] > div > div > button[aria-selected="true"] {
    color: #a78bfa !important;
}
div[data-testid="stTabs"] > div > div {
    border-bottom: 1px solid #1e1e2e !important;
}

.stButton > button {
    border-radius: 14px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    padding: 12px 28px !important;
    border: none !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #a78bfa, #818cf8) !important;
    color: #fff !important;
}
.stButton > button[kind="secondary"] {
    background: #1e1e2e !important;
    color: #888 !important;
}

div[data-testid="stNumberInput"] input {
    background: #111118 !important;
    border: 1px solid #1e1e2e !important;
    border-radius: 12px !important;
    color: #fff !important;
    font-size: 15px !important;
}

div[data-testid="stNumberInput"] label {
    color: #666 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

section[data-testid="stChatMessage"] {
    background: #111118 !important;
    border: 1px solid #1e1e2e !important;
    border-radius: 14px !important;
    margin-bottom: 8px;
}

div[data-testid="stChatInput"] textarea {
    background: #111118 !important;
    border: 1px solid #1e1e2e !important;
    border-radius: 14px !important;
    color: #fff !important;
}

.section-title {
    font-size: 11px;
    font-weight: 700;
    color: #333;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 14px;
    margin-top: 8px;
}

div[data-testid="stSelectbox"] > div > div {
    background: #111118 !important;
    border: 1px solid #1e1e2e !important;
    border-radius: 12px !important;
    color: #fff !important;
}
</style>
""", unsafe_allow_html=True)

# ── 헤더 ────────────────────────────────────────────────
day_label = get_day_label()
now_str = datetime.now().strftime("%H:%M")
st.markdown(f'<div class="app-title">YEJUNY 비서</div>', unsafe_allow_html=True)
st.markdown(f'<div class="app-date">{today} · {day_label}요일 · {now_str}</div>', unsafe_allow_html=True)

# ── 알림 배너 ────────────────────────────────────────────
notif = get_notification()
if notif:
    kind, msg = notif
    css_class = "notif-go" if kind == "go" else "notif-back"
    st.markdown(f'<div class="{css_class}">{msg}</div>', unsafe_allow_html=True)

# ── 탭 ──────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["  오늘 일과  ", "  타이머  ", "  AI 비서  "])

# ── 탭 1: 오늘 일과 ─────────────────────────────────────
with tab1:
    st.markdown('<div class="section-title">기록</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        sleep_h = st.number_input("😴  수면 (h)", 0.0, 12.0, float(data[today]["수면"]), 0.5)
    with col2:
        study_h = st.number_input("📚  공부 (h)", 0.0, 12.0, float(data[today]["공부"]), 0.5)
    hobby_h = st.number_input("🎮  취미 (h)", 0.0, 12.0, float(data[today]["취미"]), 0.5)

    if st.button("저장", type="primary"):
        data[today] = {"수면": sleep_h, "공부": study_h, "취미": hobby_h}
        save_data(data)
        st.success("저장됐어요!")

    st.markdown('<div class="section-title" style="margin-top:24px">달성률</div>', unsafe_allow_html=True)

    items = [
        ("😴", "수면", data[today]["수면"], 8, "#818cf8"),
        ("📚", "공부", data[today]["공부"], 3, "#34d399"),
        ("🎮", "취미", data[today]["취미"], 2, "#f472b6"),
    ]

    for icon, label, val, goal, color in items:
        pct = min(val / goal, 1.0) * 100
        st.markdown(f"""
        <div class="card">
            <div class="card-label">{icon} {label}</div>
            <div style="display:flex;align-items:baseline;gap:8px">
                <span class="card-value">{val}</span>
                <span class="card-sub">/ 목표 {goal}h</span>
            </div>
            <div class="bar-bg">
                <div class="bar-fill" style="width:{pct:.0f}%;background:{color}"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── 탭 2: 타이머 ────────────────────────────────────────
with tab2:
    col_l, col_r = st.columns([3, 1])
    with col_l:
        category = st.selectbox("카테고리", ["공부", "취미"])

    if not st.session_state.timer_running:
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="timer-box">
            <div class="timer-num" style="color:#222">00:00</div>
            <div class="timer-cat" style="color:#333">대기 중</div>
        </div>
        """, unsafe_allow_html=True)
        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("▶  시작", type="primary", use_container_width=True):
                st.session_state.timer_running = True
                st.session_state.timer_start = time.time()
                st.session_state.timer_category = category
                st.rerun()
    else:
        elapsed = time.time() - st.session_state.timer_start
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        cat = st.session_state.timer_category
        color_map = {"공부": "#34d399", "취미": "#f472b6"}
        c = color_map.get(cat, "#a78bfa")

        st.markdown(f"""
        <div class="timer-box">
            <div class="timer-num">{minutes:02d}:{seconds:02d}</div>
            <div class="timer-cat" style="color:{c}">{cat} 측정 중</div>
        </div>
        """, unsafe_allow_html=True)

        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("⏹  완료", type="primary", use_container_width=True):
                elapsed_hours = round(elapsed / 3600, 2)
                data[today][cat] = round(data[today].get(cat, 0) + elapsed_hours, 2)
                save_data(data)
                st.session_state.timer_running = False
                st.success(f"{minutes}분 {seconds}초 기록됐어요!")
                st.rerun()

        time.sleep(1)
        st.rerun()

# ── 탭 3: AI 비서 ───────────────────────────────────────
with tab3:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("무엇이든 물어보세요!")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        today_info = f"""오늘: {today} ({day_label}요일)
수면: {data[today]['수면']}시간
공부: {data[today]['공부']}시간
취미: {data[today]['취미']}시간"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=500,
            messages=[
                {"role": "system", "content": f"너는 YEJUNY의 하루를 관리해주는 친근한 AI 비서야. 반말로 짧고 친근하게 대화해줘.\n\n오늘 데이터:\n{today_info}"},
                *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            ]
        )

        reply = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()
