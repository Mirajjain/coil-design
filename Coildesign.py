import streamlit as st
from fpdf import FPDF
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import io
import math
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === ENHANCED CONSTANTS ===
BTU_PER_TR = 12000
TR_PER_ROW_EST = 1.75
TUBE_PITCH_MM = 25
TUBE_LENGTH_FT = 4.0
TARGET_FACE_VELOCITY_FPM = 450
MIN_REFRIGERANT_VELOCITY = 8.0  # ft/s for oil return
MAX_REFRIGERANT_VELOCITY = 60.0  # ft/s to avoid excessive pressure drop
MAX_AIR_PRESSURE_DROP = 0.6  # inches WG

# Enhanced tube properties with more accurate data
TUBE_PROPERTIES = {
    "3/8 inch": {
        "outer_dia_in": 0.375,
        "inner_dia_in": 0.311,
        "wall_thickness_in": 0.032,
        "area_ft2_per_ft": 0.0982,
        "flow_area_in2": 0.0760,
        "perimeter_ft": 0.0982
    },
    "1/2 inch": {
        "outer_dia_in": 0.500,
        "inner_dia_in": 0.402,
        "wall_thickness_in": 0.049,
        "area_ft2_per_ft": 0.1309,
        "flow_area_in2": 0.1267,
        "perimeter_ft": 0.1309
    },
    "5/8 inch": {
        "outer_dia_in": 0.625,
        "inner_dia_in": 0.527,
        "wall_thickness_in": 0.049,
        "area_ft2_per_ft": 0.1636,
        "flow_area_in2": 0.2182,
        "perimeter_ft": 0.1636
    }
}

# === ENHANCED REFRIGERANT PROPERTIES ===
REFRIGERANT_PROPERTIES = {
    "R410A": {
        "refrigerating_effect_btu_per_lbm": 51.5,
        "vapor_density_lbm_per_ft3": 3.43,
        "liquid_density_lbm_per_ft3": 70.5,
        "dynamic_viscosity_lbm_per_ft_hr": 0.030,
        "thermal_conductivity_btu_per_hr_ft_f": 0.0058,
        "specific_heat_btu_per_lbm_f": 0.38,
        "evap_temp_f": 40,
        "cond_temp_f": 105,
        "circuits_per_tr": 0.6,
        "min_velocity_fps": 10,
        "max_velocity_fps": 50
    },
    "R32": {
        "refrigerating_effect_btu_per_lbm": 95.2,
        "vapor_density_lbm_per_ft3": 2.85,
        "liquid_density_lbm_per_ft3": 60.8,
        "dynamic_viscosity_lbm_per_ft_hr": 0.028,
        "thermal_conductivity_btu_per_hr_ft_f": 0.0072,
        "specific_heat_btu_per_lbm_f": 0.45,
        "evap_temp_f": 40,
        "cond_temp_f": 105,
        "circuits_per_tr": 0.7,
        "min_velocity_fps": 8,
        "max_velocity_fps": 55
    },
    "R134a": {
        "refrigerating_effect_btu_per_lbm": 71.8,
        "vapor_density_lbm_per_ft3": 4.12,
        "liquid_density_lbm_per_ft3": 75.2,
        "dynamic_viscosity_lbm_per_ft_hr": 0.032,
        "thermal_conductivity_btu_per_hr_ft_f": 0.0051,
        "specific_heat_btu_per_lbm_f": 0.35,
        "evap_temp_f": 40,
        "cond_temp_f": 105,
        "circuits_per_tr": 0.5,
        "min_velocity_fps": 12,
        "max_velocity_fps": 45
    },
    "R407C": {
        "refrigerating_effect_btu_per_lbm": 58.3,
        "vapor_density_lbm_per_ft3": 3.28,
        "liquid_density_lbm_per_ft3": 68.9,
        "dynamic_viscosity_lbm_per_ft_hr": 0.031,
        "thermal_conductivity_btu_per_hr_ft_f": 0.0055,
        "specific_heat_btu_per_lbm_f": 0.37,
        "evap_temp_f": 40,
        "cond_temp_f": 105,
        "circuits_per_tr": 0.6,
        "min_velocity_fps": 10,
        "max_velocity_fps": 50
    }
}

# === ENHANCED CALCULATION FUNCTIONS ===

def validate_inputs(tr, cfm, tube_dia, refrigerant):
    """Validate input parameters"""
    errors = []
    warnings = []
    
    if tr <= 0 or tr > 100:
        errors.append("Cooling capacity must be between 0.1 and 100 TR")
    
    if cfm <= 0 or cfm > 50000:
        errors.append("Airflow must be between 1 and 50,000 CFM")
    
    # Check CFM/TR ratio
    cfm_per_tr = cfm / tr if tr > 0 else 0
    if cfm_per_tr < 300:
        warnings.append(f"Low CFM/TR ratio ({cfm_per_tr:.0f}). Typical range: 350-450 CFM/TR")
    elif cfm_per_tr > 500:
        warnings.append(f"High CFM/TR ratio ({cfm_per_tr:.0f}). Typical range: 350-450 CFM/TR")
    
    return errors, warnings

