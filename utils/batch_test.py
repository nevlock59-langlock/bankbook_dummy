from pathlib import Path

from rotate import rotate_image
from deskew import deskew_document


# ============================================================
# 테스트 케이스
#
# (이미지 파일명, 회전시킬 각도)
# ============================================================

TEST_CASES = [
    ("output/bankbook_0001.png", 7),
    ("output/bankbook_0002.png", -14),
    ("output/bankbook_0003.png", 23),
    ("output/bankbook_0004.png", -37),
    ("output/bankbook_0005.png", 48),
    ("output/bankbook_0006.png", -56),
    ("output/bankbook_0007.png", 67),
    ("output/bankbook_0008.png", -74),
    ("output/bankbook_0009.png", 83),
    ("output/bankbook_0010.png", -89),
]

# ============================================================
# 전체 실행
# ============================================================

results = []


for image_path, angle in TEST_CASES:

    print()
    print("#" * 70)
    print(f"TEST: {image_path} / {angle}°")
    print("#" * 70)


    # --------------------------------------------------------
    # 1. 테스트용 회전 이미지 생성
    # --------------------------------------------------------

    rotated_path = rotate_image(
        image_path,
        angle
    )


    # --------------------------------------------------------
    # 2. 원본 없이 deskew 수행
    # --------------------------------------------------------

    estimated_angle, deskewed_path = deskew_document(
        rotated_path
    )


    # --------------------------------------------------------
    # 3. 오차 계산
    #
    # 예:
    # +5° 회전 → deskew 추정 -4.99°
    #
    # 따라서 둘을 더하면 거의 0이 되어야 함.
    # --------------------------------------------------------

    error = abs(
        angle + estimated_angle
    )


    results.append({
        "file": image_path,
        "rotation": angle,
        "estimated": estimated_angle,
        "error": error,
        "rotated_path": rotated_path,
        "deskewed_path": deskewed_path,
    })


# ============================================================
# 결과 요약
# ============================================================

print()
print()
print("=" * 90)
print("SUMMARY")
print("=" * 90)

print(
    f"{'file':30}"
    f"{'rotation':>12}"
    f"{'estimated':>14}"
    f"{'error':>12}"
)

print("-" * 90)


for result in results:

    print(
        f"{result['file']:30}"
        f"{result['rotation']:>11.3f}°"
        f"{result['estimated']:>13.3f}°"
        f"{result['error']:>11.3f}°"
    )


# ============================================================
# 전체 통계
# ============================================================

errors = [
    result["error"]
    for result in results
]

if errors:

    mean_error = sum(errors) / len(errors)
    max_error = max(errors)

    print("-" * 90)

    print(
        f"mean absolute error : "
        f"{mean_error:.4f}°"
    )

    print(
        f"max absolute error  : "
        f"{max_error:.4f}°"
    )