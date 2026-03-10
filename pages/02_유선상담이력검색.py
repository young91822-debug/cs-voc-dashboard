import os
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="유선 상담이력 검색", layout="wide")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_XLSX = os.path.join(DATA_DIR, "master.xlsx")

TEXT_CANDIDATES = ["상담메모", "상담내역", "문의내용", "상담내용", "VOC", "내용", "상세내용"]
REQUIRED_COLS = ["날짜", "기업명", "대분류", "중분류", "소분류", "채널"]

st.markdown(
    """
    <style>
    .stApp {
        background: #f6f8fc;
    }
    header[data-testid="stHeader"], div[data-testid="stToolbar"], div[data-testid="stDecoration"], footer {
        display: none !important;
    }
    #MainMenu {
        visibility: hidden;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }
    .page-title {
        font-size: 30px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .page-sub {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 18px;
    }
    .filter-box {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 16px 18px 6px 18px;
        margin-bottom: 18px;
    }
    .result-box {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 16px 18px;
    }
    .result-count {
        font-size: 14px;
        font-weight: 700;
        color: #475569;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def must_cols(df: pd.DataFrame, cols):
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"master.xlsx에 필수 컬럼이 없습니다: {miss}")


@st.cache_data(show_spinner=False)
def load_master(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()

    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]

    must_cols(df, REQUIRED_COLS)

    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    for c in REQUIRED_COLS:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            df.loc[df[c].isin(["nan", "None", "NaN", ""]), c] = None

    for c in TEXT_CANDIDATES:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            df.loc[df[c].isin(["nan", "None", "NaN", ""]), c] = None

    return df


def detect_text_col(df_: pd.DataFrame) -> str | None:
    for c in TEXT_CANDIDATES:
        if c in df_.columns:
            return c
    return None


def contains_search(series: pd.Series, keyword: str) -> pd.Series:
    if not keyword:
        return pd.Series([True] * len(series), index=series.index)

    kw = str(keyword).strip()
    if not kw:
        return pd.Series([True] * len(series), index=series.index)

    return series.fillna("").astype(str).str.contains(re.escape(kw), case=False, na=False)


# -----------------------------
# load
# -----------------------------
df = load_master(MASTER_XLSX)

if df.empty:
    st.error("data/master.xlsx 를 찾을 수 없거나 데이터가 비어있어요.")
    st.stop()

text_col = detect_text_col(df)
if not text_col:
    st.error("master.xlsx 에 상담메모/상담내역 컬럼이 없어요.")
    st.stop()

df = df[df["채널"] == "유선"].copy()

if df.empty:
    st.warning("유선 데이터가 없어요.")
    st.stop()

# 검색 대상: 상담메모 + 분류 컬럼 모두 포함
df["_검색대상"] = (
    df[text_col].fillna("").astype(str) + " " +
    df["대분류"].fillna("").astype(str) + " " +
    df["중분류"].fillna("").astype(str) + " " +
    df["소분류"].fillna("").astype(str) + " " +
    df["기업명"].fillna("").astype(str)
)

min_d = pd.to_datetime(df["날짜"]).min().date()
max_d = pd.to_datetime(df["날짜"]).max().date()

st.markdown('<div class="page-title">유선 상담이력 검색</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-sub">검색창에 예를 들어 "수료관련 문의"를 입력하면 해당 문의만 필터되어 보이도록 구성한 화면입니다.</div>',
    unsafe_allow_html=True,
)

# -----------------------------
# filters
# -----------------------------
st.markdown('<div class="filter-box">', unsafe_allow_html=True)

c1, c2, c3 = st.columns([1.8, 1.2, 1.0])

with c1:
    keyword = st.text_input("검색어", placeholder="예: 수료관련 문의, 로그인, 환불, 자동결제")

with c2:
    date_range = st.date_input("기간", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_d, max_d

with c3:
    companies = ["전체"] + sorted(df["기업명"].dropna().unique().tolist())
    company = st.selectbox("기업명", companies, index=0)

c4, c5, c6 = st.columns(3)

with c4:
    big_opts = ["전체"] + sorted(df["대분류"].dropna().unique().tolist())
    big = st.selectbox("대분류", big_opts, index=0)

tmp_mid = df.copy()
if big != "전체":
    tmp_mid = tmp_mid[tmp_mid["대분류"] == big]

with c5:
    mid_opts = ["전체"] + sorted(tmp_mid["중분류"].dropna().unique().tolist())
    mid = st.selectbox("중분류", mid_opts, index=0)

tmp_small = tmp_mid.copy()
if mid != "전체":
    tmp_small = tmp_small[tmp_small["중분류"] == mid]

with c6:
    small_opts = ["전체"] + sorted(tmp_small["소분류"].dropna().unique().tolist())
    small = st.selectbox("소분류", small_opts, index=0)

st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# apply filters
# -----------------------------
fdf = df.copy()

start_dt = pd.to_datetime(start_d)
end_dt = pd.to_datetime(end_d) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

fdf = fdf[
    (pd.to_datetime(fdf["날짜"]) >= start_dt) &
    (pd.to_datetime(fdf["날짜"]) <= end_dt)
].copy()

if company != "전체":
    fdf = fdf[fdf["기업명"] == company]

if big != "전체":
    fdf = fdf[fdf["대분류"] == big]

if mid != "전체":
    fdf = fdf[fdf["중분류"] == mid]

if small != "전체":
    fdf = fdf[fdf["소분류"] == small]

if keyword and str(keyword).strip():
    fdf = fdf[contains_search(fdf["_검색대상"], keyword)].copy()

fdf = fdf.sort_values("날짜", ascending=False).reset_index(drop=True)

# 표시용 컬럼 정리
show_df = fdf.copy()
show_df["날짜"] = pd.to_datetime(show_df["날짜"], errors="coerce").dt.strftime("%Y-%m-%d")

display_cols = ["날짜", "기업명", "대분류", "중분류", "소분류", text_col]
display_names = {
    "날짜": "날짜",
    "기업명": "기업명",
    "대분류": "대분류",
    "중분류": "중분류",
    "소분류": "소분류",
    text_col: "상담메모",
}

show_df = show_df[display_cols].rename(columns=display_names)

st.markdown('<div class="result-box">', unsafe_allow_html=True)
st.markdown(f'<div class="result-count">검색 결과 {len(show_df):,}건</div>', unsafe_allow_html=True)

if show_df.empty:
    st.info("검색 결과가 없어요.")
else:
    st.dataframe(show_df, use_container_width=True, height=700)

st.markdown('</div>', unsafe_allow_html=True)