# Log pengembangan

Implementasi terdahulu diarsipkan saat pengembangan dimulai ulang dari Fase 0. Instruksi induk menjadi acuan. Templat Django, aset, mockup, dan pratinjau dipertahankan sebagai referensi tampilan.

Basis data PostgreSQL lokal `titenana` dibuat ulang dalam keadaan kosong setelah pencadangan.

## Fase 0

Menginventarisasi workspace dan arsip implementasi, memetakan kesenjangan serta menyiapkan rancangan modul, model logis, ERD, proses, aturan, otorisasi, alur evaluasi, strategi pengujian dan backlog. PostgreSQL lokal 18.6 terverifikasi memiliki nol tabel pada skema publik. Runtime dan migrasi aplikasi baru belum tersedia. Templat dan aset dipakai sebagai referensi untuk administrasi kustom dan alur pengguna.

Menyelaraskan struktur direktori dengan pembagian modul yang diberikan pengguna. Blueprint dan event asesmen berada di `apps/assessments/`, identitas dan otorisasi di `apps/accounts/`, serta evaluasi dan perencanaan adaptif di `apps/adaptive/`.

## Fase 1a · Fondasi akun dan administrasi

Menambahkan Django 5.2, konfigurasi PostgreSQL berbasis lingkungan, dependensi uv, dan akun UUID `accounts.User`. Halaman masuk, keluar, dan administrasi sistem menggunakan shell Titeni. Direktori akun bersifat baca saja. Izin ruang administrasi dan izin melihat akun diperiksa terpisah. Administrasi akademik dan penugasan prodi mengikuti inkrement struktur akademik berikutnya.

Django system checks, pemeriksaan drift migrasi, Ruff, mypy, serta dua tes integrasi lulus pada CPython 3.13.18 dan 3.14.10 dengan PostgreSQL sementara. Migrasi awal disiapkan untuk peninjauan. Basis data pengembangan `titenana` tetap memiliki nol tabel publik.

Setelah disetujui, migrasi awal diterapkan pada PostgreSQL lokal `titenana`. Pemeriksaan migrasi menunjukkan semua migrasi terpasang. Server lokal mengembalikan HTTP 200 untuk beranda, halaman masuk, dan CSS. Permintaan administrasi tanpa sesi diarahkan ke halaman masuk.

## Fase 1b · Fondasi konfigurasi akademik

Menambahkan profil fakultas tunggal, registrasi prodi menurut jenjang, periode akademik per prodi, dan penugasan konfigurasi bertanggal di administrasi kustom. PostgreSQL menegakkan profil tunggal, kode periode unik per prodi dan urutan tanggal. Pemberian dan pencabutan penugasan mencatat pelaku dan waktu. Pengelola hanya dapat melihat dan mengisi periode untuk prodi dengan penugasan aktif. Formulir berulang memakai baris tabel dengan kolom **Aksi** di kanan.

Empat tes, Django system checks, pemeriksaan drift migrasi, Ruff dan mypy lulus pada CPython 3.13.18 dan 3.14.10 dengan PostgreSQL sementara. Migrasi baru disiapkan untuk peninjauan. Kurikulum, kohort, enrollment, kerangka kompetensi, milestone dan publikasi versi menyusul.

Migrasi `academics.0001` dan `accounts.0002` diterapkan pada PostgreSQL lokal `titenana`. Pemeriksaan migrasi lulus. Profil fakultas, registrasi prodi, dan penugasan konfigurasi terverifikasi merespons setelah masuk sebagai administrator lokal.

Penyimpanan profil fakultas kini menampilkan konfirmasi sekali setelah halaman dimuat ulang. Tes integrasi memastikan konfirmasi tampil bersama nama yang tersimpan.

Tabel registrasi prodi menyediakan ikon tambah serta aksi sunting, hapus, dan simpan dengan tooltip. Sunting dan hapus memerlukan izin tindakan masing-masing. Hapus memerlukan konfirmasi dan menjaga prodi yang dirujuk oleh data akademik atau penugasan.

