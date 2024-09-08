#!/usr/bin/env python
# -*- coding:utf8 -*-

import datetime
import difflib
import json
import os
import pdb
import queue
import random
import threading
import time
import traceback
from collections import defaultdict

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from config import config


def string_similar(s1, s2):
    # exclude ' '
    return difflib.SequenceMatcher(lambda x: x == " ", s1, s2).quick_ratio()


def output_csv(data, full_file_path, cols_title=["组名", "帖子链接", "标题", "发布人链接", "发布人昵称", "最后回应时间"]):
    if ".csv" not in full_file_path:
        full_file_path = full_file_path + ".csv"

    try:
        df = pd.DataFrame(data, columns=cols_title)
        if not os.path.exists(full_file_path):
            df.to_csv(full_file_path, encoding="utf-8-sig", index=False)
        else:
            df.to_csv(full_file_path, encoding="utf-8", index=False, header=False, mode="a")

    except Exception:
        if os.path.exists(full_file_path):
            os.remove(full_file_path)
        raise


class DouBan(object):
    def __init__(self, cookies, groups, locations, house, city="beijing", date=7, filters=[]):
        self.cookies_ = cookies
        self.groups_ = groups
        self.locations_ = locations
        self.house_ = house
        self.date_ = date
        self.filters_ = filters
        self.headers_ = {
            "Host": "www.douban.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36",
            "Sec-Fetch-Dest": "document",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Referer": "https://www.douban.com/group/",
            #'Accept-Encoding': 'gzip, deflate, br',
            "Accept-Encoding": "",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cookie": self.cookies_,
        }
        self.ss_ = requests.Session()
        self.ss_.mount("http://", HTTPAdapter(max_retries=3))
        self.ss_.mount("https://", HTTPAdapter(max_retries=3))
        self.proxies_ = {"http": None, "https": None}

        self.topics_excluded_lock_ = threading.Lock()
        # filter topic_url visited
        self.topics_excluded_ = []
        self.topics_excluded_file_ = "./tmp/{0}.douban.spider.topics.excluded".format(city)

        # store topic_item what I want
        self.topics_satisfied_queue_ = queue.Queue(1000)
        # self.topics_satisfied_file_ = "./tmp/douban.spider.topics.satisfied"
        self.topics_satisfied_file_ = "./tmp/{0}.douban.spider.topics.satisfied.csv".format(city)

        # filter same person ,similar(same) title
        self.topics_similar_filter_lock_ = threading.Lock()
        # key is user, value is list of title
        self.topics_similar_filter_ = {}

        self.inited_ = False

        return

    def init(self):
        if self.inited_:
            return True
        with self.topics_excluded_lock_:
            if not os.path.exists(self.topics_excluded_file_):
                return True
            with open(self.topics_excluded_file_, "r") as fin:
                self.topics_excluded_ = json.loads(fin.read())
                print("DouBanSpider init, load {0} topics_excluded".format(len(self.topics_excluded_)))
                fin.close()
        return True

    def dump(self):
        while True:
            print("in dump")
            with self.topics_excluded_lock_:
                with open(self.topics_excluded_file_, "w") as fout:
                    fout.write(json.dumps(self.topics_excluded_))
                    print("dump topics_excluded to file, size is {0}".format(len(self.topics_excluded_)))
                    fout.close()

            while self.topics_satisfied_queue_.qsize() > 0:
                item = self.topics_satisfied_queue_.get(block=False)
                out_item = [
                    item.get("group"),
                    item.get("url"),
                    item.get("title"),
                    item.get("publish_user_url"),
                    item.get("publish_username"),
                    item.get("reply_datetime"),
                ]
                output_csv([out_item], self.topics_satisfied_file_)
                print("dump topics_satisfied to file, group:{0} topic: {1}".format(item.get("group"), item.get("url")))

            time.sleep(random.randint(5, 10))

    def add_excluded_topic(self, topic_url):
        with self.topics_excluded_lock_:
            self.topics_excluded_.append(topic_url)
        return

    def check_has_topic(self, topic_url):
        with self.topics_excluded_lock_:
            if topic_url in self.topics_excluded_:
                return True
            else:
                return False
        return False

    def check_similar_topic(self, topic_item):
        if not self.topics_similar_filter_ and os.path.exists(self.topics_satisfied_file_):
            result_dict = defaultdict(list)

            df = pd.read_csv(self.topics_satisfied_file_)
            for index, row in df.iterrows():
                result_dict[row["发布人链接"]].append(row["标题"])

            self.topics_similar_filter_ = dict(result_dict)

        with self.topics_similar_filter_lock_:
            url = topic_item.get("url")
            user = topic_item.get("publish_user_url")
            title = topic_item.get("title")
            if user not in self.topics_similar_filter_:
                self.topics_similar_filter_[user] = [title]
                return False
            else:
                old_titles = self.topics_similar_filter_.get(user)
                for ot in old_titles:
                    ratio = string_similar(title, ot)
                    if float(ratio) >= 0.8:
                        # maybe the same
                        print("found similar url:{0}".format(url))
                        return True
                self.topics_similar_filter_[user].append(title)
                return False
        return True

    def add_satisfied_topic(self, topic_item):
        if self.check_similar_topic(topic_item):
            return
        self.topics_satisfied_queue_.put(topic_item, block=False, timeout=1)
        return

    def spider_topic_detail(self, topic):
        results = []
        topic_url = topic.get("url")

        if self.check_has_topic(topic_url):
            return False
        else:
            self.add_excluded_topic(topic_url)

        if not topic_url:
            print("topic_url(empty) invalid")
            return False

        r = self.ss_.get(topic_url, headers=self.headers_, proxies=self.proxies_)
        print(">>> http get for url:{0}".format(topic_url))
        title, content = "", ""
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            sp_title = soup.find("table", "infobox")
            if sp_title:
                sp_title = sp_title.find("td", "tablecc")
                if len(sp_title) >= 2:
                    title = sp_title.contents[1]

            if not title:
                title = topic.get("title")
            sp_content = soup.find("div", "topic-richtext")
            if sp_content:
                if sp_content.p:
                    if len(sp_content.p.contents) > 0:
                        content = sp_content.p.contents[0]

            location_flag = False
            house_flag = False
            for loc in self.locations_:
                if title.find(loc) != -1 or content.find(loc) != -1:
                    location_flag = True
                    break

            if not location_flag:
                return False

            for h in self.house_:
                if title.find(h) != -1 or content.find(h) != -1:
                    house_flag = True
                    break
            if house_flag:
                print("spider topic satisfied: {0}".format(topic_url))
                print("title: {0}".format(title))
                print("content: {0}\n".format(content))
                return True

        return False

    def spider_topic_list(self, group):
        if not group:
            print("group(empty) invalid")
            return

        start = 0
        time_step = 3
        while True:
            time_step = random.randint(5, 10)
            time.sleep(time_step)
            try:
                topic_list = []
                url = "https://www.douban.com/group/{0}/discussion?start={1}".format(group, start)
                self.headers_["Referer"] = url
                r = self.ss_.get(url, headers=self.headers_, proxies=self.proxies_)
                print(">>> http get for url:{0}".format(url))
                now_time = int(time.time())
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "lxml")
                    trs = soup.find_all("tr")
                    for item in trs:
                        if len(item) < 4:
                            continue

                        tds = item.find_all("td")
                        if len(tds) != 4:
                            continue
                        if not tds[0].find("a"):
                            continue

                        topic_url = tds[0].a["href"]
                        title = tds[0].a["title"]
                        publish_user_url = tds[1].a["href"]
                        publish_username = tds[1].a.text
                        reply_time = tds[3].contents[0]  # 03-08 18:05
                        reply_year = datetime.date.today().year
                        reply_datetime = "{0}-{1}".format(reply_year, reply_time)

                        timeArray = time.strptime(reply_datetime, "%Y-%m-%d %H:%M")
                        reply_timestamp = int(time.mktime(timeArray))

                        topic = {
                            "group": group,
                            "url": topic_url,
                            "title": title,
                            "publish_user_url": publish_user_url,
                            "publish_username": publish_username,
                            "reply_datetime": reply_datetime,
                        }
                        topic_list.append(topic)

                        # 7 days or >10000 count reset start= 0
                        if (now_time - reply_timestamp) > 7 * 24 * 60 * 60 or start > 10000:
                            print("from beginning for group:{0}".format(url))
                            start = 0

                if not topic_list:
                    print("\033[1;31;40m found topic error for url:{0}".format(url))
                else:
                    print("found {0} topics for url:{1}".format(len(topic_list), url))

                for topic_item in topic_list:
                    # if not self.spider_topic_detail(topic_item):
                    #     continue
                    self.add_satisfied_topic(topic_item)
                    time.sleep(random.randint(5, 10))

                start += 30
            except Exception as e:
                print("\033[1;31;40m catch exception in spider_topic_list:{0}".format(e))
                traceback.print_exc()

        return

    def run(self):
        group_size = len(self.groups_)
        print("found {0} groups, will start to spider...".format(group_size))
        if not self.inited_:
            self.init()

        thread_list = []

        for group in self.groups_:
            sp_th = threading.Thread(target=self.spider_topic_list, args=(group,))
            sp_th.start()
            print("start thread:{0} for group:{1}".format(sp_th, group))
            thread_list.append(sp_th)

        dump_th = threading.Thread(target=self.dump)
        dump_th.start()
        print("start thread:{0} for dump".format(dump_th))
        thread_list.append(dump_th)

        while True:
            time.sleep(1)


def main(city):
    cookies = config.cookies
    if city == "beijing":
        groups = config.beijing_groups
        locations = config.locations
        house = config.house
    elif city == "shanghai":
        groups = config.shanghai_groups
        locations = config.locations
        house = config.house
    else:
        print("暂不支持该城市！")

    douban = DouBan(cookies, groups, locations, house, city)
    douban.run()


if __name__ == "__main__":
    # main("beijing")
    main("shanghai")
