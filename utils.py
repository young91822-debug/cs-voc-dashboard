import os
import io
import json
import time
import pandas as pd
from datetime import datetime

# -----------------------------
# Config
# -----------------------------
REQUIRED_COLS = ["날짜", "기업명", "대분류", "중분류", "소분류"]
CHANNELS = ["유선", "채팅", "게시판"]

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MASTER_XLSX = os.path.join(DATA_DIR, "master.xlsx")
MASTER_META = os.path.join(DATA_DIR, "master.meta")

COL_ALIAS = {
    # 날짜
    "문의일": "날짜",
    "접수일": "날짜",
    "등록일": "날짜",
    "일자": "날짜",
    "날 짜": "날짜",
    # 기업
    "기업": "기업명",
    "회사명": "기업명",
    "고객사": "기업명",
    # 분류
    "대분류명": "대분류",
    "중분류명": "중분류",
    "소분류명": "소분류",
    # 채널
    "경로": "채널",
    "채널명": "채널",
}

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def normalize_master_like(df: pd.DataFrame) -> pd.DataFrame:
    # 컬럼명 정리
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # alias 매핑
    rename = {}
    for c in df.columns:
        if c in COL_ALIAS:
            rename[c] = COL_ALIAS[c]
    if rename:
        df = df.rename(columns=rename)

    # 문자열 trim
    for c in ["기업명", "대분류", "중분류", "소분류", "채널"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    return df

def parse_date_series(s: pd.Series) -> pd.Series:
    # robust datetime parse
    return pd.to_datetime(s, errors="coerce")

def add_time_grain(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["월"] = df["날짜"].dt.to_period("M").astype(str)
    df["_월p"] = df["날짜"].dt.to_period("M")
    df["주"] = df["날짜"].dt.to_period("W").astype(str)
    df["일"] = df["날짜"].dt.date.astype(str)
    return df

def safe_div(a, b):
    try:
        if b is None or b == 0:
            return None
        return a / b
    except:
        return None

def pct_fmt(p):
    if p is None:
        return "-"
    return f"{p*100:+.1f}%"

def arrow_from_pct(p):
    if p is None:
        return ""
    return "↑" if p > 0 else ("↓" if p < 0 else "→")

def compute_latest_prev_month(df: pd.DataFrame):
    if "_월p" not in df.columns:
        return None, None
    months = sorted([x for x in df["_월p"].dropna().unique().tolist()])
    if len(months) < 2:
        return (months[-1] if months else None), None
    return months[-1], months[-2]

def month_count(df: pd.DataFrame, mp):
    if mp is None or "_월p" not in df.columns:
        return None
    return int((df["_월p"] == mp).sum())

def chips_html(items):
    # ✅ 들여쓰기/줄바꿈 때문에 코드블록으로 렌더링되는 문제 방지: 한 줄 HTML로 만든다
    spans = []
    for t in items:
        spans.append(
            f'<span style="'
            f'display:inline-block;'
            f'padding:6px 10px;'
            f'margin-right:6px;'
            f'margin-bottom:6px;'
            f'border-radius:999px;'
            f'background:rgba(255,255,255,0.78);'
            f'border:1px solid rgba(15,23,42,0.10);'
            f'font-size:12.5px;'
            f'font-weight:800;'
            f'color:rgba(15,23,42,0.82);'
            f'box-shadow:0 8px 18px rgba(2,8,23,0.06);'
            f'">{t}</span>'
        )
    return "<div style='display:flex;flex-wrap:wrap;gap:0px;'>" + "".join(spans) + "</div>"

def ensure_top_table(df: pd.DataFrame, col: str, n=10):
    t = df[col].astype(str).value_counts().head(n).reset_index()
    t.columns = [col, "건수"]
    return t

def load_master_updated_at(st=None):
    ensure_data_dir()
    if not os.path.exists(MASTER_META):
        return None
    try:
        with open(MASTER_META, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("updated_at")
    except:
        return None

def load_master_bytes(st=None):
    ensure_data_dir()
    if not os.path.exists(MASTER_XLSX):
        return None, "없음"
    try:
        with open(MASTER_XLSX, "rb") as f:
            b = f.read()
        return b, f"local:{MASTER_XLSX}"
    except:
        return None, "읽기 실패"

def save_master_bytes(master_bytes: bytes, meta: dict):
    ensure_data_dir()
    with open(MASTER_XLSX, "wb") as f:
        f.write(master_bytes)
    with open(MASTER_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
