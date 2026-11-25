# Keputusan arsitektur

| Keputusan | Status dan dasar |
| --- | --- |
| Administrasi kustom di shell Titeni | Ditetapkan pengguna. Pakai autentikasi Django, views, formulir dan kebijakan domain. Django Admin dikeluarkan dari konfigurasi paket dan URL. |
| Satu fakultas dan banyak prodi | Ditetapkan instruksi induk. Prodi memiliki konfigurasi berversi serta batas akses sendiri. |
| Identitas `accounts.User` | UUID tetap menjadi identitas internal. Login lokal memakai email unik tanpa membedakan kapitalisasi. Nama pengguna dipakai untuk tampilan. Afiliasi, enrollment dan izin memiliki siklus hidup tersendiri. |
| Monolit modular dan PostgreSQL | Ditetapkan instruksi induk. Batas modul dan pemisahan evaluasi, adaptasi serta keputusan dijabarkan dalam rancangan Fase 0. |
| Pola formulir berulang | Ditetapkan pengguna. Tabel mengutamakan tombol **Tambah baris** dan kolom **Aksi** paling kanan. |

Struktur direktori mengikuti pembagian modul yang ditetapkan pengguna dan dicatat dalam [arsitektur](ARCHITECTURE.md). Rancangan model dan pemecahan inkrement dalam Fase 0 diajukan untuk peninjauan. Keputusan akademik yang membutuhkan persetujuan tercatat dalam [pertanyaan terbuka](OPEN_QUESTIONS.md).

Integrasi SSO mendatang perlu mengikat identitas penyedia melalui pasangan penerbit dan pengenal subjek yang stabil. Kebijakan verifikasi email dan penautan akun ditetapkan saat penyedia SSO dipilih.
