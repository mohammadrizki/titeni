# Integrasi

Adaptor berversi menerima data asesmen, LMS, logbook, akademik dan repositori bukti. Normalisasi dengan skema input tervalidasi. Identitas sumber dan ID eksternal stabil membentuk kunci idempotensi. Bedakan retry payload identik dari perubahan untuk ID yang sama dan rekam revisi hanya melalui alur koreksi yang sah.

Impor CSV menyediakan validasi, pratinjau, laporan kegagalan per baris, komit yang dapat diaudit dan rekonsiliasi. Cakupan akun integrasi mengikat prodi dan sumber yang diizinkan. Simpan provenance, waktu dan versi adaptor. Gunakan aturan interpretasi akademik terbit untuk pemetaan skor eksternal. Terapkan retry outbox dan audit tanpa menyertakan payload sensitif dalam log teknis.

## CSV bukti percobaan

Impor manual memakai UTF-8 dengan pemisah koma dan empat kolom berurutan.

```csv
kode_sumber,kode_jenis_bukti,referensi,konteks
observasi,catatan,SIM-2026-01,Rawat jalan
```

Percobaan dan prodi ditentukan dari halaman yang membuka impor. Sumber dan
jenis harus tertaut pada komponen percobaan. Referensi wajib dan konteks
opsional. Berkas dibatasi 100 baris data dan 128 KiB. Unggahan hanya membawa
referensi tanpa informasi pasien.

Pengguna memeriksa pratinjau sebelum mengonfirmasi. Konfirmasi memeriksa ulang
baris dan tautan sumber. Konflik pada satu baris menghentikan seluruh batch.
Kunci kembar memakai percobaan, tautan sumber dan referensi. Jika konteks identik,
entri dilewati. Konteks berbeda dilaporkan untuk ditangani melalui alur koreksi.

Batch yang membuat rekaman menyimpan SHA-256 berkas, pelaku, waktu, dan jumlah
baris yang diimpor atau dilewati. Setiap rekaman baru mengacu ke batch dan
menunggu verifikasi. Berkas mentah tidak disimpan oleh aplikasi.
