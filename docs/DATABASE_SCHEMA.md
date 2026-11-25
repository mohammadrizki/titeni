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

`assessments.0003` menyimpan rancangan sampling per komponen. Konteks unik per
komponen dan jumlah minimum observasi harus positif. Rancangan mengikuti versi
blueprint dari komponennya dan menyimpan pelaku serta waktu pembuatan.

## Registri sumber bukti

`evidence.0001` menyimpan sumber dan jenis bukti dengan kode unik per prodi.
Kapabilitas menyimpan pasangan unik sumber dan jenis. Pemetaan kompetensi
menyimpan pasangan unik sumber dan butir pada suatu versi kerangka.
Aplikasi memeriksa kesamaan prodi ketika memilih rujukan. Keempat tabel
menyimpan pelaku dan waktu pembuatan serta melindungi rekaman yang dirujuk.

`assessments.0004` menghubungkan komponen blueprint ke kapabilitas registri
(pasangan sumber dan jenis bukti). Pasangan komponen dan kapabilitas unik.
Kapabilitas yang masih dirujuk dilindungi dari penghapusan dan perubahan jenis
melalui administrasi. Formulir memeriksa cakupan prodi dan versi blueprint.

`evidence.0002` menyimpan satu peta logis per prodi dan versi bernomor positif
unik per peta. Versi mengacu ke draf blueprint dan menyimpan salinan tampilan
komponen, cakupan, milestone dan sampling sebagai JSON. Rujukan blueprint
dilindungi, dan perubahan konfigurasi sumber tidak menulis ulang salinan lama.

`evidence.0003` menambahkan persyaratan manual pada draf blueprint. Kode unik
per draf dan jumlah minimum positif. Rujukan butir mengikuti versi kerangka
blueprint. Kapabilitas harus berada pada prodi pemilik blueprint. Peta yang
disimpan berikutnya membawa salinan persyaratan manual pada saat penyimpanan.

`evidence.0004` menambahkan draf rencana dengan rujukan terlindungi ke
pendaftaran dan versi peta artefak. Pasangan pendaftaran dan versi peta unik.
Draf membaca salinan yang tersimpan pada versi peta untuk menjaga riwayat
tanpa menduplikasi isinya.

`evidence.0005` menyimpan satu penerbitan per versi peta dan satu versi
terbit per tanggal efektif dalam satu prodi. Penerbitan menyimpan pilihan
persyaratan beserta asal, tenggat, dan penanggung jawab. Baseline satu per
pendaftaran dan merujuk penerbitan asal melalui foreign key terlindungi.

## Pencatatan pelaksanaan dan asal-usul bukti

`assessments.0005` menambahkan pelaksanaan, partisipasi, dan percobaan.
Partisipasi unik per kombinasi pelaksanaan dan pendaftaran. Nomor percobaan
positif dan unik per partisipasi. `evidence.0006` mencatat pengenal bukti
dengan pasangan sumber dan jenis dari komponen pelaksanaan. Rekaman unik
per percobaan, tautan sumber, dan pengenal. Foreign key melindungi catatan
yang dirujuk. Pencatatan menyimpan pelaku dan waktu.

`evidence.0007` menyimpan satu keputusan verifikasi per bukti. Status dibatasi
pada Terverifikasi atau Ditolak, dengan alasan wajib, pelaku, dan waktu.
Catatan tanpa keputusan ditampilkan sebagai Belum diputuskan.

`evidence.0008` menambahkan nomor versi bukti, rujukan unik ke versi sebelumnya,
dan alasan koreksi. Semua catatan lama tetap menjadi versi pertama. Pembatalan
menyimpan alasan, pelaku dan waktu dalam rekaman satu-ke-satu. Kelayakan awal
untuk rekonsiliasi berasal dari versi terbaru dengan keputusan Terverifikasi
tanpa rekaman pembatalan.

`evidence.0009` menambahkan konteks pengamatan pada versi bukti serta penempatan
hasil tinjauan. Satu versi bukti mempunyai maksimum satu penempatan. Penempatan
merujuk baseline dan nomor persyaratan dalam pilihan publikasi yang tersimpan
serta mencatat alasan, pelaku, dan waktu. Hitungan memakai bukti yang masih layak.

`evidence.0010` menambahkan batch impor CSV dan rujukan opsional dari bukti
ke batch asalnya. Batch menyimpan percobaan, digest berkas, jumlah baris baru
dan baris yang dilewati, pelaku, dan waktu. Bukti manual dan koreksi tetap
dapat dicatat tanpa batch.

`evidence.0011` menyimpan metadata lampiran PDF. Lampiran merujuk ke versi
bukti asal dengan foreign key terlindungi, dan hash unik dalam versi yang
sama. Penyimpanan berkas menggunakan pengenal acak di direktori privat
`EVIDENCE_ARTIFACT_ROOT`. Direktori ini harus berada di luar direktori
yang dilayani web atau dikumpulkan sebagai aset statis.
