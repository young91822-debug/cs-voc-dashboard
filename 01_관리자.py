import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

st.set_page_config(page_title="관리자", layout="wide")

# =============================
# Config
# =============================
REQUIRED_COLS = ["날짜", "기업명", "대분류", "중분류", "소분류"]
CHANNELS = ["유선", "채팅", "게시판"]

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
LOCAL_MASTER_PARQUET = os.path.join(DATA_DIR, "master.parquet")
LOCAL_META_PATH = os.path.join(DATA_DIR, "master.meta.txt")

# =============================
# S3 (optional)
# =============================
def s3_enabled():
    try:
        s3 = st.secrets.get("S3", None)
        return bool(s3 and s3.get("bucket") and s3.get("key"))
    except Exception:
        return False

def get_s3_client():
    import boto3
    s3 = st.secrets["S3"]
    return boto3.client(
        "s3",
        aws_access_key_id=s3.get("access_key_id"),
        aws_secret_access_key=s3.get("secret_access_key"),
        region_name=s3.get("region"),
    )

def save_master_bytes(data: bytes):
    """
    우선순위:
    1) S3 설정 있으면 S3 저장
    2) 없으면 로컬 저장(data/master.xlsx)
    """
    if s3_enabled():
        client = get_s3_client()
        s3 = st.secrets["S3"]
        client.put_object(
            Bucket=s3["bucket"],
            Key=s3["key"],
            Body=data,
            ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        meta_key = s3.get("meta_key", s3["key"] + ".meta.txt")
        client.put_object(
            Bucket=s3["bucket"],
            Key=meta_key,
            Body=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ContentType="text/plain",
        )
        return "s3"
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOCAL_MASTER_PATH, "wb") as f:
            f.write(data)
        with open(LOCAL_META_PATH, "w", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return "local"

def load_master_updated_at():
    if s3_enabled():
        client = get_s3_client()
        s3 = st.secrets["S3"]
        meta_key = s3.get("meta_key", s3["key"] + ".meta.txt")
        try:
            obj = client.get_object(Bucket=s3["bucket"], Key=meta_key)
            return obj["Body"].read().decode("utf-8", errors="ignore").strip()
        except Exception:
            return None
    else:
        if os.path.exists(LOCAL_META_PATH):
            try:
                return open(LOCAL_META_PATH, "r", encoding="utf-8").read().strip()
            except Exception:
                return None
        return None

# =============================
# Helpers
# =============================
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

def read_csv_smart(file) -> pd.DataFrame:
    try:
        df = pd.read_csv(file, encoding="utf-8-sig")
    except Exception:
        file.seek(0)
        df = pd.read_csv(file, encoding="cp949")
    return df

def try_read_excel_with_header(file, header_row: int) -> pd.DataFrame:
    file.seek(0)
    return pd.read_excel(file, header=header_row)

def read_any(file) -> pd.DataFrame:
    name = getattr(file, "name", "").lower()

    if name.endswith(".csv"):
        df = read_csv_smart(file)
        df = normalize_cols(df)
        df = apply_alias(df)
        return df

    best_df = None
    best_missing = None

    for hdr in [0, 1, 2, 3]:
        try:
            df = try_read_excel_with_header(file, hdr)
            df = normalize_cols(df)
            df = apply_alias(df)
            missing = validate_cols(df)
            if not missing:
                return df
            if best_df is None or len(missing) < len(best_missing):
                best_df = df
                best_missing = missing
        except Exception:
            continue

    if best_df is not None:
        return best_df

    file.seek(0)
    df = pd.read_excel(file)
    df = normalize_cols(df)
    df = apply_alias(df)
    return df

def load_channel_files(files, channel_label: str) -> pd.DataFrame:
    if not files:
        return pd.DataFrame()

    frames = []
    for f in files:
        df = read_any(f)
        missing = validate_cols(df)
        if missing:
            st.error(
                f"[{channel_label}] 파일 '{getattr(f,'name','')}' 에 필수 컬럼이 없습니다: {missing}\n"
                f"→ 앱이 읽은 실제 컬럼: {df.columns.tolist()}"
            )
            continue

        df = df[REQUIRED_COLS].copy()
        df["채널"] = channel_label
        df["날짜"] = parse_date_series(df["날짜"])
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)

# =============================
# Admin Auth
# =============================
def admin_ok() -> bool:
    ADMIN_TOKEN = "15886559"  # ✅ 너가 말한 토큰
    st.sidebar.markdown("---")
    st.sidebar.subheader("관리자")
    inp = st.sidebar.text_input("관리자 토큰", type="password", help="관리자만 업로드 가능")
    return inp == ADMIN_TOKEN

# =============================
# UI
# =============================
st.title("관리자 페이지")

if not admin_ok():
    st.warning("관리자 토큰이 필요합니다.")
    st.stop()

st.success("관리자 인증 완료 ✅")

updated_at = load_master_updated_at()
st.info(f"현재 master 업데이트: {updated_at or '없음'}")

st.markdown("### master 업로드")
st.caption("유선/채팅/게시판 파일을 업로드하면 하나의 master로 저장됩니다. 저장 후 대시보드에서 바로 조회 가능합니다.")

upA, upB, upC = st.columns(3)
with upA:
    files_call = st.file_uploader("유선 파일 업로드", type=["csv", "xlsx", "xls"], accept_multiple_files=True, key="admin_call")
with upB:
    files_chat = st.file_uploader("채팅 파일 업로드", type=["csv", "xlsx", "xls"], accept_multiple_files=True, key="admin_chat")
with upC:
    files_board = st.file_uploader("게시판 파일 업로드", type=["csv", "xlsx", "xls"], accept_multiple_files=True, key="admin_board")

df_call = load_channel_files(files_call, "유선")
df_chat = load_channel_files(files_chat, "채팅")
df_board = load_channel_files(files_board, "게시판")

if df_call.empty and df_chat.empty and df_board.empty:
    st.info("업로드하면 미리보기 및 저장 버튼이 활성화됩니다.")
    st.stop()

df_master = pd.concat([df_call, df_chat, df_board], ignore_index=True)

st.markdown("### 미리보기")
st.dataframe(df_master.head(200), use_container_width=True, height=360)
st.caption(f"총 {len(df_master):,}건 / 컬럼: {df_master.columns.tolist()}")

if st.button("✅ master로 저장(공유 반영)", use_container_width=True):
    # 1) Excel 저장 bytes
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_master.to_excel(writer, index=False, sheet_name="master")
        if not df_call.empty:
            df_call.to_excel(writer, index=False, sheet_name="유선")
        if not df_chat.empty:
            df_chat.to_excel(writer, index=False, sheet_name="채팅")
        if not df_board.empty:
            df_board.to_excel(writer, index=False, sheet_name="게시판")
    out.seek(0)

    loc = save_master_bytes(out.getvalue())

    # 2) 로컬이면 parquet도 같이 저장(대시보드 로딩 초고속)
    #    S3를 쓰는 경우 parquet 업로드까지는 옵션(원하면 추가해줄게)
    if loc == "local":
        os.makedirs(DATA_DIR, exist_ok=True)
        try:
            df_master.to_parquet(LOCAL_MASTER_PARQUET, index=False)
        except Exception as e:
            st.warning(f"parquet 저장 실패(엑셀은 저장됨): {e}")

    # 캐시 무효화(대시보드가 즉시 최신 반영)
    try:
        st.cache_data.clear()
    except Exception:
        pass

    st.success(f"저장 완료! ({loc}) 이제 대시보드에서 누구나 바로 조회됩니다. ✅")
    st.balloons()
