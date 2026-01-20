"""
Fuzzy Matcher

Matches voice input text to inventory items using multiple strategies.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from rapidfuzz import fuzz, process

from houndcogs.models.inventory import Item
from houndcogs.models.voice import MatchCandidate, MatchResult

logger = logging.getLogger(__name__)


@dataclass
class ParsedInput:
    """Parsed voice input with quantity and item text."""
    raw_text: str
    item_text: str
    quantity: Optional[float]
    unit: Optional[str]


class FuzzyMatcher:
    """
    Fuzzy matcher for inventory items.

    Builds an index from item names and provides multiple matching strategies.
    """

    def __init__(
        self,
        items: Dict[str, Item],
        confidence_threshold: float = 0.8,
    ):
        """
        Initialize matcher with inventory items.

        Args:
            items: Dictionary of item_id -> Item
            confidence_threshold: Minimum confidence for automatic match
        """
        self.items = items
        self.confidence_threshold = confidence_threshold

        # Build search index
        self._item_names: Dict[str, str] = {}  # normalized_name -> item_id
        self._build_index()

    def _build_index(self):
        """Build the search index from items."""
        for item_id, item in self.items.items():
            # Index by display name
            normalized = self._normalize(item.display_name)
            self._item_names[normalized] = item_id

            # Also index by item_id (which often contains category + name)
            normalized_id = self._normalize(item_id)
            if normalized_id != normalized:
                self._item_names[normalized_id] = item_id

        logger.info(f"Built fuzzy match index with {len(self._item_names)} entries")

    def _normalize(self, text: str) -> str:
        """Normalize text for matching."""
        # Lowercase, remove extra spaces
        text = ' '.join(text.lower().split())
        # Remove common prefixes/suffixes
        text = re.sub(r'^(the|a|an)\s+', '', text)
        return text

    def match_text(
        self,
        text: str,
        max_alternatives: int = 3,
    ) -> List[MatchResult]:
        """
        Match transcribed text to inventory items.

        Parses the text to extract individual items with quantities,
        then matches each to the inventory.

        Args:
            text: Transcribed voice text
            max_alternatives: Max number of alternative matches to return

        Returns:
            List of MatchResult for each parsed item
        """
        # Parse text into individual items
        parsed_items = self._parse_text(text)

        results = []
        for parsed in parsed_items:
            result = self._match_single(parsed, max_alternatives)
            results.append(result)

        return results

    def _parse_text(self, text: str) -> List[ParsedInput]:
        """
        Parse text into individual item mentions.

        Handles patterns like:
        - "buffalo trace 2 bottles"
        - "titos 3, jameson 1"
        - "2 buffalo trace, 3 titos"
        """
        text = text.lower().strip()
        items = []

        # Pattern: quantity + item or item + quantity
        # Split on common separators
        segments = re.split(r'[,;]|\band\b', text)

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            parsed = self._parse_segment(segment)
            if parsed:
                items.append(parsed)

        return items

    def _parse_segment(self, segment: str) -> Optional[ParsedInput]:
        """Parse a single segment into item + quantity."""
        # Pattern: "N item" or "item N" or "item N unit"
        patterns = [
            # "2 buffalo trace" or "two buffalo trace"
            r'^(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s+(.+?)(?:\s+(bottles?|cases?|units?))?$',
            # "buffalo trace 2" or "buffalo trace 2 bottles"
            r'^(.+?)\s+(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)(?:\s+(bottles?|cases?|units?))?$',
            # Just item name (assume quantity 1)
            r'^(.+)$',
        ]

        word_to_num = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        }

        for pattern in patterns:
            match = re.match(pattern, segment, re.IGNORECASE)
            if match:
                groups = match.groups()

                if len(groups) >= 2:
                    # Check which group is the number
                    try:
                        # First group is number
                        qty = float(groups[0])
                        item_text = groups[1]
                    except ValueError:
                        if groups[0].lower() in word_to_num:
                            qty = word_to_num[groups[0].lower()]
                            item_text = groups[1]
                        else:
                            # Second group might be number
                            try:
                                qty = float(groups[1])
                                item_text = groups[0]
                            except ValueError:
                                if groups[1].lower() in word_to_num:
                                    qty = word_to_num[groups[1].lower()]
                                    item_text = groups[0]
                                else:
                                    qty = 1.0
                                    item_text = groups[0]

                    unit = groups[2] if len(groups) > 2 and groups[2] else "bottles"
                else:
                    qty = 1.0
                    item_text = groups[0]
                    unit = "bottles"

                return ParsedInput(
                    raw_text=segment,
                    item_text=item_text.strip(),
                    quantity=qty,
                    unit=unit,
                )

        return None

    def _match_single(
        self,
        parsed: ParsedInput,
        max_alternatives: int,
    ) -> MatchResult:
        """Match a single parsed input to items."""
        query = self._normalize(parsed.item_text)

        # Try different matching strategies
        candidates = []

        # 1. Exact match
        if query in self._item_names:
            item_id = self._item_names[query]
            item = self.items[item_id]
            candidates.append(MatchCandidate(
                item_id=item_id,
                display_name=item.display_name,
                category=item.category.value if hasattr(item.category, 'value') else str(item.category),
                confidence=1.0,
                match_method="exact",
            ))

        # 2. Fuzzy match using rapidfuzz
        if not candidates or candidates[0].confidence < 1.0:
            fuzzy_matches = process.extract(
                query,
                list(self._item_names.keys()),
                scorer=fuzz.WRatio,
                limit=max_alternatives + 1,
            )

            for match_text, score, _ in fuzzy_matches:
                item_id = self._item_names[match_text]
                item = self.items[item_id]
                confidence = score / 100.0

                # Skip if already have exact match
                if any(c.item_id == item_id for c in candidates):
                    continue

                candidates.append(MatchCandidate(
                    item_id=item_id,
                    display_name=item.display_name,
                    category=item.category.value if hasattr(item.category, 'value') else str(item.category),
                    confidence=confidence,
                    match_method="fuzzy",
                ))

        # Sort by confidence
        candidates.sort(key=lambda c: c.confidence, reverse=True)

        # Determine best match
        best_match = candidates[0] if candidates else None
        alternatives = candidates[1:max_alternatives + 1] if len(candidates) > 1 else []

        is_confident = best_match and best_match.confidence >= self.confidence_threshold
        needs_review = not is_confident

        return MatchResult(
            raw_text=parsed.raw_text,
            parsed_quantity=parsed.quantity,
            parsed_unit=parsed.unit,
            matched_item=best_match,
            alternatives=alternatives,
            is_confident_match=is_confident,
            needs_review=needs_review,
        )


def create_matcher(items: Dict[str, Item]) -> FuzzyMatcher:
    """Create a FuzzyMatcher instance."""
    return FuzzyMatcher(items)
