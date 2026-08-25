| `s3a://my-bucket/output/` | 코드 — `BUCKET_NAME` + `BUCKET_PATH`로 조립 |# Kinesis → S3 (Amazon Managed Service for Apache Flink, Java)

Kinesis Data Streams에서 JSON 레코드를 읽어 변환한 뒤 S3에 적재하는 템플릿.
코드는 `src/main/java/com/example/app/App.java` 한 파일이다.

```
Kinesis (JSON 문자열)  →  transform()  →  S3 (JSON Lines)
```

```
입력: {"user_id":"b8386cda-...","name":"Frank","timestamp":"2026-05-14T00:00:29.651361Z"}
출력: {"user_id":"b8386cda-...","name":"Frank","timestamp":"2026-05-14T00:00:29.651361Z","email":"Frank@test.com"}
```

새 과제에 재사용할 때 **손대는 곳은 상단 상수와 `transform()` 뿐이다.**

---

## 1. 설정 상수

```java
private static final String STREAM_ARN = "arn:aws:kinesis:us-east-1:<ACCOUNT_ID>:stream/<STREAM_NAME>";
private static final String BUCKET_NAME = "<S3_BUCKET_NAME>";
private static final String BUCKET_PATH = "output";
private static final String INIT_POSITION = "LATEST";
```

- `STREAM_ARN` — 읽어올 스트림. **리전과 계정은 이 ARN에서 자동으로 추출**되므로 따로 설정할 필요가 없다.
- `BUCKET_NAME` / `BUCKET_PATH` — 출력 버킷 이름과 접두사. 코드가 `s3a://<name>/<path>`로 조립한다. 스킴이 `s3a://`인 이유는, Flink의 S3 파일시스템 두 개(`flink-s3-fs-presto`, `flink-s3-fs-hadoop`) 중 FileSink를 지원하는 것이 hadoop 쪽뿐이기 때문이다.
- `INIT_POSITION` — 어디부터 읽을지. `LATEST`(잡 시작 이후 들어온 것만) 또는 `TRIM_HORIZON`(스트림에 남아 있는 것부터 전부). 재처리 테스트에는 `TRIM_HORIZON`.

```java
Map<String, Properties> properties = KinesisAnalyticsRuntime.getApplicationProperties();
Properties inputProperties = properties.getOrDefault("InputStream0", new Properties());
Properties bucketProperties = properties.getOrDefault("bucket", new Properties());
```

MSF Console의 **Runtime properties**에 아래 그룹을 만들면 상수를 덮어쓴다. JAR을 다시 빌드하지 않고 값을 바꿀 수 있다.
그룹 ID와 키 이름은 AWS 공식 예제(aws-samples/amazon-managed-service-for-apache-flink-examples)의 `KinesisConnectors`, `S3Sink`와 같은 이름을 쓴다.

| Group ID | Key | 값 예시 |
| --- | --- | --- |
| `InputStream0` | `stream.arn` | `arn:aws:kinesis:us-east-1:123456789012:stream/wsi-stream` |
| `InputStream0` | `source.init.position` | `LATEST` |
| `bucket` | `name` | `my-bucket` — 버킷 **이름만**, 스킴·슬래시 없이 |
| `bucket` | `path` | `output` |

그룹 ID와 키는 **대소문자를 구분한다.** 이름은 MSF가 정하는 것이 아니라 애플리케이션 코드가 읽는 문자열이므로, 코드를 고치면 무엇이든 쓸 수 있다.
**런타임 속성은 선택사항이다.** 그룹을 안 만들면 MSF에서도 로컬에서도 위 상수가 그대로 쓰인다. AWS 문서(docs.aws.amazon.com)의 S3 예제처럼 값을 코드에 박아 쓰는 방식과 같다.

실행 시 앱이 어떤 값을 쓰는지 로그에 남고, 버킷 이름이 플레이스홀더면 바로 실패한다.

```java
LOG.info("config: stream.arn={} s3.path={} source.init.position={}", streamArn, s3Path, initPosition);
if (bucketName.contains("<")) {
    throw new IllegalArgumentException("bucket name is not configured: " + bucketName);
}
```

버킷 이름이 비면 Hadoop 계층에서 `bucket is null/empty`라는 알아보기 힘든 예외가 나기 때문에, 앞단에서 막는다.

---

## 2. 변환 — `transform()`

```java
private static ObjectNode transform(ObjectNode record) {
    record.put("email", record.path("name").asText() + "@test.com");
    return record;
}
```

레코드 1건을 받아 고쳐서 돌려준다. **과제가 바뀌면 이 메서드 본문만 다시 쓴다.**

