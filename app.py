# app.py (Premium UI v12.4.1 - margin 충돌 에러 해결 + 도넛 세로 아래로 확정 보정)
import os
import pandas as pd
import streamlit as st
import plotly.express as px

# ✅ 클릭 이벤트(있으면 사용, 없으면 일반 차트)
try:
    from streamlit_plotly_events import plotly_events
    HAS_PLOTLY_EVENTS = True
except Exception:
    plotly_events = None
    HAS_PLOTLY_EVENTS = False

st.set_page_config(page_title="VOC 대시보드", layout="wide")

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_XLSX = os.path.join(DATA_DIR, "master.xlsx")

REQUIRED_COLS = ["날짜", "기업명", "대분류", "중분류", "소분류", "채널"]
CHANNELS = ["유선", "채팅", "게시판"]

# ✅ 채널 색상(도넛/월별 누적)
CHANNEL_COLOR_MAP = {"유선": "#2563EB", "채팅": "#F97316", "게시판": "#10B981"}

# ✅ Indigo (요일/시간/기업TOP/대중소TOP)
INDIGO_MAIN = "#6366F1"
INDIGO_TOP5 = "#4338CA"
INDIGO_6_10 = "#A5B4FC"

CHART_H_TOP = 420
CHART_H_BOTTOM = 420
CHART_H_SECOND = 380  # ✅ 기업TOP10/도넛 높이 통일(밑라인 정렬)

# -----------------------------
# Helpers: 관리자 페이지 자동 탐색
# -----------------------------
def find_admin_page() -> str | None:
    pages_dir = os.path.join(BASE_DIR, "pages")
    if not os.path.isdir(pages_dir):
        return None

    files = [f for f in os.listdir(pages_dir) if f.lower().endswith(".py")]
    candidates = []
    for f in files:
        low = f.lower()
        if ("admin" in low) or ("관리자" in f):
            candidates.append(f)

    if not candidates:
        return None

    priority = ["admin.py", "1_admin.py", "관리자.py", "1_관리자.py", "01_관리자.py"]
    for p in priority:
        for c in candidates:
            if c == p:
                return f"pages/{c}"
    return f"pages/{candidates[0]}"

ADMIN_PAGE = find_admin_page()

# -----------------------------
# ✅ query param으로 관리자 이동 처리
# -----------------------------
try:
    qp = st.query_params
    goto = qp.get("goto")
except Exception:
    qp = st.experimental_get_query_params()
    goto = qp.get("goto", [None])[0]

if goto == "admin":
    if ADMIN_PAGE:
        st.switch_page(ADMIN_PAGE)
    else:
        st.warning("pages/ 폴더에 관리자 파일이 없어요. (예: pages/01_관리자.py 또는 pages/admin.py)")

