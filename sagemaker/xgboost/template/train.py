import json
import os

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


MODEL_FILE = "xgboost-model.json"
METADATA_FILE = "metadata.joblib"


def train():
    # 1. CSV 읽기
    train_dir = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
    model_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

    csv_path = os.path.join(train_dir, "Iris.csv")
    df = pd.read_csv(csv_path)

    # 헤더가 없거나 구분자·인코딩이 다르면 위 코드를 직접 바꾼다.
    # df = pd.read_csv(csv_path, header=None, names=["feature_1", "feature_2", "target"])
    # df = pd.read_csv(csv_path, sep="\t", encoding="cp949")

    print(df.head())
    df.info()
    print(df.isnull().sum())

    # 2. 데이터셋별 전처리
    # 필요한 처리를 이 블록에 직접 추가하거나 삭제한다.

    # df["city"] = df["city"].str.strip()

    # df["created_at"] = pd.to_datetime(df["created_at"])
    # df["created_year"] = df["created_at"].dt.year
    # df["created_month"] = df["created_at"].dt.month
    # df = df.drop(columns=["created_at"])

    # 숫자로 저장된 범주형은 문자열로 바꾸면 one-hot encoding된다.
    # df["region_code"] = df["region_code"].astype(str)

    # df = df[df["age"] >= 0]

    # 3. Feature와 target 선택
    target_column = "target"
    drop_columns = ["Id"]  # ID, 이름, 데이터 누수 컬럼

    x = df.drop(columns=[target_column, *drop_columns])
    y = df[target_column]
    feature_columns = x.columns.tolist()

    # 4. 문자열 feature를 one-hot encoding한다.
    # 숫자형 feature는 그대로 두고 NaN은 XGBoost가 직접 처리한다.
    x = pd.get_dummies(x, dummy_na=True, dtype=float)
    model_columns = x.columns.tolist()

    # 5. Target 변환 및 학습 데이터 분리
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(y)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    # 6. 모델 학습
    device = "cuda" if int(os.environ.get("SM_NUM_GPUS", "0")) > 0 else "cpu"
    print("device:", device)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.05,
        device=device,
        random_state=42,
    )
    model.fit(x_train, y_train)

    # 7. 평가
    prediction = model.predict(x_test)
    print("accuracy:", accuracy_score(y_test, prediction))

    # 8. 모델과 추론에 필요한 정보 저장
    metadata = {
        "label_encoder": label_encoder,
        "feature_columns": feature_columns,
        "model_columns": model_columns,
    }

    os.makedirs(model_dir, exist_ok=True)
    model.save_model(os.path.join(model_dir, MODEL_FILE))
    joblib.dump(metadata, os.path.join(model_dir, METADATA_FILE))


# 9. SageMaker Endpoint
def model_fn(model_dir):
    """Endpoint가 시작될 때 모델을 불러온다."""
    model = XGBClassifier()
    model.load_model(os.path.join(model_dir, MODEL_FILE))

    device = "cuda" if int(os.environ.get("SM_NUM_GPUS", "0")) > 0 else "cpu"
    model.set_params(device=device)

    metadata = joblib.load(os.path.join(model_dir, METADATA_FILE))
    metadata["model"] = model
    return metadata


def input_fn(request_body, content_type="application/json"):
    """JSON 요청을 DataFrame으로 바꾼다."""
    request = json.loads(request_body)
    return pd.DataFrame(request["instances"])


def predict_fn(input_data, metadata):
    """학습 때와 같은 전처리를 적용하고 예측한다."""

    # input_data가 [0, 0, 0, 0] 형태 일반 배열이라면, columns를 설정한다.
    # x = pd.DataFrame(input_data, columns=metadata["feature_columns"])

    x = input_data[metadata["feature_columns"]].copy()

    # 학습 코드의 2번에서 변환을 추가했다면 여기도 동일하게 추가한다.
    # x["region_code"] = x["region_code"].astype(str)

    # 학습 코드의 4번과 같은 one-hot encoding을 적용한다.
    x = pd.get_dummies(x, dummy_na=True, dtype=float)
    x = x.reindex(columns=metadata["model_columns"], fill_value=0)

    prediction = metadata["model"].predict(x)
    return metadata["label_encoder"].inverse_transform(prediction).tolist()


def output_fn(prediction, accept="application/json"):
    """예측 결과를 JSON으로 반환한다."""
    return json.dumps({"predictions": prediction}), "application/json"


if __name__ == "__main__":
    train()