## Fase 1b · Draf kurikulum

Pengelola dengan penugasan prodi aktif dapat membuat kurikulum, menambah versi draf kosong, dan mencatat tahap per versi. Kode kurikulum unik per prodi dan kode tahap unik per versi. Nomor versi berikutnya dialokasikan dengan kunci transaksi. Publikasi dan tanggal efektif menunggu kebijakan akademik.

Lima tes, pemeriksaan Django dan migrasi, Ruff, serta mypy lulus dengan PostgreSQL sementara pada CPython 3.13 dan 3.14. Migrasi aditif `academics.0002` diterapkan ke `titenana` lokal dan server dimulai ulang.

Sidebar Administrasi Sistem kini memakai accordion. Superuser dapat menambah dan menyunting definisi peran melalui matriks dengan checkbox izin dan pilihan ruang lingkup. Matriks menyimpan definisi peran. Penugasan pengguna tetap memakai alur penugasan yang tersedia.

Tabel Pengguna memberi superuser alur tambah dan sunting akun, reset kata sandi, serta hapus dengan konfirmasi. Pembuatan dan reset memvalidasi kata sandi. Penghapusan menjaga akun superuser dan akun yang masih dirujuk oleh catatan. Pengguna dengan izin lihat tetap dapat membaca tabel.

Login lokal beralih ke email tanpa membedakan kapitalisasi. Form akun mewajibkan email dan PostgreSQL menjaga keunikannya. Akun lama dengan email kosong perlu dilengkapi sebelum dapat masuk. Migrasi `accounts.0004` diterapkan pada `titenana`. Tujuh tes lulus pada CPython 3.13 dan 3.14, dan login administrator melalui email terverifikasi di server lokal.

Menu akun menyediakan Profil saya untuk mengubah nama pengguna dan email. Perubahan email dan kata sandi memerlukan kata sandi saat ini. Perubahan kata sandi memakai validasi Django dan mempertahankan sesi yang digunakan untuk mengubahnya.

## Fase 1b · Kohort dan pendaftaran mahasiswa

Menambahkan kohort per periode akademik, identitas mahasiswa yang terhubung ke akun, dan pendaftaran per kohort. Pengelola prodi memilih periode dalam cakupannya. Akses daftar dan penambahan pendaftaran memakai izin terpisah dan penugasan prodi aktif. Pendaftaran mencatat tanggal dan pelaku serta menjaga keunikan mahasiswa per kohort. Hubungan ke versi kurikulum efektif menunggu kebijakan publikasi.

Sepuluh tes, pemeriksaan Django dan konsistensi migrasi, Ruff, serta mypy lulus dengan PostgreSQL sementara pada CPython 3.13 dan 3.14. Migrasi aditif `academics.0003` diterapkan ke `titenana` dan server lokal dimulai ulang.


## Fase 1b · Draf kerangka kompetensi dan milestone

Menambahkan modul `apps/competencies` dan halaman Akademik → Kompetensi. Pengelola
dengan penugasan prodi aktif dapat membuka kerangka, membuat versi draf kosong,
menambah butir bertingkat, dan mencatat ekspektasi perkembangan per butir dan tahap
kurikulum berversi. Milestone mendeskripsikan ekspektasi akademik pada tahap
tersebut. Kehadiran milestone tidak menghasilkan temuan kecukupan bukti,
temuan performa, atau keputusan progresi. Versi, butir dan milestone mencatat
pelaku dan waktu pembuatan.
Alokasi nomor versi dan penambahan butir menggunakan kunci transaksi. Formulir
membatasi butir induk pada versi yang sama dan tahap kurikulum pada prodi yang sama.

Migrasi `competencies.0001` disiapkan untuk peninjauan. Publikasi, tanggal efektif,
dan pengikatan enrollment mengikuti kebijakan yang masih terbuka. Indikator
tersendiri, relasi perkembangan dan standar performa berversi menyusul.

Sebelas tes lulus pada CPython 3.13.18 dan 3.14.10 dengan PostgreSQL sementara.
Pemeriksaan Django dan drift migrasi lulus pada kedua versi. Ruff dan mypy juga
lulus. Migrasi baru hanya diuji pada basis data sementara.