# -----------------------------
# CSS
# -----------------------------
st.markdown(
    """
<style>
:root{
  --bg1:#eef2f7; --bg2:#e6ecf5;
  --card-bd: rgba(148,163,184,0.28);
  --shadow: 0 14px 34px rgba(15,23,42,0.12);
  --radius: 18px;
  --text1:#0f172a; --text2:#334155; --muted:#64748b;
  --chip-bg: rgba(99,102,241,0.10);
  --chip-bd: rgba(99,102,241,0.22);
  --chip-tx: #3730a3;
}

.stApp{ background: linear-gradient(135deg, var(--bg1) 0%, var(--bg2) 100%); }
header[data-testid="stHeader"], div[data-testid="stToolbar"], div[data-testid="stDecoration"], footer{ display:none !important; }
#MainMenu{ visibility:hidden; }
.block-container{ padding-top: 1.0rem; padding-bottom: 2.0rem; }

/* 헤더 */
.header-wrap{
  width:100%;
  border-radius: 22px;
  background: linear-gradient(135deg, #0b2a6f 0%, #103a8a 45%, #0b2a6f 100%);
  box-shadow: 0 14px 40px rgba(2,6,23,0.25);
  border: 1px solid rgba(255,255,255,0.12);
  position: relative;
  overflow: hidden;
  margin-bottom: 14px;
  height: 58px;
  display:flex;
  align-items:center;
  padding: 0 14px;
}
.header-wrap:before{
  content:""; position:absolute; inset:-80px -80px auto auto;
  width:220px;height:220px;
  background: radial-gradient(circle, rgba(255,255,255,0.22) 0%, rgba(255,255,255,0) 70%);
  transform: rotate(15deg);
}
.header-title{
  display:flex;align-items:center;gap:10px;
  color: rgba(255,255,255,0.95);
  font-weight: 850; font-size: 22px;
  z-index:2;
}
.header-dot{
  width:10px;height:10px;border-radius:999px;
  background:#3b82f6; box-shadow:0 0 0 4px rgba(59,130,246,0.25);
}
.header-admin{
  position:absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  z-index:3;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  background: rgba(255,255,255,0.14);
  border: 1px solid rgba(255,255,255,0.22);
  color: rgba(255,255,255,0.95);
  text-decoration:none;
  font-size: 18px;
  font-weight: 900;
  box-shadow: 0 6px 16px rgba(0,0,0,0.15);
}
.header-admin:hover{ background: rgba(255,255,255,0.22); }

/* 필터 카드 */
.filter-card{
  border-radius: var(--radius);
  background: rgba(255,255,255,0.90);
  border: 1px solid var(--card-bd);
  box-shadow: var(--shadow);
  padding: 12px;
  margin-bottom: 14px;
}

/* 셀렉트/기간 입력 */
div[data-baseweb="select"] > div,
div[data-testid="stDateInput"] > div{
  background-color: #f8fafc !important;
  border: 1px solid rgba(148,163,184,0.30) !important;
  border-radius: 14px !important;
  min-height: 46px !important;
  box-shadow: 0 6px 16px rgba(15,23,42,0.08) !important;
}

/* 카드 */
div[data-testid="stVerticalBlock"]:has(.card-titlebar){
  background: #ffffff !important;
  border: 1px solid var(--card-bd) !important;
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow) !important;
  padding: 14px 14px 10px 14px !important;
  margin-bottom: 14px !important;
}
/* 2겹 카드 제거 */
div[data-testid="stVerticalBlock"]:has(.card-titlebar):has(div[data-testid="stVerticalBlock"]:has(.card-titlebar)){
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin-bottom: 0 !important;
}

/* 타이틀 + 라인 */
.card-titlebar{
  display:flex; align-items:center; gap:8px;
  font-size: 14px; font-weight: 950;
  color: var(--text1);
  margin: 0 0 6px 2px;
}
.card-titlebar .icon{
  width:22px;height:22px;border-radius:8px;
  display:inline-flex;align-items:center;justify-content:center;
  background: rgba(99,102,241,0.12);
  border: 1px solid rgba(99,102,241,0.20);
  color:#3730a3;
  font-size: 13px;
}
.card-line{
  height: 2px;
  width: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(99,102,241,0.85), rgba(99,102,241,0.12));
  margin: 2px 0 10px 0;
}

/* 인사이트 칩 */
.chips{ display:flex; flex-wrap:wrap; gap:8px; margin: 0 0 8px 2px; }
.chip{
  display:inline-flex; align-items:center; gap:6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--chip-bg);
  border: 1px solid var(--chip-bd);
  color: var(--chip-tx);
  font-weight: 850;
  font-size: 12px;
}
.chip .b{ color:#0f172a; font-weight: 950; }

/* Plotly 가운데정렬 */
div[data-testid="stVerticalBlock"]:has(.card-titlebar) div[data-testid="stPlotlyChart"]{
  display:flex !important;
  justify-content:center !important;
  margin: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(.card-titlebar) div[data-testid="stPlotlyChart"] > div{
  width: 100% !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Data
# -----------------------------
def _must_cols(df: pd.DataFrame, cols):
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"master.xlsx에 필수 컬럼이 없습니다: {miss}")

@st.cache_data(show_spinner=False)
def load_master(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    _must_cols(df, REQUIRED_COLS)

    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()
    df["월"] = df["날짜"].dt.to_period("M").dt.to_timestamp()

    for c in ["기업명", "대분류", "중분류", "소분류", "채널"]:
        df[c] = df[c].astype(str).str.strip()
        df.loc[df[c].isin(["nan", "None", "NaN", ""]), c] = None
    return df

def fmt_int(x):
    try:
        return f"{int(x):,}"
    except Exception:
        return "0"

def safe_ratio(num, den):
    if not den:
        return 0.0
    return float(num) / float(den) * 100.0

def kpi(label, value, sub, color="#2563eb"):
    st.markdown(
        f"""
<div style="
  border-radius: var(--radius);
  background:#fff;
  border:1px solid rgba(148,163,184,0.28);
  box-shadow: 0 14px 34px rgba(15,23,42,0.12);
  padding:14px 16px;
  height:118px;
  display:flex; gap:12px; align-items:center;">
  <div style="width:8px;height:86px;border-radius:999px;background:{color};box-shadow:0 10px 20px {color}33;flex:0 0 auto;"></div>
  <div>
    <div style="color:#64748b;font-weight:800;font-size:13px;">{label}</div>
    <div style="color:#0f172a;font-weight:950;font-size:32px;letter-spacing:-0.6px;line-height:1.05;">{value}</div>
    <div style="color:#334155;font-size:12px;font-weight:700;">{sub}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# ✅ 여기 핵심: margin을 "옵션"으로 받아서 중복 충돌 제거
def base_layout(height: int, showlegend: bool = False, margin: dict | None = None):
    if margin is None:
        margin = dict(l=12, r=18, t=8, b=52)
    return dict(
        height=height,
        margin=margin,
        legend_title_text="",
        xaxis_title="",
        yaxis_title="",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        showlegend=showlegend,
    )

def card_title(icon: str, title: str):
    st.markdown(
        f'<div class="card-titlebar"><span class="icon">{icon}</span>{title}</div><div class="card-line"></div>',
        unsafe_allow_html=True,
    )

def chips(items):
    if not items:
        return
    html = '<div class="chips">' + "".join([f'<span class="chip">{t}</span>' for t in items]) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

def clean_label(s: str) -> str:
    return str(s).replace("👑 ", "").strip()

def top10_like(df_: pd.DataFrame, col: str, height: int, exclude_pattern: str | None = None):
    s = df_[col].dropna().astype(str).str.strip()
    if exclude_pattern:
        s = s[~s.str.contains(exclude_pattern, regex=True, na=False)]
    top = s.value_counts().head(10).reset_index()
    top.columns = [col, "건수"]
    if top.empty:
        st.info("데이터가 없어요.")
        return

    top = top.sort_values("건수", ascending=False).reset_index(drop=True)
    top["순위"] = range(1, len(top) + 1)
    top.loc[top["순위"] == 1, col] = "👑 " + top.loc[top["순위"] == 1, col]
    top["그룹"] = top["순위"].apply(lambda r: "TOP5" if r <= 5 else "6~10")
    cat_array = top[col].tolist()

    fig = px.bar(
        top,
        x="건수",
        y=col,
        orientation="h",
        color="그룹",
        color_discrete_map={"TOP5": INDIGO_TOP5, "6~10": INDIGO_6_10},
        text="건수",
    )
    fig.update_layout(**base_layout(height, showlegend=False))
    fig.update_yaxes(categoryorder="array", categoryarray=cat_array[::-1], showgrid=False, zeroline=False, showline=False)
    fig.update_xaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False)
    fig.update_traces(textposition="outside", cliponaxis=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# =============================
# Header
# =============================
admin_help = "관리자 페이지" if ADMIN_PAGE else "pages/에 관리자 파일이 없어요 (예: pages/01_관리자.py 또는 pages/admin.py)"
admin_href = "?goto=admin" if ADMIN_PAGE else "#"

st.markdown(
    f"""
<div class="header-wrap">
  <div class="header-title"><span class="header-dot"></span>VOC 대시보드</div>
  <a class="header-admin" href="{admin_href}" title="{admin_help}">🛠️</a>
</div>
""",
    unsafe_allow_html=True,
)

# =============================
# Load master
# =============================
df = load_master(MASTER_XLSX)
if df.empty:
    st.error("data/master.xlsx 를 찾을 수 없거나 데이터가 비어있어요.")
    st.stop()

min_d = df["날짜"].min().date()
max_d = df["날짜"].max().date()

st.session_state.setdefault("big", "전체")
st.session_state.setdefault("mid", "전체")
st.session_state.setdefault("small", "전체")

# =============================
# Filters
# =============================
st.markdown('<div class="filter-card">', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1.0, 1.6, 1.2, 1.8])

