#!/usr/bin/env python3

import feedparser
import time
import sqlite3
import requests
from datetime import datetime, timezone

sub = "xertunposting"
discordWebhookUrl = "eg"

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
        feedUrl = f"https://www.reddit.com/r/{self.subreddit}.rss"
        feed = feedparser.parse(feedUrl)
        return feed
    
    def PostToDiscord(self, post):
        author_name = post.author[3:]
        author_avatar_url = f"https://avatar-resolver.vercel.app/reddit/{author_name}"
        author_url = f"https://www.reddit.com/user/{author_name}"
        
        payload = {
            "username": "food eater 20",
            "avatar_url": "https://clipground.com/images/bread-loaf-png-3.png",
            "embeds": [
                {
                    "title": post.title,
                    "url": post.link,
                    "color": 16729344,
                    "author": {
                        "name": f"u/{author_name}",
                        "url": author_url,
                        "icon_url": author_avatar_url
                    },
                    "image": {
                        "url": post.media_thumbnail[0]["url"] if post.get("media_thumbnail") else None
                    },
                    "footer": {
                        "text": f"r/{self.subreddit} • Posted at {post.published}"
                    }
                }
            ]
        }
        response = requests.post(discordWebhookUrl, json=payload)
    
    @Loop
    def CheckPosts(self):
        feed = self.FetchFeed()
        if feed.entries:
            sortedEntries = sorted(feed.entries, key=lambda x: x.published_parsed, reverse=True)
            latestPost = sortedEntries[0]
            postId = latestPost.id
            postTime = datetime(*latestPost.published_parsed[:6], tzinfo=timezone.utc)
            
            if postId not in self.lastPostIds and postTime > self.botStartTime:
                print("New post detected:")
                print("Title:", latestPost.title)
                print("Link:", latestPost.link)
                print("Published:", latestPost.published)
                self.PostToDiscord(latestPost)
                self.UpdateLastPostIds(postId)
        else:
            print("No posts in feed.")
            
if __name__ == "__main__":
    feed = SubredditFeed(subreddit=sub)
    feed.CheckPosts()
