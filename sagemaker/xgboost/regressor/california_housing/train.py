import argparse, json, os, zipfile
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder


# def compress(channel_dir: str) -> pd.DataFrame:
#     with zipfile.ZipFile(f'{channel_dir}/dataset.zip') as zf:
#         zf.extractall(f'{channel_dir}/')


# ── Train ──

def train(args):

    # ── data load ──
    # compress(args.train)
    df = pd.read_csv(f'{args.train}/housing.csv')
    print("shape:", df.shape)
    print("nulls:\n", df.isnull().sum())

    df['total_bedrooms'].fillna(df['total_bedrooms'].mean(), inplace=True)
    df.drop('households', axis=1, inplace=True)
    df['average_rooms']=df['total_rooms']/df['population']
    df['average_bedrooms']=df['total_bedrooms']/df['population']
    df.drop('total_rooms',axis=1,inplace=True)
    df.drop('total_bedrooms',axis=1,inplace=True)

    label_encoder = LabelEncoder()
    df['ocean_proximity_encoded'] = label_encoder.fit_transform(df['ocean_proximity'])
    df.drop('ocean_proximity', axis=1, inplace=True)

    x = df.drop('housing_median_age', axis=1).values
    y = df['housing_median_age'].values

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42
    )

    # ── train ──
    model = XGBRegressor(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.lr,
        random_state=42,
    )
    model.fit(x_train, y_train)

    # ── predict ──
    y_pred = model.predict(x_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print("rmse:", rmse)
    print("mae:", mae)
    print("r2:", r2)

    # ── inference sample ──
    sample = np.array([[8.3252, 41.0, 6.9841, 1.0238, 322.0, 2.5556, 37.88, -122.23]])
    print("sample prediction:", float(model.predict(sample)[0]))

    # ── save artifact for endpoint ──
    os.makedirs(args.model_dir, exist_ok=True)
    model.save_model(os.path.join(args.model_dir, 'xgboost-model.json'))
    print("artifacts saved to:", args.model_dir)


# ── Inference ──

def model_fn(model_dir):
    model = XGBRegressor()
    model.load_model(os.path.join(model_dir, 'xgboost-model.json'))
    return {"model": model}


def input_fn(request_body, content_type="application/json"):
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    payload = json.loads(request_body)
    # {"instance": [8.3252, 41.0, ...]} 또는 {"instance": [[...], [...]]}
    # ['longitude', 'latitude', 'housing_median_age', 'population', 'median_income', 'median_house_value', 'ocean_proximity', 'average_rooms', 'average_bedrooms'] 순서 입력
    arr = np.array(payload["instance"], dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr


def predict_fn(input_data, artifacts):
    model = artifacts["model"]
    return model.predict(input_data).tolist()


def output_fn(prediction, accept="application/json"):
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")
    return json.dumps({"prediction": prediction}), accept


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n_estimators", type=int, default=100)
    p.add_argument("--max_depth", type=int, default=3)
    p.add_argument("--lr", type=float, default=0.1)
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