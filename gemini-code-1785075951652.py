"""
================================================================================
Enterprise Industrial Bakery Execution System (MES, OEE, SPC & Mass Balance)
Author: Principal Industrial Systems Architect
Version: 4.0 - Dynamic Interactive SPC & Full Bilingual Enterprise Edition
================================================================================
"""

import io
import math
from dataclasses import dataclass
from typing import Dict, Tuple, List, Any
import numpy as np
import pandas as pd
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ==============================================================================
# 1. PAGE CONFIGURATION & ENTERPRISE CSS
# ==============================================================================
st.set_page_config(
    page_title="Croissant Industrial MES & SPC Suite",
    page_icon="🥐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Enterprise UI
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .metric-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #1f77b4;
        margin-bottom: 10px;
    }
    .stMetric label { font-weight: 600 !important; color: #2c3e50 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        background-color: #ffffff;
        border-radius: 6px;
        padding-x: 12px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. BILINGUAL HELPER & MASTER DATABASE
# ==============================================================================
# Initialize Language in Session State
if "lang" not in st.session_state:
    st.session_state["lang"] = "العربية"

is_ar = (st.session_state["lang"] == "العربية")

def tr(ar_str: str, en_str: str) -> str:
    """Helper function for instant language switching"""
    return ar_str if is_ar else en_str

BASE_BATCH_KG: float = 200.0
MARGARINE_RATIO: float = 0.10
TRAYS_PER_TROLLEY: int = 19

PRODUCTS_DB: Dict[str, Dict[str, Any]] = {
    "Marolla 5 EGP": {
        "dough_wt": 30.0, "baked_wt": 25.5, "filling_wt": 5.0, "finish_wt": 30.5,
        "pieces_per_tray": 52, "default_pcs_carton": 48, "price_egp": 5.0,
        "forming_speed": 120, "inj_speed": 120, "pack_speed": 140
    },
    "Marolla 5 EGP (CaCao / St+Ca)": {
        "dough_wt": 30.0, "baked_wt": 25.5, "filling_wt": 5.0, "finish_wt": 30.5,
        "pieces_per_tray": 52, "default_pcs_carton": 48, "price_egp": 5.0,
        "forming_speed": 120, "inj_speed": 120, "pack_speed": 140
    },
    "Marolla 10 EGP": {
        "dough_wt": 50.0, "baked_wt": 42.0, "filling_wt": 17.0, "finish_wt": 56.0,
        "pieces_per_tray": 30, "default_pcs_carton": 36, "price_egp": 10.0,
        "forming_speed": 90, "inj_speed": 90, "pack_speed": 100
    },
    "Marolla 2 EGP": {
        "dough_wt": 14.0, "baked_wt": 12.0, "filling_wt": 2.0, "finish_wt": 14.0,
        "pieces_per_tray": 72, "default_pcs_carton": 72, "price_egp": 2.0,
        "forming_speed": 150, "inj_speed": 150, "pack_speed": 180
    },
    "Pie 10 EGP": {
        "dough_wt": 50.0, "baked_wt": 42.0, "filling_wt": 16.0, "finish_wt": 58.0,
        "pieces_per_tray": 30, "default_pcs_carton": 36, "price_egp": 10.0,
        "forming_speed": 85, "inj_speed": 85, "pack_speed": 100
    },
    "Pie 5 EGP": {
        "dough_wt": 26.0, "baked_wt": 22.0, "filling_wt": 9.0, "finish_wt": 30.0,
        "pieces_per_tray": 48, "default_pcs_carton": 48, "price_egp": 5.0,
        "forming_speed": 110, "inj_speed": 110, "pack_speed": 130
    },
    "Mini (5, 10 EGP)": {
        "dough_wt": 9.0, "baked_wt": 7.0, "filling_wt": 2.5, "finish_wt": 9.5,
        "pieces_per_tray": 120, "default_pcs_carton": 100, "price_egp": 5.0,
        "forming_speed": 180, "inj_speed": 180, "pack_speed": 200
    },
    "Brioche": {
        "dough_wt": 55.0, "baked_wt": 46.0, "filling_wt": 17.0, "finish_wt": 72.0,
        "pieces_per_tray": 30, "default_pcs_carton": 24, "price_egp": 12.0,
        "forming_speed": 80, "inj_speed": 80, "pack_speed": 90
    },
    "Mini DiP": {
        "dough_wt": 9.0, "baked_wt": 7.0, "filling_wt": 0.0, "finish_wt": 7.0,
        "pieces_per_tray": 120, "default_pcs_carton": 100, "price_egp": 4.0,
        "forming_speed": 180, "inj_speed": 999, "pack_speed": 200
    }
}

CHANGEOVER_MATRIX: Dict[str, Dict[str, int]] = {
    p1: {p2: (0 if p1 == p2 else 30) for p2 in PRODUCTS_DB.keys()}
    for p1 in PRODUCTS_DB.keys()
}
CHANGEOVER_MATRIX["Marolla 5 EGP"]["Marolla 5 EGP (CaCao / St+Ca)"] = 20
CHANGEOVER_MATRIX["Marolla 5 EGP"]["Brioche"] = 45

# ==============================================================================
# 3. CORE LOGIC ENGINES (VECTORIZED & DYNAMIC)
# ==============================================================================
class MassBalanceEngine:
    @staticmethod
    def calculate(target_units: int, dough_wt: float, baked_wt: float, filling_wt: float) -> Dict[str, float]:
        lam_dough_pc_g = dough_wt * (1.0 + MARGARINE_RATIO)
        total_base_dough_kg = (target_units * dough_wt) / 1000.0
        total_margarine_kg = total_base_dough_kg * MARGARINE_RATIO
        total_lam_dough_kg = total_base_dough_kg + total_margarine_kg
        
        batch_size_kg = BASE_BATCH_KG * (1.0 + MARGARINE_RATIO)
        batches_req = total_lam_dough_kg / batch_size_kg if batch_size_kg > 0 else 0.0
        
        evap_loss_pc_g = lam_dough_pc_g - baked_wt
        total_evap_loss_kg = (target_units * evap_loss_pc_g) / 1000.0
        total_baked_pastry_kg = (target_units * baked_wt) / 1000.0
        total_filling_kg = (target_units * filling_wt) / 1000.0
        total_finished_goods_kg = total_baked_pastry_kg + total_filling_kg
        
        return {
            "lam_dough_pc_g": lam_dough_pc_g,
            "total_base_dough_kg": total_base_dough_kg,
            "total_margarine_kg": total_margarine_kg,
            "total_lam_dough_kg": total_lam_dough_kg,
            "batches_req": batches_req,
            "evap_loss_pc_g": evap_loss_pc_g,
            "total_evap_loss_kg": total_evap_loss_kg,
            "total_baked_pastry_kg": total_baked_pastry_kg,
            "total_filling_kg": total_filling_kg,
            "total_finished_goods_kg": total_finished_goods_kg
        }


class VectorizedSPCEngine:
    A2 = 0.577
    D3 = 0.0
    D4 = 2.114
    D2 = 2.326

    @classmethod
    def generate_initial_data(cls, target_wt: float, num_subgroups: int = 20, subgroup_size: int = 5) -> pd.DataFrame:
        subgroup_ids = np.arange(1, num_subgroups + 1)
        drift_vector = np.where(subgroup_ids > 12, 0.03 * (subgroup_ids - 12), 0.0)
        
        np.random.seed(42)
        noise_matrix = np.random.normal(loc=0.0, scale=0.4, size=(num_subgroups, subgroup_size))
        
        # 🔥 Vectorized Broadcasting with np.newaxis
        weights_matrix = target_wt + drift_vector[:, np.newaxis] + noise_matrix
        
        records = []
        for i in range(num_subgroups):
            row_dict = {"Subgroup_ID": i + 1}
            for j in range(subgroup_size):
                row_dict[f"Sample_{j+1}"] = round(float(weights_matrix[i, j]), 2)
            records.append(row_dict)
        return pd.DataFrame(records)

    @classmethod
    def analyze_dataframe(cls, df: pd.DataFrame, target_wt: float, usl: float, lsl: float) -> Tuple[pd.DataFrame, Dict[str, float]]:
        sample_cols = [col for col in df.columns if col.startswith("Sample_")]
        
        df_calc = df.copy()
        df_calc['X_bar'] = df_calc[sample_cols].mean(axis=1)
        df_calc['R'] = df_calc[sample_cols].max(axis=1) - df_calc[sample_cols].min(axis=1)
        
        grand_mean = df_calc['X_bar'].mean() if not df_calc.empty else target_wt
        r_bar = df_calc['R'].mean() if not df_calc.empty else 0.5
        
        df_calc['X_CL'] = grand_mean
        df_calc['X_UCL'] = grand_mean + (cls.A2 * r_bar)
        df_calc['X_LCL'] = grand_mean - (cls.A2 * r_bar)
        df_calc['R_CL'] = r_bar
        df_calc['R_UCL'] = cls.D4 * r_bar
        df_calc['R_LCL'] = cls.D3 * r_bar
        
        sigma_within = r_bar / cls.D2 if cls.D2 > 0 else 1.0
        cp = (usl - lsl) / (6 * sigma_within) if sigma_within > 0 else 0.0
        cpu = (usl - grand_mean) / (3 * sigma_within) if sigma_within > 0 else 0.0
        cpl = (grand_mean - lsl) / (3 * sigma_within) if sigma_within > 0 else 0.0
        cpk = min(cpu, cpl)
        
        cpm_denom = 6 * np.sqrt((sigma_within ** 2) + ((grand_mean - target_wt) ** 2))
        cpm = (usl - lsl) / cpm_denom if cpm_denom > 0 else 0.0
        
        metrics = {
            "mean": round(grand_mean, 2),
            "r_bar": round(r_bar, 2),
            "sigma_within": round(sigma_within, 3),
            "cp": round(cp, 2),
            "cpk": round(cpk, 2),
            "cpm": round(cpm, 2)
        }
        return df_calc, metrics

# ==============================================================================
# 4. SIDEBAR CONTROLS & BILINGUAL TOGGLE
# ==============================================================================
st.sidebar.title("⚙️ " + tr("إعدادات النظام", "System Configuration"))

# Language Selection Switcher
lang_choice = st.sidebar.radio(
    "🌐 " + tr("لغة الواجهة / Language", "Language / اللغة"),
    ["العربية", "English"],
    index=0 if st.session_state["lang"] == "العربية" else 1
)

if lang_choice != st.session_state["lang"]:
    st.session_state["lang"] = lang_choice
    st.rerun()

is_ar = (st.session_state["lang"] == "العربية")

st.sidebar.markdown("---")
st.sidebar.header("🎯 " + tr("إعدادات المنتج والطلب", "Product & Order Setup"))
selected_prod = st.sidebar.selectbox(tr("المنتج الحالي", "Selected Product"), list(PRODUCTS_DB.keys()))
p_defaults = PRODUCTS_DB[selected_prod]

target_cartons = st.sidebar.number_input(tr("عدد الكراتين المطلوبة", "Target Cartons"), min_value=1, value=500, step=10)
pcs_per_carton = st.sidebar.number_input(tr("قطع / كرتونة", "Pcs / Carton"), min_value=1, value=int(p_defaults["default_pcs_carton"]))
total_target_units = int(target_cartons * pcs_per_carton)

# Dynamic Tray Capacity Customization
st.sidebar.markdown("---")
st.sidebar.header("📥 " + tr("تخصيص اللوجستيات والصيجان", "Logistics & Tray Customization"))
custom_pcs_per_tray = st.sidebar.number_input(
    tr("سعة الصاج المخصصة (قطعة/صاج)", "Custom Tray Capacity (pcs/tray)"),
    min_value=1,
    value=int(p_defaults["pieces_per_tray"]),
    help=tr("يمكنك تعديل سعة الصاج هنا وستنعكس تلقائياً على حسابات الصيجان والتروليات", "Modify tray capacity here to dynamically update trolley logistics")
)

st.sidebar.markdown("---")
st.sidebar.header("⚡ " + tr("سرعات خط الإنتاج", "Line Speeds Setup"))
s_form = st.sidebar.number_input(tr("سرعة التشكيل (قطع/د)", "Forming Speed (pcs/min)"), min_value=1, value=int(p_defaults["forming_speed"]))
s_inj = st.sidebar.number_input(tr("سرعة الحقن (قطع/د)", "Injection Speed (pcs/min)"), min_value=1, value=int(p_defaults["inj_speed"])) if p_defaults["filling_wt"] > 0 else 9999
s_pack = st.sidebar.number_input(tr("سرعة التغليف (قطع/د)", "Packaging Speed (pcs/min)"), min_value=1, value=int(p_defaults["pack_speed"]))

bottleneck_speed = min(s_form, s_inj, s_pack)
st.sidebar.warning(f"{tr('سرعة الاختناق الفعالة:', 'Effective Bottleneck Speed:')} **{bottleneck_speed} {tr(' قطعة/دقيقة', ' pcs/min')}**")

# ==============================================================================
# 5. DYNAMIC SESSION STATE FOR SPC
# ==============================================================================
if "spc_data" not in st.session_state or st.session_state.get("spc_product") != selected_prod:
    st.session_state["spc_data"] = VectorizedSPCEngine.generate_initial_data(target_wt=p_defaults["finish_wt"])
    st.session_state["spc_product"] = selected_prod

# ==============================================================================
# 6. MAIN WORKSPACE DASHBOARD
# ==============================================================================
st.title("🥐 " + tr("نظام إدارة إنتاج وجودة الكرواسون المتقدم (MES & SPC)", "Enterprise Croissant MES & Quality Suite"))

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "⚖️ " + tr("ميزان الكتلة", "Mass Balance"),
    "🔀 " + tr("مخطط سريان الكتلة", "Sankey Flow"),
    "📈 " + tr("ضبط الجودة الإحصائي SPC", "Dynamic SPC"),
    "🚨 " + tr("خسائر TPM", "TPM 6 Losses"),
    "⏱️ " + tr("مصفوفة التغيير", "Changeover"),
    "⚡ " + tr("كفاءة الطاقة SEC", "Energy SEC"),
    "📊 " + tr("مؤشر OEE", "OEE Performance"),
    "🚚 " + tr("اللوجستيات والصيجان", "Logistics & Trays"),
    "📄 " + tr("تصدير التقارير", "Excel Export")
])

