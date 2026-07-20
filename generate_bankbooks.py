"""Dummy 통장사본 PNG 생성기.

random data -> .md -> HTML -> PDF -> PNG -> (grain + resize) 파이프라인.
"""

import base64
import csv
import io
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path

import fitz  # pymupdf
import numpy as np
from PIL import Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa
from xhtml2pdf import files as _pisa_files


def _get_named_tmp_file_windows_safe(self):
    # xhtml2pdf's default NamedTemporaryFile keeps a handle open, which Windows
    # locks exclusively -- a second open() (e.g. reportlab loading a TTF) then
    # fails with PermissionError. Close the handle before returning instead.
    data = self.get_data()
    tmp_file = tempfile.NamedTemporaryFile(suffix=self.suffix, delete=False)
    if data:
        tmp_file.write(data)
        tmp_file.flush()
    tmp_file.close()
    _pisa_files.files_tmp.append(tmp_file)
    if self.path is None:
        self.path = tmp_file.name
    return tmp_file


_pisa_files.BaseFile.get_named_tmp_file = _get_named_tmp_file_windows_safe

from bank_data import (
    ACCOUNT_TYPES,
    BANK_CODES,
    BANK_COLORS,
    BANKS,
    BRANCH_REGIONS,
    GIVEN_NAME_FIRST,
    GIVEN_NAME_SECOND,
    SURNAMES,
)

OUTPUT_DIR = Path(__file__).parent / "output"
CSV_PATH = Path(__file__).parent / "bankbook_documents.csv"
CSV_FIELDNAMES = ["doc_id", "거래처코드", "거래처명", "은행코드", "파일명", "파일경로"]
FONT_PATH = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD_PATH = Path(r"C:\Windows\Fonts\malgunbd.ttf")
FONT_NAME = "Malgun"
FONT_BOLD_NAME = "Malgun-Bold"

HTML_TEMPLATE = """<html>
<head>
<style>
  @font-face {{
    font-family: "{font}";
    src: url("{font_uri}");
  }}
  @font-face {{
    font-family: "{font}";
    font-weight: bold;
    src: url("{font_bold_uri}");
  }}
  body {{ font-family: '{font}'; border: none; background-color: transparent; }}
  table, tr, td, div, span, p {{ border: none; background-color: transparent; }}
  .outer {{ width: 100%; }}
  .cover-cell {{
    width: 620px;
    background-color: {bg_tint};
    border: 1px solid {accent};
    border-top: 10px solid {accent};
    padding: 22px 28px 18px 28px;
  }}
  .topbar {{
    width: 100%;
  }}
  .logo-cell {{
    text-align: center;
  }}
  .logo-text {{
    font-size: 20px;
    font-weight: bold;
    color: {accent};
    margin-left: 6px;
  }}
  .seal-box {{
    width: 78px;
    height: 60px;
    border: 1px solid #999999 !important;
    text-align: center;
    vertical-align: middle;
    font-size: 10px;
    color: #888888;
  }}
  .customer-line {{
    font-size: 19px;
    font-weight: bold;
    padding-bottom: 6px;
    border-bottom: 1px solid #bbbbbb !important;
  }}
  .nim {{
    font-size: 15px;
    font-weight: normal;
    color: #555555;
  }}
  .account-type {{
    font-size: 13px;
    color: #666666;
  }}
  .account-number {{
    font-size: 26px;
    font-weight: bold;
    letter-spacing: 1px;
    color: #222222;
  }}
  .info-table {{
    width: 100%;
  }}
  .info-table td {{
    font-size: 13px;
    padding: 5px 0;
    color: #333333;
  }}
  .info-table .label {{
    width: 90px;
    color: #777777;
  }}
  .footer {{
    padding-top: 8px;
    border-top: 1px solid #cccccc !important;
    font-size: 10px;
    color: #999999;
    text-align: center;
  }}
  .spacer {{ height: 16px; font-size: 1px; line-height: 1px; }}
</style>
</head>
<body>
<table class="outer" cellpadding="0" cellspacing="0"><tr><td align="center">
<table class="cover-cell" cellpadding="0" cellspacing="0"><tr><td>

  <table class="topbar" cellpadding="0" cellspacing="0">
    <tr>
      <td style="width:30%;">
        <img src="{hamburger_uri}" width="24" height="18" />
      </td>
      <td class="logo-cell" style="width:40%;">
        <img src="{logo_mark_uri}" width="20" height="20" /><span class="logo-text">{bank_name}</span>
      </td>
      <td style="width:30%; text-align:right;">
        <table cellpadding="0" cellspacing="0" style="float:right;"><tr><td class="seal-box">인감(서명)</td></tr></table>
      </td>
    </tr>
  </table>

  <div class="spacer">&nbsp;</div>
  <div class="customer-line">{holder_name} <span class="nim">님</span></div>
  <div class="spacer">&nbsp;</div>
  <div class="account-type">{account_type}</div>
  <div class="account-number">{account_number}</div>
  <div class="spacer">&nbsp;</div>

  <table class="info-table" cellpadding="0" cellspacing="0">
    <tr>
      <td class="label">취급점</td>
      <td>{branch_name}</td>
      <td class="label">개설일</td>
      <td>{open_date}</td>
    </tr>
  </table>

  <div class="spacer">&nbsp;</div>
  <div class="footer">본 통장사본은 예금주 확인 용도의 견본이며 법적 효력이 없습니다.</div>

</td></tr></table>
</td></tr></table>
</body>
</html>
"""


