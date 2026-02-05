# app.py
import os
import json
from datetime import datetime, date, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px

# =============================
# Page
# =============================
st.set_page_config(page_title="VOC 대시보드", layout="wide")

# =============================
# Paths
# =============================
DATA_DIR = "data"
MASTER_XLSX = os.path.join(DATA_DIR, "master.xlsx")
MASTER_META = os.path.join(DATA_DIR, "master.meta")

# =============================
# Config
# =============================
REQUIRED_COLS = ["날짜", "기업명", "대분류", "중분류", "소분류", "채널"]
CHANNELS = ["유선", "채팅", "게시판"]

CHANNEL_COLOR_MAP = {
    "유선": "#E53935",
    "채팅": "#1E88E5",
    "게시판": "#FB8C00",
}

EXCLUDE_COMPANY = {"알수없음", "알 수 없음", "unknown", "Unknown", "UNKNOWN", "-", "nan", "None"}
EXCLUDE_CATEGORY = {"안내사항없음_자체해결", "안내사항없음", "자체해결"}

# =============================
# CSS
# =============================
st.markdown(
    """
    <style>
    header[data-testid="stHeader"]{display:none;}
    footer{display:none;}
    #MainMenu{visibility:hidden;}

    div[data-testid="stAppViewContainer"]{
        background:
          radial-gradient(900px 500px at 18% 10%, rgba(99,102,241,0.12), rgba(255,255,255,0) 60%),
          radial-gradient(900px 500px at 82% 0%, rgba(16,185,129,0.10), rgba(255,255,255,0) 55%),
          linear-gradient(180deg, rgba(248,250,252,1), rgba(255,255,255,1));
    }
    .block-container{padding-top:22px; padding-bottom:24px; max-width: 1400px;}

    .card{
        background: rgba(255,255,255,0.82);
        border: 1px solid rgba(15,23,42,0.10);
        border-radius: 18px;
        box-shadow: 0 18px 40px rgba(2,8,23,0.08);
        padding: 16px 16px;
        margin-bottom: 14px;
    }

    .h1{font-size:34px; font-weight:950; letter-spacing:-0.6px; margin:0 0 4px 0; color: rgba(15,23,42,0.92);}
    .sub{font-size:13px; color: rgba(15,23,42,0.55); margin:0 0 10px 0;}

    .chip-wrap{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 10px 0}
    .chip{
        display:inline-block;
        padding:6px 10px;
        border-radius:999px;
        background:rgba(255,255,255,0.88);
        border:1px solid rgba(15,23,42,0.10);
        font-size:12px;
        font-weight:900;
        color:rgba(15,23,42,0.80);
        box-shadow:0 8px 16px rgba(2,8,23,0.06);
    }

    .insight-title{
        font-size:13px;
        font-weight:950;
        color: rgba(15,23,42,0.78);
        margin: 2px 0 6px 0;
    }
    .insight{
        background: rgba(255,255,255,0.92);
        border: 1px solid rgba(15,23,42,0.10);
        border-radius: 16px;
        padding: 12px 14px;
        box-shadow: 0 12px 24px rgba(2,8,23,0.06);
        font-size: 13px;
        color: rgba(15,23,42,0.80);
        line-height: 1.55;
        white-space: pre-line;
        margin-top: 6px;
    }

    /* ✅ KPI 카드 크기 고정(다 똑같이) */
    .kpi{
        background: rgba(255,255,255,0.90);
        border: 1px solid rgba(15,23,42,0.10);
        border-radius: 18px;
        padding: 14px 16px;
        box-shadow: 0 14px 30px rgba(2,8,23,0.08);
        min-height: 120px;
        display:flex;
        flex-direction:column;
        justify-content:space-between;
    }
    .kpi-label{font-size:12px; font-weight:900; color: rgba(15,23,42,0.55);}
    .kpi-value{font-size:28px; font-weight:950; color: rgba(15,23,42,0.92); margin-top:6px;}
    .kpi-sub{font-size:12px; margin-top:10px; color: rgba(15,23,42,0.70); min-height:18px;}

    .mom-pos{color:#10B981; font-weight:950;}
    .mom-neg{color:#EF4444; font-weight:950;}
    .mom-na{color:rgba(15,23,42,0.45); font-weight:900;}

    section[data-testid="stSidebar"] .stButton > button{
        width: 100%;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        gap:8px !important;
        line-height:1.2 !important;
        padding:10px 12px !important;
        border-radius:12px !important;
        white-space:nowrap !important;
    }
    section[data-testid="stSidebar"] .stButton > button span{font-size:14px !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================
# Helpers
# =============================
def s(v):
    return "" if v is None else str(v).strip()

def to_datetime_series(x: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(x):
        return x
    return pd.to_datetime(x, errors="coerce", infer_datetime_format=True)

def card_open():
    st.markdown('<div class="card">', unsafe_allow_html=True)

def card_close():
    st.markdown("</div>", unsafe_allow_html=True)

def render_chips(items: list[str]):
    html = '<div class="chip-wrap">' + "".join([f'<span class="chip">{c}</span>' for c in items]) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

def read_meta_updated_at():
    if os.path.exists(MASTER_META):
        try:
            meta = json.loads(open(MASTER_META, "r", encoding="utf-8").read())
            return meta.get("updated_at") or "-"
        except Exception:
            return "-"
    if os.path.exists(MASTER_XLSX):
        return datetime.fromtimestamp(os.path.getmtime(MASTER_XLSX)).strftime("%Y-%m-%d %H:%M:%S")
    return "-"

def load_master_df():
    if not os.path.exists(MASTER_XLSX):
        return None
    df = pd.read_excel(MASTER_XLSX, sheet_name="master")
    df.columns = [s(c) for c in df.columns]
    return df

def apply_filters(df: pd.DataFrame, start_d: date, end_d: date,
                  channels: list[str], company: str, big: str, mid: str, small: str) -> pd.DataFrame:
    dff = df.copy()
    dff["날짜"] = to_datetime_series(dff["날짜"])
    dff = dff.dropna(subset=["날짜"])

    start_dt = datetime.combine(start_d, datetime.min.time())
    end_dt = datetime.combine(end_d, datetime.max.time())
    dff = dff[(dff["날짜"] >= start_dt) & (dff["날짜"] <= end_dt)]

    if channels:
        dff = dff[dff["채널"].isin(channels)]
    if company != "전체":
        dff = dff[dff["기업명"].astype(str) == company]
    if big != "전체":
        dff = dff[dff["대분류"].astype(str) == big]
    if mid != "전체":
        dff = dff[dff["중분류"].astype(str) == mid]
    if small != "전체":
        dff = dff[dff["소분류"].astype(str) == small]
    return dff

def prev_period_range(start_d: date, end_d: date):
    days = (end_d - start_d).days + 1
    prev_end = start_d - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return prev_start, prev_end

def safe_value_counts(df: pd.DataFrame, col: str):
    if df.empty or col not in df.columns:
        return pd.Series(dtype=int)
    x = df[col].astype(str).fillna("").map(str.strip)
    x = x[(x != "") & (x.str.lower() != "nan") & (x.str.lower() != "none")]
    return x.value_counts()

def build_insight(cur_df: pd.DataFrame, prev_df: pd.DataFrame) -> str:
    cur_total = len(cur_df)
    cur_companies = int(cur_df["기업명"].nunique()) if not cur_df.empty else 0
    cur_ch = cur_df["채널"].value_counts() if not cur_df.empty else pd.Series(dtype=int)

    def ch_line(ch):
        c = int(cur_ch.get(ch, 0))
        share = (c / cur_total * 100.0) if cur_total else 0.0
        return f"- {ch}: {c:,}건 ({share:.1f}%)"

    top_company = safe_value_counts(cur_df, "기업명")
    top_company = top_company[~top_company.index.isin(EXCLUDE_COMPANY)].head(1)

    top_big = safe_value_counts(cur_df, "대분류")
    top_big = top_big[~top_big.index.isin(EXCLUDE_CATEGORY)].head(1)

    top_company_txt = f"{top_company.index[0]} ({int(top_company.iloc[0]):,}건)" if len(top_company) else "-"
    top_big_txt = f"{top_big.index[0]} ({int(top_big.iloc[0]):,}건)" if len(top_big) else "-"

    lines = []
    lines.append(f"① 기간 총 인입: {cur_total:,}건")
    lines.append(f"② 기업 수: {cur_companies:,}개")
    lines.append("③ 채널 현황 (건수/비중)")
    lines.extend([ch_line(ch) for ch in CHANNELS])
    lines.append(f"④ 주요 원인(Top): 기업={top_company_txt}, 카테고리(대분류)={top_big_txt}")
    lines.append("⑤ 조치 제안: Top 기업·Top 카테고리 중심으로 FAQ/가이드 정비 + 급증 구간 원인 점검")
    return "\n".join(lines)

def mom_text(cur: int, prev: int) -> str:
    """✅ 마지막월 기준 전월대비"""
    if prev <= 0:
        return '<span class="mom-na">전월대비 —</span>'
    d = cur - prev
    p = (d / prev) * 100.0
    if d > 0:
        return f'<span class="mom-pos">전월대비 ▲ {d:+,} ({p:+.1f}%)</span>'
    if d < 0:
        return f'<span class="mom-neg">전월대비 ▼ {d:+,} ({p:+.1f}%)</span>'
    return '<span class="mom-na">전월대비 0 (0.0%)</span>'

def compute_last_month_mom(df_filtered: pd.DataFrame):
    """
    ✅ 현재 필터 결과 안에서 '마지막 월'과 '이전 월' 비교
    - 총 인입(건수)
    - 채널별 인입
    - 기업 수(유니크)
    """
    if df_filtered.empty:
        return None

    tmp = df_filtered.copy()
    tmp["날짜"] = to_datetime_series(tmp["날짜"])
    tmp = tmp.dropna(subset=["날짜"])

    tmp["월"] = tmp["날짜"].dt.to_period("M").astype(str)  # 2026-01
    tmp["_sort"] = tmp["날짜"].dt.strftime("%Y%m")

    months = tmp[["_sort", "월"]].drop_duplicates().sort_values("_sort")["월"].tolist()
    if len(months) < 2:
        return None

    last_m = months[-1]
    prev_m = months[-2]

    last_df = tmp[tmp["월"] == last_m]
    prev_df = tmp[tmp["월"] == prev_m]

    last_all = len(last_df)
    prev_all = len(prev_df)

    last_ch = last_df["채널"].value_counts()
    prev_ch = prev_df["채널"].value_counts()

    # ✅ 기업 수(유니크)도 월 기준으로 비교
    last_comp = int(last_df["기업명"].nunique()) if not last_df.empty else 0
    prev_comp = int(prev_df["기업명"].nunique()) if not prev_df.empty else 0

    def fmt_month(m: str) -> str:
        try:
            y, mm = m.split("-")
            return f"{y}.{mm}"
        except Exception:
            return m.replace("-", ".")

    return {
        "last_label": fmt_month(last_m),
        "prev_label": fmt_month(prev_m),
        "last_all": last_all,
        "prev_all": prev_all,
        "last_ch": last_ch,
        "prev_ch": prev_ch,
        "last_companies": last_comp,
        "prev_companies": prev_comp,
    }

def render_kpi_cards(cur_total: int, cur_ch: pd.Series, cur_companies: int, mom_info):
    """✅ KPI: 카드 크기 동일 / 전월대비 표시(기업 수도 포함)"""
    def kpi_card(label: str, value: str, sub_html: str = "") -> str:
        sub = sub_html if sub_html else "&nbsp;"
        return f"""
        <div class="kpi">
          <div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
          </div>
          <div class="kpi-sub">{sub}</div>
        </div>
        """

    if mom_info:
        tag = f"({mom_info['prev_label']} → {mom_info['last_label']})"
        mom_all = mom_text(mom_info["last_all"], mom_info["prev_all"])
        mom_comp = mom_text(mom_info["last_companies"], mom_info["prev_companies"])
        mom_by = {}
        for ch in CHANNELS:
            mom_by[ch] = mom_text(int(mom_info["last_ch"].get(ch, 0)), int(mom_info["prev_ch"].get(ch, 0)))
    else:
        tag = ""
        mom_all = '<span class="mom-na">전월대비 —</span>'
        mom_comp = '<span class="mom-na">전월대비 —</span>'
        mom_by = {ch: '<span class="mom-na">전월대비 —</span>' for ch in CHANNELS}

    cols = st.columns(5, gap="small")

    with cols[0]:
        st.markdown(kpi_card("총 인입", f"{cur_total:,}", f"{mom_all} {tag}"), unsafe_allow_html=True)

    for i, ch in enumerate(CHANNELS, start=1):
        c = int(cur_ch.get(ch, 0))
        share = (c / cur_total * 100.0) if cur_total else 0.0
        sub = f"비중 {share:.1f}% · {mom_by.get(ch, '<span class=\"mom-na\">전월대비 —</span>')} {tag}"
        with cols[i]:
            st.markdown(kpi_card(ch, f"{c:,}", sub), unsafe_allow_html=True)

    # ✅ 기업 수 카드도 전월대비 표시
    with cols[4]:
        st.markdown(kpi_card("기업 수", f"{cur_companies:,}", f"{mom_comp} {tag}"), unsafe_allow_html=True)

def make_bucket_key(df_in: pd.DataFrame, unit: str) -> pd.DataFrame:
    if df_in.empty:
        return df_in
    tmp = df_in.copy()
    tmp["날짜"] = to_datetime_series(tmp["날짜"])

    if unit == "일":
        tmp["집계키"] = tmp["날짜"].dt.strftime("%Y.%m.%d")
        tmp["_sort"] = tmp["날짜"].dt.strftime("%Y%m%d")
    elif unit == "주":
        iso = tmp["날짜"].dt.isocalendar()
        tmp["집계키"] = iso["year"].astype(str) + "W" + iso["week"].astype(str).str.zfill(2)
        tmp["_sort"] = iso["year"].astype(str) + iso["week"].astype(str).str.zfill(2)
    else:
        tmp["집계키"] = tmp["날짜"].dt.strftime("%Y.%m")
        tmp["_sort"] = tmp["날짜"].dt.strftime("%Y%m")
    return tmp

def topn_bar(df: pd.DataFrame, col: str, n=10, excludes=None, topk=5, crown=True):
    vc = safe_value_counts(df, col)
    if excludes:
        vc = vc[~vc.index.isin(excludes)]
    vc = vc.head(n)
    if vc.empty:
        return None

    data = pd.DataFrame({"name": vc.index.tolist(), "count": vc.values.tolist()})
    data = data.sort_values("count", ascending=False).reset_index(drop=True)

    # ✅ TOP1 왕관 👑
    if crown and len(data) > 0:
        data.loc[0, "name"] = "👑 " + str(data.loc[0, "name"])

    # ✅ TOP5 색 다르게
    top_color = "#1E88E5"
    rest_color = "#C7D2FE"
    colors = [top_color if i < topk else rest_color for i in range(len(data))]

    fig = px.bar(data, x="count", y="name", orientation="h", text="count")
    fig.update_traces(
        marker=dict(color=colors),
        texttemplate="%{text:,}",
        textposition="outside",
        cliponaxis=False
    )
    fig.update_layout(
        height=460,
        margin=dict(l=10, r=40, t=10, b=10),
        yaxis_title="",
        xaxis_title="건수",
        yaxis=dict(categoryorder="total ascending"),
        showlegend=False
    )
    fig.update_xaxes(rangemode="tozero")
    return fig

# =============================
# Sidebar
# =============================
st.sidebar.title("VOC 대시보드")
menu = st.sidebar.radio("메뉴", ["app", "관리자"], index=0)
if menu == "관리자":
    st.warning("관리자는 좌측 pages의 ‘01_관리자’ 페이지에서 실행됩니다.")
    st.stop()

st.sidebar.subheader("필터")
unit = st.sidebar.radio("집계 단위", ["일", "주", "월"], index=2)

# =============================
# Load data
# =============================
df = load_master_df()
if df is None:
    st.error("master.xlsx가 없습니다. 관리자에서 먼저 업로드/저장하세요.")
    st.stop()

missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(f"master.xlsx 필수 컬럼 누락: {missing}\n현재 컬럼: {list(df.columns)}")
    st.stop()

df["날짜"] = to_datetime_series(df["날짜"])
df = df.dropna(subset=["날짜"])

min_date = df["날짜"].min().date()
max_date = df["날짜"].max().date()

# ✅ 기본 기간은 항상 "전체"
if "_preset" not in st.session_state:
    st.session_state["_preset"] = "전체"

st.sidebar.markdown("**기간**")
p1 = st.sidebar.columns(3)
if p1[0].button("7일"):
    st.session_state["_preset"] = "7일"
if p1[1].button("30일"):
    st.session_state["_preset"] = "30일"
if p1[2].button("3개월"):
    st.session_state["_preset"] = "3개월"
p2 = st.sidebar.columns(2)
if p2[0].button("1년"):
    st.session_state["_preset"] = "1년"
if p2[1].button("전체"):
    st.session_state["_preset"] = "전체"

preset = st.session_state.get("_preset")

if preset == "7일":
    start_default, end_default = max(max_date - timedelta(days=6), min_date), max_date
elif preset == "30일":
    start_default, end_default = max(max_date - timedelta(days=29), min_date), max_date
elif preset == "3개월":
    start_default, end_default = max(max_date - timedelta(days=90), min_date), max_date
elif preset == "1년":
    start_default, end_default = max(max_date - timedelta(days=365), min_date), max_date
else:
    start_default, end_default = min_date, max_date

date_range = st.sidebar.date_input("기간 선택", value=(start_default, end_default))
start_d, end_d = (date_range if isinstance(date_range, tuple) and len(date_range) == 2 else (start_default, end_default))

# 채널 토글
st.sidebar.markdown("**채널**")
if "sel_channels" not in st.session_state:
    st.session_state.sel_channels = CHANNELS.copy()

def toggle_channel(ch):
    cur = st.session_state.sel_channels
    st.session_state.sel_channels = ([x for x in cur if x != ch] if ch in cur else (cur + [ch]))

def set_all_channels():
    st.session_state.sel_channels = CHANNELS.copy()

def is_on(ch):
    return ch in st.session_state.sel_channels

st.sidebar.button(("☎️ 유선" if is_on("유선") else "유선"), on_click=toggle_channel, args=("유선",))
st.sidebar.button(("💬 채팅" if is_on("채팅") else "채팅"), on_click=toggle_channel, args=("채팅",))
st.sidebar.button(("📝 게시판" if is_on("게시판") else "게시판"), on_click=toggle_channel, args=("게시판",))
st.sidebar.button("채널 전체 선택", on_click=set_all_channels)
st.sidebar.caption(f"선택됨: {', '.join(st.session_state.sel_channels) if st.session_state.sel_channels else '없음'}")

# 상세필터
with st.sidebar.expander("상세필터", expanded=False):
    companies = ["전체"] + sorted([x for x in df["기업명"].dropna().astype(str).unique().tolist() if x.strip()])
    company = st.selectbox("기업", companies, index=0)

    bigs = ["전체"] + sorted(df["대분류"].dropna().astype(str).unique().tolist())
    big = st.selectbox("대분류", bigs, index=0)

    df_big = df if big == "전체" else df[df["대분류"].astype(str) == big]
    mids = ["전체"] + sorted(df_big["중분류"].dropna().astype(str).unique().tolist())
    mid = st.selectbox("중분류", mids, index=0)

    df_mid = df_big if mid == "전체" else df_big[df_big["중분류"].astype(str) == mid]
    smalls = ["전체"] + sorted(df_mid["소분류"].dropna().astype(str).unique().tolist())
    small = st.selectbox("소분류", smalls, index=0)

# =============================
# Current / Previous period
# =============================
cur_df = apply_filters(df, start_d, end_d, st.session_state.sel_channels, company, big, mid, small)
prev_start, prev_end = prev_period_range(start_d, end_d)
prev_df = apply_filters(df, prev_start, prev_end, st.session_state.sel_channels, company, big, mid, small)

cur_total = len(cur_df)
cur_companies = int(cur_df["기업명"].nunique()) if not cur_df.empty else 0
cur_ch = cur_df["채널"].value_counts() if not cur_df.empty else pd.Series(dtype=int)

# ✅ 마지막 월 기준 전월대비 계산
mom_info = compute_last_month_mom(cur_df)

# =============================
# Header
# =============================
card_open()
st.markdown('<div class="h1">VOC 대시보드</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">전사 공유용 요약 + 전월대비 변화 + TOP 이슈를 한 번에 봅니다.</div>', unsafe_allow_html=True)

render_chips([
    f"집계: {unit}",
    f"기간: {start_d} ~ {end_d}",
    f"채널: {', '.join(st.session_state.sel_channels) if st.session_state.sel_channels else '없음'}",
    f"기업: {company}",
    f"대: {big}",
    f"중: {mid}",
    f"소: {small}",
])

st.markdown('<div class="insight-title">요약</div>', unsafe_allow_html=True)
st.markdown(f'<div class="insight">{build_insight(cur_df, prev_df)}</div>', unsafe_allow_html=True)

render_kpi_cards(cur_total, cur_ch, cur_companies, mom_info)

st.caption(f"master 업데이트: {read_meta_updated_at()}")
card_close()

# =============================
# Charts: 기간추이 / 채널비중
# =============================
c1, c2 = st.columns([1.15, 0.85], gap="large")

with c1:
    card_open()
    st.subheader("기간 추이 (채널별)")

    if cur_df.empty:
        st.info("필터 결과가 없습니다.")
    else:
        tmp = make_bucket_key(cur_df, unit)
        g = (
            tmp.groupby(["집계키", "_sort", "채널"], as_index=False)
               .size()
               .rename(columns={"size": "count"})
        )
        g = g.sort_values(["_sort", "채널"], ascending=[True, True])

        n_points = g["집계키"].nunique()
        use_line = (unit == "월" and n_points > 10)

        if use_line:
            fig = px.line(
                g,
                x="집계키",
                y="count",
                color="채널",
                markers=True,
                color_discrete_map=CHANNEL_COLOR_MAP,
            )
        else:
            fig = px.bar(
                g,
                x="집계키",
                y="count",
                color="채널",
                barmode="group",
                text="count",
                color_discrete_map=CHANNEL_COLOR_MAP,
            )
            fig.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)

        fig.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="집계기준",
            yaxis_title="건수",
            legend_title_text="채널",
        )
        fig.update_xaxes(type="category")
        fig.update_yaxes(rangemode="tozero")

        st.plotly_chart(fig, use_container_width=True)

    card_close()

with c2:
    card_open()
    st.subheader("채널 비중 (현재기간)")

    if cur_df.empty:
        st.info("필터 결과가 없습니다.")
    else:
        p = cur_df["채널"].value_counts().reset_index()
        p.columns = ["채널", "count"]

        fig2 = px.pie(
            p,
            names="채널",
            values="count",
            hole=0.55,
            color="채널",
            color_discrete_map=CHANNEL_COLOR_MAP,
        )
        fig2.update_traces(texttemplate="%{label}<br>%{percent} (%{value:,}건)")
        fig2.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10))

        st.plotly_chart(fig2, use_container_width=True)

    card_close()

# =============================
# TOP10
# =============================
card_open()
st.subheader("문의 많은 기업 TOP10 (알수없음 제외)")
fig_co = topn_bar(cur_df, "기업명", n=10, excludes=EXCLUDE_COMPANY, topk=5, crown=True)
if fig_co is None:
    st.info("표시할 데이터가 없습니다.")
else:
    st.plotly_chart(fig_co, use_container_width=True)
card_close()

tabs = st.tabs(["대분류 TOP10", "중분류 TOP10", "소분류 TOP10"])

with tabs[0]:
    card_open()
    st.subheader("문의 많은 카테고리 TOP10 (대분류)  ※ 안내사항없음_자체해결 제외")
    fig_big = topn_bar(cur_df, "대분류", n=10, excludes=EXCLUDE_CATEGORY, topk=5, crown=True)
    if fig_big is None:
        st.info("표시할 데이터가 없습니다.")
    else:
        st.plotly_chart(fig_big, use_container_width=True)
    card_close()

with tabs[1]:
    card_open()
    st.subheader("문의 많은 카테고리 TOP10 (중분류)  ※ 안내사항없음_자체해결 제외")
    fig_mid = topn_bar(cur_df, "중분류", n=10, excludes=EXCLUDE_CATEGORY, topk=5, crown=True)
    if fig_mid is None:
        st.info("표시할 데이터가 없습니다.")
    else:
        st.plotly_chart(fig_mid, use_container_width=True)
    card_close()

with tabs[2]:
    card_open()
    st.subheader("문의 많은 카테고리 TOP10 (소분류)  ※ 안내사항없음_자체해결 제외")
    fig_small = topn_bar(cur_df, "소분류", n=10, excludes=EXCLUDE_CATEGORY, topk=5, crown=True)
    if fig_small is None:
        st.info("표시할 데이터가 없습니다.")
    else:
        st.plotly_chart(fig_small, use_container_width=True)
    card_close()

# 상세 데이터는 요청대로 없음