with c1:
    f_channel = st.selectbox("채널", ["전체"] + CHANNELS, index=0, key="channel")

with c2:
    f_range = st.date_input("기간", value=(min_d, max_d), min_value=min_d, max_value=max_d, key="range")
    if isinstance(f_range, tuple) and len(f_range) == 2:
        start_d, end_d = f_range
    else:
        start_d, end_d = min_d, max_d

with c3:
    companies = ["전체"] + sorted(df["기업명"].dropna().unique().tolist())
    f_company = st.selectbox("기업명", companies, index=0, key="company")

with c4:
    l1, l2, l3 = st.columns([1, 1, 1])

    with l1:
        big_opts = ["전체"] + sorted(df["대분류"].dropna().unique().tolist())
        big = st.selectbox(
            "대분류",
            big_opts,
            index=big_opts.index(st.session_state.get("big", "전체")) if st.session_state.get("big", "전체") in big_opts else 0,
            key="big_sel",
        )

    if big != "전체":
        mid_pool = df[df["대분류"] == big]["중분류"].dropna().unique().tolist()
    else:
        mid_pool = df["중분류"].dropna().unique().tolist()
    mid_opts = ["전체"] + sorted(list(set(mid_pool)))

    with l2:
        mid = st.selectbox(
            "중분류",
            mid_opts,
            index=mid_opts.index(st.session_state.get("mid", "전체")) if st.session_state.get("mid", "전체") in mid_opts else 0,
            key="mid_sel",
        )

    small_df = df.copy()
    if big != "전체":
        small_df = small_df[small_df["대분류"] == big]
    if mid != "전체":
        small_df = small_df[small_df["중분류"] == mid]
    small_pool = small_df["소분류"].dropna().unique().tolist()
    small_opts = ["전체"] + sorted(list(set(small_pool)))

    with l3:
        small = st.selectbox(
            "소분류",
            small_opts,
            index=small_opts.index(st.session_state.get("small", "전체")) if st.session_state.get("small", "전체") in small_opts else 0,
            key="small_sel",
        )

    st.session_state["big"] = big
    st.session_state["mid"] = mid
    st.session_state["small"] = small

