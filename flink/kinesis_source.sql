%flink.ssql

-- Nginx Access Log
CREATE TABLE acclog (
  `remote` STRING,
  `host` STRING,
  `user` STRING,
  `method` STRING,
  `path` STRING,
  `code` STRING,
  `size` INT,
  `referer` STRING,
  `agent` STRING,
  `time` TIMESTAMP(3),
  WATERMARK FOR `time` AS `time` - INTERVAL '1' SECOND
)
WITH (
  'connector' = 'kinesis',
  'stream' = 'wsi-stream',
  'aws.region' = 'us-east-1',
  'scan.stream.initpos' = 'LATEST',
  'format' = 'json'
);