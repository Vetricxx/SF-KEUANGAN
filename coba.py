import streamlit as st
import pandas as pd
import os
import pickle
from datetime import datetime
import openpyxl
import io

# ======================== #
# FUNGSI MANAJEMEN USER #
# ======================== #
def load_users():
    if os.path.exists("users.pkl"):
        with open("users.pkl", "rb") as f:
            return pickle.load(f)
    return {}

def save_users(users):
    with open("users.pkl", "wb") as f:
        pickle.dump(users, f)

def login_user(username, password):
    users = load_users()
    return username in users and users[username] == password

def register_user(username, password):
    users = load_users()
    if username in users:
        return False
    users[username] = password
    save_users(users)

    return True

# ======================= #
# LOGIN DAN REGISTRASI #
# ======================= #
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Selamat Datang di Aplikasi Keuangan Sulikan Farm")
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Registrasi"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login berhasil!")
            else:
                st.error("Username atau password salah.")

    with tab2:
        st.subheader("Registrasi")
        new_username = st.text_input("Username baru")
        new_password = st.text_input("Password baru", type="password")
        if st.button("Daftar"):
            if register_user(new_username, new_password):
                st.success("Registrasi berhasil! Silakan login.")
            else:
                st.error("Username sudah digunakan.")
    st.stop()

# Fungsi menyimpan session state ke file 
def simpan_session_state():
    with open("session_state.pkl", "wb") as f:
        pickle.dump(dict(st.session_state), f)

# Fungsi memuat session state dari file 
def muat_session_state():
    if os.path.exists("session_state.pkl"):
        with open("session_state.pkl", "rb") as f:
            data = pickle.load(f)
            for k, v in data.items():
                if k not in st.session_state:
                    st.session_state[k] = v
                    
# Fungsi untuk menghapus session state file 
def hapus_session_state_file():
    if os.path.exists("session_state.pkl"):
        os.remove("session_state.pkl")

