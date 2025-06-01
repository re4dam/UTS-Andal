import requests
from bs4 import BeautifulSoup, Comment
from flask import Flask, render_template, request, redirect, url_for, jsonify
from collections import deque
import urllib.parse
import re
import sqlite3
import json
import time
from datetime import datetime

# Impor konfigurasi dan fungsi database
from config import (
    SEED_URL,
    MAIN_DOMAIN,
    MAX_CRAWL_PAGES,
    MAX_CRAWL_DEPTH,
    MAX_SEARCH_RESULTS,
    CRAWLER_USER_AGENT,
)
import database  # Menggunakan file database.py yang sudah dibuat

app = Flask(__name__)
app.config.from_object("config")  # Memuat konfigurasi dari config.py


# --- Helper Functions ---
def get_domain(url):
    try:
        return urllib.parse.urlparse(url).netloc
    except Exception:
        return None


def is_allowed_domain(url, base_domain_to_check_against):
    # base_domain_to_check_against adalah domain utama dari SEED_URL
    domain = get_domain(url)
    if domain:
        return domain == base_domain_to_check_against or domain.endswith(
            "." + base_domain_to_check_against
        )
    return False


def normalize_url(url, base_url_for_relative):
    """Membersihkan dan mengubah URL relatif menjadi absolut."""
    url = url.strip().split("#")[0]  # Hapus fragment dan spasi
    parsed_url = urllib.parse.urlparse(url)
    # Coba tambahkan https jika skema tidak ada dan base_url adalah https
    if not parsed_url.scheme:
        if urllib.parse.urlparse(base_url_for_relative).scheme == "https":
            # Cek jika URL sudah dimulai dengan // (protokol relatif)
            if url.startswith("//"):
                url = "https:" + url
            else:  # URL Path relatif
                url = urllib.parse.urljoin(base_url_for_relative, url)
        else:  # Default ke http jika base tidak https atau skema juga tidak ada
            if url.startswith("//"):
                url = "http:" + url  # atau ambil skema dari base_url_for_relative
            else:
                url = urllib.parse.urljoin(base_url_for_relative, url)

    # Jika skema masih kosong setelah join (misal base_url_for_relative adalah path tanpa skema)
    # ini seharusnya tidak terjadi jika base_url_for_relative valid
    if not urllib.parse.urlparse(url).scheme and (
        url.startswith("/") or not url.startswith("http")
    ):
        # Coba tambahkan skema dari SEED_URL
        seed_scheme = urllib.parse.urlparse(SEED_URL).scheme
        url = urllib.parse.urljoin(SEED_URL, url)

    return url


def extract_text_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for script_or_style in soup(
        ["script", "style", "meta", "link", "header", "footer", "nav", "aside", "form"]
    ):
        script_or_style.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


# --- Crawler Logic ---
CRAWLER_STATUS = {
    "running": False,
    "pages_crawled": 0,
    "current_url": "",
    "last_error": None,
}


