#!/usr/bin/env python3

import time
import sqlite3
import requests
import os
import subprocess
import hashlib
from datetime import datetime, timezone

sub = os.environ["F_SUBREDDIT"]
discordWebhookUrl = os.environ["F_WHOOK"]
cotdWebhook = os.environ["F_SWHOOK"]
cotdFlair = os.environ["F_FLAIR"]

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

gitHashShort = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("ascii").strip()
gitBranch    = subprocess.check_output(["git", "symbolic-ref", "HEAD"]).decode("ascii").strip()

class SubredditFeed:
    def __init__(self, subreddit) -> None:
        self.subreddit = subreddit
        self.conn = sqlite3.connect('reddit_posts.db')
        self.CreateTable()
        self.token = self.Auth()
        self.botStartTime = datetime.now(timezone.utc)
        self.cachedHashes = []

    def Auth(self):
        uri = "https://www.reddit.com/api/v1/access_token"
        auth = requests.auth.HTTPBasicAuth(clientId, clientSecret)
        headers = {"User-Agent": agent}
        data = {"grant_type": "password", "username": username, "password": password, "duration": "permanent"}

        res = requests.post(uri, auth=auth, data=data, headers=headers)
        if res.status_code == 200:
            json = res.json()
            print("Authenticated: ", json["access_token"])
            return json["access_token"]
        else:
            print(f"FAILED to authenticate!!!!!!: {res.status_code}")
            print(res.json())
            raise Exception("FAILED auth!!!")

    def Refresh(self):
        self.token = self.Auth()
        
    def CreateTable(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS post_hashes (
                            hash TEXT PRIMARY KEY NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                        )''')
        self.conn.commit()

    def DBTime(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT MIN(created_at) FROM post_hashes")
        result = cursor.fetchone()[0]
        if result:
            time = datetime.fromisoformat(result).replace(tzinfo=timezone.utc)
            return time
        else:
            return self.botStartTime
        
    def Validate(self, permalink: str) -> bool:
        hash = hashlib.sha256(permalink.encode()).hexdigest()
        if hash in self.cachedHashes: return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM post_hashes WHERE hash=?", (hash,))
        result = cursor.fetchone()

        if result: return False

        cursor.execute("INSERT INTO post_hashes (hash) VALUES (?)", (hash,))
        self.conn.commit()

        self.cachedHashes.append(hash)
        if len(self.cachedHashes) > 4:
            self.cachedHashes.pop(0)

        return True

    def FetchAvatar(self, user: str) -> str:
        #url = f"https://api.reddit.com/user/{user}/about.json"
        #headers = {"User-Agent": agent, "Authorization": f"bearer {self.token}"}
        #res = requests.get(url, headers=headers)
        #if res.status_code == 401:
        #    self.Refresh()
        #    headers['Authorization'] = f"bearer {self.token}"
        #    res = requests.get(feedUrl, headers=headers)
#
        #if res.status_code == 200:
        #    uri = res.json()['data']['icon_img']
        #    parsed_uri = urlsplit(uri)
        #    return urlunsplit((parsed_uri.scheme, parsed_uri.netloc, parsed_uri.path, '', ''))
        #else:
        #    print(f"EPIC FAIL! code: {res.status_code}")
        #    print(res.json())
        #    return None

        return "https://www.redditstatic.com/avatars/defaults/v2/avatar_default_7.png" # avatar issues....

        
    def FetchFeed(self):
        feedUrl = f"https://oauth.reddit.com/r/{self.subreddit}.json"
        headers = {"User-Agent": agent, "Authorization": f"bearer {self.token}"}
        res = requests.get(feedUrl, headers=headers)
        if res.status_code == 401:
            self.Refresh()
            headers['Authorization'] = f"bearer {self.token}"
            res = requests.get(feedUrl, headers=headers)

        if res.status_code == 200:
            return res.json()
        else:
            print(f"EPIC FAIL! code: {res.status_code}")
            print(res.json())
            return None
    
    def PostToDiscord(self, post, webhook):
        author_name = post['data']['author']
        author_avatar_url = self.FetchAvatar(author_name)
        author_url = f"https://www.reddit.com/user/{author_name}"

        video_url = None
        if (post['data'].get('is_video')):
            video_url = post['data']['media']['reddit_video']['fallback_url']

        image_url = post['data'].get('thumbnail')
        
        payload = {
            "username": f"food eater 20",
            "avatar_url": "https://clipground.com/images/bread-loaf-png-3.png",
            "embeds": [
                {
                    "title": post['data'].get('title'),
                    "url": f"https://www.reddit.com{post['data']['permalink']}",
                    "color": 16729344,
                    "author": {
                        "name": f"u/{author_name} on r/{self.subreddit}",
                        "url": author_url,
                        "icon_url": author_avatar_url
                    },
                    "image": {
                        "url": image_url
                    } if image_url.startswith('http') else {},
                    "description": "Unfortunately Reddit videos don't store audio (idk why). The video link sent has no audio." if (video_url != None) else "",
                    "footer": {
                        "text": f"• r/{self.subreddit}\n• Posted at {datetime.fromtimestamp(post['data']['created_utc'], tz=timezone.utc)}\n• Version: Commit #{gitHashShort} on {gitBranch}",
                    }
                }
            ]
        }
        response = requests.post(webhook, json=payload)

        if (video_url != None):
            video_payload = {
                "username": f"food eater 20 ({gitHashShort})",
                "avatar_url": "https://clipground.com/images/bread-loaf-png-3.png",
                "content": video_url
            }

            response2 = requests.post(webhook, json=video_payload)
    
    @Loop
    def CheckPosts(self):
        feed = self.FetchFeed()
        if feed and 'data' in feed and 'children' in feed['data']:
            time = self.DBTime()

            for post in feed['data']['children']:
                postTime = datetime.fromtimestamp(post['data']['created_utc'], tz=timezone.utc)
                if (postTime <= time): 
                    continue

                permalink = post['data']['permalink']
                flair = post['data'].get('link_flair_text')

                if self.Validate(permalink):
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
        else:
            print("No posts in feed (or failed lol).")
            
if __name__ == "__main__":
    feed = SubredditFeed(subreddit=sub)
    feed.CheckPosts()
