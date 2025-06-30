import streamlit as st
from fpdf import FPDF
from datetime import datetime
import io

# === Constants ===
BTU_PER_TR = 12000
tube_area_ft2_per_ft = {
    "3/8 inch": 0.0096,
    "1/2 inch": 0.0136,
    "5/8 inch": 0.0176
}
tube_inner_dia_in = {
    "3/8 inch": 0.311,
    "1/2 inch": 0.402,
    "5/8 inch": 0.527
}

# === PDF Function (In-Memory) ===
def generate_pdf_bytes(tr, cfm, rows, fpi, tubes_per_row, tube_length_ft, tube_dia_in, total_tubes, total_copper_length, surface_area, circuits, flow_per_circuit, velocity_ft_s):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    today = datetime.now().strftime("%d-%m-%Y")

    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, txt="DX Coil Design Report - R410A", ln=1, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, txt=f"Factory: Your HVAC Company", ln=1)
    pdf.cell(200, 10, txt=f"Date: {today}", ln=1)
    pdf.ln(5)

    pdf.cell(200, 10, txt=f"Cooling Capacity: {tr} TR", ln=1)
    pdf.cell(200, 10, txt=f"Airflow: {cfm} CFM", ln=1)
    pdf.cell(200, 10, txt=f"Rows: {rows}, FPI: {fpi}, Tubes/Row: {tubes_per_row}", ln=1)
    pdf.cell(200, 10, txt=f"Tube Diameter: {tube_dia_in}", ln=1)
    pdf.cell(200, 10, txt=f"Tube Length per Tube: {tube_length_ft} ft", ln=1)
    pdf.ln(5)

    pdf.cell(200, 10, txt=f"Total Tubes: {total_tubes}", ln=1)
    pdf.cell(200, 10, txt=f"Total Copper Tube Length: {total_copper_length} ft", ln=1)
    pdf.cell(200, 10, txt=f"Fin Surface Area: {surface_area} ft²", ln=1)
    pdf.cell(200, 10, txt=f"Circuits: {circuits}", ln=1)
    pdf.cell(200, 10, txt=f"Flow per Circuit: {flow_per_circuit} TR", ln=1)
    pdf.cell(200, 10, txt=f"Refrigerant Velocity: {velocity_ft_s:.2f} ft/s", ln=1)

    if velocity_ft_s < 40:
        pdf.set_text_color(200, 0, 0)
        pdf.cell(200, 10, txt="⚠️ Velocity too low — risk of oil return failure", ln=1)
    elif velocity_ft_s > 80:
        pdf.set_text_color(255, 140, 0)
        pdf.cell(200, 10, txt="⚠️ Velocity too high — risk of noise/erosion", ln=1)
    else:
        pdf.set_text_color(0, 150, 0)
        pdf.cell(200, 10, txt="✅ Velocity is within optimal range (40–80 ft/s)", ln=1)

    pdf.set_text_color(0, 0, 0)
    buffer = io.BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# === Streamlit UI ===
st.set_page_config(page_title="DX Coil Designer", layout="centered")
st.title("❄️ DX Cooling Coil Designer - R410A")

# === Inputs ===
col1, col2 = st.columns(2)
with col1:
    tr = st.number_input("Cooling Capacity (TR)", min_value=1.0, step=0.5)
    cfm = st.number_input("Airflow (CFM)", min_value=300)
    rows = st.number_input("Coil Rows", min_value=1, step=1)
    fpi = st.number_input("Fins Per Inch (FPI)", min_value=8, max_value=16, step=1)
with col2:
    tubes_per_row = st.number_input("Tubes per Row", min_value=6, step=1)
    tube_dia_in = st.selectbox("Tube Diameter", ["3/8 inch", "1/2 inch", "5/8 inch"])
    tube_length_ft = st.number_input("Tube Length (ft)", min_value=1.0, step=0.5)

# === Calculation ===
if st.button("🧲 Calculate DX Coil"):
    btu_hr = tr * BTU_PER_TR
    total_tubes = tubes_per_row * rows
    total_copper_length = total_tubes * tube_length_ft
    surface_area = round(total_copper_length * tube_area_ft2_per_ft[tube_dia_in], 2)
    circuits = round(tr * 2)
    flow_per_circuit = round(tr / circuits, 2)

    # === Refrigerant velocity (correct for R-410A) ===
    capacity_kw = tr * 3.517
    latent_heat_kj_per_kg = 300
    mass_flow_rate_kg_s = (capacity_kw * 1000) / latent_heat_kj_per_kg
    mass_flow_rate_per_circuit = mass_flow_rate_kg_s / circuits

    dia_in = tube_inner_dia_in[tube_dia_in]
    dia_m = dia_in * 0.0254
    area_m2 = 3.1416 * (dia_m / 2) ** 2
    refrigerant_density = 19  # kg/m^3 for R-410A

    velocity_m_s = mass_flow_rate_per_circuit / (refrigerant_density * area_m2)
    velocity_ft_s = velocity_m_s * 3.28084

    st.session_state.result = {
        'tr': tr, 'cfm': cfm, 'rows': rows, 'fpi': fpi,
        'tubes_per_row': tubes_per_row, 'tube_length_ft': tube_length_ft,
        'tube_dia_in': tube_dia_in, 'total_tubes': total_tubes,
        'total_copper_length': total_copper_length, 'surface_area': surface_area,
        'circuits': circuits, 'flow_per_circuit': flow_per_circuit,
        'velocity_ft_s': velocity_ft_s
    }

    # Output
    st.subheader("📊 Results")
    st.write(f"🔹 Total Cooling Load: {btu_hr:,} BTU/hr")
    st.write(f"🔹 Total Tubes: {total_tubes}")
    st.write(f"🔹 Copper Tube Length: {total_copper_length} ft")
    st.write(f"🔹 Surface Area: {surface_area} ft²")
    st.write(f"🔹 Circuits: {circuits}")
    st.write(f"🔹 Flow per Circuit: {flow_per_circuit} TR")
    st.write(f"🔹 Refrigerant Velocity: {velocity_ft_s:.2f} ft/s")

    if velocity_ft_s < 40:
        st.warning("⚠️ Too low velocity — oil return issue")
    elif velocity_ft_s > 80:
        st.warning("⚠️ Too high velocity — erosion risk")
    else:
        st.success("✅ Velocity is optimal")

# === Download PDF Button ===
if 'result' in st.session_state:
    r = st.session_state.result
    pdf_file = generate_pdf_bytes(
        r['tr'], r['cfm'], r['rows'], r['fpi'], r['tubes_per_row'],
        r['tube_length_ft'], r['tube_dia_in'], r['total_tubes'],
        r['total_copper_length'], r['surface_area'], r['circuits'],
        r['flow_per_circuit'], r['velocity_ft_s']
    )
    st.download_button(
        label="📅 Download PDF Report",
        data=pdf_file,
        file_name=f"DX_Coil_{r['tr']}TR_Report.pdf",
        mime="application/pdf"
    )
