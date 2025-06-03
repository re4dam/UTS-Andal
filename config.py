import os
from urllib.parse import urlparse

# URL Awal untuk Penelusuran (Ini akan menjadi nilai default jika DB kosong)
SEED_URL = os.environ.get("SEED_URL", "")

# Variabel ini akan diisi dinamis di app.py setelah SEED_URL dimuat dari DB
MAIN_DOMAIN = None
ALLOWED_DOMAINS = []

# Batasan untuk crawler
MAX_CRAWL_PAGES = int(
    os.environ.get("MAX_CRAWL_PAGES", 500)
)  # Batasi jumlah halaman yang di-crawl
MAX_CRAWL_DEPTH = int(os.environ.get("MAX_CRAWL_DEPTH", 5))  # Batasi kedalaman crawl

# Batasan untuk hasil pencarian
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", 50))

# Database
DATABASE_NAME = "search_engine.db"

# User-Agent untuk crawler
CRAWLER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"