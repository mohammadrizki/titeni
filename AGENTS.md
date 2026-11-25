# Panduan kontribusi Titeni

- Ikuti urutan dalam [instruksi induk](docs/MASTER_INSTRUCTION.md). Baca [roadmap](docs/IMPLEMENTATION_ROADMAP.md), [log pengembangan](docs/DEVELOPMENT_LOG.md), dan dokumen domain terkait sebelum mengubah arsitektur atau aturan pendidikan. Gunakan templat, aset, dan mockup yang tersedia sebagai referensi tampilan.
- Bangun administrasi akademik dan sistem sebagai antarmuka kustom yang menyatu dengan aplikasi. Django Admin dikeluarkan dari konfigurasi.
- Utamakan tabel untuk isian berulang dengan struktur yang sama. Sediakan tombol **Tambah baris** dan tempatkan kolom **Aksi** di paling kanan.
- Gunakan monolit modular Django, PostgreSQL, dan uv. Pertahankan kompatibilitas CPython 3.13 dan 3.14 serta desain identitas `AUTH_USER_MODEL = "accounts.User"`.
- Ajukan persetujuan sebelum mengubah aturan bisnis, memulai fase fitur, menerapkan migrasi awal, atau membuat superuser.
