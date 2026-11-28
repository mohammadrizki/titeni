from dataclasses import dataclass


@dataclass(frozen=True)
class RoleGuide:
    summary: str
    steps: tuple[str, ...]


faculty_admin = RoleGuide(
    "Menyiapkan konfigurasi fakultas dan mandat lintas prodi.",
    (
        "Buka Administrasi Sistem → Profil Fakultas untuk memperbarui data fakultas.",
        "Buka Program Studi untuk mendaftarkan prodi dan Penugasan untuk memberi akses "
        "konfigurasi pada prodi yang sesuai.",
        "Buka Mandat Komite EPA atau Mandat Komite Progresi. Siapkan mandat, anggota, "
        "ketua, dan kuorum sesuai alur komite.",
        "Atur Tenggat Banding EPA atau Tenggat Banding Progresi, lalu tunjuk komite "
        "independen dari daftar banding yang masuk.",
    ),
)

program_lead = RoleGuide(
    "Mengoordinasikan operasi akademik dan menetapkan konfigurasi yang berlaku di prodi.",
    (
        "Buka Akademik, pilih prodi, lalu periksa periode, kohort, dan pendaftaran.",
        "Tinjau peta artefak dan aturan evaluasi di ruang kerja bukti sebelum menerbitkan "
        "versi yang akan dipakai prodi.",
        "Gunakan daftar pendaftaran untuk menugaskan Peninjau Sintesis atau Peninjau "
        "Progresi. Tinjau indikasi intervensi pada riwayat evaluasi sebelum menyetujui "
        "intervensi wajib.",
        "Untuk EPA, buka versi kegiatan, berlakukan versi, lalu atur penugasan asesor "
        "dan peninjau yang sesuai.",
        "Buka Analitik Prodi dan pilih periode akademik tertutup untuk meninjau laporan agregat.",
    ),
)

academic_manager = RoleGuide(
    "Menyiapkan periode, kohort, dan pendaftaran mahasiswa.",
    (
        "Buka Akademik, pilih prodi, lalu gunakan Periode akademik untuk mencatat masa studi.",
        "Buka Kohort dan tambahkan kohort pada periode yang sesuai.",
        "Buka daftar pendaftaran kohort, lalu daftarkan akun mahasiswa dengan alamat emailnya.",
    ),
)

curriculum_manager = RoleGuide(
    "Menyusun struktur pembelajaran, kerangka kompetensi, dan konfigurasi draf EPA.",
    (
        "Buka Akademik → prodi → Kurikulum, lalu siapkan draf versi dan tahap kurikulum.",
        "Buka Kompetensi untuk menata butir, indikator, standar performa, dan milestone.",
        "Jika prodi memakai EPA, buat versi kegiatan dan skala supervisi dari tab EPA.",
        "Buka Analitik Prodi untuk melihat pola kesenjangan dan beban asesmen "
        "pada periode tertutup.",
    ),
)

assessment_manager = RoleGuide(
    "Menyiapkan blueprint dan mencatat pelaksanaan serta hasil asesmen.",
    (
        "Buka Akademik → prodi → Blueprint asesmen untuk menyusun komponen, pemetaan, "
        "sampling, dan sumber bukti.",
        "Buka Pelaksanaan asesmen untuk mencatat sesi, peserta, dan percobaan.",
        "Buka percobaan mahasiswa untuk mencatat bukti. Untuk sumber ujian yang "
        "tersedia, gunakan Impor Hasil Ujian dan tinjau pratinjau sebelum menyimpan.",
    ),
)

portfolio_manager = RoleGuide(
    "Menata sumber bukti, rancangan portofolio, dan rekonsiliasi baseline.",
    (
        "Buka Akademik → prodi → Sumber bukti untuk mencatat sumber, jenis, dan kapabilitas bukti.",
        "Buka Peta Artefak untuk meninjau cakupan blueprint dan menyiapkan draf persyaratan.",
        "Dari daftar pendaftaran, buka Rencana bukti dan rekonsiliasi untuk meninjau "
        "bukti yang cocok atau menempatkan bukti yang memerlukan peninjauan.",
    ),
)

evidence_verifier = RoleGuide(
    "Menilai apakah versi bukti memenuhi pemeriksaan verifikasi.",
    (
        "Buka Akademik → prodi → Pelaksanaan asesmen, lalu pilih sesi, percobaan, dan versi bukti.",
        "Tinjau sumber serta lampiran yang tersedia. Catat keputusan dan alasan pada halaman "
        "verifikasi untuk bukti yang dicatat oleh pengguna lain.",
        "Jika versi bukti perlu dibatalkan, catat alasannya melalui tindakan pembatalan.",
    ),
)