st.markdown("</div>", unsafe_allow_html=True)

# =============================
# Apply Filters
# =============================
fdf = df.copy()
start_dt = pd.to_datetime(start_d)
end_dt = pd.to_datetime(end_d) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
fdf = fdf[(fdf["날짜"] >= start_dt) & (fdf["날짜"] <= end_dt)]

if f_channel != "전체":
    fdf = fdf[fdf["채널"] == f_channel]
if f_company != "전체":
    fdf = fdf[fdf["기업명"] == f_company]

big = st.session_state.get("big", "전체")
mid = st.session_state.get("mid", "전체")
small = st.session_state.get("small", "전체")

if big != "전체":
    fdf = fdf[fdf["대분류"] == big]
if mid != "전체":
    fdf = fdf[fdf["중분류"] == mid]
if small != "전체":
    fdf = fdf[fdf["소분류"] == small]

# =============================
# KPI
# =============================
total = len(fdf)
by_ch = fdf["채널"].value_counts().to_dict()
cnt_tel = by_ch.get("유선", 0)
cnt_chat = by_ch.get("채팅", 0)
cnt_board = by_ch.get("게시판", 0)
corp_cnt = fdf["기업명"].nunique()

k1, k2, k3, k4 = st.columns(4)
with k1: kpi("전체 인입 건수", fmt_int(total), f"기업 수: {fmt_int(corp_cnt)}", color="#111827")
with k2: kpi("유선", fmt_int(cnt_tel), f"비중: {safe_ratio(cnt_tel, total):.1f}%", color=CHANNEL_COLOR_MAP["유선"])
with k3: kpi("채팅", fmt_int(cnt_chat), f"비중: {safe_ratio(cnt_chat, total):.1f}%", color=CHANNEL_COLOR_MAP["채팅"])
with k4: kpi("게시판", fmt_int(cnt_board), f"비중: {safe_ratio(cnt_board, total):.1f}%", color=CHANNEL_COLOR_MAP["게시판"])

st.write("")

# =============================
# TOP ROW: 월별 / 요일 / 시간대
# =============================
a1, a2, a3 = st.columns(3)

