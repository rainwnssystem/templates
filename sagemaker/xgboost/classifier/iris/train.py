import argparse, json, os, zipfile
import numpy as np
import pandas as pd
import joblib
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import os, subprocess


MODEL_FILE = "xgboost-model.json"
LABEL_ENCODER_FILE = "label_encoder.joblib"

device = "cuda" if os.environ.get("SM_NUM_GPUS", "0") != "0" else "cpu"


def compress(channel_dir: str) -> pd.DataFrame:
    with zipfile.ZipFile(f'{channel_dir}/dataset.zip') as zf:
        zf.extractall(f'{channel_dir}/')


# ── Train ──

def train(args):

    # ── data load ──
    compress(args.train)
    print(subprocess.run(["ls", "-alR", args.train], capture_output=True, text=True).stdout)
    df = pd.read_csv(f'{args.train}/Iris.csv')
    print("shape:", df.shape)
    print("nulls:\n", df.isnull().sum())

    # Id, Species 컬럼 제거 → feature matrix
    x = df.drop(labels=["Id", "Species"], axis=1).values
    y = df["Species"].values

    # XGBoost 는 수치 라벨이 필요 — LabelEncoder
    le = LabelEncoder()
    y = le.fit_transform(y)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42
    )

    # ── train ──
    model = XGBClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        device=device,
        random_state=42,
    )
    model.fit(x_train, y_train)

    # ── predict ──
    y_pred = model.predict(x_test)
    acc = accuracy_score(y_test, y_pred)
    print("acc:", acc)
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    # ── inference sample ──
    sample = np.array([[5.1, 3.5, 1.4, 0.2]])
    pred_label = le.inverse_transform(model.predict(sample))[0]
    print("sample prediction:", pred_label)

    # ── save artifact for endpoint ──
    # 모델 가중치 + LabelEncoder 둘 다 model_dir 안에 놓아야 추론 시 라벨 복구가 가능하다.
    os.makedirs(args.model_dir, exist_ok=True)
    model.save_model(os.path.join(args.model_dir, MODEL_FILE))
    joblib.dump(le, os.path.join(args.model_dir, LABEL_ENCODER_FILE))
    print("artifacts saved to:", args.model_dir)


# ── Inference ──

def model_fn(model_dir):
    model = XGBClassifier()
    model.load_model(os.path.join(model_dir, MODEL_FILE))
    le = joblib.load(os.path.join(model_dir, LABEL_ENCODER_FILE))
    return {"model": model, "label_encoder": le}


def input_fn(request_body, content_type="application/json"):
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    payload = json.loads(request_body)
    # {"instance": [5.1, 3.5, 1.4, 0.2]} 또는 {"instance": [[5.1, 3.5, 1.4, 0.2], ...]}
    arr = np.array(payload["instance"], dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr


def predict_fn(input_data, artifacts):
    model = artifacts["model"]
    le    = artifacts["label_encoder"]
    raw   = model.predict(input_data)
    return le.inverse_transform(raw).tolist()


def output_fn(prediction, accept="application/json"):
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")
    return json.dumps({"class_name": prediction}), accept


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n_estimators", type=int, default=100)
    p.add_argument("--max_depth", type=int, default=3)
    p.add_argument("--learning_rate", type=float, default=0.1)
    p.add_argument(
        "--train",
        type=str,
        default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"),
    )
    p.add_argument(
        "--model-dir",
        type=str,
        default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"),
    )
    args = p.parse_args()
    train(args)