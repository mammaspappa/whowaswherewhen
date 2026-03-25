"""Extract structured location data from biographical text using Claude API."""

import json
import os

import anthropic


def extract_locations(person_name, body_text, birth_info='', death_info=''):
    """Use Claude to extract locations from biographical text. Returns list of location dicts."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("  Warning: ANTHROPIC_API_KEY not set, skipping AI extraction")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Given the following biographical text about {person_name} ({birth_info} - {death_info}), extract every location where this person is known or believed to have been.

For each location, provide:
- place_name: The name of the place (city, region, country as appropriate)
- date_start: ISO-8601 date (YYYY-MM-DD) for the start of their time there
- date_end: ISO-8601 date (YYYY-MM-DD) for the end of their time there
- date_precision: one of "day", "month", "season", "year", "decade", "approximate"
- date_display: human-readable date string
- description: brief description of what they were doing there (1-2 sentences)
- confidence: one of "certain", "probable", "possible", "speculative"

Return ONLY a JSON array sorted chronologically. Use negative years for BCE dates (e.g., -0043 for 44 BC). Be conservative with confidence levels. If dates are uncertain, use wider ranges and lower precision.

Biographical text:
{body_text[:8000]}"""

    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=4096,
            messages=[{'role': 'user', 'content': prompt}],
        )

        text = response.content[0].text.strip()

        # Extract JSON from response (may be wrapped in markdown code block)
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        locations = json.loads(text)
        if not isinstance(locations, list):
            print("  Warning: AI response was not a JSON array")
            return []

        return locations

    except json.JSONDecodeError as e:
        print(f"  Error parsing AI response as JSON: {e}")
        return []
    except Exception as e:
        print(f"  Error calling Claude API: {e}")
        return []