Setelah disetujui, migrasi `competencies.0001_initial` diterapkan ke basis data
pengembangan lokal. Halaman Kompetensi mengembalikan HTTP 200 untuk akun dengan
penugasan prodi aktif.

## Fase 1b · Indikator kompetensi

Menambahkan tabel indikator di halaman draf kerangka kompetensi dengan alur
**Tambah baris**. Indikator terhubung ke butir dalam versi yang sedang dibuka dan
menyimpan kode, deskripsi, pelaku, serta waktu pembuatan. Kode boleh digunakan
kembali pada butir lain. Indikator mendeskripsikan ekspektasi kompetensi.
Relasi perkembangan dan standar performa berversi menyusul.

Sebelas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Pemeriksaan Django, drift migrasi, Ruff dan mypy lulus. Migrasi aditif
`competencies.0002_competencyindicator` diterapkan pada basis data pengembangan
lokal dan tabel indikator dapat dibaca.

## Fase 1b · Relasi perkembangan dan standar performa

Draf kerangka kompetensi menyediakan tabel untuk mencatat relasi terarah antarbutir
dan menambah versi standar performa. Relasi mencatat deskripsi perkembangan
akademik. Pemberlakuan prasyarat memerlukan kebijakan akademik. Menyimpan kode
standar yang sama pada butir yang sama menambahkan versi dengan nomor berikutnya
dan mempertahankan seluruh deskripsi sebelumnya. Versi standar masih berupa draf.
Publikasi, tanggal efektif dan pengikatan enrollment menunggu keputusan akademik.

Sebelas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Django checks, drift migrasi, Ruff dan mypy lulus. Migrasi aditif
`competencies.0003` diterapkan pada basis data pengembangan lokal, dan tabel
relasi serta versi standar dapat dibaca.

## Inkrement 1c · Draf blueprint asesmen

Menambahkan modul `apps/assessments` dan tab Blueprint asesmen pada ruang Akademik.
Pengelola dengan penugasan aktif dapat membuat versi draf yang mengacu pada
versi kerangka kompetensi prodi, mencatat komponen asesmen dan memetakan satu
komponen ke beberapa butir. Komponen mencatat metode, tujuan, tahap kurikulum,
dan waktu asesmen. Metode masih dicatat sebagai teks pada draf. Model registri
metode dan sumber, pemetaan indikator serta aturan sampling menyusul. Draf,
komponen, dan pemetaan menyimpan pelaku dan waktu pembuatan.

Migrasi awal `assessments.0001` disiapkan untuk peninjauan.

Dua belas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Tes blueprint mencakup isolasi prodi, versi draf, tahap kurikulum dan
pemetaan duplikat. Django checks, drift migrasi, Ruff, dan mypy lulus.

Setelah disetujui, migrasi `assessments.0001_initial` diterapkan ke basis data
pengembangan lokal. Halaman Blueprint asesmen mengembalikan HTTP 200 untuk
akun dengan penugasan prodi aktif.

## Inkrement 1c · Pemetaan indikator blueprint

Pemetaan komponen dapat menargetkan butir secara umum atau indikator dari
butir yang sama. Pemetaan umum yang sudah tersimpan dipertahankan. Formulir
membatasi indikator pada versi kerangka blueprint dan menolak indikator yang
berasal dari butir lain. PostgreSQL menjaga keunikan tiap pemetaan umum atau
pemetaan indikator per komponen.

Dua belas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Pemeriksaan Django, drift migrasi, Ruff dan mypy lulus. Migrasi
`assessments.0002` diterapkan ke basis data pengembangan lokal.

## Inkrement 1c · Rancangan sampling blueprint

Menambahkan tabel rancangan sampling di draf blueprint. Pengelola prodi
mencatat komponen, konteks, dan jumlah minimum observasi. Formulir membatasi
pilihan komponen pada draf yang sedang dibuka. Rancangan mendokumentasikan
desain asesmen. Penilaian kecukupan bukti dan penetapan kompetensi memiliki
alur tersendiri.

