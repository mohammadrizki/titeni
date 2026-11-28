from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

TERMS = {
    "Analitik Prodi": (
        "Ringkasan agregat suatu prodi pada periode akademik tertutup. Laporan membantu "
        "meninjau pola kesenjangan bukti dan performa serta beban asesmen tambahan."
    ),
    "Artefak": (
        "Berkas atau hasil kerja yang mendokumentasikan kegiatan, seperti laporan kasus "
        "atau lembar observasi. Artefak dapat dilampirkan pada rekaman bukti."
    ),
    "Asesmen": "Kegiatan untuk mengamati atau menilai performa terhadap standar yang ditetapkan.",
    "Asesmen ulang": (
        "Asesmen setelah intervensi belajar untuk melihat apakah kesenjangan performa "
        "telah tertutup. Evaluasinya menggunakan bukti dari setelah intervensi."
    ),
    "Baseline": (
        "Rencana bukti awal yang berlaku untuk satu pendaftaran mahasiswa. Baseline "
        "menyimpan versi peta artefak yang menjadi dasar persyaratan pada pendaftaran itu."
    ),
    "Banding": (
        "Permintaan tertulis mahasiswa untuk meninjau keputusan formal miliknya dalam "
        "tenggat prodi. Hasil peninjauan banding disimpan bersama riwayat keputusan."
    ),
    "Blueprint asesmen": (
        "Rancangan berversi yang menghubungkan komponen asesmen, kompetensi, tahap "
        "kurikulum, kebutuhan pengamatan, dan sumber bukti."
    ),
    "Bukti": (
        "Rekaman yang mendukung penilaian kompetensi, misalnya hasil asesmen atau "
        "observasi. Rekaman memuat konteks dan sumber serta dapat menyertakan artefak."
    ),
    "Coaching": (
        "Dialog antara mahasiswa dan pembimbing tentang refleksi yang dibagikan, "
        "termasuk umpan balik dan rekomendasi yang dapat ditindaklanjuti."
    ),
    "EPA": (
        "Singkatan dari Entrustable Professional Activity. EPA adalah satu unit pekerjaan "
        "profesional yang dapat diamati dan menggabungkan beberapa kompetensi."
    ),
    "Evaluasi bukti": (
        "Penelaahan bukti terhadap aturan dan standar yang berlaku untuk menentukan "
        "kecukupan bukti serta, jika memungkinkan, status kesenjangan performa."
    ),
    "Indikator kompetensi": (
        "Perilaku atau hasil yang dapat diamati untuk membantu menilai suatu butir kompetensi."
    ),
    "Intervensi belajar": (
        "Kegiatan belajar yang ditujukan untuk menutup kesenjangan performa yang telah "
        "teridentifikasi. Pelaksanaan dan asesmen ulang dapat dicatat di Titeni."
    ),
    "Kecukupan bukti": (
        "Seberapa memadai bukti yang tersedia untuk menilai performa pada standar tertentu. "
        "Bukti yang cukup memungkinkan penilaian apakah kesenjangan masih terbuka."
    ),
    "Keputusan formal": (
        "Hasil yang diterbitkan oleh pihak berwenang, misalnya keputusan EPA atau "
        "progresi, dengan dasar bukti dan alasan yang dapat ditelusuri."
    ),
    "Kerangka kompetensi": (
        "Susunan kompetensi dan indikator yang dituju prodi. Setiap versi menjadi acuan "
        "bagi blueprint dan standar yang terkait dengannya."
    ),
    "Kesenjangan bukti": (
        "Kekurangan bukti yang diperlukan untuk menilai performa, misalnya jumlah "
        "pengamatan, variasi konteks, atau sumber bukti yang belum cukup."
    ),
    "Kesenjangan performa": (
        "Jarak antara performa yang teramati dan standar yang dituju. Statusnya dapat "
        "ditentukan ketika bukti tersedia dalam jumlah dan cakupan yang memadai."
    ),
    "Kohort": ("Kelompok pendaftaran mahasiswa pada satu periode akademik dalam suatu prodi."),
    "Kompetensi": (
        "Kemampuan yang menggabungkan pengetahuan, keterampilan, dan sikap untuk "
        "menjalankan tugas sesuai standar."
    ),
    "Kuorum": (
        "Jumlah minimum anggota yang memenuhi syarat untuk suatu putaran komite. "
        "Titeni menghitung anggota yang hadir, berwenang, dan menyatakan bebas konflik."
    ),
    "Mandat": (
        "Pemberian kewenangan kepada komite untuk cakupan dan masa berlaku tertentu. "
        "Mandat menetapkan siapa yang dapat ikut serta dan berapa kuorum minimumnya."
    ),
    "Milestone": ("Tonggak perkembangan kompetensi yang diharapkan pada tahap kurikulum tertentu."),
    "Observasi EPA": (
        "Catatan asesor tentang pelaksanaan EPA, termasuk konteks, kompleksitas kasus, "
        "tingkat supervisi teramati, dan umpan balik."
    ),
    "Peta artefak": (
        "Rancangan dari blueprint yang memetakan sumber dan persyaratan bukti ke "
        "kompetensi. Versi terbit menjadi dasar baseline pendaftaran."
    ),
    "Progresi": (
        "Peninjauan dan keputusan mengenai capaian kompetensi atau kelanjutan studi "
        "mahasiswa, berdasarkan bukti yang ditinjau oleh pihak berwenang."
    ),
    "Refleksi": (
        "Catatan mahasiswa untuk memahami pengalaman belajar, menilai perkembangan, "
        "dan menentukan tindak lanjut. Mahasiswa memilih versi yang ingin dibagikan."
    ),
    "Rekonsiliasi bukti": (
        "Pencocokan rekaman bukti dengan persyaratan baseline untuk melihat kebutuhan "
        "yang terpenuhi atau masih memerlukan peninjauan."
    ),
    "Rencana belajar": (
        "Catatan tujuan, tindakan, dan tindak lanjut pembelajaran yang dapat ditinjau "
        "kembali oleh mahasiswa dan dibagikan kepada pembimbing sesuai pilihan."
    ),
    "Reservasi asesmen tambahan": (
        "Pemesanan slot asesmen untuk kebutuhan bukti yang teridentifikasi. "
        "Reservasi dapat ditautkan ke percobaan asesmen setelah dilaksanakan."
    ),
    "Sintesis": (
        "Rangkuman perkembangan kompetensi lintas waktu yang disusun Peninjau Sintesis. "
        "Dasarnya mencakup evaluasi dan asesmen ulang serta materi yang mahasiswa bagikan."
    ),
    "Skala supervisi": (
        "Daftar tingkat supervisi berversi yang digunakan untuk mencatat pengamatan "
        "dan mendukung peninjauan EPA."
    ),
    "Standar performa": (
        "Deskripsi tingkat performa yang diharapkan pada suatu butir kompetensi. "
        "Titeni mengaitkan penilaian dengan versi standar yang dipakai."
    ),
    "Verifikasi bukti": (
        "Pemeriksaan sumber, rekaman, dan lampiran sebelum bukti dihitung. "
        "Verifikator mencatat hasil pemeriksaan dan alasannya."
    ),
}


@login_required
@require_safe
def index(request: HttpRequest) -> HttpResponse:
    ordered = sorted(TERMS.items(), key=lambda entry: entry[0].casefold())
    groups = [
        (letter, list(terms)) for letter, terms in groupby(ordered, lambda entry: entry[0][0])
    ]
    return render(request, "core/glossary.html", {"term_groups": groups})
