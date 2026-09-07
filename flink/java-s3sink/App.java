package com.example.flinkapp;

import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.table.api.EnvironmentSettings;
import org.apache.flink.table.api.TableConfig;
import org.apache.flink.table.api.TableResult;
import org.apache.flink.table.api.bridge.java.StreamTableEnvironment;

public class App {

    private static final String STREAM_ARN = "<STREAM_ARN>";
    private static final String BUCKET_NAME = "<BUCKET_NAME>";
    private static final String AWS_REGION = "us-east-1";

    public static void main(String[] args) throws Exception {

        // ------------------------------------------------------------
        // Flink execution environment
        // ------------------------------------------------------------
        StreamExecutionEnvironment env =
                StreamExecutionEnvironment.getExecutionEnvironment();

        // ------------------------------------------------------------
        // Table / SQL environment
        // ------------------------------------------------------------
        EnvironmentSettings settings = EnvironmentSettings
                .newInstance()
                .inStreamingMode()
                .build();

        StreamTableEnvironment tableEnv =
                StreamTableEnvironment.create(env, settings);

        TableConfig tableConfig = tableEnv.getConfig();

        /*
         * Global Watermark는 모든 split(Kinesis shard)의
         * Watermark 중 최솟값을 사용한다.
         *
         * 특정 shard에 이벤트가 없으면 해당 Watermark가 멈춰
         * 전체 Watermark 진행을 막을 수 있으므로
         * idle timeout을 설정한다.
         *
         * MSF에서도 코드에서 설정 가능한 Table API / SQL 옵션이다.
         */
        tableConfig.set("table.exec.source.idle-timeout", "15 s");

        /*
         * AWS Managed Service for Apache Flink에서는
         * checkpointing을 Application configuration에서 관리한다.
         *
         * 따라서 여기서는 env.enableCheckpointing()을 호출하지 않는다.
         */

        // ------------------------------------------------------------
        // Kinesis Source
        // ------------------------------------------------------------
        String sourceDDL = """
                CREATE TABLE device (
                    temperature DOUBLE,
                    humidity DOUBLE,
                    eventtime VARCHAR(20),
                    ts AS TO_TIMESTAMP_LTZ(CAST(eventtime AS BIGINT), 0),  -- 0 (epoch seconds) | 3 (epoch milliseconds)
                    WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
                ) WITH (
                    'connector' = 'kinesis',
                    'stream.arn' = '%s',
                    'aws.region' = '%s',
                    'source.init.position' = 'LATEST',
                    'format' = 'json',
                    'json.timestamp-format.standard' = 'ISO-8601'
                )
                """.formatted(STREAM_ARN, AWS_REGION);

        tableEnv.executeSql(sourceDDL);

        // ------------------------------------------------------------
        // S3 Sink
        // ------------------------------------------------------------
        String sinkDDL = """
                CREATE TABLE sink_s3 (
                    temperature_count BIGINT,
                    avg_temperature DOUBLE,
                    window_start TIMESTAMP(3),
                    window_end TIMESTAMP(3)
                ) WITH (
                    'connector' = 'filesystem',
                    'path' = 's3a://%s/output/',
                    'format' = 'json',
                    'json.timestamp-format.standard' = 'ISO-8601',
                    'sink.rolling-policy.rollover-interval' = '30 s',
                    'sink.rolling-policy.check-interval' = '10 s'
                )
                """.formatted(BUCKET_NAME);

        tableEnv.executeSql(sinkDDL);

        // ------------------------------------------------------------
        // SQL Job execution
        // ------------------------------------------------------------
        String insertSql = """
                INSERT INTO sink_s3
                SELECT
                    COUNT(*) AS temperature_count,
                    AVG(temperature) AS avg_temperature,
                    window_start,
                    window_end
                FROM TABLE(
                    TUMBLE(
                        TABLE device,
                        DESCRIPTOR(ts),
                        INTERVAL '1' MINUTE
                    )
                )
                GROUP BY
                    window_start,
                    window_end
                """;

        TableResult result = tableEnv.executeSql(insertSql);

        /*
         * executeSql(INSERT)가 streaming job을 submit한다.
         *
         * AWS Managed Service for Apache Flink에서도
         * 별도로 env.execute()를 호출하지 않는다.
         */
        result.getJobClient()
                .ifPresent(jobClient ->
                        System.out.println(
                                "Flink Job submitted: "
                                        + jobClient.getJobID()
                        )
                );
    }
}