# SCMS | Global Transportation Optimization

Dashboard Streamlit untuk model transportasi (NWC, LCM, VAM, MODI) dengan peta rute OpenStreetMap.
Data SCMS dan koordinat sudah disertakan, jadi aplikasi langsung menampilkan hasil tanpa upload.

## Menjalankan di komputer sendiri
    pip install -r requirements.txt
    streamlit run app.py
Buka http://localhost:8501 (atau alamat Network URL yang tampil di terminal untuk akses dari perangkat lain).

## Deploy online (Streamlit Community Cloud)
1. Upload seluruh isi folder ini ke repositori GitHub (pastikan folder `data/` ikut).
2. Di share.streamlit.io pilih repositori tersebut, file utama `app.py`.

## Struktur
- app.py : tampilan dan navigasi (Overview, Data Management, Algorithm Analysis, Distribution Map)
- core.py : pembacaan data, NWC, LCM, VAM, MODI
- mapviz.py : peta rute (warna garis, ukuran node, legenda)
- data/scms_data_model_transportasi.xlsx : data bawaan (sheet Data_Bersih dan Matriks_Biaya)
- data/coordinates_filled.csv : koordinat node (kolom node, tipe, lat, lon). Perkiraan; ganti sesuai kebutuhan.

## Mengganti data
Sidebar > "Ganti data (opsional)": upload workbook (format sama dengan data bawaan) dan/atau CSV koordinat.
CSV koordinat boleh memakai kolom node/name, lat/latitude, lon/lng/longitude.
