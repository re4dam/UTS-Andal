# Proyek Mesin Pencari Internal Sederhana

Proyek ini adalah aplikasi web Flask sederhana yang berfungsi sebagai mesin pencari internal untuk sebuah domain web tertentu. Aplikasi ini terdiri dari tiga komponen utama: web crawler, sistem indexing, dan antarmuka pencarian.

## Fitur Utama

1.  **Web Crawler (Penjelajah Web)**:
    * Menggunakan algoritma Breadth-First Search (BFS) untuk menjelajahi halaman web.
    * Dimulai dari `SEED_URL` yang ditentukan dalam konfigurasi.
    * Membatasi penjelajahan pada domain utama (`MAIN_DOMAIN`) dan subdomainnya.
    * Dapat dikonfigurasi untuk batasan jumlah halaman maksimum (`MAX_CRAWL_PAGES`) dan kedalaman maksimum (`MAX_CRAWL_DEPTH`).
    * Mengikuti redirect HTTP.
    * Mengekstrak konten teks dari halaman HTML (mengabaikan tag script, style, dll.).
    * Menyimpan rute (path) yang diambil dari `SEED_URL` untuk mencapai setiap halaman.
    * Memiliki jeda antar request untuk bersikap sopan terhadap server target.
    * Menangani berbagai jenis error HTTP dan koneksi.

2.  **Indexing (Pengindeksan)**:
    * Membuat inverted index sederhana dari konten teks yang telah di-crawl.
    * Kata kunci disimpan bersama dengan ID halaman tempat kata tersebut ditemukan.
    * Memungkinkan re-indexing semua data yang sudah di-crawl.

3.  **Search Interface (Antarmuka Pencarian)**:
    * Halaman pencarian utama untuk memasukkan query.
    * Menampilkan hasil pencarian yang relevan berdasarkan query pengguna.
    * Logika pencarian menggunakan AND (semua kata kunci dalam query harus ada di halaman).
    * Hasil diurutkan berdasarkan jumlah kata kunci yang cocok dan total kemunculan kata kunci.
    * Menampilkan judul halaman, URL, dan snippet konten dengan kata kunci yang di-highlight.
    * Fitur untuk melihat rute link dari `SEED_URL` ke halaman hasil pencarian.

4.  **Admin Panel (Panel Administrasi)**:
    * Memulai/melanjutkan proses crawling.
    * Memulai proses re-indexing untuk semua konten yang ada di database.
    * Mereset database (menghapus semua data crawling dan indeks).
    * Menampilkan status crawler saat ini (apakah berjalan, jumlah halaman di-crawl, URL saat ini).
    * Status crawler di-update secara live menggunakan JavaScript.

## Teknologi yang Digunakan

* **Python 3**: Bahasa pemrograman utama.
* **Flask**: Framework web micro untuk antarmuka dan API.
* **SQLite 3**: Database engine untuk menyimpan data halaman, konten, path, dan inverted index.
* **Beautiful Soup 4**: Library untuk parsing HTML dan mengekstrak konten teks.
* **Requests**: Library untuk membuat HTTP request saat crawling.

## Struktur Proyek
├── app.py               # Logika utama aplikasi Flask, crawler, search
├── config.py            # Konfigurasi aplikasi (SEED_URL, batasan crawl, dll.)
├── database.py          # Skema dan inisialisasi database SQLite
├── templates/
│   ├── index.html       # Halaman utama pencarian
│   ├── results.html     # Halaman hasil pencarian
│   ├── crawl_admin.html # Halaman administrasi crawler
│   └── path_display_modal_content.html # Konten modal untuk menampilkan rute link
├── static/
│   └── style.css        # (File CSS untuk styling - perlu dibuat pengguna)
├── search_engine.db     # File database SQLite (dibuat saat aplikasi dijalankan pertama kali)
└── README.md            # File ini

## Instalasi dan Setup

1.  **Clone atau Unduh Proyek**:
    Dapatkan semua file proyek ke direktori lokal Anda.

2.  **Buat Virtual Environment (Direkomendasikan)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Untuk Linux/macOS
    # venv\Scripts\activate   # Untuk Windows
    ```

3.  **Install Dependencies**:
    Pastikan Anda memiliki `pip` terinstall. Buat file `requirements.txt` dengan konten berikut:
    ```txt
    Flask
    requests
    beautifulsoup4
    ```
    Kemudian install menggunakan pip:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi (Opsional)**:
    Edit file `config.py` untuk mengubah:
    * `SEED_URL`: URL awal untuk proses crawling (contoh: `"https://www.example.com/"`).
    * `MAX_CRAWL_PAGES`: Jumlah maksimum halaman yang akan di-crawl.
    * `MAX_CRAWL_DEPTH`: Kedalaman maksimum penjelajahan dari `SEED_URL`.
    * `MAX_SEARCH_RESULTS`: Jumlah maksimum hasil yang ditampilkan di halaman pencarian.
    * `CRAWLER_USER_AGENT`: User agent yang akan digunakan oleh crawler.

5.  **Inisialisasi Database**:
    Database akan diinisialisasi secara otomatis (tabel-tabel akan dibuat jika belum ada) ketika aplikasi `app.py` dijalankan pertama kali. Anda juga bisa menjalankannya secara manual jika diperlukan:
    ```bash
    python database.py
    ```

## Menjalankan Aplikasi

1.  Pastikan virtual environment Anda aktif.
2.  Jalankan aplikasi Flask:
    ```bash
    python app.py
    ```
3.  Aplikasi akan berjalan secara default di `http://0.0.0.0:5000/` atau `http://127.0.0.1:5000/`.

## Penggunaan

1.  **Halaman Utama & Pencarian**:
    * Buka `http://127.0.0.1:5000/` di browser Anda.
    * Masukkan kata kunci di kolom pencarian dan klik "Cari".
    * Hasil pencarian akan ditampilkan, lengkap dengan judul, URL, snippet, dan tombol "Lihat Rute Link".
    * Klik "Lihat Rute Link" untuk melihat bagaimana crawler mencapai halaman tersebut dari `SEED_URL`.

2.  **Halaman Admin**:
    * Buka `http://127.0.0.1:5000/admin/crawl`.
    * **Mulai/Lanjutkan Crawl**: Memulai proses crawling dari `SEED_URL`. Tombol ini akan nonaktif jika crawler sedang berjalan.
    * **Re-Index Semua Data**: Menghapus indeks lama dan membuat indeks baru dari semua konten halaman yang ada di database. Tombol ini nonaktif jika crawler sedang berjalan.
    * **Reset Database**: Menghapus semua data dari tabel `pages`, `page_content`, `paths`, `inverted_index`, dan `crawl_queue`. **Gunakan dengan hati-hati!** Tombol ini nonaktif jika crawler sedang berjalan.
    * Status crawler (berjalan, halaman di-crawl, URL saat ini) akan ditampilkan dan diperbarui secara otomatis.

## Catatan

* Proses crawling dilakukan secara sinkron pada route `/admin/crawl`. Untuk website besar, ini bisa memakan waktu lama dan sebaiknya dijalankan sebagai background task dalam aplikasi produksi.
* File `static/style.css` direferensikan dalam template HTML namun tidak disertakan dalam file yang diberikan. Anda mungkin perlu membuat file ini untuk styling yang sesuai.
* Logika pencarian masih sederhana (AND logic, basic relevance scoring). Bisa dikembangkan lebih lanjut dengan TF-IDF, PageRank, dll.
