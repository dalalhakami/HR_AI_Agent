# train_yearly_model.py
import os
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ========= إعدادات =========
DATA_FILE = "توقعات الاستقالات وتحليل البيانات.xlsx"     # اسم ملف البيانات
DATE_COL = "تاريخ انتهاء الخدمة"                  # عمود التاريخ
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "resign_yearly_rf.joblib")

FUTURE_YEARS_DEFAULT = (2026, 2027, 2028)


# ========= تجهيز البيانات سنويًا =========
def yearly_counts(df: pd.DataFrame) -> pd.Series:
    """
    يرجّع سلسلة زمنية سنوية (عدد الاستقالات لكل سنة).
    نستخدم 'YE' (Year-End) لتجنب تحذيرات Pandas.
    """
    s = (
        df.dropna(subset=[DATE_COL])
          .set_index(DATE_COL)
          .resample("YE")
          .size()
          .rename("resignations")
    )
    return s


def make_year_features(series: pd.Series, n_lags: int = 2):
    """
    ميزات بسيطة للتنبؤ السنوي:
    - year
    - lags (آخر سنة/سنتين...)
    """
    d = pd.DataFrame({
        "year": series.index.year,
        "y": series.values
    })

    for lag in range(1, n_lags + 1):
        d[f"lag_{lag}"] = d["y"].shift(lag)

    d = d.dropna()
    X = d.drop(columns=["y"])
    y = d["y"]
    return X, y, n_lags


# ========= تدريب وتقييم =========
def train_and_evaluate(series: pd.Series):
    """
    تدريب مع تقييم بسيط: آخر سنة (Holdout) للاختبار.
    """
    X, y, n_lags = make_year_features(series, n_lags=2)

    if len(X) < 3:
        raise ValueError(
            "عدد السنوات غير كافٍ للتدريب والتقييم. "
            "يفضّل توفر 4 سنوات فأكثر."
        )

    # Split: آخر صف للاختبار
    X_train, X_test = X.iloc[:-1], X.iloc[-1:]
    y_train, y_test = y.iloc[:-1], y.iloc[-1:]

    model = RandomForestRegressor(
        n_estimators=800,
        random_state=42
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, pred)
    rmse = mean_squared_error(y_test, pred, squared=False)

    return model, n_lags, float(mae), float(rmse)


# ========= Forecast سنوات قادمة =========
def forecast_years(model, series: pd.Series, years, n_lags: int = 2) -> pd.DataFrame:
    """
    تنبؤ Roll-forward سنة بسنة.
    نضيف التوقعات للسلسلة حتى نستخدمها كـ lag للسنوات التالية.
    """
    hist = series.copy()
    out = []

    for year in years:
        row = {"year": year}

        # lags من آخر قيم موجودة (حقيقية أو توقعات سابقة)
        for lag in range(1, n_lags + 1):
            row[f"lag_{lag}"] = float(hist.iloc[-lag]) if len(hist) >= lag else 0.0

        X_future = pd.DataFrame([row])
        yhat = float(model.predict(X_future)[0])
        yhat = max(0.0, yhat)  # ضمان عدم السالب

        out.append({
            "السنة": int(year),
            "الاستقالات المتوقعة": int(round(yhat))
        })

        # أضفها للسلسلة كتاريخ نهاية السنة
        hist.loc[pd.Timestamp(year=year, month=12, day=31)] = yhat

    return pd.DataFrame(out)


# ========= تشغيل كامل =========
def main():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(
            f"لم يتم العثور على الملف: {DATA_FILE}\n"
            "تأكدي أن ملف Excel موجود في نفس مجلد السكربت."
        )

    # قراءة البيانات
    df = pd.read_excel(DATA_FILE, engine="openpyxl")
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

    # إنشاء السلسلة السنوية
    series = yearly_counts(df)

    if series.empty:
        raise ValueError("لا توجد بيانات تاريخ صالحة في العمود المحدد.")

    print("✅ السنوات الموجودة في البيانات:", series.index.year.tolist())
    print(series)

    # تدريب + تقييم
    model, n_lags, mae, rmse = train_and_evaluate(series)
    print(f"\n📌 التقييم (آخر سنة Holdout): MAE={mae:.2f} | RMSE={rmse:.2f}")

    # حفظ المودل
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(
        {"model": model, "series": series, "n_lags": n_lags, "date_col": DATE_COL},
        MODEL_PATH
    )
    print(f"✅ تم حفظ النموذج في: {MODEL_PATH}")

    # توقع 2026-2028
    pred_df = forecast_years(model, series, FUTURE_YEARS_DEFAULT, n_lags=n_lags)
    print("\n🔮 توقع الاستقالات للأعوام القادمة:")
    print(pred_df)


if __name__ == "__main__":
    main()
