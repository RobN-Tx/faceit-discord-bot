'''file to hold helper functions'''
import json
import requests
import matplotlib.pyplot as plt
import config
import os.path
import datetime

from google.cloud import storage

def setup_processor(cl_args):
    '''Function to process the command line arguements
    If they exist'''

    print ("This is the name of the script= ", cl_args[0])
    print("Number of arguments= ", len(cl_args))
    print("all args= ", str(cl_args))

    if len(cl_args) < 2:
        version = "main"
    else:
        version = cl_args[1]
    
    if len(cl_args) <3:
        location = "local"
    else:
        location = cl_args[2]

    token = config.BOT_TOKEN[version]

    #if len(cl_args) < 3:
    #    logger_level = logging.ERROR
    #else:
    #    logger_level = logging.DEBUG

    return_dict = {"token": token,
                   "logger_level": "DEBUG",
                   "version":version}

    return return_dict


def queue_length(hub, logger):
    '''
    depreicated
    
    function that is passed the hub name and logger
    Does API call to faceit hub to get number of players in the queue
    Returns message or logs the error if there is an issue'''
    number_of_players = "API Error"

    try:
        response = requests.get(config.FACEITQUEUE + config.HUBS_DICT[hub]["guid"], timeout=5)
        if len(response.text) > 0:
            data = json.loads(response.text)
            number_of_players = str(data["payload"][0]["noOfPlayers"])

    except Exception as e:
        error_string = f'Error in queue_length, {e}'
        logger.error(error_string)

    return_message = f'Players in {hub} Queue: {number_of_players}'

    return return_message


def queue_players(hub, logger):
    '''function that is passed the hub name and logger
    Does API call to faceit hub to get number of players in the queue
    Returns message or logs the error if there is an issue'''
    number_of_players = 0

    try:
        response = requests.get(config.FACEITQUEUE + config.HUBS_DICT[hub]["guid"], timeout=15)
        if len(response.text) > 0:
            data = json.loads(response.text)
            number_of_players = str(data["payload"][0]["noOfPlayers"])

    except Exception as e:
        logger.error("Error in queue_length", e)

    return number_of_players


def get_queue_counts(input_dict, logger):
    '''function to get the status of queues 
    then return a dictionary for triggering message to discord'''

    for hub_name, hub_info in config.HUBS_DICT.items():
        players = 0
        test = False
        message = ""

        players = queue_players(hub_name, logger)

        if int(players) > hub_info["message_players"]:
            input_dict[hub_name]["timer"] = input_dict[hub_name]["timer"] + 1
            test = True
        else:
            input_dict[hub_name]["timer"] = 0

        plural = "" if players == hub_info["max_players"] - 1 else "s"

        missing = hub_info["max_players"] - int(players)

        message = f'Mapcore {hub_name} hub needs {missing} more player{plural}'

        input_dict[hub_name] = {"players": players,
                                "timer": input_dict[hub_name]["timer"],
                                "test": test,
                                "message": message}

    return input_dict


def build_input_dict():
    '''build the initial input dict for get_queue_counts'''
    input_dict = {}
    for hub_name in config.HUBS_DICT:
        input_dict[hub_name] = {"players": 0,
                                "timer": 0,
                                "test": False,
                                "message": 0}

    return input_dict


def build_activity_string(input_dict):
    '''build activity string'''
    na_num = input_dict["NA"]["players"]
    eu_num = input_dict["EU"]["players"]
    naw_num = input_dict["NAWingman"]["players"]
    euw_num = input_dict["EUWingman"]["players"]
    sa_num = input_dict["SA"]["players"]
    activity_string = f"Qs(WingQ): NA-{na_num}({naw_num}) EU-{eu_num}({euw_num}) SA-{sa_num}"

    return activity_string


def divide_chunks(l, n):
    '''some google fu magic to split a long list into smaller chunked lists'''
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i:i + n]


def process_games(db_games):
    '''process the dictionary of games into a list for display elsewhere'''
    list_of_games = []
    # process games and save message line to list_of_games
    for match_id, game in db_games.items():
        
        #logic to catch if the date is an int or a string and convert to string
        
        if type(game["date"]) == int:
            game["date"] = str(datetime.datetime.fromtimestamp(game["date"]).strftime('%Y-%m-%d'))
        else:
            game["date"] = game["date"][:10]
        
        

        final_score = str(game["stats"]["CT_1st"]["final_score"]) + " - " + str(game["stats"]["T_1st"]["final_score"])
        map_name = game["map_name"]
        
        path = f"e://mapcore/{map_name}/{match_id}.dem.gz"
        proper_map_name_list = map_name.split(" ")

        if len(proper_map_name_list) == 1:
            storage_name = map_name.capitalize()
            url_map_name = map_name.capitalize()
        elif len(proper_map_name_list) == 2:
            storage_name = proper_map_name_list[0].upper() + " " + proper_map_name_list[1].capitalize()
            url_map_name = proper_map_name_list[0].upper() + "%20" + proper_map_name_list[1].capitalize()
        elif len(proper_map_name_list) == 3:
            storage_name = proper_map_name_list[0].upper() + " " + proper_map_name_list[1].capitalize() + " " + proper_map_name_list[2].capitalize()
            url_map_name = proper_map_name_list[0].upper() + "%20" + proper_map_name_list[1].capitalize() + "%20" + proper_map_name_list[2].capitalize()
        #print(f'mapcore/{storage_name}/{match_id}.dem.gz')
        check_demo = blob_exists(f'mapcore/{storage_name}/{match_id}.dem.gz')
        #print(check_demo)
        if check_demo:

            demo_url = f"{config.DEMO_SERVER}{url_map_name}/{match_id}.dem.gz"
            message_line = f'{final_score.ljust(8)} on {game["date"]} - [Summary]({game["room_link"]}) - [Demo]({demo_url})\n'

        else:
            message_line = f'{final_score.ljust(8)} on {game["date"]} - [Summary]({game["room_link"]})\n'

        list_of_games.append(message_line)

    return list_of_games

