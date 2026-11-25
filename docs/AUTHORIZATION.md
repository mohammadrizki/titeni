# Otorisasi dan privasi

Kebijakan server mengevaluasi akun aktif, izin tindakan, cakupan fakultas/prodi, relasi akademik yang berlaku dan visibilitas rekaman. Tentukan program dan learner dari sumber daya atau relasi tersimpan. Terapkan kebijakan pada pembacaan, mutasi, pencarian, unduhan, API, ekspor dan tugas latar. Batasi query daftar sebelum paginasi atau agregasi.

| Pelaku | Cakupan tindakan |
| --- | --- |
| Administrator sistem/institusi | Operasi dan pengaturan yang diberikan secara eksplisit melalui administrasi kustom. Akses rekaman pendidikan tetap tunduk pada kebijakan domain. |
| Pengelola prodi, kurikulum, asesmen, portofolio | Konfigurasi di prodi yang diberikan. Publikasi dan delegasi memerlukan izin khusus. |
| Mahasiswa | Rekam pendidikan sendiri menurut visibilitas, pengajuan bukti, refleksi pribadi dan akses berbagi sesuai kebijakan. |
| Asesor dan supervisor | Peserta, asesmen atau penempatan sesuai penugasan yang masih berlaku. |
| Pembimbing dan coach | Learner tercakup dalam penugasan dan refleksi yang dibagikan secara sah. |
| Komite dan pengambil keputusan | Kasus yang tercakup mandat serta keanggotaan berlaku. |
| Akun integrasi dan auditor | Kerja impor atau baca audit yang diberikan secara terbatas untuk sumber serta cakupan yang ditentukan. |

Pemberian dan pencabutan peran mencatat pemberi, waktu, alasan dan cakupan dalam transaksi yang sama. Cegah pemberian hak ke diri sendiri tanpa kewenangan. Batasi data klinis ke rujukan terdeidentifikasi dan lindungi unduhan. Catat akses sensitif. Uji kebocoran melalui perbedaan respons, daftar, agregat, lampiran dan ekspor.

## Izin konfigurasi yang tersedia

Superuser dapat menyimpan definisi peran melalui matriks Peran & Hak Akses, dengan pilihan izin dan ruang lingkup Sistem, Program studi, atau Lainnya. Di tabel Pengguna, superuser dapat menugaskan beberapa peran sekaligus. Setiap peran berlingkup prodi mengikat penugasan pada satu program yang dipilih. Penugasan mencatat pemberi dan waktu serta mencegah duplikasi pada cakupan yang sama. Ruang lingkup Lainnya menunggu definisi target. Evaluasi izin dari matriks dan pencabutan penugasan peran belum tersedia. Penugasan konfigurasi prodi saat ini menggunakan pemeriksaan cakupan yang sudah tersedia.

Operasi tingkat fakultas memerlukan `accounts.access_system_workspace` dan izin tindakan Django untuk profil fakultas, registrasi prodi, atau penugasan konfigurasi. Penugasan diberikan kepada akun aktif selain pemberi dan berlaku pada satu prodi dalam rentang tanggalnya. Pemberian dan pencabutan mencatat pelaku dan waktu. Pencabutan juga memerlukan izin perubahan penugasan. Daftar prodi dan operasi periode memakai penugasan yang berlaku, termasuk untuk operator sistem. Penugasan konfigurasi ini memberi akses ke periode akademik. Kebijakan akses rekaman pendidikan mengikuti relasi akademik pada inkrement berikutnya.

Konfigurasi kohort memerlukan penugasan aktif pada prodi pemilik periode. Daftar mahasiswa juga memerlukan `academics.view_learnerenrollment`. Pendaftaran memerlukan tambahan `academics.add_learnerenrollment` dan memakai pencocokan email akun aktif secara tepat tanpa menampilkan direktori akun untuk dipilih. Prodi, periode, dan kohort ditentukan dari relasi tersimpan. Enrollment mencatat pelaku dan tanggal serta tidak memberi izin aplikasi secara otomatis.


Daftar dan perubahan draf kompetensi mengikuti cakupan penugasan konfigurasi aktif
seperti draf kurikulum. Halaman draf memeriksa versi terhadap prodi pada URL.
Pilihan induk dan target milestone dibatasi pada versi kerangka yang sedang
dibuka, sedangkan tahap milestone dibatasi pada prodi itu.
