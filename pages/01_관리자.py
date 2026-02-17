# pages/01_관리자.py
import io
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from utils import (
    save_master_bytes,
    load_master_updated_at,
)

st.set_page_config(page_title="관리자", layout="wide")

# -----------------------------
# Admin Token (secrets.toml 없어도 안죽게 / 안내문구 제거)
# -----------------------------
def s(v):
    return "" if v is None else str(v).strip()

def get_secret(key: str):
    v = os.environ.get(key)
    if v:
        return s(v)
    try:
        return s(st.secrets.get(key))
    except Exception:
        return ""

DEFAULT_TOKEN = get_secret("ADMIN_TOKEN") or "15886559"  # fallback (원하면 바꿔)

st.title("관리자 페이지")
st.caption("엑셀 1개 업로드(유선/채팅/게시판 시트) → 통합 master 저장 → app(대시보드)에서 자동 로드")

token = st.text_input("관리자 토큰", type="password", value="")
ok = (s(token) == s(DEFAULT_TOKEN))

if ok:
    st.success("관리자 인증 완료 ✅")
else:
    st.warning("관리자 토큰을 입력해야 업로드/저장이 가능합니다.")
    st.stop()

# -----------------------------
# Paths (프로젝트 루트 기준)
# -----------------------------
DATA_DIR = "data"
MASTER_XLSX = os.path.join(DATA_DIR, "master.xlsx")
MASTER_META = os.path.join(DATA_DIR, "master.meta")

# -----------------------------
# Reset (master 초기화)
# -----------------------------
updated_at = load_master_updated_at(st) or "없음 (처음이면 정상)"
st.info(f"현재 master 업데이트: {updated_at}")

st.warning("⚠️ 초기화(리셋)를 누르면 현재 master 데이터가 모두 삭제됩니다. (복구 불가)")

c_reset1, c_reset2 = st.columns([1.2, 2.8])
with c_reset1:
    agree = st.checkbox("복구 불가에 동의", value=False)
with c_reset2:
    do_reset = st.button("🧹 master 초기화", use_container_width=True, disabled=not agree)

if do_reset:
    os.makedirs(DATA_DIR, exist_ok=True)
    removed = []
    for p in [MASTER_XLSX, MASTER_META]:
        try:
            if os.path.exists(p):
                os.remove(p)
                removed.append(os.path.basename(p))
        except Exception:
            pass

    # ✅ 캐시까지 같이 삭제 (대시보드 잔상 방지)
    st.cache_data.clear()

    if removed:
        st.success(f"✅ 초기화 완료: {', '.join(removed)} 삭제됨 (대시보드도 데이터 없음 상태)")
    else:
        st.success("✅ 초기화 완료: 삭제할 master 파일이 없었어요 (이미 초기 상태)")
    time.sleep(0.2)
    st.rerun()

st.divider()

# -----------------------------
# One-file upload (Excel with 3 sheets)
# -----------------------------
st.subheader("엑셀 1개 업로드 (시트: 유선 / 채팅 / 게시판)")

st.caption(
    "각 시트의 컬럼(헤더)은 아래 중 하나로 맞춰주세요.\n"
    "- (권장) 헤더: 인입날짜, 인입시간, 기업명, 대분류, 중분류, 소분류\n"
    "- 또는 A~F 순서가 정확히: 인입날짜 / 인입시간 / 기업명 / 대분류 / 중분류 / 소분류"
)

up = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xls"], key="up_one")

SHEETS = ["유선", "채팅", "게시판"]

def _excel_time_to_str(x):
    """엑셀 시간(숫자/시간/문자) → 'HH:MM:SS'"""
    if pd.isna(x):
        return None
    # datetime.time
    if hasattr(x, "hour") and hasattr(x, "minute"):
        return f"{int(x.hour):02d}:{int(x.minute):02d}:{int(getattr(x, 'second', 0)):02d}"
    # 숫자(float): 엑셀 시간 비율(1일=1)
    try:
        if isinstance(x, (int, float)) and 0 <= float(x) < 1:
            total_seconds = int(round(float(x) * 24 * 60 * 60))
            hh = total_seconds // 3600
            mm = (total_seconds % 3600) // 60
            ss = total_seconds % 60
            return f"{hh:02d}:{mm:02d}:{ss:02d}"
    except Exception:
        pass
    # 문자열
    t = str(x).strip()
    if not t:
        return None
    return t

