import requests
import asyncio
import aiohttp
import pandas as pd
import re
import json
from ruclogin import get_cookies, check_cookies

cookies = get_cookies()

headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://v.ruc.edu.cn",
    "Referer": "https://v.ruc.edu.cn/campus",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

data = {
    "perpage": "200",
    "page": "1",
    "typelevel1": "95",
    "typelevel2": "22",
    "typelevel3": "0",
    "applyscore": "0",
    "begintime": "",
    "location": "",
    "progress": "0",
    "owneruid": "",
    "sponsordeptid": "",
    "query": "",
    "canregist": "0",
}


def get_data(num=200):
    p_data = data.copy()
    p_data["perpage"] = str(num)
    response = requests.post(
        "https://v.ruc.edu.cn/campus/v2/search",
        cookies=cookies,
        headers={},
        data=p_data,
    )
    df = pd.DataFrame(response.json()["data"]["data"])

    return df


async def get_page_async(session, p_data):
    try:
        async with session.post(
            "https://v.ruc.edu.cn/campus/v2/search",
            cookies=cookies,
            headers={},
            data=p_data,
        ) as response:
            j = await response.json()
            return j["data"]["data"]
    except Exception as e:
        print(e)
        print(response.text())


async def get_data_async(num=1000, pageSize=20):
    global cookies
    cookies = get_cookies()
    async with aiohttp.ClientSession() as session:
        tasks = []
        pages = num // pageSize + 1
        for page in range(1, pages + 1):
            p_data = data.copy()
            p_data["perpage"] = str(pageSize)
            p_data["page"] = str(page)
            tasks.append(get_page_async(session, p_data))
        results = await asyncio.gather(*tasks)
        df = pd.DataFrame(sum(results, []))
        return df


def get_info(aid=32779):
    response = requests.post(
        "https://v.ruc.edu.cn/campus/Regist/Info",
        cookies=cookies,
        headers={},
        data={"aid": str(aid)},
    )
    try:
        j = response.json()
        data = j["data"]
        msg = response.json()["msg"]
        if data == "我要报名":
            # 距报名结束还有<span class="bold">2</span>天，已有158人报名，剩余92个报名名额
            info = re.findall(
                r'距报名结束还有<span class="bold">(\d+)</span>天，已有(\d+)人报名，剩余(\d+)个报名名额',
                msg,
            )[0]
            return data, info[1], info[2]
        else:
            return data, "0", "0"
    except Exception as e:
        print(e)
        print(response.json())
        return "error", "0", "0"


def get_infos(aids):
    result = []
    for aid in aids:
        result.append(get_info(aid))
    return result


async def get_info_async(session, aid=32779):
    async with session.post(
        "https://v.ruc.edu.cn/campus/Regist/Info",
        cookies=cookies,
        headers={},
        data={"aid": str(aid)},
    ) as response:
        try:
            j = await response.text()
            j = json.loads(j)
            data = j["data"]
            msg = j["msg"]
            if data == "我要报名":
                # 距报名结束还有<span class="bold">2</span>天，已有158人报名，剩余92个报名名额
                info = re.findall(
                    r'距报名结束还有<span class="bold">(\d+)</span>天，已有(\d+)人报名，剩余(\d+)个报名名额',
                    msg,
                )[0]
                return [data, info[1], info[2]]
            elif data == "候补报名":
                # 距报名结束还有<span class="bold">1</span>天，还有30个候补机会
                info = re.findall(
                    r"距报名结束还有<span class=\"bold\">(\d+)</span>天，还有(\d+)个候补机会",
                    msg,
                )[0]
                return [data, "unknown", info[1]]
            else:
                return [data, "unknown", "0"]
        except Exception as e:
            print(e)
            return "error", "unknown", "unknown"


async def get_infos_async(aids):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for aid in aids:
            tasks.append(get_info_async(session, aid))
        results = await asyncio.gather(*tasks)
        return results


if __name__ == "__main__":
    print(asyncio.run(get_infos_async([32716, 32694, 32796, 32781, 32779])))
