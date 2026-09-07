-- Create Table
%flink.ssql
CREATE TABLE `sink_s3` (
  temperature_count BIGINT,
  avg_temperature DOUBLE,
  window_start TIMESTAMP(3),
  window_end TIMESTAMP(3)
)
-- PARTITIONED BY (`year`, `month`, `day`)
WITH (
  'connector' = 'filesystem',
  'path' = 's3a://<BUCKET_NAME>/output/',
  'format' = 'json',
  'json.timestamp-format.standard' = 'ISO-8601',
  'sink.rolling-policy.rollover-interval' = '30 s',
  'sink.rolling-policy.check-interval' = '10 s'
)

-- Insert Data
%flink.ssql
INSERT INTO `sink_s3`
SELECT
    COUNT(*) AS temperature_count,
    AVG(temperature) AS avg_temperature,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(TABLE device, DESCRIPTOR(event_ts), INTERVAL '1' MINUTE)
)
GROUP BY window_start, window_end

---

%flink.ssql
CREATE TABLE applog_parsed (
    `method` STRING,
    `path` STRING,
    `query` STRING,
    `size` INT,
    `year` BIGINT,
    `month` BIGINT,
    `day` BIGINT,
    `hour` BIGINT
)
PARTITIONED BY (
    `year`, `month`, `day`, `hour`
)
WITH (
  'connector' = 'filesystem',
  'path' = 's3://project-applicationlog/test',
  'format' = 'json',
  'sink.partition-commit.policy.kind' = 'success-file',
  'sink.partition-commit.delay' = '30sec',
  'sink.rolling-policy.file-size' = '1MB',
  'sink.rolling-policy.rollover-interval' = '30sec',
  'sink.rolling-policy.check-interval' = '30sec'
);

---


%flink.pyflink

env = StreamExecutionEnvironment.get_execution_environment()

env.enable_checkpointing(10 * 1000)
env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)

--

%flink.ssql(type=update)
INSERT INTO applog_parsed (`method`, `path`, `query`, `size`, `year`, `month`, `day`, `hour`)
SELECT `method`, SPLIT_INDEX(`path`, '?', 0) AS `path`, SPLIT_INDEX(`path`, '?', 1) AS `query`, `size`, YEAR(`time`), MONTH(`time`), DAYOFMONTH(`time`), HOUR(`time`)
FROM applog2;