def calculate_coil_geometry(tr_design, cfm, tube_dia):
    """Calculate basic coil geometry with improved accuracy"""
    try:
        # Estimate rows based on capacity with better correlation
        rows = max(1, round(tr_design / TR_PER_ROW_EST))
        
        # Calculate required face area
        required_face_area_ft2 = cfm / TARGET_FACE_VELOCITY_FPM
        
        # Calculate tubes per row with tube pitch consideration
        tube_pitch_ft = TUBE_PITCH_MM / 304.8  # Convert mm to ft
        tubes_per_row_float = required_face_area_ft2 / (TUBE_LENGTH_FT * tube_pitch_ft)
        tubes_per_row = max(1, round(tubes_per_row_float))
        
        # Recalculate actual dimensions
        actual_coil_width_ft = tubes_per_row * tube_pitch_ft
        actual_face_area_ft2 = TUBE_LENGTH_FT * actual_coil_width_ft
        actual_face_velocity_fpm = cfm / actual_face_area_ft2
        
        # Total tubes and surface area
        total_tubes = rows * tubes_per_row
        tube_props = TUBE_PROPERTIES[tube_dia]
        total_length_ft = total_tubes * TUBE_LENGTH_FT
        surface_area_ft2 = total_length_ft * tube_props["area_ft2_per_ft"]
        
        return {
            "rows": rows,
            "tubes_per_row": tubes_per_row,
            "total_tubes": total_tubes,
            "actual_face_area_ft2": actual_face_area_ft2,
            "actual_face_velocity_fpm": actual_face_velocity_fpm,
            "surface_area_ft2": surface_area_ft2,
            "coil_width_ft": actual_coil_width_ft,
            "coil_depth_ft": rows * tube_pitch_ft
        }
    except Exception as e:
        logger.error(f"Error in coil geometry calculation: {e}")
        raise

def calculate_enhanced_circuits(tr_design, geometry, refrigerant):
    """Enhanced circuit calculation with multiple constraints"""
    try:
        ref_props = REFRIGERANT_PROPERTIES[refrigerant]
        
        # Method 1: Based on refrigerant capacity recommendations
        circuits_from_capacity = max(1, round(tr_design / ref_props["circuits_per_tr"]))
        
        # Method 2: Based on tube count (max 16-20 tubes per circuit)
        max_tubes_per_circuit = 18
        circuits_from_tubes = max(1, math.ceil(geometry["total_tubes"] / max_tubes_per_circuit))
        
        # Method 3: Based on mass flow rate (avoid excessive velocities)
        capacity_btu_hr = tr_design * BTU_PER_TR
        total_mass_flow = capacity_btu_hr / ref_props["refrigerating_effect_btu_per_lbm"]
        
        # Estimate circuits needed to maintain reasonable velocity
        # Assume target velocity of 25 ft/s per circuit
        target_velocity = 25  # ft/s
        tube_props = TUBE_PROPERTIES[list(TUBE_PROPERTIES.keys())[1]]  # Default to 1/2 inch
        flow_area_ft2 = tube_props["flow_area_in2"] / 144
        
        circuits_from_velocity = max(1, round(total_mass_flow / (3600 * ref_props["vapor_density_lbm_per_ft3"] * target_velocity * flow_area_ft2)))
        
        # Take the maximum to ensure all constraints are met
        circuits = max(circuits_from_capacity, circuits_from_tubes, circuits_from_velocity)
        
        # Ensure circuits don't exceed total tubes
        circuits = min(circuits, geometry["total_tubes"])
        
        return circuits
        
    except Exception as e:
        logger.error(f"Error in circuit calculation: {e}")
        return max(1, round(tr_design / 2))  # Fallback

