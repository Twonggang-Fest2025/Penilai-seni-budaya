
import base64
import json
import os
import sqlite3
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from openai import OpenAI
from PIL import Image, ImageOps

st.set_page_config(page_title="Penilai Seni Budaya 700+", page_icon="📝", layout="centered")

RUBRICS = {
    "X - Seni Rupa": {
        "1": "Pengertian seni: hasil ekspresi/kreativitas manusia untuk menyampaikan perasaan, pikiran, ide, atau gagasan melalui karya.",
        "2": "Prinsip seni rupa dua dimensi: kesatuan, keseimbangan, proporsi, irama, harmoni/keselarasan, penekanan, komposisi.",
        "3": "Tujuh unsur seni rupa: titik, garis, bidang, bentuk, gelap-terang, tekstur, warna.",
        "4": "Empat jenis warna: primer (merah, kuning, biru), sekunder (hijau, jingga/oranye, ungu), tersier (campuran primer dan sekunder), netral (hitam, putih, abu-abu).",
        "5": "Seni rupa murni mengutamakan ekspresi/keindahan; seni rupa terapan memiliki fungsi pakai sekaligus mempertimbangkan keindahan. Contoh: lukisan/patung vs batik/kursi/keramik."
    },
    "XI - Seni Tari": {
        "1": "Seni adalah ekspresi kreatif manusia berupa perasaan, pikiran, ide, atau pengalaman melalui karya; seni menjadi media ekspresi diri.",
        "2": "Tenaga adalah kekuatan/energi gerak; ruang adalah tempat, arah, level, dan jangkauan gerak; waktu adalah tempo, ritme, dan durasi. Ketiganya menentukan karakter, dinamika, dan keindahan tari.",
        "3": "Wiraga = kemampuan/ketepatan gerak; wirama = kesesuaian gerak dengan irama/tempo; wirasa = penghayatan/perasaan dan ekspresi. Ketiganya membentuk tari yang harmonis dan ekspresif.",
        "4": "Gerak imitatif meniru objek/gerakan nyata, misalnya gerak hewan. Gerak imajinatif berasal dari daya khayal/kreativitas dan tidak harus meniru gerak nyata.",
        "5": "Komposisi tari: menentukan ide/tema, eksplorasi, improvisasi/pengembangan, komposisi/penyusunan, pola lantai dan unsur pendukung, evaluasi, lalu presentasi."
    },
    "XII - Seni Musik": {
        "1": "Musik klasik mengikuti tradisi/struktur klasik; tradisional diwariskan turun-temurun dalam masyarakat/daerah; modern mengikuti perkembangan zaman dan gaya masa kini; kontemporer bersifat kekinian, eksploratif dalam bunyi, teknik, ide, atau bentuk.",
        "2": "Unsur musik dalam teks: melodi (tinggi-rendah nada), ritme (pola ketukan drum), tempo (lambat lalu cepat), dinamika (lembut lalu kuat), harmoni (nada serentak/akor), timbre (warna bunyi tiap instrumen), bentuk/struktur (bagian dan pengulangan), tekstur (lapisan/pola bunyi yang berpadu).",
        "3": "Instrumen melodis memainkan melodi; harmonis memainkan nada/akor untuk harmoni/iringan; ritmis memberi atau mengatur ketukan/ritme. Contoh: pianika/seruling, gitar/keyboard, drum/tamborin/gong.",
        "4": "Cara memainkan: dipukul (drum/gong/kendang), dipetik (gitar/kecapi/harpa), digesek (biola/viola/cello), ditiup (seruling/trumpet/saxophone), ditekan (piano/keyboard), digoyang/digetar (angklung/marakas).",
        "5": "Sumber bunyi: idiophone (badan alat), membranophone (selaput), chordophone (dawai/senar), aerophone (udara), electrophone (sistem elektronik)."
    }
}

DB = "nilai_seni_budaya.db"

def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS nilai (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        waktu TEXT, kelas TEXT, nama TEXT, nomor TEXT,
        q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER,
        total INTEGER, status TEXT, catatan TEXT
    )""")
    con.commit()
    return con

def client():
    key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    return OpenAI(
        api_key=key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=90.0,
        max_retries=0
    ) if key else None

def optimize_image_bytes(img_bytes, max_side=1600, quality=78):
    """Resize + compress image before sending it to the API."""
    try:
        img = Image.open(BytesIO(img_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        if max(img.size) > max_side:
            scale = max_side / max(img.size)
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS
            )
        out = BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue()
    except Exception:
        return img_bytes


def score_sheet(img_bytes, kelas):
    cli = client()
    if not cli:
        raise RuntimeError("GEMINI_API_KEY belum diatur di Secrets.")

    img_bytes = optimize_image_bytes(img_bytes)
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    rubric = "\n".join([f"Soal {k}: {v}" for k, v in RUBRICS[kelas].items()])

    prompt = f"""
