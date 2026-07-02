import argparse, json, os, zipfile
import numpy as np
import pandas as pd
import joblib
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import base64
from PIL import Image
import io


def compress(channel_dir: str) -> pd.DataFrame:
    with zipfile.ZipFile(f'{channel_dir}/dataset.zip') as zf:
        zf.extractall(f'{channel_dir}/')


# ── Train ──

def train(args):

    # ── data load ──
    compress(args.train)

    train_data = pd.read_csv(f'{args.train}/mnist_train.csv')
    test_data = pd.read_csv(f'{args.train}/mnist_test.csv')

    y      = train_data['label']
    x      = train_data.drop('label', axis=1)
    y_test = test_data['label']
    x_test = test_data.drop('label', axis=1)

    for col in x.select_dtypes(include='object').columns:
        x[col] = x[col].astype('category')
        x_test[col] = x_test[col].astype('category')

    # XGBoost 는 수치 라벨이 필요 — LabelEncoder
    le = LabelEncoder()
    y = le.fit_transform(y)

    # ── train ──
    model = XGBClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        tree_method="hist",
        enable_categorical=True,
        random_state=42,
    )
    model.fit(x, y)

    # ── predict ──
    y_pred = model.predict(x_test)
    acc = accuracy_score(y_test, y_pred)
    print("acc:", acc)
    print(classification_report(y_test, y_pred))

    # ── save artifact for endpoint ──
    # 모델 가중치 + LabelEncoder 둘 다 model_dir 안에 놓아야 추론 시 라벨 복구가 가능하다.
    os.makedirs(args.model_dir, exist_ok=True)
    model.save_model(os.path.join(args.model_dir, 'xgboost-model.json'))
    joblib.dump(le, os.path.join(args.model_dir, 'label_encoder.joblib'))
    print("artifacts saved to:", args.model_dir)


# ── Inference ──

def model_fn(model_dir):
    model = XGBClassifier()
    model.load_model(os.path.join(model_dir, 'xgboost-model.json'))
    le = joblib.load(os.path.join(model_dir, 'label_encoder.joblib'))
    return {"model": model, "label_encoder": le}


def input_fn(request_body, content_type="application/json"):
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    payload = json.loads(request_body)

    b64 = base64.b64decode(payload['image'])
    img = Image.open(io.BytesIO(b64))
    img = img.convert('L').resize((28, 28))  # L==grayscale, 28x28(MNIST)

    # Flattening
    arr = np.array(img, dtype=np.float32).reshape(1, 784)  # 28 * 28 = 784
    return pd.DataFrame(arr, columns=[f'{r}x{c}' for r in range(1, 29) for c in range(1, 29)])


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