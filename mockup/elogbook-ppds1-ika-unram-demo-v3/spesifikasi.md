# e-Logbook PPDS-1 Ilmu Kesehatan Anak FKIK Unram: spesifikasi

Status: situs contoh versi 3 (19 Nov 2026), berkas `elogbook-demo-v3.html` dalam paket ini.
- v1: tata letak mengikuti https://pediatriugm.com/ (e-logbook IKA FK-KMK UGM)
- v2: struktur program dari "Handover Terpadu PPDS-1 IKA FKIK Unram Tahap Junior"
- v3: pola dari JEJAK Essential (https://dashboard.mohammadrizki.com/) dan lapisan integrasi

## Keputusan teknis
- Rencana awal: situs mandiri di server Unram. Opsi baru: dibangun sebagai modul di JEJAK atau saling bertukar data dengan JEJAK.
- Struktur publik mengikuti UGM: Beranda, Tentang kami, Pengumuman, Kontak, Login (Residen, Staf/SDM, Daftar akun, Unduh).
- Rancangan integrasi dengan platform lain (JEJAK, SIAKAD Unram, dasbor fakultas) belum disepakati dengan pengelola platform mana pun.

## Konteks program
- PPDS-1 IKA FKIK Unram, program baru. Kekhasan: Kesehatan Anak Kepulauan.
- Wahana utama RSUD Provinsi NTB; semua rotasi junior di sana; RS mitra mulai Semester VIII.
- Total 125 SKS; tahap junior (Semester I sampai III) 41 SKS; Semester I 17 SKS.
- Semester I: orientasi 2 minggu + Infeksi Junior ± 22 minggu. Semester II: Non Infeksi Junior ± 24 minggu. Semester III: 4 blok x 6 minggu, 4 kelompok, KM1 sampai KM4 @2 SKS + Penerapan Akademik Junior 4 SKS.
- Tingkat kemampuan: 4 tingkat kolegium (T1 Knows, T2 Knows how, T3 Shows how, T4 Does). T3* = ditetapkan prodi (KM3 Imunisasi).
- Target jumlah kasus/tindakan kosong sampai ditetapkan lewat Form Penetapan Target (Lampiran 5 Buku Panduan).
- Penilaian: WPBA (Mini-CEX, DOPS, CBD, Mini-PAT), OSCE, logbook/portofolio, bimbingan DPA. Bobot: WPBA 35, ujian tulis 20, ujian kasus/OSCE 20, sikap 15, logbook 10. Skala A >= 80, B+ >= 75, B >= 70.

## Fitur versi 3
- Satu akun bisa memegang beberapa peran; ganti peran dari header atau sidebar.
- Pendaftaran akun mandiri, admin menyetujui dan memberi peran.
- EPA entrustment skala 1 sampai 5 dicatat bersama Mini-CEX/DOPS/CBD (6 EPA contoh). Perlu keputusan prodi: tingkat kompetensi resmi tetap T1 sampai T4 kolegium; EPA hanya lapisan tambahan.
- Peta EPA per angkatan dengan persentil.
- Mode privasi aktif bawaan: inisial dan no. RM disamarkan. Break glass: buka 15 menit dengan alasan, tercatat di log akses identitas.
- Persetujuan pasien/wali lewat QR atau tertulis di rekam medis.
- Jurnal umpan balik residen; portofolio longitudinal.
- Admin: periode akademik, event asesmen, impor CSV dengan pemetaan kolom dan pratinjau.
- Halaman Integrasi: tiga jalur, pemetaan istilah, contoh ekspor JSON. Identitas pasien hanya diekspor sebagai token terenkripsi.

## Peran dan menu
- Residen: Beranda, Isi logbook, Riwayat, Capaian kompetensi, Penilaian WPBA dan EPA, Jurnal umpan balik, Bimbingan DPA, Jadwal rotasi, Portofolio dan nilai, Lapor.
- DPJP/DPA: Beranda, Verifikasi logbook, Permintaan WPBA, Residen bimbingan DPA, Semua residen.
- Koordinator Tahap Junior: Beranda, Penetapan target, Rekapitulasi capaian, Peta EPA, Blok bergilir, Pemantauan verifikasi, Indikator mutu, Laporan keselamatan.
- Admin: Beranda, Akun dan peran, Data residen, Data staf, Periode dan event asesmen, Impor CSV, Jadwal rotasi, Log akses identitas, Integrasi, Pengumuman.

## Aturan logika
- Hanya entri terverifikasi yang dihitung.
- Tindakan dihitung bila tingkat yang dicatat >= target tingkat junior.
- Keterampilan tanpa target tetap tercatat, tidak masuk persentase capaian.
- Entri tertunda > 7 hari kuning, > 14 hari merah.
- Pasien: inisial + no. RM, terenkripsi di server, disamarkan di tampilan. Diagnosis ICD-10.
- EPA terkini = level tertinggi dari tiga penilaian terakhir untuk EPA itu.
- Laporan anonim: identitas disimpan terpisah, hanya tim yang ditunjuk KPS.

## Masih contoh atau kosong (menunggu data prodi)
- Daftar keterampilan (18 contoh dari ± 80) dan target tingkatnya.
- Pemetaan blok A sampai D ke divisi; nama KM1, KM2, KM4.
- Divisi 5 segmen Non Infeksi Junior.
- Enam aturan tata kelola blok bergilir.
- SKS Semester II.
- Daftar EPA dan level harapan akhir junior (bila modul EPA dipakai).
- Nama pengelola, visi, volume kasus dan target, ambang indikator mutu.
