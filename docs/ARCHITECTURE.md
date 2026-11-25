# Arsitektur dan inventaris Fase 0

Baseline diperiksa dari workspace hasil reset dan sumber di arsip lokal sebelum reset. Workspace aktif memuat referensi UI, CSS, JavaScript, mockup dan lockfile npm. PostgreSQL lokal 18.6 memiliki nol tabel publik. Runtime Django dan lockfile Python lama berada dalam arsip.

| Aplikasi lama | Model yang ditemukan | Migrasi domain | Keputusan untuk fondasi baru |
| --- | --- | --- | --- |
| accounts | User, StudentRegistration | 0001–0002 | Pertahankan kontrak identitas UUID dan autentikasi Django. Rancang pendaftaran lewat relasi akademik dan izin tersendiri. |
| institutions | Institution, StudyProgram, InstitutionAffiliation, ProgramAffiliation | 0001–0005 | Pertahankan satu fakultas, banyak prodi dan afiliasi bertanggal sebagai desain. Tambahkan periode, kohort dan enrollment. |
| authorization | ProgramRoleGrant, ProgramAccessSettings | 0001–0004 | Gabungkan izin tindakan, cakupan, penugasan dan visibilitas. Rancang pemberian peran serta audit di frontoffice. |
| core | ApplicationSettings | 0001 | Tinjau kebutuhan pengaturan global pada administrasi kustom. |
| competencies | CompetencyFramework, CompetencyFrameworkVersion, CompetencyItem | 0001–0002 | Pertahankan konsep hierarki dan publikasi versi. Tambahkan indikator, relasi, milestone dan standar. |
| curriculum | CurriculumVersion, CurriculumUnit, UnitCoverage, CoordinatorAssignment, AchievementTarget | 0001 | Selaraskan unit, tahap, rotasi, milestone, penugasan dan enrollment dengan model versi. |
| evidence | ExpectedEvidence, ExpectedEvidenceCompetency | 0001–0004 | Pemetaan manual menjadi salah satu asal dalam model hibrida. Blueprint, registri, peta artefak dan rencana individual perlu dibangun. |

Arsip memuat proyek Django 5.2 berbasis CPython 3.13–3.14, uv, konfigurasi PostgreSQL berbasis lingkungan dan pytest-django. Sepuluh berkas tes mencakup smoke PostgreSQL, akun, peran, administrasi, frontoffice, kantor prodi, kompetensi, kurikulum dan bukti yang diharapkan. Asersi domain yang sesuai dapat menjadi referensi pengujian baru. Aplikasi lama memasang Django Admin dan mengaitkan tugas sistem dengannya. Rute dan templat yang bergantung pada Django Admin menjadi referensi visual untuk administrasi kustom.

Gunakan kembali shell dan navigasi frontoffice, komponen tabel, pola tambah baris, CSS Tailwind/Oxbow dan mockup. Tinjau kontrak URL dan data setiap templat sebelum menghubungkannya. Pertahankan tampilan dan aksesibilitas, termasuk fokus keyboard, label, aksi per baris, pesan kesalahan pada baris terkait dan nilai isian ketika validasi gagal.

| Direktori | Tanggung jawab |
| --- | --- |
| `apps/core/` | Infrastruktur bersama, termasuk mekanisme outbox dan pekerjaan latar |
| `apps/accounts/` | Identitas, autentikasi, peran, izin, dan kebijakan akses bercakupan |
| `apps/academics/` | Fakultas, prodi, kurikulum, tahap, periode, enrollment, afiliasi, dan penugasan akademik |
| `apps/competencies/` | Kerangka kompetensi, indikator, milestone, dan standar performa berversi |
| `apps/assessments/` | Blueprint dan sampling, event asesmen, partisipasi, attempt, dan hasil |
| `apps/evidence/` | Registri sumber, peta artefak, bukti yang diharapkan, rencana individual, bukti aktual, verifikasi, dan rekonsiliasi |
| `apps/adaptive/` | Aturan evaluasi, kecukupan bukti, kesenjangan performa, kebutuhan attempt tambahan, dan eskalasi |
| `apps/reflection/` | Refleksi, sensemaking, ringkasan bukti, revisi, dan visibilitas |
| `apps/coaching/` | Umpan balik, dialog, dan tindak lanjut coaching |
| `apps/learning/` | Rencana belajar, tujuan, intervensi, dan asesmen ulang |
| `apps/epa/` | EPA, observasi, skala supervisi, dan tinjauan entrustment |
| `apps/progression/` | Tinjauan kompetensi dan keputusan akademik formal oleh pihak berwenang |
| `apps/analytics/` | Evaluasi program dan pelaporan agregat |
| `apps/integrations/` | Adaptor sumber bukti eksternal, impor, dan idempotensi peristiwa eksternal |
| `apps/audit/` | Audit tindakan, akses sensitif, dan penelusuran provenance. Revisi dan provenance bukti dicatat oleh `apps/evidence/`. |
| `templates/` | Templat Django dan komponen UI Tailwind, termasuk administrasi kustom |
| `docs/` | Spesifikasi proyek dan catatan keputusan yang dipelihara bersama implementasi |

`apps/adaptive/` memisahkan evaluator kecukupan, evaluator performa, dan perencana attempt sebagai layanan domain. `apps/epa/` memasok konfigurasi, observasi, dan bahan tinjauan entrustment. Penetapan formal ditangani `apps/progression/` berdasarkan mandat yang berlaku. Tambahkan direktori aplikasi saat inkrement yang memerlukannya mulai dikerjakan.

Aplikasi web memanggil layanan domain melalui views Django dan formulir. Layanan mengelola transaksi dan kebijakan. Query membaca data dalam cakupan yang ditentukan server. Integrasi masuk melalui adaptor ke layanan yang sama. PostgreSQL menjadi sumber keadaan dan audit.

| Kesenjangan lintas domain | Fase |
| --- | --- |
| Struktur akademik, versi, rantai blueprint hingga rencana awal, administrasi kustom | 1 |
| Bukti aktual, autentisitas, percobaan, rekonsiliasi dan impor | 2 |
| Evaluasi yang dapat direproduksi dan adaptasi otomatis tanpa duplikasi | 3 |
| Ringkasan terpisah dari narasi, refleksi privat dan coaching | 4 |
| Rencana belajar, intervensi dan asesmen ulang | 5 |
| EPA opsional dan keputusan formal dengan otorisasi | 6 |
| Analitik dengan privasi dan operasi produksi | 7 |
