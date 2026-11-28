# Titeni

Portofolio reflektif dan pengembangan kompetensi.

## Pengembangan lokal

1. Gunakan uv, CPython 3.13 atau 3.14, dan PostgreSQL.
2. Jalankan `uv sync --locked`, salin `.env.example` ke `.env`, lalu isi `DJANGO_SECRET_KEY` dengan nilai acak dan `DATABASE_URL` dengan kredensial lokal.
3. Periksa konfigurasi dengan `uv run python manage.py check`.
4. Setelah migrasi lokal disetujui dan diterapkan, jalankan `uv run python manage.py runserver`.
5. Halaman masuk tersedia di `/masuk/`.
6. Akses `/administrasi/` memakai izin `accounts.access_system_workspace`.
7. Daftar akun memerlukan izin tambahan `accounts.view_user`.
8. Untuk pengujian, arahkan `DATABASE_URL` ke PostgreSQL khusus tes dengan izin membuat basis data tes, lalu jalankan `uv run pytest`.
9. Untuk membangun ulang CSS, gunakan `npm ci` dan `npm run css:build`.

## Memulai penggunaan Titeni

Setelah masuk, buka **Panduan → Panduan Memulai Titeni** untuk mengikuti
langkah penyiapan fakultas, prodi, peta artefak, dan pendaftaran mahasiswa.
Checklist **Memulai Titeni** di Beranda membaca data yang sudah tersimpan
dan meredupkan langkah yang selesai. Klik judul langkah yang belum selesai
untuk membuka halaman pengerjaannya. Setiap akun melihat langkah yang
menjadi tanggung jawab perannya. Pilih prodi bila memiliki lebih dari satu
cakupan konfigurasi. Mahasiswa melihat rekap pendaftaran sendiri dan
tautan ke Refleksi Pribadi serta Rencana Belajar ketika siap.

## Deployment produksi

Contoh ini memakai **Linux, systemd, Gunicorn, Nginx, dan PostgreSQL**.
Ganti `titeni.example.edu`, nama akun, dan jalur contoh sesuai lingkungan
tujuan. Jalankan perintah pengelolaan aplikasi dari `/srv/titeni/app`
sebagai akun layanan `titeni`. Jalankan operasi PostgreSQL dan perubahan
konfigurasi layanan dengan akun administrator yang berwenang.

### 1. Siapkan server dan PostgreSQL

- Siapkan uv, CPython 3.13 atau 3.14, PostgreSQL, Nginx, nama domain, dan
  sertifikat TLS yang mencakup domain tersebut.
- Tempatkan revisi yang akan dirilis di `/srv/titeni/app`. Siapkan
  `/srv/titeni/static` untuk aset publik dan `/srv/titeni/private-evidence`
  untuk lampiran. Akun aplikasi harus bisa menulis ke kedua direktori.
  Beri pekerja Nginx izin baca untuk direktori statis dan izin melintasi
  direktori induknya. Batasi akses direktori lampiran pada akun aplikasi
  dan akun pencadangan.
- Untuk instalasi baru pada PostgreSQL yang dikelola sendiri, contoh
  berikut dijalankan dengan koneksi administrator PostgreSQL. Perintah
  pertama meminta kata sandi untuk akun aplikasi.

```sh
createuser --pwprompt --no-superuser --no-createdb --no-createrole titeni
createdb --owner=titeni titeni
```

Untuk upgrade, gunakan basis data dan direktori lampiran yang sudah
ditetapkan. Sebelum migrasi, buat cadangan PostgreSQL dan direktori
lampiran pada titik yang sama saat penulisan dihentikan. Siapkan
lingkungan pemulihan terpisah untuk memverifikasi keduanya.

### 2. Atur lingkungan produksi

Simpan nilai berikut di `/etc/titeni/titeni.env` atau penyimpanan
konfigurasi layanan yang setara. Batasi akses ke berkas itu pada
administrator dan akun yang menjalankan perintah deployment.

```dotenv
DJANGO_SETTINGS_MODULE=config.production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=GANTI_DENGAN_KUNCI_ACAK
DJANGO_ALLOWED_HOSTS=titeni.example.edu
DATABASE_URL=postgresql://titeni:GANTI_PASSWORD_URL_ENCODED@127.0.0.1:5432/titeni
DJANGO_STATIC_ROOT=/srv/titeni/static
EVIDENCE_ARTIFACT_ROOT=/srv/titeni/private-evidence
DJANGO_TRUST_HTTPS_PROXY=true
```

