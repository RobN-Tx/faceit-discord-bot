"""main module for the new bot"""

import sys
import os
import logging
import logging.handlers
import json
import time

import requests

from apscheduler.schedulers.background import BackgroundScheduler

import webhook_listener
import argparse
import config
import MapCoreFunctions as mapcorefunctions

import FaceitClasses
from MapFetcher import MapFetcher


class MapcoreBot:
    """Bot for handling Mapcore webhooks and match events."""

    def __init__(self, port=8090, verbose=False):
        self.logger = self.build_logger(verbose)
        self.port = port

        self.webhooks = webhook_listener.Listener(
            port=self.port, handlers={"POST": self.parse_request}
        )
        self.ongoing_games = {}
        self.sched = BackgroundScheduler()
        self.sched.add_job(self.match_tester, "interval", seconds=60)
        self.life = True
        self.map_fetcher = MapFetcher("*", self.logger)

    def start(self):
        """Start the webhook listener and scheduler."""
        self.webhooks.start()
        self.sched.start()

    def match_tester(self):
        """Update scores for ongoing games."""
        try:
            for game in list(self.ongoing_games.values()):
                if not game.finished:
                    game.update_score()
                    score = game.score.get_match_score_string()
                    self.logger.debug(score)
        except Exception as e:
            self.logger.error(f"Error in match_tester: {e}", exc_info=True)

    def build_logger(self, verbose=False):
        """Build and configure logger."""
        logger = logging.getLogger("webhooks")
        logger.setLevel(logging.DEBUG if verbose else logging.ERROR)

        formatter = logging.Formatter(
            "%(asctime)s :: %(levelname)8s :: %(module)s(%(lineno)d) :: %(message)s",
            datefmt="%Y-%m-%d %I:%M:%S %p",
        )
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        logger.addHandler(console)

        logPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "logs")
        os.makedirs(logPath, exist_ok=True)
        file = logging.handlers.TimedRotatingFileHandler(
            os.path.join(logPath, "webhooks.log"),
            when="midnight",
            interval=1,
            backupCount=7,
        )
        file.setFormatter(formatter)
        logger.addHandler(file)
        logger.debug("Logging started!")
        return logger

    def match_configure(self, hook_payload, finished_flag=False):
        """Configure a match from webhook payload."""
        try:
            match_id = hook_payload["id"]
            self.logger.debug(f"Configuring match {match_id}")
            match_data = self.match_data_call(match_id)
            if match_data[0]:
                match_file = f"{match_id}/match_status_configuring_match.JSON"
                self.save_file(match_id, match_file, json.dumps(match_data[1]))
                status = "Finished" if finished_flag else "In Warm Up"
                new_match = FaceitClasses.FaceitMatch(
                    match_data[1], status, self.logger
                )
                self.ongoing_games[match_id] = new_match
        except Exception as e:
            self.logger.error(f"Error in match_configure: {e}", exc_info=True)

    def match_finished(self, hook_payload):
        """Handle match finished event."""
        try:
            match_id = hook_payload["id"]
            self.logger.debug(f"Match finished for {match_id}")
            if match_id in self.ongoing_games:
                try:
                    closed_match = self.ongoing_games[match_id].finish_match()
                    if closed_match:
                        self.ongoing_games[match_id].status = "Finished match"
                        self.ongoing_games[match_id].finished = True
                        
                    #dont like this as will hang the whole thread which isnt right
                    else:
                        time.sleep(10)
                        self.match_finished(hook_payload)
                except Exception as e:
                    self.logger.error(f"Error in match_finished (finish_match): {e}", exc_info=True)
            else:
                if self.map_fetcher.check_in_db(match_id):
                    self.logger.error(f"Match {match_id} tried to make itself again in match_finished")
                else:
                    self.match_configure(hook_payload, True)
                    self.match_finished(hook_payload)
        except Exception as e:
            self.logger.error(f"Error in match_finished: {e}", exc_info=True)

    def match_ready(self, hook_payload):
        """Handle match ready event."""
        match_id = hook_payload["id"]
        self.logger.debug(f"Match ready for {match_id}")
        if match_id in self.ongoing_games:
            self.ongoing_games[match_id].status = "Configuring"
        else:
            self.match_configure(hook_payload)
            self.match_ready(hook_payload)

    def match_cancelled(self, hook_payload):
        """Handle match cancelled event."""
        try:
            match_id = hook_payload["id"]
            reason = hook_payload.get("reason", "Manual")
            self.logger.debug(f"Match {match_id} cancelled due to {reason}")
            if match_id in self.ongoing_games:
                game = self.ongoing_games[match_id]
                game.status = f"Cancelled - {reason}"
                game.cancelled = True
                game.cancelled_text = f"Cancelled - {reason}:"
        except Exception as e:
            self.logger.error(f"Error in match_cancelled: {e}", exc_info=True)

    def demo_ready(self, hook_payload):
        """Handle demo ready event."""
        match_id = hook_payload["id"]
        if match_id in self.ongoing_games:
            processing_game = self.ongoing_games[match_id]
            try:
                if processing_game.demo_needed:
                    processing_game.demo_needed = False
                    map_name = processing_game.game_data.map_name
                    demo_url = hook_payload.get("demo_url")
                    if demo_url:
                        mapcorefunctions.demo_download(demo_url, match_id, map_name, self.logger)
                        processing_game.demoed = True
                        self.map_fetcher.finished_match_processor(match_id)
            except Exception as e:
                self.logger.error(f"Error in demo_ready: {e}", exc_info=True)
        else:
            if self.map_fetcher.check_in_db(match_id):
                self.logger.error(f"Match {match_id} tried to make itself again in demo_ready")
            else:
                self.match_finished(hook_payload)
                self.demo_ready(hook_payload)

    def match_data_call(self, match_id):
        """Fetch match data from API."""
        try:
            response = requests.get(config.MATCH_URL + match_id, timeout=10)
            if response.text:
                data = json.loads(response.text)
                if "voting" in data.get("payload", {}):
                    return (True, data)
            return (False, "Failed")
        except Exception as e:
            self.logger.error(f"Error in match_data_call: {e}", exc_info=True)
            return (False, "Failed")

    def process_body(self, request):
        """Process request body."""
        content_length = int(request.headers.get("Content-Length", 0))
        body_raw = request.body.read(content_length) if content_length > 0 else b""
        if content_length > 0:
            body = json.loads(body_raw.decode("utf-8"))
        else:
            body = {}
        return body

    def save_file(self, match_id, file_name, data):
        """Save data to file."""
        cloud_path = f'match_data/{match_id}'
        os.makedirs(cloud_path, exist_ok=True)
        full_file_name = f'match_data/{file_name}'
        try:
            with open(full_file_name, "w") as myFile:
                myFile.write(data)
        except Exception as e:
            self.logger.error(f"{full_file_name} has an issue saving file: {e}")

    def process_hook_info(self, request, body, *args, **kwargs):
        """Save hook info for debugging."""
        request_info = (
            f"Received request:\n"
            f"Method: {request.method}\n"
            f"Headers: {request.headers}\n"
            f"Args (url path): {args}\n"
            f"Keyword Args (url parameters): {kwargs}\n"
            f"Body: {json.dumps(body)}\n"
        )
        event = body.get("event")
        match_id = body.get("payload", {}).get("id")
        if event and match_id:
            file_name = f"{match_id}/{event}_hook.JSON"
            self.save_file(match_id, file_name, request_info)

    def parse_request(self, request, *args, **kwargs):
        """Parse incoming webhook request."""
        self.logger.debug("Parsing request")
        user_agent = request.headers.get("USER-AGENT")
        wibble = request.headers.get("WIBBLE")
        if user_agent == config.USER_AGENT and wibble == config.WIBBLE:
            body = self.process_body(request)
            self.process_hook_info(request, body, *args, **kwargs)
            self.logger.debug("Processing match data")
            functionDictionary = {
                "match_status_configuring": self.match_configure,
                "match_status_ready": self.match_ready,
                "match_status_cancelled": self.match_cancelled,
                "match_demo_ready": self.demo_ready,
            }
            event = body.get("event")
            payload = body.get("payload")
            if event in functionDictionary and payload:
                self.logger.debug(f"{event} for {payload.get('id')} match")
                functionDictionary[event](payload)
            else:
                self.logger.debug(f"{event} not handled")
        else:
            self.logger.debug("Failed user agent and wibble check")
        return

def parse_args():
    parser = argparse.ArgumentParser(
        prog="Webhook Listener", description="Start the webhook listener."
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        dest="verbose",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        nargs=1,
        dest="port",
        help="Port for the web server to listen on (default: 8090).",
    )
    args = parser.parse_args()
    port = args.port[0] if args.port and args.port[0] >= 0 else 8090
    return port, args.verbose

if __name__ == "__main__":
    #print("hello world")

    mapcore_bot = MapcoreBot()

    while mapcore_bot.life:
        #print("hello world")
        mapcore_bot.logger.debug("Still alive...")
        time.sleep(300)
