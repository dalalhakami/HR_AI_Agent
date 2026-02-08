import pandas as pd
import numpy as np
from fastapi import FastAPI
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import PoissonRegressor

app = FastAPI()

# --- تحميل البيانات ---
DATA_PATH = "Resigned Report Date Range.xlsx"
df = pd.read_excel(DATA_PATH, engine="openpyxl")
df["تاريخ انتهاء الخدمة"] = pd.to_datetime(df["تاريخ انتهاء الخدمة"], errors="coerce")
df = df.dropna(subset=["تاريخ انتهاء الخدمة"]).copy()
df["year"] = df["تاريخ انتهاء الخدمة"].dt.year
df["month_num"] = df["تاريخ انتهاء الخدمة"].dt.month
df["month"] = df["تاريخ انتهاء الخدمة"].dt.to_period("M").dt.to_timestamp()

# --- محرك التحليل والحلول ---
def get_analysis_data(data):
    top_dept = data["الجهة"].mode()[0] if "الجهة" in data.columns else "غير محدد"
    saudi_ratio = (data["الجنسية"].str.contains("سعودي").sum() / len(data)) * 100
    return {
        "الأعلى استقالة": top_dept,
        "نسبة توطين الاستقالات": f"{saudi_ratio:.1f}%",
        "إجمالي الحالات": len(data)
    }

def get_solutions(analysis):
    return [
        f"🚀 **حل مقترح:** دراسة بيئة العمل في قسم ({analysis['الأعلى استقالة']}) لتقليل التسرب.",
        "🎯 **مبادرة:** مراجعة خطط الاستبقاء للموظفين السعوديين لضمان الاستدامة.",
        "📅 **إجراء:** تفعيل نظام 'المقابلات الذكية' عند الاستقالة لرصد الأسباب بدقة."
    ]

@app.post("/chat")
def chat(req: dict):
    q = req.get("message", "").lower()
    
    if any(x in q for x in ["حلل", "تحليل", "اقتراح"]):
        results = get_analysis_data(df)
        solutions = get_solutions(results)
        return {"type": "analysis", "answer": results, "recommendations": solutions}
    
    elif any(x in q for x in ["توقع", "تنبؤ"]):
        # كود التوقع المبسط
        last = df["month"].max()
        future = pd.date_range(last, periods=7, freq="MS")[1:]
        preds = [{"الشهر": m.strftime('%Y-%m'), "التوقع": 5} for m in future] # قيم تجريبية
        return {"type": "forecast", "answer": preds}
    
    return {"type": "text", "answer": "أهلاً بك، اختر من الاقتراحات أو اسألني مباشرة."}