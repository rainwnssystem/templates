## 1. Set up maven project
```shell
mvn archetype:generate -DgroupId=com.example.flinkapp -DartifactId=flinkapp
```

## 2. Configure packages
- Modify pom.xml for the flink connector(kinesis) dependency and shade plugin.

## 3. Build jar and create artifact
```
mvn clean package
cp ./target/flinkapp-1.0-SNAPSHOT.jar ./pyflink-dependencies.jar
zip flinkapp.zip app.py pyflink-dependencies.jar
```