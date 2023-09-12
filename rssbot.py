#!/usr/bin/python3

# Mastodon Bot
# RSS Reader Poster

# RSSBOT by @mpoletiek
# https://enlightened.army/@mpoletiek
# 1: https://github.com/hanscees/mastodon-bot
#############

############
## RSSBOT ##
############
# RSS Bot for Enlightened.Army a Mastodon community
# Official Site: https://github.com/mpoletiek/mastodon_rss_bot
# Official RSS List: https://github.com/mpoletiek/mastodon_rss_bot/blob/main/rss_list.csv
# Official Feed: https://enlightened.army/@rssbot
############

###########
## NOTES ##
###########
# As you can probably guess tokens are stored in tokenlib_public.
# We use Mastodon.py to interact with a Mastodon instance.
#
# This script depends on 2 files
# 1. Source of RSS feeds. This comes from Github for now.
# 2. rssbot_last_run.txt: Do Not Touch. Modify at your own risk. A simple text file for keeping track of time.
###########

##################
## DEPENDENCIES ##
##################
import time, os, re, json, csv, requests

from mastodon import Mastodon
from datetime import datetime,timezone
from dateutil import parser

import feedparser
import tokenlib_public
##################

#####################
## SETUP VARIABLES ##
#####################
# botname is set in tokenlib_public.py
csv_url="./rss_list.csv"
temp_csv_path="./temp.csv"
last_run_path="./rssbot_lastrun.txt"
time_format_code = '%Y-%m-%d:%H:%M'
now_dt = datetime.utcnow() # had to turn everything to UTC
now_str = now_dt.strftime(time_format_code)
print("Now: "+now_str)

# Hashtags for toots, separate by spaces
#hashtagcontent = "#technews" #not used in my implementation

## Testing URL Hosted CSV
#r = requests.get(csv_url, stream = True)
temp_csv_path = csv_url #I used a local file with the RSS feeds, no need to retrieve from URL
# write the returned chunks to file
#with open(temp_csv_path,"wb") as tempcsv:
#    for chunk in r.iter_content(chunk_size=1024):
#         if chunk:
#             tempcsv.write(chunk)
#CREATE HASH FUNCTION - A QUICK WAY TO AVOID SOME HEADLINE EDITS THAT REPEATED THE SAME LINK AND BASICALLY DUPLICATED A POST. EACH LINK IS HASHED AND COMPARED TO A FILE CONTAINING THE LATEST 150 LINKS POSTED
def myHash(text:str):
  hash=0
  for ch in text:
    hash = ( hash*281  ^ ord(ch)*997) & 0xFFFFFFFF
  return hash




## GET LAST RUN ##
# Get the last time we ran this script
try:
    with open(last_run_path, "r") as myfile:
        data = myfile.read()
except:
    ## SET LAST RUN DATE ##
    #save value if we found new entries
    with open(last_run_path, "w") as myfile:
        myfile.write("%s" % (now_str))
    print("Wrote %s" % (last_run_path))
    # re-open file
    with open(last_run_path, "r") as myfile:
        data = myfile.read()

# Normalize date
print (data)
lr_dt = datetime.strptime(data,time_format_code)
lr_str = lr_dt.strftime(time_format_code)
print("Last Run: %s" % (lr_str))

lrgr_entry_count=0
################

## GET RSS FEED LIST ##
# reading the CSV file
target_feed = temp_csv_path
feed_list = []
with open(target_feed, mode ='r')as file:
  csvFile = csv.reader(file)
  for lines in csvFile:
        #print(lines)
        feed_list.append(lines)
#######################

# Helper function for discovering a feed's published date field
def getPubDate(entry):
    known_values = ['published', 'date','PubDate','updated','pubDate']
    this_pubdate = None
    for field in known_values:
        try: 
            this_pubdate = entry[field]
        except:
            pass

    if this_pubdate == None:
        print("Couldn't find entry date")    

    return this_pubdate

## GET RSS FEED & NEW ENTRIES ##
# Get feed, count entries
new_entries = []
# We read the hashlist from previous runs of the script
try:
    with open('hashlist.csv', newline='') as f:
        cf = csv.reader(f)
        hash_list = []
        for row in cf:
          hash_item = int(row[0])
          hash_list.append(hash_item) #hash_list = list(cf) list of lists
        print("Using existing hashlist")
except:
    print("Hash list empty")
    hash_list= []

