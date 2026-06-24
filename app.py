from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from datetime import datetime
from fpdf import FPDF
from PIL import Image
import io, os, tempfile

app = Flask(__name__)
app.secret_key = 'pusaf_secret_key_2026'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Max 50MB total

rekap_data = []  # Simpen sementara, ilang kalo server restart

def format_tanggal(dt_str):
    if not dt_str: return "-"
    try: return datetime.strptime(dt_str, '%Y-%m-%d').strftime('%d-%m-%Y')
    except: return dt_str

def cek_size_file(file_obj, max_mb=1):
    if file_obj is None or file_obj.filename == '':
        return None, None
    file_obj.seek(0, os.SEEK_END)
    size_mb = file_obj.tell() / (1024*1024)
    file_obj.seek(0)
    ext = file_obj.filename.split('.')[-1].lower()
    
    if ext in ['jpg', 'jpeg', 'png'] and size_mb > max_mb:
        return None, f"File {file_obj.filename} terlalu besar: {size_mb:.2f}MB. Max {max_mb}MB untuk gambar"
    return file_obj.read(), file_obj.filename

def add_file_to_pdf_from_bytes(pdf_obj, file_bytes, file_name, title):
    if file_bytes is None: return
    pdf_obj.add_page()
    pdf_obj.set_font("Arial", "B", 14)
    pdf_obj.cell(0, 10, title, 0, 1, "C")
    pdf_obj.ln(5)
    
    ext = file_name.split('.')[-1].lower() if file_name else ""
    
    if ext in ['jpg', 'jpeg', 'png']:
        img = Image.open(io.BytesIO(file_bytes))
        temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        img.convert('RGB').save(temp_img.name)
        
        img_w, img_h = img.size
        page_w = 190
        max_h = 250
        ratio = min(page_w / img_w, max_h / img_h)
        new_w = img_w * ratio
        new_h = img_h * ratio
        x = (210 - new_w) / 2
        
        pdf_obj.image(temp_img.name, x=x, y=30, w=new_w, h=new_h)
        os.unlink(temp_img.name)
    else:
        pdf_obj.set_font("Arial", "", 11)
        pdf_obj.cell(0, 7, f"File terlampir: {file_name}", 0, 1)

