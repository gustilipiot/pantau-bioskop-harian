import sys
import asyncio

# 🛡️ FIX WINDOWS PROACTOR EVENT LOOP CONNECTION RESET ERROR (WINERROR 10054)
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import re
import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Pantau Bioskop Harian",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Pantau Bioskop Harian")

# ==========================================
# CONSTANT: LINK PUBLISHED KAPASITAS SEAT (SHEET2)
# ==========================================
CAPACITY_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRIs81ypiEpR41DPPHCLVD6L4FTARZmEBfAebetI9hM2XsyRuQuDpyVaK95_pL-GQ/pub?gid=755835940&single=true&output=csv"

# ==========================================
# SIDEBAR NAVIGASI MODE
# ==========================================
st.sidebar.header("📌 Pilih Mode Analytics")
app_mode = st.sidebar.radio(
    "Pilih Jenis Data / Dashboard:",
    ["Showtime Harian", "Advance Ticket Sales (ATS)"],
)


# ==========================================
# HELPER: GROUPING JARINGAN BIOSKOP
# ==========================================
def map_jaringan_bioskop(bioskop_name):
    """Mengelompokkan cabang bioskop ke Induk Jaringan (Brand)."""
    name_upper = str(bioskop_name).upper().strip()

    if "PAKUWON" in name_upper and ("IMAX" in name_upper or "XXI" in name_upper or "REGULAR" in name_upper):
        return "Cinema XXI"

    cgv_malls = [
        "CGV", "BLITZ", "JWALK", "J-WALK", "PAKUWON MALL JOGJA", "PAKUWON JOGJA", 
        "BELLA TERRA", "CENTRAL PARK", "GRAND INDONESIA", "23 PASKAL", "PASKAL", 
        "BEC", "PARIS VAN JAVA", "PVJ", "FOCAL POINT", "FOCAL", "PLAZA MULIA"
    ]

    if any(keyword in name_upper for keyword in cgv_malls):
        return "CGV"
    elif "PLATINUM" in name_upper:
        return "Platinum"
    elif (
        "XXI" in name_upper
        or "PREMIERE" in name_upper
        or "IMAX" in name_upper
        or "21" in name_upper
    ):
        return "Cinema XXI"
    elif "CINEPOLIS" in name_upper or "CINEMEXX" in name_upper:
        return "Cinepolis"
    elif "NSC" in name_upper:
        return "NSC"
    elif "KOTA CINEMA" in name_upper or "KCM" in name_upper:
        return "Kota Cinema Mall"
    elif "FLIX" in name_upper:
        return "FLIX Cinema"
    elif "GOLDEN" in name_upper:
        return "Golden Theater"
    else:
        first_word = name_upper.split()[0].title() if name_upper else "Lainnya"
        return first_word if len(first_word) > 2 else "Lainnya / Independen"


def clean_show_num_int(val):
    """Normalisasi format Sesi Show menjadi integer murni 1, 2, 3, 4, 5."""
    s = str(val).upper().strip()
    
    if re.search(r"\b(SHOW\s*1|SHOW\s*I|SHOW\s*01)\b", s):
        return 1
    elif re.search(r"\b(SHOW\s*2|SHOW\s*II|SHOW\s*02)\b", s):
        return 2
    elif re.search(r"\b(SHOW\s*3|SHOW\s*III|SHOW\s*03)\b", s):
        return 3
    elif re.search(r"\b(SHOW\s*4|SHOW\s*IV|SHOW\s*04)\b", s):
        return 4
    elif re.search(r"\b(SHOW\s*5|SHOW\s*V|SHOW\s*05)\b", s):
        return 5
        
    match = re.search(r"\d+", s)
    if match:
        num = int(match.group(0))
        return num if 1 <= num <= 10 else 1
    return 1


def clean_bioskop_string(name):
    """Pembersihan nama bioskop secara mendalam untuk matching."""
    s = str(name).upper().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    stop_words = [
        "XXI", "IMAX", "PREMIERE", "CINEMA", "THEATER", "21", 
        "LIFESTYLE", "CENTER", "MALL", "SHOPPING", "REGULAR", 
        "AND", "&", "CINEPOLIS", "FLIX", "PLATINUM", "KCM"
    ]
    words = [w for w in s.split() if w not in stop_words and len(w) > 1]
    return " ".join(words)


