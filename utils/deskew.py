import cv2
import numpy as np
import math
from pathlib import Path


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

    return float(np.median(angles))


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

    angle = estimate_skew_angle(image)

    if abs(angle) < 0.5:
        corrected = image.copy()
        print("rotation skipped: already straight")
    else:
        corrected = deskew_image(
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

    return angle, Path(output_path)


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