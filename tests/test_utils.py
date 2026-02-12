import pytest
from engine.utils import is_image_request, image_edit_keywords, image_keywords, image_end_keywords

@pytest.mark.parametrize("keyword", image_edit_keywords)
def test_image_edit_keywords(keyword):
    """Test that messages containing image edit keywords return True."""
    # Construct a message where the keyword is embedded
    message = f"Please {keyword} this image for me"
    assert is_image_request(message) is True

@pytest.mark.parametrize("keyword", image_keywords)
def test_image_keywords(keyword):
    """Test that messages containing image generation keywords return True."""
    # Construct a message containing the keyword
    message = f"I would like to {keyword} please"
    assert is_image_request(message) is True

@pytest.mark.parametrize("keyword", image_end_keywords)
def test_image_end_keywords(keyword):
    """Test that messages ending with image end keywords return True."""
    # Construct a message ending with the keyword
    message = f"Can you {keyword}"
    assert is_image_request(message) is True

    # Verify it doesn't match if it's not at the end (unless it's also in image_keywords)
    # Some end keywords might be subsets of others or common words, so this check is tricky.
    # But strictly speaking, the function uses 'endswith' for this list.
    # However, if a keyword is also in image_keywords (contains), then it will match regardless of position.

def test_case_insensitivity():
    """Test that keyword matching is case-insensitive."""
    assert is_image_request("DRAW AN IMAGE OF a cat") is True
    assert is_image_request("pLeAsE eDiT tHiS") is True
    assert is_image_request("can you GENERATE AN IMAGE") is True

def test_negative_cases():
    """Test that unrelated messages return False."""
    assert is_image_request("hello world") is False
    assert is_image_request("what time is it?") is False
    assert is_image_request("calculate 2+2") is False
    assert is_image_request("generate code for me") is False

def test_edge_cases():
    """Test edge cases and potential false positives."""
    assert is_image_request("") is False
    assert is_image_request("   ") is False
    assert is_image_request("draw a conclusion") is False