# Fungsi untuk menyimpan semua data ke file Excel
def simpan_semua_ke_excel():
    if not st.session_state.get("jurnal"):
        return None, None

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

        # --- JURNAL UMUM --- #
        df_jurnal = pd.DataFrame(st.session_state.jurnal)
        df_jurnal.to_excel(writer, sheet_name="Jurnal Umum", index=False)

        # --- BUKU BESAR --- #
        akun_list = df_jurnal["Akun"].unique()
        buku_besar_all = []

        for akun in akun_list:
            df_akun = df_jurnal[df_jurnal["Akun"] == akun].copy()
            df_akun["Saldo"] = df_akun["Debit"] - df_akun["Kredit"]
            df_akun["Saldo Akumulatif"] = df_akun["Saldo"].cumsum()
            df_akun.insert(0, "Nama Akun", akun)  # Tambahkan kolom identifikasi akun
            buku_besar_all.append(df_akun)

        df_buku_besar = pd.concat(buku_besar_all, ignore_index=True)
        df_buku_besar.to_excel(writer, sheet_name="Buku Besar", index=False)

        # --- NERACA SALDO --- #
        ref_dict = df_jurnal.groupby("Akun")["Ref"].first().to_dict()

        neraca_saldo = df_jurnal.groupby("Akun")[["Debit", "Kredit"]].sum().reset_index()
        neraca_saldo["Saldo"] = neraca_saldo["Debit"] - neraca_saldo["Kredit"]
        neraca_saldo["Ref"] = neraca_saldo["Akun"].map(ref_dict)
        neraca_saldo = neraca_saldo.sort_values(by="Ref")
        cols = ["Ref", "Akun", "Debit", "Kredit", "Saldo"]
        neraca_saldo = neraca_saldo[cols]
        neraca_saldo.to_excel(writer, sheet_name="Neraca Saldo", index=False)
        
        # --- LABA RUGI --- #
        # --- LABA RUGI (Gabung semua kategori + total laba/rugi bersih) --- #
        if "data_laba_rugi" in st.session_state:
            laba_rugi_all = []

            for kategori, data in st.session_state.data_laba_rugi.items():
                df = pd.DataFrame(data)
                if not df.empty:
                    df.insert(0, "Kategori", kategori)
                    laba_rugi_all.append(df)

            if laba_rugi_all:
                df_laba_rugi = pd.concat(laba_rugi_all, ignore_index=True)

                # Hitung laba/rugi bersih #
                total_pendapatan = df_laba_rugi[df_laba_rugi["Kategori"] == "Pendapatan"]["Nominal"].sum()
                total_beban = df_laba_rugi[df_laba_rugi["Kategori"] != "Pendapatan"]["Nominal"].sum()
                laba_bersih = total_pendapatan - total_beban

                # Tambahkan baris laba/rugi bersih #
                df_laba_bersih = pd.DataFrame([{
                    "Kategori": "",
                    "Deskripsi": "Laba/Rugi Bersih",
                    "Nominal": laba_bersih
                }])

                # Gabungkan semua data + laba rugi bersih di akhir #
                df_output = pd.concat([df_laba_rugi, pd.DataFrame([{}]), df_laba_bersih], ignore_index=True)
                df_output.to_excel(writer, sheet_name="Laporan Laba Rugi", index=False)

        # --- PERUBAHAN MODAL --- #
        if (
            st.session_state.get("modal_awal") is not None and
            st.session_state.get("laba") is not None and
            st.session_state.get("prive") is not None
        ):
            ekuitas_akhir = (
                st.session_state.modal_awal +
                st.session_state.laba -
                st.session_state.prive
            )
            df_ekuitas = pd.DataFrame([{
                "Modal Awal": st.session_state.modal_awal,
                "Laba": st.session_state.laba,
                "Prive": st.session_state.prive,
                "Ekuitas Akhir": ekuitas_akhir
            }])
            df_ekuitas.to_excel(writer, sheet_name="Perubahan Ekuitas", index=False)

        # --- NERACA (Laporan Posisi Keuangan) --- #
        if "neraca" in st.session_state:
            all_data = []
            for kategori, data in st.session_state.neraca.items():
                df = pd.DataFrame(data)
                if not df.empty:
                    df['Kategori'] = kategori  # Tambahkan kolom kategori
                    all_data.append(df)

            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                combined_df.to_excel(writer, sheet_name="Neraca", index=False)

        # --- JURNAL PENUTUP --- #
        if "jurnal_penutup" in st.session_state and st.session_state.jurnal_penutup:
            df_jp = pd.DataFrame(st.session_state.jurnal_penutup)
            if not df_jp.empty:
             df_jp['Kategori'] = "Jurnal Penutup"
            df_jp.to_excel(writer, sheet_name="Jurnal Penutup", index=False)

        # --- NERACA SALDO SETELAH PENUTUPAN --- #
        if "neraca_saldo_setelah_penutupan" in st.session_state and st.session_state.neraca_saldo_setelah_penutupan:
            df_nssp = pd.DataFrame(st.session_state.neraca_saldo_setelah_penutupan)
            if not df_nssp.empty:
             df_nssp['Kategori'] = "Neraca Saldo Setelah Penutupan"
            df_nssp.to_excel(writer, sheet_name="Neraca Saldo Setelah Penutupan", index=False)


    buffer.seek(0)
    filename = "laporan_keuangan.xlsx"
    return buffer, filename

    # Ambil tanggal pertama dari jurnal
    df_jurnal = pd.DataFrame(st.session_state.jurnal)
    tanggal_pertama = pd.to_datetime(df_jurnal["Tanggal"]).min().strftime("%d-%b-%Y")

    # Buat nama file
    nama_file = f"laporan_keuangan_{tanggal_pertama}.xlsx"

    with pd.ExcelWriter(nama_file, engine="openpyxl") as writer:
        df_jurnal.to_excel(writer, index=False, sheet_name="Jurnal")
         

        # Simpan Jurnal Umum
        df_jurnal(writer, sheet_name="Jurnal Umum", index=False)

        # Buku Besar
        akun_list = df_jurnal["Akun"].unique()
        for akun in akun_list:
            df_akun = df_jurnal[df_jurnal["Akun"] == akun].copy()
            df_akun["Saldo"] = df_akun["Debit"] - df_akun["Kredit"]
            df_akun["Saldo Akumulatif"] = df_akun["Saldo"].cumsum()
            df_akun(writer, sheet_name=f"Buku Besar - {akun[:30]}", index=False)

        # Neraca Saldo
        neraca_saldo = df_jurnal.groupby("Akun")[["Debit", "Kredit"]].sum().reset_index()
        neraca_saldo["Saldo"] = neraca_saldo["Debit"] - neraca_saldo["Kredit"]
        neraca_saldo(writer, sheet_name="Neraca Saldo", index=False)

        # Laba Rugi
        if "data_laba_rugi" in st.session_state:
            for kategori, data in st.session_state.data_laba_rugi.items():
                df = pd.DataFrame(data)
                if not df.empty:
                    df(writer, sheet_name=f"Laba Rugi - {kategori[:30]}", index=False)

        # Perubahan Modal
        if st.session_state.modal_awal is not None:
            df_ekuitas = pd.DataFrame([{
                "Modal Awal": st.session_state.modal_awal,
                "Laba": st.session_state.laba,
                "Prive": st.session_state.prive,
                "Modal Akhir": st.session_state.modal_awal + st.session_state.laba - st.session_state.prive
            }])
            df_ekuitas(writer, sheet_name="Perubahan Modal", index=False)

        # Laporan Posisi Keuangan (Neraca)
        if "Laporan posisi keuangan" in st.session_state:
            for kategori, data in st.session_state["posisi keuangan"].items():
                df = pd.DataFrame(data)
                if not df.empty:
                    df(writer, sheet_name=f"Laporan posisi keuangan - {kategori[:30]}", index=False)

        # Jurnal Penutup
        if "jurnal_penutup" in st.session_state and st.session_state.jurnal_penutup:
            df_jurnal_penutup = pd.DataFrame(st.session_state.jurnal_penutup)
            df_jurnal_penutup(writer, sheet_name="Jurnal Penutup", index=False)

        # Neraca Saldo Setelah Penutupan 
        if "neraca_saldo_setelah_penutupan" in st.session_state:
            df_nssp = pd.DataFrame(st.session_state.neraca_saldo_setelah_penutupan)
            if not df_nssp.empty :
                df_nssp(writer, sheet_name="Neraca Saldo Setelah Penutupan", index=False)


    return nama_file