def calculate_refrigerant_performance(tr_design, circuits, tube_dia, refrigerant):
    """Calculate refrigerant-side performance with improved accuracy"""
    try:
        ref_props = REFRIGERANT_PROPERTIES[refrigerant]
        tube_props = TUBE_PROPERTIES[tube_dia]
        
        # Mass flow calculations
        capacity_btu_hr = tr_design * BTU_PER_TR
        total_mass_flow_lbm_hr = capacity_btu_hr / ref_props["refrigerating_effect_btu_per_lbm"]
        mass_flow_per_circuit_lbm_hr = total_mass_flow_lbm_hr / circuits
        mass_flow_per_circuit_lbm_s = mass_flow_per_circuit_lbm_hr / 3600
        
        # Velocity calculations
        flow_area_ft2 = tube_props["flow_area_in2"] / 144
        volumetric_flow_ft3_s = mass_flow_per_circuit_lbm_s / ref_props["vapor_density_lbm_per_ft3"]
        velocity_ft_s = volumetric_flow_ft3_s / flow_area_ft2
        
        # Mass velocity (G) for heat transfer and pressure drop
        mass_velocity_lbm_hr_ft2 = mass_flow_per_circuit_lbm_hr / flow_area_ft2
        
        return {
            "total_mass_flow_lbm_hr": total_mass_flow_lbm_hr,
            "mass_flow_per_circuit_lbm_hr": mass_flow_per_circuit_lbm_hr,
            "velocity_ft_s": velocity_ft_s,
            "mass_velocity_lbm_hr_ft2": mass_velocity_lbm_hr_ft2,
            "volumetric_flow_ft3_s": volumetric_flow_ft3_s
        }
        
    except Exception as e:
        logger.error(f"Error in refrigerant performance calculation: {e}")
        raise

def calculate_heat_transfer_coefficient(ref_performance, tube_dia, refrigerant):
    """Calculate heat transfer coefficient with proper correlations"""
    try:
        ref_props = REFRIGERANT_PROPERTIES[refrigerant]
        tube_props = TUBE_PROPERTIES[tube_dia]
        
        # Tube geometry
        inner_dia_ft = tube_props["inner_dia_in"] / 12
        
        # Reynolds number calculation
        G = ref_performance["mass_velocity_lbm_hr_ft2"]
        mu = ref_props["dynamic_viscosity_lbm_per_ft_hr"]
        reynolds = G * inner_dia_ft / mu
        
        # Prandtl number
        cp = ref_props["specific_heat_btu_per_lbm_f"]
        k = ref_props["thermal_conductivity_btu_per_hr_ft_f"]
        prandtl = cp * mu / k
        
        # Nusselt number - Enhanced correlations
        if reynolds > 10000:
            # Gnielinski correlation for turbulent flow (more accurate)
            f = (0.790 * math.log(reynolds) - 1.64) ** (-2)
            numerator = (f/8) * (reynolds - 1000) * prandtl
            denominator = 1 + 12.7 * (f/8)**0.5 * (prandtl**(2/3) - 1)
            nusselt = numerator / denominator
        elif reynolds > 2300:
            # Dittus-Boelter for transition/turbulent
            nusselt = 0.023 * (reynolds ** 0.8) * (prandtl ** 0.4)
        else:
            # Laminar flow
            nusselt = 3.66
        
        # Heat transfer coefficient (Btu/hr-ft²-°F)
        h_coeff = nusselt * k / inner_dia_ft
        
        return {
            "h_coeff": h_coeff,
            "reynolds": reynolds,
            "prandtl": prandtl,
            "nusselt": nusselt,
            "flow_regime": "Turbulent" if reynolds > 4000 else "Transition" if reynolds > 2300 else "Laminar"
        }
        
    except Exception as e:
        logger.error(f"Error in heat transfer calculation: {e}")
        return {"h_coeff": 100, "reynolds": 5000, "prandtl": 1, "nusselt": 20, "flow_regime": "Estimated"}

def calculate_pressure_drops(ref_performance, geometry, tube_dia, refrigerant, fin_spacing_fpi):
    """Calculate both air-side and refrigerant-side pressure drops"""
    try:
        ref_props = REFRIGERANT_PROPERTIES[refrigerant]
        tube_props = TUBE_PROPERTIES[tube_dia]
        
        # === AIR-SIDE PRESSURE DROP ===
        face_velocity_fpm = geometry["actual_face_velocity_fpm"]
        rows = geometry["rows"]
        
        # Enhanced air-side correlation
        velocity_ft_s = face_velocity_fpm / 60
        
        # Base pressure drop per row (empirical correlation for finned tubes)
        # Based on ASHRAE correlations
        dp_per_row_inwg = 0.0015 * (velocity_ft_s ** 1.8)
        
        # Corrections
        fin_density_factor = (fin_spacing_fpi / 12) ** 0.3
        row_interference_factor = rows ** 1.1  # Non-linear due to wake effects
        
        air_dp_inwg = dp_per_row_inwg * fin_density_factor * row_interference_factor
        
        # === REFRIGERANT-SIDE PRESSURE DROP ===
        inner_dia_ft = tube_props["inner_dia_in"] / 12
        velocity_ft_s = ref_performance["velocity_ft_s"]
        
        # Reynolds number
        G = ref_performance["mass_velocity_lbm_hr_ft2"]
        mu = ref_props["dynamic_viscosity_lbm_per_ft_hr"]
        reynolds = G * inner_dia_ft / mu
        
        # Friction factor
        if reynolds > 2300:
            # Blasius correlation for smooth tubes
            friction_factor = 0.316 / (reynolds ** 0.25)
        else:
            friction_factor = 64 / reynolds
        
        # Pressure drop (psi) - Darcy-Weisbach equation
        rho = ref_props["vapor_density_lbm_per_ft3"]
        L_over_D = TUBE_LENGTH_FT / inner_dia_ft
        
        ref_dp_psi = friction_factor * L_over_D * (rho * velocity_ft_s**2) / (2 * 32.174 * 144)
        
        return {
            "air_dp_inwg": air_dp_inwg,
            "ref_dp_psi": ref_dp_psi,
            "reynolds_ref": reynolds,
            "friction_factor": friction_factor
        }
        
    except Exception as e:
        logger.error(f"Error in pressure drop calculation: {e}")
        return {"air_dp_inwg": 0.1, "ref_dp_psi": 1.0, "reynolds_ref": 5000, "friction_factor": 0.02}

