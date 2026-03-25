import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE = os.path.join(BASE_DIR, 'data', 'wwww.db')
GEOCACHE_FILE = os.path.join(BASE_DIR, 'data', 'geocache.json')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
