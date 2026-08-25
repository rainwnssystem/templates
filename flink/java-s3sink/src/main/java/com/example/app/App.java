package com.example.app;

import com.amazonaws.services.kinesisanalytics.runtime.KinesisAnalyticsRuntime;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringEncoder;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.connector.file.sink.FileSink;
import org.apache.flink.connector.kinesis.source.KinesisStreamsSource;
import org.apache.flink.connector.kinesis.source.config.KinesisSourceConfigOptions;
import org.apache.flink.core.fs.Path;
import org.apache.flink.streaming.api.environment.LocalStreamEnvironment;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.filesystem.OutputFileConfig;
import org.apache.flink.util.Collector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.Properties;


// InputStream0	 stream.arn            <STREAM_ARN>
// InputStream0	 source.init.position  LATEST
// bucket	 name	               my-bucket (only bucket name)
// bucket	 path	               output
public class App {

    // Defaults, overridden by MSF runtime properties (groups "InputStream0" and "bucket")
    private static final String STREAM_ARN = "arn:aws:kinesis:us-east-1:<ACCOUNT_ID>:stream/<STREAM_NAME>";
    private static final String BUCKET_NAME = "<S3_BUCKET_NAME>";
    private static final String BUCKET_PATH = "output";
    private static final String INIT_POSITION = "LATEST"; // LATEST | TRIM_HORIZON

    // Edit here: change one record, return null to drop it
    private static ObjectNode transform(ObjectNode record) {
        record.put("email", record.path("name").asText() + "@test.com");
        return record;
    }

    private static final Logger LOG = LoggerFactory.getLogger(App.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) throws Exception {

        // MSF runtime properties, falling back to the constants above when running locally
        Map<String, Properties> properties = KinesisAnalyticsRuntime.getApplicationProperties();
        Properties inputProperties = properties.getOrDefault("InputStream0", new Properties());
        Properties bucketProperties = properties.getOrDefault("bucket", new Properties());

        String streamArn = inputProperties.getProperty("stream.arn", STREAM_ARN);
        String initPosition = inputProperties.getProperty("source.init.position", INIT_POSITION);
        String bucketName = bucketProperties.getProperty("name", BUCKET_NAME);
        String s3Path = "s3a://" + bucketName + "/" + bucketProperties.getProperty("path", BUCKET_PATH);

        LOG.info("config: stream.arn={} s3.path={} source.init.position={}", streamArn, s3Path, initPosition);
        if (bucketName.contains("<")) {
            throw new IllegalArgumentException("bucket name is not configured: " + bucketName);
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // FileSink commits files on completed checkpoints. MSF manages checkpointing itself.
        if (env instanceof LocalStreamEnvironment) {
            env.enableCheckpointing(5000);
        }

        // Source: read records as raw JSON strings (region is taken from the stream ARN)
        Configuration sourceConfig = new Configuration();
        sourceConfig.set(KinesisSourceConfigOptions.STREAM_INITIAL_POSITION,
                KinesisSourceConfigOptions.InitialPosition.valueOf(initPosition));

        KinesisStreamsSource<String> source = KinesisStreamsSource.<String>builder()
                .setStreamArn(streamArn)
                .setSourceConfig(sourceConfig)
                .setDeserializationSchema(new SimpleStringSchema())
                .build();

        // Sink: one JSON object per line, at <S3_PATH>/yyyy-MM-dd--HH/record-<uuid>-<n>.json
        // Only the prefix and suffix come from this code. FileSink defaults add the rest:
        // the hourly directory (processing time), the writer uuid and the part counter.
        // A file is closed after 128MB, 60s of age, or 60s without input (default rolling policy).
        FileSink<String> sink = FileSink
                .forRowFormat(new Path(s3Path), new SimpleStringEncoder<String>("UTF-8"))
                .withOutputFileConfig(OutputFileConfig.builder()
                        .withPartPrefix("record")
                        .withPartSuffix(".json")
                        .build())
                .build();

        env.fromSource(source, WatermarkStrategy.noWatermarks(), "kinesis-source", Types.STRING)
                .flatMap(App::process)
                .returns(String.class) // lambdas erase generics, so the output type is declared here
                .sinkTo(sink);

        env.execute("kinesis-to-s3");
    }

    // JSON string -> tree -> transform() -> JSON string
    private static void process(String json, Collector<String> out) throws Exception {
        ObjectNode result = transform((ObjectNode) MAPPER.readTree(json));
        if (result != null) {
            out.collect(MAPPER.writeValueAsString(result));
        }
    }
}
