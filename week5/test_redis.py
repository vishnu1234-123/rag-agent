import redis

r=redis.Redis(host="localhost",port=6379,decode_responses=True)

#basic set/get
r.set("greeting","hello from redis")
value=r.get("greeting")
print(f"Stored value: {value}")

#check connection
print(f"Redis ping: {r.ping()}")