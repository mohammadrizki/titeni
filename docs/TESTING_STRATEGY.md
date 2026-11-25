# Strategi pengujian

Gunakan pytest dan pytest-django dengan PostgreSQL sungguhan untuk constraint, transaksi, locking, JSONB dan migrasi. Isolasi basis data pengujian dari basis data pengembangan. Jalankan Django system checks, pemeriksaan drift migrasi, Ruff dan mypy pada CPython 3.13 dan 3.14 saat runtime tersedia.

| Skenario | Pemeriksaan penerimaan |
| --- | --- |
| A, B | Baseline otomatis memakai versi efektif. Asal hibrida tercatat dan aturan ekuivalensi mencegah penghitungan ganda. |
| C, D, Q | Gap menghasilkan kebutuhan terarah. Bukti baru dapat mengurangi kebutuhan. Batas memicu eskalasi. |
| E, F, G | Gap tertutup menghentikan kebutuhan tambahan. Gap terbuka mengarah ke intervensi. Asesmen ulang kembali ke evaluasi. |
| H, I, O | Riwayat refleksi dan coaching, atribusi ringkasan, serta pembatasan akses pada UI, API, ekspor dan unduhan. |
| J, K | Perubahan versi atau invalidasi memicu interpretasi baru sambil mempertahankan histori. |
| L, M | Gunakan transaksi terpisah untuk skenario konkurensi. Ulangi impor dan pastikan satu bukti dihitung. |
| N | Uji akun lintas prodi, relasi kedaluwarsa, pencabutan izin dan delegasi tanpa mandat. |
| P | Uji program tanpa EPA, program dengan observasi, dan penetapan entrustment oleh manusia berwenang. |
| R, S | Bukti yang hilang dan persyaratan lengkap tetap mengikuti aturan kecukupan serta standar sebelum temuan performa. |

Uji UI administrasi kustom lewat alur biasa, termasuk navigasi keyboard dan tambah/hapus baris. Gunakan data demonstrasi sintetis. Pada Fase 0 pemeriksaan mencakup dokumen dan koneksi PostgreSQL lokal.
