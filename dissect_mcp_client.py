import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

SERVER_PY = "/Users/whiteing/GitHub/Dissect-mcp-server/dissect_mcp_server.py"
PYTHON_BIN = "/Users/whiteing/GitHub/Dissect-mcp-server/.venv/bin/python"
IMAGE_PATH = "/Users/whiteing/GitHub/Dissect-mcp-server/Caldera_01_diskImage.E01"

# Dissect 바이너리 / 출력 디렉토리 경로
DISSECT_VENV_BIN = "/Users/whiteing/GitHub/Dissect-mcp-server/.venv/bin"
ACQUIRE_OUTPUT_DIR = "/Users/whiteing/GitHub/Dissect-mcp-server/acquire_output"
EXTRACT_DIR = "/Users/whiteing/GitHub/Dissect-mcp-server/dissect_extracts"

RESULTS_DIR = Path("./results")


def _ensure_dirs() -> None:
    Path(ACQUIRE_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(EXTRACT_DIR).mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def save_and_print(
    result: types.CallToolResult,
    name: str,
) -> None:
    """Tool 결과를 콘솔에 찍고 ./results/<name>.json 으로 저장."""
    texts: list[str] = []
    for content in result.content:
        if isinstance(content, types.TextContent):
            texts.append(content.text)
        else:
            texts.append(str(content))

    joined = "\n".join(texts).strip()
    out_path = RESULTS_DIR / f"{name}.json"

    try:
        data = json.loads(joined)
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        print(pretty)
        out_path.write_text(pretty, encoding="utf-8")
        print(f"\n[+] Saved JSON result → {out_path}")
    except json.JSONDecodeError:
        print(joined)
        out_path.write_text(joined, encoding="utf-8")
        print(f"\n[+] Saved raw text result → {out_path}")


async def main() -> None:
    _ensure_dirs()

    server_params = StdioServerParameters(
        command=PYTHON_BIN,
        args=[SERVER_PY],
        env={
            "DISSECT_TARGET_QUERY": f"{DISSECT_VENV_BIN}/target-query",
            "DISSECT_RDUMP": f"{DISSECT_VENV_BIN}/rdump",
            "DISSECT_TARGET_FS": f"{DISSECT_VENV_BIN}/target-fs",
            "DISSECT_ACQUIRE_BIN": f"{DISSECT_VENV_BIN}/acquire",
            "DISSECT_ACQUIRE_DIR": ACQUIRE_OUTPUT_DIR,
            "DISSECT_EXTRACT_DIR": EXTRACT_DIR,
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) disk_image_info
            print("\n=== disk_image_info ===")
            info_result = await session.call_tool(
                "disk_image_info",
                arguments={"image_path": IMAGE_PATH},
            )
            save_and_print(info_result, "disk_image_info")

            # 2) list_plugins
            print("\n=== list_plugins ===")
            lp_result = await session.call_tool(
                "list_plugins",
                arguments={"image_path": IMAGE_PATH},
            )
            save_and_print(lp_result, "list_plugins")

            # 3) list_artifact_plugins (서버에 새로 추가한 MCP tool)
            print("\n=== list_artifact_plugins ===")
            lap_result = await session.call_tool(
                "list_artifact_plugins",
                arguments={},
            )
            save_and_print(lap_result, "list_artifact_plugins")

            # JSON 파싱해서 artifacts 목록 가져오기
            artifacts_raw = ""
            for c in lap_result.content:
                if isinstance(c, types.TextContent):
                    artifacts_raw += c.text
            artifacts = json.loads(artifacts_raw)["artifacts"]

            # 4) 각 artifact plugin을 하나씩 순차 실행
            for art in artifacts:
                key = art["key"]
                plugin = art["plugin"]
                print(f"\n=== run_single_plugin: {key} ({plugin}) ===")

                res = await session.call_tool(
                    "run_single_plugin",
                    arguments={
                        "image_path": IMAGE_PATH,
                        "plugin": plugin,
                        "max_rows": 500,  # 필요에 따라 조절
                    },
                )
                # 플러그인마다 파일 따로 저장
                save_and_print(res, f"artifact_{key}")

            # 5) extract_system_profile
            print("\n=== extract_system_profile ===")
            esp_result = await session.call_tool(
                "extract_system_profile",
                arguments={"image_path": IMAGE_PATH},
            )
            save_and_print(esp_result, "extract_system_profile")


if __name__ == "__main__":
    asyncio.run(main())