assessor = RoleGuide(
    "Mencatat temuan terstruktur dan observasi tempat kerja sesuai penugasan.",
    (
        "Buka Penugasan Asesor, periksa revisi bukti dan standar yang ditetapkan, "
        "lalu catat temuan beserta alasannya.",
        "Untuk penugasan EPA, buka Observasi EPA, pilih penugasan, lalu isi tanggal, "
        "konteks, kompleksitas, tingkat supervisi teramati, dan umpan balik.",
    ),
)

progression_reviewer = RoleGuide(
    "Menyusun draf rekomendasi capaian kompetensi dan progresi.",
    (
        "Buka Peninjauan Progresi dan pilih pendaftaran mahasiswa yang ditugaskan.",
        "Tinjau evaluasi produksi, hasil asesmen ulang, dan keputusan EPA yang tersedia.",
        "Pilih bukti yang mendukung rekomendasi, isi alasan, lalu simpan draf. "
        "Setiap revisi tersedia dalam riwayat.",
    ),
)

epa_reviewer = RoleGuide(
    "Menyusun draf rekomendasi tingkat supervisi EPA.",
    (
        "Buka Peninjauan EPA dan pilih penugasan mahasiswa.",
        "Baca observasi dan umpan balik dari versi EPA yang tercakup.",
        "Pilih observasi pendukung dan tingkat supervisi dari skala yang ditugaskan. "
        "Tulis alasan dan simpan draf.",
    ),
)

adaptation_manager = RoleGuide(
    "Menilai kecukupan bukti dan mengelola kebutuhan asesmen tambahan.",
    (
        "Buka Rencana bukti → Evaluasi bukti untuk meninjau versi aturan, "
        "menyiapkan pratinjau, atau mencatat evaluasi.",
        "Gunakan penugasan asesor bila dibutuhkan temuan terstruktur. Siapkan opsi "
        "dan slot di Kebijakan percobaan tambahan.",
        "Buka pratinjau rencana untuk menata reservasi. Tinjau Antrean eskalasi untuk "
        "kebutuhan yang masih memerlukan tindak lanjut.",
    ),
)

lecturer = RoleGuide(
    "Identitas dosen pada prodi penugasan. Tugas di Titeni mengikuti peran fungsional akun.",
    (
        "Buka panduan peran fungsional lain pada halaman ini untuk melihat langkah tugas.",
        "Jika tugas yang diberikan belum muncul, hubungi pengelola akun untuk "
        "memeriksa penugasan peran dan prodi.",
    ),
)

synthesis_reviewer = RoleGuide(
    "Merangkum perkembangan kompetensi mahasiswa yang ditugaskan.",
    (
        "Buka Rencana Belajar → Penugasan Peninjau Sintesis.",
        "Pilih pendaftaran, lalu telaah evaluasi produksi dan materi yang dibagikan kepada Anda.",
        "Tulis rangkuman perkembangan dan tindak lanjut pada bagian Sintesis peninjau.",
    ),
)

reflection_advisor = RoleGuide(
    "Mendampingi refleksi, tujuan belajar, dan tindak lanjut intervensi.",
    (
        "Buka Refleksi Pribadi dan lihat refleksi yang dibagikan. Buka dialog coaching "
        "untuk menanggapi atau mencatat rekomendasi.",
        "Buka Rencana Belajar → Tujuan yang dibagikan kepada saya untuk meninjau "
        "versi tujuan yang diberikan mahasiswa.",
        "Dari antrean tinjauan tujuan, buka Draf intervensi pembelajaran untuk "
        "menyiapkan draf atau memverifikasi pelaksanaan pada penugasan Anda.",
    ),
)

student = RoleGuide(
    "Mencatat refleksi dan tujuan belajar serta menindaklanjuti pembelajaran.",
    (
        "Buka Refleksi Pribadi, pilih pendaftaran, lalu tulis refleksi. "
        "Bagikan versi yang dipilih kepada pembimbing jika diperlukan.",
        "Buka Rencana Belajar untuk mencatat tujuan, meninjau rekomendasi, atau "
        "melaporkan intervensi yang sudah dilaksanakan.",
        "Jika keputusan tersedia, buka Keputusan EPA atau Keputusan Progresi. "
        "Baca alasan dan gunakan formulir banding selama tenggat yang tertera.",
    ),
)
