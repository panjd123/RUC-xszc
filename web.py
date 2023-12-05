from flask import Flask, render_template
import pandas as pd
import datetime
from main import sync_get_campus
import getpass
import configparser
import os.path as osp
import sys
import paramiko

app = Flask(__name__)


@app.route("/")
def index():
    mtime = (
        datetime.datetime.fromtimestamp(osp.getmtime("lec.csv"))
        if osp.exists("lec.csv")
        else datetime.datetime(1970, 1, 1)
    )
    ntime = datetime.datetime.now()
    if (ntime - mtime).seconds > 60 * 60 * 8:  # 8 hours
        df, _ = sync_get_campus()
        mtime = ntime
    else:
        df = pd.read_csv("lec.csv")
    full_slots_found = False
    df["insert"] = False
    for i, row in df.iterrows():
        if row["status"] == "名额已满":
            if not full_slots_found:
                df.loc[i, "insert"] = True
                full_slots_found = True
    df_dict = df.to_dict(orient="records")
    html = render_template(
        "index.html",
        data_dicts=df_dict,
        gen_time=mtime.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return html


def gen_html(file_path):
    with app.app_context():
        html = index()
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)


def gen_send_html():
    config = configparser.ConfigParser()
    config.read("config.ini")
    try:
        gen_html("lec.html")
    except Exception as e:
        print(e)
        return
    host = config["UPLOAD"]["host"]
    port = config["UPLOAD"]["port"]
    username = config["UPLOAD"]["username"]
    key = None
    if not config["UPLOAD"]["password"]:
        if osp.exists(config["UPLOAD"]["key_path"]):
            key = paramiko.Ed25519Key.from_private_key_file(
                config["UPLOAD"]["key_path"]
            )
        else:
            password = getpass.getpass("Password: ")
    else:
        password = config["UPLOAD"]["password"]
    print(
        "Connecting to %s@%s:%s with %s"
        % (username, host, port, "key" if key else "password")
    )
    transport = paramiko.Transport((host, int(port)))
    if key is not None:
        transport.connect(username=username, pkey=key)
    else:
        transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.put("lec.html", config["UPLOAD"]["target_path"])
    sftp.close()
    transport.close()
    print("Upload success")
    print("Visit %s" % config["UPLOAD"]["url"])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        # python web.py run
        gen_html("lec.html")
        app.run(debug=False)
    else:
        # python web.py send
        # df, text = sync_get_campus()
        # print(df)
        gen_send_html()