Dua belas tes lulus pada CPython 3.13 dan 3.14. Pemeriksaan Django, drift
migrasi, Ruff, dan mypy lulus. Migrasi aditif `assessments.0003` diterapkan
ke basis data pengembangan lokal dan tabel sampling dapat dibaca.

## Akademik · Aksi baris

Menyeragamkan kolom Aksi di kanan tabel Akademik, termasuk kompetensi dan
blueprint. Pratinjau membuka rincian baris. Sunting membuka formulir dengan
Simpan di kolom Aksi. Hapus meminta konfirmasi dan memeriksa rujukan.
Izin tindakan dan cakupan prodi diperiksa di server. Menyunting deskripsi standar
performa membuat versi draf baru. Kerangka pada blueprint yang sudah berisi
komponen tetap terikat pada versi yang dipilih ketika draf dibuat.

Kohort yang sudah memiliki mahasiswa mempertahankan periode akademiknya.
Tiga belas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Django checks, drift migrasi, Ruff, dan mypy lulus.

## Inkrement 1c · Registri sumber bukti

Tab Sumber bukti memuat registri per prodi. Pengelola mencatat jenis bukti,
cara sumber menghasilkan dan memverifikasi bukti, serta kapabilitas dan
pemetaan ke butir pada draf kompetensi prodi. Tabel memakai aksi baris yang
sudah tersedia. Pengaitan ke blueprint dan tahap pengumpulan bukti menyusul.
Migrasi awal `evidence.0001_initial` disiapkan untuk peninjauan.

Empat belas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Tes registri mencakup cakupan prodi, rujukan silang, duplikasi, dan pratinjau.
Pemeriksaan Django, drift migrasi, Ruff dan mypy lulus.

Setelah disetujui, migrasi `evidence.0001_initial` diterapkan ke basis data
pengembangan lokal. Tab Sumber bukti mengembalikan HTTP 200 untuk akun
dengan penugasan prodi aktif.

## Inkrement 1c · Sumber bukti komponen blueprint

Draf blueprint menyediakan tabel untuk memilih pasangan sumber dan jenis bukti
yang terdaftar sebagai kapabilitas prodi. Satu komponen dapat memiliki beberapa
kapabilitas. Pemetaan menolak duplikasi, komponen dari draf lain, dan sumber
atau jenis dari prodi lain. Kapabilitas yang dipakai blueprint tidak dapat
diubah jenisnya atau dihapus dari registri. Tautan ini mencatat rancangan
asesmen untuk peta artefak yang akan dikembangkan pada inkrement 1c.

Empat belas tes lulus pada CPython 3.13 dan 3.14. Pemeriksaan Django, drift
migrasi, Ruff dan mypy lulus. Migrasi aditif `assessments.0004` diterapkan
ke basis data pengembangan lokal dan tabel tautan dapat dibaca.

## Inkrement 1c · Pratinjau peta artefak

Draf blueprint dapat membuka pratinjau peta artefak untuk prodi yang sama.
Tabel komponen menampilkan tahap, target butir atau indikator, pasangan sumber
dan jenis bukti, serta sampling. Tabel cakupan menampilkan komponen blueprint,
pemetaan sumber dari registri dan milestone untuk butir pada versi kompetensi
yang dirujuk. Kolom kosong memberi tanda pada rujukan yang belum dirancang
atau dipetakan. Data dihitung dari konfigurasi draf saat halaman dibuka.
Peta tersimpan, konfigurasi persyaratan, dan rencana individual menyusul.

Empat belas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Tes peta mencakup cakupan prodi dan draf, penggabungan konfigurasi, kondisi
belum dipetakan, dan penolakan penulisan. Pemeriksaan Django, drift migrasi,
Ruff, dan mypy lulus. Perubahan ini tidak memerlukan migrasi.

## Inkrement 1c · Versi draf peta artefak

