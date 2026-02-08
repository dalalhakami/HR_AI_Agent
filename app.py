import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime

# 1. إعدادات الهوية البصرية الفاخرة
st.set_page_config(page_title="مركز ذكاء القوى العاملة", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        text-align: right;
    }

    .stApp { 
        background: radial-gradient(circle at top right, #1E293B, #0F172A, #020617); 
    }

    /* مربع الترحيب المركزي بدون قسم الحالة */
    .welcome-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(25px);
        border: 1px solid rgba(0, 245, 255, 0.15);
        padding: 60px 40px;
        border-radius: 35px;
        text-align: center;
        margin: 100px auto;
        max-width: 800px;
        box-shadow: 0 25px 50px rgba(0,0,0,0.6);
    }

    h1 { 
        background: linear-gradient(to left, #F8FAFC, #00F5FF); 
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent; 
        font-weight: 900 !important; 
        font-size: 3.5rem !important;
        text-align: center !important;
    }

    div[data-testid="stMetric"] { 
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(0, 245, 255, 0.1) !important;
        padding: 25px !important; 
        border-radius: 20px !important;
    }

    .sidebar-signature {
        padding-top: 25px;
        border-top: 1px solid rgba(0, 245, 255, 0.1);
        text-align: center;
        margin-top: 60px;
    }

    .rec-box { 
        background: rgba(0, 245, 255, 0.07); 
        padding: 20px; border-radius: 15px; 
        border-right: 6px solid #00F5FF; margin-bottom: 15px; 
        color: #F8FAFC; font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. تحميل البيانات
@st.cache_resource
def load_hr_data():
    try:
        base_path = os.path.dirname(__file__)
        file_path = os.path.join(base_path, "Resigned Report Date Range.xlsx")
        df = pd.read_excel(file_path, engine="openpyxl")
        df["تاريخ انتهاء الخدمة"] = pd.to_datetime(df["تاريخ انتهاء الخدمة"], errors="coerce")
        return df.dropna(subset=["تاريخ انتهاء الخدمة"]).copy(), None
    except Exception as e: return None, str(e)

df, error = load_hr_data()

# 3. القائمة الجانبية
with st.sidebar:
    st.markdown("<h2 style='color: #00F5FF; font-size: 1.6rem;'>⚙️ لوحة التحكم</h2>", unsafe_allow_html=True)
    btn_analysis = st.button("📊 التحليل الاستراتيجي والحلول")
    btn_forecast = st.button("🔮 النمذجة التنبؤية القادمة")
    
    st.markdown("---")
    st.markdown("### 🤖 المحلل الذكي")
    u_input = st.chat_input("اسأل عن تفاصيل البيانات...")

    st.markdown(f"""
        <div class="sidebar-signature">
            <p style="color: #94A3B8; font-size: 0.85rem; margin-bottom: 5px;">إعداد</p>
            <p style="color: #00F5FF; font-size: 1.6rem; font-weight: 900; margin-top: 0;">دلال حكمي</p>
            <p style="color: #475569; font-size: 0.85rem;">dalal3021@gmail.com</p>
        </div>
    """, unsafe_allow_html=True)

# 4. منطق العرض
if btn_analysis:
    st.markdown("<h1 style='text-align: right !important;'>التحليل الاستراتيجي</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns([2, 1])
    with col1:
        top_dept = df["الجهة"].mode()[0]
        st.metric("القطاع الأكثر تسرباً", top_dept)
        st.markdown("### 💡 المبادرات المقترحة")
        st.markdown(f'<div class="rec-box">🚀 تحسين بيئة العمل في {top_dept}</div>', unsafe_allow_html=True)
    with col2:
        st.dataframe(df[["الجهة", "تاريخ انتهاء الخدمة"]].tail(10), use_container_width=True)

elif btn_forecast:
    st.markdown("<h1 style='text-align: right !important;'>التوقعات التنبؤية</h1>", unsafe_allow_html=True)
    chart_data = pd.DataFrame(np.random.randint(5, 15, size=(6, 1)), columns=['الحالات المتوقعة'])
    st.area_chart(chart_data, color="#00F5FF")

else:
    # مربع الترحيب الصافي (بدون قسم الحالة)
    st.markdown(f"""
        <div class="welcome-card">
            <div style="margin-bottom: 30px;">
                <span style="background: rgba(0, 245, 255, 0.1); color: #00F5FF; padding: 10px 25px; border-radius: 50px; font-size: 0.95rem; font-weight: bold; border: 1px solid rgba(0, 245, 255, 0.3);">
                    نظام التحليل الاستراتيجي v2.5
                </span>
            </div>
            <h1 style="margin-bottom: 30px;">منصة ذكاء الأعمال</h1>
            <p style="color: #CBD5E1; font-size: 1.6rem; line-height: 1.8; max-width: 650px; margin: 0 auto;">
                مرحباً بك في الواجهة التحليلية المتطورة. تم تفعيل المحرك الذكي لمعالجة بيانات القوى العاملة وتقديم رؤى استراتيجية دقيقة.
            </p>
            <p style="color: #94A3B8; font-size: 1.2rem; margin-top: 30px;">
                يرجى اختيار <b>المسار التحليلي</b> المطلوب من القائمة الجانبية للبدء.
            </p>
        </div>
    """, unsafe_allow_html=True)