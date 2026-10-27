"""Validate API documentation without calling models or modifying the service."""

import argparse
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from export_api_docs import METHODS, ROOT, reference_markdown


def operations(spec):
    return {(method, path) for path, item in spec["paths"].items() for method in item if method in METHODS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, help="原始运行 OpenAPI，校验端点集合未增减")
    parser.add_argument("--metaschema", type=Path, help="可选的 OpenAPI 3.1 官方 JSON metaschema")
    parser.add_argument("--verification", type=Path, help="可选的隔离调用核验记录，仅使用合成响应")
    args = parser.parse_args()
    folder = ROOT / "docs" / "api"
    spec = json.loads((folder / "openapi.json").read_text())
    assert spec["openapi"] == "3.1.0"
    all_operations = operations(spec)
    ids = [operation["operationId"] for item in spec["paths"].values() for method, operation in item.items() if method in METHODS]
    assert len(ids) == len(set(ids)), "Operation ID 重复"
    for schema in spec["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)

    def check_refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                pointer = value["$ref"]
                assert pointer.startswith("#/"), pointer
                target = spec
                for part in pointer[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)
    check_refs(spec)
    assert (folder / "ENDPOINTS.md").read_text() == reference_markdown(spec), "完整参考与 OpenAPI 不一致，请重新导出"

    guide = (folder / "README.md").read_text()
    parsed_examples = 0
    for block in re.findall(r"```json\n(.*?)\n```", guide, re.S):
        example = json.loads(block)
        parsed_examples += 1
        schema_name = None
        if isinstance(example, dict) and "newMessage" in example:
            schema_name = "RunAgentRequest"
        elif isinstance(example, dict) and "stateDelta" in example:
            schema_name = "UpdateSessionRequest"
        elif isinstance(example, dict) and "artifact" in example:
            schema_name = "SaveArtifactRequest"
        if schema_name:
            Draft202012Validator({"$ref": "#/components/schemas/" + schema_name, "components": spec["components"]}).validate(example)

    for page in folder.glob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", page.read_text()):
            if re.match(r"^(?:https?://|#)", link):
                continue
            assert (page.parent / link.split("#", 1)[0]).exists(), (page.name, link)
    if args.runtime:
        runtime = json.loads(args.runtime.read_text())
        assert operations(runtime) == all_operations, "发布定义与运行服务的 HTTP method/path 不一致"
    if args.metaschema:
        Draft202012Validator(json.loads(args.metaschema.read_text())).validate(spec)
    if args.verification:
        verification = json.loads(args.verification.read_text())
        assert verification["synthetic_only"] and not verification["live_model_api_used"]
        for name, data in [("ProjectCapabilityState", verification["capability_state"]), ("ProjectModelState", verification["model_state"]), ("Event-Output", verification["sample_event"])]:
            Draft202012Validator({"$ref": "#/components/schemas/" + name, "components": spec["components"]}).validate(data)
    print(json.dumps({"status": "PASS", "paths": len(spec["paths"]), "operations": len(all_operations),
                      "schemas": len(spec["components"]["schemas"]), "guide_json_examples": parsed_examples,
                      "runtime_coverage_checked": bool(args.runtime), "official_metaschema_checked": bool(args.metaschema),
                      "synthetic_responses_checked": bool(args.verification)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
