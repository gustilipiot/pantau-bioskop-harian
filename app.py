import re
import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================
# KONFIGURASI HALAMAN STREAMLIT
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
    ["🎬 Showtime Harian", "🎟️ Advance Ticket Sales (ATS)"],
)


# ==========================================
# HELPER: PEMETAAN INDUK JARINAGAN BIOSKOP
# ==========================================
def map_jaringan_bioskop(bioskop_name):
    name_upper = str(bioskop_name).upper().strip()

    if "PLATINUM" in name_upper:
        return "Platinum"
    elif "CGV" in name_upper or "BLITZ" in name_upper:
        return "CGV"
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


def parse_ticket_value(val):
    """Menangani angka biasa, teks, maupun rumus penjumlahan seperti '731+411'."""
    val_str = str(val).strip()
    if not val_str or val_str.lower() == "nan":
        return 0

    if "+" in val_str:
        numbers = re.findall(r"\d+", val_str)
        return sum(int(n) for n in numbers)

    match = re.search(r"\d+", val_str)
    return int(match.group(0)) if match else 0


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
    """Membaca seluruh section film dan jaringan (XXI, CGV, Cinepolis, dll.) dalam 1 file ATS."""
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
            if "LOKASI" in row_str or any(
                j in row_str for j in ["XXI", "CGV", "CINEPOLIS", "PLATINUM"]
            ):
                if any(
                    "SHOW" in str(v).upper() or "SEPTEMBER" in str(v).upper()
                    for v in row
                ):
                    header_rows.append(idx)

        if not header_rows:
            header_rows = [1]

        film_sections = []

        for i, h_idx in enumerate(header_rows):
            title_row = df_raw.iloc[max(0, h_idx - 1)].dropna()
            film_title = "Unknown Film"
            for val in title_row:
                s_val = str(val).strip()
                if (
                    s_val.upper()
                    not in ["NO", "XXI", "CGV", "LOKASI", "CINEPOLIS", ""]
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
            data_rows = data_rows[
                ~data_rows["Bioskop"]
                .astype(str)
                .str.contains("TOTAL", case=False)
            ]
            data_rows = data_rows[
                ~data_rows["Kota"].astype(str).str.contains("TOTAL", case=False)
            ]

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
            melted["Sesi_Show"] = melted["Tanggal_Sesi"].apply(
                lambda x: str(x).split(" | ")[1]
                if " | " in str(x)
                else "SHOW"
            )

            # PARSE NILAI TIKET DENGAN FUNGSI PENJUMLAHAN PRESISI (misal: '731+411' -> 1142)
            melted["Tiket_Terjual"] = melted["Tiket_Terjual"].apply(
                parse_ticket_value
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
# MODE 1: SHOWTIME HARIAN ANALYTICS
# ==========================================
if app_mode == "🎬 Showtime Harian":
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
            st.plotly_chart(fig_trend_showtime, use_container_width=True)

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
                st.plotly_chart(fig_trend_bioskop, use_container_width=True)

            with col_t2:
                fig_trend_harga = px.line(
                    trend_daily,
                    x="Tanggal_Str",
                    y="Rata_Harga",
                    color="Nama_Film",
                    markers=True,
                    title="Rata-Rata Harga Tiket Harian (Rp)",
                )
                st.plotly_chart(fig_trend_harga, use_container_width=True)

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
                use_container_width=True,
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
                st.plotly_chart(fig_comp_showtimes, use_container_width=True)

            with c_comp2:
                fig_comp_bioskop = px.bar(
                    film_summary,
                    x="Nama_Film",
                    y="Jangkauan_Bioskop",
                    color="Nama_Film",
                    title="Perbandingan Ekspansi Jaringan Bioskop",
                    text_auto=True,
                )
                st.plotly_chart(fig_comp_bioskop, use_container_width=True)

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
                    title="Komposisi Induk Jaringan Bioskop",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                st.plotly_chart(fig_jaringan, use_container_width=True)

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
                st.plotly_chart(fig_kota, use_container_width=True)

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
                    use_container_width=True,
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
            st.plotly_chart(fig_jam, use_container_width=True)

        with tab_raw:
            st.subheader("📋 Data Detail Showtime")
            st.dataframe(filtered_df, use_container_width=True)

    else:
        st.info("👈 Silakan unggah file CSV Showtime di sidebar sebelah kiri.")


# ==========================================
# MODE 2: ADVANCE TICKET SALES (ATS) ANALYTICS
# ==========================================
elif app_mode == "🎟️ Advance Ticket Sales (ATS)":
    st.markdown("### 🎟️ Dashboard Advance Ticket Sales (ATS / Presale)")

    st.sidebar.markdown("---")
    st.sidebar.header("📥 Sumber Data ATS")

    ats_source = st.sidebar.radio(
        "Pilih Metode Input Data ATS:",
        ["🔗 Google Sheets (Live Link)", "📁 Upload File Manual"],
    )

    df_ats = pd.DataFrame()

    if ats_source == "🔗 Google Sheets (Live Link)":
        gsheet_url = st.sidebar.text_input(
            "URL CSV Published Google Sheets:",
            placeholder="https://docs.google.com/spreadsheets/d/e/.../pub?output=csv",
        )
        if st.sidebar.button("🔄 Reload Data Google Sheets"):
            st.cache_data.clear()

        if gsheet_url:
            df_ats = process_single_ats_file(gsheet_url, is_url=True)
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
        ]

        # Summary Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "🎟️ Total Tiket Terjual (ATS)",
            f"{filtered_ats['Tiket_Terjual'].sum():,}",
        )
        m2.metric(
            "🏢 Bioskop Membuka ATS",
            f"{filtered_ats['Bioskop'].nunique():,}",
        )
        m3.metric("🏙️ Kota Terjangkau", f"{filtered_ats['Kota'].nunique():,}")
        m4.metric(
            "📅 Hari Penayangan Presale",
            f"{filtered_ats['Hari_Tanggal'].nunique():,}",
        )

        st.markdown("---")

        tab_ats_overview, tab_ats_sesi, tab_ats_kota, tab_ats_raw = st.tabs(
            [
                "📅 Penjualan per Hari & Tanggal",
                "🕒 Demografi Sesi Show",
                "🏙️ Top Kota & Jaringan",
                "📋 Detail Data ATS",
            ]
        )

        with tab_ats_overview:
            st.subheader("📅 Total Tiket Presale Terjual per Hari & Tanggal")

            ats_daily = (
                filtered_ats.groupby(["Hari_Tanggal", "Nama_Film"])[
                    "Tiket_Terjual"
                ]
                .sum()
                .reset_index()
            )

            # PENGURUTAN HARI SECARA KRONOLOGIS
            day_order = {
                "JUMAT": 1,
                "SABTU": 2,
                "MINGGU": 3,
                "SENIN": 4,
                "SELASA": 5,
                "RABU": 6,
                "KAMIS": 7,
            }

            def get_day_rank(val):
                first_word = str(val).split()[0].upper()
                return day_order.get(first_word, 99)

            ats_daily["Rank"] = ats_daily["Hari_Tanggal"].apply(get_day_rank)
            ats_daily = ats_daily.sort_values("Rank")

            fig_ats_daily = px.bar(
                ats_daily,
                x="Hari_Tanggal",
                y="Tiket_Terjual",
                color="Nama_Film",
                barmode="group",
                title="Penjualan Tiket Berdasarkan Hari Penayangan",
                labels={
                    "Hari_Tanggal": "Hari & Tanggal Penayangan",
                    "Tiket_Terjual": "Jumlah Tiket Terjual",
                },
                text_auto=True,
            )
            st.plotly_chart(fig_ats_daily, use_container_width=True)

            st.subheader("📊 Tabel Ringkasan Penjualan Harian")
            pivot_daily = filtered_ats.pivot_table(
                index="Hari_Tanggal",
                columns="Nama_Film",
                values="Tiket_Terjual",
                aggfunc="sum",
                fill_value=0,
            )
            pivot_daily["TOTAL TIKET"] = pivot_daily.sum(axis=1)
            st.dataframe(
                pivot_daily.style.format("{:,}"), use_container_width=True
            )

        with tab_ats_sesi:
            st.subheader("🕒 Demand Tiket Berdasarkan Sesi Show (Show 1 - 5)")
            ats_show = (
                filtered_ats.groupby(["Sesi_Show", "Nama_Film"])[
                    "Tiket_Terjual"
                ]
                .sum()
                .reset_index()
            )

            fig_ats_show = px.bar(
                ats_show,
                x="Sesi_Show",
                y="Tiket_Terjual",
                color="Nama_Film",
                barmode="group",
                title="Perbandingan Penjualan Tiket per Jam Show",
                text_auto=True,
            )
            st.plotly_chart(fig_ats_show, use_container_width=True)

        with tab_ats_kota:
            c_k1, c_k2 = st.columns(2)
            with c_k1:
                st.subheader("Penjualan per Induk Jaringan Bioskop")
                top_ats_jaringan = (
                    filtered_ats.groupby("Jaringan")["Tiket_Terjual"]
                    .sum()
                    .reset_index()
                )
                fig_ats_j = px.pie(
                    top_ats_jaringan,
                    names="Jaringan",
                    values="Tiket_Terjual",
                    hole=0.4,
                    title="Pangsa Presale per Jaringan",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                st.plotly_chart(fig_ats_j, use_container_width=True)

            with c_k2:
                st.subheader("Top 10 Kota Presale Terbanyak")
                top_ats_kota = (
                    filtered_ats.groupby("Kota")["Tiket_Terjual"]
                    .sum()
                    .nlargest(10)
                    .reset_index()
                )
                fig_ats_k = px.bar(
                    top_ats_kota,
                    x="Tiket_Terjual",
                    y="Kota",
                    orientation="h",
                    color="Tiket_Terjual",
                    color_continuous_scale="Blugrn",
                    text_auto=True,
                )
                fig_ats_k.update_layout(
                    yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(fig_ats_k, use_container_width=True)

        with tab_ats_raw:
            st.subheader("📋 Data Rekapitulasi Presale (ATS)")
            st.dataframe(filtered_ats, use_container_width=True)

    elif ats_source == "📁 Upload File Manual" and not uploaded_ats:
        st.info("👈 Silakan unggah file Excel/CSV ATS di sidebar sebelah kiri.")