with a1:
    with st.container():
        card_title("📅", "월별 인입 추이")
        if fdf.empty:
            st.info("선택 조건에 해당하는 데이터가 없어요.")
        else:
            g = fdf.groupby(["월", "채널"]).size().reset_index(name="건수")
            wide = (
                g.pivot_table(index="월", columns="채널", values="건수", aggfunc="sum", fill_value=0)
                .reset_index()
                .sort_values("월")
            )
            for ch in CHANNELS:
                if ch not in wide.columns:
                    wide[ch] = 0
            wide["총합"] = wide["유선"] + wide["채팅"] + wide["게시판"]
            long = wide.melt(id_vars=["월", "총합"], value_vars=["유선", "채팅", "게시판"], var_name="채널", value_name="건수")
            long["채널"] = pd.Categorical(long["채널"], categories=["유선", "채팅", "게시판"], ordered=True)

            fig = px.bar(long, x="월", y="건수", color="채널", barmode="stack", color_discrete_map=CHANNEL_COLOR_MAP)
            fig.update_layout(**base_layout(CHART_H_TOP, showlegend=True))
            fig.update_layout(legend=dict(orientation="h", x=1.0, xanchor="right", y=1.15, yanchor="top", font=dict(size=11)))
            fig.update_xaxes(type="date", tickformat="%Y.%m", showgrid=False, zeroline=False, showline=False, ticks="outside")
            fig.update_yaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False)
            fig.update_layout(bargap=0.25)
            for _, row in wide.iterrows():
                fig.add_annotation(x=row["월"], y=row["총합"], text=f"{int(row['총합']):,}", showarrow=False, yshift=10, font=dict(size=11, color="#0f172a"))

            best = wide.loc[wide["총합"].idxmax()]
            chips([f"피크 월 <span class='b'>{pd.to_datetime(best['월']).strftime('%Y.%m')}</span> · <span class='b'>{int(best['총합']):,}</span>건"])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with a2:
    with st.container():
        card_title("🗓️", "요일별 인입 추이")
        if fdf.empty:
            st.info("선택 조건에 해당하는 데이터가 없어요.")
        else:
            dow_map = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
            tmp = fdf.copy()
            tmp["요일"] = tmp["날짜"].dt.weekday.map(dow_map)
            order = ["월", "화", "수", "목", "금", "토", "일"]
            gd = tmp.groupby("요일").size().reindex(order, fill_value=0).reset_index()
            gd.columns = ["요일", "건수"]
            best = gd.loc[gd["건수"].idxmax()]
            chips([f"피크 요일 <span class='b'>{best['요일']}</span> · <span class='b'>{int(best['건수']):,}</span>건"])
            figd = px.bar(gd, x="요일", y="건수", text="건수", color_discrete_sequence=[INDIGO_MAIN])
            figd.update_layout(**base_layout(CHART_H_TOP, showlegend=False))
            figd.update_xaxes(type="category", categoryorder="array", categoryarray=order, showgrid=False, zeroline=False, showline=False)
            figd.update_yaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False)
            figd.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(figd, use_container_width=True, config={"displayModeBar": False})

with a3:
    with st.container():
        card_title("⏱️", "시간대별 인입 추이 (08~18시)")
        if fdf.empty:
            st.info("선택 조건에 해당하는 데이터가 없어요.")
        else:
            tmp = fdf.copy()
            tmp["시간"] = tmp["날짜"].dt.hour
            hours = list(range(8, 19))
            gh = tmp.groupby("시간").size().reindex(hours, fill_value=0).reset_index()
            gh.columns = ["시간", "건수"]
            best = gh.loc[gh["건수"].idxmax()]
            chips([f"피크 시간 <span class='b'>{int(best['시간']):02d}시</span> · <span class='b'>{int(best['건수']):,}</span>건"])
            figh = px.line(gh, x="시간", y="건수", markers=True, color_discrete_sequence=[INDIGO_MAIN])
            figh.update_layout(**base_layout(CHART_H_TOP, showlegend=False))
            figh.update_xaxes(tickmode="array", tickvals=hours, ticktext=[f"{h:02d}시" for h in hours], showgrid=False, zeroline=False, showline=False)
            figh.update_yaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False)
            st.plotly_chart(figh, use_container_width=True, config={"displayModeBar": False})

# =============================
# SECOND ROW: 기업 TOP10 + 도넛 (도넛 아래로 확정)
# =============================
b1, b2 = st.columns([1.6, 1.0])

