"""Scrape biographical data from Wikipedia."""

import re

import requests
from bs4 import BeautifulSoup


def fetch_page(person_name=None, url=None):
    """Fetch and parse a Wikipedia page. Returns dict with extracted data and body text."""
    if url is None:
        slug = person_name.replace(' ', '_')
        url = f'https://en.wikipedia.org/wiki/{slug}'

    resp = requests.get(url, headers={'User-Agent': 'WhoWasWhereWhen/1.0'}, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Extract title
    title_el = soup.find('h1', {'id': 'firstHeading'})
    name = title_el.get_text().strip() if title_el else person_name or 'Unknown'

    # Extract first paragraph as description
    content_div = soup.find('div', {'id': 'mw-content-text'})
    description = ''
    if content_div:
        for p in content_div.find_all('p', recursive=True):
            text = p.get_text().strip()
            if len(text) > 50:
                # Remove citation brackets like [1] [2]
                description = re.sub(r'\[\d+\]', '', text).strip()
                break

    # Extract body text for AI processing
    body_text = ''
    if content_div:
        paragraphs = []
        for p in content_div.find_all('p'):
            text = p.get_text().strip()
            if text:
                paragraphs.append(re.sub(r'\[\d+\]', '', text))
        body_text = '\n\n'.join(paragraphs)

    # Try to extract birth/death from infobox
    birth_date = None
    death_date = None
    infobox = soup.find('table', {'class': 'infobox'})
    if infobox:
        for row in infobox.find_all('tr'):
            header = row.find('th')
            if header:
                header_text = header.get_text().strip().lower()
                value = row.find('td')
                if value:
                    if 'born' in header_text:
                        birth_date = value.get_text().strip()
                    elif 'died' in header_text:
                        death_date = value.get_text().strip()

    # Extract image URL from infobox
    image_url = None
    if infobox:
        img = infobox.find('img')
        if img and img.get('src'):
            image_url = 'https:' + img['src'] if img['src'].startswith('//') else img['src']

    return {
        'name': name,
        'description': description,
        'wikipedia_url': url,
        'image_url': image_url,
        'birth_date_raw': birth_date,
        'death_date_raw': death_date,
        'body_text': body_text,
    }
