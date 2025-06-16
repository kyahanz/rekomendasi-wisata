import streamlit as st
import pandas as pd
import random
from itertools import cycle
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe

# Load data tempat wisata
places_df = pd.read_csv("tourism_with_id.csv")

# Normalisasi kolom
places_df.columns = places_df.columns.str.strip().str.lower()

# Filter hanya destinasi di Bandung
places_df = places_df[places_df['city'].str.lower().str.contains("bandung")]

# Konfigurasi halaman
st.set_page_config(page_title="Bandung Explorer - Itinerary Cerdas", layout="wide")
st.title("🧳 Bandung Explorer")
st.markdown("Bantu kamu memilih destinasi terbaik di Bandung berdasarkan preferensi dan anggaran.")

# Session state untuk menyimpan itinerary yang sedang aktif
if "itinerary" not in st.session_state:
    st.session_state.itinerary = {}

# Fungsi koneksi ke Google Sheets
@st.cache_resource
def setup_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("reliable-plasma-437208-g3-87a9070a0e82.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1zJv9sNtE41B1sDWst_i2PbXgmtE3Be-X4IHtd0vta1Q/edit#gid=0")
    return sheet.sheet1

# Input preferensi pengguna
st.sidebar.header("🧭 aIsi Preferensi Kamu")
nama_pengguna = st.sidebar.text_input("Nama Anda:")
selected_categories = st.sidebar.multiselect("Pilih Kategori Wisata Favorit:", options=places_df['category'].dropna().unique(), default=None)
max_budget = st.sidebar.number_input("Berapa budget kamu (Rp)?", min_value=0, value=300000, step=50000)
max_place = st.sidebar.slider("Mau berapa tempat dikunjungi?", 2, 5, 3)
submit_btn = st.sidebar.button("🚀 Tampilkan Itinerary")
refresh_btn = st.sidebar.button("🔄 Refresh Rekomendasi")

if submit_btn or refresh_btn:
    filtered_places = places_df[(places_df['price'] <= max_budget)]
    if selected_categories:
        filtered_places = filtered_places[filtered_places['category'].isin(selected_categories)]

    filtered_places = filtered_places.sample(frac=1, random_state=random.randint(1, 9999)).reset_index(drop=True)

    best_rated = filtered_places.sort_values(by="rating", ascending=False).head(max_place)
    cheapest = filtered_places.sort_values(by="price", ascending=True).head(max_place)

    most_expensive = []
    total = 0
    for _, row in filtered_places.sort_values(by="price", ascending=False).iterrows():
        if total + row["price"] <= max_budget and len(most_expensive) < max_place:
            most_expensive.append(row)
            total += row["price"]
    most_expensive = pd.DataFrame(most_expensive)

    st.session_state.itinerary = {
        "best_rated": best_rated,
        "cheapest": cheapest,
        "most_expensive": most_expensive,
        "nama": nama_pengguna
    }

# Fungsi tampil itinerary dengan jam unik
waktu_jam = [
    ("Pagi", "08.00"),
    ("Siang", "11.00"),
    ("Sore", "14.00"),
    ("Petang", "17.00"),
    ("Malam", "19.00")
]

def tampilkan_itinerary(title, df):
    st.subheader(title)
    total_price = 0
    waktu_cycle = cycle(waktu_jam)
    waktu_terpakai = set()

    for _, row in df.iterrows():
        while True:
            waktu_label, jam = next(waktu_cycle)
            if waktu_label not in waktu_terpakai:
                waktu_terpakai.add(waktu_label)
                break
            elif len(waktu_terpakai) >= len(waktu_jam):
                waktu_label += " (opsional)"
                break

        st.markdown(f"### {waktu_label} - {row['place_name']} ({jam})")
        st.markdown(f"📍 Kota: {row['city']}")
        st.markdown(f"🏷️ Kategori: {row['category']}")
        st.markdown(f"💰 Harga Tiket: Rp {int(row['price']):,}")
        st.markdown(f"⭐ Rating: {row['rating']}")
        with st.expander("📖 Lihat Deskripsi Lengkap"):
            st.write(row['description'])
        st.markdown("---")
        total_price += row['price']

    st.success(f"💸 Total Estimasi Biaya: Rp {int(total_price):,}")

# Tampilkan itinerary jika ada
if st.session_state.itinerary:
    nama_pengguna = st.session_state.itinerary.get("nama", "")
    st.markdown(f"### Selamat Datang, {nama_pengguna} 👋")
    tampilkan_itinerary("✨ Itinerary Rekomendasi Terbaik (Rating Tertinggi)", st.session_state.itinerary["best_rated"])
    tampilkan_itinerary("💸 Itinerary Termurah", st.session_state.itinerary["cheapest"])
    tampilkan_itinerary("💰 Itinerary Paling Mewah", st.session_state.itinerary["most_expensive"])

    st.subheader("🗳️ Bagaimana Pengalamanmu?")
    selected_itinerary = st.selectbox("Pilih Itinerary untuk Dinilai:", ["best_rated", "cheapest", "most_expensive"], format_func=lambda x: {"best_rated": "Rating Tertinggi", "cheapest": "Termurah", "most_expensive": "Paling Mewah"}[x])
    rating_data = []
    current_df = st.session_state.itinerary[selected_itinerary]
    for i, row in current_df.iterrows():
        rating_input = st.slider(
            f"Rating untuk {row['place_name']}:",
            min_value=1.0, max_value=5.0, value=4.0, step=0.1, key=f"rate_{selected_itinerary}_{row['place_id']}"
        )
        rating_data.append((row['place_name'], rating_input))

if st.button("✅ Kirim Rating"):
    st.success("Terima kasih atas penilaianmu!")
    sheet = setup_gsheet()
    existing = pd.DataFrame(sheet.get_all_records(), dtype=str)
    existing.columns = [col.strip().lower() for col in existing.columns]

    if not {'user_id', 'place_id', 'place_ratings'}.issubset(set(existing.columns)):
        st.error("❌ Kolom header di Google Sheet tidak sesuai. Harus: user_id, place_id, place_ratings")
    else:
        existing["user_id"] = pd.to_numeric(existing["user_id"], errors="coerce")
        user_id = int(existing["user_id"].max()) + 1 if not existing.empty else 1

        new_rows = []
        for nama, rating in rating_data:
            match = places_df[places_df['place_name'] == nama]['place_id']
            place_id = int(match.iloc[0]) if not match.empty else -1
            if place_id != -1:
                new_rows.append({
                    "user_id": user_id,
                    "place_id": place_id,
                    "place_ratings": rating
                })
                st.write(f"{nama}: {rating:.1f} ⭐ (disimpan ke Google Sheet)")

        if new_rows:
            updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
            sheet.clear()
            set_with_dataframe(sheet, updated)