Pratinjau dapat menyimpan salinan konfigurasi saat tombol Simpan versi draf
dikirim. Peta memakai urutan versi per prodi dan menyimpan blueprint asal,
pelaku, waktu serta salinan data yang dapat dibaca kembali. Tampilan versi lama
tetap sama saat konfigurasi sumber diubah. Tampilan versi tersimpan bersifat
baca saja. Publikasi peta dan pembentukan persyaratan atau rencana bukti
individual masih menyusul.

Empat belas tes lulus pada CPython 3.13 dan 3.14. Tes mencakup urutan versi,
isolasi antarprodi, dan kestabilan peta lama setelah konfigurasi berubah.
Pemeriksaan Django, drift migrasi, Ruff dan mypy lulus. Migrasi aditif
`evidence.0002` diterapkan ke basis data pengembangan lokal.

## Inkrement 1c · Draf persyaratan bukti manual

Pengelola dapat membuka Kelola persyaratan bukti dari pratinjau peta artefak.
Persyaratan manual mencatat kode, nama, target butir, pasangan sumber dan jenis
bukti, jumlah minimum, serta konteks opsional. Draf ditampilkan pada pratinjau
dan disalin ke versi peta yang baru disimpan. Peta lama tetap dapat dibaca.
Persyaratan otomatis, penggabungan asal, tenggat dan pembentukan rencana
individual menunggu mekanisme dan kebijakan terkait.

Empat belas tes lulus pada CPython 3.13 dan 3.14. Pemeriksaan Django, drift
migrasi, Ruff dan mypy lulus. Migrasi aditif `evidence.0003` diterapkan pada
basis data pengembangan lokal dan tabel persyaratan dapat dibaca.

## Inkrement 1c · Usulan persyaratan dari blueprint

Peta artefak menampilkan satu usulan per rancangan sampling pada komponen
yang memiliki target kompetensi dan kapabilitas sumber. Semua target dan
kapabilitas tetap tercatat pada usulan yang sama. Minimum observasi berasal
dari rancangan sampling dan tidak dibagi per target atau sumber. Usulan
ditampilkan terpisah dari persyaratan manual, ikut disalin ke versi peta baru,
dan belum menjadi bagian dari rencana mahasiswa. Versi peta sebelumnya tetap
dapat dibuka memakai data yang tersimpan saat itu.

Empat belas tes lulus pada CPython 3.13 dan 3.14 dengan PostgreSQL sementara.
Tes mencakup beberapa konteks dan sumber, komponen yang belum lengkap, serta
versi peta lama. Pemeriksaan Django, drift migrasi, Ruff, dan mypy lulus.
Perubahan ini tidak memerlukan migrasi.

## Akademik · Izin Kaprodi pada aksi baris

Aksi Sunting dan Hapus kini membaca izin yang dicentang pada penugasan peran
prodi. Pemeriksaan cakupan konfigurasi aktif dan izin Django yang sudah tersedia
tetap berlaku. Untuk kurikulum, penghapusan juga menghapus draf kosong yang dibuat
bersamanya dalam satu transaksi. Draf yang masih dirujuk, misalnya oleh tahap
kurikulum, melindungi kurikulum dari penghapusan.

Lima belas tes lulus pada CPython 3.13 dan 3.14. Akun Kaprodi lokal
terverifikasi melihat Sunting dan Hapus di daftar Kurikulum.

Matriks Peran & Hak Akses kini menyediakan izin dari modul Kompetensi.
Peran Kaprodi pada basis data pengembangan lokal diberi izin sunting dan hapus
untuk butir, indikator, milestone, relasi perkembangan, serta versi standar
performa. Izin berlaku pada prodi yang ditugaskan. Akun Kaprodi lokal
terverifikasi melihat kedua aksi pada draf kompetensi.

## Inkrement 1c · Draf rencana bukti individual

