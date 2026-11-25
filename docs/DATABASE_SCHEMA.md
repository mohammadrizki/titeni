# Rancangan skema PostgreSQL

| Agregat | Atribut inti dan invariant |
| --- | --- |
| Fakultas dan prodi | Fakultas tunggal melalui kunci singleton. Kode prodi unik per fakultas. Tahap pendidikan tercatat per prodi. |
| Akun dan relasi akademik | UUID akun, pengenal login unik, relasi afiliasi dan penugasan bertanggal. Enrollment menunjuk learner, prodi, kohort, periode dan konteks kurikulum. |
| Konfigurasi berversi | Nomor versi unik per induk. Simpan status, masa berlaku, pelaku dan waktu publikasi. Peta, rencana dan evaluasi menyimpan FK ke versi terbit yang mereka gunakan. |
| Kompetensi | Kode butir unik per versi. Induk, indikator, relasi perkembangan dan milestone berbagi versi yang sah. Periksa siklus pada hierarki. |
| Blueprint dan registri | Item mengacu metode, tahap dan waktu. Tabel penghubung menampung pemetaan indikator, aturan sampling, kapabilitas sumber dan verifikasi. |
| Peta dan rencana | Template merekam konteks, jumlah, sumber layak, kriteria, tenggat atau aturan jadwal, dan asal. Kunci idempotensi rencana mengikat enrollment, konteks masuk dan versi peta. Perubahan mencatat revisi dan pelaku. |
| Asesmen dan evidence | Event, partisipasi, attempt dan hasil memakai FK bertipe. Evidence menyimpan jenis, sumber, learner, waktu kejadian dan waktu akuisisi. Revisi menyimpan konteks, verifikasi, skor, artefak serta provenance. Identitas eksternal unik dalam namespace sumber. |
| Evaluasi dan adaptasi | Simpan versi standar dan aturan, snapshot revisi, waktu, versi mesin, alasan, temuan, serta hasil per dimensi. Kunci idempotensi evaluasi mengikat target, aturan dan snapshot. Kunci aktif adaptasi mengikat rencana dan identitas kebutuhan menurut kebijakan. |
| Refleksi dan coaching | Simpan versi prompt, penulis, link bukti dan revisi, grant visibilitas, log akses serta relasi coaching yang berlaku. Simpan ringkasan mesin sebagai entitas tersendiri. |
| Pembelajaran, EPA dan progresi | Versikan tujuan dan standar, tautkan intervensi ke gap serta asesmen ulang. Simpan versi EPA dan skala. Keputusan menyimpan hasil, alasan, peserta, mandat, tanggal dan dukungan historis. |
| Operasional | Audit menyimpan aktor, tindakan, target, cakupan, waktu dan alasan jika relevan. Outbox memiliki kunci pengiriman, status dan waktu retry. |

Gunakan FK bertipe, constraint keunikan dan check constraint untuk tanggal, cakupan alternatif eksklusif dan batas nilai. Layanan transaksional menegakkan relasi lintas tabel seperti kesamaan prodi. Indeks mendukung query berdasarkan prodi, enrollment, target, waktu dan status aktif. Pertahankan rujukan historis dengan proteksi penghapusan. Simpan parameter aturan terstruktur dalam JSONB dengan validasi skema.

## Skema draf kompetensi

`competencies.0001` menyimpan satu kerangka per prodi, nomor versi positif yang
unik per kerangka, dan kode butir unik per versi. Milestone menghubungkan butir
dengan tahap pada versi kurikulum tertentu. Foreign key melindungi rekaman yang
masih dirujuk. Validasi formulir dan model memeriksa cakupan induk dan tahap,
serta mencegah siklus hierarki. Versi, butir, dan milestone menyimpan pelaku dan
waktu pembuatan.

`competencies.0002` menambahkan indikator dengan kode unik per butir. Indikator
mengikuti versi kerangka dari butir induknya dan menyimpan pelaku serta waktu
pembuatan. Formulir membatasi pemilihan butir pada draf yang sedang dibuka.

`competencies.0003` menambahkan relasi perkembangan terarah antarbutir dalam satu
draf dan standar performa berversi. Relasi menolak rujukan ke diri sendiri dan
duplikasi pasangan asal-tujuan dengan deskripsi yang sama. Kode standar unik per
butir dan nomor versi positif unik per standar. Setiap versi menyimpan deskripsi,
pelaku, dan waktu pembuatan. Nomor versi dialokasikan dengan kunci transaksi draf.

## Skema draf blueprint asesmen

`assessments.0001` menyimpan satu blueprint logis per prodi dengan nomor versi
positif yang unik per blueprint. Setiap draf merujuk satu versi kerangka
kompetensi, dan tiap komponen merujuk satu tahap kurikulum. Kode komponen unik
per draf. Pemetaan menggunakan pasangan komponen dan butir yang unik. Formulir
memeriksa cakupan prodi serta versi kerangka yang dirujuk.
