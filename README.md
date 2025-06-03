# Proyek Mesin Pencari Internal Sederhana

Proyek ini adalah aplikasi web Flask sederhana yang berfungsi sebagai mesin pencari internal untuk sebuah domain web tertentu. Aplikasi ini terdiri dari tiga komponen utama: web crawler, sistem indexing, dan antarmuka pencarian, dengan kemampuan untuk mengkonfigurasi URL awal (Seed URL) melalui antarmuka admin.

## Fitur Utama

1.  **Web Crawler (Penjelajah Web)**:
    * Menggunakan algoritma Breadth-First Search (BFS) untuk menjelajahi halaman web.
    * Dimulai dari `SEED_URL` yang dikelola melalui database dan dapat diubah via panel admin. Awalnya, jika database kosong, nilai default dari `config.py` akan digunakan.
    * Membatasi penjelajahan pada domain utama (`MAIN_DOMAIN`, yang secara dinamis berasal dari `SEED_URL` saat ini) dan subdomainnya.
    * Dapat dikonfigurasi untuk batasan jumlah halaman maksimum (`MAX_CRAWL_PAGES`) dan kedalaman maksimum (`MAX_CRAWL_DEPTH`) melalui file `config.py`.
    * Mengikuti redirect HTTP.
    * Mengekstrak konten teks dari halaman HTML (mengabaikan tag script, style, dll.).
    * Menyimpan rute (path) yang diambil dari `SEED_URL` untuk mencapai setiap halaman, termasuk URL, teks link, dan judul halaman sumber.
    * Memiliki jeda antar request (sekitar 0.6 detik) untuk bersikap sopan terhadap server target.
    * Menangani berbagai jenis error HTTP dan koneksi.

2.  **Indexing (Pengindeksan)**:
    * Membuat inverted index sederhana dari konten teks yang telah di-crawl.
    * Kata kunci disimpan bersama dengan ID halaman tempat kata tersebut ditemukan.
    * Memungkinkan re-indexing semua data yang sudah di-crawl melalui panel admin.

3.  **Search Interface (Antarmuka Pencarian)**:
    * Halaman pencarian utama untuk memasukkan query.
    * Menampilkan hasil pencarian yang relevan berdasarkan query pengguna.
    * Logika pencarian menggunakan AND (semua kata kunci dalam query harus ada di halaman).
    * Hasil diurutkan berdasarkan jumlah kata kunci yang cocok dan total kemunculan kata kunci.
    * Menampilkan judul halaman, URL, dan snippet konten dengan kata kunci yang di-highlight.
    * Fitur untuk melihat rute link dari `SEED_URL` ke halaman hasil pencarian.

4.  **Admin Panel (Panel Administrasi)**:
    * Mengubah `SEED_URL` yang disimpan di database. Perubahan ini memerlukan reset database dan crawl ulang untuk diterapkan sepenuhnya.
    * Memulai/melanjutkan proses crawling dari `SEED_URL` saat ini.
    * Menghentikan proses crawling yang sedang berjalan.
    * Memulai proses re-indexing untuk semua konten yang ada di database.
    * Mereset database (menghapus semua data crawling, indeks, dan mengembalikan `SEED_URL` ke nilai default dari `config.py`).
    * Menampilkan status crawler saat ini (apakah berjalan, jumlah halaman di-crawl, URL saat ini, error terakhir).
    * Status crawler di-update secara live menggunakan JavaScript.

## Teknologi yang Digunakan

* **Python 3**: Bahasa pemrograman utama.
* **Flask**: Framework web micro untuk antarmuka dan API.
* **SQLite 3**: Database engine untuk menyimpan data halaman, konten, path, inverted index, dan konfigurasi (`SEED_URL`).
* **Beautiful Soup 4**: Library untuk parsing HTML dan mengekstrak konten teks.
* **Requests**: Library untuk membuat HTTP request saat crawling.

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
   

4.  **Konfigurasi Awal (Opsional untuk variabel selain `SEED_URL`)**:
    Edit file `config.py` untuk mengubah:
    * `SEED_URL`: URL awal default yang akan digunakan jika database baru atau `SEED_URL` belum ada di database. Setelah dijalankan pertama kali, `SEED_URL` dikelola melalui panel admin.
    * `MAX_CRAWL_PAGES`: Jumlah maksimum halaman yang akan di-crawl.
    * `MAX_CRAWL_DEPTH`: Kedalaman maksimum penjelajahan dari `SEED_URL`.
    * `MAX_SEARCH_RESULTS`: Jumlah maksimum hasil yang ditampilkan di halaman pencarian.
    * `CRAWLER_USER_AGENT`: User agent yang akan digunakan oleh crawler.

5.  **Inisialisasi Database**:
    Database (`search_engine.db`) dan tabel-tabel yang diperlukan (termasuk tabel `config_settings` untuk `SEED_URL`) akan diinisialisasi secara otomatis ketika aplikasi `app.py` dijalankan pertama kali. Anda juga bisa menjalankannya secara manual jika diperlukan:
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
    * **Ubah Seed URL**: Masukkan URL baru dan klik "Update Seed URL". Disarankan untuk mereset database dan memulai crawl baru setelahnya.
    * **Mulai Crawl**: Memulai proses crawling dari `SEED_URL` saat ini. Tombol ini akan nonaktif jika crawler sedang berjalan.
    * **Berhenti Crawl**: Mengirim permintaan untuk menghentikan crawler. Akan berhenti setelah menyelesaikan proses halaman saat ini.
    * **Re-Index Semua Data**: Menghapus indeks lama dan membuat indeks baru dari semua konten halaman yang ada di database. Tombol ini nonaktif jika crawler sedang berjalan.
    * **Reset Database**: Menghapus semua data dari tabel (`pages`, `page_content`, `paths`, `inverted_index`, `crawl_queue`, dan data `config_settings` termasuk `SEED_URL` yang akan dikembalikan ke default). **Gunakan dengan hati-hati!** Tombol ini nonaktif jika crawler sedang berjalan.
    * Status crawler (berjalan, halaman di-crawl, URL saat ini, error terakhir) akan ditampilkan dan diperbarui secara otomatis.

## Catatan

* Proses crawling dilakukan secara sinkron pada route `/admin/crawl`. Untuk website besar, ini bisa memakan waktu lama dan sebaiknya dijalankan sebagai background task dalam aplikasi produksi. Tabel `crawl_queue` ada dalam skema database namun tidak aktif digunakan oleh crawler sinkron saat ini.
* File `static/style.css` direferensikan dalam template HTML namun tidak disertakan dalam file yang diberikan. Anda mungkin perlu membuat file ini untuk styling yang sesuai.
* Logika pencarian masih sederhana (AND logic, basic relevance scoring). Bisa dikembangkan lebih lanjut dengan TF-IDF, PageRank, dll.
