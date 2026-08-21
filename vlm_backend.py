"""OCR/VLM 백엔드 선택 및 실행.

VLM_BACKEND 환경변수로 백엔드를 고른다:
  - "paddle": 기존 PaddleOCR 경로
  - "ollama" (기본값): 로컬 `ollama serve` + qwen3-vl 계열 비전 모델

백엔드가 무엇이든 run_ocr(image_path) -> list[str] 계약은 동일하게 유지한다.
(PaddleOCR의 rec_texts와 동일한 형태: 이미지에서 인식된 텍스트 줄의 리스트)

VLM_BACKEND="ollama"일 때는 paddleocr import 자체가 실행되지 않는다
(_run_paddle 내부에서만 지연 import 하기 때문).
"""

import base64
import json
import os
import re

os.environ["PADDLE_PDX_ENABLE_MKLDNN_BY_DEFAULT"] = "0"

VLM_BACKEND = os.environ.get("VLM_BACKEND", "ollama").strip().lower()
assert VLM_BACKEND in ["ollama", "paddle"]

OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-vl:2b-instruct")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

_paddle_ocr_engine = None


def _get_paddle_engine():
    global _paddle_ocr_engine
    if _paddle_ocr_engine is None:
        from paddleocr import PaddleOCR

        _paddle_ocr_engine = PaddleOCR(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _paddle_ocr_engine


def _run_paddle(image_path):
    ocr = _get_paddle_engine()
    result = ocr.predict(image_path)
    return result[0].get("rec_texts", [])


OLLAMA_PROMPT = (
    "당신은 OCR 엔진입니다. 첨부된 통장사본 이미지에 보이는 모든 텍스트를 "
    "위에서 아래로, 같은 줄은 왼쪽에서 오른쪽 순서로 정확하게 추출하세요. "
    "설명이나 마크다운 없이 다음 JSON 형식으로만 답하세요: "
    '{"texts": ["줄1", "줄2", ...]}'
)


def _extract_json_text(raw):
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return text


def _run_ollama(image_path):
    import requests

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": OLLAMA_PROMPT,
        "images": [image_b64],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0},
    }

    try:
        resp = requests.post(
            f"{OLLAMA_ENDPOINT}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Ollama 응답이 {OLLAMA_TIMEOUT:g}초 안에 도착하지 않았습니다(timeout). "
            f"모델({OLLAMA_MODEL})이 무겁거나 서버가 응답하지 않고 있을 수 있습니다."
        ) from e
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Ollama 서버({OLLAMA_ENDPOINT})에 연결할 수 없습니다. "
            "터미널에서 `ollama serve`를 실행한 뒤 다시 시도하세요."
        ) from e

    if resp.status_code == 404:
        raise RuntimeError(
            f"Ollama에 모델 '{OLLAMA_MODEL}'이(가) 설치되어 있지 않습니다. "
            f"`ollama pull {OLLAMA_MODEL}` 명령으로 먼저 설치하세요."
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Ollama 서버 오류 (status={resp.status_code}): {resp.text[:500]}"
        )

    try:
        body = resp.json()
    except ValueError as e:
        raise RuntimeError(
            f"Ollama 응답을 JSON으로 파싱할 수 없습니다. 원본 응답 일부: {resp.text[:300]}"
        ) from e

    raw = body.get("response", "")
    cleaned = _extract_json_text(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama 모델 출력이 JSON 형식이 아닙니다. 원본 응답 일부: {raw[:300]}"
        ) from e

    texts = parsed.get("texts", []) if isinstance(parsed, dict) else []
    return [str(t) for t in texts]


def run_ocr(image_path):
    if VLM_BACKEND == "ollama":
        return _run_ollama(image_path)
    if VLM_BACKEND == "paddle":
        return _run_paddle(image_path)
    raise RuntimeError(
        f"알 수 없는 VLM_BACKEND 값입니다: '{VLM_BACKEND}' (paddle 또는 ollama만 지원)"
    )