def generate_pdf_bukti(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "BUKTI POTONGAN GAJI", 0, 1, "C")
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, f"Tanggal Input: {data['tanggal']}", 0, 1)
    pdf.cell(0, 7, f"Nama Kantor: {data['kantor']}", 0, 1)
    pdf.cell(0, 7, f"Nama Karyawan: {data['karyawan']}", 0, 1)
    pdf.cell(0, 7, f"Jumlah Hari Kerja: {data['hari_kerja']} hari", 0, 1)
    
    if data.get('nama_keluar') or data.get('nama_baru'):
        line = ""
        if data.get('nama_keluar') and data.get('tgl_keluar'):
            line += f"Karyawan Keluar: {data['nama_keluar']} - {format_tanggal(data['tgl_keluar'])}"
        if data.get('nama_baru') and data.get('tgl_masuk'):
            if line: line += " | "
            line += f"Karyawan Baru: {data['nama_baru']} - {format_tanggal(data['tgl_masuk'])}"
        pdf.cell(0, 7, line, 0, 1)
    pdf.ln(5)
    
    rincian = data['rincian']
    ada_potongan = any([rincian.get('bon',0), rincian.get('kredit',0), rincian.get('kecerobohan',0), 
                       rincian.get('bon_prive',0), rincian.get('minus',0), rincian.get('denda',0), 
                       rincian.get('pot_tdk_masuk',0), rincian.get('pot_lain_1',0)] + [p['jumlah'] for p in rincian.get('pot_lain',[])])
    
    if ada_potongan:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "Rincian Potongan:", 0, 1)
        pdf.set_font("Arial", "", 11)
        
        if rincian.get('bon',0) > 0:
            pdf.cell(0, 6, f"- Bon Panjar: Rp {rincian['bon']:,} | Sisa: Rp {rincian['sisa_bon']:,}".replace(",", "."), 0, 1)
        if rincian.get('kredit',0) > 0:
            pdf.cell(0, 6, f"- Kredit Lunak: Rp {rincian['kredit']:,} | Sisa: Rp {rincian['sisa_kredit']:,}".replace(",", "."), 0, 1)
        if rincian.get('kecerobohan',0) > 0:
            pdf.cell(0, 6, f"- Kecerobohan: Rp {rincian['kecerobohan']:,} | Sisa: Rp {rincian['sisa_kecerobohan']:,}".replace(",", "."), 0, 1)
            if rincian.get('ket_kecerobohan'):
                pdf.cell(0, 6, f"  Keterangan: {rincian['ket_kecerobohan']}", 0, 1)
        if rincian.get('bon_prive',0) > 0:
            pdf.cell(0, 6, f"- Bon Prive: Rp {rincian['bon_prive']:,}".replace(",", "."), 0, 1)
        if rincian.get('minus',0) > 0:
            pdf.cell(0, 6, f"- Minus Tunai: Rp {rincian['minus']:,}".replace(",", "."), 0, 1)
        if rincian.get('denda',0) > 0:
            pdf.cell(0, 6, f"- Denda Minus: Rp {rincian['denda']:,}".replace(",", "."), 0, 1)
        if rincian.get('tdk_masuk_hari',0) > 0 and rincian.get('pot_tdk_masuk',0) > 0:
            pdf.cell(0, 6, f"- Tidak Masuk {rincian['tdk_masuk_hari']} hari: Rp {rincian['pot_tdk_masuk']:,}".replace(",", "."), 0, 1)
        if rincian.get('nama_pot_lain_1') and rincian.get('pot_lain_1',0) > 0:
            pdf.cell(0, 6, f"- Lainnya {rincian['nama_pot_lain_1']}: Rp {rincian['pot_lain_1']:,} | Sisa: Rp {rincian['sisa_pot_lain_1']:,}".replace(",", "."), 0, 1)
        for pot in rincian.get('pot_lain',[]):
            if pot['nama'].strip() != "" and pot['jumlah'] > 0:
                pdf.cell(0, 6, f"- Lainnya {pot['nama']}: Rp {pot['jumlah']:,} | Sisa: Rp {pot['sisa']:,}".replace(",", "."), 0, 1)
        
        pdf.ln(3)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, f"TOTAL POTONGAN: Rp {data['total']:,}".replace(",", "."), 0, 1)
    
    if data.get('kritik_saran', '').strip() != "":
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "Kritik & Saran:", 0, 1)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6, data['kritik_saran'])
    
    pdf.ln(8)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, "Mohon karyawan mengirim file PDF ini via WhatsApp ke Bagian Pengurus PUSAF", 0, 1, "C")
    
    add_file_to_pdf_from_bytes(pdf, data.get('ktp_bytes'), data.get('ktp_name'), "LAMPIRAN: KTP KARYAWAN BARU")
    add_file_to_pdf_from_bytes(pdf, data.get('surat_bytes'), data.get('surat_name'), "LAMPIRAN: SURAT KETERANGAN SAKIT")
    add_file_to_pdf_from_bytes(pdf, data.get('filelain_bytes'), data.get('filelain_name'), "LAMPIRAN: FILE LAINNYA")
    
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf.output(temp_pdf.name)
    return temp_pdf.name

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama_kantor = request.form.get('nama_kantor', '').strip()
        nama_karyawan = request.form.get('nama_karyawan', '').strip()
        jumlah_hari_kerja = request.form.get('jumlah_hari_kerja', type=int)
        
        if not nama_kantor or not nama_karyawan or jumlah_hari_kerja is None:
            flash('Nama Kantor, Nama Karyawan & Jumlah Hari Kerja wajib diisi!', 'danger')
            return redirect(url_for('index'))
        
        # Validasi file 1MB
        ktp_bytes, ktp_name = cek_size_file(request.files.get('ktp_baru'), 1)
        surat_bytes, surat_name = cek_size_file(request.files.get('surat_sakit'), 1)
        filelain_bytes, filelain_name = cek_size_file(request.files.get('file_lainnya'), 1)
        
        if isinstance(ktp_name, str) and 'terlalu besar' in ktp_name:
            flash(ktp_name, 'danger'); return redirect(url_for('index'))
        if isinstance(surat_name, str) and 'terlalu besar' in surat_name:
            flash(surat_name, 'danger'); return redirect(url_for('index'))
        if isinstance(filelain_name, str) and 'terlalu besar' in filelain_name:
            flash(filelain_name, 'danger'); return redirect(url_for('index'))
        
        # Hitung potongan
        potongan_bon = request.form.get('potongan_bon', 0, type=int) or 0
        sisa_bon = request.form.get('sisa_bon', 0, type=int) or 0
        potongan_kredit = request.form.get('potongan_kredit', 0, type=int) or 0
        sisa_kredit = request.form.get('sisa_kredit', 0, type=int) or 0
        potongan_kecerobohan = request.form.get('potongan_kecerobohan', 0, type=int) or 0
        sisa_kecerobohan = request.form.get('sisa_kecerobohan', 0, type=int) or 0
        bon_prive = request.form.get('bon_prive', 0, type=int) or 0
        minus_tunai = request.form.get('minus_tunai', 0, type=int) or 0
        denda_minus = request.form.get('denda_minus', 0, type=int) or 0
        jumlah_tidak_masuk = request.form.get('jumlah_tidak_masuk', 0, type=int) or 0
        potongan_tidak_masuk = request.form.get('potongan_tidak_masuk', 0, type=int) or 0
        jumlah_potongan_lain = request.form.get('jumlah_potongan_lain', 0, type=int) or 0
        sisa_potongan_lain = request.form.get('sisa_potongan_lain', 0, type=int) or 0
        
        total_potongan = potongan_bon + potongan_kredit + potongan_kecerobohan + bon_prive + denda_minus + potongan_tidak_masuk + jumlah_potongan_lain
        
        detail_pot_lain = []
        nama_lain = request.form.getlist('nama_lain[]')
        jumlah_lain = request.form.getlist('jumlah_lain[]')
        sisa_lain = request.form.getlist('sisa_lain[]')
        for n, j, s in zip(nama_lain, jumlah_lain, sisa_lain):
            j_int = int(j) if j else 0
            s_int = int(s) if s else 0
            total_potongan += j_int
            if n.strip() and j_int > 0:
                detail_pot_lain.append({"nama": n, "jumlah": j_int, "sisa": s_int})
        
        data_bukti = {
            "tanggal": datetime.now().strftime('%d-%m-%Y %H:%M'),
            "kantor": nama_kantor,
            "karyawan": nama_karyawan,
            "hari_kerja": jumlah_hari_kerja,
            "nama_keluar": request.form.get('nama_keluar', '').strip(),
            "tgl_keluar": request.form.get('tgl_keluar'),
            "nama_baru": request.form.get('nama_baru', '').strip(),
            "tgl_masuk": request.form.get('tgl_masuk'),
            "kritik_saran": request.form.get('kritik_saran', '').strip(),
            "ktp_bytes": ktp_bytes, "ktp_name": ktp_name,
            "surat_bytes": surat_bytes, "surat_name": surat_name,
            "filelain_bytes": filelain_bytes, "filelain_name": filelain_name,
            "rincian": {
                "bon": potongan_bon, "sisa_bon": sisa_bon,
                "kredit": potongan_kredit, "sisa_kredit": sisa_kredit,
                "kecerobohan": potongan_kecerobohan, "sisa_kecerobohan": sisa_kecerobohan,
                "ket_kecerobohan": request.form.get('keterangan_kecerobohan', ''),
                "bon_prive": bon_prive, "minus": minus_tunai, "denda": denda_minus,
                "tdk_masuk_hari": jumlah_tidak_masuk, "pot_tdk_masuk": potongan_tidak_masuk,
                "nama_pot_lain_1": request.form.get('nama_potongan_lain', ''),
                "pot_lain_1": jumlah_potongan_lain, "sisa_pot_lain_1": sisa_potongan_lain,
                "pot_lain": detail_pot_lain
            },
            "total": total_potongan
        }
        
        rekap_data.append(data_bukti)
        pdf_path = generate_pdf_bukti(data_bukti)
        
        return send_file(pdf_path, as_attachment=True, download_name=f"Bukti_{nama_karyawan}_{datetime.now().strftime('%d%m%Y%H%M%S')}.pdf")
    
    return render_template('index.html', rekap_count=len(rekap_data))

