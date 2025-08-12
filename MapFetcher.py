import datetime
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import requests

import config
import MapCoreFunctions as mapcorefunctions
from MapCoreDb import MapCoreDb


class MapFetcher:
    """
    MapFetcher is responsible for fetching, processing, and storing map and match data from external APIs,
    specifically for Faceit CS2 matches. It interacts with a database to store match details and demos,
    and provides utilities for backfilling historical data, processing match statistics, and handling demo downloads.
    Args:
        target_map (str): The target map name or identifier to filter matches.
        logger (logging.Logger): Logger instance for error and event logging.
    Attributes:
        matches (dict): Stores processed match data indexed by match ID.
        maps (dict): Stores map data.
        target_map_string (str): Lowercase string of the target map for filtering.
        db (MapCoreDb): Database handler for storing and checking matches.
        logger (logging.Logger): Logger for logging errors and events.
    Methods:
        build_map_list():
            Iterates over configured hubs and builds the map list by fetching matches.
        backfiller(games_to_fetch=20, start_offset=0):
            Backfills historical matches for all hubs, starting from a given offset.
        hub_match_build(hub, games_to_fetch=20, start_offset=0):
            Fetches matches for a specific hub in batches, starting from a given offset.
        fetch_maps(hub, run_offset):
            Fetches match data from the API for a specific hub and offset, processes and stores matches and demos.
        check_in_db(match_id):
            Checks if a match with the given ID exists in the database.
        match_processor(match):
            Processes a single match, filtering by target map, and stores its details if relevant.
        finished_match_processor(finished_match_id):
            Processes and stores details for a finished match by its ID.
        match_detailer(match):
            Extracts and structures detailed match information for database storage.
        stats_processor(match_id):
            Fetches and processes match statistics for a given match ID.
    Exceptions:
        All methods log errors using the provided logger and print detailed traceback information on exceptions.
    """

    def __init__(self, target_map, logger):
        """
        Initializes the MapFetcher instance.

        Args:
            target_map (str): The name of the target map to fetch and save.
            logger (logging.Logger): Logger instance for logging messages.

        Attributes:
            matches (dict): Stores match data.
            maps (dict): Stores map data.
            target_map_string (str): Lowercase string of the target map name.
            db (MapCoreDb): Database connection to 'MapCore_Dev.db'.
            logger (logging.Logger): Logger instance for logging.
        """
        print("hello Im the map fetcher and saver")
        self.matches = {}
        self.maps = {}
        self.target_map_string = target_map.lower()
        self.db = MapCoreDb("MapCore_Dev.db")
        self.logger = logger

    def build_map_list(self):
        """
        Iterates through all hubs defined in the configuration and builds a map list for each hub.

        For each hub in `config.HUBS_DICT`, calls `self.hub_match_build` with the hub's GUID.

        Returns:
            None
        """
        for hub in config.HUBS_DICT:
            self.hub_match_build(hub["guid"])

    def backfiller(self, games_to_fetch=20, start_offset=0):
        """
        Fetches and processes a specified number of games for each hub, starting from a given offset.

        Args:
            games_to_fetch (int, optional): The number of games to fetch for each hub. Defaults to 20.
            start_offset (int, optional): The starting offset for fetching games. Defaults to 0.

        Returns:
            None
        """
        for hub in config.HUBS_DICT:
            self.hub_match_build(hub["guid"], games_to_fetch, start_offset)

    def hub_match_build(self, hub, games_to_fetch=20, start_offset=0):
        """
        Fetches maps for a given hub in batches, starting from a specified offset.
        Args:
            hub: The hub identifier or object for which to fetch maps.
            games_to_fetch (int, optional): Total number of games to fetch. Defaults to 20.
            start_offset (int, optional): The starting offset for fetching games. Defaults to 0.
        Notes:
            - The function rounds the number of games to fetch to the nearest multiple of 20.
            - Maps are fetched in batches of 20, starting from the start_offset.
            - For each batch, the offset is incremented by 20 until the desired number of games is fetched.
        """

        games_rounded = 20 * round(games_to_fetch / 20)
        i = 0
        while i <= games_rounded:
            run_offset = i + start_offset
            print(run_offset)
            self.fetch_maps(hub, run_offset)
            i = i + 20

    def fetch_maps(self, hub, run_offset):
        """
        Fetches match data for a specified hub and offset, processes new matches, and manages demo file downloads.
        This method sends a GET request to the configured match API to retrieve match information for the given hub and offset.
        For each match returned:
            - Prints match ID and status.
            - Checks if the match already exists in the database.
            - Processes the match if it is not cancelled and not pre-existing.
            - Determines the map name from the match voting data.
            - Constructs the expected demo file storage path.
            - Checks if the demo file exists in cloud storage.
            - Downloads the demo file if it does not exist in cloud storage.
        Args:
            hub (str): The hub identifier used to fetch matches.
            run_offset (int): The offset for paginated match fetching.
        Raises:
            Logs errors and exception details if any occur during processing.
        
        part of the backfiller
        """

        request_url = config.NEW_MATCH_URL.format(hub_id=config.HUBS_DICT[hub], offset=run_offset)

        headers = {"Authorization": "Bearer " + config.API_TOKEN}

        response = requests.get(request_url, headers=headers, timeout=15)

        try:  # (len(response.text) > 0) and (response.text is not None):
            matches_payload = json.loads(response.text)["items"]

            for match in matches_payload:
                print(match["match_id"])
                print(match["status"])

                pre_existing = self.db.check_match(match["match_id"])
                if match["status"] != "CANCELLED":

                    if not pre_existing:

                        self.match_processor(match)

                    map_guid = match["voting"]["map"]["pick"][0]
                    print(map_guid)
                    map_name = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid][0]["name"]
                    demo_storage_name = f'mapcore/{map_name}/{match["match_id"]}.dem.gz'

                    demo_in_cloud = mapcorefunctions.blob_exists(demo_storage_name)

                    if demo_in_cloud:
                        print("demo in cloud")

                    else:
                        mapcorefunctions.demo_download(match["demo_url"][0], match["match_id"], map_name, self.logger)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.logger.error(exc_type, fname, exc_tb.tb_lineno)

    def check_in_db(self, match_id):
        """
        Checks if a match with the given match_id exists in the database.
        Args:
            match_id (str or int): The unique identifier of the match to check.
        Returns:
            bool: True if the match exists in the database, False otherwise.
        Side Effects:
            Prints the existence status of the match to the console.
        """
        pre_existing = self.db.check_match(match_id)

        print(f"match {match_id} exists? {pre_existing}")

        return pre_existing

    def match_processor(self, match):
        """
        Processes a match dictionary to determine if it matches the target map string.
        The function extracts the selected map's GUID from the match voting data, then retrieves
        the map's name and class name. If the target map string is a wildcard ("*"), all maps
        will be processed regardless of their name or class name. Otherwise, only matches where
        the target map string is found within the map's name or class name are processed further
        using `self.match_detailer`.
        Args:
            match (dict): A dictionary containing match information, including voting data
                with map picks and entities.
        Returns:
            dict: The processed match details if the target map string matches the map's name
                or class name, or if the target is a wildcard. Otherwise, returns None.
        """
        map_guid = None
        map_name = ""
        class_name = ""

        if match["voting"]["map"]["pick"]:
            map_guid = match["voting"]["map"]["pick"][0]
            map_entities = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid]
            map_name_list = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid]
            if map_name_list:
                map_name = map_name_list[0]["name"].lower()
            else:
                map_name = ""
            map_name = map_entities[0]["name"].lower()
        else:
            map_name = "unknown"
            map_name = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid][0]["name"].lower()
            class_name = [class_name for class_name in match["voting"]["map"]["entities"] if class_name["guid"] == map_guid][0]["class_name"].lower()

        processed = None

        if self.target_map_string == "*":
            processed = self.match_detailer(match)

        elif self.target_map_string in map_name or self.target_map_string in class_name:
            processed = self.match_detailer(match)

        return processed

    def finished_match_processor(self, finished_match_id):
        '''function to process a finished game and store'''
        target_url = config.MATCH_URL + finished_match_id
        pre_existing = False
        response = requests.get(target_url, timeout=15)

        return_bool = False
        try:
            if (len(response.text) > 0) and (response.text is not None):
                match_payload = json.loads(response.text)["payload"]
                if "voting" in match_payload.keys():
                    pre_existing = self.match_detailer(match_payload)
                    return_bool = pre_existing
                else:
                    # print("failed save gamne", match_payload)
                    return_bool = False
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            error_string = f'Error finished_match_processor, {e}'
            self.logger.error(exc_type, fname, exc_tb.tb_lineno, error_string)

        return return_bool

    def match_detailer(self, match):
        '''function to detail the match, id map etc for db store'''
        match_data = {}
        pre_existing = False
        match_id = None
        try:

            if "id" in match.keys():
                match_id = match["id"]
            elif "match_id" in match.keys():
                match_id = match["match_id"]
            else:
                print(match.keys())

            map_guid = match["voting"]["map"]["pick"][0]
            map_name = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid][0]["name"].lower()
            
            if 'startedAt' in match.keys():
                print('startedAt', match['startedAt'])
                match["started_at"] = match['startedAt']
            elif 'started_at' in match.keys():
                print('started_at', match['started_at'])
                match["started_at"] = str(datetime.datetime.fromtimestamp(match["started_at"]).strftime('%Y-%m-%dT%H:%M:%SZ'))
            # print(match.keys())
            if "demo_url" in match.keys():
                stats = self.stats_processor(match_id)
                match_data = {
                    "id": match_id,
                    "hub": match["competition_name"],
                    "map_guid": match["voting"]["map"]["pick"][0],
                    "map_name": map_name,
                    "class_name": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["game_map_id"] == map_guid][0]["class_name"].lower(),
                    "room_link": "https://www.faceit.com/en/cs2/room/" + match_id,
                    "stats": stats,
                    "match_time": match["started_at"],
                    "image": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["game_map_id"] == map_guid][0]["image_sm"],
                    "demo_url": match["demo_url"][0]
                }
                self.matches[match_id] = match_data
                pre_existing = self.db.insert_match(match_data)
            elif match["status"] != "CANCELLED":
                stats = self.stats_processor(match_id)
                match_data = {
                    "id": match_id,
                    "hub": "Cancelled",
                    "map_guid": match["voting"]["map"]["pick"][0],
                    "map_name": map_name,
                    "class_name": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["game_map_id"] == map_guid][0]["class_name"].lower(),
                    "room_link": "https://www.faceit.com/en/cs2/room/" + match_id,
                    "stats": stats,
                    "match_time": match["started_at"],
                    "image": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["guid"] == map_guid][0]["image_sm"],
                    "demo_url": "No URL"
                }
                self.matches[match_id] = match_data
                pre_existing = self.db.insert_match(match_data)
                print("no demo url")

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            error_string = f'Error finished_match_processor, {e}'
            self.logger.error(match.keys(), exc_type, fname, exc_tb.tb_lineno, error_string)

        return pre_existing

    def stats_processor(self, match_id):
        '''function to process game stats ready for db store'''
        response = requests.get(config.STATS_URL + match_id, timeout=15)
        finished_match_data = json.loads(response.text)

        if len(finished_match_data) > 0 and response.status_code == 200:
            team_1 = finished_match_data[0]["teams"][0]["i5"]
            team_1_score = finished_match_data[0]["teams"][0]["c5"]
            team_2 = finished_match_data[0]["teams"][1]["i5"]
            team_2_score = finished_match_data[0]["teams"][1]["c5"]

            team_1_1st_half = finished_match_data[0]["teams"][0]["i3"]
            team_1_2nd_half = finished_match_data[0]["teams"][0]["i4"]
            team_2_1st_half = finished_match_data[0]["teams"][1]["i3"]
            team_2_2nd_half = finished_match_data[0]["teams"][1]["i4"]

            ct_rounds = int(team_1_1st_half) + int(team_2_2nd_half)
            t_rounds = int(team_1_2nd_half) + int(team_2_1st_half)

            match_stats = {
                "CT_1st": {
                    "name": team_1,
                    "final_score": team_1_score,
                    "1st_half": team_1_1st_half,
                    "2nd_half": team_1_2nd_half,
                },
                "T_1st": {
                    "name": team_2,
                    "final_score": team_2_score,
                    "1st_half": team_2_1st_half,
                    "2nd_half": team_2_2nd_half,
                },
                "t_rounds": str(t_rounds),
                "ct_rounds": str(ct_rounds),
            }
        else:
            match_stats = {
                "CT_1st": {
                    "name": "unknown",
                    "final_score": 0,
                    "1st_half": 0,
                    "2nd_half": 0,
                },
                "T_1st": {
                    "name": "unknown",
                    "final_score": 0,
                    "1st_half": 0,
                    "2nd_half": 0,
                },
            }
        return match_stats


if __name__ == "__main__":
    
    logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("debug2.log", "a", 2000, 14),
        logging.StreamHandler(),
    ]
    )

    logger = logging.getLogger("")

    logger.error('Started')
    mf = MapFetcher("*", logger)
    mf.backfiller(10, 0)
    games = mf.db.print_all()
    print(len(games))
