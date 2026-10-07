import sys
import asyncio

# 🛡️ FIX WINDOWS PROACTOR EVENT LOOP CONNECTION RESET ERROR (WINERROR 10054)
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import re
import time
import io
import urllib.request
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

    if "UPDATE RECAP" in name_upper or "LAST UPDATE" in name_upper or "UPDATE ATS" in name_upper:
        return "Unknown"

    xxi_keywords = ["XXI", "IMAX", "PREMIERE", " 21", "21 ", "PAKUWON MALL REGULAR", "PAKUWON"]
    if any(k in name_upper for k in xxi_keywords) or name_upper.endswith("21"):
        return "Cinema XXI"

    cinepolis_keywords = [
        "CINEPOLIS", "CINEMEXX", "PEJATEN", "GAJAH MADA PLAZA", "PLUIT VILLAGE",
        "PLAZA RENON", "LIVING PLAZA BALIKPAPAN", "BOTANIA", "EKALOKASARI", "Q MALL",
        "LIPPO", "DEPOK TOWN SQUARE", "DETOS", "PHINISI POINT", "MALANG TOWN SQUARE",
        "MATOS", "MEDAN FAIR", "PALEMBANG ICON", "LIVING WORLD PEKANBARU",
        "SIANTAR CITY", "MALL OF SERANG", "MAXXBOX", "PACIFIC TEGAL",
        "CITIPLAZA KUTABUMI", "CITIPLAZA", "KUTABUMI",
        "MANGGA DUA SQUARE", "MANGGA DUA",
        "MAL PEKANBARU", "MALL PEKANBARU",
        "KEBAYORAN PARK MALL", "KEBAYORAN PARK",
        "SUN PLAZA",
        "SIDEWALK JIMBARAN", "SIDEWALK",
        "DISTRIK 1 MEIKARTA", "MEIKARTA",
        "KSQUARE BATAM", "KSQUARE",
        "KALIBATA CITY SQUARE", "KALIBATA CITY",
        "PONDOK KELAPA TOWN SQUARE", "PONDOK KELAPA",
        "SENAYAN PARK"
    ]
    if any(keyword in name_upper for keyword in cinepolis_keywords):
        return "Cinepolis"

    cgv_keywords = [
        "CGV", "BLITZ", "4DX", "PASKAL", "PVJ", "PARIS VAN JAVA", "JWALK", "J-WALK",
        "BELLA TERRA", "CENTRAL PARK", "GRAND INDONESIA", "GREEN PRAMUKA", "SUNTER",
        "BUARAN", "AEON", "DEPOK MALL", "LAGOON AVENUE", "BEKASI CYBER", "BEKASI TRADE",
        "VIVO SENTUL", "CITRA MAJA", "LIVING PLAZA JABABEKA", "FESTIVE WALK", "CIKAMPEK",
        "SADANG", "BEC", "KINGS", "MIKO", "METRO INDAH", "TRANSMART", "GRAND MALL LAMPUNG",
        "GRAGE", "RITA SUPERMALL", "SOCIAL MARKET", "PTC MALL", "PAKUWON MALL JOGJA",
        "PLAZA LAWU", "KEDIRI MALL", "BLITAR SQUARE", "SUNRISE MALL", "ICON MALL",
        "BG JUNCTION", "MASPION", "MARVELL", "MALANG CITY", "WIJAYA KUSUMA", "ROXY SQUARE",
        "PARK AVENUE", "GRAND BATAM", "RAYA PADANG", "HOLIDAY PEKANBARU", "PLAZA MULIA",
        "PANAKKUKANG", "FOCAL POINT", "TERAS KOTA", "PARADISE WALK", "FOODMOSPHERE",
        "ECOPLAZA", "CIPUTRA TANGERANG", "GRAND BATAVIA", "POINS", "FX SUDIRMAN",
        "PACIFIC PLACE", "SLIPI JAYA", "DTC DEPOK", "PLAZA BALIKPAPAN"
    ]
    if any(keyword in name_upper for keyword in cgv_keywords):
        return "CGV"

    elif "PLATINUM" in name_upper:
        return "Platinum"
    elif "NSC" in name_upper:
        return "NSC"
    elif "KOTA CINEMA" in name_upper or "KCM" in name_upper:
        return "Kota Cinema Mall"
    elif "FLIX" in name_upper:
        return "FLIX Cinema"
    elif "GOLDEN" in name_upper:
        return "Golden Theater"
    else:
        return "Lainnya / Independen"