# === PANGGIL DI SINI (SEBELUM st.title(), st.sidebar, dst.) ===
muat_session_state()

st.set_page_config(page_title="LAPORAN KEUANGAN SULIKAN FARM", layout="wide")
st.title("LAPORAN KEUANGAN TERNAK KALKUN SEMARANG")

st.sidebar.markdown("<h2 style='text-align: center;'><br>LAPORAN KEUANGAN<br>SULIKAN FARM</h2>", unsafe_allow_html=True)

menu = st.sidebar.radio("Pilih Navigasi:", (
    "Beranda",
    "Jurnal Umum",
    "Buku Besar",
    "Neraca Saldo",
    "Laporan Laba Rugi",
    "Laporan Perubahan Modal",
    "Laporan Posisi Keuangan",
    "Jurnal Penutup",
    "Neraca Saldo Setelah Penutupan",
    "Unduh Data"

))

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.username = None


if menu == "Beranda":
    st.title("Selamat Datang di Laporan Keuangan SULIKAN FARM")
    st.markdown("""
        ### Deskripsi Aplikasi
        Aplikasi ini dirancang untuk membantu Anda untuk mengelola dan menyusun laporan keuangan ternak kalkun dengan mudah dan efisien.  
        Dengan fitur-fitur yang lengkap, Anda dapat mencatat transaksi, melihat laporan keuangan, dan mengunduh data dalam format Excel.
        Anda dapat mengelola:
        - Jurnal Umum
        - Buku Besar
        - Neraca Saldo
        - Laporan Laba Rugi
        - Perubahan Modal
        - Laporan Posisi Keuangan
        - Jurnal Penutup
        - Neraca Saldo Setelah Penutupan
        - Unduh Data

        ### Petunjuk Penggunaan
        1. Masukkan transaksi melalui Jurnal Umum.
        2. Data akan otomatis terhubung ke Buku Besar dan Neraca Saldo.
        3. Untuk laporan laba rugi, perubahan ekuitas dan neraca, gunakan menu input manual.
        4. Gunakan tombol reset di tiap halaman untuk memulai data baru.

        ### Catatan
        - Pastikan jurnal Anda seimbang (total debit = total kredit).
        - Pastikan menginput dengan teliti dan cek secara berkala.
    """)

    st.info("Gunakan menu di sidebar untuk mulai mencatat dan melihat laporan keuangan Anda.")