# ==========================================
# HELPER: LOAD DATA KAPASITAS SEAT
# ==========================================
@st.cache_data(ttl=3600)
def load_capacity_data(url):
    """Membaca data kapasitas kursi dari Published Google Sheets CSV (XXI & CGV)."""
    try:
        df_cap = pd.read_csv(url)
        df_cap.columns = [str(c).strip().upper() for c in df_cap.columns]
        
        bioskop_col = None
        for col in df_cap.columns:
            if "XXI" in col or "CGV" in col or "BIOSKOP" in col or "NAMA" in col or "LOKASI" in col:
                bioskop_col = col
                break
        if not bioskop_col:
            bioskop_col = df_cap.columns[0]

        val_cols = [c for c in df_cap.columns if c != bioskop_col]

        melted_cap = pd.melt(
            df_cap,
            id_vars=[bioskop_col],
            value_vars=val_cols,
            var_name="Sesi_Show_Raw",
            value_name="Kapasitas_Seat"
        )
        
        melted_cap.rename(columns={bioskop_col: "Bioskop_Cap_Raw"}, inplace=True)
        melted_cap["Bioskop_Cap_Clean"] = melted_cap["Bioskop_Cap_Raw"].apply(clean_bioskop_string)
        melted_cap["Show_Num_Int"] = melted_cap["Sesi_Show_Raw"].apply(clean_show_num_int)
        
        melted_cap["Kapasitas_Seat"] = pd.to_numeric(melted_cap["Kapasitas_Seat"], errors="coerce").fillna(0).astype(int)
        
        return melted_cap
    except Exception as e:
        st.error(f"Gagal memuat data kapasitas dari Google Sheets: {e}")
        return pd.DataFrame()


# ==========================================
# 1. HELPER SHOWTIME HARIAN
# ==========================================
def extract_date_and_film(filename):
    match = re.search(r"(\d{4}[-_]?\d{2}[-_]?\d{2})", filename)
    if match:
        raw_date = match.group(1).replace("_", "-")
        if len(raw_date) == 8 and raw_date.isdigit():
            date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        else:
            date_str = raw_date
    else:
        date_str = None

    clean_name = filename.replace(".csv", "").replace("hasil_", "")
    if match:
        clean_name = clean_name.replace(match.group(1), "")
    clean_name = re.sub(r"[-_]+", " ", clean_name).strip().title()

    return date_str, clean_name if clean_name else "Unassigned Film"


def clean_and_process_showtime(files):
    all_dfs = []
    for file in files:
        df = pd.read_csv(file)
        extracted_date, film_name = extract_date_and_film(file.name)
        df["Nama_Film"] = film_name
        df["Tanggal_Str"] = (
            extracted_date if extracted_date else "Unknown Date"
        )

        df["Jaringan"] = df["Bioskop"].apply(map_jaringan_bioskop)

        if "Harga" in df.columns:
            df["Harga_Clean"] = (
                df["Harga"]
                .astype(str)
                .str.replace(r"[^\d]", "", regex=True)
                .apply(lambda x: int(x) if x != "" else 0)
            )
        else:
            df["Harga_Clean"] = 0

        jam_cols = [c for c in df.columns if re.match(r"^Jam_\d+$", c)]
        id_vars = [
            c
            for c in [
                "Kota",
                "Bioskop",
                "Jaringan",
                "Studio",
                "Harga",
                "Harga_Clean",
                "Nama_Film",
                "Tanggal_Str",
            ]
            if c in df.columns
        ]

        df_melted = pd.melt(
            df,
            id_vars=id_vars,
            value_vars=jam_cols,
            var_name="Sesi_Jam",
            value_name="Jam_Tayang",
        ).dropna(subset=["Jam_Tayang"])

        df_melted["Jam_Tayang"] = (
            df_melted["Jam_Tayang"].astype(str).str.strip()
        )
        all_dfs.append(df_melted)

    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()


