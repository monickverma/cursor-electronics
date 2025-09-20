# train.py
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from preprocess import X, y, encoders

# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Train RandomForest with balanced classes
model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    class_weight="balanced"
)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print("✅ Training complete | Accuracy:", round(acc, 3))

# Save model + encoders
bundle = {"model": model, "encoders": encoders}
joblib.dump(bundle, "internship_model.pkl")
print("💾 Model saved to internship_model.pkl")
