# Titeni

Portofolio reflektif dan pengembangan kompetensi.

## Pengembangan lokal

1. Gunakan uv, CPython 3.13 atau 3.14, dan PostgreSQL.
2. Jalankan `uv sync --locked`, salin `.env.example` ke `.env`, lalu isi `DJANGO_SECRET_KEY` dengan nilai acak dan `DATABASE_URL` dengan kredensial lokal.
3. Periksa konfigurasi dengan `uv run python manage.py check`.
4. Setelah migrasi lokal disetujui dan diterapkan, jalankan `uv run python manage.py runserver`.
5. Halaman masuk tersedia di `/masuk/`.
6. Akses `/administrasi/` memakai izin `accounts.access_system_workspace`.
7. Daftar akun memerlukan izin tambahan `accounts.view_user`.
8. Untuk pengujian, arahkan `DATABASE_URL` ke PostgreSQL khusus tes dengan izin membuat basis data tes, lalu jalankan `uv run pytest`.
9. Untuk membangun ulang CSS, gunakan `npm ci` dan `npm run css:build`.
