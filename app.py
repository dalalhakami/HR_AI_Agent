import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import plotly.express as px
from dateutil.relativedelta import relativedelta
from sklearn.ensemble import RandomForestRegressor


# =========================
# 1) إعدادات الواجهة
# =========================
st.set_page_config(page_title="مركز ذكاء القوى العاملة", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Tajawal', sans-serif; text-align: right; }
.stApp { background: radial-gradient(circle at top right, #1E293B, #0F172A, #020617); }
h1 { 
  background: linear-gradient(to left, #F8FAFC, #00F5FF);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  font-weight: 900 !important; font-size: 3.0rem !important;
  text-align: center !important;
}
.small-muted { color: #94A3B8; font-size: 0.95rem; }
.welcome-card {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(25px);
  border: 1px solid rgba(0, 245, 255, 0.15);
  padding: 50px 35px;
  border-radius: 30px;
  text-align: center;
  margin: 55px auto 20px auto;
  max-width: 980px;
  box-shadow: 0 25px 50px rgba(0,0,0,0.6);
}
.sidebar-signature{
  padding-top: 14px;
  border-top: 1px solid rgba(0, 245, 255, 0.1);
  text-align: center;
  margin-top: 14px;
}
.rec-box { 
  background: rgba(0, 245, 255, 0.07); 
  padding: 16px; border-radius: 14px; 
  border-right: 5px solid #00F5FF; margin-bottom: 12px; 
  color: #F8FAFC; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

px.defaults.template = "plotly_dark"


# =========================
# 2) تحميل البيانات
# =========================
@st.cache_data
def load_actual_data():
    base = os.path.dirname(__file__)
    path = os.path.join(base, "Resigned Report Date Range.xlsx")
    df = pd.read_excel(path, engine="openpyxl")
    df["تاريخ انتهاء الخدمة"] = pd.to_datetime(df["تاريخ انتهاء الخدمة"], errors="coerce", dayfirst=True)
    return df

@st.cache_data
def load_forecast_file():
    base = os.path.dirname(__file__)
    path = os.path.join(base, "توقعات الاستقالات وتحليل البيانات.xlsx")
    return pd.read_excel(path, engine="openpyxl")

try:
    df = load_actual_data()
    error = None
except Exception as e:
    df = None
    error = str(e)

try:
    forecast_file_df = load_forecast_file()
except Exception:
    forecast_file_df = None


# =========================
# 3) تجهيز توقع الملف السنوي (مصدر ثابت)
# =========================
def get_file_yearly_forecast(fdf: pd.DataFrame) -> pd.DataFrame:
    if fdf is None or fdf.empty:
        return pd.DataFrame()

    needed = {"السنة", "عدد الاستقالات المتوقع"}
    if not needed.issubset(set(fdf.columns)):
        return pd.DataFrame()

    out = (fdf.groupby("السنة", as_index=False)["عدد الاستقالات المتوقع"]
           .sum()
           .rename(columns={"عدد الاستقالات المتوقع": "الاستقالات المتوقعة (ملف)"}))
    out["السنة"] = pd.to_numeric(out["السنة"], errors="coerce").astype("Int64")
    out = out.dropna(subset=["السنة"]).copy()
    out["السنة"] = out["السنة"].astype(int)
    out["الاستقالات المتوقعة (ملف)"] = pd.to_numeric(out["الاستقالات المتوقعة (ملف)"], errors="coerce").fillna(0).round().astype(int)
    return out.sort_values("السنة").reset_index(drop=True)

file_yearly_fc = get_file_yearly_forecast(forecast_file_df)


# =========================
# 4) أدوات Parsing + Filters
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
    s = re.sub(r"\s+", " ", s)
    return s

def get_ref_today(dff: pd.DataFrame) -> pd.Timestamp:
    mx = dff["تاريخ انتهاء الخدمة"].max()
    return pd.Timestamp.today().normalize() if pd.isna(mx) else pd.Timestamp(mx).normalize()

def parse_date_any(s: str):
    s = (s or "").strip()
    if not s:
        return pd.NaT
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def extract_between_dates(qn: str):
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

    m = re.search(r"(?:جهه|جهة|الجهه|الجهة)\s*[:：]\s*(.+)", qn)
    if m:
        val = m.group(1).strip()[:80]
        dff = dff[dff["الجهة"].astype(str).str.contains(val, na=False)]

    m = re.search(r"(?:جنسيه|جنسية|الجنسية|الجنسيه)\s*[:：]\s*(.+)", qn)
    if m:
        val = m.group(1).strip()[:80]
        dff = dff[dff["الجنسية"].astype(str).str.contains(val, na=False)]

    return dff


# =========================
# 5) سلسلة زمنية + توقع (يومي/شهري) داخل التطبيق
# =========================
def make_series(dff: pd.DataFrame, freq="D"):
    if freq == "M":
        freq = "ME"
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

def forecast_time(dff: pd.DataFrame, steps=30, freq="D"):
    s = make_series(dff, freq=("ME" if freq == "M" else "D"))

    min_need = 60 if freq == "D" else 12
    if len(s) < min_need:
        base = float(s.tail(30).mean()) if freq == "D" else float(s.tail(6).mean())
        if np.isnan(base):
            base = 0.0
        base_i = int(round(base))
        future_idx = (
            pd.date_range(s.index.max() + pd.Timedelta(days=1), periods=steps, freq="D")
            if freq == "D"
            else pd.date_range(s.index.max() + pd.offsets.MonthBegin(1), periods=steps, freq="MS")
        )
        return pd.DataFrame({"التاريخ": future_idx, "الحالات المتوقعة": [max(0, base_i)] * len(future_idx)})

    X, y, use_lags = make_features(s, freq=("D" if freq == "D" else "M"))
    model = RandomForestRegressor(n_estimators=450, random_state=42)
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

    return pd.DataFrame({"التاريخ": future_idx, "الحالات المتوقعة": np.round(preds).astype(int)})


# =========================
# 6) فعلي سنوي + مقارنة فعلي×متوقع (ملف)
# =========================
def actual_yearly_counts(dff: pd.DataFrame) -> pd.DataFrame:
    x = dff.dropna(subset=["تاريخ انتهاء الخدمة"]).copy()
    x["السنة"] = x["تاريخ انتهاء الخدمة"].dt.year
    y = x.groupby("السنة").size().reset_index(name="الاستقالات الفعلية").sort_values("السنة").reset_index(drop=True)
    y["السنة"] = y["السنة"].astype(int)
    return y

def compare_actual_vs_file_forecast(actual_df: pd.DataFrame, file_fc: pd.DataFrame) -> pd.DataFrame:
    if actual_df is None or actual_df.empty:
        return pd.DataFrame()
    out = actual_df.merge(file_fc, on="السنة", how="left")
    out["الاستقالات المتوقعة (ملف)"] = out["الاستقالات المتوقعة (ملف)"].fillna(0).astype(int)
    out["الفرق (فعلي-متوقع)"] = out["الاستقالات الفعلية"] - out["الاستقالات المتوقعة (ملف)"]
    return out


# =========================
# 7) auto_chart (يرد + يرسم) — السنوي من الملف
# =========================
def auto_chart(dff_base: pd.DataFrame, q: str, top_n=10, sidebar_info=""):
    qn = norm_ar(q)
    ref_today = get_ref_today(dff_base)

    dff = apply_question_entity_filters(dff_base.copy(), q)

    dr = get_date_range_from_question(q, ref_today)
    if dr:
        start, end = dr
        end_inclusive = end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        dff = dff[(dff["تاريخ انتهاء الخدمة"] >= start) & (dff["تاريخ انتهاء الخدمة"] <= end_inclusive)]
        range_text = f"📅 الفترة: من **{start.date()}** إلى **{end.date()}** (مرجع: {ref_today.date()})"
    else:
        range_text = f"📅 الفترة: حسب فلاتر السايدبار (مرجع: {ref_today.date()})"

    def footer(msg: str):
        parts = [msg, range_text]
        if sidebar_info:
            parts.append(sidebar_info)
        return "\n\n".join(parts)

    if dff.empty:
        return footer("⚠️ لا توجد بيانات مطابقة للسؤال/الفلاتر."), None, None

    # (A) أحدث سجلات جدول (بدون أعمدة مفقودة)
    if ("احدث" in qn or "اخر" in qn or "latest" in qn) and ("جدول" in qn or "table" in qn or "سجلات" in qn):
        wanted_cols = ["الجهة", "الجنسية", "تاريخ انتهاء الخدمة", "سبب الاستقالة"]
        safe_cols = [c for c in wanted_cols if c in dff.columns]
        tbl = dff.sort_values("تاريخ انتهاء الخدمة", ascending=False).head(10)[safe_cols]
        return footer("🕒 أحدث 10 سجلات:"), None, tbl

    # (B) عدد/إجمالي
    if any(k in qn for k in ["كم", "عدد", "اجمالي", "إجمالي", "المجموع", "total"]):
        return footer(f"📊 **عدد الاستقالات = {len(dff):,}**"), None, None

    # (C) توزيع
    if any(k in qn for k in ["توزيع", "نسب", "نسبة", "pie", "دائره", "دائرة"]):
        if "جنس" in qn:
            vc = dff["الجنسية"].value_counts().head(top_n).rename_axis("الجنسية").reset_index(name="العدد")
            fig = px.pie(vc, values="العدد", names="الجنسية", hole=0.45, title=f"توزيع الجنسيات (Top {top_n})")
            fig.update_traces(textinfo="percent+label")
            return footer("🌍 توزيع الجنسيات"), fig, vc

        if any(k in qn for k in ["جهه", "جهة", "الجهة", "اداره", "إدارة"]):
            vc = dff["الجهة"].value_counts().head(top_n).rename_axis("الجهة").reset_index(name="العدد")
            fig = px.pie(vc, values="العدد", names="الجهة", hole=0.45, title=f"توزيع الجهات (Top {top_n})")
            fig.update_traces(textinfo="percent+label")
            return footer("🏢 توزيع الجهات"), fig, vc

    # (D) أكثر / أقل
    if any(k in qn for k in ["اكثر", "الأكثر", "اعلى", "أعلى", "top", "اكبر", "أكبر"]):
        if "جنس" in qn:
            vc = dff["الجنسية"].value_counts().head(top_n).rename_axis("الجنسية").reset_index(name="العدد")
            fig = px.bar(vc, x="الجنسية", y="العدد", text_auto=True, title=f"أكثر الجنسيات (Top {top_n})")
            return footer("🌍 أكثر الجنسيات"), fig, vc

        vc = dff["الجهة"].value_counts().head(top_n).rename_axis("الجهة").reset_index(name="العدد")
        fig = px.bar(vc, x="الجهة", y="العدد", text_auto=True, title=f"أكثر الجهات (Top {top_n})")
        fig.update_layout(xaxis_tickangle=-35)
        return footer("🏢 أكثر الجهات"), fig, vc

    if any(k in qn for k in ["اقل", "الأقل", "ادنى", "أدنى", "bottom"]):
        if "جنس" in qn:
            vc = dff["الجنسية"].value_counts().tail(top_n).rename_axis("الجنسية").reset_index(name="العدد")
            fig = px.bar(vc, x="الجنسية", y="العدد", text_auto=True, title=f"أقل الجنسيات (Bottom {top_n})")
            return footer("📉 أقل الجنسيات"), fig, vc

        vc = dff["الجهة"].value_counts().tail(top_n).rename_axis("الجهة").reset_index(name="العدد")
        fig = px.bar(vc, x="الجهة", y="العدد", text_auto=True, title=f"أقل الجهات (Bottom {top_n})")
        fig.update_layout(xaxis_tickangle=-35)
        return footer("📉 أقل الجهات"), fig, vc

    # (E) ترند
    if any(k in qn for k in ["ترند", "اتجاه", "عبر الزمن", "trend", "line", "خطي", "خط"]):
        monthly = any(k in qn for k in ["شهري", "شهر"])
        freq = "M" if monthly else "D"
        ts = make_series(dff, freq=freq).reset_index()
        ts.columns = ["التاريخ", "العدد"]
        fig = px.line(ts, x="التاريخ", y="العدد", markers=True, title=("الاتجاه شهريًا" if monthly else "الاتجاه يوميًا"))
        return footer("📈 الاتجاه عبر الزمن"), fig, ts.tail(200)

    # (F) توقع — السنوي من ملف التوقع (توحيد)
    if any(k in qn for k in ["توقع", "يتوقع", "تنبؤ", "يتنبا", "القادم", "الجاي"]):
        years = sorted({int(y) for y in re.findall(r"(20\d{2})", qn)})

        # إذا ذكر سنة/سنوات: نجيب من ملف التوقع (نفس اليسار)
        if years:
            if not file_yearly_fc.empty:
                preds = file_yearly_fc[file_yearly_fc["السنة"].isin(years)].copy()
                if not preds.empty:
                    fig = px.bar(preds, x="السنة", y="الاستقالات المتوقعة (ملف)", text_auto=True, title="توقع سنوي (من ملف التوقع)")
                    return footer(f"🔮 توقع سنوي من الملف للسنوات: {', '.join(map(str, years))}"), fig, preds

            # fallback إذا الملف ما يغطي السنوات
            return footer("⚠️ ملف التوقع لا يحتوي على هذه السنوات."), None, file_yearly_fc

        # شهري
        if any(k in qn for k in ["شهري", "شهر", "اشهر", "شهور"]):
            m = re.search(r"(\d+)\s*(شهر|اشهر|شهور)", qn)
            steps = int(m.group(1)) if m else 6
            fc = forecast_time(dff, steps=steps, freq="M")
            fig = px.bar(fc, x="التاريخ", y="الحالات المتوقعة", text_auto=True, title=f"توقع الاستقالات ({steps} أشهر)")
            return footer("🔮 توقع شهري"), fig, fc

        # يومي
        m = re.search(r"(\d+)\s*(يوم|ايام)", qn)
        steps = int(m.group(1)) if m else 30
        fc = forecast_time(dff, steps=steps, freq="D")
        fig = px.area(fc, x="التاريخ", y="الحالات المتوقعة", title=f"توقع الاستقالات ({steps} يوم)")
        return footer("🔮 توقع يومي"), fig, fc

    # (G) fallback: لو السؤال غير واضح -> ترند شهري افتراضي
    ts = make_series(dff, freq="M").reset_index()
    ts.columns = ["التاريخ", "العدد"]
    fig = px.line(ts, x="التاريخ", y="العدد", markers=True, title="ترند شهري (افتراضي)")
    msg = "ℹ️ ما فهمت صيغة السؤال بالكامل، فعرّضت لك **ترند شهري افتراضي**. جرّبي: (توزيع الجنسيات) / (أكثر جهة) / (توقع 30 يوم) / (توقع 2026)."
    return footer(msg), fig, ts.tail(200)


# =========================
# 8) Sidebar
# =========================
with st.sidebar:
    st.markdown("<h2 style='color:#00F5FF'>⚙️ لوحة التحكم</h2>", unsafe_allow_html=True)

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

    # ---- ملف التوقع (أسفل يسار)
    st.markdown("<div style='height: 28vh;'></div>", unsafe_allow_html=True)
    st.markdown("### 📄 ملف التوقع (لوحده)")

    if file_yearly_fc.empty:
        st.info("ملف التوقعات غير موجود أو أعمدته غير صحيحة.")
    else:
        st.metric("إجمالي المتوقع (من الملف)", int(file_yearly_fc["الاستقالات المتوقعة (ملف)"].sum()))
        fig_f = px.bar(file_yearly_fc, x="السنة", y="الاستقالات المتوقعة (ملف)", text_auto=True, title="التوقع السنوي (من الملف)")
        st.plotly_chart(fig_f, use_container_width=True)
        st.dataframe(file_yearly_fc, use_container_width=True)

    st.markdown("""
        <div class="sidebar-signature">
            <p style="color:#94A3B8;font-size:0.85rem;margin-bottom:4px;">إعداد</p>
            <p style="color:#00F5FF;font-size:1.5rem;font-weight:900;margin:0;">دلال حكمي</p>
            <p style="color:#475569;font-size:0.85rem;margin-top:4px;">dalal3021@gmail.com</p>
        </div>
    """, unsafe_allow_html=True)


# =========================
# 9) فلاتر السايدبار
# =========================
dff_sidebar = apply_sidebar_filters(df, date_range, dept_sel, nat_sel)

sidebar_info = " | ".join([
    f"🎛️ فلاتر السايدبار: الفترة ({date_range[0]} → {date_range[1]})",
    "الجهة: " + (", ".join(dept_sel[:3]) + ("…" if len(dept_sel) > 3 else "") if dept_sel else "كل الجهات"),
    "الجنسية: " + (", ".join(nat_sel[:3]) + ("…" if len(nat_sel) > 3 else "") if nat_sel else "كل الجنسيات"),
])


# =========================
# 10) Tabs
# =========================
tab1, tab2, tab3, tab4 = st.tabs(["📊 نظرة عامة", "📈 الاتجاهات", "🔮 التوقعات", "🤖 اسألني"])

with tab1:
    st.markdown("<h1>نظرة عامة</h1>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي الاستقالات", f"{len(dff_sidebar):,}")
    c2.metric("عدد الجهات", int(dff_sidebar["الجهة"].nunique()) if not dff_sidebar.empty else 0)
    c3.metric("عدد الجنسيات", int(dff_sidebar["الجنسية"].nunique()) if not dff_sidebar.empty else 0)

    if dff_sidebar.empty:
        st.info("لا توجد بيانات ضمن الفلاتر الحالية.")
    else:
        colA, colB = st.columns(2)
        with colA:
            nat_counts = dff_sidebar["الجنسية"].value_counts().head(top_n).rename_axis("الجنسية").reset_index(name="العدد")
            fig = px.pie(nat_counts, values="العدد", names="الجنسية", hole=0.45, title=f"Top {top_n} جنسيات")
            fig.update_traces(textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

        with colB:
            dept_counts = dff_sidebar["الجهة"].value_counts().head(top_n).rename_axis("الجهة").reset_index(name="العدد")
            fig = px.bar(dept_counts, x="الجهة", y="العدد", text_auto=True, title=f"Top {top_n} جهات")
            fig.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

        top_dept = dff_sidebar["الجهة"].mode().iloc[0] if not dff_sidebar["الجهة"].mode().empty else "غير محدد"
        st.markdown("### 💡 توصيات", unsafe_allow_html=True)
        st.markdown(f'<div class="rec-box">🚀 تعزيز برامج الاستبقاء داخل: {top_dept}</div>', unsafe_allow_html=True)
        st.markdown('<div class="rec-box">📈 تحليل أسباب الاستقالة وتحسين تجربة الموظف</div>', unsafe_allow_html=True)

with tab2:
    st.markdown("<h1>الاتجاهات</h1>", unsafe_allow_html=True)

    if dff_sidebar.empty:
        st.info("لا توجد بيانات ضمن الفلاتر الحالية.")
    else:
        gran = st.radio("الدقة الزمنية", ["يومي", "شهري"], horizontal=True)
        freq = "M" if gran == "شهري" else "D"
        ts = make_series(dff_sidebar, freq=freq).reset_index()
        ts.columns = ["التاريخ", "العدد"]
        fig = px.line(ts, x="التاريخ", y="العدد", markers=True, title=f"الاتجاه ({gran})")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ts.tail(120), use_container_width=True)

with tab3:
    st.markdown("<h1>التوقعات</h1>", unsafe_allow_html=True)

    if dff_sidebar.empty:
        st.info("لا توجد بيانات ضمن الفلاتر الحالية.")
    else:
        mode = st.radio("نوع التوقع", ["يومي (30 يوم)", "شهري (6 أشهر)", "سنوي (من الملف 2026-2028)", "مقارنة فعلي × متوقع (سنوي)"], horizontal=True)

        if mode.startswith("يومي"):
            fc = forecast_time(dff_sidebar, steps=30, freq="D")
            fig = px.area(fc, x="التاريخ", y="الحالات المتوقعة", title="توقع الاستقالات (30 يوم)")
            st.metric("إجمالي المتوقع", int(fc["الحالات المتوقعة"].sum()))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(fc, use_container_width=True)

        elif mode.startswith("شهري"):
            fc = forecast_time(dff_sidebar, steps=6, freq="M")
            fig = px.bar(fc, x="التاريخ", y="الحالات المتوقعة", text_auto=True, title="توقع الاستقالات (6 أشهر)")
            st.metric("إجمالي المتوقع", int(fc["الحالات المتوقعة"].sum()))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(fc, use_container_width=True)

        elif mode.startswith("سنوي"):
            if file_yearly_fc.empty:
                st.warning("ملف التوقع غير جاهز.")
            else:
                yrs = [2026, 2027, 2028]
                preds = file_yearly_fc[file_yearly_fc["السنة"].isin(yrs)].copy()
                fig = px.bar(preds, x="السنة", y="الاستقالات المتوقعة (ملف)", text_auto=True, title="توقع سنوي (من الملف)")
                st.metric("إجمالي المتوقع (3 سنوات)", int(preds["الاستقالات المتوقعة (ملف)"].sum()))
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(preds, use_container_width=True)

        else:
            act = actual_yearly_counts(dff_sidebar)
            cmp_df = compare_actual_vs_file_forecast(act, file_yearly_fc)

            if cmp_df.empty:
                st.warning("لا توجد بيانات للمقارنة.")
            else:
                long = cmp_df.melt(id_vars="السنة",
                                   value_vars=["الاستقالات الفعلية", "الاستقالات المتوقعة (ملف)"],
                                   var_name="النوع", value_name="العدد")
                fig = px.line(long, x="السنة", y="العدد", color="النوع", markers=True, title="مقارنة فعلي × متوقع (من الملف)")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(cmp_df, use_container_width=True)

with tab4:
    st.markdown("<h1>اسألني</h1>", unsafe_allow_html=True)
    st.markdown("<p class='small-muted'>اكتبي سؤال… النظام يرد ويطلع رسم بياني تلقائيًا.</p>", unsafe_allow_html=True)

    q = st.chat_input("مثال: ترند شهري | توزيع الجنسيات | أكثر جهة | توقع 30 يوم | توقع 2026 | أحدث سجلات جدول")

    if q:
        with st.chat_message("assistant"):
            try:
                msg, fig, table = auto_chart(dff_sidebar, q, top_n=top_n, sidebar_info=sidebar_info)
                st.write(msg)
                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True)
                if table is not None:
                    st.dataframe(table, use_container_width=True)
            except Exception as e:
                st.error("صار خطأ أثناء تحليل السؤال، لكن التطبيق شغال.")
                st.code(str(e))
    else:
        st.markdown("""
        <div class="welcome-card">
            <h1 style="margin-bottom: 14px;">اسألني</h1>
            <p style="color:#CBD5E1;font-size:1.15rem;line-height:1.9;max-width:760px;margin:0 auto;">
            أمثلة:
            <br><b>كم استقالوا آخر 3 شهور</b> — <b>توزيع الجنسيات</b> — <b>أكثر جهة</b> — <b>ترند شهري</b>
            <br><b>توقع 30 يوم</b> — <b>توقع 6 أشهر</b> — <b>توقع 2026</b> — <b>أحدث سجلات جدول</b>
            <br>فلترة داخل السؤال: <b>جهة: الموارد البشرية</b> أو <b>جنسية: سعودي</b>
            </p>
        </div>
        """, unsafe_allow_html=True)

if dff_sidebar.empty:
    st.info("لا توجد بيانات ضمن فلاتر السايدبار الحالية. وسّعي الفترة أو أزيلي بعض الفلاتر.")

st.markdown("<div style='text-align:center;color:#94A3B8;margin-top:10px;'>© Workforce Intelligence Platform | Dalal Hakami</div>", unsafe_allow_html=True)
