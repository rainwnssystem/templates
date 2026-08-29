# SageMaker Tabular Classification

CSV 데이터를 XGBoost로 분류하고 SageMaker Endpoint로 배포하는 템플릿이다.

- [`train.py`](./train.py): 전처리, 학습, Endpoint 코드
- [`estimator.ipynb`](./estimator.ipynb): 다운로드, S3 업로드, 학습, 배포

## 1. 데이터 다운로드

```python
%cd ~/SageMaker/

!curl -L "<DOWNLOAD_URL>" -o dataset.zip
!unzip -o dataset.zip -d dataset
!find dataset -type f
```

- `curl -L`: 리다이렉트된 다운로드 주소를 따라간다.
- `find`: 압축을 푼 뒤 실제 CSV 경로를 확인한다.

로그인이 필요한 사이트는 인증된 다운로드 URL이나 해당 사이트의 CLI를 사용한다. 토큰은 Notebook 코드에 직접 적지 않는다.

## 2. CSV 확인

```python
import pandas as pd

df = pd.read_csv("dataset/Iris.csv")
df.info()
display(df.head())
display(df.isnull().sum())
```

확인할 내용:

- target 컬럼
- ID처럼 제외할 컬럼
- 숫자형과 문자열 컬럼
- 헤더, 구분자, 인코딩
- 결측치

## 3. CSV 읽기

[`train.py`](./train.py)에서 실제 파일명으로 바꾼다.

```python
csv_path = os.path.join(train_dir, "Iris.csv")
df = pd.read_csv(csv_path)
```

헤더가 없는 CSV:

```python
df = pd.read_csv(
    csv_path,
    header=None,
    names=["feature_1", "feature_2", "target"],
)
```

`header=None`이 없으면 첫 번째 데이터 행이 컬럼명으로 처리된다.

TSV 또는 CP949 파일:

```python
df = pd.read_csv(csv_path, sep="\t", encoding="cp949")
```

## 4. 데이터셋별 전처리

필요한 처리는 `2. 데이터셋별 전처리` 블록에 직접 작성한다.

```python
df["city"] = df["city"].str.strip()

df["created_at"] = pd.to_datetime(df["created_at"])
df["created_year"] = df["created_at"].dt.year
df["created_month"] = df["created_at"].dt.month
df = df.drop(columns=["created_at"])
```

학습 전처리를 추가했다면 `predict_fn`에도 같은 처리를 추가한다. 학습과 Endpoint의 feature가 달라지면 예측할 수 없다.

## 5. Feature와 target 선택

Iris 기준:

```python
target_column = "Species"
drop_columns = ["Id"]

x = df.drop(columns=[target_column, *drop_columns])
y = df[target_column]
```

- `target_column`: 모델이 맞힐 정답
- `drop_columns`: ID, 이름, 데이터 누수 컬럼
- `x`: 모델 입력
- `y`: 모델 정답

다른 데이터셋에서는 실제 컬럼명으로 바꾼다.

## 6. One-hot encoding

```python
x = pd.get_dummies(
    x,
    dummy_na=True,
    dtype=float,
)
```

`pd.get_dummies()`는 문자열 컬럼을 자동으로 one-hot encoding하고 숫자형 컬럼은 그대로 둔다.

```text
city → city_Busan, city_Seoul, city_nan
```

- `dummy_na=True`: 문자열 결측치를 별도 `nan` 범주로 만든다.
- `dtype=float`: one-hot 값을 `0.0`, `1.0`으로 만든다.
- 숫자형 `NaN`: XGBoost가 직접 처리한다.

숫자로 저장된 범주형은 숫자형과 자동으로 구분할 수 없다. 필요한 컬럼만 전처리 블록에서 문자열로 바꾼다.

```python
df["region_code"] = df["region_code"].astype(str)
```

Endpoint에서도 동일하게 바꾼다.

```python
x["region_code"] = x["region_code"].astype(str)
```

## 7. Target과 데이터 분리

```python
label_encoder = LabelEncoder()
y = label_encoder.fit_transform(y)
```

`LabelEncoder`는 target을 `0`, `1`, `2`로 바꾼다. One-hot encoding은 feature에 적용하므로 역할이 다르다.

```python
x_train, x_test, y_train, y_test = train_test_split(
    x,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y,
)
```

- 80%는 학습에 사용한다.
- 20%는 평가에 사용한다.
- `stratify=y`는 클래스 비율을 비슷하게 유지한다.
- 클래스마다 데이터가 너무 적어 오류가 나면 `stratify=y`를 제거한다.

## 8. 모델 학습

```python
device = "cuda" if int(os.environ.get("SM_NUM_GPUS", "0")) > 0 else "cpu"

model = XGBClassifier(
    n_estimators=100,
    max_depth=5,
    learning_rate=0.05,
    device=device,
    random_state=42,
)
model.fit(x_train, y_train)
```

GPU가 있는 인스턴스면 `cuda`, 없으면 `cpu`를 사용한다.

## 9. 모델 저장

```python
metadata = {
    "label_encoder": label_encoder,
    "feature_columns": feature_columns,
    "model_columns": model_columns,
}

model.save_model(os.path.join(model_dir, "xgboost-model.json"))
joblib.dump(metadata, os.path.join(model_dir, "metadata.joblib"))
```

- `feature_columns`: Endpoint 요청에서 받을 원본 컬럼
- `model_columns`: one-hot encoding 후 XGBoost가 학습한 컬럼
- `metadata.joblib`: LabelEncoder와 두 컬럼 목록

`numeric_columns`, `categorical_columns`, 중앙값은 저장하지 않는다.

## 10. SageMaker 학습

```python
inputs = S3Uploader.upload(
    "dataset/Iris.csv",
    f"s3://{bucket}/sagemaker/dataset",
)
```

```python
estimator = XGBoost(
    entry_point="train.py",
    role=role,
    instance_type="ml.m5.large",
    instance_count=1,
    framework_version="3.0-5",
    output_path=f"s3://{bucket}/sagemaker/dataset/output/",
)

estimator.fit({"train": inputs})
```

Notebook의 로컬 파일은 별도 학습 인스턴스가 직접 읽을 수 없으므로 S3에 업로드한다.

## 11. Endpoint

배포:

```python
predictor = estimator.deploy(
    initial_instance_count=1,
    instance_type="ml.m5.large",
    endpoint_name="<ENDPOINT_NAME>",
)
```

요청에는 target과 제외 컬럼을 넣지 않는다.

```python
body = {
    "instances": [
        {
            "SepalLengthCm": 5.1,
            "SepalWidthCm": 3.5,
            "PetalLengthCm": 1.4,
            "PetalWidthCm": 0.2,
        }
    ]
}
```

`predict_fn`은 문자열 feature를 one-hot encoding한 뒤 `model_columns` 순서에 맞춘다.

```python
x = pd.get_dummies(x, dummy_na=True, dtype=float)
x = x.reindex(columns=metadata["model_columns"], fill_value=0)
```

호출:

```python
response = boto3.client("sagemaker-runtime").invoke_endpoint(
    EndpointName="<ENDPOINT_NAME>",
    ContentType="application/json",
    Body=json.dumps(body),
)
print(json.load(response["Body"]))
```

사용이 끝나면 Endpoint를 삭제한다. 삭제 전까지 인스턴스 비용이 발생한다.

```python
predictor.delete_endpoint(delete_endpoint_config=True)
predictor.delete_model()
```