def bfs_crawler(start_url, max_pages=MAX_CRAWL_PAGES, max_depth=MAX_CRAWL_DEPTH):
    global CRAWLER_STATUS
    if CRAWLER_STATUS["running"]:
        print("Crawler already running.")
        return

    CRAWLER_STATUS.update(
        {"running": True, "pages_crawled": 0, "current_url": "", "last_error": None}
    )
    print(f"Starting BFS crawl from: {start_url}")

    base_domain_of_seed = get_domain(start_url)
    if not base_domain_of_seed:
        CRAWLER_STATUS.update(
            {
                "running": False,
                "last_error": f"Invalid start URL or cannot determine base domain: {start_url}",
            }
        )
        print(CRAWLER_STATUS["last_error"])
        return

    # Antrian: (url_to_fetch, current_depth, json_string_of_path_taken_to_get_to_url_to_fetch)
    # path_taken_to_get_to_url_to_fetch adalah list of dicts: [{'url': 'prev_url', 'text': 'link_text', 'title': 'prev_page_title'}, ...]
    queue = deque([(start_url, 0, json.dumps([]))])
    visited_urls = (
        set()
    )  # Set untuk menyimpan URL yang kontennya *sudah diproses* atau sedang diproses

    conn = database.get_db_connection()

    # Inisialisasi page_id untuk start_url jika belum ada (untuk path awal)
    cursor_init = conn.cursor()
    cursor_init.execute("SELECT id FROM pages WHERE url = ?", (start_url,))
    seed_page_row = cursor_init.fetchone()
    if not seed_page_row:
        try:
            cursor_init.execute(
                "INSERT INTO pages (url, title) VALUES (?, ?)",
                (start_url, "Seed URL (Initial)"),
            )
            # page_id_start_url = cursor_init.lastrowid # Tidak langsung digunakan di sini
            cursor_init.execute(
                "INSERT OR IGNORE INTO paths (page_id, path_data) VALUES ((SELECT id FROM pages WHERE url=?), ?)",
                (start_url, json.dumps([])),
            )
            conn.commit()
        except (
            sqlite3.IntegrityError
        ):  # Mungkin ada race condition jika dijalankan paralel, atau sudah ada
            print(f"Seed URL {start_url} likely already inserted or race condition.")
        except Exception as e_init:
            print(f"Error initializing seed URL {start_url} in DB: {e_init}")
    cursor_init.close()

    while queue and CRAWLER_STATUS["pages_crawled"] < max_pages:
        current_url_from_queue, depth, path_to_current_url_from_queue_json = (
            queue.popleft()
        )
        path_leading_to_current_url_from_queue = json.loads(
            path_to_current_url_from_queue_json
        )

        CRAWLER_STATUS["current_url"] = f"Attempting: {current_url_from_queue}"

        # 1. Periksa apakah URL asli dari antrian (sebelum redirect) sudah dikunjungi (kontennya diproses)
        # Ini lebih sebagai optimasi agar tidak melakukan request jika sumbernya sudah diproses
        # Namun, pengecekan utama adalah pada final_url_after_redirect
        if current_url_from_queue in visited_urls:
            # print(f"Skipping already processed or queued-for-processing source URL: {current_url_from_queue}")
            continue

        if depth > max_depth:
            print(
                f"Max depth {max_depth} reached for {current_url_from_queue}. Skipping."
            )
            continue

        # Tandai URL sumber sebagai "pernah dilihat/diantrikan" untuk menghindari loop antrian sederhana.
        # visited_urls utama akan diisi oleh final_url_after_redirect.
        # Ini membantu jika A -> B, dan C juga -> A (agar A tidak di-request ulang dari C)
        # visited_urls.add(current_url_from_queue) # Komentari dulu, fokus pada final_url

        response = None  # Inisialisasi response
        final_url_after_redirect = None

        try:
            headers = {
                "User-Agent": CRAWLER_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": path_leading_to_current_url_from_queue[-1]["url"]
                if path_leading_to_current_url_from_queue
                else start_url,
                "DNT": "1",  # Do Not Track
                "Upgrade-Insecure-Requests": "1",  # Minta HTTPS jika tersedia
            }
            print(f"Requesting (Depth {depth}): {current_url_from_queue}")
            response = requests.get(
                current_url_from_queue,
                headers=headers,
                timeout=12,
                allow_redirects=True,
            )
            final_url_after_redirect = response.url  # URL aktual setelah semua redirect

            # 2. Periksa domain dari final_url_after_redirect
            if not is_allowed_domain(final_url_after_redirect, base_domain_of_seed):
                print(
                    f"Skipping (domain not allowed): {current_url_from_queue} -> {final_url_after_redirect}"
                )
                CRAWLER_STATUS["last_error"] = (
                    f"Domain not allowed: {final_url_after_redirect}"
                )
                visited_urls.add(
                    current_url_from_queue
                )  # Tandai URL asli agar tidak dicoba lagi dari sumber lain
                if final_url_after_redirect != current_url_from_queue:
                    visited_urls.add(final_url_after_redirect)  # Tandai juga final URL
                continue

            # 3. Periksa apakah final_url_after_redirect (URL konten aktual) sudah diproses
            if final_url_after_redirect in visited_urls:
                print(
                    f"Skipping already processed final URL: {final_url_after_redirect} (Original from queue: {current_url_from_queue})"
                )
                visited_urls.add(
                    current_url_from_queue
                )  # Pastikan URL asli juga ditandai jika berbeda
                continue

            visited_urls.add(
                final_url_after_redirect
            )  # Ini URL yang kontennya akan kita proses
            if (
                current_url_from_queue != final_url_after_redirect
            ):  # Jika redirect terjadi, tandai juga sumbernya.
                visited_urls.add(current_url_from_queue)

            response.raise_for_status()  # Lemparkan error untuk status 4xx/5xx PADA FINAL URL

            if "text/html" not in response.headers.get("Content-Type", "").lower():
                print(f"Skipping non-HTML content: {final_url_after_redirect}")
                CRAWLER_STATUS["last_error"] = f"Non-HTML: {final_url_after_redirect}"
                continue

            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")
            page_title_tag = soup.find("title")
            page_title_of_final_url = (
                page_title_tag.string.strip()
                if page_title_tag and page_title_tag.string
                else "No Title"
            )
            text_content = extract_text_from_html(html_content)

            # Tentukan path yang benar ke konten final_url_after_redirect
            path_to_final_url_content_items = list(
                path_leading_to_current_url_from_queue
            )  # Salin
            if current_url_from_queue != final_url_after_redirect:
                # Tambahkan langkah redirect ke path
                path_to_final_url_content_items.append(
                    {
                        "url": current_url_from_queue,  # URL yang menyebabkan redirect
                        "text": "[Redirected]",
                        "title": "Original URL before redirect",  # Atau ambil title dari current_url jika pernah di-crawl
                    }
                )
            path_to_final_url_content_json = json.dumps(path_to_final_url_content_items)

            # Simpan/Update data halaman untuk final_url_after_redirect
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM pages WHERE url = ?", (final_url_after_redirect,)
            )
            page_row = cursor.fetchone()
            page_id_of_final_url = None

            if page_row:
                page_id_of_final_url = page_row["id"]
                cursor.execute(
                    "UPDATE pages SET title = ?, last_crawled_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (page_title_of_final_url, page_id_of_final_url),
                )
            else:
                cursor.execute(
                    "INSERT INTO pages (url, title) VALUES (?, ?)",
                    (final_url_after_redirect, page_title_of_final_url),
                )
                page_id_of_final_url = cursor.lastrowid

            if page_id_of_final_url is None:  # Seharusnya tidak terjadi
                print(
                    f"Error: Could not get or create page_id for {final_url_after_redirect}"
                )
                conn.rollback()
                continue

            cursor.execute(
                "INSERT OR REPLACE INTO page_content (page_id, text_content) VALUES (?, ?)",
                (page_id_of_final_url, text_content),
            )
            cursor.execute(
                "INSERT OR REPLACE INTO paths (page_id, path_data) VALUES (?, ?)",
                (page_id_of_final_url, path_to_final_url_content_json),
            )
            conn.commit()  # Commit setelah semua data halaman terkait berhasil disimpan

            CRAWLER_STATUS["pages_crawled"] += 1
            CRAWLER_STATUS["last_error"] = None  # Reset error jika berhasil

            # Indexing (sederhana)
            index_page_content(
                page_id_of_final_url, text_content, cursor
            )  # Gunakan cursor yang sama
            conn.commit()  # Commit setelah indexing

            # Temukan semua link di halaman (dari final_url_after_redirect)
            # Path untuk anak-anak dari final_url_after_redirect:
            base_path_for_children_items = (
                path_to_final_url_content_items
                + [
                    {
                        "url": final_url_after_redirect,
                        "text": page_title_of_final_url,  # Atau link text spesifik jika ini adalah 'self-referential step'
                        "title": page_title_of_final_url,
                    }
                ]
            )

            for link_tag in soup.find_all("a", href=True):
                raw_href = link_tag["href"]
                link_text = link_tag.get_text(strip=True) or raw_href

                # Normalisasi URL berdasarkan final_url_after_redirect
                next_url_to_queue = normalize_url(raw_href, final_url_after_redirect)

                if (
                    next_url_to_queue
                    and next_url_to_queue not in visited_urls
                    and is_allowed_domain(next_url_to_queue, base_domain_of_seed)
                ):
                    if (
                        CRAWLER_STATUS["pages_crawled"] + len(queue) < max_pages * 1.5
                    ):  # Heuristik
                        path_for_this_new_link_json = json.dumps(
                            base_path_for_children_items
                        )  # Sebenarnya path ke parent (final_url)
                        # Koreksi: path_for_this_new_link_json adalah path KE final_url_after_redirect
                        # path yang dikirim ke antrian adalah path MENUJU next_url_to_queue

                        # Path yang disimpan ke antrian adalah: path_yang_membawa_ke_final_url + langkah_dari_final_url_ke_next_url
                        # `base_path_for_children_items` sudah benar sebagai path yang akan dikirim ke anak
                        # Karena `base_path_for_children_items` adalah `path_to_final_url_content_items` + info `final_url_after_redirect` itu sendiri.

                        # path_to_queue_for_next_url = base_path_for_children_items # ini adalah path menuju parentnya (final_url)
                        # Sebenarnya, path_to_final_url_content_items adalah path menuju final_url
                        # Jadi path untuk anak adalah path_to_final_url_content_items + {final_url, link_text, title_final_url}

                        current_path_for_child_items = list(
                            path_to_final_url_content_items
                        )  # Path yang membawa ke final_url
                        current_path_for_child_items.append(
                            {  # Tambahkan langkah dari final_url
                                "url": final_url_after_redirect,
                                "text": link_text,  # Teks link yang diklik di halaman final_url
                                "title": page_title_of_final_url,
                            }
                        )
                        queue.append(
                            (
                                next_url_to_queue,
                                depth + 1,
                                json.dumps(current_path_for_child_items),
                            )
                        )
            cursor.close()

        except requests.exceptions.HTTPError as e:
            CRAWLER_STATUS["last_error"] = (
                f"HTTP error for {current_url_from_queue} (Final URL: {final_url_after_redirect or 'N/A'}): {e}"
            )
            print(CRAWLER_STATUS["last_error"])
            # Tandai kedua URL sebagai 'visited' agar tidak dicoba ulang jika gagal permanen
            visited_urls.add(current_url_from_queue)
            if final_url_after_redirect:
                visited_urls.add(final_url_after_redirect)
        except requests.exceptions.SSLError as e:
            CRAWLER_STATUS["last_error"] = (
                f"SSL error for {current_url_from_queue}: {e}"
            )
            print(CRAWLER_STATUS["last_error"])
            visited_urls.add(current_url_from_queue)
        except requests.exceptions.ConnectionError as e:
            CRAWLER_STATUS["last_error"] = (
                f"Connection error for {current_url_from_queue}: {e}"
            )
            print(CRAWLER_STATUS["last_error"])
            visited_urls.add(current_url_from_queue)
        except requests.exceptions.Timeout as e:
            CRAWLER_STATUS["last_error"] = f"Timeout for {current_url_from_queue}: {e}"
            print(CRAWLER_STATUS["last_error"])
            visited_urls.add(current_url_from_queue)
        except requests.exceptions.RequestException as e:
            CRAWLER_STATUS["last_error"] = (
                f"Request error for {current_url_from_queue}: {e}"
            )
            print(CRAWLER_STATUS["last_error"])
            visited_urls.add(current_url_from_queue)
        except Exception as e:
            CRAWLER_STATUS["last_error"] = (
                f"General error processing {current_url_from_queue}: {e}"
            )
            print(CRAWLER_STATUS["last_error"])
            visited_urls.add(current_url_from_queue)
            if conn:
                conn.rollback()  # Rollback jika ada error umum saat operasi DB
        finally:
            time.sleep(0.6)  # Sedikit tingkatkan jeda

    conn.close()
    CRAWLER_STATUS.update({"running": False, "current_url": "Crawl Finished"})
    print(
        f"Crawl finished. Pages crawled: {CRAWLER_STATUS['pages_crawled']}. Last error: {CRAWLER_STATUS['last_error']}"
    )


