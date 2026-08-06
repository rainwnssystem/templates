-- Athena -> Query Editor -> Create table from S3 bucket data

CREATE EXTERNAL TABLE IF NOT EXISTS `wsi-database`.`accesslog` (
  `clientip` string,
  `year` int,
  `month` int,
  `day` int,
  `hour` int,
  `minute` int,
  `second` int,
  `method` string,
  `path` string,
  `protocol` string,
  `responsecode` int,
  `processingtime` float,
  `useragent` string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
STORED AS INPUTFORMAT 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat' OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION 's3://wsi-log-bosk/accesslog/'
TBLPROPERTIES ('classification' = 'parquet');