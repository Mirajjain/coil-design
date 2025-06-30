import streamlit as st
from fpdf import FPDF
from datetime import datetime

# === Page Setup ===
st.set_page_config(page_title="DX Coil Designer (R-410A)", layout="centered")
st.title("❄️ DX Cooling Coil Designer - R410A")

# === Input Section ===
col1, col2 = st.columns(2)

with col1:
    tr = st.number_input("Cooling Capacity (TR)", min_value=1.0, step=0.5)
    cfm = st.number_input("Airflow (CFM)", min_value=300)
    rows = st.number_input("No. of Coil Rows", min_value=1, step=1)
    fpi = st.number_input("Fins Per Inch (FPI)", min_value=8, max_value=16, step=1)

with col2:
    tubes_per_row = st.number_input("Tubes per Row", min_value=6, step=1)
    tube_dia_in = st.selectbox("Tube Diameter", ["3/8 inch", "1/2 inch", "5/8 inch"])
    tube_length_ft = st.number_input("Tube Length (ft per tube)", min_value=1.0, step=0.5)

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

# === PDF Function ===
def generate_pdf(tr, cfm, rows, fpi, tubes_per_row, tube_length_ft, tube_dia_in, total_tubes, total_copper_length, surface_area, circuits, flow_per_circuit, velocity_ft_s):
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
    filename = f"DX_Coil_Design_{tr}TR_{today.replace('-', '')}.pdf"
    pdf.output(filename)
    return filename

# === Main Logic ===
if st.button("🧮 Calculate DX Coil"):
    # --- Calculations ---
    btu_hr = tr * BTU_PER_TR
    total_tubes = tubes_per_row * rows
    total_copper_length = total_tubes * tube_length_ft
    circuits = round(tr * 2)
    flow_per_circuit = round(tr / circuits, 2)
    surface_area = round(total_copper_length * tube_area_ft2_per_ft[tube_dia_in], 2)

    # --- Velocity Calculation ---
    mass_flow_rate = tr * 180  # lb/hr
    mass_flow_rate_per_circuit = mass_flow_rate / circuits
    dia_in = tube_inner_dia_in[tube_dia_in]
    area_in2 = 3.1416 * (dia_in / 2) ** 2
    area_ft2 = area_in2 / 144
    refrigerant_density = 0.3  # lb/ft³ (approx R410A vapor)
    velocity_ft_s = (mass_flow_rate_per_circuit / 3600) / (refrigerant_density * area_ft2)

    # --- Display Results ---
    st.subheader("📊 Results:")
    st.write(f"🔹 Total Cooling Load: **{btu_hr:,} BTU/hr**")
    st.write(f"🔹 Total Tubes: **{total_tubes}**")
    st.write(f"🔹 Copper Tube Length: **{total_copper_length} ft**")
    st.write(f"🔹 Fin Surface Area: **{surface_area} ft²**")
    st.write(f"🔹 Suggested Circuits: **{circuits}**")
    st.write(f"🔹 Flow per Circuit: **{flow_per_circuit} TR**")

    st.markdown("---")
    st.subheader("💨 Refrigerant Flow Check")
    st.write(f"🔹 Refrigerant Velocity: **{velocity_ft_s:.2f} ft/s**")

    if velocity_ft_s < 40:
        st.warning("⚠️ Velocity too low — risk of oil return failure!")
    elif velocity_ft_s > 80:
        st.warning("⚠️ Velocity too high — possible noise or erosion!")
    else:
        st.success("✅ Velocity is within ideal range (40–80 ft/s)")

    # --- Download PDF ---
    if st.button("📥 Download PDF Report"):
        pdf_file = generate_pdf(
            tr, cfm, rows, fpi, tubes_per_row, tube_length_ft, tube_dia_in,
            total_tubes, total_copper_length, surface_area, circuits,
            flow_per_circuit, velocity_ft_s
        )
        st.success(f"✅ PDF saved as: {pdf_file}")