# --- Indexing Logic --- (Sama seperti sebelumnya)
def index_page_content(page_id, text_content, db_cursor):
    # Gunakan db_cursor yang sudah ada (dari bfs_crawler) untuk efisiensi
    words = set(re.findall(r"\b\w{3,}\b", text_content.lower()))
    for word in words:
        try:
            db_cursor.execute(
                "INSERT OR IGNORE INTO inverted_index (keyword, page_id) VALUES (?, ?)",
                (word, page_id),
            )
        except Exception as e:
            print(f"Error indexing word '{word}' for page_id {page_id}: {e}")
            # Tidak perlu conn.commit() di sini, akan di-commit oleh pemanggil


def reindex_all_data():
    conn = database.get_db_connection()
    cursor = conn.cursor()
    print("Clearing old index...")
    cursor.execute("DELETE FROM inverted_index")
    conn.commit()
    print("Re-indexing all pages...")
    cursor.execute(
        "SELECT p.id, pc.text_content FROM pages p JOIN page_content pc ON p.id = pc.page_id"
    )
    rows = cursor.fetchall()
    count = 0
    for row in rows:
        if row["text_content"]:  # Pastikan ada konten
            index_page_content(row["id"], row["text_content"], cursor)
            count += 1
            if count % 100 == 0:
                conn.commit()  # Commit secara berkala
                print(f"Indexed {count} pages...")
    conn.commit()  # Commit sisa
    conn.close()
    print(f"Re-indexing complete. Total {count} pages re-indexed.")


