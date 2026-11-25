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
