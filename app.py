"""통장사본 OCR 검증 대시보드.

CSV(bankbook_documents.csv)의 문서 목록을 보여주고, 선택한 행의 이미지를
PaddleOCR로 인식한 뒤 호출시각/반환시각/문자인식결과/검증결과를 표로 표시한다.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from bank_data import BANK_CODES

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "bankbook_documents.csv"
BANK_CODE_TO_NAME = {v: k for k, v in BANK_CODES.items()}

st.set_page_config(page_title="통장사본 OCR 검증", layout="wide")
st.title("통장사본 OCR 검증 대시보드")


@st.cache_data
def load_csv():
    return pd.read_csv(CSV_PATH, dtype=str)


@st.cache_resource
def get_ocr_engine():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang="korean",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def run_ocr(image_path):
    ocr = get_ocr_engine()
    result = ocr.predict(image_path)
    return result[0].get("rec_texts", [])


def verify(texts, vendor_name, bank_code):
    joined = "".join(texts)
    name_ok = vendor_name in joined
    bank_name = BANK_CODE_TO_NAME.get(bank_code, "")
    bank_ok = bool(bank_name) and bank_name in joined

    if name_ok and bank_ok:
        return "일치"
    if name_ok:
        return "불일치 (은행명 확인 안됨)"
    if bank_ok:
        return "불일치 (거래처명 확인 안됨)"
    return "불일치"


def execute_ocr_for_row(row):
    call_time = datetime.now()
    texts = run_ocr(row["파일경로"])
    return_time = datetime.now()
    record = {
        "doc_id": row["doc_id"],
        "파일명": row["파일명"],
        "요청시각": call_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "반환시각": return_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "문자인식결과": " | ".join(texts),
        "검증결과": verify(texts, row["거래처명"], row["은행코드"]),
    }
    st.session_state.ocr_history.insert(0, record)
    return record


if "ocr_history" not in st.session_state:
    st.session_state.ocr_history = []
if "selected_doc_id" not in st.session_state:
    st.session_state.selected_doc_id = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None

df = load_csv()

st.subheader("원본 CSV")
event = st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="csv_table",
)

processed_doc_ids = {r["doc_id"] for r in st.session_state.ocr_history}
remaining_df = df[~df["doc_id"].isin(processed_doc_ids)]

st.write(f"전체 {len(df)}건 중 **{len(df) - len(remaining_df)}건 완료**, **{len(remaining_df)}건 미완료** (기존 이력은 유지되며, 미완료 항목만 실행합니다)")

if st.button("전체 문서 일괄 실행", key="run_all_btn", disabled=remaining_df.empty):
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(remaining_df)
    for i, (_, row) in enumerate(remaining_df.iterrows(), start=1):
        status_text.text(f"({i}/{total}) 처리 중: {row['파일명']} — 1장당 약 20초 정도 걸릴 수 있습니다")
        execute_ocr_for_row(row)
        progress_bar.progress(i / total)
    status_text.text(f"전체 실행 완료 ({total}건 처리)")
    st.rerun()

# 버튼 클릭으로 인한 재실행에서도 선택이 유지되도록 doc_id를 세션에 고정 저장
if event and event.selection and event.selection.rows:
    st.session_state.selected_doc_id = df.iloc[event.selection.rows[0]]["doc_id"]

if st.session_state.selected_doc_id is not None:
    row = df[df["doc_id"] == st.session_state.selected_doc_id].iloc[0]
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(row["파일경로"], caption=row["파일명"], use_container_width=True)
    with col2:
        st.write(f"**doc_id**: {row['doc_id']}")
        st.write(f"**거래처코드**: {row['거래처코드']}")
        st.write(f"**거래처명**: {row['거래처명']}")
        st.write(f"**은행코드**: {row['은행코드']} ({BANK_CODE_TO_NAME.get(row['은행코드'], '알수없음')})")

        if st.button("문자인식 실행", key="run_ocr_btn"):
            with st.spinner("OCR 실행 중... (이미지 1장당 약 20초 정도 걸릴 수 있습니다)"):
                record = execute_ocr_for_row(row)
            st.session_state.last_result = record

    # 방금 실행한 결과를 표 갱신과 별개로 즉시 확인 가능하도록 표시
    if st.session_state.last_result and st.session_state.last_result["doc_id"] == row["doc_id"]:
        r = st.session_state.last_result
        st.success("OCR 실행 완료")
        st.write(f"**요청시각**: {r['요청시각']}")
        st.write(f"**반환시각**: {r['반환시각']}")
        st.write(f"**검증결과**: {r['검증결과']}")
        st.text_area("문자인식 전체 텍스트", r["문자인식결과"], height=100, key="last_result_text")
else:
    st.info("위 표에서 행을 클릭해 선택하세요.")

if st.session_state.ocr_history:
    st.subheader("OCR 실행 결과 이력")
    st.dataframe(
        pd.DataFrame(st.session_state.ocr_history),
        use_container_width=True,
        hide_index=True,
        column_config={
            "문자인식결과": st.column_config.TextColumn(width="large"),
        },
    )
