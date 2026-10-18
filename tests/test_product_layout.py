"""A layout's driving parameters, read by name: one shaft diameter drives three parts."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from anvilate.product import Product, ProductError, parse_product, parts_list, product_tree


def _mm(v: float) -> dict:
    return {"magnitude": v, "unit": "mm"}


def _holder(envelope: list, kg: float, holes: list | None = None) -> dict:
    return {"envelope": envelope, "mass": {"magnitude": kg, "unit": "kg"},
            "reason": "not yet detailed", "holes": holes or []}  # fmt: skip


def _bore(tag: str) -> list[dict]:
    return [{"tag": tag, "x": _mm(0), "y": _mm(0), "z": _mm(5), "face": "top",
             "diameter": {"layout": "shaft_dia"}}]  # fmt: skip


def _shaft_line(shaft_dia: float = 20.0) -> dict:
    """A shaft, a bearing seat and a collar, each reading ``shaft_dia``; ``stroke`` is unread."""
    shaft = {"layout": "shaft_dia"}
    return {
        "name": "spindle",
        "layout": {"parameters": [
            {"name": "shaft_dia", "value": _mm(shaft_dia), "source": "bearing catalogue bore"},
            {"name": "stroke", "value": _mm(300), "source": "customer requirement"},
        ]},
        "definitions": [
            {"id": "shaft", "identity": {"description": "shaft", "source": "make"},
             "placeholder": _holder([shaft, shaft, _mm(100)], 0.3)},
            {"id": "seat", "identity": {"description": "bearing seat", "source": "make"},
             "placeholder": _holder([_mm(60), _mm(60), _mm(10)], 0.4, _bore("bore"))},
            {"id": "collar", "identity": {"description": "collar", "source": "buy"},
             "placeholder": _holder([_mm(40), _mm(40), _mm(10)], 0.1, _bore("bore"))},
        ],
        "instances": [{"name": "seat", "item": "seat"}, {"name": "shaft", "item": "shaft"},
                      {"name": "collar", "item": "collar"}],
        "ground": "seat",
    }  # fmt: skip


def test_one_parameter_drives_every_item_that_reads_it():
    product = parse_product(_shaft_line())
    shaft, seat, collar = (d.placeholder for d in product.definitions)
    assert [q.to("mm").magnitude for q in shaft.envelope[:2]] == [20.0, 20.0]
    assert seat.holes[0].diameter.to("mm").magnitude == 20.0
    assert collar.holes[0].diameter.to("mm").magnitude == 20.0
    wider = parse_product(_shaft_line(25.0))
    shaft, seat, collar = (d.placeholder for d in wider.definitions)
    # changing the layout changes all three; no item's own entry was edited
    assert shaft.envelope[0].to("mm").magnitude == 25.0
    assert seat.holes[0].diameter.to("mm").magnitude == 25.0
    assert collar.holes[0].diameter.to("mm").magnitude == 25.0


def test_the_layout_records_its_readers_and_names_the_unused_parameter():
    layout = parse_product(_shaft_line()).layout
    assert layout is not None
    readers = layout.parameters[0].read_by
    assert readers == ("shaft:placeholder.envelope.0", "shaft:placeholder.envelope.1",
                       "seat:placeholder.holes.0.diameter",
                       "collar:placeholder.holes.0.diameter")  # fmt: skip
    assert layout.unused == ("stroke",)


def test_a_catalog_spec_reads_a_parameter_too():
    root = Path(__file__).resolve().parents[1]
    plate = yaml.safe_load((root / "examples" / "parts" / "mounting_plate.spec.yaml").read_text())
    plate["element_params"]["thickness"] = {"layout": "plate_t"}
    document = _shaft_line()
    document["layout"]["parameters"].append(
        {"name": "plate_t", "value": _mm(8), "source": "stiffness sizing"}
    )
    document["definitions"].append({"id": "plate", "identity": {"description": "plate",
                                    "source": "make"}, "spec": plate})  # fmt: skip
    product = parse_product(document)
    spec = product.definitions[-1].spec
    assert spec["element_params"]["thickness"] == {"magnitude": 8.0, "unit": "mm"}
    assert product.layout.parameters[-1].read_by == ("plate:spec.element_params.thickness",)


def test_the_layout_is_in_no_parts_list():
    lines = parts_list(product_tree(parse_product(_shaft_line())))
    assert sorted(line.description for line in lines) == ["bearing seat", "collar", "shaft"]


def test_a_provisional_number_follows_the_value_its_item_reads():
    def numbers(dia: float) -> dict[str, str]:
        tree = product_tree(parse_product(_shaft_line(dia)))
        return {node.definition: node.part_number for node in tree.children}

    narrow, wide = numbers(20.0), numbers(25.0)
    assert all(narrow[k] != wide[k] for k in ("shaft", "seat", "collar"))


def test_a_name_the_layout_does_not_declare_is_refused():
    document = _shaft_line()
    document["definitions"][0]["placeholder"]["mass"] = {"layout": "shaft_mass"}
    with pytest.raises(ProductError, match="'shaft' reads layout parameter 'shaft_mass' at "
                       "placeholder.mass, which the layout does not declare"):  # fmt: skip
        parse_product(document)


def test_a_parameter_declared_twice_is_refused():
    document = _shaft_line()
    document["layout"]["parameters"].append(copy.deepcopy(document["layout"]["parameters"][1]))
    with pytest.raises(ProductError, match=r"\['stroke'\] are declared twice"):
        parse_product(document)


def test_a_stored_product_cannot_claim_a_reader_it_does_not_have():
    product = parse_product(_shaft_line())
    assert Product.model_validate(product.model_dump(mode="json")) == product
    dumped = product.model_dump(mode="json")
    dumped["definitions"][0]["placeholder"]["envelope"][0] = _mm(30)
    # a refusal inside the model's validator reaches model_validate as a ValidationError
    with pytest.raises(ValueError, match="'shaft:placeholder.envelope.0' as a reader"):
        Product.model_validate(dumped)
    dumped = product.model_dump(mode="json")
    dumped["layout"]["parameters"][1]["read_by"] = ["nowhere:spec.x"]
    with pytest.raises(ValueError, match="'nowhere:spec.x'"):
        Product.model_validate(dumped)


def test_a_layout_is_its_parameters():
    layout = parse_product(_shaft_line()).layout
    assert len(layout) == 2 and layout.parameters[1] in layout
    assert [p.name for p in layout] == ["shaft_dia", "stroke"]