# --- Search Logic --- (Sama seperti sebelumnya, tapi pastikan snippet handling baik)
def search_keywords(query_string):
    keywords = [
        kw.strip().lower() for kw in query_string.split() if len(kw.strip()) >= 3
    ]
    if not keywords:
        return []

    conn = database.get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(keywords))

    # Query untuk mencari halaman yang mengandung SEMUA kata kunci (AND logic)
    # dan menghitung jumlah kemunculan kata kunci sebagai 'relevance'
    # (Catatan: ini bukan TF-IDF, hanya hitungan sederhana)
    sql_query = f"""
        SELECT p.id, p.url, p.title, COUNT(DISTINCT ii.keyword) as matched_keywords, SUM(1) as total_keyword_occurrences
        FROM pages p
        JOIN inverted_index ii ON p.id = ii.page_id
        WHERE ii.keyword IN ({placeholders})
        GROUP BY p.id, p.url, p.title
        HAVING matched_keywords = ? 
        ORDER BY matched_keywords DESC, total_keyword_occurrences DESC, p.title ASC
        LIMIT ?
    """
    query_params = keywords + [len(keywords), MAX_SEARCH_RESULTS]

    cursor.execute(sql_query, query_params)
    db_results = cursor.fetchall()

    formatted_results = []
    for row in db_results:
        snippet = ""
        # Ambil konten untuk snippet
        cursor.execute(
            "SELECT text_content FROM page_content WHERE page_id = ?", (row["id"],)
        )
        content_row = cursor.fetchone()
        if content_row and content_row["text_content"]:
            content_text_lower = content_row["text_content"].lower()
            first_kw_to_highlight = keywords[
                0
            ]  # Ambil keyword pertama untuk fokus snippet

            best_pos = -1
            # Cari posisi terbaik untuk snippet (sekitar salah satu keyword)
            for kw_idx, kw in enumerate(keywords):
                try:
                    pos = content_text_lower.index(kw)
                    if (
                        kw_idx == 0 or best_pos == -1
                    ):  # Prioritaskan keyword pertama atau jika belum ada
                        best_pos = pos
                    # Bisa ditambahkan logika untuk memilih posisi keyword yg paling relevan/jarang
                except ValueError:
                    continue  # Keyword tidak ada (seharusnya tidak terjadi jika HAVING COUNT = len(keywords))

            if best_pos != -1:
                start = max(0, best_pos - 75)
                end = min(
                    len(content_row["text_content"]), best_pos + len(keywords[0]) + 75
                )  # Sesuaikan panjang snippet
                snippet_text = content_row["text_content"][start:end]

                # Highlight keywords dalam snippet (sederhana)
                highlighted_snippet = snippet_text
                for kw_highlight in keywords:
                    # Gunakan regex untuk case-insensitive highlighting dan whole word
                    pattern = re.compile(
                        r"\b(" + re.escape(kw_highlight) + r")\b", re.IGNORECASE
                    )
                    highlighted_snippet = pattern.sub(
                        r"<strong>\1</strong>", highlighted_snippet
                    )
                snippet = (
                    ("..." if start > 0 else "")
                    + highlighted_snippet
                    + ("..." if end < len(content_row["text_content"]) else "")
                )
            else:  # Fallback jika keyword tidak ditemukan di konten (aneh)
                snippet = content_row["text_content"][:150] + "..."

        formatted_results.append(
            {
                "id": row["id"],
                "url": row["url"],
                "title": row["title"] if row["title"] else row["url"],
                "snippet": snippet,
            }
        )

    conn.close()
    return formatted_results


