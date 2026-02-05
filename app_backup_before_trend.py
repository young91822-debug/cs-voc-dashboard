import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import os

st.set_page_config(page_title="VOC 대시보드", layout="wide")

# =============================
# ✅ Premium UI
# =============================
st.markdown(
    """
<style>
.stApp { background: linear-gradient(180deg, #FAFAFB 0%, #F3F4F6 100%); }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px; }
h1, h2, h3 { letter-spacing: -0.02em; }
.small-muted { color: rgba(17,24,39,0.60); font-size: 12px; line-height: 1.55; }

[data-testid="stMetric"] {
  background: rgba(255,255,255,0.78);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  padding: 12px 14px;
  box-shadow: 0 10px 22px rgba(17, 24, 39, 0.06);
  min-height: 118px;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
}
[data-testid="stMetricValue"] { color:#111827; font-weight:800; line-height:1.12; font-size:30px; }
[data-testid="stMetricValue"] > div {
  white-space: normal !important;
  word-break: break-word !important;
  overflow: visible !important;
}
@media (max-width: 1200px){
  [data-testid="stMetricValue"]{font-size:26px;}
  [data-testid="stMetric"]{min-height:124px;}
}

.badge {
  display:inline-block; padding:4px 10px; border-radius:999px;
  font-size:12px; font-weight:800;
  background: rgba(37,99,235,0.12); color:#1D4ED8;
  border: 1px solid rgba(29,78,216,0.18);
}
.card {
  background: rgba(255,255,255,0.82);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 18px;
  padding: 16px 18px;
  box-shadow: 0 12px 26px rgba(17, 24, 39, 0.07);
}
.ai-title {
  font-size: 16px;
  font-weight: 900;
  color:#111827;
}
.ai-sub {
  margin-top: 4px;
  color: rgba(17,24,39,0.60);
  font-size: 12px;
}
.ai-body {
  margin-top: 12px;
  font-size: 13px;
  color: rgba(17,24,39,0.86);
  line-height: 1.65;
}
.ai-kpi {
  display: grid;
  grid-template-columns: repeat(3, minmax(0,1fr));
  gap: 10px;
  margin-top: 12px;
}
.ai-kpi-item {
  background: rgba(249,250,251,0.95);
  border: 1px solid rgba(15,23,42,0.06);
  border-radius: 14px;
  padding: 10px 12px;
}
.ai-kpi-label { font-size: 11px; color: rgba(17,24,39,0.60); font-weight: 800; }
.ai-kpi-val { margin-top: 4px; font-size: 14px; font-weight: 900; color:#111827; }
.ai-foot {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(15,23,42,0.12);
  font-size: 12px;
  color: rgba(17,24,39,0.65);
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Config
# -----------------------------
REQUIRED_COLS = ["날짜", "기업명", "대분류", "중분류", "소분류"]
CHANNELS = ["유선", "채팅", "게시판"]
CHANNEL_COLOR_MAP = {"유선": "#EF4444", "게시판": "#F59E0B", "채팅": "#3B82F6"}

COL_ALIAS = {
    "문의일": "날짜",
    "접수일": "날짜",
    "등록일": "날짜",
    "일자": "날짜",
    "날 짜": "날짜",
    "기업": "기업명",
    "회사": "기업명",
    "회사명": "기업명",
    "고객사": "기업명",
    "법인명": "기업명",
    "대분류명": "대분류",
    "중분류명": "중분류",
    "소분류명": "소분류",
    "대 분류": "대분류",
    "중 분류": "중분류",
    "소 분류": "소분류",
}

DATA_DIR = "data"
LOCAL_MASTER_PATH = os.path.join(DATA_DIR, "master.xlsx")

def load_master_bytes():
    try:
        if os.path.exists(LOCAL_MASTER_PATH):
            with open(LOCAL_MASTER_PATH, "rb") as f:
                return f.read()
        return None
    except Exception:
        return None

def load_master_updated_at():
    meta_path = os.path.join(DATA_DIR, "master.meta.txt")
    if os.path.exists(meta_path):
        try:
            return open(meta_path, "r", encoding="utf-8").read().strip()
        except Exception:
            return None
    return None

def clean_colname(x) -> str:
    s = str(x)
    s = s.replace("\u00a0", " ")
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = " ".join(s.split()).strip()
    return s

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [clean_colname(c) for c in df.columns]
    return df

def apply_alias(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for c in df.columns:
        key = clean_colname(c)
        if key in COL_ALIAS:
            rename_map[c] = COL_ALIAS[key]
    if rename_map:
        df = df.rename(columns=rename_map)
    return normalize_cols(df)

def validate_cols(df: pd.DataFrame) -> list:
    return [c for c in REQUIRED_COLS if c not in df.columns]

def parse_date_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")

def add_time_grain(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["날짜"]).copy()
    df["일"] = df["날짜"].dt.date
    iso = df["날짜"].dt.isocalendar()
    df["주"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    df["월"] = df["날짜"].dt.to_period("M").astype(str)
    return df

def safe_div(a, b):
    if b is None or b == 0 or pd.isna(b):
        return None
    return a / b

def pct_fmt(p):
    if p is None or pd.isna(p):
        return "-"
    return f"{p*100:.1f}%"

def arrow_from_pct(p):
    if p is None or pd.isna(p):
        return ""
    if p > 0:
        return "▲"
    if p < 0:
        return "▼"
    return "–"

def parse_ymd(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def get_qp():
    try:
        return dict(st.query_params)
    except Exception:
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}

def qp_get1(qp, key, default=None):
    v = qp.get(key, default)
    if isinstance(v, list):
        return v[0] if v else default
    return v

def qp_get_list(qp, key, default_list=None):
    v = qp.get(key, None)
    if v is None:
        return default_list if default_list is not None else []
    if isinstance(v, list):
        v = v[0] if len(v) == 1 else ",".join(v)
    if isinstance(v, str):
        return [x for x in v.split(",") if x != ""]
    return default_list if default_list is not None else []

def top_table(data: pd.DataFrame, col: str, n: int = 10) -> pd.DataFrame:
    t = data[col].astype(str).value_counts().head(n).reset_index()
    t.columns = [col, "건수"]
    return t

def make_rank_bar(df: pd.DataFrame, cat_col: str, val_col: str = "건수",
                  title: str = "", top_k: int = 5, height: int = 420,
                  orientation: str = "h"):
    if df is None or df.empty:
        return None
    t = df.copy().reset_index(drop=True)
    t["순위"] = range(1, len(t) + 1)
    t["구분"] = t["순위"].apply(lambda r: f"TOP{top_k}" if r <= top_k else "기타")
    t_plot = t.sort_values(val_col, ascending=True)

    fig = px.bar(
        t_plot,
        x=val_col if orientation == "h" else cat_col,
        y=cat_col if orientation == "h" else val_col,
        orientation=orientation,
        text=val_col,
        color="구분",
        color_discrete_map={f"TOP{top_k}": "#2563EB", "기타": "#CBD5E1"},
        title=title,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=50, t=55, b=10),
        legend_title_text="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    if orientation == "h":
        fig.update_layout(yaxis=dict(categoryorder="array", categoryarray=t_plot[cat_col].tolist()))
        fig.update_xaxes(title=val_col)
        fig.update_yaxes(title="")
    else:
        fig.update_layout(xaxis=dict(categoryorder="array", categoryarray=t_plot[cat_col].tolist()))
        fig.update_xaxes(title="")
        fig.update_yaxes(title=val_col)
    return fig

# =============================
# ✅ Dashboard
# =============================
st.title("VOC 대시보드")
updated_at = load_master_updated_at()
st.caption(f"master 업데이트: {updated_at or '없음'}")

mb = load_master_bytes()
if mb is None:
    st.warning("저장된 master가 없습니다. 관리자 페이지에서 master.xlsx를 먼저 업로드/저장해주세요.")
    st.stop()

master_file = io.BytesIO(mb)
dfm = pd.read_excel(master_file, sheet_name="master")
dfm = normalize_cols(dfm)
dfm = apply_alias(dfm)

missing = validate_cols(dfm)
if missing:
    st.error(f"master에 필수 컬럼이 없습니다: {missing} / 실제 컬럼: {dfm.columns.tolist()}")
    st.stop()

if "채널" not in dfm.columns:
    st.error("master에 '채널' 컬럼이 없습니다. 관리자 저장 로직을 확인하세요.")
    st.stop()

dfm["날짜"] = parse_date_series(dfm["날짜"])
df = add_time_grain(dfm[REQUIRED_COLS + ["채널"]].copy())

qp = get_qp()

# -----------------------------
# Sidebar Filters
# -----------------------------
st.sidebar.header("필터")
unit = st.sidebar.radio("집계 단위", ["일", "주", "월"], index=2)

qp_channels = qp_get_list(qp, "channels", None)
default_channels = [c for c in CHANNELS if (not qp_channels or c in qp_channels)]
channels = st.sidebar.multiselect("채널", options=CHANNELS, default=default_channels)

min_d, max_d = df["날짜"].min(), df["날짜"].max()
default_start = parse_ymd(qp_get1(qp, "start", "")) or min_d.date()
default_end = parse_ymd(qp_get1(qp, "end", "")) or max_d.date()

if default_start < min_d.date():
    default_start = min_d.date()
if default_end > max_d.date():
    default_end = max_d.date()
if default_start > default_end:
    default_start, default_end = min_d.date(), max_d.date()

date_range = st.sidebar.date_input(
    "기간",
    value=(default_start, default_end),
    min_value=min_d.date(),
    max_value=max_d.date(),
)
start_date, end_date = date_range if isinstance(date_range, tuple) else (min_d.date(), max_d.date())

base = df.copy()
base = base[(base["날짜"].dt.date >= start_date) & (base["날짜"].dt.date <= end_date)]
base = base[base["채널"].isin(channels)]

companies = sorted(base["기업명"].dropna().astype(str).unique().tolist())
company_options = ["전체"] + companies
qp_company = qp_get1(qp, "company", "전체")
default_company = qp_company if qp_company in company_options else "전체"
sel_company = st.sidebar.selectbox("기업명", options=company_options, index=company_options.index(default_company))

fdf = base.copy()
if sel_company != "전체":
    fdf = fdf[fdf["기업명"].astype(str) == str(sel_company)]

L_opts = sorted(fdf["대분류"].dropna().astype(str).unique().tolist())
qp_L = qp_get_list(qp, "L", [])
default_L = [x for x in qp_L if x in L_opts]
sel_L = st.sidebar.multiselect("대분류", options=L_opts, default=default_L)
tmp = fdf.copy()
if sel_L:
    tmp = tmp[tmp["대분류"].astype(str).isin([str(x) for x in sel_L])]

M_opts = sorted(tmp["중분류"].dropna().astype(str).unique().tolist())
qp_M = qp_get_list(qp, "M", [])
default_M = [x for x in qp_M if x in M_opts]
sel_M = st.sidebar.multiselect("중분류", options=M_opts, default=default_M)
tmp2 = tmp.copy()
if sel_M:
    tmp2 = tmp2[tmp2["중분류"].astype(str).isin([str(x) for x in sel_M])]

S_opts = sorted(tmp2["소분류"].dropna().astype(str).unique().tolist())
qp_S = qp_get_list(qp, "S", [])
default_S = [x for x in qp_S if x in S_opts]
sel_S = st.sidebar.multiselect("소분류", options=S_opts, default=default_S)
if sel_S:
    tmp2 = tmp2[tmp2["소분류"].astype(str).isin([str(x) for x in sel_S])]

fdf = tmp2
if fdf.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# -----------------------------
# 최신월/전월 계산
# -----------------------------
fdf["_월p"] = pd.PeriodIndex(fdf["월"], freq="M")
months_sorted = sorted(fdf["_월p"].unique())
latest_m = months_sorted[-1] if months_sorted else None
prev_m = months_sorted[-2] if len(months_sorted) >= 2 else None

def count_in_month(df_, m):
    if m is None:
        return None
    return int((df_["_월p"] == m).sum())

total_latest = count_in_month(fdf, latest_m)
total_prev = count_in_month(fdf, prev_m)
total_delta_pct = safe_div((total_latest - total_prev), total_prev) if (total_latest is not None and total_prev is not None) else None

# =============================
# ✅ 전월 대비 자동 요약 (AI처럼)
# =============================
st.markdown(
    f"""
<div class="card">
  <div style="display:flex; align-items:center; gap:10px;">
    <span class="badge">전월 대비 자동 요약</span>
    <div class="ai-title">이번 달 VOC 변화 요약</div>
  </div>
  <div class="ai-sub">
    기준: 최신월 {str(latest_m) if latest_m is not None else "-"} vs 전월 {str(prev_m) if prev_m is not None else "-"} · 현재 필터(기간/채널/기업/분류) 반영
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.write("")

def build_monthly_insight(df_):
    if latest_m is None or prev_m is None:
        return (
            "전월 비교가 불가합니다.",
            ["최소 2개월 데이터가 있어야 전월 대비 분석이 가능합니다."],
            {"전체 변화": "-", "가장 큰 증가": "-", "가장 큰 감소": "-"},
        )

    # 채널별 변화
    ch_cur = df_[df_["_월p"] == latest_m]["채널"].value_counts()
    ch_prv = df_[df_["_월p"] == prev_m]["채널"].value_counts()
    ch_rows = []
    for ch in CHANNELS:
        a = int(ch_cur.get(ch, 0))
        b = int(ch_prv.get(ch, 0))
        p = safe_div((a - b), b)
        ch_rows.append((ch, a, b, p, a - b))
    ch_rows_sorted = sorted(ch_rows, key=lambda x: x[4], reverse=True)
    best_ch = ch_rows_sorted[0]

    dims = ["채널", "대분류", "중분류", "소분류"]
    mcnt = df_.groupby(["_월p"] + dims).size().reset_index(name="건수")
    cur = mcnt[mcnt["_월p"] == latest_m].copy().rename(columns={"건수": "최근월"})
    prv = mcnt[mcnt["_월p"] == prev_m].copy().rename(columns={"건수": "전월"})
    t = cur.merge(prv[dims + ["전월"]], on=dims, how="left")
    t["전월"] = t["전월"].fillna(0).astype(int)
    t["증가"] = (t["최근월"] - t["전월"]).astype(int)

    inc = t[t["증가"] > 0].sort_values(["증가", "최근월"], ascending=False)
    dec = t[t["증가"] < 0].sort_values(["증가", "최근월"], ascending=True)

    def fmt_item(r):
        pct = safe_div(r["증가"], r["전월"]) if r["전월"] > 0 else None
        pct_s = pct_fmt(pct)
        return f"[{r['채널']}] {r['소분류']} (대:{r['대분류']}/중:{r['중분류']}) · {r['전월']:,}→{r['최근월']:,} (+{r['증가']:,}, {pct_s})"

    top_inc_txt = fmt_item(inc.iloc[0]) if not inc.empty else "증가 항목이 없습니다."
    top_dec_txt = (
        f"[{dec.iloc[0]['채널']}] {dec.iloc[0]['소분류']} (대:{dec.iloc[0]['대분류']}/중:{dec.iloc[0]['중분류']}) · "
        f"{int(dec.iloc[0]['전월']):,}→{int(dec.iloc[0]['최근월']):,} ({int(dec.iloc[0]['증가']):,})"
        if not dec.empty else "감소 항목이 없습니다."
    )

    headline = (
        f"전체 문의는 전월 대비 {arrow_from_pct(total_delta_pct)} {pct_fmt(total_delta_pct)} 변화했습니다."
        if total_delta_pct is not None else "전체 문의 변화율은 계산할 수 없습니다."
    )

    bullets = [
        f"채널 변화: {best_ch[0]}이(가) 가장 크게 변동했습니다. ({best_ch[2]:,}→{best_ch[1]:,}, {arrow_from_pct(best_ch[3])} {pct_fmt(best_ch[3])})",
        f"증가 포인트: {top_inc_txt}",
        f"감소 포인트: {top_dec_txt}",
    ]

    kpis = {
        "전체 변화": f"{arrow_from_pct(total_delta_pct)} {pct_fmt(total_delta_pct)}" if total_delta_pct is not None else "-",
        "가장 큰 증가": (inc.iloc[0]["소분류"] if not inc.empty else "-"),
        "가장 큰 감소": (dec.iloc[0]["소분류"] if not dec.empty else "-"),
    }
    return headline, bullets, kpis

headline, bullets, kpis = build_monthly_insight(fdf)

st.markdown(
    f"""
<div class="card">
  <div class="ai-body"><b>{headline}</b></div>

  <div class="ai-body" style="margin-top:10px;">
    <div style="font-weight:900; margin-bottom:6px;">핵심 포인트</div>
    <ul style="margin: 0; padding-left: 18px;">
      <li style="margin-bottom:6px;">{bullets[0]}</li>
      <li style="margin-bottom:6px;">{bullets[1]}</li>
      <li style="margin-bottom:0;">{bullets[2]}</li>
    </ul>
  </div>

  <div class="ai-kpi">
    <div class="ai-kpi-item">
      <div class="ai-kpi-label">전월 대비 전체</div>
      <div class="ai-kpi-val">{kpis["전체 변화"]}</div>
    </div>
    <div class="ai-kpi-item">
      <div class="ai-kpi-label">증가 TOP</div>
      <div class="ai-kpi-val">{kpis["가장 큰 증가"]}</div>
    </div>
    <div class="ai-kpi-item">
      <div class="ai-kpi-label">감소 TOP</div>
      <div class="ai-kpi-val">{kpis["가장 큰 감소"]}</div>
    </div>
  </div>

  <div class="ai-foot">
    ※ 이 요약은 “현재 선택 조건” 기준으로 월간 변화를 자동 정리한 것입니다. (전월 0건 항목은 % 대신 ‘-’)
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.divider()

# =============================
# 1) KPI (요약)
# =============================
st.subheader("요약")

top_L = fdf["대분류"].astype(str).value_counts().head(1)
top_M = fdf["중분류"].astype(str).value_counts().head(1)
top_S = fdf["소분류"].astype(str).value_counts().head(1)

top_L_name = "-" if top_L.empty else str(top_L.index[0])
top_M_name = "-" if top_M.empty else str(top_M.index[0])
top_S_name = "-" if top_S.empty else str(top_S.index[0])

top_L_cnt = 0 if top_L.empty else int(top_L.iloc[0])
top_M_cnt = 0 if top_M.empty else int(top_M.iloc[0])
top_S_cnt = 0 if top_S.empty else int(top_S.iloc[0])

k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "총 문의(선택조건)",
    f"{len(fdf):,}건",
    None if total_delta_pct is None else f"{arrow_from_pct(total_delta_pct)} {pct_fmt(total_delta_pct)} (최근월 기준)",
)
k2.metric("Top 대분류", top_L_name, f"{top_L_cnt:,}건")
k3.metric("Top 중분류", top_M_name, f"{top_M_cnt:,}건")
k4.metric("Top 소분류", top_S_name, f"{top_S_cnt:,}건")

# ✅✅ 여기! 요약 밑에 “추이 & 채널 구성” 복구
st.divider()
st.subheader("추이 & 채널 구성")

trend_month = (
    fdf.groupby(["월", "채널"])
    .size()
    .reset_index(name="건수")
)

trend_month["_월p"] = pd.PeriodIndex(trend_month["월"], freq="M")
trend_month["월_한글"] = trend_month["_월p"].dt.month.astype(int).astype(str) + "월"
trend_month = trend_month.sort_values(["_월p", "채널"])

month_order = (
    trend_month[["월_한글", "_월p"]]
    .drop_duplicates()
    .sort_values("_월p")["월_한글"]
    .tolist()
)

left, right = st.columns([2.2, 1.2])

with left:
    fig_bar = px.bar(
        trend_month,
        x="월_한글",
        y="건수",
        color="채널",
        barmode="group",
        text="건수",
        color_discrete_map=CHANNEL_COLOR_MAP,
        category_orders={"월_한글": month_order},
        title="월 단위 문의 추이 (채널별)",
    )
    fig_bar.update_traces(textposition="outside", cliponaxis=False)
    fig_bar.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=60, b=10),
        legend_title_text="",
        yaxis_title="건수",
        xaxis_title="월",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with right:
    ch = fdf["채널"].value_counts().reset_index()
    ch.columns = ["채널", "건수"]
    figP = px.pie(
        ch,
        names="채널",
        values="건수",
        hole=0.55,
        title="채널 구성비",
        color="채널",
        color_discrete_map=CHANNEL_COLOR_MAP,
    )
    figP.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=60, b=10),
        legend_title_text="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(figP, use_container_width=True)

st.divider()

# =============================
# 문의 많은 기업 TOP10 (표 왼쪽 / 차트 오른쪽, TOP5 강조)
# =============================
st.subheader("문의 많은 기업 TOP10 (현재 기간/채널/분류 기준)")
comp10 = fdf["기업명"].astype(str).value_counts().head(10).reset_index()
comp10.columns = ["기업명", "건수"]

left, right = st.columns([1.25, 1.0])

with left:
    show = comp10.copy()
    show.index = range(1, len(show) + 1)
    try:
        sty = show.style.apply(
            lambda row: ["background-color: rgba(37,99,235,0.10); font-weight:700;" if row.name < 5 else "" for _ in row],
            axis=1
        )
        st.dataframe(sty, use_container_width=True, height=420)
    except Exception:
        st.dataframe(show, use_container_width=True, height=420)

with right:
    fig_comp = make_rank_bar(
        comp10, cat_col="기업명", val_col="건수",
        title="기업 TOP10", top_k=5, height=420, orientation="h"
    )
    if fig_comp is not None:
        st.plotly_chart(fig_comp, use_container_width=True)

st.divider()

# =============================
# Top 분석 (차트 위 / 표 아래, TOP5 강조)
# =============================
st.subheader("Top 분석")
tab1, tab2, tab3 = st.tabs(["대분류 Top 10", "중분류 Top 10", "소분류 Top 10"])

with tab1:
    tL = top_table(fdf, "대분류", n=10)
    figL = make_rank_bar(tL, "대분류", "건수", "대분류 Top 10", 5, 420, "h")
    if figL is not None:
        st.plotly_chart(figL, use_container_width=True)
    show = tL.copy()
    show.index = range(1, len(show) + 1)
    try:
        sty = show.style.apply(
            lambda row: ["background-color: rgba(37,99,235,0.10); font-weight:700;" if row.name < 5 else "" for _ in row],
            axis=1
        )
        st.dataframe(sty, use_container_width=True, height=360)
    except Exception:
        st.dataframe(show, use_container_width=True, height=360)

with tab2:
    tM = top_table(fdf, "중분류", n=10)
    figM = make_rank_bar(tM, "중분류", "건수", "중분류 Top 10", 5, 420, "h")
    if figM is not None:
        st.plotly_chart(figM, use_container_width=True)
    show = tM.copy()
    show.index = range(1, len(show) + 1)
    try:
        sty = show.style.apply(
            lambda row: ["background-color: rgba(37,99,235,0.10); font-weight:700;" if row.name < 5 else "" for _ in row],
            axis=1
        )
        st.dataframe(sty, use_container_width=True, height=360)
    except Exception:
        st.dataframe(show, use_container_width=True, height=360)

with tab3:
    tS = top_table(fdf, "소분류", n=10)
    figS = make_rank_bar(tS, "소분류", "건수", "소분류 Top 10", 5, 420, "h")
    if figS is not None:
        st.plotly_chart(figS, use_container_width=True)
    show = tS.copy()
    show.index = range(1, len(show) + 1)
    try:
        sty = show.style.apply(
            lambda row: ["background-color: rgba(37,99,235,0.10); font-weight:700;" if row.name < 5 else "" for _ in row],
            axis=1
        )
        st.dataframe(sty, use_container_width=True, height=360)
    except Exception:
        st.dataframe(show, use_container_width=True, height=360)

st.caption("※ 개인정보/상담내용은 포함하지 말고, 분류/기업/날짜만 업로드하세요.")
