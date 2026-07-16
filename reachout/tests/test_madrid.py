from reachout.api.madrid import BARRIOS, match_barrio

def test_barrios_length():
    assert len(BARRIOS) == 24
    assert len(set(BARRIOS)) == 24

def test_match_barrio_exact():
    assert match_barrio("Chueca") == "Chueca"
    assert match_barrio("Salamanca") == "Salamanca"

def test_match_barrio_accent_case_insensitive():
    assert match_barrio("malasana") == "Malasaña"
    assert match_barrio("chamberi") == "Chamberí"
    assert match_barrio("CHAMBERI") == "Chamberí"
    assert match_barrio("sol") == "Sol"

def test_match_barrio_embedded_phrase():
    assert match_barrio("cerca de Lavapiés") == "Lavapiés"
    assert match_barrio("tiendas en malasana") == "Malasaña"

def test_match_barrio_none_empty_unknown():
    assert match_barrio(None) is None
    assert match_barrio("") is None
    assert match_barrio("Barcelona") is None
    assert match_barrio("   ") is None
