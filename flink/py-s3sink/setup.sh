# <!-- Source: https://mvnrepository.com/artifact/org.apache.flink/flink-connector-aws-kinesis-streams -->
# <dependency>
#     <groupId>org.apache.flink</groupId>
#     <artifactId>flink-connector-aws-kinesis-streams</artifactId>
#     <version>6.0.1-2.0</version>
#     <scope>test</scope>
# </dependency>

mvn package
zip flink-app.zip streaming_job.py flink-connector-aws-kinesis-streams.jar