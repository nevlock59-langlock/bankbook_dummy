import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from deskew import deskew_document


def read_paths_from_csv(csv_path):
    """
    1열짜리 CSV에서 파일 경로 목록을 읽는다.
    헤더가 있어도 되고 없어도 된다.
    """

    paths = []

    with open(
        csv_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.reader(f)

        for row in reader:

            if not row:
                continue

            value = row[0].strip()

            if not value:
                continue

            # 흔한 헤더명은 자동으로 건너뜀
            if value.lower() in {
                "file_path",
                "filepath",
                "path",
                "파일경로",
                "파일경로명",
            }:
                continue

            paths.append(value)

    return paths


def run_batch(csv_path, output_jsonl=None):

    csv_path = Path(csv_path)

    paths = read_paths_from_csv(csv_path)

    if output_jsonl is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_jsonl = (
            csv_path.parent
            / f"deskew_results_{timestamp}.jsonl"
        )

    output_jsonl = Path(output_jsonl)

    success_count = 0
    fail_count = 0

    print("=" * 70)
    print(f"CSV         : {csv_path}")
    print(f"documents   : {len(paths)}")
    print(f"result log  : {output_jsonl}")
    print("=" * 70)

    with open(
        output_jsonl,
        "w",
        encoding="utf-8"
    ) as log_file:

        for index, file_path in enumerate(paths, start=1):

            original_path = Path(file_path)

            print()
            print(
                f"[{index}/{len(paths)}] "
                f"{original_path.name}"
            )

            try:

                estimated_angle, deskewed_path = (
                    deskew_document(original_path)
                )

                record = {
                    "original_filename": original_path.name,
                    "original_path": str(original_path),
                    "deskew_angle": round(
                        estimated_angle,
                        6
                    ),
                    "deskewed_path": str(deskewed_path),
                    "status": "success",
                }

                success_count += 1

                print(
                    f"OK | deskew={estimated_angle:.3f}°"
                )

            except Exception as e:

                record = {
                    "original_filename": original_path.name,
                    "original_path": str(original_path),
                    "deskew_angle": None,
                    "deskewed_path": None,
                    "status": "failed",
                    "error": str(e),
                }

                fail_count += 1

                print(
                    f"FAIL | {e}"
                )

            # 한 문서 = JSON 한 줄
            log_file.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
                + "\n"
            )

            # 실행 중 죽어도 앞 기록은 최대한 남기기
            log_file.flush()

    print()
    print("=" * 70)
    print("BATCH SUMMARY")
    print("=" * 70)
    print(f"total   : {len(paths)}")
    print(f"success : {success_count}")
    print(f"failed  : {fail_count}")
    print(f"log     : {output_jsonl}")

    return output_jsonl


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="CSV 파일목록 기반 문서 일괄 deskew 테스트"
    )

    parser.add_argument(
        "csv",
        help="1열짜리 파일 절대경로 CSV"
    )

    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="결과 JSONL 경로"
    )

    args = parser.parse_args()

    run_batch(
        args.csv,
        args.output
    )