- 인자 `record`는 JSON 객체 트리다. POJO 클래스를 선언하지 않으므로 입력에 모르는 필드가 있어도 그대로 보존되고, 필드가 늘어도 코드를 고칠 필요가 없다.
- 반환값이 `null`이면 그 레코드는 S3에 쓰이지 않고 버려진다(필터링).

### Jackson 치트시트

| 목적 | 코드 |
| --- | --- |
| 값 읽기 | `record.path("name").asText()` — 키가 없으면 `""`. `asInt()` / `asLong()` / `asDouble()` / `asBoolean()` |
| 중첩 값 읽기 | `record.at("/user/profile/id").asText()` |
| 키 존재 확인 | `record.has("name")` |
| 추가·수정 | `record.put("key", "값")` — 숫자·불리언은 따옴표 없이 들어간다 |
| 중첩 객체 | `record.putObject("obj").put("k", "v")` |
| 배열 | `record.putArray("tags").add("a").add("b")` |
| 이름 변경 | `JsonNode v = record.remove("old"); if (v != null) record.set("new", v);` |
| 삭제 | `record.remove("key")` |
| 지정한 키만 남기기 | `record.retain("user_id", "email")` |
| 레코드 버리기 | `if (조건) return null;` |

`path()`는 키가 없어도 예외 대신 빈 값을 돌려준다. `get()`은 `null`을 돌려주므로 바로 이어 쓰면 NPE가 난다.

집계(`keyBy` + window)나 조인처럼 필드를 타입 있게 오래 들고 다녀야 하는 단계가 생기면, 그 구간만 POJO로 바꾸는 편이 낫다. 스트림 타입 자체를 `ObjectNode`로 만들면 Flink가 Kryo로 직렬화해 느려지고 상태 스키마 진화도 막힌다.

---

## 3. Source

```java
KinesisStreamsSource<String> source = KinesisStreamsSource.<String>builder()
        .setStreamArn(streamArn)
        .setSourceConfig(sourceConfig)
        .setDeserializationSchema(new SimpleStringSchema())
        .build();
```

`SimpleStringSchema`는 Kinesis 레코드의 바이트를 UTF-8 문자열로만 바꾼다. **여기서는 JSON을 파싱하지 않는다.** 스트림 타입이 `String`이라 스키마 클래스가 필요 없다.

`KinesisStreamsSource`는 Flink 2.x용 커넥터(FLIP-27)로, 스트림 **이름이 아니라 ARN**을 받는다. Flink 1.x에서 쓰던 `FlinkKinesisConsumer`는 Flink 2.0에서 제거됐다.

```java
Configuration sourceConfig = new Configuration();
sourceConfig.set(KinesisSourceConfigOptions.STREAM_INITIAL_POSITION,
        KinesisSourceConfigOptions.InitialPosition.valueOf(initPosition));
```

읽기 시작 위치 설정. 다른 커넥터 옵션도 같은 `Configuration`에 넣으면 된다.

---

## 4. Sink

```java
FileSink<String> sink = FileSink
        .forRowFormat(new Path(s3Path), new SimpleStringEncoder<String>("UTF-8"))
        .withOutputFileConfig(OutputFileConfig.builder()
                .withPartPrefix("record")
                .withPartSuffix(".json")
                .build())
        .build();
```

`SimpleStringEncoder`는 문자열을 UTF-8로 쓰고 줄바꿈을 붙인다. 결과 파일은 JSON 배열이 아니라 **한 줄에 객체 하나(JSON Lines)** 이고, Athena/Glue의 기본 JSON 포맷이 이 형식이다.

### 저장 경로가 만들어지는 원리

실제로 생기는 경로는 이렇다.

```
s3a://my-bucket/output/2026-08-24--07/record-3f9c1a2e-8b04-4e77-9c31-0d2f5a6b7c88-0.json
```

**코드에 보이는 건 세 조각뿐이고, 나머지는 FileSink가 자동으로 붙인다.**

| 조각 | 출처 |
| --- | --- |
| `s3a://my-bucket/output/` | 코드 — `BUCKET_NAME` + `BUCKET_PATH`로 조립한 `s3Path` |
| `2026-08-24--07` | **FileSink 기본값** — `forRowFormat()`이 버킷 지정자를 안 받으면 `new DateTimeBucketAssigner<>()`를 자동으로 끼워 넣고, 그 기본 포맷이 `yyyy-MM-dd--HH`다 |
| `record` | 코드 — `withPartPrefix` |
| `-<uuid>-<n>` | **FileSink 내부** — uuid는 subtask(병렬 인스턴스)마다 하나씩 생기고, `<n>`은 파일이 롤링될 때마다 +1 된다. API로 끌 수 없다 |
| `.json` | 코드 — `withPartSuffix` |

