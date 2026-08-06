### Output plugin

- **cloudwatch**
    - `$(ecs_task_id)` 등의 metadata variable 사용이 가능하다.
    - https://github.com/aws/amazon-cloudwatch-logs-for-fluent-bit#templating-log-group-and-stream-names
- **cloudwatch_logs**
    - metadata variable을 사용할 수 없으며, `init-metadata` 를 사용하면 가능하다.
    - https://github.com/aws-samples/amazon-ecs-firelens-examples/tree/mainline/examples/fluent-bit/init-metadata
- `"log_key": "log"` 를 logConfiguration에 추가하여 log record만 return할 수 있다.
    - https://github.com/aws-samples/amazon-ecs-firelens-examples/tree/mainline/examples/fluent-bit/cloudwatchlogs

## Firelens Fluentbit → Cloudwatch (기본 conf 사용)

- 별도의 conf 없이 aws-for-fluent-bit의 기본 설정으로 구성한다.
- https://github.com/aws-samples/amazon-ecs-firelens-examples/blob/mainline/examples/fluent-bit/cloudwatchlogs/task-definition-cloudwatch.json

### app container

- cloudwatch plugin에서 `$(ecs_task_id)` `$(ecs_cluster)` `$(ecs_task_arn)` 등을 사용한다.

```json
"logConfiguration": {
	"logDriver": "awsfirelens",
	"options": {
		"log_group_name": "/wsi/app/customer",
		"log_stream_name": "$(ecs_task_id)",
		"auto_create_group": "true",
		"log_key": "log",
		"region": "ap-northeast-2",
		"workers": "1",
		"Name": "cloudwatch",
		"retry_limit": "2"
	}
},
```

- 또는 cloudwatch_logs plugin에서 `:init-latest` tag를 통해 env를 사용한다.

```json
...
"logConfiguration": {
	"logDriver": "awsfirelens",
	"options": {
		"log_group_name": "/wsi/app/customer",
		"log_stream_name": "logs/${ECS_TASK_ID}",
		"auto_create_group": "true",
		"log_key": "log",
		"region": "ap-northeast-2",
		"workers": "1",
		"Name": "cloudwatch_logs",
		"retry_limit": "2"
	}
},
...
"image": "public.ecr.aws/aws-observability/aws-for-fluent-bit:init-latest",
...
```

### log_router container

- `enable-ecs-log-metadata` 가 true/false인 것에 따라 로그에 ecs metadata를 함께 내보낸다.
    - 이 옵션이 `true` 여야 cloudwatch 플러그인에서 `$(variable)` 사용이 가능하다.

```json
"logConfiguration": {
	"logDriver": "awslogs",
	"options": {
		"awslogs-group": "firelens/customer",
		"awslogs-create-group": "true",
		"awslogs-region": "ap-northeast-2",
		"awslogs-stream-prefix": "firelens"
	}
},
```

```json
"firelensConfiguration": {
	"type": "fluentbit",
	"options": {
		"enable-ecs-log-metadata": "false"
	}
},
```

## Custom fluent-bit config (only filter & parser)

- 새로운 fluentbit image를 만들어서 ECR에 올려 사용할 수 있다.
- https://github.com/aws-samples/amazon-ecs-firelens-examples/tree/mainline/examples/fluent-bit/filter-multiline

```
fluent-bit-custom
⨽ Dockerfile
⨽ extra.conf
⨽ parser.conf
```

### Dockerfile

```docker
FROM public.ecr.aws/aws-observability/aws-for-fluent-bit:init-latest

ADD parser.conf /parser.conf
ADD extra.conf /extra.conf
```

### extra.conf

- INPUT, OUTPUT은 제외하고 `[SERVICE]` `[FILTER]` `[PARSER]` 만 작성하면 된다.

```yaml
[SERVICE]
    Flush        1
    Log_Level    info
    Parsers_File /parser.conf

# parsing log with parser
[FILTER]
    Name         parser
    Match        *
    Key_Name     log
    Parser       docker

# exclude log with /healthz path
[FILTER]
    Name   grep
    Match  *
    Exclude log /healthz
```

- log record만 return하려면 다음 filter를 추가한다.

```yaml
# return only 'log' record
[FILTER]
    Name record_modifier
    Match *
    Allowlist_key log
```

- 위 filter는 `"log_key": "log"` 를 logConfiguration에 추가해서도 해결 가능하다.
    - amazon-ecs-firelens-examples/examples/fluent-bit/cloudwatchlogs at mainline · aws-samples/amazon-ecs-firelens-examples

### parser.conf

- regex는 Rubular에서 확인한다.

```yaml
[PARSER]
    Name        docker
    Format      json
    Time_Key    time
    Time_Format %Y/%m/%d - %H:%M:%S
    Decode_Field_As escaped_utf8 log

[PARSER]
    Name   app
    Format regex
    Regex  ^(?<year>[^\x20]*)-(?<month>[^\x20]*)-(?<day>[^\x20]*) (?<hour>[^\x20]*):(?<minute>[^\x20]*):(?<second>[^\x20]*),[^\x20]* [^\x20]* [^\x20]* (?<ip>[^\x20]*) (?<port>[^\x20]*) (?<method>[^\x20]*) (?<path>[^\x20]*) (?<statuscode>[^\x20]*)
```