# ------------------------------------------------------------------------------
# TAB 1: MASS BALANCE
# ------------------------------------------------------------------------------
with tab1:
    st.subheader("📝 " + tr("مواصفات المنتج الحالي التنافسية", "Product Recipe Parameters"))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        dough_wt = st.number_input(tr("وزن العجين الأساسي (جرام)", "Base Dough Wt (g)"), value=float(p_defaults["dough_wt"]), step=0.5)
    with c2:
        baked_wt = st.number_input(tr("الوزن المخبوز (جرام)", "Baked Wt (g)"), value=float(p_defaults["baked_wt"]), step=0.5)
    with c3:
        filling_wt = st.number_input(tr("وزن الحشوة (جرام)", "Filling Wt (g)"), value=float(p_defaults["filling_wt"]), step=0.5)
    with c4:
        finish_wt = st.number_input(tr("الوزن النهائي التام (جرام)", "Finished Product Wt (g)"), value=float(p_defaults["finish_wt"]), step=0.5)

    mb = MassBalanceEngine.calculate(total_target_units, dough_wt, baked_wt, filling_wt)
    
    st.markdown("---")
    st.subheader("📊 " + tr("نتائج ميزان الكتلة المخططة للوردية", "Shift Planned Mass Balance Results"))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(tr("إجمالي القطع المطلوبة", "Total Target Units"), f"{total_target_units:,} pcs")
    m2.metric(tr("عدد العجنات المطلوب (220kg)", "Required Batches (220kg)"), f"{mb['batches_req']:.2f} Batches")
    m3.metric(tr("العجين الأساسي المطلوب", "Total Base Dough"), f"{mb['total_base_dough_kg']:.1f} kg")
    m4.metric(tr("مارجرين التوريق (10%)", "Lamination Margarine"), f"{mb['total_margarine_kg']:.1f} kg")
    
    m5, m6, m7, m8 = st.columns(4)
    m5.metric(tr("إجمالي العجين المورق", "Total Laminated Dough"), f"{mb['total_lam_dough_kg']:.1f} kg")
    m6.metric(tr("فقد البخر بالفرن", "Oven Evaporation Loss"), f"{mb['total_evap_loss_kg']:.1f} kg")
    m7.metric(tr("إجمالي الحشوة المطلوبة", "Total Filling Required"), f"{mb['total_filling_kg']:.1f} kg")
    m8.metric(tr("وزن المنتج النهائي التام", "Total Finished Goods"), f"{mb['total_finished_goods_kg']:.1f} kg")