# --- JURNAL UMUM ---
if menu == "Jurnal Umum":
    st.header("Jurnal Umum")
    if "jurnal" not in st.session_state:
        st.session_state.jurnal = []

    with st.form("form_jurnal"):
        st.subheader("Input Transaksi Jurnal")
        tanggal = st.date_input("Tanggal", value=datetime.today())
        keterangan = st.text_input("Akun")
        akun = st.text_input("Ref")
        debit = st.number_input("Debit", min_value=0.0, format="%.2f")
        kredit = st.number_input("Kredit", min_value=0.0, format="%.2f")
        submitted = st.form_submit_button("Tambah")

        if submitted:
            if akun:
                st.session_state.jurnal.append({
                    "Tanggal": tanggal.strftime("%Y-%m-%d"),
                    "Akun": keterangan,
                    "Ref": akun,
                    "Debit": debit,
                    "Kredit": kredit
                })
                simpan_session_state()
            else:
                st.warning("Nama akun tidak boleh kosong!")

    if st.session_state.jurnal:
        df_jurnal = pd.DataFrame(st.session_state.jurnal)
        st.dataframe(df_jurnal, use_container_width=True)
        st.subheader("Edit Jurnal Jika Perlu:")
        df_edit = st.data_editor(df_jurnal, num_rows="dynamic", use_container_width=True, key="edit_jurnal")
        if st.button("Simpan Perubahan Jurnal"):
            st.session_state.jurnal = df_edit.to_dict(orient="records")
            simpan_session_state()
            st.success("Perubahan jurnal berhasil disimpan.")

        total_debit = df_jurnal["Debit"].sum()
        total_kredit = df_jurnal["Kredit"].sum()

        col1, col2 = st.columns(2)
        col1.metric("Total Debit", f"{total_debit:,.2f}")
        col2.metric("Total Kredit", f"{total_kredit:,.2f}")

        if total_debit == total_kredit:
            st.success("Jurnal seimbang!")
        else:
            st.error("Jurnal tidak seimbang!")

    if st.button("Reset Semua Data"):
        st.session_state.jurnal = []
        hapus_session_state_file()
        st.success("Data jurnal berhasil direset.")
        st.rerun()

# --- BUKU BESAR ---
elif menu == "Buku Besar":
    st.header("Buku Besar")

    if "jurnal" not in st.session_state or not st.session_state.jurnal:
        st.info("Belum ada data jurnal.")
    else:
        df_jurnal = pd.DataFrame(st.session_state.jurnal)
        akun_unik = df_jurnal["Akun"].unique()
        akun_dipilih = st.selectbox("Pilih Akun", akun_unik)

        df_akun = df_jurnal[df_jurnal["Akun"] == akun_dipilih].copy()
        df_akun["Saldo"] = (df_akun["Debit"] - df_akun["Kredit"]).cumsum()

        st.subheader(f"Buku Besar: {akun_dipilih}")
        st.dataframe(df_akun[["Tanggal", "Ref", "Debit", "Kredit", "Saldo"]], use_container_width=True)

        total_debit = df_akun["Debit"].sum()
        total_kredit = df_akun["Kredit"].sum()

        col1, col2 = st.columns(2)
        col1.metric("Total Debit", f"{total_debit:,.2f}")
        col2.metric("Total Kredit", f"{total_kredit:,.2f}")


