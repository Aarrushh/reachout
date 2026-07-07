import validate as v
from query_parser import SYNONYMS, parse_query


def _assert_valid(intent):
    ok, err = v.validate(intent, "search_intent.schema.json")
    assert ok, err


def test_t1_spanish_query_with_place_name():
    result = parse_query("algo para el dolor de cabeza en Malasaña")
    assert result == {
        "status": "ok",
        "raw_query": "algo para el dolor de cabeza en Malasaña",
        "keywords": ["dolor de cabeza", "analgésico", "paracetamol", "ibuprofeno"],
        "category_hints": ["pharmacy"],
        "location_text": "Malasaña",
    }
    _assert_valid(result)


def test_t2_no_location_cross_language():
    result = parse_query("cargador usb c")
    assert result == {
        "status": "ok",
        "raw_query": "cargador usb c",
        "keywords": ["cargador", "usb c", "charger"],
        "category_hints": ["electronics"],
        "location_text": None,
    }
    _assert_valid(result)


def test_t3_nothing_extractable():
    result = parse_query("???")
    assert result == {
        "status": "incomplete",
        "raw_query": "???",
        "missing_fields": ["keywords"],
    }
    _assert_valid(result)


def test_hardware_category_is_covered_and_ambiguous_with_electronics():
    result = parse_query("necesito pilas")
    _assert_valid(result)
    assert result["status"] == "ok"
    assert "hardware" in result["category_hints"]
    assert "electronics" in result["category_hints"]


def test_english_query_uses_bilingual_synonyms():
    result = parse_query("something for a headache")
    _assert_valid(result)
    assert result["status"] == "ok"
    assert "pharmacy" in result["category_hints"]
    assert "paracetamol" in result["keywords"]


def test_synonyms_map_has_multiword_bilingual_entries():
    assert any(" " in key for key in SYNONYMS)
    assert any(key in SYNONYMS for key in ["dolor de cabeza", "fiebre", "pilas"])
    assert any(key in SYNONYMS for key in ["headache", "fever"])


def test_default_path_never_touches_network(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-should-not-be-used")

    def _boom(*args, **kwargs):
        raise AssertionError("LLM path must not run without use_llm=True")

    monkeypatch.setattr("llm.parse_with_llm", _boom, raising=False)
    result = parse_query("cargador usb c")
    _assert_valid(result)
    assert result["keywords"] == ["cargador", "usb c", "charger"]


def test_fallback_on_schema_rejection_still_validates(monkeypatch):
    import query_parser

    def _legacy_shape(query):
        return {"raw_query": query, "keywords": ["x"], "category_hint": "pharmacy"}

    monkeypatch.setattr(query_parser, "_rule_based_parse", _legacy_shape)
    result = parse_query("leche")
    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["raw_query"] == "leche"
