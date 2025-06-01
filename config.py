import os
from urllib.parse import urlparse

# URL Awal untuk Penelusuran
SEED_URL = os.environ.get("SEED_URL", "https://unj.ac.id/")  # Contoh, bisa diganti

# Ekstrak domain utama untuk membatasi penelusuran
parsed_seed_url = urlparse(SEED_URL)
MAIN_DOMAIN = parsed_seed_url.netloc

# Daftar domain yang diizinkan (termasuk subdomain dari SEED_URL)
# Ini akan diisi secara dinamis atau memerlukan logika lebih lanjut jika subdomain sangat banyak
# Untuk sekarang, kita akan fokus pada domain utama dan subdomain langsung.
ALLOWED_DOMAINS = [MAIN_DOMAIN]  # Akan diperluas oleh logika crawler

# Batasan untuk crawler
MAX_CRAWL_PAGES = int(
    os.environ.get("MAX_CRAWL_PAGES", 500)
)  # Batasi jumlah halaman yang di-crawl
MAX_CRAWL_DEPTH = int(os.environ.get("MAX_CRAWL_DEPTH", 5))  # Batasi kedalaman crawl

# Batasan untuk hasil pencarian
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", 10))

# Database
DATABASE_NAME = "search_engine.db"

# User-Agent untuk crawler
# CRAWLER_USER_AGENT = (
#     "InternalSearchBot/1.0 (+http://example.com/botinfo)"  # Ganti dengan info relevan
# )

CRAWLER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
