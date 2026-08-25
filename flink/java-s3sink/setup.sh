# create mvn project template
mvn archetype:generate -DgroupId=com.example.app -DartifactId=app -DarchetypeArtifactId=maven-archetype-quickstart -DarchetypeVersion=1.5 -DinteractiveMode=false

# check dependencies
mvn compile

# build a jar
# mvn package