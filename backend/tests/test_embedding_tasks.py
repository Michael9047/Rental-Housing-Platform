from types import SimpleNamespace

from app.models.unit_type import PropertyType
from app.tasks.embedding_tasks import build_unit_type_embedding_payload


def test_embedding_payload_uses_safe_unit_type_and_institute_features() -> None:
    unit_type = SimpleNamespace(
        bedrooms=1,
        bathrooms=2,
        property_type=PropertyType.studio,
        institute=SimpleNamespace(country="SG"),
    )

    payload = build_unit_type_embedding_payload(unit_type)

    assert payload == {
        "title": "Rental unit",
        "description": "1 bedrooms 2 bathrooms",
        "address": "",
        "district": "SG",
        "property_type": "studio",
    }


def test_embedding_payload_tolerates_missing_institute_and_optional_type() -> None:
    unit_type = SimpleNamespace(
        bedrooms=None,
        bathrooms=None,
        property_type=None,
        institute=None,
    )

    payload = build_unit_type_embedding_payload(unit_type)

    assert payload["description"] == "0 bedrooms 0 bathrooms"
    assert payload["district"] == ""
    assert payload["property_type"] == ""
