# Adaptive Evidence Engine

1. Terima peristiwa bukti tervalidasi, koreksi, perubahan verifikasi, atau invalidasi dengan identitas idempoten. Resolusi enrollment, target, versi aturan dan standar yang berlaku.
2. Rekonsiliasi bukti yang sah berdasarkan tipe, konteks, waktu, sumber dan verifikasi. Simpan hubungan pemenuhan dan revisi bukti yang terpakai.
3. Nilai kecukupan berdasarkan kuantitas, kualitas, cakupan, kebaruan, autentisitas, keberagaman dan konsistensi, termasuk triangulasi, ketidakpastian dan konsekuensi keputusan. Aturan terbit dapat menentukan syarat berbeda untuk temuan terbuka dan tertutup.
4. Jika kurang, klasifikasikan gap bukti. Gunakan kebutuhan terjadwal yang relevan, cakup beberapa gap dengan satu attempt jika diizinkan, dan pertimbangkan beban, tenggat, konteks, asesor dan ketersediaan. Buat atau revisi kebutuhan, supersede yang berlebih dan belum dikerjakan, lalu eskalasi bila mencapai batas atau opsi yang sah habis.
5. Jika cukup, hentikan kebutuhan tambahan yang sudah tidak relevan dan evaluasi performa. Temuan terbuka mengarah ke jalur intervensi dan asesmen ulang sesuai kebijakan. Temuan tertutup menyiapkan bahan tinjauan.
6. Simpan snapshot, versi mesin, alasan dan perubahan audit dalam transaksi. Jadwalkan notifikasi dan pemrosesan turunan melalui outbox setelah commit.

Serialisasikan perubahan per rencana dan target yang terdampak dengan penguncian dan constraint unik. Koreksi atau invalidasi membentuk evaluasi baru. Revisi lama serta keputusan formal tetap dapat ditelusuri. Gunakan aturan deklaratif berversi dengan operator dan tipe parameter yang diizinkan, validasi, pratinjau simulasi, persetujuan publikasi dan penghentian versi. Ambang dan prioritas mengikuti kebijakan yang disetujui prodi.
