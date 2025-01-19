from flask import Flask, request, jsonify
import os
import redis
import time

app = Flask(__name__)

# 从环境变量读取 Redis 配置
redis_host = os.getenv("REDIS_HOST", "localhost")  # 默认 localhost
redis_port = os.getenv("REDIS_PORT", 6379)  # 默认端口 6379
redis_db = os.getenv("REDIS_DB", 1)  # 默认使用 db 1

# 连接Redis
redis_client = redis.StrictRedis(
    host=redis_host, port=redis_port, db=redis_db, decode_responses=True
)


# POST接口：保存数据
@app.route("/save", methods=["POST"])
def save_data():
    # 获取请求的JSON数据
    data = request.get_json()
    _id = data.get("id")
    num = data.get("num")

    if not _id or not num:
        return jsonify({"error": "Missing id, num"}), 400

    # 验证id是否为16位纯数字字符串
    if not isinstance(_id, str) or not _id.isdigit() or len(_id) != 16:
        return jsonify({"error": "Invalid id format"}), 400

    # 验证num是否为正整数
    if not isinstance(num, int) or num <= 0:
        return jsonify({"error": "Invalid num value"}), 400

    # 获取当前时间戳
    _time = int(time.time())

    # 设置过期时间（time + 3天）
    expiry_time = int(_time) + 3 * 24 * 3600  # 3天后过期
    redis_client.hset(
        _id,
        mapping={
            "num": num,
            "time": _time,
            "expiry_time": expiry_time,
            "show_count": 0,
            "count": 0,
            "valid": 0,
        },
    )

    # 设置ID过期时间
    redis_client.expireat(_id, expiry_time)

    return jsonify({"message": "Data saved successfully"}), 200


# GET接口：返回未确认是否有效且最旧的ID
@app.route("/get", methods=["GET"])
def get_data():
    # 存储所有未确认是否有效的ID（valid为None或不设置valid）
    unconfirmed_ids = []

    # 使用SCAN命令遍历所有的ID
    cursor = "0"
    while cursor != 0:
        cursor, keys = redis_client.scan(cursor=cursor, match="*", count=100)
        for _id in keys:
            # 检查每个ID的有效性（valid字段是否存在或为None）
            valid_status = redis_client.hget(_id, "valid")
            show_count = int(redis_client.hget(_id, "show_count"))
            count = int(redis_client.hget(_id, "count"))
            num = int(redis_client.hget(_id, "num"))
            if valid_status is None or int(valid_status) == 0:  # 表示未确认有效性
                max_count = get_max_count(num)
                max_show_count = get_max_show_count(num)
                if count < max_count and show_count < max_show_count:
                    unconfirmed_ids.append(_id)

    # 如果没有未确认是否有效的ID
    if not unconfirmed_ids:
        return jsonify({"id": ""}), 200

    # 查找最旧的ID
    oldest_id = None
    oldest_time = float("inf")

    for _id in unconfirmed_ids:
        # 获取每个ID的时间戳
        time_created = int(redis_client.hget(_id, "time"))
        if time_created < oldest_time:
            oldest_time = time_created
            oldest_id = _id

    # 更新返回次数
    redis_client.hincrby(oldest_id, "count", 1)

    # 返回最旧的未确认是否有效的ID
    return jsonify({"id": oldest_id}), 200


def get_max_count(num):
    return num * 10


def get_max_show_count(num):
    if num == 1:
        return 5
    elif num == 2:
        return 9
    elif num == 3:
        return 15
    elif num == 4:
        return 21
    else:
        return num * 5


# 新增接口：设置ID的有效状态
@app.route("/set_valid", methods=["POST"])
def set_valid():
    # 获取请求的JSON数据
    data = request.get_json()
    _id = data.get("id")
    valid = data.get("valid")

    if _id is None or valid is None:
        return jsonify({"error": "Missing id or valid parameter"}), 400

    # 检查valid参数是否是布尔值
    if not isinstance(valid, int):
        return jsonify({"error": "Valid parameter must be an integer"}), 400

    # 设置ID的有效状态
    if valid == 1 or valid == -1:
        redis_client.hset(_id, "valid", valid)
    elif valid == 0:
        # 更新出现次数
        redis_client.hincrby(_id, "count", 1)
    else:
        return jsonify({"error": "Valid parameter must be 1, 0 or -1"}), 400

    return (
        jsonify(
            {
                "message": f"ID {_id} is now marked as {'valid' if valid == 1 else 'invalid' if valid == -1 else 'unconfirmed'}."
            }
        ),
        200,
    )


# 新增接口：获取ID的有效状态
@app.route("/get_valid", methods=["GET"])
def get_valid():
    _id = request.args.get("id")

    if _id is None:
        return jsonify({"error": "Missing id parameter"}), 400

    # 获取ID的有效状态
    valid_status = redis_client.hget(_id, "valid")

    return jsonify({"valid": (valid_status == "1")}), 200


# 新增接口：获取所有有效的ID
@app.route("/get_valid_ids", methods=["GET"])
def get_valid_ids():
    valid_ids = []

    # 使用SCAN命令遍历所有的ID
    cursor = "0"
    while cursor != 0:
        cursor, keys = redis_client.scan(cursor=cursor, match="*", count=100)
        for _id in keys:
            # 检查每个ID的有效性
            valid_status = redis_client.hget(_id, "valid")
            if valid_status == "1":
                valid_ids.append(_id)

    # 返回所有有效的ID
    return jsonify({"valid_ids": valid_ids}), 200


if __name__ == "__main__":
    # 启动Flask服务
    app.run(host="0.0.0.0", port=5000)
