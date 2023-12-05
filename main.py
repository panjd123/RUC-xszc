from rucpost import get_data, get_data_async, get_infos, get_infos_async
import asyncio


async def get_campus():
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
    VALID_STATUS = ["我要报名", "候补报名", "活动即将开始", "取消报名", "取消候补报名", "名额已满"]

    df = await get_data_async(1000, pageSize=50)
    df.to_csv("data.csv", index=False)

    activities = df.query(
        "(progressname == '报名中' or progressname == '报名未开始') and typelevel3 == 108"
    )[INFO_COLUMNS]

    aids = activities["aid"].values
    if len(aids) == 0:
        infos = [None, None, None]
    else:
        infos = await get_infos_async(aids)

    activities[["status", "slots", "left_slots"]] = infos

    valid_activities = activities[activities["status"].isin(VALID_STATUS)]

    valid_activities = valid_activities.sort_values(by=["begintime"])

    index = valid_activities["status"].apply(lambda x: VALID_STATUS.index(x))

    valid_activities = valid_activities.iloc[index.argsort()]

    valid_activities = valid_activities.sort_values(by="left_slots", ascending=False)

    urls = [
        f"https://v.ruc.edu.cn/campus#/activity/partakedetail/{aid}/show"
        for aid in valid_activities["aid"]
    ]
    valid_activities

    valid_activities["url"] = urls
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
        for _, row in valid_activities.iterrows()
    ]

    text = "\n\n".join(text)

    valid_activities.to_csv("lec.csv", index=False)

    return valid_activities, text


def sync_get_campus():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(get_campus())


if __name__ == "__main__":
    df, text = sync_get_campus()
    print(text)