### Task Definition

- log_router container에서 firelensConfiguration을 아래와 같이 작성한다.

```json
"firelensConfiguration": {
		"type": "fluentbit",
		"options": {
				"config-file-type": "file",
				"config-file-value": "/extra.conf"
		}
},
```

- app container에서 logConfiguration을 아래와 같이 작성한다.
- cloudwatch plugin에서 `$(ecs_task_id)` `$(ecs_cluster)` `$(ecs_task_arn)` 등을 사용한다.

```json
"logConfiguration": {
	"logDriver": "awsfirelens",
	"options": {
		"log_group_name": "/wsi/app/customer",
		"log_stream_name": "$(ecs_task_id)",
		"auto_create_group": "true",
		"log_key": "log",
		"region": "ap-northeast-2",
		"workers": "1",
		"Name": "cloudwatch",
		"retry_limit": "2"
	}
},
```

- 또는 cloudwatch_logs plugin에서 `init-metadata` 를 통해 env를 사용한다.

```json
"logConfiguration": {
	"logDriver": "awsfirelens",
	"options": {
		"log_group_name": "/wsi/app/customer",
		"log_stream_name": "logs/${ECS_TASK_ID}",
		"auto_create_group": "true",
		"log_key": "log",
		"region": "ap-northeast-2",
		"workers": "1",
		"Name": "cloudwatch_logs",
		"retry_limit": "2"
	}
},
```

- 이제 ECS Service를 생성한 후 Cloudwatch Logs에서 동작을 확인한다.

## Custom fluent-bit config (All)

- `rewrite_tag` 를 통해 전체 부분을 한번에 구성할 수 있다.

```
fluent-bit-custom
⨽ Dockerfile
⨽ extra.conf
⨽ parser.conf
```

### Dockerfile

```docker
FROM public.ecr.aws/aws-observability/aws-for-fluent-bit

COPY parser.conf /parser.conf
COPY extra.conf /extra.conf

CMD ["/fluent-bit/bin/fluent-bit", "-c", "/extra.conf"]
```

### extra.conf

- `[INPUT]` `[SERVICE]` `[FILTER]` `[PARSER]` `[OUTPUT]` 을 모두 작성한다.

```yaml
[SERVICE]
    Flush        1
    Log_Level    info
    Parsers_File /parser.conf

[INPUT]
    Name forward
    Unix_Path /var/run/fluent.sock

[FILTER]
    Name ecs
    Match app.*
    ECS_Tag_Prefix app.
    ADD ecs_task_id $TaskID
    ADD ecs_task_family $TaskDefinitionFamily
    ADD ecs_task_arn $TaskARN
    ADD ecs_container_name $ECSContainerName
    ADD cluster $ClusterName

[FILTER]
    Name         rewrite_tag
    Match        app.*
    Rule         ecs_task_family (.*) log.$1.$ecs_container_name false
    Emitter_Name re_emitted

# return only 'log' record
[FILTER]
    Name record_modifier
    Match log.product.*
    Allowlist_key log

# parsing log with parser
[FILTER]
    Name     parser
    Match    log.product.*
    Key_Name log
    Parser   docker

# exclude log with /healthz path
[FILTER]
    Name   grep
    Match  log.*
    Exclude log /healthz

[OUTPUT]
    Name cloudwatch_logs
    Match log.*
    region ap-northeast-2
    log_group_template /wsi/app/$ecs_container_name
    log_group_name wsi/app/failback-logs
    log_stream_template $ecs_task_id
    log_stream_name failback
    auto_create_group true
```

### parser.conf

- regex는 Rubular에서 확인한다.

```yaml
[PARSER]
    Name        docker
    Format      json
    Time_Key    time
    Time_Format %Y/%m/%d - %H:%M:%S
    Decode_Field_As escaped_utf8 log

[PARSER]
    Name   app
    Format regex
    Regex  ^(?<year>[^\x20]*)-(?<month>[^\x20]*)-(?<day>[^\x20]*) (?<hour>[^\x20]*):(?<minute>[^\x20]*):(?<second>[^\x20]*),[^\x20]* [^\x20]* [^\x20]* (?<ip>[^\x20]*) (?<port>[^\x20]*) (?<method>[^\x20]*) (?<path>[^\x20]*) (?<statuscode>[^\x20]*)
```

### Task Definition

- log_router container에서 firelensConfiguration을 아래와 같이 작성한다.

```json
"firelensConfiguration": {
		"type": "fluentbit",
		"options": {
				"config-file-type": "file",
				"config-file-value": "/extra.conf"
		}
},
```

- app container에서 logConfiguration을 아래와 같이 작성한다.

```json
"logConfiguration": {
	"logDriver": "awsfirelens",
	"options": {}
},
```

- 이제 ECS Service를 생성한 후 Cloudwatch Logs에서 동작을 확인한다.