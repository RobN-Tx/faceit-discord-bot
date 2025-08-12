'''main module for a faceit match, to monitor its life and progress'''

from dataclasses import dataclass
import json
import requests
import discord
import config
import logging



class FaceitMatch:
    '''FaceitMatch class manages the lifecycle and data of a Faceit match, including score updates, match status, and Discord message formatting.
        logger (logging.Logger): Logger for logging events and errors.
        status (str): Current status of the match.
        demo_needed (bool): Indicates if a demo is needed for the match.
    Methods:
        __init__(match_config_json: dict, status: str, logger: logging.Logger):
            Initializes a new FaceitMatch instance with configuration, status, and logger.
        update_score():
            Handles cancellation, missing data, and error logging.
        finish_match():
        build_embedded_message():
            Builds and returns a Discord embedded message summarizing the match, including team names, scores,
            map information, and demo links if available.
                discord.Embed: The formatted embedded message for Discord.
    '''
    def __init__(self, match_config_json: dict, status: str, logger: logging.Logger):
        """
        Initializes a new instance of the class with match configuration, status, and logger.

        Args:
            match_config_json (dict): The JSON configuration for the match, containing payload data.
            status (Any): The initial status of the match.
            logger (logging.Logger): Logger instance for logging events.

        Attributes:
            logger (logging.Logger): Logger for the class.
            status (Any): Current status of the match.
            finished (bool): Indicates if the match is finished.
            demo_needed (bool): Indicates if a demo is needed.
            demoed (bool): Indicates if the demo has been processed.
            cancelled (bool): Indicates if the match has been cancelled.
            cancelled_text (str): Reason for cancellation.
            match_id (str): Unique identifier for the match.
            ct_start (FaceitTeam): Team starting as Counter-Terrorists.
            t_start (FaceitTeam): Team starting as Terrorists.
            game_data (GameData): Game data object for the match.
            score (MatchScore): Score object for the match.
            discord_messages (list): List of Discord messages related to the match.
            failed_count (int): Number of failed attempts or operations.
        """

        self.logger = logger
        self.status = status
        self.finished = False
        self.demo_needed = True
        self.demoed = False
        self.cancelled = False
        self.cancelled_text = ""
        self.match_id = match_config_json["payload"]["id"]
        self.ct_start = FaceitTeam(match_config_json["payload"]["teams"]["faction1"])
        self.t_start = FaceitTeam(match_config_json["payload"]["teams"]["faction2"])
        self.game_data = GameData(match_config_json, self.logger)
        self.score = MatchScore()
        self.discord_messages = []
        self.failed_count  = 0

    def update_score(self):
        """
        Updates the match score and status by fetching the latest match data from the Faceit API.
        - If `failed_count` reaches 30, cancels the match and resets scores.
        - Sends a GET request to the match URL using the match ID.
        - Parses the response and updates the match status and scores accordingly.
        - Handles cases where the match is cancelled or summary results are missing.
        - Increments `failed_count` on errors or missing data.
        - Logs debug and error information for troubleshooting.
        Returns:
            bool: True if the score update was successful, False otherwise.
        """
        
        if self.failed_count == 30:
            self.status = "CANCELLED"
            self.score.match_score.ct_start = 0
            self.score.match_score.t_start = 0
            self.cancelled = True

        try:
            response = requests.get(config.MATCH_URL + self.match_id, timeout=20)
            if len(response.text) > 0:
                data = json.loads(response.text)
                if "payload" in data.keys():
                    debug_string = f'{self.match_id}, self status: {self.status}, state: {data["payload"]["state"]}, status: {data["payload"]["status"]}'
                    self.logger.debug(debug_string)
                    match_state = config.MATCH_STATE[data["payload"]["state"]]
                    self.status = match_state
                    if self.status == "CANCELLED" or self.status == "ABANDONED":
                        self.score.match_score.ct_start = 0
                        self.score.match_score.t_start = 0
                        self.cancelled = True
                        
                    else:
                        if "summaryResults" in data["payload"].keys() and not self.status == "FINISHED":
                            summary_results = data["payload"]["summaryResults"]

                            self.score.update_scores(summary_results)
                        else:
                            self.logger.debug("issue in update score no summaryResults")
                            self.logger.debug(data)
                            self.failed_count = self.failed_count + 1
                else:
                    self.logger.debug("issue in update score no payload")
                    self.logger.debug(data)
                    self.failed_count = self.failed_count + 1
            return True

        except Exception as e:
            msg = "Error in match_data_call" + self.match_id
            self.logger.error(msg, e)
            self.failed_count = self.failed_count + 1
            return False
            

    def finish_match(self):
        """
        Finalizes the match by fetching match statistics from an external API, updating score attributes,
        and processing overtime information.
        Returns:
            bool: True if the match was successfully finished or abandoned after repeated failures,
                  False if the operation failed but has not yet reached the abandonment threshold.
        """
        try:
            response = requests.get(config.STATS_URL + self.match_id, timeout=5)
            finished_match_data = json.loads(response.text)

            self.score.match_score.ct_start = finished_match_data[0]["teams"][0]["c5"]
            self.score.match_score.t_start = finished_match_data[0]["teams"][1]["c5"]
            self.score.first_half.ct_start = finished_match_data[0]["teams"][0]["i3"]
            self.score.first_half.t_start = finished_match_data[0]["teams"][1]["i3"]
            self.score.second_half.ct_start = finished_match_data[0]["teams"][0]["i4"]
            self.score.second_half.t_start = finished_match_data[0]["teams"][1]["i4"]

            self.score.overtimes = []
            self.score.ot_processor(self.score.match_score.ct_start, self.score.match_score.t_start)
            return True

        except Exception as e:
            msg = "Error in finish match call " + self.match_id + str(e)
            self.logger.error(msg, exc_info=True)
            self.failed_count += 1

            if self.failed_count == 30:
                self.status = "Abandoned?"
                self.score.match_score.ct_start = 0
                self.score.match_score.t_start = 0
                self.cancelled = True
                return True
            return False


    def build_embedded_message(self):
        
        try:
            map_name = self.game_data.map_name
            
            if self.cancelled:
                title_text = self.cancelled_text
            else:
                title_text = self.status+":"

            embeded_message = discord.Embed(title=title_text,
                description="# " + map_name + "\n On " + self.game_data.hub, color=0xff5500)

            embeded_message.set_thumbnail(url=self.game_data.map_img)
            embeded_message.add_field(
                name="`" + self.ct_start.team_name + "`", value=self.ct_start.team_listing, inline=True)

            score_detail = self.score.get_final_scores_string() if self.finished else self.score.get_ot_scores_string()

            embeded_message.add_field(name=self.score.get_match_score_string(), value=score_detail, inline=True)
            embeded_message.add_field(
                name="`" + self.t_start.team_name + "`", value=self.t_start.team_listing, inline=True)
            embeded_message.add_field(
                name=" ", value="[Summary](https://www.faceit.com/en/cs2/room/" + self.match_id + ")")

            if self.demoed:
                embeded_message.add_field(
                    name=" ", value="--", inline=True)
                demo_link = f'{config.DEMO_SERVER}{map_name.replace(" ", "%20")}/{self.match_id}.dem.gz'
                embeded_message.add_field(
                    name=" ", value=f"[Demo]({demo_link})", inline=True)

            return embeded_message
        except Exception as e:
                error_string = f"Error in demo_download, {e}"
                self.logger.error(error_string, exc_info=True)