def clean_show_num_int(val):
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


# ==========================================
# HELPER: RESOLVER KOTA DENGAN AUTO-LOOKUP
# ==========================================
KOTA_MANUAL_MAP = {
    "HOLLYWOOD XXI": "Jakarta",
    "HOLLYWOOD": "Jakarta",
    "JWALK MALL": "Yogyakarta",
    "JWALK": "Yogyakarta",
    "GANDARIA CITY": "Jakarta",
    "GANDARIA": "Jakarta",
    "HERMES": "Medan",
    "PALEMBANG SQUARE": "Palembang",
    "PLAZA MULIA": "Samarinda",
    "LIVING WORLD DENPASAR": "Denpasar",
    "PAKOWON MALL": "Surabaya",
    "PAKUWON MALL": "Surabaya",
    "FOCAL POINT": "Medan",
    "MANANTOS 3": "Manado",
    "MANTOS 3": "Manado",
    "AYANI": "Pontianak",
    "DP MALL": "Semarang",
}

def resolve_kota(row):
    k_val = str(row["Kota"]).strip()
    b_val = str(row["Bioskop"]).strip().upper()
    
    if k_val and k_val.lower() not in ["nan", "none", "unknown", ""] and not k_val.isdigit() and "UPDATE" not in k_val.upper() and "TOTAL" not in k_val.upper():
        return k_val.title()
        
    for key, city in KOTA_MANUAL_MAP.items():
        if key in b_val:
            return city
            
    known_cities = [
        "JAKARTA", "SURABAYA", "MEDAN", "BANDUNG", "SEMARANG", "PALEMBANG",
        "MAKASSAR", "BATAM", "PEKANBARU", "DENPASAR", "YOGYAKARTA", "JOGJA",
        "MALANG", "SOLO", "BALIKPAPAN", "SAMARINDA", "MANADO", "PONTIANAK",
        "BANJARMASIN", "PADANG", "LAMPUNG", "BOGOR", "DEPOK", "TANGERANG", "BEKASI"
    ]
    for city in known_cities:
        if city in b_val:
            return "Yogyakarta" if city == "JOGJA" else city.title()
            
    return "Unknown"


# ==========================================
# HELPER: PARSE TANGGAL SNAPSHOT KRONOLOGIS
# ==========================================
MONTH_MAP = {
    "JAN": 1, "JANUARI": 1, "FEB": 2, "FEBRUARI": 2, "MAR": 3, "MARET": 3,
    "APR": 4, "APRIL": 4, "MEI": 5, "MAY": 5, "JUN": 6, "JUNI": 6,
    "JUL": 7, "JULI": 7, "AGU": 8, "AGUSTUS": 8, "AUG": 8, "SEP": 9, "SEPTEMBER": 9,
    "OKT": 10, "OKTOBER": 10, "OCT": 10, "NOV": 11, "NOVEMBER": 11, "DES": 12, "DESEMBER": 12, "DEC": 12
}

