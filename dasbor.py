import pandas as pd
import streamlit as st

st.title("🎬 Live Dashboard Showtime Bioskop")

# 1. Fitur Upload File
uploaded_files = st.file_uploader(
    "Unggah CSV Showtime Harian", type=["csv"], accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        df = pd.read_csv(file)

        # Extraction info dari nama file atau kolom Tambahan
        # Transformasi Harga (Rp 30.000 -> 30000)
        df["Harga_Clean"] = (
            df["Harga"]
            .str.replace("Rp ", "", regex=False)
            .str.replace(".", "", regex=False)
            .astype(float)
        )

        # Unpivot jam tayang
        jam_cols = [c for c in df.columns if c.startswith("Jam_")]
        df_melted = pd.melt(
            df,
            id_vars=["Kota", "Bioskop", "Studio", "Harga_Clean"],
            value_vars=jam_cols,
            var_name="Sesi",
            value_name="Jam_Tayang",
        ).dropna(subset=["Jam_Tayang"])

        all_data.append(df_melted)

    # Gabung semua data
    final_df = pd.concat(all_data, ignore_index=True)

    # 2. Visualisasi Dashboard
    st.metric("Total Showtimes", len(final_df))
    st.metric("Total Bioskop", final_df["Bioskop"].nunique())

    # Distribusi per Kota
    st.subheader("Jumlah Penayangan per Kota")
    st.bar_chart(final_df["Kota"].value_counts().head(10))

    # Detail Data
    st.dataframe(final_df)