날짜 디렉터리는 **레코드의 `timestamp` 필드가 아니라 Flink가 그 레코드를 처리한 시각(processing time)** 기준이다. 그래서 `TRIM_HORIZON`으로 며칠 전 데이터를 재처리하면 전부 오늘 디렉터리에 떨어진다. 타임존은 `ZoneId.systemDefault()`라서 MSF(UTC)와 로컬 IDE(KST)의 결과가 다르다.

파일이 닫히기 전에는 `.record-<uuid>-0.json.inprogress.<uuid>` 형태의 숨김 파일이고, 체크포인트가 완료돼야 위 이름으로 확정된다. S3에 `.inprogress`만 보인다면 체크포인트가 아직 안 돈 것이다.

### 체크포인트

```java
if (env instanceof LocalStreamEnvironment) {
    env.enableCheckpointing(5000);
}
```

FileSink는 **체크포인트가 완료돼야** in-progress 파일을 최종 파일로 커밋한다. 체크포인트가 없으면 S3에 완성된 파일이 영영 안 생긴다. MSF에서는 서비스가 체크포인팅을 관리하므로 로컬 실행일 때만 켠다. (MSF 2.2+는 서비스가 관리하는 설정을 코드로 바꾸면 예외를 던진다.)

---

## 5. 파이프라인

```java
env.fromSource(source, WatermarkStrategy.noWatermarks(), "kinesis-source", Types.STRING)
        .flatMap(App::process)
        .returns(String.class)
        .sinkTo(sink);

env.execute("kinesis-to-s3");
```

- `noWatermarks()` — 이벤트 시간 기반 window를 쓰지 않으므로 워터마크가 필요 없다.
- `Types.STRING` — `KinesisStreamsSource<T>`는 `ResultTypeQueryable`을 구현하지 않아 `T`가 지워진다. 타입 정보를 안 넘기면 잡 제출 시점에 `The return type of function 'kinesis-source' could not be determined automatically` 예외가 난다.
- `.returns(String.class)` — 람다·메서드 참조도 마찬가지로 제네릭 타입이 지워지므로 출력 타입을 명시해야 한다.
- `flatMap`을 쓴 이유는 `transform()`이 `null`을 반환할 때 레코드를 버리기 위해서다. `map`에서 null을 반환하면 직렬화 단계에서 NPE가 날 수 있다.

```java
private static void process(String json, Collector<String> out) throws Exception {
    ObjectNode result = transform((ObjectNode) MAPPER.readTree(json));
    if (result != null) {
        out.collect(MAPPER.writeValueAsString(result));
    }
}
```

문자열 → 트리 → `transform()` → 문자열. JSON을 다루는 부분은 여기 한 곳뿐이다.

- `(ObjectNode)` 캐스팅은 레코드 최상위가 JSON 객체 `{...}`라는 전제다. 배열이면 `ClassCastException`이 난다.
- 깨진 JSON이 들어오면 `readTree`가 예외를 던져 잡이 재시작 루프에 빠진다. 무시하고 넘기려면 이 메서드를 `try/catch`로 감싸고 실패 시 아무것도 `collect`하지 않으면 된다.
- `ObjectMapper`는 thread-safe라 `static` 하나를 공유한다. Flink 내부의 shaded Jackson과는 별개 라이브러리라 충돌하지 않는다.

---

## 테스트 데이터 보내기

`send-test-data.sh`가 변환 전 형식의 레코드를 Kinesis에 넣는다.

```sh
./send-test-data.sh <stream-name> [count]          # count 기본 10
AWS_REGION=us-east-1 ./send-test-data.sh wsi-stream 50
```

- `INIT_POSITION`이 `LATEST`면 **앱이 Running 상태가 된 뒤에** 실행해야 한다. 이미 넣어둔 데이터를 읽히려면 `TRIM_HORIZON`으로 바꾼다.
- S3에 파일이 확정되기까지 체크포인트 주기(MSF 기본 60초)만큼 걸린다. 그전에는 `.inprogress` 파일만 보인다.

```sh
aws s3 ls --recursive s3://<버킷>/output/
```

---

## 빌드 & 배포

```sh
mvn clean package                     # target/java-s3sink-1.0.jar (uber JAR)
aws s3 cp target/java-s3sink-1.0.jar s3://<code-bucket>/java-s3sink-1.0.jar
```

MSF 애플리케이션 설정:
- Runtime: **Apache Flink 2.3** (Java 17)
- Application code location: 위 S3 객체
- IAM role: `../application-policy.json` (Kinesis read, S3 read/write, CloudWatch Logs)
- Checkpointing: 활성화

## 버전

| 항목 | 버전 |
| --- | --- |
| Apache Flink | 2.3.0 |
| flink-connector-aws-kinesis-streams | 6.0.0-2.0 (Flink 2.x 호환 유일 버전) |
| aws-kinesisanalytics-runtime | 1.2.0 |
| Java | 17 |
