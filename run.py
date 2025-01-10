import sys
import os
import mysql.connector
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import re
import datetime
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from wxcloudrun import app  # 导入 wxcloudrun 模块的 app 实例

# 配置日志
logging.basicConfig(filename='crawler.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ChromeDriver 正确路径 (服务器环境)
chrome_driver_path = '/usr/bin/chromedriver'

url = "https://quote.eastmoney.com/qihuo/v2505.html"

# 交易时间段 (小时, 分钟)
trading_times = [
    ((8, 59), (10, 15)),
    ((10, 30), (11, 30)),
    ((13, 30), (15, 00)),
    ((20, 59), (23, 00)),
]

last_saved_data = None

def is_trading_time():
    """检查当前时间是否在交易时间内"""
    now = datetime.datetime.now()
    current_time = (now.hour, now.minute)

    for start, end in trading_times:
        if start <= current_time <= end:
            return True
    return False

def get_sheet_name():
    """获取当前日期作为 Sheet 名称"""
    now = datetime.datetime.now()
    return now.strftime("%Y年%m月%d日")

def scrape_data():
    global last_saved_data
    try:
        logging.info("开始抓取数据...")
        # MySQL 数据库配置 (从环境变量中读取)
        mydb = mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST"),
            port=int(os.environ.get("MYSQL_PORT", 3306)),
            user=os.environ.get("MYSQL_USER"),
            password=os.environ.get("MYSQL_PASSWORD"),
            database=os.environ.get("MYSQL_DATABASE")
        )
        mycursor = mydb.cursor()
        logging.info("成功连接到数据库。")

        # 创建数据表（如果不存在）
        mycursor.execute("""
            CREATE TABLE IF NOT EXISTS pvc_data (
                time VARCHAR(255),
                price VARCHAR(255),
                arrow VARCHAR(255),
                volume VARCHAR(255),
                change_val VARCHAR(255),
                nature VARCHAR(255),
                date DATE
            )
        """)
        mydb.commit()
        logging.info("成功创建或连接数据表。")

        # 创建 Service 对象
        service = Service(executable_path=chrome_driver_path)
        # 配置 Chrome Options (Headless 模式)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # 创建 WebDriver 实例，使用 Service 和 Options
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        logging.info(f"成功打开网页：{url}")

        table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='sidertabbox' and contains(@style, 'margin-top: 10px;')]/div[@class='sidertabbox_c false']/table[@class='table1 pl3 undefined']"))
        )
        new_rows = []
        for row in table.find_elements(By.TAG_NAME, 'tr')[1:]:
            cells = row.find_elements(By.TAG_NAME, 'td')
            if len(cells) == 5:
                time_val = cells[0].text.strip()
                price_val = cells[1].text.strip()
                arrow = re.findall(r'[↑↓]', price_val)
                arrow = arrow[0] if arrow else ''
                price_val = re.sub(r'[↑↓]', '', price_val)
                volume_val = cells[2].text.strip()
                change_val = cells[3].text.strip()
                nature_val = cells[4].text.strip()
                new_rows.append([time_val, price_val, arrow, volume_val, change_val, nature_val])

        if new_rows:
            new_df = pd.DataFrame(new_rows, columns=['时间', '价格', '箭头', '现量', '仓差', '性质'])
            sheet_name = get_sheet_name()
            current_date = datetime.datetime.strptime(sheet_name, "%Y年%m月%d日").date()

            if last_saved_data is None or not new_df.equals(last_saved_data):
                for index, row in new_df.iterrows():
                    sql = "INSERT INTO pvc_data (time, price, arrow, volume, change_val, nature, date) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                    val = (row['时间'], row['价格'], row['箭头'], row['现量'], row['仓差'], row['性质'], current_date)
                    try:
                        mycursor.execute(sql, val)
                        mydb.commit()
                        logging.info(f"数据已插入数据库：{val}")
                    except mysql.connector.Error as err:
                        if err.errno == 1062:  # 处理重复数据插入的错误
                            pass
                        else:
                            logging.error(f"插入数据失败: {err}")
                logging.info(f"{sheet_name}数据已更新并保存到 MySQL。")
                last_saved_data = new_df.copy()
            else:
                logging.info("数据没有变化，跳过保存。")
        else:
            logging.info("没有抓取到数据")
        mycursor.close() #关闭cursor
        mydb.close() #关闭数据库连接
        driver.quit() #关闭driver
    except Exception as e:
        logging.error(f"抓取数据时发生错误：{e}")

# 创建后台调度器
scheduler = BackgroundScheduler()
# 每隔一段时间运行一次抓取任务（例如每分钟一次）
scheduler.add_job(func=scrape_data, trigger="interval", minutes=1)
scheduler.start()

# Flask 应用退出时关闭调度器
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def index():
    return "Hello from Flask!"

@app.route("/scrape")
def trigger_scrape():
    scrape_data()
    return "手动触发抓取完成！"

# 启动Flask Web服务(修改)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) #从环境变量PORT获取端口，如果没有则使用8080
