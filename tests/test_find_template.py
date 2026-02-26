import pytest
from engine.commands.fun import find_template

# Some sample templates for testing
TEMPLATES = [
    "Drake Bad Good",
    "10 Guy",
    "Grumpy Cat",
    "Y U No",
    "Futurama Fry",
    "Chemistry Cat",
    "Condescending Wonka",
    "Distracted Boyfriend",
    "Expanding Brain",
    "Success Kid",
    "Two Buttons"
]

def test_find_template_manual_match():
    # drake is in MANUAL_TEMPLATE_MAP, should return Drake Bad Good
    assert find_template("drake", TEMPLATES) == "Drake Bad Good"
    assert find_template("can we use drake?", TEMPLATES) == "Drake Bad Good"
    assert find_template("drake meme", TEMPLATES) == "Drake Bad Good"

def test_find_template_direct_match():
    assert find_template("Success Kid", TEMPLATES) == "Success Kid"
    assert find_template("success kid", TEMPLATES) == "Success Kid"
    assert find_template("SUCCESS KID", TEMPLATES) == "Success Kid"

def test_find_template_partial_match():
    # "boyfriend" is part of "Distracted Boyfriend"
    assert find_template("boyfriend", TEMPLATES) == "Distracted Boyfriend"
    # "expanding" is part of "Expanding Brain"
    assert find_template("expanding", TEMPLATES) == "Expanding Brain"

def test_find_template_fuzzy_match():
    # Fuzzy match "succes kid" (missing 's') to "Success Kid"
    # ratio is ~0.95, cutoff is 0.8
    assert find_template("succes kid", TEMPLATES) == "Success Kid"

    # "twobuttons" (10 chars) vs "two buttons" (11 chars)
    # shared: "two", "buttons" (10)
    # ratio: 20/21 = 0.95
    assert find_template("twobuttons", TEMPLATES) == "Two Buttons"

def test_find_template_no_match():
    assert find_template("something completely different", TEMPLATES) is None
    assert find_template("", TEMPLATES) is None
    assert find_template("   ", TEMPLATES) is None

def test_find_template_fuzzy_near_cutoff():
    # "Drak Bad Good" vs "Drake Bad Good"
    # ratio is 24/27 = 0.888 > 0.8
    assert find_template("Drak Bad Good", TEMPLATES) == "Drake Bad Good"

def test_find_template_case_insensitivity():
    assert find_template("DRAKE", TEMPLATES) == "Drake Bad Good"
    assert find_template("dRaKe", TEMPLATES) == "Drake Bad Good"

def test_find_template_ignore_special_chars_in_manual_map():
    # "drake!!" should still match "drake" in manual map
    assert find_template("drake!!", TEMPLATES) == "Drake Bad Good"