# --- NERACA SALDO ---
elif menu == "Neraca Saldo":
    st.header("Neraca Saldo")

    if "jurnal" in st.session_state and st.session_state.jurnal:
        df_jurnal = pd.DataFrame(st.session_state.jurnal).sort_values(by=["Ref", "Tanggal"])

        # Hitung saldo akumulatif terakhir per akun
        akun_list = df_jurnal["Akun"].unique()
        saldo_akhir_list = []

        for akun in akun_list:
            df_akun = df_jurnal[df_jurnal["Akun"] == akun].copy()
            df_akun["Saldo"] = df_akun["Debit"] - df_akun["Kredit"]
            df_akun["Saldo Akumulatif"] = df_akun["Saldo"].cumsum()
            saldo_akhir = df_akun["Saldo Akumulatif"].iloc[-1]

            # Ambil referensi dari entri pertama akun tsb
            ref = df_akun["Ref"].iloc[0]

            # Bagi ke debit/kredit sesuai saldo
            debit = saldo_akhir if saldo_akhir >= 0 else 0
            kredit = -saldo_akhir if saldo_akhir < 0 else 0

            saldo_akhir_list.append({
                "Ref": ref,
                "Akun": akun,
                "Debit": debit,
                "Kredit": kredit
            })

        df_saldo = pd.DataFrame(saldo_akhir_list)
        df_saldo = df_saldo.sort_values(by="Ref")

        total_debit = df_saldo["Debit"].sum()
        total_kredit = df_saldo["Kredit"].sum()

        # Tambahkan baris total
        total_row = pd.DataFrame({
            "Ref": ["TOTAL"],
            "Akun": [""],
            "Debit": [total_debit],
            "Kredit": [total_kredit]
        })

        df_saldo_tampil = pd.concat([df_saldo, total_row], ignore_index=True)

        st.dataframe(df_saldo_tampil[["Ref", "Akun", "Debit", "Kredit"]], use_container_width=True)

        # Validasi keseimbangan
        if total_debit == total_kredit:
            st.success("✅ Neraca Saldo Seimbang")
        else:
            st.error(f"❌ Neraca Saldo Tidak Seimbang — Selisih: Rp {abs(total_debit - total_kredit):,.2f}")

    else:
        st.info("Belum ada data jurnal untuk dihitung.")


# --- LAPORAN LABA RUGI ---
elif menu == "Laporan Laba Rugi":
    st.header("Laporan Laba Rugi")

    if "jurnal" in st.session_state and st.session_state.jurnal:
        df_jurnal = pd.DataFrame(st.session_state.jurnal)

        akun_pendapatan = df_jurnal[df_jurnal["Akun"].str.contains("Pendapatan", case=False)]
        akun_beban = df_jurnal[df_jurnal["Akun"].str.contains("Beban", case=False)]

        total_pendapatan = akun_pendapatan["Kredit"].sum()
        total_beban = akun_beban["Debit"].sum()
        laba_bersih = total_pendapatan - total_beban

        st.subheader("Ringkasan")
        st.metric("Total Pendapatan", f"{total_pendapatan:,.2f}")
        st.metric("Total Beban", f"{total_beban:,.2f}")
        st.metric("Laba Bersih", f"{laba_bersih:,.2f}")

        st.subheader("Detail Pendapatan dan Beban")
        st.write("**Pendapatan**")
        st.dataframe(akun_pendapatan, use_container_width=True)
        st.write("**Beban**")
        st.dataframe(akun_beban, use_container_width=True)

    else:
        st.info("Belum ada data jurnal.")