# ------------------------------------------------------------------------------
# TAB 2: SANKEY FLOW
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("🔀 " + tr("مخطط سريان وتوازن الكتل (Sankey Diagram)", "Sankey Mass Flow Diagram"))
    labels = [
        tr("العجين الأساسي", "Base Dough"),
        tr("مارجرين التوريق", "Margarine (10%)"),
        tr("العجين المورق", "Laminated Dough"),
        tr("فقد البخر بالفرن", "Evaporation Loss"),
        tr("القاعدة المخبوزة", "Baked Base"),
        tr("الحشوة", "Filling"),
        tr("المنتج النهائي التام", "Finished Goods")
    ]
    fig_sankey = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15, thickness=20, line=dict(color="black", width=0.5),
            label=labels,
            color=["#3498db", "#f39c12", "#e67e22", "#e74c3c", "#2ecc71", "#9b59b6", "#27ae60"]
        ),
        link=dict(
            source=[0, 1, 2, 2, 4, 5],
            target=[2, 2, 3, 4, 6, 6],
            value=[mb['total_base_dough_kg'], mb['total_margarine_kg'], mb['total_evap_loss_kg'], 
                   mb['total_baked_pastry_kg'], mb['total_baked_pastry_kg'], mb['total_filling_kg']]
        )
    )])
    fig_sankey.update_layout(title_text=tr("سريان تحول المواد الخام إلى منتجات نهائية (كجم)", "Raw Material Mass Transformation Flow (kg)"), font_size=12, height=450)
    st.plotly_chart(fig_sankey, use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 3: DYNAMIC INTERACTIVE SPC ENGINE
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("📈 " + tr("نظام ضبط الجودة الإحصائي الديناميكي (Dynamic Interactive SPC)", "Dynamic Interactive Statistical Process Control"))
    
    usl = finish_wt + 1.5
    lsl = finish_wt - 1.5
    
    # 📥 Form to Add New Live Sample
    with st.expander("➕ " + tr("إضافة عينة سحبة جديدة للتحليل الفوري", "Add New Subgroup Sample for Real-Time Analysis"), expanded=True):
        st.markdown(tr("أدخل أوزان 5 قطع من السحبة الجديدة ليتم تحديث منحنى SPC ومؤشرات Cpk تلقائياً:", "Enter 5 sample weights from the new subgroup to automatically update SPC charts and Cpk:"))
        
        c_in1, c_in2, c_in3, c_in4, c_in5, c_btn = st.columns([1, 1, 1, 1, 1, 1.2])
        with c_in1:
            w1 = st.number_input(tr("قطعة 1", "Sample 1"), value=float(finish_wt), step=0.1, key="in_w1")
        with c_in2:
            w2 = st.number_input(tr("قطعة 2", "Sample 2"), value=float(finish_wt + 0.1), step=0.1, key="in_w2")
        with c_in3:
            w3 = st.number_input(tr("قطعة 3", "Sample 3"), value=float(finish_wt - 0.2), step=0.1, key="in_w3")
        with c_in4:
            w4 = st.number_input(tr("قطعة 4", "Sample 4"), value=float(finish_wt + 0.3), step=0.1, key="in_w4")
        with c_in5:
            w5 = st.number_input(tr("قطعة 5", "Sample 5"), value=float(finish_wt - 0.1), step=0.1, key="in_w5")
            
        with c_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🚀 " + tr("إضافة للتحليل", "Add Sample"), use_container_width=True):
                new_sub_id = len(st.session_state["spc_data"]) + 1
                new_row = {
                    "Subgroup_ID": new_sub_id,
                    "Sample_1": w1, "Sample_2": w2, "Sample_3": w3, "Sample_4": w4, "Sample_5": w5
                }
                st.session_state["spc_data"] = pd.concat([st.session_state["spc_data"], pd.DataFrame([new_row])], ignore_index=True)
                st.success(f"✅ {tr('تمت إضافة السحبة رقم', 'Added Subgroup #')}{new_sub_id} {tr('بنجاح!', 'successfully!')}")
                st.rerun()

    # Calculate Current SPC
    spc_df_calc, spc_metrics = VectorizedSPCEngine.analyze_dataframe(
        st.session_state["spc_data"], target_wt=finish_wt, usl=usl, lsl=lsl
    )
    
    # Render X-Bar & R Charts
    col_chart1, col_chart2 = st.columns([0.7, 0.3])
    with col_chart1:
        fig_spc = go.Figure()
        fig_spc.add_trace(go.Scatter(x=spc_df_calc["Subgroup_ID"], y=spc_df_calc['X_bar'], mode='lines+markers', name=tr('متوسط السحبة X-bar', 'X-bar Mean'), line=dict(color='#1f77b4', width=2)))
        fig_spc.add_trace(go.Scatter(x=spc_df_calc["Subgroup_ID"], y=spc_df_calc['X_UCL'], mode='lines', name='UCL', line=dict(color='red', dash='dash')))
        fig_spc.add_trace(go.Scatter(x=spc_df_calc["Subgroup_ID"], y=spc_df_calc['X_LCL'], mode='lines', name='LCL', line=dict(color='red', dash='dash')))
        fig_spc.add_hline(y=finish_wt, line_dash="solid", line_color="green", annotation_text=tr("الهدف Target", "Target"))
        fig_spc.add_hline(y=usl, line_dash="dot", line_color="purple", annotation_text="USL")
        fig_spc.add_hline(y=lsl, line_dash="dot", line_color="purple", annotation_text="LSL")
        
        fig_spc.update_layout(
            title=f"{tr('مخطط التحكم في أوزان المنتج (X-Bar Chart) | عدد السحبات:', 'Weight Control Chart (X-Bar Chart) | Total Subgroups:')} {len(spc_df_calc)}",
            xaxis_title=tr("رقم السحبة (Subgroup ID)", "Subgroup ID"),
            yaxis_title=tr("الوزن (جرام)", "Weight (g)"),
            height=400, template="plotly_white"
        )
        st.plotly_chart(fig_spc, use_container_width=True)
        
    with col_chart2:
        st.markdown(f"#### 📊 {tr('مؤشرات مقدرة العملية', 'Process Capability Results')}")
        st.metric(tr("متوسط الوزن الفعلي", "Actual Mean Weight"), f"{spc_metrics['mean']} g")
        st.metric(tr("مؤشر Cpk الفعلي", "Actual Cpk Index"), f"{spc_metrics['cpk']}", delta=tr("مقبول" if spc_metrics['cpk'] >= 1.33 else "تحذير - غير متمركز", "Capable" if spc_metrics['cpk'] >= 1.33 else "Warning"))
        st.metric(tr("مؤشر تاغوتشي Cpm", "Taguchi Cpm Index"), f"{spc_metrics['cpm']}")
        st.metric(tr("الانحراف المعياري Sigma", "Process Sigma"), f"±{spc_metrics['sigma_within']} g")

    # Raw Data Table with Reset Button
    col_tb1, col_tb2 = st.columns([0.8, 0.2])
    with col_tb1:
        st.markdown(f"##### 📋 {tr('سجل قراءات العينات الإحصائية الحالية', 'Current Subgroup Sample Readings Log')}")
    with col_tb2:
        if st.button("🔄 " + tr("إعادة ضبط البيانات", "Reset Data"), use_container_width=True):
            st.session_state["spc_data"] = VectorizedSPCEngine.generate_initial_data(target_wt=finish_wt)
            st.rerun()
            
    st.dataframe(st.session_state["spc_data"].style.highlight_max(axis=1, color="#ffcdd2"), use_container_width=True, height=220)

# ------------------------------------------------------------------------------
# TAB 4: TPM SIX BIG LOSSES
# ------------------------------------------------------------------------------
with tab4:
    st.subheader("🚨 " + tr("تحليل الخسائر الست الكبرى (TPM Six Big Losses)", "TPM 6 Big Losses Analysis"))
    
    t1, t2 = st.columns(2)
    with t1:
        loss_breakdown = st.number_input(tr("أعطال الماكينات الميكانيكية (دقيقة)", "Equipment Breakdown (mins)"), value=25, step=5)
        loss_setup = st.number_input(tr("وقت الإعداد والتغيير (دقيقة)", "Setup & Adjustment (mins)"), value=30, step=5)
        loss_minor = st.number_input(tr("التوقفات اللحظية الصغيرة (دقيقة)", "Minor Stoppages (mins)"), value=10, step=1)
    with t2:
        loss_speed = st.number_input(tr("خسائر بطء السرعة الإسمية (دقيقة)", "Reduced Speed Losses (mins)"), value=15, step=5)
        loss_defects = st.number_input(tr("عجائن ومنتجات معيبة (قطع)", "Process Quality Defects (pcs)"), value=120, step=10)
        loss_startup = st.number_input(tr("هالك بداية التشغيل (قطع)", "Startup Yield Losses (pcs)"), value=80, step=10)

    tpm_df = pd.DataFrame({
        tr("تصنيف الفقد", "Loss Category"): [
            tr("الإعداد والتغيير", "Setup & Changeover"),
            tr("أعطال الماكينات", "Equipment Breakdown"),
            tr("بطء السرعة", "Speed Losses"),
            tr("التوقفات اللحظية", "Minor Stoppages"),
            tr("عيوب التصنيع", "Process Defects"),
            tr("هالك بداية التشغيل", "Startup Losses")
        ],
        tr("التأثير (دقائق)", "Impact (Mins)"): [
            loss_setup, loss_breakdown, loss_speed, loss_minor,
            (loss_defects / bottleneck_speed), (loss_startup / bottleneck_speed)
        ]
    }).sort_values(by=tr("التأثير (دقائق)", "Impact (Mins)"), ascending=False)

    fig_pareto = px.bar(
        tpm_df, x=tr("تصنيف الفقد", "Loss Category"), y=tr("التأثير (دقائق)", "Impact (Mins)"),
        text_auto='.1f', title=tr("مخطط باريتو للخسائر الست بالدقائق", "Pareto Analysis of 6 Big Losses"),
        color=tr("التأثير (دقائق)", "Impact (Mins)"), color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 5: CHANGEOVER MATRIX
# ------------------------------------------------------------------------------
with tab5:
    st.subheader("⏱️ " + tr("مصفوفة أوقات التغيير المعيارية بين المنتجات", "Standard Changeover Time Matrix"))
    ch1, ch2 = st.columns(2)
    with ch1:
        from_prod = st.selectbox(tr("المنتج الحالي (From)", "From Product"), list(CHANGEOVER_MATRIX.keys()), index=0)
    with ch2:
        to_prod = st.selectbox(tr("المنتج الجديد (To)", "To Product"), list(CHANGEOVER_MATRIX.keys()), index=1)
        
    std_change_mins = CHANGEOVER_MATRIX.get(from_prod, {}).get(to_prod, 30)
    st.info(f"⏱️ {tr('الوقت المعياري المستهدف للتغيير من', 'Standard Changeover Time from')} [{from_prod}] {tr('إلى', 'to')} [{to_prod}]: **{std_change_mins} {tr('دقيقة', 'Minutes')}**")
    st.dataframe(pd.DataFrame(CHANGEOVER_MATRIX), use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 6: ENERGY SEC
# ------------------------------------------------------------------------------
with tab6:
    st.subheader("⚡ " + tr("مؤشر استهلاك الطاقة النوعي (SEC Calculator)", "Specific Energy Consumption (SEC) Calculator"))
    e1, e2 = st.columns(2)
    with e1:
        elec_kwh = st.number_input(tr("إجمالي استهلاك الكهرباء (kWh)", "Total Electricity (kWh)"), value=420.0, step=10.0)
        elec_rate = st.number_input(tr("سعر kWh الكهرباء (جنيه)", "Electricity Tariff (EGP/kWh)"), value=2.20, step=0.1)
    with e2:
        gas_m3 = st.number_input(tr("إجمالي استهلاك الغاز (m³)", "Total Natural Gas (m³)"), value=115.0, step=5.0)
        gas_rate = st.number_input(tr("سعر m³ الغاز (جنيه)", "Gas Tariff (EGP/m³)"), value=4.50, step=0.1)

    tot_kg = mb['total_finished_goods_kg']
    sec_elec = elec_kwh / tot_kg if tot_kg > 0 else 0.0
    sec_gas = gas_m3 / tot_kg if tot_kg > 0 else 0.0
    total_energy_cost = (elec_kwh * elec_rate) + (gas_m3 * gas_rate)
    cost_per_carton = total_energy_cost / target_cartons if target_cartons > 0 else 0.0

    st.markdown("---")
    sec1, sec2, sec3, sec4 = st.columns(4)
    sec1.metric(tr("SEC الكهرباء النوعي", "Specific Electricity SEC"), f"{sec_elec:.3f} kWh/kg")
    sec2.metric(tr("SEC الغاز النوعي", "Specific Gas SEC"), f"{sec_gas:.3f} m³/kg")
    sec3.metric(tr("تكلفة الطاقة / كرتونة", "Energy Cost / Carton"), f"{cost_per_carton:.2f} EGP")
    sec4.metric(tr("إجمالي فاتورة طاقة الوردية", "Total Shift Energy Bill"), f"{total_energy_cost:,.2f} EGP")

# ------------------------------------------------------------------------------
# TAB 7: OEE & FINANCIAL LOSS
# ------------------------------------------------------------------------------
with tab7:
    st.subheader("📊 " + tr("مؤشرات الفعالية الكلية للمعدات OEE والأثر المالي", "Overall Equipment Effectiveness (OEE) & Financial Losses"))
    planned_mins = st.number_input(tr("زمن الوردية المخطط (دقيقة)", "Planned Shift Time (mins)"), value=480, step=30)
    total_downtime = loss_breakdown + loss_setup + loss_minor
    operating_mins = max(0.0, planned_mins - total_downtime)
    
    actual_units = operating_mins * bottleneck_speed
    total_scrap = loss_defects + loss_startup
    good_units = max(0.0, actual_units - total_scrap)
    
    availability = (operating_mins / planned_mins * 100) if planned_mins > 0 else 0.0
    performance = max(0.0, 100.0 - (loss_speed / planned_mins * 100)) if planned_mins > 0 else 0.0
    quality = (good_units / actual_units * 100) if actual_units > 0 else 100.0
    oee = (availability * performance * quality) / 10000.0

    o1, o2, o3, o4 = st.columns(4)
    o1.metric(tr("الإتاحة (Availability)", "Availability"), f"{availability:.1f}%")
    o2.metric(tr("الأداء (Performance)", "Performance"), f"{performance:.1f}%")
    o3.metric(tr("الجودة (Quality)", "Quality"), f"{quality:.1f}%")
    o4.metric(tr("مؤشر OEE الكلي", "Overall OEE"), f"{oee:.1f}%")

    unit_price = float(p_defaults["price_egp"])
    total_financial_loss = ((total_downtime * bottleneck_speed) + total_scrap) * unit_price
    st.error(f"💰 **{tr('إجمالي الخسارة المالية المباشرة للتوقفات والهالك:', 'Direct Financial Loss from Downtime & Scrap:')} {total_financial_loss:,.2f} EGP**")

# ------------------------------------------------------------------------------
# TAB 8: CUSTOMIZABLE LOGISTICS & TROLLEYS
# ------------------------------------------------------------------------------
with tab8:
    st.subheader("🚚 " + tr("حسابات اللوجستيات والصيجان المخصصة", "Customized Tray & Logistics Calculation"))
    
    # Dynamic Tray Calculation based on Custom Input
    total_trays = math.ceil(total_target_units / custom_pcs_per_tray) if custom_pcs_per_tray > 0 else 0
    total_trolleys = math.ceil(total_trays / TRAYS_PER_TROLLEY)
    
    film_cm = st.number_input(tr("طول شريط الفيلم لكل قطعة (سم)", "Film Strip Length / Pc (cm)"), value=18.0, step=1.0)
    roll_m = st.number_input(tr("طول رول الفيلم الممتاز (متر)", "Film Roll Length (m)"), value=1000.0, step=100.0)
    
    tot_film_m = (total_target_units * (film_cm / 100.0))
    rolls_req = math.ceil(tot_film_m / roll_m) if roll_m > 0 else 0
    
    l1, l2, l3, l4 = st.columns(4)
    l1.metric(tr("سعة الصاج الفعالة", "Effective Tray Capacity"), f"{custom_pcs_per_tray} pcs/tray")
    l2.metric(tr("إجمالي الصيجان المطلوبة", "Total Trays Required"), f"{total_trays:,} Trays")
    l3.metric(tr("إجمالي التروليات المطلوبة", "Total Trolleys Required"), f"{total_trolleys:,} Trolleys")
    l4.metric(tr("عدد رولات الفيلم", "Film Rolls Required"), f"{rolls_req:,} Rolls ({tot_film_m:,.0f} m)")

# ------------------------------------------------------------------------------
# TAB 9: EXCEL REPORT EXPORT
# ------------------------------------------------------------------------------
with tab9:
    st.subheader("📄 " + tr("تصدير التقرير الفني المعتمد للوردية (Excel Export)", "Export Certified Shift Excel Report"))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        summary_df = pd.DataFrame([{
            "Product": selected_prod,
            "Target Units": total_target_units,
            "Custom Tray Capacity": custom_pcs_per_tray,
            "Total Trays": total_trays,
            "Total Trolleys": total_trolleys,
            "Base Dough (kg)": mb['total_base_dough_kg'],
            "Margarine 10% (kg)": mb['total_margarine_kg'],
            "Total Laminated Dough (kg)": mb['total_lam_dough_kg'],
            "Batches (220kg)": mb['batches_req'],
            "Evaporation Loss (kg)": mb['total_evap_loss_kg'],
            "Filling Required (kg)": mb['total_filling_kg'],
            "Finished Goods (kg)": mb['total_finished_goods_kg'],
            "Cpk Index": spc_metrics['cpk'],
            "Cpm Index": spc_metrics['cpm'],
            "OEE Score (%)": round(oee, 2),
            "SEC Elec (kWh/kg)": round(sec_elec, 3),
            "SEC Gas (m3/kg)": round(sec_gas, 3),
            "Total Financial Loss (EGP)": round(total_financial_loss, 2)
        }])
        summary_df.to_excel(writer, sheet_name='Shift Summary', index=False)
        tpm_df.to_excel(writer, sheet_name='TPM Losses', index=False)
        st.session_state["spc_data"].to_excel(writer, sheet_name='SPC Sample Readings', index=False)
        
    st.download_button(
        label="📥 " + tr("تحميل تقرير الوردية الشامل صيغة Excel", "Download Certified Shift Excel Report (.xlsx)"),
        data=output.getvalue(),
        file_name=f"Master_Shift_Report_{selected_prod.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )