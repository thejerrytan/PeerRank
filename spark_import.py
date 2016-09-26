# Import anon-links.txt to mySQL users table using spark. Run this using spark_submit
from pyspark.conf import SparkConf
from pyspark import SparkContext
from pyspark.sql import SparkSession, Row
from pyspark.sql import SQLContext
from pyspark.sql.types import *

MYSQL_USER     = 'root'
MYSQL_PW       = 'root'
MYSQL_TABLE    = 'new_temp'
MYSQL_DB       = 'test'
# PATH_TO_DATA = "/Users/Jerry/Desktop/links1.txt"
# PATH_TO_DATA = "/Volumes/Mac/data/links-anon.txt"
PATH_TO_DATA   = "gs://peerrank-141304.appspot.com/data/links-anon.txt"
PATH_TO_SPARK  = "gs://dataproc-6b80d17c-615b-4b31-adb7-be505aa9fd31-us/scripts/spark_import.py"

sc = SparkContext()
sqlcontext = SQLContext(sc)

spark = SparkSession.builder.master("local").appName("PeerRanK").getOrCreate()
schema = StructType([
	StructField("listed_count", IntegerType(), True),
	StructField("user_id", IntegerType(), True)
	])

distFile = sc.textFile(PATH_TO_DATA)
follower = distFile.map(lambda x: int(x.split(' ')[0].strip('\n')))
users = distFile.map(lambda x: int(x.split(' ')[1].strip('\n'))).union(follower).distinct()
data = users.map(lambda x: Row(user_id=x, listed_count=None))

df = sqlcontext.createDataFrame(data, schema)
df.write.jdbc("jdbc:mysql://104.198.155.210:3306/test?user=root&password=root", MYSQL_TABLE, 'append', properties={"driver": 'com.mysql.jdbc.Driver'})
