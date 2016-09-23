# Import anon-links.txt to mySQL users table using spark. Run this using spark_submit
from pyspark.conf import SparkConf
from pyspark import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql import SQLContext
from pyspark.sql.types import *

MYSQL_USER = 'root'
MYSQL_PW = 'root'
MYSQL_TABLE = 'users'
MYSQL_DB = 'test'
# PATH_TO_DATA = "/Users/Jerry/Desktop/anon-links.txt"
# PATH_TO_DATA = "/Volumes/Mac/data/links-anon.txt"
PATH_TO_DATA = "gs://peerrank-141304.appspot.com/data/links-anon.txt"
PATH_TO_SPARK = "gs://dataproc-6b80d17c-615b-4b31-adb7-be505aa9fd31-us/scripts/spark_import.py"

sc = SparkContext()
sqlcontext = SQLContext(sc)

spark = SparkSession.builder.master("local").appName("PeerRanK").getOrCreate()
schema = StructType([
	StructField("id", IntegerType(), True)
	])

distFile = sc.textFile(PATH_TO_DATA)
data = distFile.map(lambda x: (int(x.split(' ')[0].strip('\n')),))

df = sqlcontext.createDataFrame(data, schema).drop_duplicates()
df.write.jdbc("jdbc:mysql://104.196.149.230:3306/test?user=root&password=root", MYSQL_TABLE, 'overwrite', properties={"driver": 'com.mysql.jdbc.Driver'})