# --- LAPORAN PERUBAHAN MODAL ---
elif menu == "Laporan Perubahan Modal":
    st.header("Laporan Perubahan Modal")

    if "jurnal" in st.session_state and st.session_state.jurnal:
        df_jurnal = pd.DataFrame(st.session_state.jurnal)

        # Modal awal
        modal_awal = df_jurnal[df_jurnal["Akun"].str.contains("Modal", case=False)]["Kredit"].sum()

        # Prive
        prive = df_jurnal[df_jurnal["Akun"].str.contains("Prive", case=False)]["Debit"].sum()

        # Ambil laba rugi dari halaman sebelumnya (langsung hitung ulang)
        pendapatan = df_jurnal[df_jurnal["Akun"].str.contains("Pendapatan", case=False)]["Kredit"].sum()
        beban = df_jurnal[df_jurnal["Akun"].str.contains("Beban", case=False)]["Debit"].sum()
        laba_bersih = pendapatan - beban

        modal_akhir = modal_awal + laba_bersih - prive

        st.write(f"**Modal Awal:** Rp {modal_awal:,.2f}")
        st.write(f"**Laba Bersih:** Rp {laba_bersih:,.2f}")
        st.write(f"**Prive:** Rp {prive:,.2f}")
        st.write(f"**Modal Akhir:** Rp {modal_akhir:,.2f}")

    else:
        st.info("Belum ada data jurnal.")

# --- LAPORAN POSISI KEUANGAN ---
elif menu == "Laporan Posisi Keuangan":
    st.header("Laporan Posisi Keuangan (Neraca)")

    if "jurnal" in st.session_state and st.session_state.jurnal:
        df_jurnal = pd.DataFrame(st.session_state.jurnal)
        df_jurnal = df_jurnal.sort_values(by=["Ref", "Tanggal"])

        akun_list = df_jurnal["Akun"].unique()
        saldo_akhir_list = []

        for akun in akun_list:
            df_akun = df_jurnal[df_jurnal["Akun"] == akun].copy()
            df_akun["Saldo"] = df_akun["Debit"] - df_akun["Kredit"]
            df_akun["Saldo Akumulatif"] = df_akun["Saldo"].cumsum()
            saldo_akhir = df_akun["Saldo Akumulatif"].iloc[-1]
            ref = df_akun["Ref"].iloc[0]
            debit = saldo_akhir if saldo_akhir >= 0 else 0
            kredit = -saldo_akhir if saldo_akhir < 0 else 0
            saldo_akhir_list.append({"Ref": ref, "Akun": akun, "Debit": debit, "Kredit": kredit})

        df_neraca = pd.DataFrame(saldo_akhir_list)
        df_neraca = df_neraca.sort_values(by="Ref")

        st.dataframe(df_neraca, use_container_width=True)
    else:
        st.info("Belum ada data jurnal.")

