# Titeni

Portofolio reflektif dan pengembangan kompetensi. Lihat [instruksi induk](docs/MASTER_INSTRUCTION.md) dan [roadmap](docs/IMPLEMENTATION_ROADMAP.md).

## Pengembangan lokal

Gunakan uv, CPython 3.13 atau 3.14, dan PostgreSQL. Jalankan `uv sync --locked`, salin `.env.example` ke `.env`, lalu isi `DJANGO_SECRET_KEY` dengan nilai acak dan `DATABASE_URL` dengan kredensial lokal. Periksa konfigurasi dengan `uv run python manage.py check`.

Setelah migrasi lokal disetujui dan diterapkan, jalankan `uv run python manage.py runserver`. Halaman masuk tersedia di `/masuk/`. Akses `/administrasi/` memakai izin `accounts.access_system_workspace`. Daftar akun memerlukan izin tambahan `accounts.view_user`.

Untuk pengujian, arahkan `DATABASE_URL` ke PostgreSQL khusus tes dengan izin membuat basis data tes, lalu jalankan `uv run pytest`. Untuk membangun ulang CSS, gunakan `npm ci` dan `npm run css:build`.