# ==========================================
# 2. HELPER ADVANCE TICKET SALES (ATS)
# ==========================================
def process_single_ats_file(file, is_url=False):
    """Membaca seluruh section film dalam 1 file ATS."""
    try:
        if is_url:
            df_raw = pd.read_csv(file, header=None)
            file_name = "Google Sheets"
        else:
            file_name = getattr(file, "name", "ATS File")
            if file_name.endswith(".csv"):
                df_raw = pd.read_csv(file, header=None)
            else:
                df_raw = pd.read_excel(file, header=None)

        header_rows = []
        for idx, row in df_raw.iterrows():
            row_str = " ".join(row.dropna().astype(str)).upper()
            if ("XXI" in row_str or "CGV" in row_str or "LOKASI" in row_str) and ("NO" in row_str or "SHOW" in row_str):
                header_rows.append(idx)

        if not header_rows:
            header_rows = [0]

        film_sections = []

        for i, h_idx in enumerate(header_rows):
            title_row = df_raw.iloc[max(0, h_idx - 1)].dropna()
            film_title = "Unknown Film"
            for val in title_row:
                s_val = str(val).strip()
                if (
                    s_val.upper() not in ["NO", "XXI", "CGV", "LOKASI", ""]
                    and not s_val.isdigit()
                ):
                    film_title = s_val
                    break

            next_h = (
                header_rows[i + 1] if i + 1 < len(header_rows) else len(df_raw)
            )
            section_df = df_raw.iloc[h_idx:next_h].copy()

            row_dates = section_df.iloc[0, 3:].values
            row_shows = section_df.iloc[1, 3:].values

            cleaned_dates = []
            curr_d = "Tanggal Unknown"
            for d in row_dates:
                if pd.notna(d) and str(d).strip() != "":
                    curr_d = " ".join(str(d).strip().split())
                cleaned_dates.append(curr_d)

            col_names = ["No", "Bioskop", "Kota"] + [
                f"{d} | {s}" for d, s in zip(cleaned_dates, row_shows)
            ]

            data_rows = section_df.iloc[2:].copy()
            data_rows = data_rows.iloc[:, : len(col_names)]
            data_rows.columns = col_names[: data_rows.shape[1]]

            data_rows = data_rows[data_rows["Bioskop"].notna()]
            
            data_rows["Bioskop_Upper"] = data_rows["Bioskop"].astype(str).str.strip().str.upper()
            invalid_bioskop_pattern = r"^TOTAL|^LOKASI$|^NO$|^CGV$|^XXI$|^CINEPOLIS$|^PLATINUM$|^FLIX$"
            data_rows = data_rows[~data_rows["Bioskop_Upper"].str.contains(invalid_bioskop_pattern, regex=True)]

            data_rows["Bioskop"] = data_rows["Bioskop"].astype(str).str.strip()
            data_rows["Kota"] = (
                data_rows["Kota"].astype(str).str.strip().str.title()
            )
            data_rows["Jaringan"] = data_rows["Bioskop"].apply(
                map_jaringan_bioskop
            )

            val_cols = [c for c in data_rows.columns if "|" in str(c)]
            melted = pd.melt(
                data_rows,
                id_vars=["Bioskop", "Kota", "Jaringan"],
                value_vars=val_cols,
                var_name="Tanggal_Sesi",
                value_name="Tiket_Terjual",
            )

            melted["Hari_Tanggal"] = melted["Tanggal_Sesi"].apply(
                lambda x: str(x).split(" | ")[0]
                if " | " in str(x)
                else str(x)
            )
            
            melted["Raw_Show"] = melted["Tanggal_Sesi"].apply(
                lambda x: str(x).split(" | ")[1]
                if " | " in str(x)
                else "SHOW 1"
            )
            melted["Show_Num_Int"] = melted["Raw_Show"].apply(clean_show_num_int)
            melted["Sesi_Show"] = "SHOW " + melted["Show_Num_Int"].astype(str)

            melted["Tiket_Terjual"] = (
                melted["Tiket_Terjual"].astype(str).str.extract(r"(\d+)")[0]
            )
            melted["Tiket_Terjual"] = (
                pd.to_numeric(melted["Tiket_Terjual"], errors="coerce")
                .fillna(0)
                .astype(int)
            )

            melted["Nama_Film"] = film_title
            melted["Sumber_File"] = file_name

            valid_sec = melted[melted["Tiket_Terjual"] > 0]
            if not valid_sec.empty:
                film_sections.append(valid_sec)

        if film_sections:
            return pd.concat(film_sections, ignore_index=True)
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Gagal memproses data ATS: {e}")
        return pd.DataFrame()


def process_ats_data(files):
    all_ats_dfs = []
    for file in files:
        df_processed = process_single_ats_file(file, is_url=False)
        if not df_processed.empty:
            all_ats_dfs.append(df_processed)

    if all_ats_dfs:
        return pd.concat(all_ats_dfs, ignore_index=True)
    return pd.DataFrame()


