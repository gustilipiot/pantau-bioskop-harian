import re
import pandas as pd
import plotly.express as px
import streamlit as st

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Cinema Showtime & Trend Analytics",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Live Dashboard & Trend Analytics Showtime Bioskop")
st.write(
    "Unggah file CSV harian (misal: 1 file per hari) untuk melihat tren perkembangan penayangan, pergerakan harga, dan perbandingan antar film."
)

# Sidebar Area Upload
st.sidebar.header("📥 Unggah Multi-File Harian")
uploaded_files = st.sidebar.file_uploader(
    "Pilih File CSV Harian",
    type=["csv"],
    accept_multiple_files=True,
)


def extract_date_and_film(filename):
    """Mencoba mengekstrak tanggal dan nama film dari nama file."""
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


def clean_and_process_data(files):
    all_dfs = []

    for file in files:
        df = pd.read_csv(file)

        extracted_date, film_name = extract_date_and_film(file.name)
        df["Nama_Film"] = film_name
        df["Tanggal_Str"] = (
            extracted_date if extracted_date else "Unknown Date"
        )

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
        combined = pd.concat(all_dfs, ignore_index=True)
        return combined
    return pd.DataFrame()


if uploaded_files:
    df_combined = clean_and_process_data(uploaded_files)

    # Filter Sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Filter Dashboard")

    film_list = sorted(df_combined["Nama_Film"].unique().tolist())
    selected_film = st.sidebar.multiselect(
        "Pilih Film", options=film_list, default=film_list
    )

    kota_list = sorted(df_combined["Kota"].dropna().unique().tolist())
    selected_kota = st.sidebar.multiselect(
        "Pilih Kota", options=kota_list, default=kota_list
    )

    filtered_df = df_combined[
        (df_combined["Nama_Film"].isin(selected_film))
        & (df_combined["Kota"].isin(selected_kota))
    ]

    # KPI Summary Cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🎬 Total Showtimes", f"{len(filtered_df):,}")
    c2.metric("📅 Jumlah Hari Data", f"{filtered_df['Tanggal_Str'].nunique():,}")
    c3.metric("🏢 Total Bioskop", f"{filtered_df['Bioskop'].nunique():,}")
    c4.metric("🏙️ Total Kota", f"{filtered_df['Kota'].nunique():,}")
    c5.metric(
        "💵 Rata-Rata Harga", f"Rp {filtered_df['Harga_Clean'].mean():,.0f}"
    )

    st.markdown("---")

    # Pembuatan Tab (Dipanggil di sini setelah data terisi)
    tab_trend, tab_compare, tab_sebaran, tab_jam, tab_raw = st.tabs(
        [
            "📈 Tren Harian",
            "🆚 Komparasi Film",
            "📊 Sebaran & Wilayah",
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
                title="Jumlah Bioskop Aktif Menayangkan per Hari",
            )
            st.plotly_chart(fig_trend_bioskop, use_container_width=True)

        with col_t2:
            fig_trend_harga = px.line(
                trend_daily,
                x="Tanggal_Str",
                y="Rata_Harga",
                color="Nama_Film",
                markers=True,
                title="Pergerakan Rata-Rata Harga Tiket Harian (Rp)",
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
            )
            fig_kota.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_kota, use_container_width=True)

        with c_s2:
            st.subheader("Komposisi Jaringan Bioskop")
            bioskop_counts = (
                filtered_df["Bioskop"].value_counts().head(10).reset_index()
            )
            bioskop_counts.columns = ["Bioskop", "Showtimes"]
            fig_bio = px.pie(
                bioskop_counts,
                names="Bioskop",
                values="Showtimes",
                hole=0.4,
            )
            st.plotly_chart(fig_bio, use_container_width=True)

    with tab_jam:
        st.subheader("🕒 Distribusi Jam Tayang (Peak Hours)")
        jam_counts = (
            filtered_df["Jam_Tayang"].value_counts().head(15).reset_index()
        )
        jam_counts.columns = ["Jam Tayang", "Jumlah Sesi"]
        fig_jam = px.bar(
            jam_counts,
            x="Jam Tayang",
            y="Jumlah Sesi",
            color="Jumlah Sesi",
            color_continuous_scale="Oranges",
        )
        st.plotly_chart(fig_jam, use_container_width=True)

    with tab_raw:
        st.subheader("📋 Data Rekapitulasi Gabungan")
        st.dataframe(filtered_df, use_container_width=True)

else:
    st.info(
        "👈 Silakan unggah beberapa file CSV harian di sidebar sebelah kiri untuk menampilkan grafik dan analisis komparasi."
    )