FROM python:3.9-slim-buster 
# 更换基础镜像，alpine镜像对selenium支持不好

# 容器默认时区为UTC，如需使用上海时间请启用以下时区设置命令
RUN apt-get update && apt-get install -y tzdata && \ # 修改安装方式
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 安装必要的系统依赖(selenium需要)
RUN apt-get install -y wget unzip chromium-browser

# 下载并安装 ChromeDriver (根据你的 Chrome 版本选择合适的版本)
RUN wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE/chromedriver_linux64.zip
RUN unzip chromedriver_linux64.zip
RUN mv chromedriver /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver

# 拷贝当前项目到/app目录下（.dockerignore中文件除外）
COPY . /app

# 设定当前的工作目录
WORKDIR /app

# 安装依赖
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple 
#使用国内镜像源加速
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 设置环境变量（在云托管控制台设置）
# ENV MYSQL_HOST=your_mysql_host
# ENV MYSQL_PORT=3306
# ENV MYSQL_USER=your_mysql_user
# ENV MYSQL_PASSWORD=your_mysql_password
# ENV MYSQL_DATABASE=your_mysql_database

# 暴露端口。使用 8080 端口，与 Gunicorn 绑定一致
EXPOSE 8080

# 执行启动命令,使用Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "run:app"]