from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment


def main():
    # Flink execution environment
    env = StreamExecutionEnvironment.get_execution_environment()

    # Table / SQL environment
    table_env = StreamTableEnvironment.create(
        stream_execution_environment=env
    )
    
    table_config = table_env.get_config()
    
    # Global Watermark는 모든 split(kinesis shard)의 Watermark 중 최솟값을 사용한다.
    # 특정 split에 이벤트가 없으면 해당 Watermark가 멈춰 전체 Watermark 진행을 막을 수 있어 timeout을 설정한다.
    table_config.set("table.exec.source.idle-timeout", "15 s")
    # table_config.set("execution.checkpointing.interval", "10 s")

    # Source
    table_env.execute_sql("""
        CREATE TABLE device (
            temperature DOUBLE,
            humidity DOUBLE,
            eventtime VARCHAR(20),  -- epoch seconds
            ts AS TO_TIMESTAMP_LTZ(CAST(eventtime AS BIGINT), 0),  -- 0 (epoch seconds) | 3 (epoch milliseconds)
            WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kinesis',
            'stream.arn' = '<STREAM_ARN>',
            'aws.region' = 'us-east-1',
            'source.init.position' = 'LATEST',
            'format' = 'json',
            'json.timestamp-format.standard' = 'ISO-8601'
        )
    """)

    # Sink
    table_env.execute_sql("""
        CREATE TABLE sink_s3 (
          temperature_count BIGINT,
          avg_temperature DOUBLE,
          window_start TIMESTAMP(3),
          window_end TIMESTAMP(3)
        ) WITH (
            'connector' = 'filesystem',
            'path' = 's3a://<BUCKET_NAME>/output/',
            'format' = 'json',
            'json.timestamp-format.standard' = 'ISO-8601',
            'sink.rolling-policy.rollover-interval' = '30 s',
            'sink.rolling-policy.check-interval' = '10 s'
        )
    """)

    # SQL Job execution
    table_env.execute_sql("""
        INSERT INTO `sink_s3`
        SELECT
            COUNT(*) AS temperature_count,
            AVG(temperature) AS avg_temperature,
            window_start,
            window_end
        FROM TABLE(
            TUMBLE(TABLE device, DESCRIPTOR(ts), INTERVAL '1' MINUTE)
        )
        GROUP BY window_start, window_end
    """)


if __name__ == '__main__':
    main()