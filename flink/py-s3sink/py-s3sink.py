#########################################################################################################
#
# Extract this python code(streaming_job.py) with flink-connector-aws-kinesis-streams.jar
#
# mvn package
# zip flink-app.zip streaming_job.py flink-connector-aws-kinesis-streams.jar
#
#########################################################################################################


import json
import os

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kinesis import FlinkKinesisConsumer
from pyflink.datastream.connectors.file_system import FileSink, RollingPolicy, OutputFileConfig
from pyflink.common.serialization import SimpleStringSchema, Encoder

PROPS_FILE = "/etc/flink/application_properties.json"

STREAM_NAME = "demo-stream"
AWS_REGION  = "us-east-1"
S3_OUTPUT   = "s3://your-bucket/flink-output/"

def load_app_props():
    if not os.path.isfile(PROPS_FILE):
        return {}
    with open(PROPS_FILE) as f:
        return {g["PropertyGroupId"]: g["PropertyMap"] for g in json.load(f)}

def main():
    props = load_app_props()
    stream_name = props.get("consumer.config.0", {}).get("input.stream.name", STREAM_NAME)
    aws_region  = props.get("consumer.config.0", {}).get("aws.region",        AWS_REGION)
    s3_output   = props.get("producer.config.0", {}).get("output.s3.path",    S3_OUTPUT)

    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(60_000)

    source = FlinkKinesisConsumer(
        stream_name,
        SimpleStringSchema(),
        {"aws.region": aws_region, "stream.initial.position": "LATEST"},
    )

    sink = (
        FileSink.for_row_format(s3_output, Encoder.simple_string_encoder())
        .with_rolling_policy(
            RollingPolicy.default_rolling_policy(
                part_size=128 * 1024 * 1024,  # 128 MB
                rollover_interval=60 * 1_000,  # 1분
                inactivity_interval=60 * 1_000,
            )
        )
        .with_output_file_config(
            OutputFileConfig.builder()
            .with_part_prefix("output")
            .with_part_suffix(".json")
            .build()
        )
        .build()
    )

    env.add_source(source).sink_to(sink)
    env.execute("KinesisToS3")

if __name__ == "__main__":
    main()