for feed in feed_list:

    print("Feed: %s" % (feed))
    try:
        d = feedparser.parse(feed[0])
    except:
        print("Failed to parse RSS feed: %s" %(feed))

    print ("Found %s entries in RSS Feed." % (len(d['entries'])))
    # foreach entry, see if it's newer than last run
    for entry in d['entries']:
        # check multiple values for published date
        entry_dt_str = getPubDate(entry)
        entry_dt = None
        # Did we find an entry date?
        if entry_dt_str != None:
            entry_dt = parser.parse(entry_dt_str)
            entry_dt_str = entry_dt.strftime(time_format_code)
        # Normalize date
        new_dt = datetime.strptime(entry_dt_str,time_format_code)
        #print (new_dt, now_dt, lr_dt) #used to check times
        # Check if entry is new!
        # First make sure entry isn't in the future
        # Entry time is smaller than now time.
        # This means it was posted in the past.
        # We don't accept posts from the "future".
        if new_dt < now_dt:
            if new_dt > lr_dt: # Entry time is larger than last run time.
                lrgr_entry_count += 1
                print("New Entry: %s" % (entry['title']))
                # Check multiple values for entry link
                if entry['link']:
                    new_entries.append([entry['title'], entry['link'], entry_dt_str,d['feed']['title']])
                    #new_entries.append([entry['description'], entry['link'], entry_dt_str])
                elif entry['guid']:
                    new_entries.append([entry['title'], entry['guid'], entry_dt_str,d['feed']['title']])
                    #new_entries.append([entry['description'], entry['guid'], entry_dt_str])
###############################

## NEW ENTRIES FOUND ##
# If we find new entries, we'll attempt to post them
if len(new_entries) > 0:
    ####################################
    ## SETTING UP MASTODON CONNECTION ##
    ## modify tokenlib_pub.py for Auth #
    ####################################
    ## now lets get the tokens for our bot
    ## we choose pixey for now
    tokendict=tokenlib_public.getmytokenfor("mas.to")
    pa_token = tokendict["pa_token"]
    host_instance = tokendict["host_instance"]
    botname = tokendict["botname"]
    print("host instance is", host_instance)
    print("POSTING AS %s" %(botname))

    # we need this to use pythons Mastodon.py package
    mastodon = Mastodon(
        access_token = pa_token,
        api_base_url = host_instance
    )

    ## POST NEW ENTRIES ##
    toots_attempted_count=0
    # collect array of pubDates
    new_pubdates = []
    for toot in reversed(new_entries): #I reversed the order of new entries so older entries are posted first
        toots_attempted_count += 1
        print("Posting New Toot %s/%s in 20 seconds" % (toots_attempted_count, len(new_entries)))
        time.sleep(20)
        # the text to toot
        feed_raw = toot[0]
        sep = '<br /><img src'
        stripped1 = feed_raw.split(sep, 1)[0]
        sep1 = '<br /><video controls'
        stripped = stripped1.split(sep1, 1)[0]
        no_br = stripped.replace("<br />"," ")
        feed_link = toot[1]
        new_pubdates.append(toot[2])
        sep2 = '<'
        depurado = no_br.split(sep2, 1)[0] #All this because one site had html code inside the description field
        origen = toot[3]
        toottxt = "Origen: %s\n\n%s \n\n%s" % (origen, depurado, feed_link)
               
        # prepend botname to hashtags
        hashtag1 = "#" + botname

        #hashtags and toottext together
        post_text = str(toottxt) + "\n" # creating post text
        post_hash = (myHash(feed_link)) #we hash the link in the post
        if hash_list.count(post_hash)==0: #Only post if link has not been posted before
           #post_text = post_text[0:499] #commented. This was used to limit the lenght but URL were cut. Since Mastodon accepts very long URLs it's OK to have longer posts.
           print("%s\n" % (post_text))
           print("Hash:", str(post_hash))
           if len(hash_list)<150:
               hash_list.insert(0, post_hash)
               #hash_list.append(post_hash)
           else: #If we have reached the 150 hashes, we add the new one at the top and remove the last one
               hash_list.insert(0, post_hash)
               hash_list.pop()
           ## POST TOOT ##
           try: 
               mastodon.status_post(post_text)
               print("Toot posted")
           except:

               print("Failed to post to Mastodon")

        else:
           print("Duplicated toot. Did not post")
    # sort the pubdates
    new_pubdates.sort(reverse=True)
    print("Latest post date: %s" % (new_pubdates[0]))
    print("Number of hashes", str(len(hash_list)))
    with open('hashlist.csv', 'w') as file:
       writer = csv.writer(file)
       for val in hash_list:
           writer.writerow([val])
    with open(last_run_path, "w") as myfile:
        myfile.write("%s" % (new_pubdates[0]))

else:
    print("No New Entries")
######################
