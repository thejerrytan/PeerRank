# Import anon-links.txt to mySQL users table using spark. Run this using spark_submit
from pyspark.conf import SparkConf
from pyspark import SparkContext
from pyspark.sql import SparkSession, Row
from pyspark.sql import SQLContext
from pyspark.sql.types import *
import json, os, socket

ENV                = json.loads(open(os.path.join(os.path.dirname(__file__), 'env.json')).read())
MYSQL_HOST         = ENV['MYSQL_HOST'] if socket.gethostname() != ENV['INSTANCE_HOSTNAME'] else "localhost"
MYSQL_USER         = ENV['MYSQL_USER']
MYSQL_PW           = ENV['MYSQL_PW']
MYSQL_PORT         = ENV['MYSQL_PORT']
MYSQL_FOLLOW_TABLE = 'follows'
MYSQL_DB           = ENV['MYSQL_DB']
# PATH_TO_DATA     = "/Users/Jerry/Desktop/links1.txt"
# PATH_TO_DATA     = "/Volumes/Mac/data/links-anon.txt"
PATH_TO_DATA       = "gs://peerrank-141304.appspot.com/data/links-anon.txt"
PATH_TO_SPARK      = "gs://dataproc-6b80d17c-615b-4b31-adb7-be505aa9fd31-us/scripts/spark_import.py"

sc = SparkContext()
sqlcontext = SQLContext(sc)

spark = SparkSession.builder.master("local").appName("PeerRanK").getOrCreate()
# schema = StructType([
# 	StructField("listed_count", IntegerType(), True),
# 	StructField("user_id", IntegerType(), True)
# 	])
schema = StructType([
	StructField("follower", IntegerType(), True),
	StructField("followee", IntegerType(), True),
	])
distFile = sc.textFile(PATH_TO_DATA)
follower = distFile.map(lambda x: tuple(map(lambda y: int(y.strip('\n')), x.split(' '))))
# users = distFile.map(lambda x: int(x.split(' ')[1].strip('\n'))).union(follower).distinct()
# data = users.map(lambda x: Row(user_id=x, listed_count=None))
data = follower.map(lambda x: Row(follower=x[0], followee=x[1]))

df = sqlcontext.createDataFrame(data, schema)
df.write.jdbc("jdbc:mysql://%s:%s/%s?user=%s&password=%s" % (MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PW), MYSQL_FOLLOW_TABLE, 'append', properties={"driver": 'com.mysql.jdbc.Driver'})
