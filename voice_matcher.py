"""
Voice Item Matcher - Fuzzy matching for voice-to-text inventory counting.

This module provides intelligent matching between voice transcripts and inventory items.
Uses rapidfuzz for fuzzy string matching with confidence scoring.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz


@dataclass
class MatchResult:
    """Result of a fuzzy match operation."""
    item_id: str
    matched_text: str  # What part of the item name matched
    confidence: float  # 0.0-1.0
    method: str  # "exact", "fuzzy", "partial", "token_sort"


class VoiceItemMatcher:
    """
    Intelligent fuzzy matcher for voice transcripts to inventory items.

    Features:
    - Multiple matching strategies (exact, fuzzy, partial, token sort)
    - Confidence scoring (0.0-1.0)
    - Support for common variations and abbreviations
    - Category-aware matching
    """

    def __init__(self, inventory_dataset):
        """
        Initialize the matcher with an inventory dataset.

        Args:
            inventory_dataset: InventoryDataset object with items dict
        """
        self.items = inventory_dataset.items
        self.search_index = self._build_search_index()

    def _build_search_index(self) -> Dict[str, List[str]]:
        """
        Build a search index with multiple variations of each item name.

        Returns:
            Dict mapping item_id to list of searchable text variations
        """
        index = {}

        for item_id, item in self.items.items():
            variations = []

            # 1. Full item_id (e.g., "WHISKEY Buffalo Trace")
            variations.append(item_id)

            # 2. Display name
            variations.append(item.display_name)

            # 3. Item name without category prefix
            # "WHISKEY Buffalo Trace" -> "Buffalo Trace"
            parts = item_id.split(' ', 1)
            if len(parts) > 1:
                # Only add the suffix if it's unique enough (more than one word or longer than 4 chars)
                # This prevents all "VODKA Well", "RUM Well" etc from having identical "Well" variation
                suffix = parts[1]
                suffix_words = suffix.split()
                if len(suffix_words) > 1 or len(suffix) > 4:
                    variations.append(suffix)

            # 4. Lowercase versions for case-insensitive matching
            variations.append(item_id.lower())
            variations.append(item.display_name.lower())

            # 5. Reversed word order for two-word items (critical for "well vodka" vs "VODKA Well")
            # "VODKA Well" -> also add "Well VODKA" and "well vodka"
            if len(parts) == 2:
                # Add reversed order in both cases
                reversed_id = f"{parts[1]} {parts[0]}"
                variations.append(reversed_id)
                variations.append(reversed_id.lower())

            # 6. Category + short name
            # "Whiskey Buffalo" from "WHISKEY Buffalo Trace"
            if len(parts) > 1:
                name_words = parts[1].split()
                if name_words:
                    variations.append(f"{item.category} {name_words[0]}")

            # 7. Remove common words that add noise
            cleaned = self._clean_for_matching(item_id)
            variations.append(cleaned)

            index[item_id] = list(set(variations))  # Remove duplicates

        return index

    def _clean_for_matching(self, text: str) -> str:
        """
        Clean text for matching by removing noise words and normalizing.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text
        """
        # Convert to lowercase
        text = text.lower()

        # Remove common noise words
        noise_words = ['bottle', 'keg', 'draft', 'on tap', 'the', 'a', 'an']
        for word in noise_words:
            text = re.sub(r'\b' + word + r'\b', '', text, flags=re.IGNORECASE)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _has_key_word_match(self, transcript: str, variation: str) -> bool:
        """
        Check if transcript contains key identifying words from the variation.

        Prevents bad matches like "Villa San-Juliette" matching "Villa Sandi"
        where only the first word matches but the brand name is different.

        Args:
            transcript: User input (lowercase)
            variation: Item variation to check (lowercase)

        Returns:
            True if key brand words are present in transcript
        """
        # Split into words
        transcript_words = set(transcript.split())
        variation_words = set(variation.split())

        # Common category/type words that shouldn't be the only match
        non_distinctive = {
            'vodka', 'whiskey', 'bourbon', 'rum', 'gin', 'tequila',
            'beer', 'wine', 'ipa', 'lager', 'pale', 'ale', 'stout',
            'red', 'white', 'chardonnay', 'pinot', 'grigio', 'noir', 'sauvignon', 'blanc',
            'the', 'a', 'an', 'bottle', 'can', 'draft', 'keg'
        }

        # Get distinctive words from variation (the brand name parts)
        distinctive_variation_words = variation_words - non_distinctive

        if not distinctive_variation_words:
            # If no distinctive words, allow the match (edge case)
            return True

        # Check if at least one distinctive word appears in transcript
        # For multi-word brands like "Buffalo Trace" or "Villa San-Juliette",
        # at least one of the brand words must match
        matches = transcript_words & distinctive_variation_words

        return len(matches) > 0

    def match(self, transcript: str, top_n: int = 3) -> List[MatchResult]:
        """
        Find the best matching items for a voice transcript.

        Tries multiple matching strategies:
        1. Exact match (case-insensitive)
        2. Fuzzy match (Levenshtein distance)
        3. Partial ratio (substring matching)
        4. Token sort ratio (word order independent)

        Args:
            transcript: Voice-to-text transcript
            top_n: Number of top matches to return

        Returns:
            List of MatchResult objects sorted by confidence (highest first)
        """
        if not transcript or not transcript.strip():
            return []

        transcript = transcript.strip()
        self._clean_for_matching(transcript)
        results = []

        # Strategy 1: Exact match (case-insensitive)
        for item_id, variations in self.search_index.items():
            for variation in variations:
                if transcript.lower() == variation.lower():
                    results.append(MatchResult(
                        item_id=item_id,
                        matched_text=variation,
                        confidence=1.0,
                        method="exact"
                    ))
                    break

        # If we found exact matches, return them immediately
        if results:
            return results[:top_n]

        # Strategy 2: Fuzzy matching with multiple algorithms
        all_candidates = []

        for item_id, variations in self.search_index.items():
            best_score = 0
            best_variation = None
            best_method = None

            for variation in variations:
                # Try different matching algorithms
                scores = {
                    'fuzzy': fuzz.ratio(transcript.lower(), variation.lower()),
                    'partial': fuzz.partial_ratio(transcript.lower(), variation.lower()),
                    'token_sort': fuzz.token_sort_ratio(transcript.lower(), variation.lower())
                }

                # Find the best score for this variation
                for method, score in scores.items():
                    if score > best_score:
                        best_score = score
                        best_variation = variation
                        best_method = method

            # Add to candidates if score is above threshold
            # Use stricter threshold (65%) and require key brand words to match
            if best_score >= 65:
                # Additional check: ensure key brand words are present
                if self._has_key_word_match(transcript.lower(), best_variation.lower()):
                    all_candidates.append((
                        item_id,
                        best_variation,
                        best_score / 100.0,  # Convert to 0.0-1.0
                        best_method
                    ))
            elif best_score >= 50:
                # Lower threshold (50-65%) only if very strong key word overlap
                transcript_words = set(transcript.lower().split())
                variation_words = set(best_variation.lower().split())

                # Remove common noise words for comparison
                noise = {'the', 'a', 'an', 'vodka', 'whiskey', 'rum', 'gin', 'beer', 'wine', 'bottle', 'can'}
                transcript_key_words = transcript_words - noise
                variation_key_words = variation_words - noise

                # Require at least 80% of key words to match
                if transcript_key_words and variation_key_words:
                    overlap = len(transcript_key_words & variation_key_words)
                    min_keys = min(len(transcript_key_words), len(variation_key_words))
                    if overlap / min_keys >= 0.8:
                        all_candidates.append((
                            item_id,
                            best_variation,
                            best_score / 100.0,
                            best_method
                        ))

        # Sort by confidence and take top N
        all_candidates.sort(key=lambda x: x[2], reverse=True)

        for item_id, matched_text, confidence, method in all_candidates[:top_n]:
            results.append(MatchResult(
                item_id=item_id,
                matched_text=matched_text,
                confidence=confidence,
                method=method
            ))

        return results

    def parse_count_from_transcript(self, transcript: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Parse item name and count from a transcript.

        Handles formats like:
        - "buffalo trace three"
        - "titos 5"
        - "3 miller lite"
        - "bourbon barrel two point five"
        - "buffalo trace 850 grams" (weight-based)
        - "bud light keg 65 pounds" (keg weight)

        Args:
            transcript: Voice transcript

        Returns:
            Tuple of (item_text, count_value, is_weight, weight_unit)
        """
        # Number word to digit mapping
        number_words = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
            'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
            'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
            'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
            'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
            'eighty': 80, 'ninety': 90, 'hundred': 100
        }

        # Fractional words
        fraction_words = {
            'half': 0.5, 'quarter': 0.25, 'third': 0.33
        }

        transcript_lower = transcript.lower().strip()

        # Check for weight-based input (grams or pounds)
        # Pattern: "item name 850 grams" or "item 65 pounds"
        weight_match = re.search(r'(.+?)\s+(\d+(?:\.\d+)?)\s*(grams?|g|pounds?|lbs?|lb)\s*$', transcript_lower)
        if weight_match:
            item_text = weight_match.group(1).strip()
            weight_value = float(weight_match.group(2))
            weight_unit = weight_match.group(3)

            # Normalize unit
            if weight_unit in ['grams', 'gram', 'g']:
                normalized_unit = 'grams'
            else:
                normalized_unit = 'pounds'

            # Return as special format: (item_text, weight_value, weight_unit)
            # The caller will need to handle this differently
            return (item_text, weight_value, normalized_unit)

        # Pattern 1: Number at the end (e.g., "buffalo trace 3")
        match = re.search(r'(.+?)\s+(\d+(?:\.\d+)?)\s*$', transcript_lower)
        if match:
            return (match.group(1).strip(), float(match.group(2)), None)

        # Pattern 2: Number at the start (e.g., "3 miller lite")
        match = re.search(r'^(\d+(?:\.\d+)?)\s+(.+)$', transcript_lower)
        if match:
            return (match.group(2).strip(), float(match.group(1)), None)

        # Pattern 3: Number word at the end (e.g., "buffalo trace three")
        words = transcript_lower.split()
        if len(words) >= 2:
            last_word = words[-1]
            if last_word in number_words:
                item_text = ' '.join(words[:-1])
                return (item_text, float(number_words[last_word]), None)

            # Check for "point" pattern (e.g., "two point five")
            if len(words) >= 3 and words[-2] == 'point':
                second_last = words[-3] if len(words) >= 3 else None
                if second_last in number_words and last_word in number_words:
                    count = number_words[second_last] + (number_words[last_word] / 10.0)
                    item_text = ' '.join(words[:-3])
                    return (item_text, count, None)

        # Pattern 4: Number word at the start (e.g., "three buffalo trace")
        if words and words[0] in number_words:
            item_text = ' '.join(words[1:])
            return (item_text, float(number_words[words[0]]), None)

        # Pattern 5: Fraction words (e.g., "buffalo trace half")
        if words and words[-1] in fraction_words:
            item_text = ' '.join(words[:-1])
            return (item_text, fraction_words[words[-1]], None)

        # No count found, return transcript as item text with no count
        return (transcript, None, None)

    def match_with_count(self, transcript: str, top_n: int = 3) -> Tuple[List[MatchResult], Optional[float], Optional[str]]:
        """
        Parse and match a transcript that includes both item name and count.

        Args:
            transcript: Voice transcript (e.g., "buffalo trace 3" or "buffalo trace 850 grams")
            top_n: Number of top matches to return

        Returns:
            Tuple of (match_results, count_value, weight_unit)
            - weight_unit is "grams" or "pounds" if weight was detected, None otherwise
        """
        # First, try to parse out the count/weight
        parse_result = self.parse_count_from_transcript(transcript)
        item_text, count_value, weight_unit = parse_result

        # Then match the item text
        matches = self.match(item_text, top_n=top_n)

        return matches, count_value, weight_unit

    def get_confidence_level(self, confidence: float) -> str:
        """
        Convert confidence score to human-readable level.

        Args:
            confidence: Score from 0.0 to 1.0

        Returns:
            "high", "medium", or "low"
        """
        if confidence >= 0.85:
            return "high"
        elif confidence >= 0.70:
            return "medium"
        else:
            return "low"

    def suggest_alternatives(self, transcript: str, exclude_item_ids: List[str] = None) -> List[str]:
        """
        Suggest alternative item names based on partial transcript.

        Useful for autocomplete or disambiguation UI.

        Args:
            transcript: Partial transcript
            exclude_item_ids: Item IDs to exclude from suggestions

        Returns:
            List of item_id suggestions
        """
        if not transcript:
            return []

        exclude_item_ids = exclude_item_ids or []
        matches = self.match(transcript, top_n=10)

        suggestions = []
        for match in matches:
            if match.item_id not in exclude_item_ids and match.confidence >= 0.5:
                suggestions.append(match.item_id)

        return suggestions[:5]