def make_hamburger_icon_uri():
    from PIL import ImageDraw

    icon = Image.new("RGBA", (60, 44), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    for y in (4, 20, 36):
        draw.rectangle([0, y, 59, y + 7], fill=(102, 102, 102, 255))
    buf = io.BytesIO()
    icon.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


HAMBURGER_ICON_URI = make_hamburger_icon_uri()
_LOGO_MARK_CACHE = {}


def make_logo_mark_uri(accent_hex):
    if accent_hex in _LOGO_MARK_CACHE:
        return _LOGO_MARK_CACHE[accent_hex]

    size = 40
    hex_digits = accent_hex.lstrip("#")
    rgb = tuple(int(hex_digits[i : i + 2], 16) for i in (0, 2, 4))
    icon = Image.new("RGBA", (size, size), rgb + (255,))
    buf = io.BytesIO()
    icon.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    uri = f"data:image/png;base64,{b64}"
    _LOGO_MARK_CACHE[accent_hex] = uri
    return uri


def lighten(hex_color, amount=0.90):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def register_font():
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD_NAME, str(FONT_BOLD_PATH)))
    pdfmetrics.registerFontFamily(
        FONT_NAME,
        normal=FONT_NAME,
        bold=FONT_BOLD_NAME,
        italic=FONT_NAME,
        boldItalic=FONT_BOLD_NAME,
    )


def random_account_number(bank_name):
    cfg = BANKS[bank_name]
    segments = cfg["segments"]
    prefix = cfg["prefix"]
    parts = []
    for i, length in enumerate(segments):
        if i == 0 and prefix:
            remaining = length - len(prefix)
            part = prefix + "".join(random.choices("0123456789", k=remaining))
        else:
            part = "".join(random.choices("0123456789", k=length))
        parts.append(part)
    return "-".join(parts)


def random_name():
    return random.choice(SURNAMES) + random.choice(GIVEN_NAME_FIRST) + random.choice(GIVEN_NAME_SECOND)


def random_branch():
    return random.choice(BRANCH_REGIONS) + "지점"


def random_vendor_code():
    return "1" + "".join(random.choices("0123456789", k=5))


def random_open_date():
    start = date(2003, 1, 1)
    end = date.today()
    delta_days = (end - start).days
    d = start + timedelta(days=random.randint(0, delta_days))
    return d.strftime("%Y.%m.%d")


def random_bankbook_data():
    bank_name = random.choice(list(BANKS.keys()))
    return {
        "bank_name": bank_name,
        "account_number": random_account_number(bank_name),
        "holder_name": random_name(),
        "branch_name": random_branch(),
        "open_date": random_open_date(),
        "account_type": random.choice(ACCOUNT_TYPES),
    }


def render_pdf(data):
    font_uri = str(FONT_PATH).replace("\\", "/")
    font_bold_uri = str(FONT_BOLD_PATH).replace("\\", "/")
    accent = BANK_COLORS[data["bank_name"]]
    full_html = HTML_TEMPLATE.format(
        font=FONT_NAME,
        font_uri=font_uri,
        font_bold_uri=font_bold_uri,
        accent=accent,
        bg_tint=lighten(accent, 0.92),
        hamburger_uri=HAMBURGER_ICON_URI,
        logo_mark_uri=make_logo_mark_uri(accent),
        **data,
    )

    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(src=full_html, dest=pdf_buffer)
    return pdf_buffer.getvalue()


def pdf_to_image(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    zoom = random.uniform(1.3, 2.4)  # 다양한 스캔 해상도를 흉내
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return img


def apply_grain(img, sigma=None):
    if sigma is None:
        sigma = random.uniform(2.0, 6.0)  # 눈으로 봤을 때 평이하게 읽히는 수준
    arr = np.asarray(img).astype(np.float32)
    noise = np.random.normal(0, sigma, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def apply_random_resize(img):
    target_width = random.randint(600, 1600)
    ratio = target_width / img.width
    target_height = int(img.height * ratio)
    resample = random.choice([Image.BILINEAR, Image.BICUBIC, Image.NEAREST, Image.LANCZOS])
    return img.resize((target_width, target_height), resample=resample)


def generate_one(index, used_vendor_codes):
    data = random_bankbook_data()
    pdf_bytes = render_pdf(data)
    img = pdf_to_image(pdf_bytes)
    img = apply_grain(img)
    img = apply_random_resize(img)

    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = f"bankbook_{index:04d}.png"
    out_path = OUTPUT_DIR / filename
    img.save(out_path)

    vendor_code = random_vendor_code()
    while vendor_code in used_vendor_codes:
        vendor_code = random_vendor_code()
    used_vendor_codes.add(vendor_code)

    row = {
        "doc_id": index,
        "거래처코드": vendor_code,
        "거래처명": data["holder_name"],
        "은행코드": BANK_CODES[data["bank_name"]],
        "파일명": filename,
        "파일경로": str(out_path),
    }
    return out_path, row


def main(count=100):
    register_font()
    used_vendor_codes = set()
    rows = []
    for i in range(1, count + 1):
        path, row = generate_one(i, used_vendor_codes)
        rows.append(row)
        print(f"[{i}/{count}] {path.name}")

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV saved: {CSV_PATH}")


if __name__ == "__main__":
    main()
