import os
import shutil
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("dissect-MCP")

TARGET_QUERY_BIN = os.getenv("DISSECT_TARGET_QUERY")
RDUMP_BIN = os.getenv("DISSECT_RDUMP")
TARGET_FS_BIN = os.getenv("DISSECT_TARGET_FS")
ACQUIRE_BIN = os.getenv("DISSECT_ACQUIRE_BIN")

ACQUIRE_OUTPUT_DIR = os.getenv("DISSECT_ACQUIRE_DIR")
DEFAULT_EXTRACT_DIR = os.getenv("DISSECT_EXTRACT_DIR")

class DissectError(RuntimeError):
    """Dissect 관련 외부 명령 실패 시 사용하는 예외."""

def _resolve_image(image_path: str) -> Dict[str, Any]:
    """
    디스크 이미지 경로 정규화 및 분할(raw) 이미지 병합 처리.

    - 입력: image_path (예: SCHARDT.001, 2023_KDFS.E01 등)
    - raw 분할 이미지(.001, .002 ...) 이면서 EWF(.E01, .EX01 등)가 아닌 경우:
      * 디렉터리 내 동일 prefix + .[0-9][0-9][0-9] 패턴을 모두 찾고
      * <stem>.raw 로 병합(SCHARDT.001 → SCHARDT.raw)
    - EWF 계열(.E01, .EX01 등)은 병합 없이 그대로 사용
    - 반환:
      {
        "original": 원본 경로(str),
        "target": 실제 사용될 경로(str),  (병합된 .raw 또는 원본)
        "segments": 세그먼트 목록(str 리스트),
        "merged": 병합 여부(bool)
      }
    """
    p = Path(image_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")

    segments: List[Path] = []
    merged = False
    merged_path: Optional[Path] = None

    m = re.search(r"\.([0-9]{3})$", p.name)
    if m and p.suffix.lower() not in {".e01", ".e02", ".ex01"}:
        stem = p.name[:-4]
        segs = sorted(p.parent.glob(stem + ".[0-9][0-9][0-9]"))
        if len(segs) > 1:
            segments = list(segs)
            merged_path = p.parent / f"{stem}.raw"
            if not merged_path.exists():
                merged_path.parent.mkdir(parents=True, exist_ok=True)
                with merged_path.open("wb") as out:
                    for seg in segments:
                        with seg.open("rb") as f:
                            shutil.copyfileobj(f, out)
            merged = True

    if not segments:
        segments = [p]

    return {
        "original": str(p),
        "target": str(merged_path or p),
        "segments": [str(s) for s in segments],
        "merged": merged,
    }

@mcp.tool()
def disk_image_info(image_path: str) -> Dict[str, Any]:
    """
    디스크 이미지 기본 정보 확인 (분할 이미지 병합 여부 포함).

    - _resolve_image 로 raw 스플릿 병합 여부 계산
    - 병합/세그먼트 목록, 파일 크기, 확장자 등 메타 정보 반환
    """
    resolved = _resolve_image(image_path)
    target = Path(resolved["target"])
    stat = target.stat()

    return {
        "original_path": resolved["original"],
        "resolved_path": str(target),
        "merged": resolved["merged"],
        "segments": resolved["segments"],
        "size_bytes": stat.st_size,
        "extension": target.suffix.lower(),
    }