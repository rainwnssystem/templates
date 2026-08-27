import json
import pymysql
import redis
from redis.cluster import RedisCluster
from flask import Flask, jsonify, request


app = Flask(__name__)


# RDS MySQL
db = pymysql.connect(
    host="wsi-rds-instance.cbnpgxnvzfnd.us-east-1.rds.amazonaws.com",
    port=3307,
    user="wsi",
    password="$RBiK7nG.OQR_:>k>.SV$6PDd#?8",
    database="wsi",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
)


# ElastiCache Valkey
cache = RedisCluster(
    host="clustercfg.wsi-cache-cluster.6ojm1j.use1.cache.amazonaws.com",
    port=6390,
    decode_responses=True,
    ssl=True,
)


CACHE_TTL = 60


def get_user(user_id):
    key = f"user:{user_id}"

    # 1. Cache 조회
    cached = cache.get(key)

    if cached:
        print("CACHE HIT")
        return json.loads(cached)

    print("CACHE MISS")

    # 2. Cache miss → RDS 조회
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, email FROM users WHERE id = %s",
            (user_id,),
        )
        user = cursor.fetchone()

    if not user:
        return None

    # 3. Cache 저장
    cache.set(
        key,
        json.dumps(user, default=str),
        ex=CACHE_TTL,
    )

    return user


# GET
@app.get("/users/<int:user_id>")
def user_detail(user_id):
    user = get_user(user_id)

    if not user:
        return jsonify({"error": "user not found"}), 404

    return jsonify(user)


# POST
@app.post("/users")
def create_user():
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON body required"}), 400

    name = data.get("name")
    email = data.get("email")

    if not name or not email:
        return jsonify({
            "error": "name and email are required"
        }), 400

    # 1. RDS에 INSERT
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users (name, email)
            VALUES (%s, %s)
            """,
            (name, email),
        )

        user_id = cursor.lastrowid

    user = {
        "id": user_id,
        "name": name,
        "email": email,
    }

    # 2. Valkey에도 저장
    key = f"user:{user_id}"

    cache.set(
        key,
        json.dumps(user),
        ex=CACHE_TTL,
    )

    return jsonify(user), 201


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )