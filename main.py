from rucpost import get_data, get_data_async, get_infos, get_infos_async
import asyncio
import pandas as pd
from timeit import default_timer as timer


def get_added_lectures(new_lectures, old_lectures):
    added_lectures = []
    for _, lecture in new_lectures.iterrows():
        if lecture["aid"] not in old_lectures["aid"].values:
            added_lectures.append(lecture)
            continue
        old_lecture = old_lectures[old_lectures["aid"] == lecture["aid"]].iloc[0]
        if lecture["status"] != old_lecture["status"]:
            added_lectures.append(lecture)
    added_lectures = pd.DataFrame(added_lectures)
    if not added_lectures.empty:
        added_lectures = added_lectures[
            added_lectures["status"].isin(["我要报名", "候补报名"])
        ]
    return added_lectures


def gen_keyinfo(lecs_df: pd.DataFrame):
    lecs_df = lecs_df[lecs_df["status"].isin(["我要报名", "候补报名"])]
    text = "\n".join(
        f"({p}, {n}, {b})"
        for p, n, b in zip(
            lecs_df["partakemodename"], lecs_df["allowednum"], lecs_df["begintime"]
        )
    )
    return text


def gen_text(lecs_df: pd.DataFrame):
    text = [
        f"""{row['aname']}
    开始时间：{row['begintime']}
    结束时间：{row['endtime']}
    地点：{row['location']}
    点名方式：{row['partakemodename']}
    状态：{row['status']}
    剩余名额：{row['left_slots']}
    简介：{row['abstract']}
    url: {row['url']}
    """
        for _, row in lecs_df.iterrows()
    ]
    return "\n\n".join(text)


async def get_lectures():
    INFO_COLUMNS = [
        "aid",
        "aname",
        "abstract",
        "begintime",
        "endtime",
        "location",
        "partakemodename",
        "poster",
    ]
    VALID_STATUS = [
        "我要报名",
        "候补报名",
        "活动即将开始",
        "取消报名",
        "取消候补报名",
        "名额已满",
    ]
    df = await get_data_async(300, pageSize=30)
    # df.to_csv("data.csv", index=False)

    lectures = df.query(
        "(progressname == '报名中' or progressname == '报名未开始') and typelevel3 == 108"
    )[INFO_COLUMNS]

    aids = lectures["aid"].values
    if len(aids) == 0:
        infos = [None, None, None]
    else:
        infos = await get_infos_async(aids)

    lectures[["status", "slots", "left_slots"]] = infos

    valid_lectures = lectures[lectures["status"].isin(VALID_STATUS)]

    valid_lectures = valid_lectures.sort_values(by=["begintime"])

    index = valid_lectures["status"].apply(lambda x: VALID_STATUS.index(x))

    valid_lectures = valid_lectures.iloc[index.argsort()]

    valid_lectures = valid_lectures.sort_values(by="left_slots", ascending=False)

    urls = [
        f"https://v.ruc.edu.cn/campus#/activity/partakedetail/{aid}/show"
        for aid in valid_lectures["aid"]
    ]

    valid_lectures["url"] = urls

    text = gen_text(valid_lectures)

    valid_lectures["update"] = int(pd.to_datetime("now", utc=True).timestamp())

    valid_lectures.to_json("lec.json", orient="records", force_ascii=False)

    return valid_lectures, text


def sync_get_lectures():
    lectures, text = asyncio.run(get_lectures())
    if len(lectures) == 0:
        lectures.loc[0, "aname"] = "当前没有任何讲座"
        lectures.loc[0, "abstract"] = "不知道这个时候放什么图片合适"
        lectures.loc[0, "poster"] = (
            # "https://img1.baidu.com/it/u=1988686668,1486343908&fm=253&fmt=auto&app=138&f=JPEG?w=500&h=500"
            "/static/vme1.png"
        )
        lectures.loc[0, "url"] = "https://v.ruc.edu.cn//campus#/search"
        lectures.loc[0, "update"] = int(pd.to_datetime("now", utc=True).timestamp())
    return lectures, text


if __name__ == "__main__":
    tic = timer()
    df, text = sync_get_lectures()
    toc = timer()
    print(df)
    print(f"Costs {toc - tic} seconds")
