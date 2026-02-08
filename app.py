import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import plotly.express as px
from dateutil.relativedelta import relativedelta
from sklearn.ensemble import RandomForestRegressor


# =========================
# 1) إعدادات الهوية البصرية
# =========================
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

.welcome-card {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(25px);
    border: 1px solid rgba(0, 245, 255, 0.15);
    padding: 60px 40px;
    border-radius: 35px;
    text-align: center;
    margin: 70px auto 30px auto;
    max-width: 980px;
    box-shadow: 0 25px 50px rgba(0,0,0,0.6);
}

h1 { 
    background: linear-gradient(to left, #F8FAFC, #00F5FF); 
    -webkit-background-clip: text; 
    -webkit-text-fill-color: transparent; 
    font-weight: 900 !important; 
    font-size: 3.1rem !important;
    text-align: center !important;
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
.small-muted {
    color: #94A3B8;
    font-size: 0.95rem;
}
</style>
""", unsafe_allow_html=True)

px.defaults.template = "plotly_dark"


# =========================
# 2) تحميل البيانات
# =========================
@st.cache_data
def load_hr_data():
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "Resigned Report Date Range.xlsx")
    df = pd.read_excel(file_path, engine="openpyxl")
    df["تاريخ انتهاء الخدمة"] = pd.to_datetime(df["تاريخ انتهاء الخدمة"], errors="coerce")
    return df

try:
    df = load_hr_data()
    error = None
except Exception as e:
    df = None
    error = str(e)


# =========================
# 3) أدوات Parsing + Filters
# =========================
AR_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "أبريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7, "اغسطس": 8, "أغسطس": 8,
    "سبتمبر": 9, "اكتوبر": 10, "أكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12
}

def norm_ar(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي")
    return s

def get_ref_today(dff: pd.DataFrame) -> pd.Timestamp:
    mx = dff["تاريخ انتهاء الخدمة"].max()
    if pd.isna(mx):
        return pd.Timestamp.today().normalize()
    return pd.Timestamp(mx).normalize()

def parse_date_any(s: str):
    s = (s or "").strip()
    if not s:
        return pd.NaT
    # محاولات شائعة
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return pd.to_datetime(pd.Timestamp.strptime(s, fmt))
        except Exception:
            pass
    # fallback pandas
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def extract_between_dates(qn: str):
    # من 2025-01-01 إلى 2025-03-31
    m = re.search(r"من\s+(.+?)\s+(?:الى|إلى)\s+(.+)", qn)
    if not m:
        return None
    d1 = parse_date_any(m.group(1))
    d2 = parse_date_any(m.group(2))
    if pd.isna(d1) or pd.isna(d2):
        return None
    start = min(pd.Timestamp(d1).normalize(), pd.Timestamp(d2).normalize())
    end = max(pd.Timestamp(d1).normalize(), pd.Timestamp(d2).normalize())
    return start, end

def extract_relative_range(qn: str, ref_today: pd.Timestamp):
    # آخر 3 شهور / آخر 10 ايام / آخر أسبوع
    m = re.search(r"(?:اخر|آخر)\s+(\d+)\s*(يوم|ايام|اسبوع|اسابيع|شهر|شهور|اشهر|سنه|سنوات)", qn)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if "يوم" in unit:
            start = ref_today - pd.Timedelta(days=n)
        elif "اسبوع" in unit:
            start = ref_today - pd.Timedelta(weeks=n)
        elif "شهر" in unit or "اشهر" in unit or "شهور" in unit:
            start = pd.Timestamp(ref_today - relativedelta(months=n)).normalize()
        else:
            start = pd.Timestamp(ref_today - relativedelta(years=n)).normalize()
        return start, ref_today

    if "اخر شهر" in qn or "آخر شهر" in qn:
        start = pd.Timestamp(ref_today - relativedelta(months=1)).normalize()
        return start, ref_today

    if "اخر اسبوع" in qn or "آخر اسبوع" in qn:
        start = ref_today - pd.Timedelta(weeks=1)
        return start, ref_today

    return None

def extract_month_year(qn: str):
    # يناير 2025 / 2025 / فبراير 2024
    year = None
    m = re.search(r"(20\d{2})", qn)
    if m:
        year = int(m.group(1))

    month = None
    for name, num in AR_MONTHS.items():
        if norm_ar(name) in qn:
            month = num
            break

    if year and month:
        start = pd.Timestamp(year=year, month=month, day=1)
        end = (start + relativedelta(months=1)) - pd.Timedelta(days=1)
        return start, end

    if year and not month:
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)
        return start, end

    return None

def get_date_range_from_question(q: str, ref_today: pd.Timestamp):
    qn = norm_ar(q)
    r = extract_between_dates(qn)
    if r: return r
    r = extract_relative_range(qn, ref_today)
    if r: return r
    r = extract_month_year(qn)
    if r: return r
    return None

def apply_sidebar_filters(df_in, date_range, dept_sel, nat_sel):
    dff = df_in.dropna(subset=["تاريخ انتهاء الخدمة"]).copy()

    start = pd.to_datetime(date_range[0])
    end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    dff = dff[(dff["تاريخ انتهاء الخدمة"] >= start) & (dff["تاريخ انتهاء الخدمة"] <= end)]

    if dept_sel:
        dff = dff[dff["الجهة"].astype(str).isin(dept_sel)]
    if nat_sel:
        dff = dff[dff["الجنسية"].astype(str).isin(nat_sel)]
    return dff

def apply_question_entity_filters(dff: pd.DataFrame, q: str):
    qn = norm_ar(q)

    # جهة: ...
    m = re.search(r"(?:جهه|الجهه|جهة|الجهة)\s*[:：]\s*(.+)", qn)
    if m:
        val = m.group(1).strip()[:60]
        dff = dff[dff["الجهة"].astype(str).str.contains(val, na=False)]

    # جنسية: ...
    m = re.search(r"(?:جنسيه|الجنسية|الجنسيه|جنسية)\s*[:：]\s*(.+)", qn)
    if m:
        val = m.group(1).strip()[:60]
        dff = dff[dff["الجنسية"].astype(str).str.contains(val, na=False)]

    return dff

def make_series(dff: pd.DataFrame, freq="D"):
    s = (dff.dropna(subset=["تاريخ انتهاء الخدمة"])
            .set_index("تاريخ انتهاء الخدمة")
            .resample(freq)
            .size()
            .rename("y"))
    if freq == "D":
        s = s.asfreq("D", fill_value=0)
    return s

def make_features(series: pd.Series, freq="D"):
    d = pd.DataFrame({"y": series})

    if freq == "D":
        d["dow"] = d.index.dayofweek
        d["dom"] = d.index.day
        d["month"] = d.index.month
        d["is_weekend"] = (d["dow"] >= 4).astype(int)
        use_lags = (1, 7, 14, 28)
    else:
        d["month"] = d.index.month
        d["quarter"] = d.index.quarter
        use_lags = (1, 2, 3, 6)

    for lag in use_lags:
        d[f"lag_{lag}"] = d["y"].shift(lag)

    d = d.dropna()
    X = d.drop(columns=["y"])
    y = d["y"]
    return X, y, use_lags

def forecast(dff: pd.DataFrame, steps=30, freq="D"):
    s = make_series(dff, freq=freq)

    # fallback إذا البيانات قليلة
    if len(s) < (60 if freq == "D" else 12):
        base = int(round(s.tail(30).mean())) if freq == "D" else int(round(s.tail(6).mean()))
        future_idx = (
            pd.date_range(s.index.max() + pd.Timedelta(days=1), periods=steps, freq="D")
            if freq == "D"
            else pd.date_range(s.index.max() + pd.offsets.MonthBegin(1), periods=steps, freq="MS")
        )
        return pd.DataFrame({"التاريخ": future_idx, "الحالات المتوقعة": [max(0, base)] * len(future_idx)})

    X, y, use_lags = make_features(s, freq=freq)
    model = RandomForestRegressor(n_estimators=400, random_state=42)
    model.fit(X, y)

    future_idx = (
        pd.date_range(s.index.max() + pd.Timedelta(days=1), periods=steps, freq="D")
        if freq == "D"
        else pd.date_range(s.index.max() + pd.offsets.MonthBegin(1), periods=steps, freq="MS")
    )

    s_ext = s.copy()
    preds = []

    for dt in future_idx:
        row = {}
        if freq == "D":
            row["dow"] = dt.dayofweek
            row["dom"] = dt.day
            row["month"] = dt.month
            row["is_weekend"] = int(dt.dayofweek >= 4)
        else:
            row["month"] = dt.month
            row["quarter"] = dt.quarter

        for lag in use_lags:
            row[f"lag_{lag}"] = float(s_ext.iloc[-lag])

        yhat = float(model.predict(pd.DataFrame([row]))[0])
        yhat = max(0.0, yhat)
        preds.append(yhat)
        s_ext.loc[dt] = yhat

    out = pd.DataFrame({"التاريخ": future_idx, "الحالات المتوقعة": np.round(preds).astype(int)})
    return out


# =========================
# 4) المحلل الذكي: اختيار الرسم تلقائيًا
# =========================
def auto_chart(dff_base: pd.DataFrame, q: str, top_n=10, sidebar_info=""):
    qn = norm_ar(q)

    # مرجع "آخر 3 شهور" = آخر تاريخ بالبيانات بعد فلاتر السايدبار
    ref_today = get_ref_today(dff_base)

    # طبّقي فلاتر الكيان من السؤال (جهة: / جنسية:)
    dff = apply_question_entity_filters(dff_base.copy(), q)

    # طبّقي فلاتر التاريخ من السؤال (آخر 3 شهور / من..الى / يناير 2025 ...)
    dr = get_date_range_from_question(q, ref_today)
    range_text = ""
    if dr:
        start, end = dr
        end_inclusive = end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        dff = dff[(dff["تاريخ انتهاء الخدمة"] >= start) & (dff["تاريخ انتهاء الخدمة"] <= end_inclusive)]
        range_text = f"📅 الفترة: من **{start.date()}** إلى **{end.date()}** (مرجع البيانات: {ref_today.date()})"

    # Helpers
    def add_footer(msg: str):
        parts = [msg]
        if range_text:
            parts.append(range_text)
        if sidebar_info:
            parts.append(sidebar_info)
        return "\n\n".join(parts)

    # ===== جدول / أحدث =====
    if any(k in qn for k in ["اخر", "احدث", "latest", "حديث", "آخر", "أحدث"]) and any(k in qn for k in ["سجل", "سجلات", "جدول", "table"]):
        tbl = dff.sort_values("تاريخ انتهاء الخدمة").tail(10)[["الجهة", "الجنسية", "تاريخ انتهاء الخدمة"]]
        return add_footer("🕒 أحدث 10 سجلات:"), None, tbl

    # ===== عدد =====
    if any(k in qn for k in ["كم", "عدد", "اجمالي", "إجمالي", "المجموع", "total"]):
        return add_footer(f"📊 عدد الاستقالات = **{len(dff)}**"), None, None

    # ===== توقع =====
    if any(k in qn for k in ["توقع", "يتوقع", "تنبؤ", "يتنبا", "القادم", "الجاي", "الشهر القادم", "الاسبوع القادم"]):
        # شهري
        if any(k in qn for k in ["شهري", "شهر", "اشهر", "شهور"]):
            m = re.search(r"(\d+)\s*(شهر|اشهر|شهور)", qn)
            steps = int(m.group(1)) if m else 6
            fc = forecast(dff, steps=steps, freq="M")
            fig = px.bar(fc, x="التاريخ", y="الحالات المتوقعة", text_auto=True, title=f"توقع الاستقالات ({steps} أشهر)")
            return add_footer("🔮 توقع شهري"), fig, fc

        # يومي
        m = re.search(r"(\d+)\s*(يوم|ايام)", qn)
        steps = int(m.group(1)) if m else 30
        fc = forecast(dff, steps=steps, freq="D")
        fig = px.area(fc, x="التاريخ", y="الحالات المتوقعة", title=f"توقع الاستقالات ({steps} يوم)")
        return add_footer("🔮 توقع يومي"), fig, fc

    # ===== توزيع (Pie) =====
    if any(k in qn for k in ["توزيع", "نسب", "نسبة", "pie", "دائره", "دائرة"]):
        if "جنس" in qn:
            vc = dff["الجنسية"].value_counts().head(top_n).rename_axis("الجنسية").reset_index(name="العدد")
            fig = px.pie(vc, values="العدد", names="الجنسية", hole=0.4, title=f"توزيع الجنسيات (Top {top_n})")
            fig.update_traces(textinfo="percent+label")
            return add_footer("🌍 توزيع الجنسيات"), fig, vc

        if any(k in qn for k in ["جهه", "جهة", "قطاع", "اداره", "إدارة"]):
            vc = dff["الجهة"].value_counts().head(top_n).rename_axis("الجهة").reset_index(name="العدد")
            fig = px.pie(vc, values="العدد", names="الجهة", hole=0.4, title=f"توزيع الجهات (Top {top_n})")
            fig.update_traces(textinfo="percent+label")
            return add_footer("🏢 توزيع الجهات"), fig, vc

    # ===== أكثر / أقل (Bar) =====
    if any(k in qn for k in ["اكثر", "الأكثر", "اعلى", "أعلى", "top", "اكبر", "أكبر"]):
        if "جنس" in qn:
            vc = dff["الجنسية"].value_counts().head(top_n).rename_axis("الجنسية").reset_index(name="العدد")
            fig = px.bar(vc, x="الجنسية", y="العدد", text_auto=True, title=f"أكثر الجنسيات (Top {top_n})")
            return add_footer("🌍 أكثر الجنسيات"), fig, vc

        vc = dff["الجهة"].value_counts().head(top_n).rename_axis("الجهة").reset_index(name="العدد")
        fig = px.bar(vc, x="الجهة", y="العدد", text_auto=True, title=f"أكثر الجهات (Top {top_n})")
        fig.update_layout(xaxis_tickangle=-35)
        return add_footer("🏢 أكثر الجهات"), fig, vc

    if any(k in qn for k in ["اقل", "الأقل", "ادنى", "أدنى", "bottom"]):
        if "جنس" in qn:
            vc = dff["الجنسية"].value_counts().tail(top_n).rename_axis("الجنسية").reset_index(name="العدد")
            fig = px.bar(vc, x="الجنسية", y="العدد", text_auto=True, title=f"أقل الجنسيات (Bottom {top_n})")
            return add_footer("📉 أقل الجنسيات"), fig, vc

        vc = dff["الجهة"].value_counts().tail(top_n).rename_axis("الجهة").reset_index(name="العدد")
        fig = px.bar(vc, x="الجهة", y="العدد", text_auto=True, title=f"أقل الجهات (Bottom {top_n})")
        fig.update_layout(xaxis_tickangle=-35)
        return add_footer("📉 أقل الجهات"), fig, vc

    # ===== ترند / زمن (Line) =====
    if any(k in qn for k in ["ترند", "اتجاه", "عبر الزمن", "زمن", "trend", "line", "خطي", "خط"]):
        freq = "M" if any(k in qn for k in ["شهري", "شهر"]) else "D"
        ts = make_series(dff, freq=freq).reset_index()
        ts.columns = ["التاريخ", "العدد"]
        title = "الاتجاه شهريًا" if freq == "M" else "الاتجاه يوميًا"
        fig = px.line(ts, x="التاريخ", y="العدد", markers=True, title=title)
        return add_footer("📈 الاتجاه عبر الزمن"), fig, ts.tail(120)

    # ===== نسبة جنسية محددة (سؤال مثل: كم نسبة السعوديين؟) =====
    if any(k in qn for k in ["نسبة", "نسبه", "percent", "%"]):
        total = len(dff)
        if total == 0:
            return add_footer("لا توجد بيانات ضمن الفلاتر الحالية."), None, None
        # محاولة التقاط جنسية مذكورة
        uniques = dff["الجنسية"].dropna().astype(str).unique().tolist()
        for nat in uniques:
            if norm_ar(nat) in qn:
                count = (dff["الجنسية"].astype(str) == nat).sum()
                pct = (count / total) * 100
                return add_footer(f"📌 نسبة **{nat}** = **{pct:.2f}%** ({count} من {total})"), None, None

    # Default Help
    help_msg = (
        "اكتبي سؤال مثل:\n"
        "- **كم استقالوا آخر 3 شهور**\n"
        "- **من 2025-01-01 إلى 2025-03-31 كم عدد الاستقالات**\n"
        "- **توزيع الجنسيات** / **توزيع الجهات**\n"
        "- **أكثر جهة** / **أقل جهة**\n"
        "- **ترند شهري** / **ترند يومي**\n"
        "- **توقع 30 يوم** / **توقع 6 أشهر**\n"
        "- **أحدث سجلات جدول**\n\n"
        "وللفلترة داخل السؤال:\n"
        "- **كم استقالوا آخر 3 شهور جهة: الموارد البشرية**\n"
        "- **توزيع الجنسيات جنسية: سعودي** (أو بدونها)\n"
    )
    return add_footer(help_msg), None, None


# =========================
# 5) واجهة Sidebar (Filters + Chat)
# =========================
with st.sidebar:
    st.markdown("<h2 style='color: #00F5FF; font-size: 1.6rem;'>⚙️ لوحة التحكم</h2>", unsafe_allow_html=True)

    if df is None:
        st.error(f"تعذر تحميل الملف: {error}")
        st.stop()

    df_clean = df.dropna(subset=["تاريخ انتهاء الخدمة"]).copy()
    if df_clean.empty:
        st.error("لا توجد بيانات صالحة في عمود تاريخ انتهاء الخدمة.")
        st.stop()

    min_d = df_clean["تاريخ انتهاء الخدمة"].min().date()
    max_d = df_clean["تاريخ انتهاء الخدمة"].max().date()

    date_range = st.date_input("📅 الفترة", value=(min_d, max_d), min_value=min_d, max_value=max_d)

    dept_list = sorted(df_clean["الجهة"].dropna().astype(str).unique().tolist())
    nat_list  = sorted(df_clean["الجنسية"].dropna().astype(str).unique().tolist())

    dept_sel = st.multiselect("🏢 الجهة", dept_list, default=[])
    nat_sel  = st.multiselect("🌍 الجنسية", nat_list, default=[])

    top_n = st.slider("Top N", 3, 20, 10)

    st.markdown("---")
    st.markdown("### 🤖 المحلل الذكي")
    u_input = st.chat_input("اسألي: كم/توزيع/أكثر/أقل/ترند/توقع/جدول...")

    st.markdown("""
        <div class="sidebar-signature">
            <p style="color: #94A3B8; font-size: 0.85rem; margin-bottom: 5px;">إعداد</p>
            <p style="color: #00F5FF; font-size: 1.6rem; font-weight: 900; margin-top: 0;">دلال حكمي</p>
            <p style="color: #475569; font-size: 0.85rem;">dalal3021@gmail.com</p>
        </div>
    """, unsafe_allow_html=True)


# =========================
# 6) تطبيق فلاتر السايدبار
# =========================
dff_sidebar = apply_sidebar_filters(df, date_range, dept_sel, nat_sel)

# نص يوضح فلاتر السايدبار في رد الشاتبوت
sidebar_info_parts = []
sidebar_info_parts.append(f"🎛️ فلاتر السايدبار: الفترة ({date_range[0]} → {date_range[1]})")
if dept_sel:
    sidebar_info_parts.append(f"الجهة: {', '.join(dept_sel[:3])}{'…' if len(dept_sel) > 3 else ''}")
else:
    sidebar_info_parts.append("الجهة: كل الجهات")
if nat_sel:
    sidebar_info_parts.append(f"الجنسية: {', '.join(nat_sel[:3])}{'…' if len(nat_sel) > 3 else ''}")
else:
    sidebar_info_parts.append("الجنسية: كل الجنسيات")
sidebar_info = " | ".join(sidebar_info_parts)


# =========================
# 7) Tabs Dashboard
# =========================
tab1, tab2, tab3, tab4 = st.tabs(["📊 نظرة عامة", "📈 الاتجاهات", "🔮 التوقعات", "🤖 اسألني"])

with tab1:
    st.markdown("<h1>نظرة عامة</h1>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي السجلات", f"{len(dff_sidebar):,}")
    c2.metric("عدد الجهات", int(dff_sidebar["الجهة"].nunique()))
    c3.metric("عدد الجنسيات", int(dff_sidebar["الجنسية"].nunique()))

    colA, colB = st.columns(2)

    with colA:
        nat_counts = (dff_sidebar["الجنسية"].value_counts().head(top_n)
                      .rename_axis("الجنسية").reset_index(name="العدد"))
        fig = px.pie(nat_counts, values="العدد", names="الجنسية", hole=0.4, title=f"Top {top_n} جنسيات")
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with colB:
        dept_counts = (dff_sidebar["الجهة"].value_counts().head(top_n)
                       .rename_axis("الجهة").reset_index(name="العدد"))
        fig = px.bar(dept_counts, x="الجهة", y="العدد", text_auto=True, title=f"Top {top_n} جهات")
        fig.update_layout(xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    # مبادرات مقترحة (اختياري — مثل كودك القديم)
    if not dff_sidebar.empty:
        top_dept = dff_sidebar["الجهة"].mode().iloc[0] if not dff_sidebar["الجهة"].mode().empty else "غير محدد"
        st.markdown("### 💡 مبادرات مقترحة", unsafe_allow_html=True)
        st.markdown(f'<div class="rec-box">🚀 تحسين بيئة العمل وتطوير المزايا في {top_dept}</div>', unsafe_allow_html=True)
        st.markdown('<div class="rec-box">📈 تكثيف برامج الاستبقاء للموظفين المتميزين</div>', unsafe_allow_html=True)

with tab2:
    st.markdown("<h1>الاتجاهات</h1>", unsafe_allow_html=True)

    gran = st.radio("الدقة الزمنية", ["يومي", "شهري"], horizontal=True)
    freq = "D" if gran == "يومي" else "M"

    ts = make_series(dff_sidebar, freq=freq).reset_index()
    ts.columns = ["التاريخ", "العدد"]

    fig = px.line(ts, x="التاريخ", y="العدد", markers=True, title=f"الاستقالات ({gran})")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.markdown("<h1>التوقعات</h1>", unsafe_allow_html=True)

    mode = st.radio("نوع التوقع", ["يومي (30 يوم)", "شهري (6 أشهر)"], horizontal=True)

    if mode.startswith("يومي"):
        fc = forecast(dff_sidebar, steps=30, freq="D")
        fig = px.area(fc, x="التاريخ", y="الحالات المتوقعة", title="توقع الاستقالات (30 يوم)")
    else:
        fc = forecast(dff_sidebar, steps=6, freq="M")
        fig = px.bar(fc, x="التاريخ", y="الحالات المتوقعة", text_auto=True, title="توقع الاستقالات (6 أشهر)")

    st.metric("إجمالي المتوقع", int(fc["الحالات المتوقعة"].sum()))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(fc, use_container_width=True)

with tab4:
    st.markdown("<h1>اسألني</h1>", unsafe_allow_html=True)
    st.markdown("<p class='small-muted'>اكتبي سؤال، وسيتم اختيار الرسم تلقائيًا (Pie/Bar/Line/Forecast) + فترة الحساب تُعرض دائمًا.</p>", unsafe_allow_html=True)

    if u_input:
        st.markdown("<h2 style='color: #00F5FF;'>🤖 إجابة المحلل الذكي:</h2>", unsafe_allow_html=True)
        with st.chat_message("assistant"):
            msg, fig, table = auto_chart(dff_sidebar, u_input, top_n=top_n, sidebar_info=sidebar_info)
            st.write(msg)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

            # عرض الجدول فقط إذا المستخدم ذكر "جدول"
            if table is not None and ("جدول" in u_input or "table" in u_input.lower()):
                st.dataframe(table, use_container_width=True)
    else:
        st.markdown("""
        <div class="welcome-card">
            <div style="margin-bottom: 20px;">
                <span style="background: rgba(0, 245, 255, 0.1); color: #00F5FF; padding: 10px 25px; border-radius: 50px; font-size: 0.95rem; font-weight: bold; border: 1px solid rgba(0, 245, 255, 0.3);">
                    نظام التحليل الاستراتيجي v3.0
                </span>
            </div>
            <h1 style="margin-bottom: 18px;">منصة ذكاء الأعمال</h1>
            <p style="color: #CBD5E1; font-size: 1.35rem; line-height: 1.8; max-width: 750px; margin: 0 auto;">
                استخدمي الفلاتر في القائمة الجانبية، ثم اسألي سؤال في المحلل الذكي — سيظهر الرسم تلقائيًا مع فترة الحساب.
            </p>
            <p style="color: #94A3B8; font-size: 1.05rem; margin-top: 18px;">
                أمثلة: <b>كم استقالوا آخر 3 شهور</b> — <b>توزيع الجنسيات</b> — <b>أكثر جهة</b> — <b>ترند شهري</b> — <b>توقع 30 يوم</b>
            </p>
        </div>
        """, unsafe_allow_html=True)

# تنبيه إذا الفلاتر ضيقة جدًا
if dff_sidebar.empty:
    st.info("لا توجد بيانات ضمن فلاتر السايدبار الحالية. وسّعي الفترة أو أزيلي بعض الفلاتر.")
