"""Shared date resolver: converts natural language dates to ISO 8601.

Handles: exact dates, month-year, year only, decades, approximate dates,
BCE dates, date ranges, and seasons.
"""

import re

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9,
    'oct': 10, 'nov': 11, 'dec': 12,
}

SEASONS = {
    'spring': (3, 5),
    'summer': (6, 8),
    'autumn': (9, 11),
    'fall': (9, 11),
    'winter': (12, 2),
    'early': (1, 4),
    'late': (9, 12),
}

# Patterns ordered from most specific to least specific
PATTERNS = [
    # "March 15, 1917" or "15 March 1917"
    (r'(\d{1,2})\s+(%MONTHS%)\s+(\d{3,4})', 'dmy'),
    (r'(%MONTHS%)\s+(\d{1,2}),?\s+(\d{3,4})', 'mdy'),
    # "March 1917"
    (r'(%MONTHS%)\s+(\d{3,4})', 'my'),
    # "c. 1500" / "circa 1500" / "around 1500" / "approximately 1500"
    (r'(?:c\.?|circa|around|approximately|about|roughly)\s*(\d{3,4})', 'approx'),
    # "1480s" / "the 1480s"
    (r'(?:the\s+)?(\d{3})0s', 'decade'),
    # "44 BC" / "332 BCE" / "44 B.C."
    (r'(\d{1,4})\s*(?:BC|BCE|B\.C\.E?\.?)', 'bce'),
    # "spring 1498" / "summer of 1917"
    (r'(%SEASONS%)\s+(?:of\s+)?(\d{3,4})', 'season'),
    # "1495-1497" or "1495 - 1497" or "1495 to 1497"
    (r'(\d{3,4})\s*[-–—to]+\s*(\d{3,4})', 'range'),
    # Plain year "1917"
    (r'\b(\d{3,4})\b', 'year'),
]

# Compile patterns with month/season substitution
_MONTH_RE = '|'.join(MONTHS.keys())
_SEASON_RE = '|'.join(SEASONS.keys())
COMPILED_PATTERNS = []
for pat, ptype in PATTERNS:
    pat = pat.replace('%MONTHS%', _MONTH_RE)
    pat = pat.replace('%SEASONS%', _SEASON_RE)
    COMPILED_PATTERNS.append((re.compile(pat, re.IGNORECASE), ptype))


def _format_year(year):
    """Format year as ISO string, handling BCE."""
    if year < 0:
        return f"{year:05d}"
    return f"{year:04d}"


def resolve_date(text):
    """Parse a date string into structured components.

    Returns: (date_start, date_end, precision, display) or (None, None, None, None)
    All dates are ISO 8601 format (YYYY-MM-DD). BCE years are negative.
    """
    if not text or not text.strip():
        return None, None, None, None

    text = text.strip()

    for pattern, ptype in COMPILED_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        if ptype == 'dmy':
            day, month_str, year_str = match.group(1), match.group(2), match.group(3)
            month = MONTHS[month_str.lower()]
            year = int(year_str)
            ds = f"{_format_year(year)}-{month:02d}-{int(day):02d}"
            return ds, ds, 'day', f"{month_str.capitalize()} {day}, {year}"

        elif ptype == 'mdy':
            month_str, day, year_str = match.group(1), match.group(2), match.group(3)
            month = MONTHS[month_str.lower()]
            year = int(year_str)
            ds = f"{_format_year(year)}-{month:02d}-{int(day):02d}"
            return ds, ds, 'day', f"{month_str.capitalize()} {day}, {year}"

        elif ptype == 'my':
            month_str, year_str = match.group(1), match.group(2)
            month = MONTHS[month_str.lower()]
            year = int(year_str)
            # Month range
            if month == 12:
                end_month, end_year = 12, year
            else:
                end_month, end_year = month, year
            ds = f"{_format_year(year)}-{month:02d}-01"
            de = f"{_format_year(end_year)}-{end_month:02d}-28"
            return ds, de, 'month', f"{month_str.capitalize()} {year}"

        elif ptype == 'approx':
            year = int(match.group(1))
            ds = f"{_format_year(year)}-01-01"
            de = f"{_format_year(year)}-12-31"
            return ds, de, 'approximate', f"c. {year}"

        elif ptype == 'decade':
            decade_start = int(match.group(1)) * 10
            ds = f"{_format_year(decade_start)}-01-01"
            de = f"{_format_year(decade_start + 9)}-12-31"
            return ds, de, 'decade', f"{decade_start}s"

        elif ptype == 'bce':
            year = -int(match.group(1))
            ds = f"{_format_year(year)}-01-01"
            de = f"{_format_year(year)}-12-31"
            return ds, de, 'year', f"{abs(year)} BC"

        elif ptype == 'season':
            season_str, year_str = match.group(1), match.group(2)
            year = int(year_str)
            start_month, end_month = SEASONS[season_str.lower()]
            if start_month > end_month:
                # Winter spans year boundary
                ds = f"{_format_year(year)}-{start_month:02d}-01"
                de = f"{_format_year(year + 1)}-{end_month:02d}-28"
            else:
                ds = f"{_format_year(year)}-{start_month:02d}-01"
                de = f"{_format_year(year)}-{end_month:02d}-28"
            return ds, de, 'season', f"{season_str.capitalize()} {year}"

        elif ptype == 'range':
            year1, year2 = int(match.group(1)), int(match.group(2))
            # Handle 2-digit end year: "1495-97" -> 1495-1497
            if year2 < 100 and year1 > 100:
                year2 = (year1 // 100) * 100 + year2
            ds = f"{_format_year(year1)}-01-01"
            de = f"{_format_year(year2)}-12-31"
            return ds, de, 'year', f"{year1} - {year2}"

        elif ptype == 'year':
            year = int(match.group(1))
            # Skip implausible years
            if year < 100 or year > 2100:
                continue
            ds = f"{_format_year(year)}-01-01"
            de = f"{_format_year(year)}-12-31"
            return ds, de, 'year', str(year)

    return None, None, None, None