Anda adalah asisten pemeriksa ujian esai Seni Budaya SMA.
Kelas: {kelas}
Setiap soal bernilai maksimal 20, total 100.

Kunci/rubrik:
{rubric}

Tugas:
1. Baca nama siswa dan kelas/identitas jika terlihat.
2. Baca jawaban nomor 1 sampai 5 dari foto. Jangan mengarang jawaban yang tidak terlihat.
3. Nilai berdasarkan kesesuaian konsep dengan rubrik, bukan kesamaan kata.
4. Jawaban singkat tetapi inti konsep benar tetap mendapat nilai.
5. Jawaban sebagian benar mendapat nilai sebagian.
6. Jika tulisan/foto tidak terbaca, beri status PERLU CEK dan jangan menebak.
7. Nilai tiap soal 0-20 dan total harus merupakan jumlah kelima nilai.
8. Fokus pada lembar jawaban yang sedang diperiksa. Jangan membandingkan dengan siswa lain.

Kembalikan HANYA JSON valid dengan format:
{{
  "nama": "",
  "kelas_terbaca": "",
  "jawaban": {{"1":"","2":"","3":"","4":"","5":""}},
  "nilai": {{"1":0,"2":0,"3":0,"4":0,"5":0}},
  "status": "OK atau PERLU CEK",
  "catatan": ""
}}
"""

    response = cli.chat.completions.create(
        model="gemini-3.8-flash",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}"
                    }
                }
            ]
        }],
        temperature=0,
        max_tokens=1200
    )

    text_response = response.choices[0].message.content.strip()
    if text_response.startswith("```"):
        text_response = text_response.replace("```json", "").replace("```", "").strip()

    data = json.loads(text_response)
    vals = {
        str(i): max(0, min(20, int(data["nilai"].get(str(i), 0))))
        for i in range(1, 6)
    }
    data["nilai"] = vals
    data["total"] = sum(vals.values())
    return data


def score_batch(files, kelas, progress_callback=None):
    """Nilai beberapa lembar secara paralel dengan batas concurrency."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = [None] * len(files)
    max_workers = min(3, len(files))

    def worker(index, file_bytes):
        try:
            data = score_sheet(file_bytes, kelas)
            return index, data, None
        except Exception as e:
            return index, None, str(e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(worker, i, f.getvalue())
            for i, f in enumerate(files)
        ]

        completed = 0
        for future in as_completed(futures):
            index, data, error = future.result()
            results[index] = {"data": data, "error": error}
            completed += 1
            if progress_callback:
                progress_callback(completed, len(files))

    return results

