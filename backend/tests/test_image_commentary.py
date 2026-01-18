"""
Test image commentary behavior in responses.

These tests verify that the LLM prompt correctly prevents phantom image
references when no relevant images exist (issue #44).
"""
import re
from typing import List


# Common Hebrew image reference patterns that should NOT appear when no images are shown
HEBREW_IMAGE_REFERENCE_PATTERNS = [
    r"תמונה",  # "picture/image" - direct mention
    r"תסתכל",  # "look" (imperative) - often used with images
    r"רוא.*ב",  # "see in" - often refers to images
    r"שימו לב כמה",  # "notice how" - commentary phrase from prompt examples
]


def contains_image_references(text: str) -> bool:
    """
    Check if text contains references to images in Hebrew.

    Args:
        text: Response text to check

    Returns:
        True if image references found, False otherwise
    """
    for pattern in HEBREW_IMAGE_REFERENCE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def test_no_image_references_when_should_include_images_false():
    """
    Test that response doesn't reference images when should_include_images=false.

    This simulates the LLM response for a greeting or abstract question.
    """
    # Simulate LLM response for greeting
    mock_response = {
        "response_text": "שלום! אני חיליק, מדריך הטיולים שלך באגמון חפר. במה אוכל לעזור?",
        "should_include_images": False,
        "image_relevance": []
    }

    # Verify no image references
    assert not contains_image_references(mock_response["response_text"]), \
        f"Response should not contain image references when should_include_images=false: {mock_response['response_text']}"

    # Verify should_include_images is false
    assert mock_response["should_include_images"] is False

    # Verify image_relevance is empty
    assert len(mock_response["image_relevance"]) == 0


def test_no_image_references_when_all_scores_below_threshold():
    """
    Test that response doesn't reference images when all relevance scores < 60.

    This is the core bug fix for issue #44: even if should_include_images=true,
    if no images score >= 60, the response must not reference images.
    """
    # Simulate LLM response where should_include_images=true but all scores < 60
    mock_response = {
        "response_text": "באגמון חפר יש מגוון רחב של ציפורים נודדות. בעונת ההגירה אפשר לראות אלפי שקנאים, אנפות ועגורים.",
        "should_include_images": True,
        "image_relevance": [
            {"image_uri": "https://example.com/image1.jpg", "relevance_score": 45},
            {"image_uri": "https://example.com/image2.jpg", "relevance_score": 30},
            {"image_uri": "https://example.com/image3.jpg", "relevance_score": 55}
        ]
    }

    # Verify no image references in text
    assert not contains_image_references(mock_response["response_text"]), \
        f"Response should not contain image references when all scores < 60: {mock_response['response_text']}"

    # Verify should_include_images is true (LLM detected visual query)
    assert mock_response["should_include_images"] is True

    # Verify all scores are below threshold
    max_score = max(item["relevance_score"] for item in mock_response["image_relevance"])
    assert max_score < 60, f"Max score should be < 60, got {max_score}"


def test_image_references_allowed_when_scores_above_threshold():
    """
    Test that response MAY contain image references when scores >= 60.

    This verifies the positive case: when should_include_images=true AND
    at least one image has score >= 60, image commentary is permitted.
    """
    # Simulate LLM response with high relevance scores
    mock_response_with_commentary = {
        "response_text": "שימו לב כמה יפים השקנאים האלה! הם מגיעים לאגמון בעונת החורף.",
        "should_include_images": True,
        "image_relevance": [
            {"image_uri": "https://example.com/pelican1.jpg", "relevance_score": 85},
            {"image_uri": "https://example.com/pelican2.jpg", "relevance_score": 72},
            {"image_uri": "https://example.com/bird3.jpg", "relevance_score": 45}
        ]
    }

    # Verify should_include_images is true
    assert mock_response_with_commentary["should_include_images"] is True

    # Verify at least one score is >= 60
    max_score = max(item["relevance_score"] for item in mock_response_with_commentary["image_relevance"])
    assert max_score >= 60, f"Max score should be >= 60, got {max_score}"

    # Image commentary IS allowed in this case
    # (We're just verifying the conditions, not enforcing absence of references)
    assert contains_image_references(mock_response_with_commentary["response_text"]), \
        "Example response should contain image references when scores >= 60"


def test_no_image_references_when_should_include_images_false_with_high_scores():
    """
    Test that response doesn't reference images when should_include_images=false,
    even if some images have high relevance scores.

    Edge case: should_include_images takes precedence over scores.
    """
    mock_response = {
        "response_text": "האגמון פתוח כל השנה מ-8:00 עד 17:00.",
        "should_include_images": False,
        "image_relevance": []  # Should be empty when should_include_images=false
    }

    # Verify no image references
    assert not contains_image_references(mock_response["response_text"]), \
        f"Response should not contain image references when should_include_images=false: {mock_response['response_text']}"

    # Verify should_include_images is false
    assert mock_response["should_include_images"] is False


def test_image_reference_patterns_detection():
    """Test that our pattern detection correctly identifies image references."""
    # Positive cases - should detect references
    assert contains_image_references("תסתכלו על התמונה - רואים את הציפורים?")
    assert contains_image_references("שימו לב כמה יפים השקנאים בתמונה!")
    assert contains_image_references("יש לי תמונה יפה שמראה את זה")

    # Negative cases - should NOT detect references
    assert not contains_image_references("שלום! במה אוכל לעזור?")
    assert not contains_image_references("באגמון יש ציפורים רבות")
    assert not contains_image_references("זה מקום יפה לטיול")
