-- Flink 1.15 (Studio)
-- ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/table/kinesis/#connector-options-kinesis-legacy
%flink.ssql
CREATE TABLE `device` (
  `temperature` DOUBLE,
  `humidity` DOUBLE,
  `eventtime` VARCHAR(20),  -- epoch
  `deviceid` VARCHAR(20),
  -- 0(seconds) | 3(milliseconds)
  --`ts` AS TO_TIMESTAMP_LTZ(CAST(eventtime AS BIGINT), 0),  -- epoch parsing
  WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
)
WITH (
  'connector' = 'kinesis',
  'stream' = 'project-stream',
  'aws.region' = 'us-east-1',
  'scan.stream.initpos' = 'LATEST',
  'format' = 'json'
);

-- Flink 2.3
-- ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/table/kinesis/#amazon-kinesis-data-streams-sql-connector
%flink.ssql
CREATE TABLE `device` (
  `temperature` DOUBLE,
  `humidity` DOUBLE,
  `eventtime` VARCHAR(20),  -- epoch
  `deviceid` VARCHAR(20),
  -- 0(seconds) | 3(milliseconds)
  --`ts` AS TO_TIMESTAMP_LTZ(CAST(eventtime AS BIGINT), 0),  -- epoch parsing
  WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
)
WITH (
  'connector' = 'kinesis',
  'stream.arn' = 'arn:aws:kinesis:<REGION>:<ACCOUNT_ID>:stream/<STREAM_NAME>',
  'aws.region' = 'us-east-1',
  'source.init.position' = 'LATEST',
  'format' = 'json'
);