Daftar pendaftaran mahasiswa menyediakan tautan Rencana bukti untuk pengelola
berizin. Pengelola memilih versi peta tersimpan pada prodi yang sama untuk
membuat draf. Pengiriman ulang pasangan pendaftaran dan peta membuka draf
yang sudah ada. Draf menampilkan persyaratan manual dan usulan blueprint
dari versi peta yang dipilih serta mencatat pelaku dan waktu pembuatan.
Aktivasi baseline, aturan penggabungan, tenggat dan penanggung jawab masih
menunggu kebijakan akademik.

Enam belas tes lulus pada CPython 3.13 dan 3.14, termasuk akses berlingkup,
penolakan peta lintas prodi, pengiriman ulang, dan pembacaan versi tersimpan.
Pemeriksaan Django, drift migrasi, Ruff dan mypy lulus. Migrasi aditif
`evidence.0004` diterapkan ke basis data pengembangan lokal.

## Inkrement 1c · Penerbitan peta dan baseline bukti

Kaprodi berizin dapat memilih persyaratan manual dan blueprint dari versi peta
tersimpan, mengisi tenggat atau penanggung jawab bila diperlukan, dan menerbitkan
versi dengan tanggal efektif. Versi terbit menyimpan pilihan tanpa penggabungan.
Pendaftaran baru merujuk versi terbaru yang efektif pada tanggal pendaftaran.
Pendaftaran tanpa versi efektif tetap dapat dibuat dan tidak memperoleh baseline.
Penerbitan baru tidak mengubah baseline lama atau memproses ulang pendaftaran
lama. Penerbitan dan pendaftaran menyelaraskan pemilihan versi melalui kunci
transaksi prodi.

Enam belas tes lulus pada CPython 3.13 dan 3.14. Tes fokus penerbitan serta
pendaftaran juga lulus setelah verifikasi ulang. Django checks, drift migrasi,
Ruff, dan mypy lulus. Migrasi aditif `evidence.0005` diterapkan pada basis
data pengembangan lokal dan izin penerbitan diberikan pada peran Kaprodi
berlingkup prodi.

Tab Peta Artefak kini tersedia langsung di Akademik. Daftarnya menampilkan
pratinjau dari draf blueprint dan versi peta tersimpan beserta status serta
tanggal efektifnya. Akses melalui draf blueprint juga tetap tersedia.

## Fase 2a · Pelaksanaan, percobaan, dan asal-usul bukti

Tab Pelaksanaan asesmen mencatat tanggal pelaksanaan dari komponen blueprint
dan percobaan mahasiswa per pelaksanaan. Nomor percobaan bertambah per
partisipasi di bawah kunci transaksi. Pengelola dapat mencatat pengenal bukti
beserta pasangan sumber dan jenis yang telah ditautkan ke komponen. Rekaman
menyimpan percobaan, pelaku, dan waktu. Komponen yang sudah dipakai pada
pelaksanaan serta tautan sumber yang sudah dipakai untuk pencatatan bukti
dilindungi dari penyuntingan.
Verifikasi, artefak unggahan, penilaian, dan pemenuhan baseline belum tersedia
di alur ini. Peran memerlukan izin eksplisit sesuai tindakan.

Tujuh belas tes lulus pada CPython 3.13 dan 3.14. Django checks, drift migrasi,
Ruff, dan mypy lulus. Migrasi aditif `assessments.0005` dan `evidence.0006`
diterapkan ke basis data pengembangan lokal dan tabel baru dapat dibaca.

## Fase 2a · Keputusan verifikasi bukti

Pengguna dengan peran verifikator yang ditugaskan pada prodi dapat memutuskan
bukti dari daftar Bukti percobaan. Pencatat tidak dapat memverifikasi catatannya
sendiri. Keputusan pertama disimpan bersama alasan, pelaku, dan waktu.
Pengiriman berikutnya ditolak tanpa mengubah keputusan. Rekonsiliasi,
revisi, dan pembatalan keputusan belum tersedia.

Tujuh belas tes lulus pada CPython 3.13 dan 3.14. Tes mencakup kedua status,
alasan wajib, penolakan verifikasi sendiri, pembatasan prodi, dan perlindungan
keputusan. Django checks, drift migrasi, Ruff dan mypy lulus. Migrasi aditif
`evidence.0007` diterapkan ke basis data pengembangan lokal.

