import re
from typing import Optional, Tuple

# Stoplist for common words that might be accidentally caught
STOPLIST = {
    "open", "closed", "while", "priority", "operation", "installed",
    "operates", "before", "from", "rating", "type", "casing", "housing",
    "cracked", "service", "shutdown", "running", "idle", "active"
}

# Mapping of tag prefixes to Equipment Types
PREFIX_TO_TYPE = {
    "P": "Pump",
    "PU": "Pump",
    "PX": "Pump",
    "V": "Valve",
    "PSV": "Valve",
    "FV": "Valve",
    "XV": "Valve",
    "CV": "Valve",
    "TIC": "Sensor",
    "LT": "Sensor",
    "PT": "Sensor",
    "TT": "Sensor",
    "FT": "Sensor",
    "C": "Compressor",
    "K": "Compressor",
    "HX": "Heat Exchanger",
    "E": "Heat Exchanger",
    "TK": "Tank",
    "T": "Tank",
    "M": "Motor",
    "B": "Boiler",
}

# Regex for ISA-style tags: 1-4 letters, optional hyphen, 2-5 digits, optional 1-2 letter suffix
# Examples: P-301, PX-202, PSV-209, V-204A, TIC-101, P301
TAG_PATTERN = r'\b([A-Z]{1,4})-?(\d{2,5})([A-Z]{1,2})?\b'

# Pre-compile regexes for performance
TAG_REGEX = re.compile(TAG_PATTERN, re.IGNORECASE)

# Basic pattern for capitalized words or numbers (for locations/people)
# E.g., 'Arun', 'Zone 5'
CAPITALIZED_OR_DIGIT_PATTERN = r'\b([A-Z][a-z]+|[A-Z]+|\d+)\b'
CAPITALIZED_OR_DIGIT_REGEX = re.compile(CAPITALIZED_OR_DIGIT_PATTERN)

def validate_and_parse_tag(text: str) -> Optional[Tuple[str, str, float]]:
    """
    Validates if a text contains a valid equipment tag.
    Returns (tag, equipment_type, confidence) or None if invalid.
    """
    # Extract the tag part from text if it contains other words like "Pump P-301"
    match = TAG_REGEX.search(text)
    if not match:
        return None
    
    # Reconstruct the tag in a standard format (e.g., P-301)
    prefix = match.group(1).upper()
    number = match.group(2)
    suffix = (match.group(3) or "").upper()
    
    # Standardize to always have a hyphen
    tag = f"{prefix}-{number}{suffix}"
    
    if prefix in PREFIX_TO_TYPE:
        eq_type = PREFIX_TO_TYPE[prefix]
        confidence = 0.95
    else:
        eq_type = "Equipment"
        confidence = 0.60
        
    return tag, eq_type, confidence

def is_valid_location_or_person(text: str) -> bool:
    """
    Validates if a location or person name is plausible.
    Must not be in stoplist, and must contain a digit or a capitalized word.
    """
    if not text:
        return False
        
    # Check stoplist on individual lowercase words
    words = text.lower().split()
    if any(word in STOPLIST for word in words):
        return False
        
    # Check if it has a digit or capitalized proper noun
    return bool(CAPITALIZED_OR_DIGIT_REGEX.search(text))
