"""Train the baseline civic-issue text classifier from ml/civic_issues.csv.
Run: python train_model.py
This starter dataset is illustrative; replace/expand it with reviewed, labelled local reports.
"""
from pathlib import Path
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "ml" / "civic_issues.csv"
OUT = ROOT / "ml" / "civic_model.joblib"

df = pd.read_csv(DATA).dropna(subset=["description", "category"])
X, y = df["description"].astype(str), df["category"].astype(str)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)
model = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)),
    ("classifier", LogisticRegression(max_iter=1500, class_weight="balanced")),
])
model.fit(X_train, y_train)
pred = model.predict(X_test)
print(f"Holdout accuracy on small starter dataset: {accuracy_score(y_test, pred):.3f}")
print(classification_report(y_test, pred, zero_division=0))
joblib.dump(model, OUT)
print(f"Saved model: {OUT}")
print("NOTE: This is a demonstration baseline, not a validated municipal decision system.")