## Fase 2a · Koreksi dan pembatalan bukti

Pengguna berizin mencatat dapat mengoreksi bukti terkini dengan alasan.
Koreksi membuat versi baru yang belum diputuskan serta mempertahankan versi
dan keputusan sebelumnya. Verifikator prodi selain pencatat dapat membatalkan
versi terkini. Pembatalan melindungi riwayat keputusan dan menyimpan pelaku,
waktu, serta alasan. Daftar bukti menampilkan status Digantikan atau Dibatalkan
dan detail menautkan versi terkait. Query kelayakan menyaring versi lama,
bukti yang belum terverifikasi, dan bukti yang dibatalkan. Pencocokan terhadap
persyaratan baseline menunggu aturan tersendiri.

Tujuh belas tes lulus pada CPython 3.13 dan 3.14, termasuk koreksi satu rantai,
verifikasi ulang, penolakan pembatalan sendiri dan pemilihan bukti yang layak.
Django checks, drift migrasi, Ruff dan mypy lulus. Migrasi `evidence.0008`
diterapkan ke basis data pengembangan lokal.

## Fase 2b · Rekonsiliasi baseline

Rencana bukti menautkan halaman Rekonsiliasi bukti. Bukti yang layak pada
pendaftaran yang sama dicocokkan dengan persyaratan terbit. Kecocokan tunggal
dengan pengenal komponen, sumber dan jenis, serta konteks lengkap dihitung
otomatis. Pengelola berizin memilih satu penempatan dengan alasan untuk bukti
yang perlu ditinjau. Koreksi dan pembatalan mengeluarkan versi lama dari
hitungan serta mempertahankan penempatan historis. Hitungan memberi gambaran
pemenuhan baseline. Evaluasi kecukupan dan kompetensi tetap terpisah.

Tujuh belas tes lulus pada CPython 3.13 dan 3.14. Pengujian mencakup pencocokan
tunggal, ganda, konteks kosong, penempatan manual, dan penghitungan ulang setelah
pembatalan. Django checks, drift migrasi, Ruff dan mypy lulus. Migrasi
`evidence.0009` diterapkan ke basis data pengembangan lokal.

## Fase 2b · Impor bukti CSV

Impor tersedia dari Bukti percobaan untuk pengguna yang dapat mencatat
bukti. Pratinjau menampilkan hasil per baris, lalu permintaan konfirmasi
memeriksa ulang data untuk percobaan dan pengguna yang sama. Pengulangan
identik dilewati. Konflik menahan seluruh batch. Rekaman baru menunggu
verifikasi dan menyimpan asal impor melalui rujukan ke batch.

Tujuh belas tes lulus pada CPython 3.13 dan 3.14. Tes mencakup pratinjau
tanpa penulisan, pengulangan, pemeriksaan ulang pada konfirmasi, konflik,
dan asal impor. Django checks, drift migrasi, Ruff dan mypy lulus. Migrasi
`evidence.0010` diterapkan pada basis data pengembangan lokal.

## Fase 2 · Lampiran PDF privat

Detail bukti menyediakan lampiran PDF maksimal 10 MiB. Aplikasi memeriksa
ukuran, ekstensi dan penanda format PDF, lalu menyimpan berkas di direktori
privat dan menyajikan unduhan setelah pemeriksaan izin. Pengulangan berkas
identik pada versi yang sama tidak membuat entri baru. Lampiran tetap terikat
pada versi asal setelah koreksi atau pembatalan. Validasi format tidak menilai
isi atau menghapus identitas pasien. Retensi dan penghapusan masih menunggu
kebijakan sebelum fitur dipakai dengan data nyata.

Tujuh belas tes lulus pada CPython 3.13 dan 3.14, termasuk validasi berkas,
unduhan berizin, pemisahan rujukan lampiran, dan riwayat lampiran setelah
koreksi. Django checks, drift migrasi, Ruff dan mypy lulus. Migrasi
`evidence.0011` diterapkan pada basis data pengembangan lokal.
