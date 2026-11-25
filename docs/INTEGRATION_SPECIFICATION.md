# Integrasi

Adaptor berversi menerima data asesmen, LMS, logbook, akademik dan repositori bukti. Normalisasi dengan skema input tervalidasi. Identitas sumber dan ID eksternal stabil membentuk kunci idempotensi. Bedakan retry payload identik dari perubahan untuk ID yang sama dan rekam revisi hanya melalui alur koreksi yang sah.

Impor CSV menyediakan validasi, pratinjau, laporan kegagalan per baris, komit yang dapat diaudit dan rekonsiliasi. Cakupan akun integrasi mengikat prodi dan sumber yang diizinkan. Simpan provenance, waktu dan versi adaptor. Gunakan aturan interpretasi akademik terbit untuk pemetaan skor eksternal. Terapkan retry outbox dan audit tanpa menyertakan payload sensitif dalam log teknis.