def save_result(kelas, data, nomor=""):
    con = db()
    con.execute("""INSERT INTO nilai
        (waktu,kelas,nama,nomor,q1,q2,q3,q4,q5,total,status,catatan)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), kelas,
         data.get("nama",""), nomor,
         data["nilai"]["1"], data["nilai"]["2"], data["nilai"]["3"],
         data["nilai"]["4"], data["nilai"]["5"], data["total"],
         data.get("status","OK"), data.get("catatan","")))
    con.commit()
    con.close()

st.title("📝 Penilai Otomatis Seni Budaya")
st.caption("Untuk pemeriksaan sekitar 700+ lembar siswa • Gemini AI • 5 soal × 20 poin")

tab1, tab2 = st.tabs(["📷 Nilai dari Foto", "📊 Rekap Nilai"])

with tab1:
    kelas = st.selectbox("Pilih kelas / mata pelajaran", list(RUBRICS.keys()))
    nomor = st.text_input(
        "Nomor/ID awal siswa (opsional)",
        placeholder="Contoh: 001 — jika 10 foto, nomor menjadi 001, 002, 003, dst."
    )

    st.subheader("📷 1. Kamera")
    foto_kamera = st.camera_input("Foto satu lembar jawaban")

    st.subheader("📎 2. Upload Banyak Foto")
    foto_upload = st.file_uploader(
        "Pilih 5–10 foto lembar jawaban sekaligus",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="jawaban_banyak"
    )

    jumlah_upload = len(foto_upload) if foto_upload else 0

    if jumlah_upload:
        st.success(f"✅ {jumlah_upload} lembar jawaban dipilih.")
        if jumlah_upload > 10:
            st.warning("Maksimal 10 foto sekaligus. Hanya 10 foto pertama yang akan dinilai.")

    total_dinilai = jumlah_upload
    if not jumlah_upload and foto_kamera is not None:
        total_dinilai = 1

    if total_dinilai:
        st.info(f"📄 Total yang akan dinilai: {min(total_dinilai, 10)} lembar")

    siap_nilai = (
        (foto_upload is not None and 1 <= len(foto_upload) <= 10)
        or (not foto_upload and foto_kamera is not None)
    )

    if st.button(
        "🚀 NILAI SEMUA LEMBAR",
        type="primary",
        use_container_width=True,
        disabled=not siap_nilai
    ):
        if foto_upload:
            files_to_score = foto_upload[:10]
        else:
            files_to_score = [foto_kamera]

        progress = st.progress(0, text="Menyiapkan penilaian...")
        status_box = st.empty()

        def update_progress(done, total):
            percent = int(done / total * 100)
            progress.progress(
                percent,
                text=f"Menilai {done}/{total} lembar..."
            )
            status_box.info(
                f"⏳ Selesai {done} dari {total} lembar. "
                "Beberapa lembar diproses bersamaan agar lebih cepat."
            )

        try:
            results = score_batch(files_to_score, kelas, update_progress)

            nomor_awal = None
            if nomor.strip().isdigit():
                nomor_awal = int(nomor.strip())

            batch_results = []
            berhasil = 0
            gagal = 0

            for idx, result in enumerate(results):
                data = result["data"]
                error = result["error"]

                if data is not None:
                    if nomor_awal is not None:
                        nomor_siswa = str(nomor_awal + idx).zfill(len(nomor.strip()))
                    else:
                        nomor_siswa = str(idx + 1)

                    save_result(kelas, data, nomor_siswa)
                    batch_results.append({
                        "Lembar": idx + 1,
                        "Nomor": nomor_siswa,
                        "Nama": data.get("nama", "") or "(tidak terbaca)",
                        "Nilai": data["total"],
                        "Status": data.get("status", "OK"),
                        "Catatan": data.get("catatan", "")
                    })
                    berhasil += 1
                else:
                    batch_results.append({
                        "Lembar": idx + 1,
                        "Nomor": str(idx + 1),
                        "Nama": "GAGAL",
                        "Nilai": "-",
                        "Status": "GAGAL",
                        "Catatan": error or "Tidak diketahui"
                    })
                    gagal += 1

            st.session_state["batch_results"] = batch_results
            progress.progress(100, text="✅ Semua lembar selesai diproses.")

            if gagal:
                st.warning(f"Penilaian selesai: {berhasil} berhasil, {gagal} gagal.")
            else:
                st.success(f"🎉 {berhasil} lembar berhasil dinilai.")

        except Exception as e:
            st.error(f"❌ Gagal memproses batch: {e}")

    if "batch_results" in st.session_state:
        st.subheader("📊 Hasil Penilaian Batch")
        st.dataframe(
            pd.DataFrame(st.session_state["batch_results"]),
            use_container_width=True,
            hide_index=True
        )
        st.info(
            "Nilai otomatis adalah bantuan pemeriksaan. "
            "Lembar berstatus PERLU CEK sebaiknya diperiksa kembali dari foto aslinya."
        )


with tab2:
    con = db()
    df = pd.read_sql_query("SELECT * FROM nilai ORDER BY id DESC", con)
    con.close()
    if df.empty:
        st.info("Belum ada hasil penilaian.")
    else:
        kelas_filter = st.selectbox("Filter kelas", ["Semua"] + list(RUBRICS.keys()), key="filter")
        view = df if kelas_filter == "Semua" else df[df["kelas"] == kelas_filter]
        st.metric("Jumlah lembar tersimpan", len(view))
        st.dataframe(view, use_container_width=True, hide_index=True)
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            view.to_excel(writer, index=False, sheet_name="Nilai")
        st.download_button("⬇️ Download Excel", out.getvalue(),
                           file_name="Rekap_Nilai_Seni_Budaya.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

st.divider()
st.caption("Catatan: kunci/rubrik di aplikasi mengikuti soal ASTS Seni Budaya X, XI, XII yang diberikan.")
