# pages/01_관리자.py
import io
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from utils import (
    REQUIRED_COLS,
    CHANNELS,
    normalize_master_like,
    parse_date_series,
    save_master_bytes,
    load_master_updated_at,
)

st.set_page_config(page_title="관리자", layout="wide")

# -----------------------------
# Admin Token (secrets.toml 없어도 안죽게)
# -----------------------------
def s(v):
    return "" if v is None else str(v).strip()

def get_secret(key: str):
    # 1) 환경변수 우선
    v = os.environ.get(key)
    if v:
        return s(v)

    # 2) secrets.toml (없으면 StreamlitSecretNotFoundError 나므로 try/except 필수)
    try:
        return s(st.secrets.get(key))
    except Exception:
        return ""

DEFAULT_TOKEN = get_secret("ADMIN_TOKEN") or "15886559"  # fallback 유지 (원하면 바꿔)

st.title("관리자 페이지")
st.caption("유선/채팅/게시판 파일 업로드 → 통합 master 저장 → app(대시보드)에서 자동 로드")

# 토큰이 기본값(폴백)으로 잡힌 경우 안내
if DEFAULT_TOKEN == "15886559":
    st.info(
        "⚠️ ADMIN_TOKEN이 설정되어 있지 않아 기본 토큰(15886559)으로 동작 중입니다.\n\n"
        "원하는 토큰으로 바꾸려면 아래 중 하나로 설정하세요.\n"
        "- 프로젝트 폴더에 `.streamlit/secrets.toml` 생성 후 `ADMIN_TOKEN = \"원하는값\"`\n"
        "- 또는 PowerShell에서 실행 전 `$env:ADMIN_TOKEN=\"원하는값\"`"
    )

token = st.text_input("관리자 토큰", type="password", value="")
ok = (s(token) == s(DEFAULT_TOKEN))

if ok:
    st.success("관리자 인증 완료 ✅")
else:
    st.warning("관리자 토큰을 입력해야 업로드/저장이 가능합니다.")
    st.stop()

updated_at = load_master_updated_at(st) or "없음 (처음이면 정상)"
st.info(f"현재 master 업데이트: {updated_at}")

st.divider()

# -----------------------------
# Upload
# -----------------------------
c1, c2, c3 = st.columns(3, gap="large")
with c1:
    up_tel = st.file_uploader("유선 파일 업로드", type=["csv", "xlsx", "xls"], key="up_tel")
with c2:
    up_chat = st.file_uploader("채팅 파일 업로드", type=["csv", "xlsx", "xls"], key="up_chat")
with c3:
    up_board = st.file_uploader("게시판 파일 업로드", type=["csv", "xlsx", "xls"], key="up_board")


def read_any(file):
    """csv/xlsx 자동 읽기"""
    if file is None:
        return None
    name = (file.name or "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)


def prep(df: pd.DataFrame, channel_name: str) -> pd.DataFrame:
    """
    utils.normalize_master_like로 컬럼 표준화 후,
    REQUIRED_COLS + 채널 컬럼으로 master 형태로 정리
    """
    if df is None or df.empty:
        raise ValueError(f"[{channel_name}] 파일이 비어있습니다.")

    df = normalize_master_like(df)

    miss = [c for c in REQUIRED_COLS if c not in df.columns]
    if miss:
        raise ValueError(f"[{channel_name}] 필수 컬럼 누락: {miss} / 실제: {df.columns.tolist()}")

    df = df[REQUIRED_COLS].copy()
    df["날짜"] = parse_date_series(df["날짜"])
    df = df[df["날짜"].notna()].copy()

    df["채널"] = channel_name
    for c in ["기업명", "대분류", "중분류", "소분류"]:
        df[c] = df[c].astype(str).str.strip()

    df["채널"] = df["채널"].astype(str).str.strip()
    return df


dfs = []
errors = []
counts = {"유선": 0, "채팅": 0, "게시판": 0}

for file_obj, ch in [(up_tel, "유선"), (up_chat, "채팅"), (up_board, "게시판")]:
    if file_obj is None:
        continue
    try:
        d0 = read_any(file_obj)
        d1 = prep(d0, ch)
        dfs.append(d1)
        counts[ch] = int(len(d1))
    except Exception as e:
        errors.append(f"[{ch}] {getattr(file_obj, 'name', '파일')} 처리 실패: {e}")

st.subheader("업로드 로드 결과(채널별 건수)")
cc1, cc2, cc3 = st.columns(3)
cc1.metric("유선", f"{counts['유선']:,}건")
cc2.metric("채팅", f"{counts['채팅']:,}건")
cc3.metric("게시판", f"{counts['게시판']:,}건")

if errors:
    st.error("업로드/전처리 오류가 있습니다.\n\n- " + "\n- ".join(errors))

can_save = (len(dfs) > 0) and (len(errors) == 0)

st.caption("파일을 업로드하면 미리보기 및 저장 버튼이 활성화됩니다.")

if dfs:
    st.markdown("#### 미리보기(통합 전, 상위 80행)")
    preview = pd.concat(dfs, ignore_index=True).head(80)
    st.dataframe(preview, use_container_width=True)

st.divider()

btn = st.button("💾 master 저장(통합)", disabled=not can_save, use_container_width=True)

if btn:
    t0 = time.perf_counter()
    with st.spinner("통합/저장 중..."):
        merged = pd.concat(dfs, ignore_index=True)

        merged = merged[REQUIRED_COLS + ["채널"]].copy()
        merged = merged.dropna(subset=["날짜"]).copy()

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            merged.to_excel(w, index=False, sheet_name="master")

        b = out.getvalue()
        elapsed = time.perf_counter() - t0

        meta = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rows": int(len(merged)),
            "save_seconds": round(float(elapsed), 3),
        }

        save_master_bytes(b, meta)

    st.success("저장 완료! 왼쪽 메뉴에서 app을 눌러주세요 👈")
    st.caption(f"저장 시간: {elapsed:.2f}초 / 저장 rows: {len(merged):,}")
    time.sleep(0.2)
    st.rerun()