class FaceitTeam:

    def __init__(self, team_dict):

        self.team_name = team_dict["name"]
        self.roster = team_dict["roster"]
        self.team_members = self.build_team_members()
        self.team_listing = self.build_team_string()

    def build_team_members(self):

        team_list = []

        for member in self.roster:
            player = FaceitPlayer(member)
            team_list.append(player)

        return team_list

    def build_team_string(self):

        team_listing = ""

        for player in self.roster:
            team_listing = team_listing + \
                config.FACEIT_LEVELS[player["gameSkillLevel"]] + \
                " " + player["nickname"] + "\n"

        return team_listing


class FaceitPlayer:

    def __init__(self, player_dict):
        # (player_dict)
        self.id = player_dict["id"]
        self.name = player_dict["nickname"]
        self.skill_level = player_dict["gameSkillLevel"]
        self.skill_icon = config.FACEIT_LEVELS[self.skill_level]


class MatchScore:

    def __init__(self):

        self.match_score = SegmentScore("Match", 0, 0)
        self.first_half = SegmentScore("H1", 0, 0)
        self.second_half = SegmentScore("H2", 0, 0)
        self.overtimes = []

    def get_match_score_string(self):

        score_string = f"** {self.match_score.ct_start} - {self.match_score.t_start} **"
        return score_string

    def get_ot_scores_string(self):
        message_string = ""
        if len(self.overtimes) > 0:
            message_string = ""
            for ot_segment in self.overtimes:
                score_string = f"{ot_segment.ct_start} - {ot_segment.t_start}\n"
                message_string = message_string + score_string

        return message_string

    def get_final_scores_string(self):

        message_string = ""

        score_string = f"{self.first_half.ct_start} - {self.first_half.t_start}\n"
        message_string = message_string + score_string
        score_string = f"{self.second_half.ct_start} - {self.second_half.t_start}\n"
        message_string = message_string + score_string

        if len(self.overtimes) > 0:

            for ot_segment in self.overtimes:
                score_string = f"{ot_segment.ct_start} - {ot_segment.t_start}\n"
                message_string = message_string + score_string

        return message_string

    def update_scores(self, summary_results_dict):

        if "factions" in summary_results_dict.keys():

            self.match_score.ct_start = summary_results_dict["factions"]["faction1"]["score"]
            self.match_score.t_start = summary_results_dict["factions"]["faction2"]["score"]

            self.ot_processor(int(self.match_score.ct_start), int(self.match_score.t_start))

    def ot_processor(self, ct_start, t_start):

        current_ct = int(ct_start)
        current_t = int(t_start)

        max_recorded_rounds = 24 + (len(self.overtimes) * 6)

        total_rounds = current_ct + current_t

        number_overtimes = len(self.overtimes) - 1 if len(self.overtimes) > 0 else 0

        ct_ot = current_ct - (12 + (number_overtimes * 3)) if current_ct > 12 else 0
        t_ot = current_t - (12 + (number_overtimes * 3)) if current_ct > 12 else 0

        if total_rounds > max_recorded_rounds:

            new_ot_name = "OT" + str(len(self.overtimes) + 1)

            if ct_ot > 3 and t_ot > 3:

                if len(self.overtimes) == 0:
                    self.overtimes.append(SegmentScore(new_ot_name, 3, 3))
                    self.ot_processor(current_ct, current_t)
                else: 
                    self.overtimes[-1].ct_start = 3
                    self.overtimes[-1].t_start = 3
                    ct_ot = current_ct - (12 + ((len(self.overtimes)) * 3))
                    t_ot = current_t - (12 + ((len(self.overtimes)) * 3))

                    self.overtimes.append(SegmentScore(new_ot_name, ct_ot - 3, t_ot))

                    self.ot_processor(current_ct, current_t)

            else:

                if len(self.overtimes) > 0:
                    self.overtimes[-1].ct_start = 3
                    self.overtimes[-1].t_start = 3
                ct_ot = current_ct - (12 + ((len(self.overtimes)) * 3))
                t_ot = current_t - (12 + ((len(self.overtimes)) * 3))

                self.overtimes.append(SegmentScore(new_ot_name, ct_ot, t_ot))

        else:
            if total_rounds > 24:
                self.overtimes[-1].ct_start = ct_ot
                self.overtimes[-1].t_start = t_ot


class GameData:

    def __init__(self, match_config_json, logger):
        
        self.hub = ""
        self.map_name = ""
        self.logger = logger
        try:
            game_payload = match_config_json["payload"]
            self.hub = game_payload["entity"]["name"]
            self.server = game_payload["voting"]["location"]["pick"]
            self.map_id = game_payload["voting"]["map"]["pick"][0]

            self.map_name = "Errored - id is" + str(self.map_id)

            for map_dict in game_payload["maps"]:
                if self.map_id == map_dict["game_map_id"]:
                    self.map_name = map_dict["name"]
                    self.class_name = map_dict["class_name"]
                    self.map_img = map_dict["image_sm"]
            self.success = True

        except Exception as e:
            error_string = f'Error in GameData__init__, {e}'
            self.logger.error(error_string, exc_info=True)
            self.success = False


@dataclass
class SegmentScore:
    segment_name: str
    ct_start: int
    t_start: int