def get_demo_direct(demo_url):

    if len(demo_url)>0:
        body = {"resource_url": demo_url}
        headers = {"Content-Type":"application/json", 'Authorization': f'Bearer {config.API_TOKEN}'}

        response = requests.post(config.DEMO_REQUEST_URL, json=body, headers=headers)
        payload = json.loads(response.text)

        demo_download_url = payload["payload"]["download_url"] 
        return_string = f"[Demo]({demo_download_url})"

    else:
        print("didnt save demo_url")

        return_string = "No demo"
    return return_string


def build_chart(games_data, title_time='week'):
    '''function to build the chart and save locally, passes back the file name
    for the bot to post'''

    title_text = (f'In the last {title_time} there were {games_data["total"]}'
                  f'games in total,\n {games_data["match_type_counter"]["fiveman"]} '
                  f'5v5 games and {games_data["match_type_counter"]["Wingman"]} Wingman games')
    x = [map_name.replace('contest ', '').capitalize() for map_name in games_data["maps_counter"]]
    y = games_data["maps_counter"].values()
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(15, 9))
    ax2 = fig.add_subplot()
    ax2.bar(x, y, color="#ff5500")
    ax2.set_xticklabels(x, rotation=45, fontsize=12)
    ax2.set_title(title_text, fontsize=25)
    filename = "matches.png"
    plt.savefig(filename)

    return filename

def upload_blob(bucket_name, source_file_name, destination_blob_name, map_name):
    """Uploads a file to the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file_name = "local/path/to/file"
    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client.from_service_account_json(r"service_account.json", project=config.CLOUD_PROJECT)
    bucket = storage_client.bucket(bucket_name)
    destination_blob_full_name = f"mapcore/{map_name}/{destination_blob_name}"
    #print(destination_blob_full_name)
    blob = bucket.blob(destination_blob_full_name)

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request to upload is aborted if the object's
    # generation number does not match your precondition. For a destination
    # object that does not yet exist, set the if_generation_match precondition to 0.
    # If the destination object already exists in your bucket, set instead a
    # generation-match precondition using its generation number.
    #generation_match_precondition = 0
    try:
        blob.upload_from_filename(source_file_name)

        #print(
        #    f"File {source_file_name} uploaded to {destination_blob_name}."
        #)
        return f"File {source_file_name} uploaded to {destination_blob_name}."
    except Exception as e:
        return e

def blob_exists(filename):
    storage_client = storage.Client.from_service_account_json(r"service_account.json", project=config.CLOUD_PROJECT)
    bucket = storage_client.get_bucket(config.CLOUD_BUCKET)
    blob = bucket.blob(filename)
    return blob.exists()

def demo_download(demo_url, match_id, map_name, logger):
    '''function to download the demos from faceit'''
    
    try:
        
        check_demo = blob_exists(f'mapcore/{map_name}/{match_id}.dem.gz')
        
        if not check_demo:
            body = {"resource_url": demo_url}
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.API_TOKEN}",
            }

            response = requests.post(
                config.DEMO_REQUEST_URL, json=body, headers=headers
            )
            logger.error(response.status_code)
            logger.error(response.text)
            payload = json.loads(response.text)
            if "payload" in payload.keys():
                demo_download_url = payload["payload"]["download_url"]
                file_loc = f"{config.STORAGE_LOCATION}temp.dem.gz"
                r = requests.get(demo_download_url, stream=True)
                with open(file_loc, "wb") as fd:
                    for chunk in r.iter_content(chunk_size=128):
                        fd.write(chunk)

                debug_msg = f"Demo downloaded {match_id}"
                logger.debug(debug_msg)
                upload_debug_msg = upload_blob(config.CLOUD_BUCKET, file_loc, f"{match_id}.dem.gz", map_name)
                logger.error(upload_debug_msg)
        
    except Exception as e:
                error_string = f"Error in demo_download, {e}"
                logger.error(error_string, exc_info=True)