def parse_date_sort_key(date_str):
    s = str(date_str).strip().upper()
    try:
        parsed = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            return parsed
    except Exception:
        pass
    
    match = re.search(r"(\d{1,2})\s*([A-Z]+)\s*(\d{2,4})?", s)
    if match:
        day = int(match.group(1))
        m_str = match.group(2)
        year = int(match.group(3)) if match.group(3) else 2026
        if year < 100:
            year += 2000
        month = MONTH_MAP.get(m_str, 1)
        return pd.Timestamp(year=year, month=month, day=day)
        
    num_match = re.search(r"\d+", s)
    if num_match:
        return pd.Timestamp(year=2026, month=1, day=int(num_match.group(0)))
        
    return pd.Timestamp(year=1970, month=1, day=1)


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
        if hasattr(file, "seek"):
            file.seek(0)
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
@st.cache_data(ttl=5, show_spinner=False)
def load_ats_data_raw(file_path_or_url, is_url=False, timestamp=0):
    """Membaca isi raw file ATS dengan invalidasi cache otomatis."""
    if is_url:
        live_url = f"{file_path_or_url}{'&' if '?' in file_path_or_url else '?'}_ts={timestamp}"
        req = urllib.request.Request(
            live_url, 
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content_bytes = response.read()
        return content_bytes
    return None


def process_single_ats_file(file, is_url=False):
    """Membaca seluruh data ATS berdasarkan rentang baris presisi Excel:
       - XXI: BW4:BW17
       - CGV: BW25:BW122
       - Cinepolis: BW130:BW173
    """
    try:
        ts_now = int(time.time())
        if is_url:
            content_bytes = load_ats_data_raw(file, is_url=True, timestamp=ts_now)
            file_name = "Google Sheets"
        else:
            file_name = getattr(file, "name", "ATS File")
            if hasattr(file, "seek"):
                file.seek(0)
            content_bytes = file.read()

        if is_url or file_name.lower().endswith(".csv"):
            csv_text = content_bytes.decode("utf-8-sig", errors="ignore")
            df_raw = pd.read_csv(io.StringIO(csv_text), header=None, low_memory=False)
        else:
            df_raw = pd.read_excel(io.BytesIO(content_bytes), header=None)

        bw_col_idx = 74 if df_raw.shape[1] > 74 else None
        bx_col_idx = 75 if df_raw.shape[1] > 75 else None

        # Ambil Judul Film dari baris awal
        film_title = "Unknown Film"
        for val in df_raw.iloc[0:3].values.flatten():
            s_val = str(val).strip()
            if s_val.upper() not in ["NO", "XXI", "CGV", "CINEPOLIS", "LOKASI", "NAN", "NONE", ""] and not s_val.isdigit() and "UPDATE" not in s_val.upper():
                film_title = s_val
                break

        # XXI: Baris Excel 4-17 -> iloc[3:17]
        # CGV: Baris Excel 25-122 -> iloc[24:122]
        # Cinepolis: Baris Excel 130-173 -> iloc[129:173]
        ranges = [
            ("Cinema XXI", 3, 17),
            ("CGV", 24, 122),
            ("Cinepolis", 129, 173)
        ]

        header_dates = df_raw.iloc[1, 3:].values if len(df_raw) > 1 else []
        header_shows = df_raw.iloc[2, 3:].values if len(df_raw) > 2 else []

        cleaned_dates = []
        curr_d = "Tanggal Unknown"
        for d in header_dates:
            if pd.notna(d) and str(d).strip() != "":
                curr_d = " ".join(str(d).strip().split())
            cleaned_dates.append(curr_d)

        max_sesi_col = min(len(cleaned_dates), 65)
        col_names = ["No", "Bioskop", "Kota"] + [
            f"{d} | {s}" for d, s in zip(cleaned_dates[:max_sesi_col], header_shows[:max_sesi_col])
        ]

        all_sliced_blocks = []

        for default_brand, start_idx, end_idx in ranges:
            if len(df_raw) > start_idx:
                block_df = df_raw.iloc[start_idx:min(end_idx, len(df_raw))].copy()
                
                # Forward fill kota untuk sel merged
                block_df.iloc[:, 2] = block_df.iloc[:, 2].replace(r"^\s*$", None, regex=True).ffill()

                admission_bw_list = []
                kapasitas_bx_list = []

                for r_idx, row in block_df.iterrows():
                    val_bw = row.iloc[bw_col_idx] if (bw_col_idx is not None and bw_col_idx < len(row)) else 0
                    val_bw_clean = pd.to_numeric(str(val_bw).replace(",", "").replace(".", "").strip(), errors="coerce")
                    admission_bw_list.append(int(val_bw_clean) if pd.notna(val_bw_clean) else 0)

                    val_bx = row.iloc[bx_col_idx] if (bx_col_idx is not None and bx_col_idx < len(row)) else 0
                    val_bx_clean = pd.to_numeric(str(val_bx).replace(",", "").replace(".", "").strip(), errors="coerce")
                    kapasitas_bx_list.append(int(val_bx_clean) if pd.notna(val_bx_clean) else 0)

                data_sliced = block_df.iloc[:, : len(col_names)].copy()
                data_sliced.columns = col_names[: data_sliced.shape[1]]
                
                data_sliced["Total_Admission_BW"] = admission_bw_list
                data_sliced["Total_Kapasitas_BX"] = kapasitas_bx_list

                data_sliced = data_sliced[data_sliced["Bioskop"].notna()]
                data_sliced["Bioskop_Clean"] = data_sliced["Bioskop"].astype(str).str.strip()
                
                invalid_names = ["LOKASI", "NO", "CGV", "XXI", "CINEPOLIS", "TOTAL", "JUMLAH", "SUBTOTAL", "GRAND TOTAL"]
                data_sliced = data_sliced[
                    (~data_sliced["Bioskop_Clean"].str.upper().isin(invalid_names)) &
                    (~data_sliced["Bioskop_Clean"].str.upper().str.startswith("TOTAL")) &
                    (~data_sliced["Bioskop_Clean"].str.upper().str.contains("UPDATE", na=False))
                ]

                data_sliced["Bioskop"] = data_sliced["Bioskop_Clean"]
                data_sliced["Kota"] = data_sliced.apply(resolve_kota, axis=1)
                data_sliced["Jaringan"] = default_brand

                all_sliced_blocks.append(data_sliced)

        if not all_sliced_blocks:
            return pd.DataFrame()

        combined_sliced = pd.concat(all_sliced_blocks, ignore_index=True)

        val_cols = [c for c in combined_sliced.columns if "|" in str(c)]
        melted = pd.melt(
            combined_sliced,
            id_vars=["Bioskop", "Kota", "Jaringan", "Total_Admission_BW", "Total_Kapasitas_BX"],
            value_vars=val_cols,
            var_name="Tanggal_Sesi",
            value_name="Tiket_Terjual",
        )

        melted["Hari_Tanggal"] = melted["Tanggal_Sesi"].apply(
            lambda x: str(x).split(" | ")[0] if " | " in str(x) else str(x)
        )
        
        melted["Raw_Show"] = melted["Tanggal_Sesi"].apply(
            lambda x: str(x).split(" | ")[1] if " | " in str(x) else "SHOW 1"
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

        return melted

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

        jaringan_list = sorted([j for j in df_combined["Jaringan"].unique().tolist() if j != "Unknown"])
        selected_jaringan = st.sidebar.multiselect(
            "Pilih Jaringan Bioskop",
            options=jaringan_list,
            default=jaringan_list,
        )

        kota_list = sorted([
            k for k in df_combined["Kota"].dropna().unique().tolist() 
            if k.upper() != "UNKNOWN" and "UPDATE" not in k.upper() and "TOTAL" not in k.upper()
        ])
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
        c2.metric("📅 Jumlah Hari Data", f"{filtered_df['Tanggal_Str'].nunique():,}")
        c3.metric("🏢 Total Bioskop", f"{filtered_df['Bioskop'].nunique():,}")
        c4.metric("🏙️ Total Kota", f"{filtered_df['Kota'].nunique():,}")
        c5.metric("💵 Rata-Rata Harga", f"Rp {filtered_df['Harga_Clean'].mean():,.0f}")

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
                    title="Komposisi Induk Jaringan Bioskop (Cinema XXI, CGV, Cinépolis, Platinum, dll.)",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                st.plotly_chart(fig_jaringan, width="stretch")

            with c_s2:
                st.subheader("Top 10 Kota Terbanyak")
                top_kota = (
                    filtered_df[~filtered_df["Kota"].isin(["Nan", "None", "Unknown", ""])]["Kota"].value_counts().head(10).reset_index()
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
                placeholder="misal: Eastvara / Transmart / Central Park / Pejaten",
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

    if st.sidebar.button("🔄 Refresh Data Google Sheets"):
        st.cache_data.clear()
        st.success("✅ Cache berhasil dibersihkan! Menarik data terbaru dari Google Sheets...")
        st.rerun()

    df_ats = pd.DataFrame()

    if "Google Sheets" in ats_source:
        gsheet_url = st.sidebar.text_input(
            "URL CSV Published Google Sheets ATS:",
            value="https://docs.google.com/spreadsheets/d/e/2PACX-1vRIs81ypiEpR41DPPHCLVD6L4FTARZmEBfAebetI9hM2XsyRuQuDpyVaK95_pL-GQ/pub?output=csv",
        )

        if gsheet_url:
            df_ats = process_single_ats_file(gsheet_url, is_url=True)
            if df_ats.empty:
                st.warning("⚠️ Data ATS belum terload dari URL ini.")
    else:
        uploaded_ats = st.sidebar.file_uploader(
            "Upload File Excel / CSV ATS",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
        )
        if uploaded_ats:
            df_ats = process_ats_data(uploaded_ats)

    if not df_ats.empty:
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filter ATS")

        film_ats_list = sorted(df_ats["Nama_Film"].unique().tolist())
        selected_ats_film = st.sidebar.multiselect("Pilih Film", options=film_ats_list, default=film_ats_list)

        jaringan_ats_list = sorted([j for j in df_ats["Jaringan"].unique().tolist() if j != "Unknown"])
        selected_ats_jaringan = st.sidebar.multiselect("Pilih Jaringan Bioskop", options=jaringan_ats_list, default=jaringan_ats_list)

        kota_ats_list = sorted([
            k for k in df_ats["Kota"].unique().tolist() 
            if k.upper() != "UNKNOWN" and "UPDATE" not in k.upper() and "TOTAL" not in k.upper()
        ])
        selected_ats_kota = st.sidebar.multiselect("Pilih Kota", options=kota_ats_list, default=kota_ats_list)

        filtered_ats = df_ats[
            (df_ats["Nama_Film"].isin(selected_ats_film))
            & (df_ats["Jaringan"].isin(selected_ats_jaringan))
            & (df_ats["Kota"].isin(selected_ats_kota))
        ].copy()

        # 🕒 SORTING KRONOLOGIS UNTUK TANGGAL SNAPSHOT
        filtered_ats["_Date_Sort"] = filtered_ats["Hari_Tanggal"].apply(parse_date_sort_key)
        
        sorted_hari_tanggal = (
            filtered_ats[["Hari_Tanggal", "_Date_Sort"]]
            .drop_duplicates()
            .sort_values("_Date_Sort")["Hari_Tanggal"]
            .tolist()
        )

        # 🎯 REKAPITULASI DEDUPED AKURAT PER SECTION & BIOSKOP
        raw_bio_rows = filtered_ats[
            ["Nama_Film", "Bioskop", "Kota", "Jaringan", "Total_Admission_BW", "Total_Kapasitas_BX"]
        ].drop_duplicates(subset=["Nama_Film", "Bioskop", "Kota", "Jaringan"])

        bio_unique = raw_bio_rows.groupby(["Bioskop", "Kota", "Jaringan"]).agg(
            Total_Admission=("Total_Admission_BW", "sum"),
            Total_Capacity=("Total_Kapasitas_BX", "sum")
        ).reset_index()

        bio_unique["Occupancy_Rate_%"] = bio_unique.apply(
            lambda r: min((r["Total_Admission"] / r["Total_Capacity"] * 100.0), 100.0) if r["Total_Capacity"] > 0 else 0.0,
            axis=1
        ).round(2)

        total_tiket_terjual = bio_unique["Total_Admission"].sum()
        total_kapasitas_studio = bio_unique["Total_Capacity"].sum()
        overall_occ = (total_tiket_terjual / total_kapasitas_studio * 100.0) if total_kapasitas_studio > 0 else 0.0
        overall_occ = min(overall_occ, 100.0)

        # TAMPILAN METRIK METRIC CARD
        if enable_occupancy:
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("🎟 Tiket Terjual (Kolom BW)", f"{total_tiket_terjual:,}")
            m2.metric("💺 Total Kapasitas (Kolom BX)", f"{total_kapasitas_studio:,}")
            m3.metric("📊 Occupancy Rate", f"{overall_occ:.1f}%")
            m4.metric("🏢 Total Bioskop", f"{bio_unique['Bioskop'].nunique():,}")
            m5.metric("🏙️ Total Kota", f"{bio_unique['Kota'].nunique():,}")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🎟 Tiket Terjual (Kolom BW)", f"{total_tiket_terjual:,}")
            m2.metric("🏢 Bioskop Membuka ATS", f"{bio_unique['Bioskop'].nunique():,}")
            m3.metric("🏙️ Kota Terjangkau", f"{bio_unique['Kota'].nunique():,}")
            m4.metric("📅 Snapshot Data", f"{filtered_ats['Hari_Tanggal'].nunique():,}")

        st.markdown("---")

        tab_list = [
            "🏙️ Top Kota & Jaringan",
            "📊 Heatmap & Visualisasi Occupancy",
            "📅 Tren Penjualan per Snapshot Tanggal",
            "📋 Detail Data ATS"
        ]
        
        tabs = st.tabs(tab_list)

        # TAB 1: TOP KOTA & JARINGAN + REKAP TABEL BIOSKOP
        with tabs[0]:
            c_k1, c_k2 = st.columns(2)
            with c_k1:
                st.subheader("Penjualan per Induk Jaringan Bioskop")
                jaringan_summary = bio_unique.groupby("Jaringan")["Total_Admission"].sum().reset_index()
                fig_ats_j = px.pie(
                    jaringan_summary,
                    names="Jaringan",
                    values="Total_Admission",
                    hole=0.4,
                    title="Pangsa Presale per Jaringan",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                st.plotly_chart(fig_ats_j, width="stretch")

            with c_k2:
                st.subheader("Top 10 Kota Presale Terbanyak")
                kota_summary = bio_unique[~bio_unique["Kota"].str.upper().isin(["NAN", "NONE", "UNKNOWN", ""])].groupby("Kota")["Total_Admission"].sum().nlargest(10).reset_index()
                
                fig_ats_k = px.bar(
                    kota_summary,
                    x="Total_Admission",
                    y="Kota",
                    orientation="h",
                    color="Total_Admission",
                    color_continuous_scale="Blugrn",
                    text_auto=True,
                )
                fig_ats_k.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_ats_k, width="stretch")

            st.markdown("---")
            # 📌 TABEL REKAPITULASI PENJUALAN TIKET PER BIOSKOP (TETAP TERSEDIA AKURAT)
            st.subheader("🏢 Rekapitulasi Penjualan Tiket per Bioskop (Akurat dari Kolom BW & BX)")

            rekap_tabel = bio_unique.sort_values("Total_Admission", ascending=False).reset_index(drop=True)
            rekap_tabel.index = rekap_tabel.index + 1

            if enable_occupancy:
                st.dataframe(
                    rekap_tabel.style.format({
                        "Total_Admission": "{:,}",
                        "Total_Capacity": "{:,}",
                        "Occupancy_Rate_%": "{:.2f}%"
                    }),
                    width="stretch",
                    height=500
                )
            else:
                st.dataframe(
                    rekap_tabel[["Bioskop", "Kota", "Jaringan", "Total_Admission"]].style.format({
                        "Total_Admission": "{:,}"
                    }),
                    width="stretch",
                    height=500
                )

        # TAB 2: HEATMAP & VISUALISASI OCCUPANCY RATE (%)
        with tabs[1]:
            if enable_occupancy and not bio_unique.empty:
                st.subheader("📊 Visualisasi & Heatmap Occupancy Rate (%) per Bioskop")

                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    st.markdown("#### Top 15 Bioskop dengan Occupancy Rate Tertinggi (%)")
                    top_occ = bio_unique.nlargest(15, "Occupancy_Rate_%").sort_values("Occupancy_Rate_%", ascending=True)
                    fig_top_occ = px.bar(
                        top_occ,
                        x="Occupancy_Rate_%",
                        y="Bioskop",
                        orientation="h",
                        color="Occupancy_Rate_%",
                        color_continuous_scale="Reds",
                        text_auto=".1f",
                        hover_data=["Kota", "Jaringan", "Total_Admission", "Total_Capacity"]
                    )
                    fig_top_occ.update_layout(xaxis_title="Occupancy Rate (%)", yaxis_title="")
                    st.plotly_chart(fig_top_occ, width="stretch")

                with col_o2:
                    st.markdown("#### Rata-Rata Occupancy Rate (%) per Jaringan")
                    jaringan_occ = bio_unique.groupby("Jaringan").agg(
                        Avg_Occupancy=("Occupancy_Rate_%", "mean"),
                        Total_Admission=("Total_Admission", "sum"),
                        Total_Capacity=("Total_Capacity", "sum")
                    ).reset_index()
                    jaringan_occ["Jaringan_Occupancy_%"] = (jaringan_occ["Total_Admission"] / jaringan_occ["Total_Capacity"] * 100.0).round(2)

                    fig_jaringan_occ = px.bar(
                        jaringan_occ,
                        x="Jaringan",
                        y="Jaringan_Occupancy_%",
                        color="Jaringan_Occupancy_%",
                        color_continuous_scale="Viridis",
                        text_auto=".1f"
                    )
                    fig_jaringan_occ.update_layout(yaxis_title="Occupancy Rate (%)", xaxis_title="")
                    st.plotly_chart(fig_jaringan_occ, width="stretch")

                st.markdown("---")
                st.markdown("#### 🔥 Heatmap Occupancy Rate (%) berdasarkan Kota & Jaringan")
                
                pivot_occ = bio_unique.groupby(["Kota", "Jaringan"]).agg(
                    Adm=("Total_Admission", "sum"),
                    Cap=("Total_Capacity", "sum")
                ).reset_index()
                pivot_occ["Occupancy_%"] = (pivot_occ["Adm"] / pivot_occ["Cap"] * 100.0).round(1)

                heatmap_df = pivot_occ.pivot(index="Kota", columns="Jaringan", values="Occupancy_%").fillna(0)

                if not heatmap_df.empty:
                    fig_heatmap = px.imshow(
                        heatmap_df,
                        labels=dict(x="Jaringan Bioskop", y="Kota", color="Occupancy (%)"),
                        x=heatmap_df.columns,
                        y=heatmap_df.index,
                        color_continuous_scale="YlOrRd",
                        text_auto=True,
                        aspect="auto"
                    )
                    fig_heatmap.update_layout(height=max(400, len(heatmap_df) * 25))
                    st.plotly_chart(fig_heatmap, width="stretch")
            else:
                st.info("💡 Aktifkan opsi 'Hitung Occupancy Rate (%)' di sidebar untuk melihat tab analisis heatmap ini.")

        # TAB 3: TREN PENJUALAN SNAPSHOT TERURUT KRONOLOGIS
        with tabs[2]:
            st.subheader("📅 Perkembangan Tiket Presale Terjual per Snapshot Tanggal")
            
            ats_daily = (
                filtered_ats.groupby(["Hari_Tanggal", "_Date_Sort", "Nama_Film"])["Tiket_Terjual"]
                .sum()
                .reset_index()
                .sort_values("_Date_Sort")
            )

            fig_ats_daily = px.bar(
                ats_daily,
                x="Hari_Tanggal",
                y="Tiket_Terjual",
                color="Nama_Film",
                barmode="group",
                title="Penjualan Tiket per Snapshot Data (Terurut Kronologis)",
                text_auto=True,
                category_orders={"Hari_Tanggal": sorted_hari_tanggal}
            )
            fig_ats_daily.update_xaxes(categoryorder="array", categoryarray=sorted_hari_tanggal)
            st.plotly_chart(fig_ats_daily, width="stretch")

        # TAB 4: DETAIL DATA
        with tabs[3]:
            st.subheader("📋 Data Detail Rekapitulasi Presale (ATS)")
            st.dataframe(filtered_ats.drop(columns=["_Date_Sort"], errors="ignore"), width="stretch")