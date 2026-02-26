import pytest
from engine.utils import extract_image_prompt

def test_extract_image_prompt_start():
    # 'draw an image of' is a keyword
    message = "draw an image of a futuristic city"
    expected = "a futuristic city"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_end():
    # 'generate image' is a keyword
    message = "a beautiful sunset generate image"
    expected = "a beautiful sunset"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_middle():
    # If text is before keyword, it returns text before.
    # 'generate image' is a keyword
    message = "a cybernetic dragon generate image style vaporwave"
    expected = "a cybernetic dragon"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_seeyuh_removal():
    message = "seeyuh draw an image of a happy dog"
    expected = "a happy dog"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_case_insensitivity():
    message = "DRAW AN IMAGE OF A NEON SIGN"
    expected = "a neon sign"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_whitespace():
    message = "   draw an image of    lots of space   "
    expected = "lots of space"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_no_keyword():
    message = "just a random conversation"
    expected = "just a random conversation"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_multiple_keywords():
    # "draw an image of" is likely first in the list
    # The function iterates through the list of keywords and stops at the first one found in the string.
    # If "draw an image of" is found first (checked first), it uses that.
    message = "draw an image of a cat generate image"
    expected = "a cat generate image"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_special_chars():
    message = "draw an image of @#$%^&*"
    expected = "@#$%^&*"
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_keyword_is_whole_message():
    # If the message IS the keyword
    message = "draw an image of"
    expected = ""
    assert extract_image_prompt(message) == expected

def test_extract_image_prompt_keyword_is_whole_message_stripped():
    # If the message IS the keyword with whitespace
    message = "  draw an image of  "
    expected = ""
    assert extract_image_prompt(message) == expected