def calculate_fin_efficiency(tube_dia, fin_spacing_fpi, fin_thickness_in, face_velocity_fpm):
    """Calculate fin efficiency with enhanced correlation"""
    try:
        tube_props = TUBE_PROPERTIES[tube_dia]
        
        # Geometry calculations
        tube_pitch_in = TUBE_PITCH_MM / 25.4
        tube_outer_dia_in = tube_props["outer_dia_in"]
        fin_height_in = (tube_pitch_in - tube_outer_dia_in) / 2
        
        # Heat transfer coefficients
        k_fin = 120  # Aluminum thermal conductivity (Btu/hr-ft-°F)
        
        # Air-side heat transfer coefficient (enhanced correlation)
        h_air = 8 + 0.025 * face_velocity_fpm  # Improved correlation
        
        # Fin parameter
        m = math.sqrt(2 * h_air / (k_fin * fin_thickness_in))
        m_L = m * fin_height_in
        
        # Fin efficiency
        if m_L > 0.01:  # Avoid division by zero
            fin_eff = math.tanh(m_L) / m_L
        else:
            fin_eff = 1.0
        
        # Surface effectiveness
        fin_spacing_in = 1 / fin_spacing_fpi
        fin_area_per_tube = 2 * fin_height_in * fin_spacing_in  # Both sides
        bare_tube_area_per_tube = math.pi * tube_outer_dia_in * fin_spacing_in
        
        total_surface_area = fin_area_per_tube + bare_tube_area_per_tube
        effective_surface_area = fin_eff * fin_area_per_tube + bare_tube_area_per_tube
        
        surface_effectiveness = effective_surface_area / total_surface_area if total_surface_area > 0 else 1.0
        
        return {
            "fin_efficiency": fin_eff,
            "surface_effectiveness": surface_effectiveness,
            "fin_height_in": fin_height_in,
            "h_air": h_air
        }
        
    except Exception as e:
        logger.error(f"Error in fin efficiency calculation: {e}")
        return {"fin_efficiency": 0.85, "surface_effectiveness": 0.90, "fin_height_in": 0.5, "h_air": 15}

def validate_design(ref_performance, pressure_drops, geometry, refrigerant):
    """Validate design parameters and provide recommendations"""
    warnings = []
    errors = []
    
    ref_props = REFRIGERANT_PROPERTIES[refrigerant]
    velocity = ref_performance["velocity_ft_s"]
    air_dp = pressure_drops["air_dp_inwg"]
    face_velocity = geometry["actual_face_velocity_fpm"]
    
    # Refrigerant velocity checks
    if velocity < ref_props["min_velocity_fps"]:
        warnings.append(f"Low refrigerant velocity ({velocity:.1f} ft/s) - oil return concerns")
    elif velocity > ref_props["max_velocity_fps"]:
        errors.append(f"Excessive refrigerant velocity ({velocity:.1f} ft/s) - high pressure drop")
    
    # Air pressure drop checks
    if air_dp > MAX_AIR_PRESSURE_DROP:
        warnings.append(f"High air pressure drop ({air_dp:.3f} in WG) - check fan capacity")
    
    # Face velocity checks
    if face_velocity < 300:
        warnings.append(f"Low face velocity ({face_velocity:.0f} FPM) may reduce heat transfer")
    elif face_velocity > 600:
        warnings.append(f"High face velocity ({face_velocity:.0f} FPM) increases pressure drop")
    
    # Reynolds number check
    reynolds = pressure_drops.get("reynolds_ref", 0)
    if reynolds < 2000:
        warnings.append("Laminar flow conditions - consider increasing velocity")
    
    return warnings, errors

