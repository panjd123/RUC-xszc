from flask import Flask, render_template, g
import pandas as pd
import datetime
from main import sync_get_lectures, get_added_lectures, gen_keyinfo, gen_text
import sqlite3
import sys
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from gunicorn.app.wsgiapp import WSGIApplication
import logging
from logging.handlers import RotatingFileHandler
from timeit import default_timer as timer

app = Flask(__name__)
scheduler = BackgroundScheduler()

DATABASE = "lec.db"

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("xszc")
handler = RotatingFileHandler("web.log", maxBytes=10000)
formatter = logging.Formatter(
    "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

sender_email = os.environ.get("SENDER_EMAIL", None)
sender_password = os.environ.get("SENDER_PASSWORD", None)


def get_receiver_emails():
    receiver_emails = []

    if os.path.exists("./receiver_emails.txt"):
        receiver_emails = open("./receiver_emails.txt").read().splitlines()

    if sender_email not in receiver_emails:
        receiver_emails.insert(0, sender_email)

    return receiver_emails


def get_db():
    if not hasattr(g, "_database"):
        db = sqlite3.connect(DATABASE)
        g._database = db
    else:
        db = g._database
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    sync_get_lectures()
    df = pd.read_json("lec.json", orient="records")
    db = sqlite3.connect(DATABASE)
    df.to_sql("lectures", db, if_exists="replace", index=False)
    db.commit()
    db.close()


def store_dataframe(df):
    db = get_db()
    df.to_sql("lectures", db, if_exists="replace", index=False)
    db.commit()


def load_dataframe():
    db = get_db()
    df = pd.read_sql_query("SELECT * FROM lectures", db)
    return df


def notify_new_lectures(added_df):
    if not sender_email or not sender_password:
        logger.info("No email configured, skip sending email")
        return

    with app.app_context():
        html = index(added_df)
        key = gen_keyinfo(added_df)
        msg = MIMEMultipart("alternative")
        if key:
            msg["Subject"] = "[形策讲座] " + key
        else:
            msg["Subject"] = "[形策讲座] 服务器测试"
        msg["From"] = sender_email

        part1 = MIMEText(html, "html")
        msg.attach(part1)

        with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
            server.login(sender_email, sender_password)
            for receiver_email in get_receiver_emails():
                msg["To"] = receiver_email
                server.sendmail(sender_email, receiver_email, msg.as_string())
                logger.info("Email sent to %s", receiver_email)


def update_db(force_notification=False):
    with app.app_context():
        logger.info("Update started")
        df, text = sync_get_lectures()
        logger.info("Update finished, %d lectures found", len(df))
        db = get_db()
        old_df = load_dataframe()
        df.to_sql("lectures", db, if_exists="replace", index=False)
        db.commit()
        added_df = get_added_lectures(df, old_df)

        if force_notification:
            logger.info("Force notification")
            notify_new_lectures(df)
        elif len(added_df) > 0:
            logger.info("New lectures found, notify")
            notify_new_lectures(added_df)


@app.route("/")
def index(df=None):
    if df is None:
        df = load_dataframe()
        logger.info("Index request received, %d lectures returned", len(df))
    mtime = df["update"].max() if len(df) else None
    full_slots_found = False
    df["insert"] = False
    for i, row in df.iterrows():
        if row["status"] == "名额已满":
            if not full_slots_found:
                df.loc[i, "insert"] = True
                full_slots_found = True
        if row["status"] == "取消报名":
            df.loc[i, "status"] = "网站作者已报名，无法查看剩余名额"
        if row["status"] == "取消候补报名":
            df.loc[i, "status"] = "网站作者已报名，无法查看剩余名额"
    df_dict = df.to_dict(orient="records")
    gen_time = (
        datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        if mtime
        else "Unknown"
    )
    html = render_template(
        "index.html",
        data_dicts=df_dict,
        gen_time=gen_time,
    )
    return html


@app.route("/donate")
def donate():
    return render_template("donate.html")


def gen_html(file_path):
    with app.app_context():
        html = index()
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)


class StandaloneApplication(WSGIApplication):
    def __init__(self, application, options=None):
        self.application = application
        self.options = options or {}
        super(StandaloneApplication, self).__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


if __name__ == "__main__":
    SCHEDULE_INTERVAL = 120

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_db()
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        scheduler.add_job(update_db, "interval", seconds=SCHEDULE_INTERVAL)
        scheduler.start()
        update_db(force_notification=True)
        options = {
            # "bind": "%s:%s" % ("10.47.251.153", "8000"),
            "bind": "%s:%s" % ("127.0.0.1", "8000"),
            "workers": 4,
        }
        StandaloneApplication(app, options).run()
    elif len(sys.argv) > 1 and sys.argv[1] == "performance":
        with app.app_context():
            tic = timer()
            html = index()
            print(html)
            toc = timer()
            print("Time elapsed: ", toc - tic)
    # elif len(sys.argv) > 1 and sys.argv[1] == "test":
    #     from ruclogin import get_cookies, check_cookies
    #     for i in range(5):
    #         cookies = get_cookies()
    #         if not check_cookies(cookies):
    #             print("Error")
    #             exit(1)
    #         else:
    #             print(f"{i} Pass")
    else:
        scheduler.add_job(update_db, "interval", seconds=SCHEDULE_INTERVAL)
        scheduler.start()
        update_db(force_notification=True)
        app.run(host="0.0.0.0", debug=True)
