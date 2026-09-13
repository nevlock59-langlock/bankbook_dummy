import cv2
import numpy as np
import math
from pathlib import Path

def resize_for_ocr(image, max_side=2000):
    h, w = image.shape[:2]

    scale = min(1.0, max_side / max(h, w))

    if scale == 1.0:
        return image

    return cv2.resize(
        image,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_AREA,
    )

def horizontal_projection_score(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(
        gray,
        50,
        150
    )

    # 회전하면서 생긴 바깥 테두리가 점수를 먹지 않게
    # 중앙 80% 정도만 평가
    h, w = edges.shape
    edges = edges[
        int(h * 0.1):int(h * 0.9),
        int(w * 0.1):int(w * 0.9)
    ]

    projection = np.sum(
        edges > 0,
        axis=1
    ).astype(np.float32)

    mean = np.mean(projection)

    if mean == 0:
        return 0.0

    return float(
        (
            np.percentile(projection, 90)
            - np.percentile(projection, 10)
        )
        / mean
    )

def read_image(path):
    """
    한글/공백이 포함된 Windows 경로도 안전하게 읽는다.
    """
    path = str(path)

    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)

    if image is None:
        raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {path}")

    return image


def save_image(path, image):
    """
    한글/공백이 포함된 Windows 경로도 안전하게 저장한다.
    """
    path = Path(path)

    ext = path.suffix.lower()

    if ext not in [".jpg", ".jpeg", ".png"]:
        ext = ".png"
        path = path.with_suffix(ext)

    success, encoded = cv2.imencode(ext, image)

    if not success:
        raise RuntimeError(f"이미지 저장 실패: {path}")

    encoded.tofile(str(path))

  
def choose_deskew(image, angle, min_gain=0.05):
    base_score = horizontal_projection_score(image)

    cand1 = deskew_image(image, angle)
    cand2 = deskew_image(image, -angle)

    score1 = horizontal_projection_score(cand1)
    score2 = horizontal_projection_score(cand2)

    best_score, best_img, best_angle = max(
        (score1, cand1, angle),
        (score2, cand2, -angle),
        (base_score, image, 0.0),
        key=lambda x: x[0]
    )
    
    print(f"estimated skew  : {angle:.3f}°")
    print(f"applied angle   : {applied_angle:.3f}°")
    
    if best_score < base_score * (1 + min_gain):
        return image, 0.0
        
    return best_img, best_angle

def estimate_skew_angle(image):
    """
    문서 내부의 수평선들을 찾아 기울기 각도를 추정한다.
    """

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    edges = cv2.Canny(
        gray,
        50,
        150,
        apertureSize=3
    )

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=80,
        maxLineGap=20
    )

    if lines is None:
        raise RuntimeError("문서에서 충분한 직선을 찾지 못했습니다.")

    angles = []
    weights = []

    for line in lines:
        x1, y1, x2, y2 = np.asarray(line).reshape(-1)[:4]

        dx = x2 - x1
        dy = y2 - y1

        angle = math.degrees(
            math.atan2(dy, dx)
        )

        # 선 방향은 180° 주기이므로 [-90, 90)로 정규화
        if angle >= 90:
            angle -= 180
        elif angle < -90:
            angle += 180

        length = math.hypot(dx, dy)

        angles.append(angle)
        weights.append(length)

    angles = np.array(angles)

    bins = np.arange(-90, 91, 2)
    hist, edges = np.histogram(angles, bins=bins)

    i = np.argmax(hist)

    dominant = angles[
        (angles >= edges[i]) &
        (angles < edges[i + 1])
    ]

    return float(np.median(dominant))


def deskew_image(image, angle):
    """
    추정한 기울기만큼 반대 방향으로 보정한다.
    """

    height, width = image.shape[:2]

    center = (
        width / 2,
        height / 2
    )

    matrix = cv2.getRotationMatrix2D(
        center,
        angle,
        1.0
    )

    corrected = cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    return corrected


def deskew_document(
    input_path,
    output_path=None
):
    """
    문서 이미지 한 장을 자동으로 회전 보정한다.

    Parameters
    ----------
    input_path:
        원본 이미지 경로

    output_path:
        보정 결과 경로.
        생략하면 원본 옆에 *_deskewed.png 로 저장한다.

    Returns
    -------
    estimated_angle, output_path
    """

    input_path = Path(input_path)

    image = read_image(input_path)
    image = resize_for_ocr(image)
    angle = estimate_skew_angle(image)
    corrected, applied_angle = choose_deskew(
        image,
        angle
    )
    

    if output_path is None:
        output_path = (
            input_path.parent
            / f"{input_path.stem}_deskewed.png"
        )

    save_image(
        output_path,
        corrected
    )

    print("=" * 60)
    print(f"input           : {input_path}")
    print(f"estimated skew  : {angle:.3f}°")
    print(f"output          : {output_path}")

    return applied_angle, Path(output_path)


# ============================================================
# 직접 실행
# ============================================================

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="스캔 문서 자동 회전 보정"
    )

    parser.add_argument(
        "input",
        help="보정할 이미지 경로"
    )

    parser.add_argument(
        "-o",
        "--output",
        help="결과 이미지 경로",
        default=None
    )

    args = parser.parse_args()

    deskew_document(
        args.input,
        args.output
    )
