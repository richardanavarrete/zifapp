"""
Tests for LLM-based voice matching with bartender shorthand.

Run with: pytest tests/test_voice_matcher_llm.py -v
Or for quick local test: python tests/test_voice_matcher_llm.py
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_matcher import VoiceItemMatcher, MatchResult


@dataclass
class MockItem:
    """Mock Item for testing."""
    item_id: str
    display_name: str
    category: str
    vendor: str = "Test Vendor"


class MockInventoryDataset:
    """Mock inventory dataset with typical bar items."""

    def __init__(self):
        self.items: Dict[str, MockItem] = {
            # Vodka
            "VODKA Titos": MockItem("VODKA Titos", "Titos", "VODKA"),
            "VODKA Grey Goose": MockItem("VODKA Grey Goose", "Grey Goose", "VODKA"),
            "VODKA Well": MockItem("VODKA Well", "Well Vodka", "VODKA"),
            "VODKA Ketel One": MockItem("VODKA Ketel One", "Ketel One", "VODKA"),

            # Whiskey
            "WHISKEY Buffalo Trace": MockItem("WHISKEY Buffalo Trace", "Buffalo Trace", "WHISKEY"),
            "WHISKEY Jack Daniels Tennessee Fire": MockItem("WHISKEY Jack Daniels Tennessee Fire", "Jack Fire", "WHISKEY"),
            "WHISKEY Jameson": MockItem("WHISKEY Jameson", "Jameson", "WHISKEY"),
            "WHISKEY Makers Mark": MockItem("WHISKEY Makers Mark", "Makers Mark", "WHISKEY"),

            # Rum
            "RUM Captain Morgan Spiced": MockItem("RUM Captain Morgan Spiced", "Captain Morgan Spiced", "RUM"),
            "RUM Bacardi Silver": MockItem("RUM Bacardi Silver", "Bacardi Silver", "RUM"),

            # Tequila
            "TEQUILA Patron Silver": MockItem("TEQUILA Patron Silver", "Patron Silver", "TEQUILA"),
            "TEQUILA Don Julio Blanco": MockItem("TEQUILA Don Julio Blanco", "Don Julio Blanco", "TEQUILA"),

            # Beer
            "BEER DFT Bud Light": MockItem("BEER DFT Bud Light", "Bud Light Draft", "BEER"),
            "BEER BTL Miller Lite": MockItem("BEER BTL Miller Lite", "Miller Lite Bottle", "BEER"),
            "BEER DFT Stella Artois": MockItem("BEER DFT Stella Artois", "Stella Artois Draft", "BEER"),
        }


# Test cases from the user's requirements
BARTENDER_TEST_CASES = [
    # (transcript, expected_item, expected_count)
    ("Tito's handle 8 and a half", "VODKA Titos", 8.5),
    ("Goose 3", "VODKA Grey Goose", 3),
    ("Captain 5", "RUM Captain Morgan Spiced", 5),
    ("BT 2", "WHISKEY Buffalo Trace", 2),
    ("Jack fire 4", "WHISKEY Jack Daniels Tennessee Fire", 4),
    ("well vodka 6", "VODKA Well", 6),
    ("Patron 2 and a half", "TEQUILA Patron Silver", 2.5),
    ("Bud Light draft half", "BEER DFT Bud Light", 0.5),
]

# This should NOT match anything
NO_MATCH_CASES = [
    "Henny",  # Hennessy not in inventory
    "Crown",  # Crown Royal not in inventory
]


def test_bartender_shorthand():
    """Test that LLM correctly matches bartender shorthand."""
    # Skip if no API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("SKIP: OPENAI_API_KEY not set")
        return

    dataset = MockInventoryDataset()
    matcher = VoiceItemMatcher(dataset, api_key=api_key)

    print("\n" + "=" * 70)
    print("BARTENDER SHORTHAND MATCHING TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    for transcript, expected_item, expected_count in BARTENDER_TEST_CASES:
        matches, count, _, needs_manual = matcher.match_with_count(transcript)

        actual_item = matches[0].item_id if matches and not needs_manual else None
        actual_count = count

        item_ok = actual_item == expected_item
        count_ok = actual_count == expected_count

        status = "PASS" if (item_ok and count_ok) else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"\n[{status}] \"{transcript}\"")
        print(f"  Expected: {expected_item}, {expected_count}")
        print(f"  Got:      {actual_item}, {actual_count}")
        if matches:
            print(f"  Method:   {matches[0].method}, Confidence: {matches[0].confidence}")

    print("\n" + "-" * 70)
    print("NO-MATCH TESTS (should return no matches)")
    print("-" * 70)

    for transcript in NO_MATCH_CASES:
        matches, count, _, needs_manual = matcher.match_with_count(transcript)

        # For no-match cases, needs_manual should be True (item needs manual mapping)
        if needs_manual or not matches:
            print(f"\n[PASS] \"{transcript}\" - Correctly flagged for manual mapping (needs_manual={needs_manual})")
            passed += 1
        else:
            # LLM matched something it shouldn't have
            print(f"\n[FAIL] \"{transcript}\" - LLM incorrectly matched to {matches[0].item_id}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


def test_fallback_to_rapidfuzz():
    """Test that matcher falls back to rapidfuzz when API key is missing."""
    dataset = MockInventoryDataset()

    # Create matcher with no API key
    matcher = VoiceItemMatcher(dataset, api_key=None)
    matcher.api_key = None  # Ensure it's None

    # Should fall back to rapidfuzz
    matches, count, _, needs_manual = matcher.match_with_count("Buffalo Trace 3")

    assert len(matches) > 0, "Should have matches from rapidfuzz fallback"
    assert matches[0].method != "llm", "Should not be LLM method"
    print(f"Fallback test: matched '{matches[0].item_id}' with method '{matches[0].method}'")


if __name__ == "__main__":
    print("Running voice matcher LLM tests...\n")

    # Run fallback test first (doesn't need API key)
    print("Testing rapidfuzz fallback (no API key)...")
    test_fallback_to_rapidfuzz()
    print("Fallback test passed!\n")

    # Run main tests (needs API key)
    success = test_bartender_shorthand()
    sys.exit(0 if success else 1)
