from src.utils import clean_text


def test_clean_text_collapses_whitespace():
    assert clean_text("Hola   mundo\n\tprueba") == "Hola mundo prueba"
