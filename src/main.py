#!/usr/bin/env python3

import time
import sqlite3
import requests
import os
from datetime import datetime, timezone

sub = "xertunposting"
discordWebhookUrl = os.environ["F_WHOOK"]
cotdWebhook = os.environ["F_SWHOOK"]
cotdFlair = "cat of the day"

clientId = os.environ["F_ID"]
clientSecret = os.environ["F_SECRET"]
username = os.environ["F_USERNAME"]
password = os.environ["F_PASSWORD"]

agent = "FoodEater Bot"

def Loop(func):
    def Wrapper(*args, **kwargs):
        try:
            while True:
                func(*args, **kwargs)
                time.sleep(10)
        except KeyboardInterrupt:
            print("Stopping...")
    return Wrapper

class SubredditFeed:
    def __init__(self, subreddit) -> None:
        self.subreddit = subreddit
        self.conn = sqlite3.connect('reddit_posts.db')
        self.CreateTable()
        self.lastPostIds = self.GetLastPostIds()
        self.botStartTime = datetime.now(timezone.utc)
        self.token = self.Auth()

    def Auth(self):
        uri = "https://www.reddit.com/api/v1/access_token"
        auth = requests.auth.HTTPBasicAuth(clientId, clientSecret)
        headers = {"User-Agent": agent}
        data = {"grant_type": "password", "username": username, "password": password}

        res = requests.post(uri, auth=auth, data=data, headers=headers)
        if res.status_code == 200:
            token = res.json()["access_token"]
            print("Authenticated...")
            return token
        else:
            print(f"FAILED to authenticate!!!!!!: {res.status_code}")
            print(res.json())
            raise Exception("FAILED auth!!!")
        
    def CreateTable(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS last_posts (
                            subreddit TEXT,
                            post_ids TEXT
                        )''')
        self.conn.commit()
        
    def GetLastPostIds(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT post_ids FROM last_posts WHERE subreddit=?", (self.subreddit,))
        result = cursor.fetchone()
        if result:
            return result[0].split(',')
        else:
            return []
        
    def UpdateLastPostIds(self, postId):
        self.lastPostIds.append(postId)
        if len(self.lastPostIds) > 10:
            self.lastPostIds.pop(0)
        
        cursor = self.conn.cursor()
        cursor.execute("REPLACE INTO last_posts (subreddit, post_ids) VALUES (?, ?)", (self.subreddit, ','.join(self.lastPostIds)))
        self.conn.commit()
        
    def FetchFeed(self):
        feedUrl = f"https://oauth.reddit.com/r/{self.subreddit}.json"
        headers = {"User-Agent": agent, "Authorization": f"bearer {self.token}"}
        res = requests.get(feedUrl, headers=headers)
        if res.status_code == 200:
            return res.json()
        else:
            print(f"EPIC FAIL! code: {res.status_code}")
            print(res.json())
            return None
    
    def PostToDiscord(self, post, webhook):
        author_name = post['data']['author']
        author_avatar_url = f"https://avatar-resolver.vercel.app/reddit/{author_name}"
        author_url = f"https://www.reddit.com/user/{author_name}"

        video_url = None
        if (post['data'].get('is_video')):
            video_url = post['data']['media']['reddit_video']['fallback_url']

        image_url = post['data'].get('thumbnail')
        
        payload = {
            "username": "food eater 20",
            "avatar_url": "https://clipground.com/images/bread-loaf-png-3.png",
            "embeds": [
                {
                    "title": post['data'].get('title'),
                    "url": f"https://www.reddit.com{post['data']['permalink']}",
                    "color": 16729344,
                    "author": {
                        "name": f"u/{author_name}",
                        "url": author_url,
                        "icon_url": author_avatar_url
                    },
                    "image": {
                        "url": image_url
                    } if image_url.startswith('http') else {},
                    "video": {
                        "url": video_url if video_url else None
                    } if (video_url and video_url.startswith('http') and (post['data'].get('is_video'))) else {},
                    "footer": {
                        "text": f"r/{self.subreddit} • Posted at {datetime.fromtimestamp(post['data']['created_utc'], tz=timezone.utc)}"
                    }
                }
            ]
        }
        response = requests.post(webhook, json=payload)
    
    @Loop
    def CheckPosts(self):
        feed = self.FetchFeed()
        if feed and 'data' in feed and 'children' in feed['data']:
            for post in feed['data']['children']:
                postId = post['data']['id']
                postTime = datetime.fromtimestamp(post['data']['created_utc'], tz=timezone.utc)
                flair = post['data'].get('link_flair_text')

                if postId not in self.lastPostIds and postTime > self.botStartTime:
                    if flair == cotdFlair:
                        print("COTD detected:")
                        print("Title:", post['data']['title'])
                        print("Link:", f"https://www.reddit.com{post['data']['permalink']}")
                        print("Published:", postTime)
                        print("Flair:", flair)
                        self.PostToDiscord(post, cotdWebhook)
                    else:
                        print("New post detected (without specific flair):")
                        print("Title:", post['data']['title'])
                        print("Link:", f"https://www.reddit.com{post['data']['permalink']}")
                        print("Published:", postTime)
                        print("Flair: ", flair)
                        self.PostToDiscord(post, discordWebhookUrl)
                    self.UpdateLastPostIds(postId)
        else:
            print("No posts in feed (or failed lol).")
            
if __name__ == "__main__":
    feed = SubredditFeed(subreddit=sub)
    feed.CheckPosts()