@app.route('/rekap')
def rekap():
    if not rekap_data:
        flash('Belum ada data untuk direkap', 'warning')
        return redirect(url_for('index'))
    
    pdf = FPDF()
    for idx, data in enumerate(rekap_data):
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"REKAP #{idx+1} - BUKTI POTONGAN GAJI", 0, 1, "C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 7, f"Tanggal: {data['tanggal']}", 0, 1)
        pdf.cell(0, 7, f"Nama Kantor: {data['kantor']}", 0, 1)
        pdf.cell(0, 7, f"Nama Karyawan: {data['karyawan']}", 0, 1)
        pdf.cell(0, 7, f"Jumlah Hari Kerja: {data['hari_kerja']} hari", 0, 1)
        
        if data.get('nama_keluar') or data.get('nama_baru'):
            line = ""
            if data.get('nama_keluar') and data.get('tgl_keluar'):
                line += f"Karyawan Keluar: {data['nama_keluar']} - {format_tanggal(data['tgl_keluar'])}"
            if data.get('nama_baru') and data.get('tgl_masuk'):
                if line: line += " | "
                line += f"Karyawan Baru: {data['nama_baru']} - {format_tanggal(data['tgl_masuk'])}"
            pdf.cell(0, 7, line, 0, 1)
        pdf.ln(5)
        
        rincian = data['rincian']
        if rincian.get('bon',0) > 0:
            pdf.cell(0, 6, f"- Bon Panjar: Rp {rincian['bon']:,} | Sisa: Rp {rincian['sisa_bon']:,}".replace(",", "."), 0, 1)
        if rincian.get('kredit',0) > 0:
            pdf.cell(0, 6, f"- Kredit Lunak: Rp {rincian['kredit']:,} | Sisa: Rp {rincian['sisa_kredit']:,}".replace(",", "."), 0, 1)
        if rincian.get('kecerobohan',0) > 0:
            pdf.cell(0, 6, f"- Kecerobohan: Rp {rincian['kecerobohan']:,} | Sisa: Rp {rincian['sisa_kecerobohan']:,}".replace(",", "."), 0, 1)
        if rincian.get('bon_prive',0) > 0:
            pdf.cell(0, 6, f"- Bon Prive: Rp {rincian['bon_prive']:,}".replace(",", "."), 0, 1)
        if rincian.get('denda',0) > 0:
            pdf.cell(0, 6, f"- Denda Minus: Rp {rincian['denda']:,}".replace(",", "."), 0, 1)
        if rincian.get('tdk_masuk_hari',0) > 0 and rincian.get('pot_tdk_masuk',0) > 0:
            pdf.cell(0, 6, f"- Tidak Masuk {rincian['tdk_masuk_hari']} hari: Rp {rincian['pot_tdk_masuk']:,}".replace(",", "."), 0, 1)
        if rincian.get('nama_pot_lain_1') and rincian.get('pot_lain_1',0) > 0:
            pdf.cell(0, 6, f"- Lainnya {rincian['nama_pot_lain_1']}: Rp {rincian['pot_lain_1']:,} | Sisa: Rp {rincian['sisa_pot_lain_1']:,}".replace(",", "."), 0, 1)
        for pot in rincian.get('pot_lain',[]):
            if pot['nama'].strip() != "" and pot['jumlah'] > 0:
                pdf.cell(0, 6, f"- Lainnya {pot['nama']}: Rp {pot['jumlah']:,} | Sisa: Rp {pot['sisa']:,}".replace(",", "."), 0, 1)
        
        pdf.ln(3)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, f"TOTAL POTONGAN: Rp {data['total']:,}".replace(",", "."), 0, 1)
        
        if data.get('kritik_saran', '').strip() != "":
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 7, "Kritik & Saran:", 0, 1)
            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(0, 6, data['kritik_saran'])
        
        pdf.ln(8)
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 6, "Mohon karyawan mengirim file PDF ini via WhatsApp ke Bagian Pengurus PUSAF", 0, 1, "C")
        
        add_file_to_pdf_from_bytes(pdf, data.get('ktp_bytes'), data.get('ktp_name'), f"LAMPIRAN KTP - {data['karyawan']}")
        add_file_to_pdf_from_bytes(pdf, data.get('surat_bytes'), data.get('surat_name'), f"LAMPIRAN SURAT SAKIT - {data['karyawan']}")
        add_file_to_pdf_from_bytes(pdf, data.get('filelain_bytes'), data.get('filelain_name'), f"LAMPIRAN LAINNYA - {data['karyawan']}")
    
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf.output(temp_pdf.name)
    return send_file(temp_pdf.name, as_attachment=True, download_name=f"Rekap_Semua_{datetime.now().strftime('%d%m%Y')}.pdf")

if __name__ == '__main__':
    app.run(debug=True)
