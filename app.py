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


def score_sheet(img_bytes, kelas, soal_images=None):
    cli = client()
    if not cli:
        raise RuntimeError("GEMINI_API_KEY belum diatur di Secrets.")

    # Kompres/rescale foto agar upload ke API lebih ringan dan cepat.
    img_bytes = optimize_image_bytes(img_bytes)
    b64 = base64.b64encode(img_bytes).decode("utf-8")

    rubric = "\n".join([f"Soal {k}: {v}" for k, v in RUBRICS[kelas].items()])

    # Foto soal yang diunggah guru menjadi referensi tambahan.
    soal_content = []
    if soal_images:
        soal_content.append({
            "type": "text",
            "text": "Berikut foto soal asli. Gunakan foto-foto ini sebagai acuan untuk mencocokkan pertanyaan dengan jawaban siswa. Jangan mengganti pertanyaan berdasarkan pengetahuan umum."
        })
        for idx, soal_bytes in enumerate(soal_images, start=1):
            soal_b64 = base64.b64encode(
                optimize_image_bytes(soal_bytes, max_side=1400, quality=75)
            ).decode("utf-8")
            soal_content.append({
                "type": "text",
                "text": f"Foto soal {idx}"
            })
            soal_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{soal_b64}"
                }
            })
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
            "content": (
                [{"type": "text", "text": prompt}]
                + soal_content
                + [
                    {
                        "type": "text",
                        "text": "Berikut foto lembar jawaban siswa yang harus dinilai."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}"
                        }
                    }
                ]
            )
        }],
        temperature=0,
        max_tokens=1200
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    vals = {str(i): max(0, min(20, int(data["nilai"].get(str(i), 0)))) for i in range(1,6)}
    data["nilai"] = vals
    data["total"] = sum(vals.values())
    return data

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
    nomor = st.text_input("Nomor/ID siswa (opsional)", placeholder="Contoh: 001")

    st.subheader("📚 Foto Soal")
    st.caption("Upload minimal 5 foto soal. Foto-foto ini akan menjadi referensi AI saat menilai jawaban siswa.")
    foto_soal = st.file_uploader(
        "📎 Upload minimal 5 foto soal",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="foto_soal"
    )

    if foto_soal and len(foto_soal) < 5:
        st.warning(f"⚠️ Baru {len(foto_soal)} foto soal. Minimal 5 foto diperlukan sebelum penilaian.")
    elif foto_soal:
        st.success(f"✅ {len(foto_soal)} foto soal siap digunakan sebagai referensi.")

    foto = st.camera_input("📸 Foto lembar jawaban")
    if foto is None:
        foto = st.file_uploader("Atau pilih foto dari galeri", type=["jpg","jpeg","png","webp"])

    if foto:
        st.image(foto, caption="Foto yang akan diperiksa", use_container_width=True)
        siap_nilai = foto_soal is not None and len(foto_soal) >= 5

        if st.button(
            "🚀 NILAI SEKARANG",
            type="primary",
            use_container_width=True,
            disabled=not siap_nilai
        ):
            with st.spinner("Membaca foto soal + jawaban dan menilai..."):
                try:
                    soal_bytes = [f.getvalue() for f in foto_soal]
                    data = score_sheet(
                        foto.getvalue(),
                        kelas,
                        soal_images=soal_bytes
                    )
                    st.session_state["hasil"] = data
                    save_result(kelas, data, nomor)
                except Exception as e:
                    err = str(e)
                    if "timeout" in err.lower() or "timed out" in err.lower():
                        st.error("⏱️ API terlalu lama merespons (batas 90 detik). Coba foto yang lebih jelas/kecil atau coba lagi.")
                    elif "429" in err or "quota" in err.lower() or "resource_exhausted" in err.lower():
                        st.error("⚠️ Kuota/kredit API sedang habis atau terkena batas penggunaan. Periksa penggunaan API Gemini.")
                    else:
                        st.error(f"❌ Gagal memproses: {err}")

    if "hasil" in st.session_state:
        d = st.session_state["hasil"]
        st.success(f"Total nilai: {d['total']} / 100")
        if d.get("status") == "PERLU CEK":
            st.warning("⚠️ Hasil ini perlu diperiksa kembali karena ada bagian yang kurang terbaca.")
        st.write(f"**Nama:** {d.get('nama','') or '(tidak terbaca)'}")
        rows = []
        for i in range(1,6):
            rows.append({"Soal": f"Soal {i}", "Nilai": d["nilai"][str(i)], "Jawaban terbaca": d.get("jawaban",{}).get(str(i),"")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.info("Nilai otomatis adalah bantuan pemeriksaan. Untuk tulisan yang meragukan, gunakan status PERLU CEK dan periksa foto aslinya.")

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