Dengan CPython sudah tersedia, buat kunci acak memakai perintah berikut.

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Simpan kunci bersama konfigurasi layanan agar tetap tersedia saat restart
dan upgrade. Jika kata sandi
PostgreSQL mengandung karakter khusus URL, enkode bagian kata sandinya.
Untuk PostgreSQL jarak jauh, gunakan parameter TLS yang disyaratkan
penyedia. Isi `DJANGO_ALLOWED_HOSTS` dengan nama host tanpa skema atau
port. Formulir dari origin HTTPS lain yang memang perlu dipercaya dapat
didaftarkan melalui `DJANGO_CSRF_TRUSTED_ORIGINS`.

Contoh ini mengaktifkan `DJANGO_TRUST_HTTPS_PROXY` karena Nginx
mengakhiri TLS dan menetapkan ulang `X-Forwarded-Proto`. Untuk penerapan
yang menerima HTTPS langsung di server aplikasi, gunakan
`DJANGO_TRUST_HTTPS_PROXY=false`. [Pengaturan reverse proxy Django](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header)

### 3. Pasang dependensi dan periksa target

```sh
cd /srv/titeni/app
uv sync --locked --no-dev --python 3.13

# Dengan berkas lingkungan tepercaya yang memakai sintaks shell sederhana.
set -a
. /etc/titeni/titeni.env
set +a

uv run --no-sync python manage.py check --deploy
uv run --no-sync python manage.py shell -c \
  'from django.db import connection; s = connection.settings_dict; print(s["NAME"], s["HOST"], s["PORT"])'
uv run --no-sync python manage.py migrate --plan
```

Cocokkan nama basis data, host, dan port dengan target rilis sebelum
menjalankan migrasi. HSTS berlaku selama 3.600 detik secara bawaan.
Tinjau W005 dan W021 dari `check --deploy` sesuai kebijakan domain.
Cakupan subdomain dan preload dikendalikan oleh
`DJANGO_HSTS_INCLUDE_SUBDOMAINS` dan `DJANGO_HSTS_PRELOAD`.
Durasi dapat diatur lewat `DJANGO_HSTS_SECONDS`. Periksa seluruh
peringatan deployment sebelum membuka layanan. [Panduan deployment Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)

### 4. Terapkan migrasi, peran, dan aset

Setelah rencana migrasi ditinjau dan penerapan ke target disetujui,
jalankan perintah berikut.

```sh
uv run --no-sync python manage.py migrate --noinput
```

Pada instalasi baru, jalankan `uv run --no-sync python manage.py createsuperuser`
setelah mendapat persetujuan sesuai panduan kontribusi. Isi alamat email
akun agar dapat masuk melalui `/masuk/`. Sinkronisasi memerlukan
superuser aktif. Jika ada beberapa superuser
aktif, tambahkan `--actor-id UUID` pada setiap pemanggilan.

```sh
uv run --no-sync python manage.py sync_access_roles
# Tinjau pratinjau matriks sebelum menyimpan perubahan.
uv run --no-sync python manage.py sync_access_roles --apply
uv run --no-sync python manage.py sync_access_roles
uv run --no-sync python manage.py migrate --check
uv run --no-sync python manage.py collectstatic --noinput
```

Jika rilis mengubah sumber CSS dan keluaran CSS belum dibangun, jalankan
`npm ci` dan `npm run css:build` sebelum `collectstatic`. Sajikan
hanya `DJANGO_STATIC_ROOT` pada rute `/static/`. Lampiran di
`EVIDENCE_ARTIFACT_ROOT` diunduh melalui endpoint Django yang memeriksa
izin pengguna.

### 5. Jalankan Gunicorn dan Nginx

Repo mengunci dependensi aplikasi lewat `uv.lock`. Untuk contoh WSGI
ini, tetapkan `TITENI_GUNICORN_VERSION` ke versi Gunicorn yang telah
disetujui untuk deployment. Pasang versi tersebut ke lingkungan rilis
setelah `uv sync`.

