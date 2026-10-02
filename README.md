# Aplikasi Penilai Otomatis Seni Budaya — 700+ Siswa

Versi online/mobile untuk membantu memeriksa lembar jawaban esai Seni Budaya kelas X, XI, XII.

## Fitur
- Foto langsung dari kamera HP atau unggah dari galeri.
- 5 soal, masing-masing maksimal 20 poin.
- Penilaian berdasarkan konsep/rubrik, bukan kecocokan kata persis.
- Status PERLU CEK jika bagian jawaban kurang terbaca.
- Rekap nilai dan ekspor Excel.
- Tidak dibatasi 700 siswa secara logika aplikasi.

## Deploy
Paling mudah menggunakan Streamlit Community Cloud:
1. Buat repository GitHub dan unggah `app.py` serta `requirements.txt`.
2. Buka https://share.streamlit.io dan masuk.
3. Pilih Create app → repository → `app.py` → Deploy.
4. Di App settings/Secrets, masukkan:
   OPENAI_API_KEY = "API_KEY_ANDA"
5. Buka URL `*.streamlit.app` dari HP.

Jangan menaruh API key langsung di `app.py` atau repository.

## Catatan data
Versi ini memakai SQLite lokal. Untuk penggunaan jangka panjang dengan banyak perangkat, sebaiknya database persisten (misalnya Supabase/Google Sheets/database cloud) dipasang pada tahap berikutnya. Hasil yang sudah tampil dapat diekspor ke Excel.

## Rubrik
Rubrik sudah disusun dari soal ASTS Seni Budaya:
- X: Seni Rupa
- XI: Seni Tari
- XII: Seni Musik
