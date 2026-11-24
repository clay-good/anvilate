"""The worked gear reducer, taken through its whole journey in ONE request, offline.

A product is not a part, and the questions it raises are not a part's. This asks the
Anvilate server the one question an agent would ask about
`examples/products/gear_reducer.product.yaml` — build it — and reads everything else out
of the single reply. Nothing is fetched: the request is handled in this process and the
document is a file in this repository.

The reply carries four things, and the last two are what make it a journey rather than a
report:

- `product`, the ITEM tree: each item's own card.
- `whole_product`, the checks only a product has — how its load reaches the floor, and the
  drive train's. 18/36 twice is 4:1, so 1,500 rpm in is 375 rpm out, inside the 370 to
  380 rpm band the driven machine asks for, and 10 N·m in is 40 N·m out. Every one of
  these passes.
- `journey`, how far the design has come. It reads `described` and NOT `screened`, because
  seven of the reducer's items are still placeholders — and a journey read from the
  whole-product checks alone would have said `screened`, since those all pass. No FEA is
  demanded by this document, so that stage is not applicable rather than failing, and no
  study is declared, so optimisation is not applicable either.
- `next`, what to do about it: declare the specs of the items standing in as placeholders.
  That is the step that moves the design on, and it is derived from the card rather than
  chosen by anyone.

    python examples/gear_reducer_journey.py
"""

from __future__ import annotations

from pathlib import Path

_PRODUCT = Path(__file__).resolve().parent / "products" / "gear_reducer.product.yaml"


def answered() -> dict:
    """The server's reply to one `build_combination` request for the reducer."""
    from anvilate._models import parse_yaml
    from anvilate.mcp import handle_request

    document = parse_yaml(_PRODUCT.read_text(encoding="utf-8"))
    reply = handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "build_combination", "arguments": {"combination": document}},
    })  # fmt: skip
    return reply["result"]["structuredContent"]


def main() -> None:
    answer = answered()
    print(f"the reducer's items: {answer['product']['status']}")
    for node in answer["product"]["nodes"]:
        print(f"  {node['status']} — {node['path']}")
    print(f"\nthe product as a whole: {answer['whole_product']['status']}")
    for entry in answer["whole_product"]["entries"]:
        print(f"  {entry['status']} — {entry['name']}: {entry['detail']}")
    print(f"\nthe design has reached: {answer['journey']['stage']}")
    for stage in answer["journey"]["stages"]:
        gaps = "; ".join(stage["gaps"])
        print(f"  {stage['stage']}: {stage['state']}" + (f" — {gaps}" if gaps else ""))
    print("\nwhat to do next:")
    for step in answer["next"]["steps"]:
        passed = ", ".join(f"{k}={v}" for k, v in step["arguments"].items())
        print(f"  {step['tool']}({passed}): {step['reason']}")


if __name__ == "__main__":
    main()
