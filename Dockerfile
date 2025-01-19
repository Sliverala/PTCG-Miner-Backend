# 使用官方 Python 镜像作为基础镜像
FROM python:3.12-slim

# 设置工作目录为 /app
WORKDIR /app

# 复制当前目录的所有内容到容器的 /app 目录
COPY . /app

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 Flask 默认端口
EXPOSE 5000

# 设置容器启动时运行的命令
CMD ["python", "main.py"]
