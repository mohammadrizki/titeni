# e-Logbook PPDS-1 Ilmu Kesehatan Anak FKIK Unram: paket serah terima situs contoh (v3)

Disiapkan untuk admin JEJAK. Pemilik: dr. Putu Aditya Wiguna, M.Sc., Sp.A (Koordinator Tahap Junior PPDS-1 IKA FKIK Unram).
Tanggal: 19 November 2026.

## Isi paket

| Berkas | Kegunaan |
| --- | --- |
| `elogbook-demo-v3.html` | Situs contoh yang bisa diklik. Satu berkas, buka langsung di browser. |
| `spesifikasi.md` | Ringkasan keputusan, peran, menu, aturan logika, dan hal yang masih kosong. |
| `contoh-ekspor-residen.json` | Contoh ekspor data satu residen (skema usulan `elogbook-ppds1-ika-unram/0.1`). |
| `contoh-impor-nilai.csv`, `contoh-impor-residen.csv` | Contoh berkas untuk fitur impor CSV. |

## Cara membuka

1. Klik dua kali `elogbook-demo-v3.html`. Chrome, Edge, atau Firefox versi baru sudah cukup. Tidak perlu server atau instalasi.
2. Pilih **Login**, lalu pakai salah satu **akun demo** di bawah formulir:
   - Residen: dr. Ayu Lestari (Semester III), dr. Indah Permatasari (Semester II), dr. Lalu Rizki Maulana (Semester I)
   - Staf: DPJP dan DPA, Koordinator Tahap Junior (contoh akun dengan beberapa peran), Admin program studi
3. Perubahan yang Anda buat tersimpan di browser Anda sendiri. Menu **Atur ulang data contoh** mengembalikan data awal.

Gambar QR persetujuan dimuat dari cdnjs.cloudflare.com. Tanpa internet, kotak QR tampil sebagai placeholder.

## Yang perlu diketahui sebelum dipakai

- **Ini prototipe tampilan, bukan kode produksi.** Semua logika berjalan di browser dengan JavaScript biasa dan data disimpan di localStorage. Tidak ada server, basis data, autentikasi, maupun enkripsi sungguhan. Untuk dimasukkan ke JEJAK, layar dan aturannya perlu dibangun ulang di stack JEJAK. Prototipe ini berfungsi sebagai spesifikasi yang bisa diklik.
- **Semua data fiktif.** Nama residen dan staf (kecuali nama koordinator), pasien, nomor RM, nilai, target, dan EPA adalah rekaan.
- **Beberapa isi masih contoh dan menunggu keputusan prodi.** Daftar lengkapnya ada di `spesifikasi.md`, bagian "Masih contoh atau kosong".

## Perbedaan utama dengan logbook sarjana

| Aspek | e-Logbook PPDS-1 IKA |
| --- | --- |
| Peserta | Residen PPDS (peran baru, mirip mahasiswa) |
| Unit rotasi | Rotasi Infeksi Junior, segmen Non Infeksi Junior, dan blok bergilir Semester III (4 blok x 6 minggu, 4 kelompok) |
| Tingkat kompetensi | Empat Tingkat Kemampuan kolegium IKA: T1 Knows, T2 Knows how, T3 Shows how, T4 Does. Wajib, dicatat di setiap entri pasien dan tindakan. |
| EPA | Skala entrustment 1 sampai 5, dicatat bersama Mini-CEX, DOPS, atau CBD. Modul tambahan, belum diputuskan prodi. |
| Aturan hitung | Tindakan dihitung bila entri sudah diverifikasi DPJP dan tingkatnya mencapai target tingkat junior. Keterampilan tanpa target tetap tercatat, tetapi tidak masuk persentase capaian. |
| Target | Ditetapkan koordinator lewat Form Penetapan Target (volume kasus aktual, target, alasan) |
| Penilaian semester | WPBA 35, ujian tulis 20, ujian kasus/OSCE 20, sikap 15, logbook 10 |
| Pembimbing | DPJP (verifikasi dan WPBA) dan DPA (bimbingan akademik). Satu staf bisa memegang keduanya. |
| Fitur khusus | Laporan perundungan dan beban kerja secara anonim; indikator mutu; peta EPA per angkatan |

## Entitas data (ringkas)

- **Residen**: nim, nama, angkatan, semester, kelompok (Semester III), dpa
- **Staf**: nip, nama, divisi, peran (bisa lebih dari satu: dpjp, koordinator, admin)
- **Jadwal rotasi**: residen, label, mata kuliah, divisi, semester, mulai, selesai, blok, periode
- **Entri logbook**: residen, tanggal, jenis (pasien, tindakan, jaga), rotasi, divisi, unit, dpjp verifikator, status (menunggu, terverifikasi, revisi), komentar, tanggal verifikasi
  - pasien dan tindakan: inisial dan no. RM (terenkripsi), usia, jenis kelamin, diagnosis ICD-10, tingkat T1 sampai T4, status persetujuan (QR atau rekam medis), tindakan (untuk jenis tindakan)
  - jaga: shift, jam, jumlah pasien
- **Keterampilan**: nama, divisi, target tingkat (T1 sampai T4, tanda * bila ditetapkan prodi), target jumlah, volume aktual, alasan
- **Target kasus per divisi**: target jumlah, volume aktual, alasan
- **Asesmen**: jenis (Mini-CEX, DOPS, CBD, Mini-PAT, OSCE), tanggal, penilai, semester, kasus, nilai, EPA, level entrustment, umpan balik (baik, perlu diperbaiki), status
- **Bimbingan DPA**: residen, dpa, tanggal, topik, catatan, tindak lanjut
- **Laporan keselamatan**: kategori, isi, anonim, status, tindak lanjut (identitas pelapor disimpan terpisah)
- **Log akses identitas**: waktu, pengguna, peran, entri, alasan
- **Periode akademik dan event asesmen**

Contoh bentuk lengkapnya ada di `contoh-ekspor-residen.json`.

## Usulan integrasi dengan JEJAK

Tiga jalur, dari yang paling sederhana:

1. **Ekspor dan impor berkala** (JSON atau CSV per periode). Tidak perlu kerja sama teknis.
2. **API dengan token**, misalnya `GET /api/v1/residen/{nim}/logbook?periode=...`
3. **Akun institusi bersama (SSO Unram)**

Atau: e-logbook PPDS dibangun sebagai **modul baru di dalam JEJAK**, dengan peran "Residen PPDS" dan kolom tambahan untuk Tingkat Kemampuan kolegium.

## Pertanyaan untuk admin JEJAK

1. Apakah JEJAK bisa menampung peran Residen PPDS dan program studi spesialis, atau lebih baik sistem terpisah yang saling bertukar data?
2. Apakah ada API atau format impor/ekspor resmi yang bisa kami ikuti?
3. Bisakah kolom Tingkat Kemampuan T1 sampai T4 ditambahkan di samping EPA 1 sampai 5?
4. Di mana data disimpan, dan siapa yang bisa membuka identitas pasien? (Prodi meminta mode privasi bawaan dan log akses.)
5. Apakah SSO Unram sudah tersedia untuk JEJAK?