# --- Flask Routes --- (Sebagian besar sama, penyesuaian kecil mungkin pada get_path_route)
@app.route("/", methods=["GET", "POST"])
def index_page():
    if request.method == "POST":
        query = request.form.get("query")
        if query:
            return redirect(url_for("search_results_page", query=query))
    return render_template("index.html")


@app.route("/search")
def search_results_page():
    query = request.args.get("query", "")
    results = []
    if query:
        results = search_keywords(query)
    return render_template(
        "results.html", query=query, results=results, max_results=MAX_SEARCH_RESULTS
    )


@app.route("/get_path/<int:page_id>")
def get_path_route(page_id):
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Ambil path_data dan URL halaman target
    cursor.execute(
        """
        SELECT p.url as target_url, p.title as target_title, pa.path_data 
        FROM pages p 
        LEFT JOIN paths pa ON p.id = pa.page_id 
        WHERE p.id = ?
    """,
        (page_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Page not found in database."}), 404

    target_url = row["target_url"]
    target_title = row["target_title"] or "Halaman Tujuan"  # Fallback title

    path_list_from_db = []
    if row["path_data"]:
        try:
            path_list_from_db = json.loads(row["path_data"])
            if not isinstance(path_list_from_db, list) or not all(
                isinstance(item, dict) and "url" in item and "text" in item
                for item in path_list_from_db
                if item
            ):  # Cek format
                raise ValueError("Invalid path data format")
        except (json.JSONDecodeError, ValueError) as e:
            print(
                f"Error decoding path_data for page_id {page_id}: {e}. Path data: {row['path_data']}"
            )
            return jsonify({"error": f"Invalid path data in database: {e}"}), 500

    # Bangun path yang akan ditampilkan
    # Path dimulai dari SEED_URL
    display_path = [
        {"url": SEED_URL, "text": "Halaman Awal (Seed)", "title": "Seed URL"}
    ]

    # Tambahkan langkah-langkah dari path_list_from_db
    for step in path_list_from_db:
        # Pastikan step valid, jika tidak, log dan lewati
        if isinstance(step, dict) and "url" in step and "text" in step:
            # 'title' dalam step adalah judul halaman DARI mana link itu berasal
            display_path.append(
                {
                    "url": step["url"],
                    "text": step["text"] or step["url"],  # Teks link yang diklik
                    "title": step.get(
                        "title", step["url"]
                    ),  # Judul halaman tempat link berada
                }
            )
        else:
            print(f"Skipping invalid step in path_data for page_id {page_id}: {step}")

    # Langkah terakhir adalah halaman target itu sendiri, jika belum ada di ujung path
    # path_list_from_db adalah path *menuju* target_url.
    # display_path seharusnya sudah mencakup langkah terakhir yang mengarah ke target_url,
    # namun target_url itu sendiri sebagai "node tujuan" perlu ditampilkan.
    # Jika display_path masih kosong setelah SEED_URL (artinya target_url adalah SEED_URL itu sendiri)
    if target_url == SEED_URL and len(display_path) == 1:
        pass  # Sudah benar, display_path hanya berisi Seed URL
    elif not display_path or (
        display_path[-1]["url"] != target_url
        and display_path[-1]["url"] != path_list_from_db[-1]["url"]
        if path_list_from_db
        else True
    ):
        # Jika path terakhir bukan URL target (misal path_list_from_db kosong karena target adalah seed atau anak langsung seed)
        # atau jika path terakhir dari DB tidak menunjuk ke target_url (seharusnya tidak terjadi jika path benar)
        # Tambahkan target URL sebagai tujuan akhir eksplisit jika belum.
        # Ini lebih untuk kasus jika target_url adalah SEED_URL atau anak langsungnya
        # di mana path_list_from_db bisa kosong atau hanya 1 elemen.

        # Kondisi yang lebih baik: jika path_list_from_db kosong dan target bukan SEED, tambahkan.
        # Jika path_list_from_db tidak kosong, step terakhir di path_list_from_db adalah link *ke* target_url.
        # Jadi kita tidak perlu menambahkan target_url secara eksplisit lagi ke display_path
        # KECUALI untuk memperjelas bahwa itu adalah halaman tujuan akhir.

        # Jika path_list_from_db ada, elemen terakhirnya adalah link *yang diklik* di halaman *sebelum* target.
        # URL di step terakhir path_list_from_db adalah URL halaman *sebelum* target.
        # Jadi, kita selalu perlu menambahkan info halaman target itu sendiri.

        # Untuk memastikan, hapus logika rumit di atas dan sederhanakan:
        # display_path sudah berisi langkah-langkah *menuju* target_url.
        # Kita hanya perlu pastikan path_display_modal_content.html bisa menampilkannya dengan benar.
        # Template HTML akan menampilkan URL target dari argumennya.
        pass

    return render_template(
        "path_display_modal_content.html",
        path=display_path,
        seed_url=SEED_URL,
        target_url=target_url,
        target_title=target_title,
    )


@app.route("/admin/crawl", methods=["GET", "POST"])
def admin_crawl_page():
    global CRAWLER_STATUS
    message = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "start_crawl" and not CRAWLER_STATUS["running"]:
            try:
                # Untuk produksi, jalankan di background thread:
                # import threading
                # thread = threading.Thread(target=bfs_crawler, args=(SEED_URL, MAX_CRAWL_PAGES, MAX_CRAWL_DEPTH))
                # thread.daemon = True # Agar thread berhenti jika main app berhenti
                # thread.start()
                # message = "Crawler started in background. Check server logs for progress."
                # Untuk sekarang, jalankan sinkron untuk debugging lebih mudah:
                bfs_crawler(SEED_URL, MAX_CRAWL_PAGES, MAX_CRAWL_DEPTH)
                message = f"Crawling process completed. Pages crawled: {CRAWLER_STATUS['pages_crawled']}."
                if CRAWLER_STATUS["last_error"]:
                    message += f" Last error: {CRAWLER_STATUS['last_error']}"

            except Exception as e:
                message = f"Error starting crawl: {e}"
                CRAWLER_STATUS["running"] = False
        elif action == "start_crawl" and CRAWLER_STATUS["running"]:
            message = "Crawler is already running."
        elif action == "reindex":
            try:
                reindex_all_data()
                message = "Re-indexing process completed."
            except Exception as e:
                message = f"Error starting re-indexing: {e}"
        elif action == "reset_db":
            try:
                if CRAWLER_STATUS["running"]:
                    message = "Cannot reset database while crawler is running."
                else:
                    conn_reset = database.get_db_connection()
                    cursor_reset = conn_reset.cursor()
                    tables_to_clear = [
                        "inverted_index",
                        "paths",
                        "page_content",
                        "pages",
                        "crawl_queue",
                    ]
                    for table in tables_to_clear:
                        cursor_reset.execute(f"DELETE FROM {table}")
                        try:  # Reset sequence untuk autoincrement (SQLite specific)
                            cursor_reset.execute(
                                f"DELETE FROM sqlite_sequence WHERE name='{table}'"
                            )
                        except sqlite3.OperationalError:
                            pass  # Abaikan jika tabel sequence tidak ada
                    conn_reset.commit()
                    database.init_db()  # Buat ulang tabel jika terhapus (init_db harus CREATE IF NOT EXISTS)
                    conn_reset.close()
                    CRAWLER_STATUS.update(
                        {
                            "running": False,
                            "pages_crawled": 0,
                            "current_url": "",
                            "last_error": None,
                        }
                    )
                    message = "Database has been reset."
            except Exception as e:
                message = f"Error resetting database: {e}"

    return render_template(
        "crawl_admin.html",
        crawler_status=CRAWLER_STATUS,
        message=message,
        seed_url=SEED_URL,
    )


@app.route("/admin/crawl_status")
def get_crawl_status_route():  # Ubah nama fungsi agar tidak konflik
    global CRAWLER_STATUS
    return jsonify(CRAWLER_STATUS)


if __name__ == "__main__":
    database.init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)  # Port bisa disesuaikan