def build_master_from_sheet(df_sheet: pd.DataFrame, channel_name: str) -> pd.DataFrame:
    if df_sheet is None or df_sheet.empty:
        raise ValueError(f"[{channel_name}] 시트가 비어있습니다.")

    df = df_sheet.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # 1) 헤더명이 이미 있는 경우
    header_map = {
        "인입날짜": "인입날짜",
        "인입시간": "인입시간",
        "기업명": "기업명",
        "대분류": "대분류",
        "중분류": "중분류",
        "소분류": "소분류",
    }

    has_named = all(k in df.columns for k in header_map.keys())

    if not has_named:
        # 2) A~F 순서 강제 매핑 (첫 6컬럼)
        if df.shape[1] < 6:
            raise ValueError(f"[{channel_name}] 컬럼이 6개 미만입니다. 현재 컬럼수={df.shape[1]}")
        cols6 = df.columns[:6].tolist()
        df = df.rename(
            columns={
                cols6[0]: "인입날짜",
                cols6[1]: "인입시간",
                cols6[2]: "기업명",
                cols6[3]: "대분류",
                cols6[4]: "중분류",
                cols6[5]: "소분류",
            }
        )

    need = ["인입날짜", "인입시간", "기업명", "대분류", "중분류", "소분류"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise ValueError(f"[{channel_name}] 필수 컬럼 누락: {miss} / 실제: {df.columns.tolist()}")

    # 날짜/시간 파싱
    d = pd.to_datetime(df["인입날짜"], errors="coerce")
    t = df["인입시간"].apply(_excel_time_to_str)
    dt = pd.to_datetime(d.dt.strftime("%Y-%m-%d") + " " + t.fillna("00:00:00"), errors="coerce")

    out = pd.DataFrame(
        {
            "날짜": dt,
            "기업명": df["기업명"].astype(str).str.strip(),
            "대분류": df["대분류"].astype(str).str.strip(),
            "중분류": df["중분류"].astype(str).str.strip(),
            "소분류": df["소분류"].astype(str).str.strip(),
            "채널": channel_name,
        }
    )

    out = out.dropna(subset=["날짜"]).copy()

    # 빈값 정리
    for c in ["기업명", "대분류", "중분류", "소분류", "채널"]:
        out.loc[out[c].isin(["nan", "None", "NaN", ""]), c] = None

    return out

dfs = []
errors = []
counts = {k: 0 for k in SHEETS}

if up is not None:
    try:
        book = pd.ExcelFile(up)
        sheet_names = [str(x).strip() for x in book.sheet_names]

        # 시트 존재 체크(유선/채팅/게시판)
        missing_sheets = [s for s in SHEETS if s not in sheet_names]
        if missing_sheets:
            raise ValueError(f"시트가 없습니다: {missing_sheets} / 현재 시트: {sheet_names}")

        for ch in SHEETS:
            try:
                df_sheet = pd.read_excel(book, sheet_name=ch)
                dm = build_master_from_sheet(df_sheet, ch)
                dfs.append(dm)
                counts[ch] = int(len(dm))
            except Exception as e:
                errors.append(f"[{ch}] 처리 실패: {e}")

    except Exception as e:
        errors.append(f"엑셀 읽기 실패: {e}")

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
    st.markdown("#### 미리보기(통합 후, 상위 80행)")
    preview = pd.concat(dfs, ignore_index=True).head(80)
    st.dataframe(preview, use_container_width=True)

st.divider()

btn = st.button("💾 master 저장(통합) — 저장 시 기존 데이터 자동 초기화", disabled=not can_save, use_container_width=True)

if btn:
    t0 = time.perf_counter()
    with st.spinner("통합/저장 중..."):
        merged = pd.concat(dfs, ignore_index=True)

        os.makedirs(DATA_DIR, exist_ok=True)

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

        # ✅ 대시보드 잔상 방지 (캐시 클리어)
        st.cache_data.clear()

    st.success("저장 완료! 대시보드(app)로 이동하면 바로 반영됩니다 ✅")
    st.caption(f"저장 시간: {elapsed:.2f}초 / rows: {len(merged):,}")
    time.sleep(0.2)
    st.rerun()
