"""통장사본 OCR 검증 대시보드.

CSV(bankbook_documents.csv)의 문서 목록을 체크박스로 표시하고, 체크된 행만
VLM_BACKEND 설정에 따라 PaddleOCR 또는 Ollama로 인식한 뒤
호출시각/반환시각/문자인식결과/검증결과를 표로 표시한다.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from bank_data import BANK_CODES
from vlm_backend import OLLAMA_MODEL, OLLAMA_PROMPT, VLM_BACKEND, run_ocr

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "bankbook_documents.csv"
BATCH_METADATA_PATH = BASE_DIR / "batch_metadata.jsonl"
BATCHES_DIR = BASE_DIR / "batches"
BANK_CODE_TO_NAME = {v: k for k, v in BANK_CODES.items()}
OCR_LABEL = "AI 문자인식" if VLM_BACKEND == "ollama" else "OCR"

st.set_page_config(page_title=f"통장사본 {OCR_LABEL} 검증", layout="wide")
st.markdown(
    '<style>[data-testid="stImageContainer"] img { border: 1px solid #f0f0f0; }</style>',
    unsafe_allow_html=True,
)
st.title(f"통장사본 {OCR_LABEL} 검증 대시보드")
st.caption(f"문자인식 백엔드: {VLM_BACKEND}")


@st.cache_data
def load_csv():
    return pd.read_csv(CSV_PATH, dtype=str)


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


def resolve_image_path(row):
    return str(BASE_DIR / row["파일경로"])


def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def execute_ocr_for_row(row):
    call_time = datetime.now()
    texts = run_ocr(resolve_image_path(row))
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


def render_history_table():
    if st.session_state.ocr_history:
        st.subheader(f"{OCR_LABEL} 실행 결과 이력")
        st.dataframe(
            pd.DataFrame(st.session_state.ocr_history),
            use_container_width=True,
            hide_index=True,
            column_config={
                "문자인식결과": st.column_config.TextColumn(width="large"),
            },
        )


if "ocr_history" not in st.session_state:
    st.session_state.ocr_history = []
if "checked_doc_ids" not in st.session_state:
    st.session_state.checked_doc_ids = set()
if "preview_doc_id" not in st.session_state:
    st.session_state.preview_doc_id = None
if "prev_select_all" not in st.session_state:
    st.session_state.prev_select_all = False
if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0
if "editor_default_checked" not in st.session_state:
    st.session_state.editor_default_checked = False

df = load_csv()

st.subheader("원본 CSV")

select_all = st.checkbox("전체 선택", key="select_all_checkbox")
bulk_change = False
if select_all and not st.session_state.prev_select_all:
    st.session_state.editor_default_checked = True
    st.session_state.editor_nonce += 1
    bulk_change = True
elif not select_all and st.session_state.prev_select_all:
    st.session_state.editor_default_checked = False
    st.session_state.editor_nonce += 1
    bulk_change = True
st.session_state.prev_select_all = select_all

# data_editor에 넘기는 "선택" 기본값은 리런 사이에 절대 바뀌지 않아야 한다.
# (매번 누적된 체크 상태를 다시 먹이면 Streamlit이 기존 편집 내역을 리셋해버림)
df_view = df.copy()
df_view.insert(0, "선택", st.session_state.editor_default_checked)

edited_df = st.data_editor(
    df_view,
    use_container_width=True,
    hide_index=True,
    disabled=[c for c in df_view.columns if c != "선택"],
    column_config={"선택": st.column_config.CheckboxColumn("선택")},
    key=f"csv_editor_{st.session_state.editor_nonce}",
)

new_checked = set(edited_df.loc[edited_df["선택"], "doc_id"])
if not bulk_change:
    newly_ticked = new_checked - st.session_state.checked_doc_ids
    if len(newly_ticked) == 1:
        st.session_state.preview_doc_id = next(iter(newly_ticked))
st.session_state.checked_doc_ids = new_checked

processed_doc_ids = {r["doc_id"] for r in st.session_state.ocr_history}
runnable_doc_ids = [d for d in st.session_state.checked_doc_ids if d not in processed_doc_ids]

st.write(
    f"전체 {len(df)}건 중 **{len(processed_doc_ids)}건 완료**, "
    f"**{len(st.session_state.checked_doc_ids)}건 선택** "
    f"(선택 중 미완료 **{len(runnable_doc_ids)}건**을 실행합니다)"
)

if st.button("실행", type="primary", key="run_selected_btn", disabled=not runnable_doc_ids):
    batch_id = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    batch_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    batch_jsonl_path = BATCHES_DIR / f"{batch_id}.jsonl"

    rows_to_run = df[df["doc_id"].isin(runnable_doc_ids)]
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(rows_to_run)
    completed = 0
    batch_error = None
    for i, (_, row) in enumerate(rows_to_run.iterrows(), start=1):
        status_text.text(f"({i}/{total}) 처리 중: {row['파일명']} — 1장당 약 20초 정도 걸릴 수 있습니다")
        try:
            record = execute_ocr_for_row(row)
            append_jsonl(batch_jsonl_path, {"batch_id": batch_id, **record})
            completed += 1
            progress_bar.progress(i / total)
        except RuntimeError as e:
            batch_error = str(e)
            st.error(batch_error)
            break

    append_jsonl(
        BATCH_METADATA_PATH,
        {
            "batch_id": batch_id,
            "started_at": batch_started_at,
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "backend": VLM_BACKEND,
            "model": OLLAMA_MODEL if VLM_BACKEND == "ollama" else None,
            "requested_doc_ids": runnable_doc_ids,
            "requested_count": total,
            "completed_count": completed,
            "status": "completed" if batch_error is None else "failed",
            "error": batch_error,
            "batch_jsonl": batch_jsonl_path.relative_to(BASE_DIR).as_posix(),
        },
    )

    if batch_error is None:
        status_text.text(f"실행 완료 ({total}건 처리)")
        st.rerun()

if st.session_state.preview_doc_id is not None:
    row = df[df["doc_id"] == st.session_state.preview_doc_id].iloc[0]
    record = next(
        (r for r in st.session_state.ocr_history if r["doc_id"] == row["doc_id"]),
        None,
    )
    col1, col_right = st.columns([1, 2])
    with col1:
        st.image(resolve_image_path(row), caption=row["파일명"], use_container_width=True)
    with col_right:
        col2, col3 = st.columns([1, 1])
        with col2:
            st.write(f"**doc_id**: {row['doc_id']}")
            st.write(f"**거래처코드**: {row['거래처코드']}")
            st.write(f"**거래처명**: {row['거래처명']}")
            st.write(f"**은행코드**: {row['은행코드']} ({BANK_CODE_TO_NAME.get(row['은행코드'], '알수없음')})")

            if record:
                st.success(f"{OCR_LABEL} 실행 완료")
                st.write(f"**요청시각**: {record['요청시각']}")
                st.write(f"**반환시각**: {record['반환시각']}")
                st.write(f"**검증결과**: {record['검증결과']}")
                st.text_area(
                    "문자인식 전체 텍스트",
                    record["문자인식결과"],
                    height=100,
                    key="preview_result_text",
                )
        with col3:
            if record and VLM_BACKEND == "ollama":
                st.write(f"**Sent prompt to {OLLAMA_MODEL}**")
                st.text_area(
                    "전송한 프롬프트",
                    OLLAMA_PROMPT,
                    height=200,
                    key="preview_prompt_text",
                    disabled=True,
                )

        # 이미지 옆 2/3 영역의 남는 하단 공간에 이력 표를 배치
        render_history_table()
else:
    st.info("위 표에서 체크박스를 선택하세요.")
    render_history_table()
