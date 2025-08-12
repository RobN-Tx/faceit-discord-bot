'''Config file for mapcore faceit discord bot'''
import os

#discord bot tokens
BOT_TOKEN = dict(
    main = "put discord bot token here",
    dev = "put discord bot token here"
)

#local demo storage location
STORAGE_LOCATION = os.environ['HOME']+"/"

#cloud storage for demo info - using google
CLOUD_BUCKET = "mapcore-demos"
CLOUD_PROJECT = "google cloud project if here"

#faceit api token if doing/able to do demo downloads
API_TOKEN = "faceit demo api token here"

# put a dictionary of the hubs/blubs you want to watch
HUBS_DICT = dict(
    HUBNAME = {"guid":"hub guid here",
          "message_players":7,
          "max_players":10},
    WingmanHUB = {"guid":"hub guid here",
          "message_players":3,
          "max_players":4},

)

#discord channel name
CHANNEL_NAME = "hub-looking-for-players"
#channel for summary chart every friday
FRIDAY_CHANNEL_NAME = "hub-chat-and-help"


#faceit api urls
FACEITQUEUE = "https://api.faceit.com/queue/v1/queue/hub/"
STATS_URL = "https://api.faceit.com/stats/v1/stats/matches/"
MATCH_URL = "https://api.faceit.com/match/v2/match/"
DEMO_REQUEST_URL = "https://open.faceit.com/download/v2/demos/download"

DEMO_SERVER = "https://storage.googleapis.com/mapcore-demos/mapcore/"#/"

#for our discord these are the emoji ids for the facit levels
FACEIT_LEVELS = {1: "<:level1:741416090407665844>",
                         2: "<:level2:741416090076315669>",
                         3: "<:level3:741416090034372670>",
                         4: "<:level4:741416090420379738>",
                         5: "<:level5:741416090353008720>",
                         6: "<:level6:741416090407665854>",
                         7: "<:level7:741416090298482770>",
                         8: "<:level8:741416090617511956>",
                         9: "<:level9:741416090483032245>",
                         10: "<:level10:741416090516586526>"
}

#info passed to the bot via the webhook to make sure its the faceit webhooks
USER_AGENT = "faceit-webhooks/1.0"
WIBBLE = "secret-squirrel"

#dictionary to convert from the faceit match states to a more human readable version
MATCH_STATE = {
    "CONFIGURING": "Configuring match",
    "READY": "Warm up",
    "ONGOING": "Ongoing match",
    "CANCELLED": "Cancelled",
    "FINISHED": "Finished"
}