```sh
: "${TITENI_GUNICORN_VERSION:?Tetapkan versi Gunicorn untuk deployment}"
uv pip install --python .venv/bin/python "gunicorn==$TITENI_GUNICORN_VERSION"
.venv/bin/gunicorn --version
```

Jalankan kembali instalasi Gunicorn setelah sinkronisasi dependensi
pada rilis berikutnya. Perintah pengelolaan memakai `uv run --no-sync`
agar lingkungan rilis yang sudah disiapkan langsung digunakan. [Sinkronisasi lingkungan uv](https://docs.astral.sh/uv/concepts/projects/sync/)

Contoh unit `/etc/systemd/system/titeni.service` mengikuti [panduan Django dengan Gunicorn](https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/gunicorn/).

```ini
[Unit]
Description=Titeni WSGI
After=network.target

[Service]
User=titeni
Group=titeni
WorkingDirectory=/srv/titeni/app
EnvironmentFile=/etc/titeni/titeni.env
ExecStart=/srv/titeni/app/.venv/bin/gunicorn --bind 127.0.0.1:8000 config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Muat unit dan jalankan layanan.

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now titeni
sudo systemctl status titeni --no-pager
```

Untuk upgrade, jalankan `sudo systemctl restart titeni` setelah
migrasi dan penyiapan aset, lalu periksa statusnya.

Pasang konfigurasi Nginx berikut dalam konteks `http`. Ganti jalur
sertifikat dan pastikan konfigurasi Nginx memuat tipe MIME media statis.
Pertahankan listener Gunicorn di loopback.

```nginx
server {
    listen 80;
    server_name titeni.example.edu;
    return 301 https://titeni.example.edu$request_uri;
}

server {
    listen 443 ssl;
    server_name titeni.example.edu;
    ssl_certificate /etc/nginx/tls/titeni-fullchain.pem;
    ssl_certificate_key /etc/nginx/tls/titeni-key.pem;

    location /static/ {
        alias /srv/titeni/static/;
    }

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Atur default virtual host untuk menolak domain di luar deployment.
Sesuaikan batas ukuran permintaan Nginx dengan formulir unggah yang
digunakan, termasuk overhead multipart untuk PDF sampai 10 MiB.
Periksa konfigurasi sebelum memuat ulang Nginx. [Pengaturan header proxy Nginx](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)

```sh
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

### 6. Verifikasi rilis

```sh
curl -I http://titeni.example.edu/masuk/
curl -I https://titeni.example.edu/masuk/
curl -I https://titeni.example.edu/static/titeni/evidence.css
sudo journalctl -u titeni -n 50 --no-pager
```

- Harapkan pengalihan HTTP ke HTTPS, respons sukses dari halaman masuk
  dan CSS, serta header HSTS pada respons HTTPS aplikasi sesuai setelan.
- Masuk dengan akun uji yang berizin. Periksa halaman prodi dan unduh
  PDF melalui endpoint aplikasi. Pastikan permintaan tanpa sesi diarahkan
  ke halaman masuk dan akun prodi lain ditolak.
- Untuk upgrade, periksa log dan hasil uji sebelum membuka kembali akses.
  Jika perlu pemulihan, gunakan cadangan basis data dan media dari titik
  yang sama. Uji keduanya pada target terisolasi sebelum mengalihkan
  layanan ke target itu.

### Pulihkan akses superuser

Jalankan dari direktori aplikasi dengan lingkungan deployment yang benar.
Untuk produksi, muat konfigurasi lingkungan dan cocokkan target PostgreSQL
seperti pada langkah 3. Jika lupa nama pengguna, tampilkan daftar
superuser aktif dan email masuknya dari terminal yang berwenang.

```sh
uv run --no-sync python manage.py shell -c \
  'from apps.accounts.models import User; print(*User.objects.filter(is_superuser=True, is_active=True).order_by("username").values_list("username", "email"), sep="\n")'
```

Pilih nama pengguna akun yang akan dipulihkan, lalu jalankan perintah berikut.

```sh
uv run --no-sync python manage.py changepassword NAMA_PENGGUNA
```

Masukkan kata sandi baru dua kali di prompt terminal. Masuk kembali melalui
`/masuk/` menggunakan **email akun** dan kata sandi baru.