with b1:
    with st.container():
        card_title("🏢", "문의 많은 기업 TOP 10")

        exclude_companies = {"알수없음", "(주)휴넷"}
        top = (
            fdf[~fdf["기업명"].isin(exclude_companies)]
            ["기업명"].dropna()
            .value_counts().head(10)
            .reset_index()
        )
        top.columns = ["기업명", "건수"]

        if top.empty:
            st.info("표시할 기업 데이터가 없어요.")
        else:
            top = top.sort_values("건수", ascending=False).reset_index(drop=True)
            top["순위"] = range(1, len(top) + 1)
            top.loc[top["순위"] == 1, "기업명"] = "👑 " + top.loc[top["순위"] == 1, "기업명"]
            top["그룹"] = top["순위"].apply(lambda r: "TOP5" if r <= 5 else "6~10")
            cat_array = top["기업명"].tolist()

            top1_name = clean_label(top.loc[0, "기업명"])
            top1_cnt = int(top.loc[0, "건수"])
            chips([f"TOP1 <span class='b'>{top1_name}</span> · <span class='b'>{top1_cnt:,}</span>건"])

            figc = px.bar(
                top,
                x="건수",
                y="기업명",
                orientation="h",
                color="그룹",
                color_discrete_map={"TOP5": INDIGO_TOP5, "6~10": INDIGO_6_10},
                text="건수",
            )
            figc.update_layout(**base_layout(CHART_H_SECOND, showlegend=False))
            figc.update_yaxes(categoryorder="array", categoryarray=cat_array[::-1], showgrid=False, zeroline=False, showline=False)
            figc.update_xaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False)
            figc.update_traces(textposition="outside", cliponaxis=False)

            if HAS_PLOTLY_EVENTS:
                selected = plotly_events(
                    figc,
                    click_event=True,
                    hover_event=False,
                    select_event=False,
                    override_height=CHART_H_SECOND,
                    key="evt_company_top10",
                )
                if selected:
                    picked = clean_label(selected[0].get("y", ""))
                    if picked:
                        st.session_state["company"] = picked if picked in companies else "전체"
                        st.rerun()
            else:
                st.plotly_chart(figc, use_container_width=True, config={"displayModeBar": False})

with b2:
    with st.container():
        card_title("🍩", "채널 비중")

        if total == 0:
            st.info("표시할 데이터가 없어요.")
        else:
            donut_df = pd.DataFrame({"채널": ["유선", "채팅", "게시판"], "건수": [cnt_tel, cnt_chat, cnt_board]})
            if donut_df["건수"].sum() == 0:
                st.info("표시할 데이터가 없어요.")
            else:
                figp = px.pie(
                    donut_df,
                    names="채널",
                    values="건수",
                    hole=0.62,
                    color="채널",
                    color_discrete_map=CHANNEL_COLOR_MAP,
                )

                # ✅ 이제 margin 중복 없음(여기서만 커스텀 margin 넣음)
                figp.update_layout(
                    **base_layout(
                        CHART_H_SECOND,
                        showlegend=True,
                        margin=dict(l=12, r=12, t=34, b=44),
                    ),
                    legend=dict(
                        orientation="h",
                        x=0.5, xanchor="center",
                        y=1.08, yanchor="bottom",
                        font=dict(size=11),
                    ),
                )

                # ✅ 원 자체를 아래로
                figp.update_traces(
                    domain=dict(x=[0.0, 1.0], y=[0.00, 0.90]),
                    textposition="inside",
                    texttemplate="%{value:,}<br>(%{percent})",
                    hovertemplate="%{label}<br>%{value:,}건 (%{percent})<extra></extra>",
                )

                # ✅ 가운데 숫자도 같이 아래로
                total_sum = int(donut_df["건수"].sum())
                figp.add_annotation(
                    x=0.5, y=0.45,
                    xref="paper", yref="paper",
                    text=f"<span style='color:#0f172a;font-size:30px;font-weight:950;'>{total_sum:,}</span>",
                    showarrow=False,
                    align="center",
                )

                st.plotly_chart(figp, use_container_width=True, config={"displayModeBar": False})

# =============================
# Bottom: 대/중/소 TOP10
# =============================
EXCLUDE_PATTERN = r"(안내사항없음|자체해결|_자체해결)"
c1, c2, c3 = st.columns(3)

with c1:
    with st.container():
        card_title("🗂️", "대분류 TOP 10")
        top10_like(fdf, "대분류", CHART_H_BOTTOM, exclude_pattern=EXCLUDE_PATTERN)

with c2:
    with st.container():
        card_title("🧩", "중분류 TOP 10")
        top10_like(fdf, "중분류", CHART_H_BOTTOM, exclude_pattern=EXCLUDE_PATTERN)

with c3:
    with st.container():
        card_title("🏷️", "소분류 TOP 10")
        top10_like(fdf, "소분류", CHART_H_BOTTOM, exclude_pattern=EXCLUDE_PATTERN)

st.caption("※ Premium UI v12.4.1 (margin 충돌 에러 해결 + 도넛 세로 중앙 보정 확정)")