# ==========================================
# MAIN ROUTING APP MODE
# ==========================================
if "Showtime" in app_mode:
    st.markdown("### 📊 Dashboard Showtime & Jadwal Bioskop")

    st.sidebar.markdown("---")
    st.sidebar.header("📥 Unggah File Showtime")
    uploaded_showtime = st.sidebar.file_uploader(
        "Upload File CSV Showtime", type=["csv"], accept_multiple_files=True
    )

    if uploaded_showtime:
        df_combined = clean_and_process_showtime(uploaded_showtime)

        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filter Dashboard")

        film_list = sorted(df_combined["Nama_Film"].unique().tolist())
        selected_film = st.sidebar.multiselect(
            "Pilih Film", options=film_list, default=film_list
        )

        jaringan_list = sorted(df_combined["Jaringan"].unique().tolist())
        selected_jaringan = st.sidebar.multiselect(
            "Pilih Jaringan Bioskop",
            options=jaringan_list,
            default=jaringan_list,
        )

        kota_list = sorted(df_combined["Kota"].dropna().unique().tolist())
        selected_kota = st.sidebar.multiselect(
            "Pilih Kota", options=kota_list, default=kota_list
        )

        filtered_df = df_combined[
            (df_combined["Nama_Film"].isin(selected_film))
            & (df_combined["Jaringan"].isin(selected_jaringan))
            & (df_combined["Kota"].isin(selected_kota))
        ]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🎬 Total Showtimes", f"{len(filtered_df):,}")
        c2.metric(
            "📅 Jumlah Hari Data", f"{filtered_df['Tanggal_Str'].nunique():,}"
        )
        c3.metric("🏢 Total Bioskop", f"{filtered_df['Bioskop'].nunique():,}")
        c4.metric("🏙️ Total Kota", f"{filtered_df['Kota'].nunique():,}")
        c5.metric(
            "💵 Rata-Rata Harga",
            f"Rp {filtered_df['Harga_Clean'].mean():,.0f}",
        )

        st.markdown("---")

        tab_trend, tab_compare, tab_sebaran, tab_jam, tab_raw = st.tabs(
            [
                "📈 Tren Harian",
                "🆚 Komparasi Film",
                "📊 Sebaran & Jaringan",
                "🕒 Jam Tayang Populer",
                "📋 Data Detail",
            ]
        )

        with tab_trend:
            st.subheader("📈 Tren Perkembangan Showtime Harian")
            trend_daily = (
                filtered_df.groupby(["Tanggal_Str", "Nama_Film"])
                .agg(
                    Total_Showtimes=("Jam_Tayang", "count"),
                    Jumlah_Bioskop=("Bioskop", "nunique"),
                    Rata_Harga=("Harga_Clean", "mean"),
                )
                .reset_index()
                .sort_values("Tanggal_Str")
            )

            fig_trend_showtime = px.line(
                trend_daily,
                x="Tanggal_Str",
                y="Total_Showtimes",
                color="Nama_Film",
                markers=True,
                title="Pergerakan Total Showtimes per Hari",
            )
            st.plotly_chart(fig_trend_showtime, width="stretch")

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                fig_trend_bioskop = px.line(
                    trend_daily,
                    x="Tanggal_Str",
                    y="Jumlah_Bioskop",
                    color="Nama_Film",
                    markers=True,
                    title="Jumlah Bioskop Aktif Menayangkan",
                )
                st.plotly_chart(fig_trend_bioskop, width="stretch")

            with col_t2:
                fig_trend_harga = px.line(
                    trend_daily,
                    x="Tanggal_Str",
                    y="Rata_Harga",
                    color="Nama_Film",
                    markers=True,
                    title="Rata-Rata Harga Tiket Harian (Rp)",
                )
                st.plotly_chart(fig_trend_harga, width="stretch")

        with tab_compare:
            st.subheader("🆚 Perbandingan Head-to-Head Antar Film")
            film_summary = (
                filtered_df.groupby("Nama_Film")
                .agg(
                    Total_Showtimes=("Jam_Tayang", "count"),
                    Jangkauan_Bioskop=("Bioskop", "nunique"),
                    Jangkauan_Kota=("Kota", "nunique"),
                    Rata_Harga_Tiket=("Harga_Clean", "mean"),
                )
                .reset_index()
            )

            st.dataframe(
                film_summary.style.format(
                    {
                        "Total_Showtimes": "{:,}",
                        "Jangkauan_Bioskop": "{:,}",
                        "Jangkauan_Kota": "{:,}",
                        "Rata_Harga_Tiket": "Rp {:,.0f}",
                    }
                ),
                width="stretch",
            )

            c_comp1, c_comp2 = st.columns(2)
            with c_comp1:
                fig_comp_showtimes = px.bar(
                    film_summary,
                    x="Nama_Film",
                    y="Total_Showtimes",
                    color="Nama_Film",
                    title="Perbandingan Total Showtimes",
                    text_auto=True,
                )
                st.plotly_chart(fig_comp_showtimes, width="stretch")

            with c_comp2:
                fig_comp_bioskop = px.bar(
                    film_summary,
                    x="Nama_Film",
                    y="Jangkauan_Bioskop",
                    color="Nama_Film",
                    title="Perbandingan Ekspansi Jaringan Bioskop",
                    text_auto=True,
                )
                st.plotly_chart(fig_comp_bioskop, width="stretch")

        with tab_sebaran:
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                st.subheader("Pangsa Pasar Jaringan Bioskop (Market Share)")
                jaringan_counts = (
                    filtered_df["Jaringan"].value_counts().reset_index()
                )
                jaringan_counts.columns = ["Jaringan", "Showtimes"]

                fig_jaringan = px.pie(
                    jaringan_counts,
                    names="Jaringan",
                    values="Showtimes",
                    hole=0.4,
                    title="Komposisi Induk Jaringan Bioskop (Cinema XXI, CGV, Platinum, dll.)",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                st.plotly_chart(fig_jaringan, width="stretch")

            with c_s2:
                st.subheader("Top 10 Kota Terbanyak")
                top_kota = (
                    filtered_df["Kota"].value_counts().head(10).reset_index()
                )
                top_kota.columns = ["Kota", "Jumlah Showtimes"]
                fig_kota = px.bar(
                    top_kota,
                    x="Jumlah Showtimes",
                    y="Kota",
                    orientation="h",
                    color="Jumlah Showtimes",
                    color_continuous_scale="Viridis",
                    text_auto=True,
                )
                fig_kota.update_layout(
                    yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(fig_kota, width="stretch")

            st.markdown("---")
            st.subheader("🔍 Cari Showtime Bioskop / Cabang Spesifik")
            search_bioskop = st.text_input(
                "Ketik Nama Bioskop atau Cabang:",
                placeholder="misal: Eastvara / Transmart / Central Park",
            )

            if search_bioskop:
                filtered_search = filtered_df[
                    filtered_df["Bioskop"].str.contains(
                        search_bioskop, case=False, na=False
                    )
                ]
                st.write(
                    f"Ditemukan **{len(filtered_search)}** showtimes untuk kata kunci: **'{search_bioskop}'**"
                )
                st.dataframe(
                    filtered_search[
                        [
                            "Kota",
                            "Jaringan",
                            "Bioskop",
                            "Studio",
                            "Harga_Clean",
                            "Jam_Tayang",
                            "Nama_Film",
                        ]
                    ],
                    width="stretch",
                )

        with tab_jam:
            st.subheader("🕒 Distribusi Jam Tayang (Peak Hours)")
            jam_counts = (
                filtered_df["Jam_Tayang"]
                .value_counts()
                .head(15)
                .reset_index()
            )
            jam_counts.columns = ["Jam Tayang", "Jumlah Sesi"]
            fig_jam = px.bar(
                jam_counts,
                x="Jam Tayang",
                y="Jumlah Sesi",
                color="Jumlah Sesi",
                color_continuous_scale="Oranges",
                text_auto=True,
            )
            st.plotly_chart(fig_jam, width="stretch")

        with tab_raw:
            st.subheader("📋 Data Detail Showtime")
            st.dataframe(filtered_df, width="stretch")

    else:
        st.info("👈 Silakan unggah file CSV Showtime di sidebar sebelah kiri.")


# ==========================================
# MODE 2: ADVANCE TICKET SALES (ATS) ANALYTICS
# ==========================================
else:
    st.markdown("### 🎟️ Dashboard Advance Ticket Sales (ATS / Presale)")

    st.sidebar.markdown("---")
    st.sidebar.header("📥 Sumber Data ATS")

    ats_source = st.sidebar.radio(
        "Pilih Metode Input Data ATS:",
        ["Google Sheets (Live Link)", "Upload File Manual (CSV/Excel)"],
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Fitur Analisis Kapasitas")
    enable_occupancy = st.sidebar.checkbox("💺 Hitung Occupancy Rate (%)", value=True)

    df_ats = pd.DataFrame()

    if "Google Sheets" in ats_source:
        gsheet_url = st.sidebar.text_input(
            "URL CSV Published Google Sheets ATS:",
            placeholder="https://docs.google.com/spreadsheets/d/e/.../pub?output=csv",
        )
        if st.sidebar.button("🔄 Reload Data Google Sheets"):
            st.cache_data.clear()

        if gsheet_url:
            df_ats = process_single_ats_file(gsheet_url, is_url=True)
            if df_ats.empty:
                st.warning("⚠️ Data berhasil diakses namun tidak ada baris tiket (> 0) yang ter-parse dari URL Google Sheets ini.")
        else:
            st.info(
                "💡 Masukkan URL Published CSV Google Sheets di sidebar (File > Share > Publish to Web > CSV)."
            )

    else:
        uploaded_ats = st.sidebar.file_uploader(
            "Upload File Excel / CSV ATS",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
        )
        if uploaded_ats:
            df_ats = process_ats_data(uploaded_ats)
            if df_ats.empty:
                st.warning("⚠️ File terunggah tetapi tidak menemukan format data ATS yang sesuai.")
        else:
            st.info("👈 Silakan unggah file Excel/CSV ATS di sidebar sebelah kiri.")

    if not df_ats.empty:
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filter ATS")

        film_ats_list = sorted(df_ats["Nama_Film"].unique().tolist())
        selected_ats_film = st.sidebar.multiselect(
            "Pilih Film", options=film_ats_list, default=film_ats_list
        )

        jaringan_ats_list = sorted(df_ats["Jaringan"].unique().tolist())
        selected_ats_jaringan = st.sidebar.multiselect(
            "Pilih Jaringan Bioskop",
            options=jaringan_ats_list,
            default=jaringan_ats_list,
        )

        kota_ats_list = sorted(df_ats["Kota"].unique().tolist())
        selected_ats_kota = st.sidebar.multiselect(
            "Pilih Kota", options=kota_ats_list, default=kota_ats_list
        )

        filtered_ats = df_ats[
            (df_ats["Nama_Film"].isin(selected_ats_film))
            & (df_ats["Jaringan"].isin(selected_ats_jaringan))
            & (df_ats["Kota"].isin(selected_ats_kota))
        ].copy()

        # 🕒 HELPER: PARSE & URUTKAN TANGGAL SNAPSHOT SECARA KRONOLOGIS
        def parse_date_sort_key(date_str):
            try:
                parsed = pd.to_datetime(date_str, errors="coerce")
                if pd.notna(parsed):
                    return parsed
            except Exception:
                pass
            
            match = re.search(r"\d+", str(date_str))
            if match:
                return int(match.group(0))
            return 0

        filtered_ats["_Date_Sort"] = filtered_ats["Hari_Tanggal"].apply(parse_date_sort_key)
        
        sorted_hari_tanggal = (
            filtered_ats[["Hari_Tanggal", "_Date_Sort"]]
            .drop_duplicates()
            .sort_values("_Date_Sort")["Hari_Tanggal"]
            .tolist()
        )

        # 🔗 MATCHING DATA KAPASITAS DARI GOOGLE SHEETS (SHEET2)
        df_cap = load_capacity_data(CAPACITY_SHEET_URL)
        
        if not df_cap.empty:
            ats_bioskop_list = filtered_ats["Bioskop"].unique()
            cap_bioskop_list = df_cap["Bioskop_Cap_Clean"].unique()
            
            mapping_dict = {}
            for b_ats in ats_bioskop_list:
                clean_ats = clean_bioskop_string(b_ats)
                best_match = None
                
                for b_cap in cap_bioskop_list:
                    if clean_ats and b_cap and (clean_ats in b_cap or b_cap in clean_ats):
                        best_match = b_cap
                        break
                
                if not best_match:
                    words_ats = clean_ats.split()
                    for b_cap in cap_bioskop_list:
                        if words_ats and any(w in b_cap for w in words_ats if len(w) > 2):
                            best_match = b_cap
                            break

                mapping_dict[b_ats] = best_match if best_match else clean_ats

            filtered_ats["Bioskop_Cap_Matched"] = filtered_ats["Bioskop"].map(mapping_dict)

            # Lookup Tuples Tepat: (Nama_Clean, Show_Num_Int) -> Kapasitas Kursi
            cap_lookup = df_cap.set_index(["Bioskop_Cap_Clean", "Show_Num_Int"])["Kapasitas_Seat"].to_dict()
            avg_cap_lookup = df_cap.groupby("Bioskop_Cap_Clean")["Kapasitas_Seat"].mean().to_dict()
            global_avg_cap = df_cap["Kapasitas_Seat"].mean()

            def get_seat_capacity(row):
                key = (row["Bioskop_Cap_Matched"], int(row["Show_Num_Int"]))
                val = cap_lookup.get(key, 0)
                if val <= 0:
                    val = avg_cap_lookup.get(row["Bioskop_Cap_Matched"], 0)
                if val <= 0:
                    val = global_avg_cap if global_avg_cap > 0 else 150
                return int(val)

            filtered_ats["Kapasitas_Seat"] = filtered_ats.apply(get_seat_capacity, axis=1)
        else:
            filtered_ats["Kapasitas_Seat"] = 150

        # =========================================================
        # 🛠 METRIK & OCCUPANCY RATE AGREGAT LENGKAP
        # =========================================================
        total_tiket_terjual = filtered_ats["Tiket_Terjual"].sum()
        
        # Total Kapasitas Studio Keseluruhan (1 Show per Bioskop x Sesi Show)
        df_unique_shows = filtered_ats.groupby(["Bioskop", "Sesi_Show"])["Kapasitas_Seat"].first().reset_index()
        total_kapasitas_studio = df_unique_shows["Kapasitas_Seat"].sum()
        
        overall_occ = (total_tiket_terjual / total_kapasitas_studio * 100.0) if total_kapasitas_studio > 0 else 0.0
        overall_occ = min(overall_occ, 100.0)

        if filtered_ats["Kapasitas_Seat"].sum() > 0:
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("🎟 Tiket Terjual (Akumulasi Presale)", f"{total_tiket_terjual:,}")
            m2.metric("💺 Total Kapasitas Studio (Hari H)", f"{total_kapasitas_studio:,}")
            m3.metric("📊 Occupancy Rate", f"{overall_occ:.1f}%")
            m4.metric("🏢 Total Bioskop", f"{filtered_ats['Bioskop'].nunique():,}")
            m5.metric("🏙️ Total Kota", f"{filtered_ats['Kota'].nunique():,}")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🎟️ Total Tiket Terjual (ATS)", f"{total_tiket_terjual:,}")
            m2.metric("🏢 Bioskop Membuka ATS", f"{filtered_ats['Bioskop'].nunique():,}")
            m3.metric("🏙️ Kota Terjangkau", f"{filtered_ats['Kota'].nunique():,}")
            m4.metric("📅 Snapshot Data", f"{filtered_ats['Hari_Tanggal'].nunique():,}")

        st.markdown("---")

        tab_list = [
            "📅 Tren Penjualan per Snapshot Tanggal",
            "🕒 Demografi Sesi Show",
            "🏙️ Top Kota & Jaringan",
        ]
        
        if enable_occupancy:
            tab_list.append("💺 Analisis Occupancy Rate (%)")
            
        tab_list.append("📋 Detail Data ATS")

        tabs = st.tabs(tab_list)

        # TAB 1: TREN AKUMULASI PRESALE PER TANGGAL SNAPSHOT
        with tabs[0]:
            st.subheader("📅 Perkembangan Tiket Presale Terjual per Snapshot Tanggal")
            
            ats_daily = filtered_ats.groupby(["Hari_Tanggal", "_Date_Sort", "Nama_Film"])["Tiket_Terjual"].sum().reset_index()
            ats_daily = ats_daily.sort_values("_Date_Sort")

            fig_ats_daily = px.bar(
                ats_daily,
                x="Hari_Tanggal",
                y="Tiket_Terjual",
                color="Nama_Film",
                barmode="group",
                title="Penjualan Tiket Berdasarkan Tanggal Penarikan Data (Urut Kronologis)",
                text_auto=True,
                category_orders={"Hari_Tanggal": sorted_hari_tanggal}
            )
            fig_ats_daily.update_xaxes(categoryorder="array", categoryarray=sorted_hari_tanggal)
            st.plotly_chart(fig_ats_daily, width="stretch")

            pivot_daily = filtered_ats.pivot_table(
                index="Hari_Tanggal",
                columns="Nama_Film",
                values="Tiket_Terjual",
                aggfunc="sum",
                fill_value=0,
            )
            pivot_daily["TOTAL TIKET"] = pivot_daily.sum(axis=1)
            st.dataframe(pivot_daily.style.format("{:,}"), width="stretch")

        # TAB 2: DEMOGRAFI SESI SHOW
        with tabs[1]:
            st.subheader("🕒 Demand Tiket Berdasarkan Tanggal Snapshot & Sesi Show")
            
            ats_show_date = filtered_ats.groupby(["Hari_Tanggal", "_Date_Sort", "Sesi_Show", "Nama_Film"])["Tiket_Terjual"].sum().reset_index()
            ats_show_date = ats_show_date.sort_values("_Date_Sort")

            urutan_show = ["SHOW 1", "SHOW 2", "SHOW 3", "SHOW 4", "SHOW 5"]
            
            fig_ats_show = px.bar(
                ats_show_date,
                x="Hari_Tanggal",
                y="Tiket_Terjual",
                color="Sesi_Show",
                barmode="group",
                facet_col="Nama_Film" if ats_show_date["Nama_Film"].nunique() > 1 else None,
                title="Perbandingan Penjualan Tiket per Tanggal Snapshot & Jam Show",
                text_auto=True,
                category_orders={"Hari_Tanggal": sorted_hari_tanggal, "Sesi_Show": urutan_show}
            )
            fig_ats_show.update_xaxes(categoryorder="array", categoryarray=sorted_hari_tanggal)
            st.plotly_chart(fig_ats_show, width="stretch")

        with tabs[2]:
            c_k1, c_k2 = st.columns(2)
            with c_k1:
                st.subheader("Penjualan per Induk Jaringan Bioskop")
                top_ats_jaringan = filtered_ats.groupby("Jaringan")["Tiket_Terjual"].sum().reset_index()
                fig_ats_j = px.pie(
                    top_ats_jaringan,
                    names="Jaringan",
                    values="Tiket_Terjual",
                    hole=0.4,
                    title="Pangsa Presale per Jaringan",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                st.plotly_chart(fig_ats_j, width="stretch")

            with c_k2:
                st.subheader("Top 10 Kota Presale Terbanyak")
                top_ats_kota = filtered_ats.groupby("Kota")["Tiket_Terjual"].sum().nlargest(10).reset_index()
                fig_ats_k = px.bar(
                    top_ats_kota,
                    x="Tiket_Terjual",
                    y="Kota",
                    orientation="h",
                    color="Tiket_Terjual",
                    color_continuous_scale="Blugrn",
                    text_auto=True,
                )
                fig_ats_k.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_ats_k, width="stretch")

        # 💺 TAB KHUSUS OCCUPANCY RATE
        if enable_occupancy and "💺 Analisis Occupancy Rate (%)" in tab_list:
            tab_occ_idx = tab_list.index("💺 Analisis Occupancy Rate (%)")
            with tabs[tab_occ_idx]:
                st.subheader("💺 Analisis Rasio Keterisian Kursi (% Occupancy Rate Penayangan)")
                
                urutan_show = ["SHOW 1", "SHOW 2", "SHOW 3", "SHOW 4", "SHOW 5"]
                
                # 1. Agregat per Bioskop & Sesi Show
                occ_show_agg = filtered_ats.groupby(["Bioskop", "Sesi_Show"]).agg(
                    Total_Terjual=("Tiket_Terjual", "sum"),
                    Kapasitas_Single=("Kapasitas_Seat", "first")
                ).reset_index()
                
                occ_show_agg["Occupancy_Rate_%"] = occ_show_agg.apply(
                    lambda r: min((float(r["Total_Terjual"]) / float(r["Kapasitas_Single"]) * 100.0), 100.0) if float(r["Kapasitas_Single"]) > 0 else 0.0,
                    axis=1
                ).round(1)

                col_occ1, col_occ2 = st.columns(2)
                
                with col_occ1:
                    st.markdown("##### 📊 % Occupancy Rate Keseluruhan per Sesi Show")
                    
                    occ_sesi_overall = filtered_ats.groupby("Sesi_Show").agg(
                        Total_Terjual=("Tiket_Terjual", "sum")
                    ).reset_index()
                    
                    cap_by_show = df_unique_shows.groupby("Sesi_Show")["Kapasitas_Seat"].sum().to_dict()
                    occ_sesi_overall["Kapasitas_Show_Total"] = occ_sesi_overall["Sesi_Show"].map(cap_by_show)
                    
                    occ_sesi_overall["Rate_%"] = occ_sesi_overall.apply(
                        lambda r: min((r["Total_Terjual"] / r["Kapasitas_Show_Total"] * 100.0), 100.0) if r["Kapasitas_Show_Total"] > 0 else 0.0,
                        axis=1
                    ).round(1)
                    
                    fig_occ_sesi = px.bar(
                        occ_sesi_overall,
                        x="Sesi_Show",
                        y="Rate_%",
                        color="Rate_%",
                        color_continuous_scale="Reds",
                        title="% Keterisian per Sesi Show (Terjual / Total Kapasitas)",
                        text_auto=".1f",
                        category_orders={"Sesi_Show": urutan_show}
                    )
                    fig_occ_sesi.update_xaxes(categoryorder="array", categoryarray=urutan_show)
                    st.plotly_chart(fig_occ_sesi, width="stretch")

                with col_occ2:
                    st.markdown("##### 🏢 Top 20 Bioskop % Occupancy Rate Highest")
                    
                    occ_bio_overall = filtered_ats.groupby("Bioskop").agg(
                        Total_Terjual=("Tiket_Terjual", "sum")
                    ).reset_index()
                    
                    cap_by_bio = df_unique_shows.groupby("Bioskop")["Kapasitas_Seat"].sum().to_dict()
                    occ_bio_overall["Total_Kapasitas"] = occ_bio_overall["Bioskop"].map(cap_by_bio)
                    
                    occ_bio_overall["Rate_%"] = occ_bio_overall.apply(
                        lambda r: min((r["Total_Terjual"] / r["Total_Kapasitas"] * 100.0), 100.0) if r["Total_Kapasitas"] > 0 else 0.0,
                        axis=1
                    ).round(1)
                    occ_bio_overall = occ_bio_overall.sort_values("Rate_%", ascending=False).head(20)
                    
                    fig_occ_bio = px.bar(
                        occ_bio_overall,
                        x="Rate_%",
                        y="Bioskop",
                        orientation="h",
                        color="Rate_%",
                        color_continuous_scale="Purples",
                        title="Top 20 Bioskop Keterisian Tertinggi (%)",
                        text_auto=".1f"
                    )
                    
                    fig_occ_bio.update_layout(
                        yaxis={"categoryorder": "total ascending", "dtick": 1},
                        height=600,
                        margin=dict(l=160, r=60, t=50, b=50)
                    )
                    fig_occ_bio.update_traces(textposition="outside")
                    
                    st.plotly_chart(fig_occ_bio, width="stretch")

        st.markdown("---")

        # 🔥 HEATMAP BIOSKOP vs SESI SHOW vs OR (%)
        st.subheader("🔥 Heatmap Occupancy Rate (%) per Jaringan & Jam Tayang")
        
        heatmap_df = occ_show_agg.pivot(
            index="Bioskop",
            columns="Sesi_Show",
            values="Occupancy_Rate_%"
        ).fillna(0.0)
        
        existing_shows = [s for s in urutan_show if s in heatmap_df.columns]
        if existing_shows:
            heatmap_df = heatmap_df[existing_shows]
        
        fig_heatmap = px.imshow(
            heatmap_df,
            labels=dict(x="Sesi Show", y="Bioskop", color="Occupancy Rate (%)"),
            x=heatmap_df.columns,
            y=heatmap_df.index,
            color_continuous_scale="YlOrRd",
            text_auto=".1f",
            aspect="auto",
            title="Peta Kepadatan Penonton (% OR) per Jaringan & Jam Tayang Hari H"
        )
        
        fig_heatmap.update_xaxes(side="top")
        fig_heatmap.update_layout(height=max(400, len(heatmap_df) * 30))
        
        st.plotly_chart(fig_heatmap, width="stretch")

        with tabs[-1]:
            st.subheader("📋 Data Detail Rekapitulasi Presale (ATS)")
            st.dataframe(filtered_ats.drop(columns=["_Date_Sort"], errors="ignore"), width="stretch")