# === ENHANCED PDF GENERATOR ===
def generate_enhanced_pdf(data, warnings, errors):
    """Generate comprehensive PDF report"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Enhanced DX Coil Selection Report", ln=1, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}", ln=1, align="C")
        pdf.ln(5)
        
        # Design Parameters
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Design Parameters", ln=1)
        pdf.set_font("Arial", "", 10)
        
        for key, value in data.items():
            if isinstance(value, (int, float)):
                if isinstance(value, float):
                    pdf.cell(0, 6, f"{key}: {value:.3f}", ln=1)
                else:
                    pdf.cell(0, 6, f"{key}: {value}", ln=1)
            else:
                pdf.cell(0, 6, f"{key}: {value}", ln=1)
        
        # Warnings and Errors
        if warnings or errors:
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "Design Review", ln=1)
            pdf.set_font("Arial", "", 10)
            
            for warning in warnings:
                pdf.cell(0, 6, f"WARNING: {warning}", ln=1)
            
            for error in errors:
                pdf.cell(0, 6, f"ERROR: {error}", ln=1)
        
        # Save to buffer
        buffer = io.BytesIO()
        pdf_string = pdf.output(dest='S').encode('latin-1')
        buffer.write(pdf_string)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return None

# === ENHANCED VISUALIZATION ===
def create_enhanced_visualizations(geometry, ref_performance, pressure_drops, circuits):
    """Create comprehensive visualization plots"""
    try:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. Coil Layout
        ax1.set_aspect('equal')
        rows = geometry["rows"]
        tubes_per_row = geometry["tubes_per_row"]
        
        # Color mapping for circuits
        colors = plt.cm.Set3(np.linspace(0, 1, circuits))
        
        for i in range(rows):
            for j in range(tubes_per_row):
                x = j * TUBE_PITCH_MM
                y = i * TUBE_PITCH_MM
                
                circuit_id = j % circuits
                circle = plt.Circle((x, y), TUBE_PITCH_MM/4, 
                                  fill=True, color=colors[circuit_id], 
                                  alpha=0.7, edgecolor='black', linewidth=1)
                ax1.add_patch(circle)
                ax1.text(x, y, str(circuit_id + 1), ha='center', va='center', 
                        fontsize=8, fontweight='bold')
        
        margin = TUBE_PITCH_MM
        ax1.set_xlim(-margin, (tubes_per_row - 1) * TUBE_PITCH_MM + margin)
        ax1.set_ylim(-margin, (rows - 1) * TUBE_PITCH_MM + margin)
        ax1.set_xlabel('Width (mm)')
        ax1.set_ylabel('Depth (mm)')
        ax1.grid(True, alpha=0.3)
        ax1.set_title(f"Coil Layout\n{rows} rows × {tubes_per_row} tubes, {circuits} circuits")
        
        # 2. Velocity vs Pressure Drop
        velocities = np.linspace(5, 70, 100)
        pressure_drops_curve = 0.001 * (velocities ** 1.8)
        
        ax2.plot(velocities, pressure_drops_curve, 'b-', linewidth=2, label='Pressure Drop Curve')
        ax2.axvline(x=ref_performance["velocity_ft_s"], color='r', linestyle='--', 
                   label=f'Design Point ({ref_performance["velocity_ft_s"]:.1f} ft/s)')
        ax2.axvline(x=10, color='g', linestyle=':', alpha=0.7, label='Min Velocity')
        ax2.axvline(x=50, color='orange', linestyle=':', alpha=0.7, label='Max Velocity')
        ax2.set_xlabel('Refrigerant Velocity (ft/s)')
        ax2.set_ylabel('Relative Pressure Drop')
        ax2.set_title('Velocity vs Pressure Drop')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # 3. Performance Summary Bar Chart
        performance_metrics = [
            'Face Velocity\n(FPM/100)',
            'Ref Velocity\n(ft/s)',
            'Air ΔP\n(in WG×10)',
            'Ref ΔP\n(psi)',
            'Circuits'
        ]
        
        performance_values = [
            geometry["actual_face_velocity_fpm"] / 100,
            ref_performance["velocity_ft_s"],
            pressure_drops["air_dp_inwg"] * 10,
            pressure_drops["ref_dp_psi"],
            circuits
        ]
        
        bars = ax3.bar(performance_metrics, performance_values, color=['skyblue', 'lightgreen', 'orange', 'lightcoral', 'gold'])
        ax3.set_title('Performance Summary')
        ax3.set_ylabel('Scaled Values')
        ax3.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for bar, value in zip(bars, performance_values):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{value:.2f}', ha='center', va='bottom', fontsize=9)
        
        # 4. Capacity Distribution
        total_capacity = geometry["total_tubes"] * TR_PER_ROW_EST / geometry["rows"]
        capacity_per_circuit = total_capacity / circuits
        
        circuit_labels = [f'Circuit {i+1}' for i in range(circuits)]
        circuit_capacities = [capacity_per_circuit] * circuits
        
        wedges, texts, autotexts = ax4.pie(circuit_capacities, labels=circuit_labels, autopct='%1.1f%%',
                                          colors=colors[:circuits])
        ax4.set_title(f'Capacity Distribution\nTotal: {total_capacity:.2f} TR')
        
        plt.tight_layout()
        return fig
        
    except Exception as e:
        logger.error(f"Error creating visualizations: {e}")
        return None

# === MAIN STREAMLIT APPLICATION ===
def main():
    st.set_page_config(page_title="Enhanced DX Coil Selector", layout="wide", 
                       page_icon="❄️", initial_sidebar_state="expanded")
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stAlert > div {
        padding: 0.5rem 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">❄️ Enhanced DX Coil Selector</h1>', unsafe_allow_html=True)
    st.markdown("**Professional HVAC coil sizing with advanced heat transfer calculations**")
    
    # === SIDEBAR FOR ADVANCED OPTIONS ===
    with st.sidebar:
        st.header("🔧 Advanced Configuration")
        
        st.subheader("Fin Parameters")
        fin_spacing = st.selectbox("Fin Spacing (FPI)", [8, 10, 12, 14, 16], index=2)
        fin_thickness = st.number_input("Fin Thickness (inches)", 
                                       min_value=0.004, max_value=0.015, 
                                       value=0.006, step=0.001, format="%.3f")
        
        st.subheader("Operating Conditions")
        evap_temp = st.number_evap_temp = st.number_input("Evaporating Temperature (°F)", 
                                   min_value=20, max_value=60, 
                                   value=40, step=1)
        
        cond_temp = st.number_input("Condensing Temperature (°F)", 
                                   min_value=80, max_value=130, 
                                   value=105, step=1)
        
        st.subheader("Design Constraints")
        max_air_dp = st.number_input("Max Air Pressure Drop (in WG)", 
                                    min_value=0.1, max_value=1.0, 
                                    value=0.6, step=0.1, format="%.1f")
        
        min_ref_vel = st.number_input("Min Refrigerant Velocity (ft/s)", 
                                     min_value=5, max_value=15, 
                                     value=8, step=1)
        
        show_advanced = st.checkbox("Show Advanced Results", value=False)
    
    # === MAIN INPUT SECTION ===
    st.header("📋 Design Requirements")
    
    col1, col2 = st.columns(2)
    
    with col1:
        tr_design = st.number_input("Cooling Capacity (Tons of Refrigeration)", 
                                   min_value=0.5, max_value=100.0, 
                                   value=10.0, step=0.5, format="%.1f")
        
        cfm = st.number_input("Airflow Rate (CFM)", 
                             min_value=100, max_value=50000, 
                             value=int(tr_design * 400), step=100)
    
    with col2:
        tube_diameter = st.selectbox("Tube Diameter", 
                                    list(TUBE_PROPERTIES.keys()), 
                                    index=1)
        
        refrigerant = st.selectbox("Refrigerant Type", 
                                  list(REFRIGERANT_PROPERTIES.keys()), 
                                  index=0)
    
    # === CALCULATION TRIGGER ===
    if st.button("🔍 Analyze Coil Design", type="primary"):
        with st.spinner("Performing enhanced calculations..."):
            try:
                # Input validation
                errors, warnings = validate_inputs(tr_design, cfm, tube_diameter, refrigerant)
                
                if errors:
                    for error in errors:
                        st.error(f"❌ {error}")
                    return
                
                if warnings:
                    for warning in warnings:
                        st.warning(f"⚠️ {warning}")
                
                # Core calculations
                geometry = calculate_coil_geometry(tr_design, cfm, tube_diameter)
                circuits = calculate_enhanced_circuits(tr_design, geometry, refrigerant)
                ref_performance = calculate_refrigerant_performance(tr_design, circuits, tube_diameter, refrigerant)
                heat_transfer = calculate_heat_transfer_coefficient(ref_performance, tube_diameter, refrigerant)
                pressure_drops = calculate_pressure_drops(ref_performance, geometry, tube_diameter, refrigerant, fin_spacing)
                fin_efficiency = calculate_fin_efficiency(tube_diameter, fin_spacing, fin_thickness, geometry["actual_face_velocity_fpm"])
                
                # Design validation
                design_warnings, design_errors = validate_design(ref_performance, pressure_drops, geometry, refrigerant)
                
                # === RESULTS DISPLAY ===
                st.success("✅ Calculations completed successfully!")
                
                # Main Results
                st.header("📊 Design Results")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Tubes", geometry["total_tubes"])
                    st.metric("Rows", geometry["rows"])
                
                with col2:
                    st.metric("Tubes per Row", geometry["tubes_per_row"])
                    st.metric("Circuits", circuits)
                
                with col3:
                    st.metric("Face Velocity", f"{geometry['actual_face_velocity_fpm']:.0f} FPM")
                    st.metric("Ref Velocity", f"{ref_performance['velocity_ft_s']:.1f} ft/s")
                
                with col4:
                    st.metric("Air ΔP", f"{pressure_drops['air_dp_inwg']:.3f} in WG")
                    st.metric("Ref ΔP", f"{pressure_drops['ref_dp_psi']:.2f} psi")
                
                # Coil Dimensions
                st.subheader("📐 Coil Dimensions")
                dim_col1, dim_col2, dim_col3 = st.columns(3)
                
                with dim_col1:
                    st.metric("Coil Width", f"{geometry['coil_width_ft']:.2f} ft")
                
                with dim_col2:
                    st.metric("Coil Depth", f"{geometry['coil_depth_ft']:.2f} ft")
                
                with dim_col3:
                    st.metric("Face Area", f"{geometry['actual_face_area_ft2']:.1f} ft²")
                
                # Performance Indicators
                st.subheader("⚡ Performance Indicators")
                
                perf_col1, perf_col2, perf_col3 = st.columns(3)
                
                with perf_col1:
                    cfm_per_tr = cfm / tr_design
                    if 350 <= cfm_per_tr <= 450:
                        st.success(f"CFM/TR Ratio: {cfm_per_tr:.0f} ✅")
                    else:
                        st.warning(f"CFM/TR Ratio: {cfm_per_tr:.0f} ⚠️")
                
                with perf_col2:
                    if heat_transfer["flow_regime"] == "Turbulent":
                        st.success(f"Flow: {heat_transfer['flow_regime']} ✅")
                    else:
                        st.warning(f"Flow: {heat_transfer['flow_regime']} ⚠️")
                
                with perf_col3:
                    if fin_efficiency["fin_efficiency"] > 0.8:
                        st.success(f"Fin Efficiency: {fin_efficiency['fin_efficiency']:.1%} ✅")
                    else:
                        st.warning(f"Fin Efficiency: {fin_efficiency['fin_efficiency']:.1%} ⚠️")
                
                # Design Validation Messages
                if design_warnings or design_errors:
                    st.subheader("🔍 Design Review")
                    
                    for warning in design_warnings:
                        st.warning(f"⚠️ {warning}")
                    
                    for error in design_errors:
                        st.error(f"❌ {error}")
                
                # Advanced Results (if enabled)
                if show_advanced:
                    st.header("🔬 Advanced Analysis")
                    
                    with st.expander("Heat Transfer Analysis", expanded=True):
                        ht_col1, ht_col2 = st.columns(2)
                        
                        with ht_col1:
                            st.metric("Reynolds Number", f"{heat_transfer['reynolds']:.0f}")
                            st.metric("Prandtl Number", f"{heat_transfer['prandtl']:.3f}")
                        
                        with ht_col2:
                            st.metric("Nusselt Number", f"{heat_transfer['nusselt']:.1f}")
                            st.metric("Heat Transfer Coeff", f"{heat_transfer['h_coeff']:.1f} Btu/hr-ft²-°F")
                    
                    with st.expander("Mass Flow Analysis", expanded=True):
                        mf_col1, mf_col2 = st.columns(2)
                        
                        with mf_col1:
                            st.metric("Total Mass Flow", f"{ref_performance['total_mass_flow_lbm_hr']:.1f} lbm/hr")
                            st.metric("Mass Flow per Circuit", f"{ref_performance['mass_flow_per_circuit_lbm_hr']:.1f} lbm/hr")
                        
                        with mf_col2:
                            st.metric("Mass Velocity", f"{ref_performance['mass_velocity_lbm_hr_ft2']:.0f} lbm/hr-ft²")
                            st.metric("Volumetric Flow", f"{ref_performance['volumetric_flow_ft3_s']:.3f} ft³/s")
                    
                    with st.expander("Surface Analysis", expanded=True):
                        surf_col1, surf_col2 = st.columns(2)
                        
                        with surf_col1:
                            st.metric("Surface Area", f"{geometry['surface_area_ft2']:.1f} ft²")
                            st.metric("Fin Height", f"{fin_efficiency['fin_height_in']:.3f} inches")
                        
                        with surf_col2:
                            st.metric("Air-side h", f"{fin_efficiency['h_air']:.1f} Btu/hr-ft²-°F")
                            st.metric("Surface Effectiveness", f"{fin_efficiency['surface_effectiveness']:.1%}")
                
                # === VISUALIZATION ===
                st.header("📈 Visual Analysis")
                
                try:
                    fig = create_enhanced_visualizations(geometry, ref_performance, pressure_drops, circuits)
                    if fig:
                        st.pyplot(fig)
                    else:
                        st.error("Unable to generate visualizations")
                except Exception as e:
                    st.error(f"Visualization error: {str(e)}")
                
                # === DATA EXPORT ===
                st.header("📄 Export Results")
                
                # Prepare data for export
                export_data = {
                    "Design_Capacity_TR": tr_design,
                    "Airflow_CFM": cfm,
                    "Tube_Diameter": tube_diameter,
                    "Refrigerant": refrigerant,
                    "Total_Tubes": geometry["total_tubes"],
                    "Rows": geometry["rows"],
                    "Tubes_per_Row": geometry["tubes_per_row"],
                    "Circuits": circuits,
                    "Coil_Width_ft": geometry["coil_width_ft"],
                    "Coil_Depth_ft": geometry["coil_depth_ft"],
                    "Face_Area_ft2": geometry["actual_face_area_ft2"],
                    "Face_Velocity_FPM": geometry["actual_face_velocity_fpm"],
                    "Surface_Area_ft2": geometry["surface_area_ft2"],
                    "Refrigerant_Velocity_ft_s": ref_performance["velocity_ft_s"],
                    "Mass_Flow_Total_lbm_hr": ref_performance["total_mass_flow_lbm_hr"],
                    "Air_Pressure_Drop_inWG": pressure_drops["air_dp_inwg"],
                    "Ref_Pressure_Drop_psi": pressure_drops["ref_dp_psi"],
                    "Reynolds_Number": heat_transfer["reynolds"],
                    "Heat_Transfer_Coeff": heat_transfer["h_coeff"],
                    "Fin_Efficiency": fin_efficiency["fin_efficiency"],
                    "Flow_Regime": heat_transfer["flow_regime"],
                    "CFM_per_TR": cfm / tr_design
                }
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV Export
                    df = pd.DataFrame([export_data])
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📊 Download CSV Report",
                        data=csv,
                        file_name=f"dx_coil_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    # PDF Export
                    try:
                        pdf_buffer = generate_enhanced_pdf(export_data, design_warnings, design_errors)
                        if pdf_buffer:
                            st.download_button(
                                label="📄 Download PDF Report",
                                data=pdf_buffer.getvalue(),
                                file_name=f"dx_coil_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                mime="application/pdf"
                            )
                        else:
                            st.error("PDF generation failed")
                    except Exception as e:
                        st.error(f"PDF export error: {str(e)}")
                
                # === SUMMARY TABLE ===
                st.header("📋 Design Summary")
                
                summary_data = {
                    "Parameter": [
                        "Cooling Capacity", "Airflow Rate", "Coil Configuration", 
                        "Face Velocity", "Refrigerant Velocity", "Air Pressure Drop",
                        "Total Surface Area", "Fin Efficiency", "Flow Regime"
                    ],
                    "Value": [
                        f"{tr_design} TR",
                        f"{cfm:,} CFM",
                        f"{geometry['rows']} rows × {geometry['tubes_per_row']} tubes ({circuits} circuits)",
                        f"{geometry['actual_face_velocity_fpm']:.0f} FPM",
                        f"{ref_performance['velocity_ft_s']:.1f} ft/s",
                        f"{pressure_drops['air_dp_inwg']:.3f} in WG",
                        f"{geometry['surface_area_ft2']:.1f} ft²",
                        f"{fin_efficiency['fin_efficiency']:.1%}",
                        heat_transfer['flow_regime']
                    ],
                    "Status": [
                        "✅", "✅", "✅",
                        "✅" if 300 <= geometry['actual_face_velocity_fpm'] <= 600 else "⚠️",
                        "✅" if min_ref_vel <= ref_performance['velocity_ft_s'] <= 50 else "⚠️",
                        "✅" if pressure_drops['air_dp_inwg'] <= max_air_dp else "⚠️",
                        "✅", 
                        "✅" if fin_efficiency['fin_efficiency'] > 0.8 else "⚠️",
                        "✅" if heat_transfer['flow_regime'] == "Turbulent" else "⚠️"
                    ]
                }
                
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"Calculation error: {str(e)}")
                logger.error(f"Main calculation error: {e}")
    
    # === FOOTER ===
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9em;'>
        <p>🔧 Enhanced DX Coil Selector v2.0 | Professional HVAC Design Tool</p>
        <p>⚠️ For design verification only. Consult manufacturer specifications for final selection.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