# --- JURNAL PENUTUP ---
elif menu == "Jurnal Penutup":
    st.header("Jurnal Penutup")

    if "jurnal" in st.session_state and st.session_state.jurnal:
        df_jurnal = pd.DataFrame(st.session_state.jurnal)

        # Filter akun nominal
        pendapatan = df_jurnal[df_jurnal["Akun"].str.contains("Pendapatan", case=False)]
        beban = df_jurnal[df_jurnal["Akun"].str.contains("Beban", case=False)]
        prive = df_jurnal[df_jurnal["Akun"].str.contains("Prive", case=False)]

        # Hitung laba bersih
        total_pendapatan = pendapatan["Kredit"].sum()
        total_beban = beban["Debit"].sum()
        laba_bersih = total_pendapatan - total_beban

        # Buat jurnal penutup
        penutup = []
        for i, row in pendapatan.iterrows():
            penutup.append({"Tanggal": row["Tanggal"], "Akun": row["Akun"], "Ref": row["Ref"], "Debit": row["Kredit"], "Kredit": 0})
        for i, row in beban.iterrows():
            penutup.append({"Tanggal": row["Tanggal"], "Akun": row["Akun"], "Ref": row["Ref"], "Debit": 0, "Kredit": row["Debit"]})

        penutup.append({"Tanggal": datetime.today().strftime("%Y-%m-%d"), "Akun": "Ikhtisar Laba Rugi", "Ref": "IK", "Debit": total_pendapatan - total_beban, "Kredit": 0})
        penutup.append({"Tanggal": datetime.today().strftime("%Y-%m-%d"), "Akun": "Modal", "Ref": "MOD", "Debit": 0, "Kredit": total_pendapatan - total_beban})

        if not prive.empty:
            for i, row in prive.iterrows():
                penutup.append({"Tanggal": row["Tanggal"], "Akun": "Modal", "Ref": "MOD", "Debit": row["Debit"], "Kredit": 0})
                penutup.append({"Tanggal": row["Tanggal"], "Akun": "Prive", "Ref": row["Ref"], "Debit": 0, "Kredit": row["Debit"]})

        df_penutup = pd.DataFrame(penutup)
        st.dataframe(df_penutup, use_container_width=True)
    else:
        st.info("Belum ada data jurnal.")

# --- NERACA SALDO SETELAH PENUTUPAN ---
elif menu == "Neraca Saldo Setelah Penutupan":
    st.header("Neraca Saldo Setelah Penutupan")

    if "jurnal" in st.session_state and st.session_state.jurnal:
        df_jurnal = pd.DataFrame(st.session_state.jurnal)

        akun_tutup = ["Pendapatan", "Beban", "Prive"]
        df_filtered = df_jurnal[~df_jurnal["Akun"].str.contains('|'.join(akun_tutup), case=False)]

        akun_list = df_filtered["Akun"].unique()
        saldo_akhir_list = []

        for akun in akun_list:
            df_akun = df_filtered[df_filtered["Akun"] == akun].copy()
            df_akun["Saldo"] = df_akun["Debit"] - df_akun["Kredit"]
            df_akun["Saldo Akumulatif"] = df_akun["Saldo"].cumsum()
            saldo_akhir = df_akun["Saldo Akumulatif"].iloc[-1]
            ref = df_akun["Ref"].iloc[0]
            debit = saldo_akhir if saldo_akhir >= 0 else 0
            kredit = -saldo_akhir if saldo_akhir < 0 else 0
            saldo_akhir_list.append({"Ref": ref, "Akun": akun, "Debit": debit, "Kredit": kredit})

        df_saldo_akhir = pd.DataFrame(saldo_akhir_list)
        df_saldo_akhir = df_saldo_akhir.sort_values(by="Ref")

        total_debit = df_saldo_akhir["Debit"].sum()
        total_kredit = df_saldo_akhir["Kredit"].sum()

        st.dataframe(df_saldo_akhir, use_container_width=True)

        if total_debit == total_kredit:
            st.success("✅ Neraca Saldo Setelah Penutupan Seimbang")
        else:
            st.error(f"❌ Neraca Saldo Tidak Seimbang — Selisih: Rp {abs(total_debit - total_kredit):,.2f}")

    else:
        st.info("Belum ada data jurnal.")

       
# --- UNDUH DATA ---
elif menu == "Unduh Data":
    st.title("Unduh Laporan Keuangan")

    if st.button("Simpan ke Excel"):
        excel_io, filename = simpan_semua_ke_excel()
        if excel_io:
            st.session_state.excel_io = excel_io
            st.session_state.excel_filename = filename
            st.success("File berhasil dibuat, silakan unduh di bawah.")
        else:
            st.warning("Tidak ada data jurnal untuk disimpan.")

    if "excel_io" in st.session_state and "excel_filename" in st.session_state:
        st.download_button(
            label="📥 Unduh Laporan Keuangan Excel",
            data=st.session_state.excel_io,
            file_name=st.session_state.excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Klik tombol 'Simpan ke Excel' terlebih dahulu untuk membuat file.")