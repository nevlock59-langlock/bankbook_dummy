from PIL import Image
from pathlib import Path
import argparse


def rotate_image(
    input_path,
    angle,
    output_path=None
):
    input_path = Path(input_path)

    image = Image.open(input_path).convert("RGB")

    rotated = image.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor="white"
    )

    if output_path is None:
        angle_text = str(angle).replace(".", "_")

        output_path = (
            input_path.parent
            / f"{input_path.stem}_rotated_{angle_text}deg.png"
        )

    rotated.save(output_path)

    print("=" * 60)
    print(f"input  : {input_path}")
    print(f"angle  : {angle}°")
    print(f"output : {output_path}")

    return Path(output_path)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="문서 테스트용 회전 이미지 생성"
    )

    parser.add_argument(
        "input",
        help="원본 이미지 경로"
    )

    parser.add_argument(
        "angle",
        type=float,
        help="회전 각도"
    )

    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="결과 이미지 경로"
    )

    args = parser.parse_args()

    rotate_image(
        args.input,
        args.angle,
        args.output
    )