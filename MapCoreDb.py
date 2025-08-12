'''Module to control the mapcore database'''
import sqlite3
import json
import csv
import datetime


class MapCoreDb:
    '''the class for the database control'''

    def __init__(self, db_file):

        self.match_table_name = "mapcore_dev_matches"

        self.db_name = db_file

        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)

        self.cursor = self.conn.cursor()
        print("Database created and Successfully Connected to SQLite")

    def test_life(self):

        try:
            cursor = self.conn.cursor()
            sqlite_select_query = "select sqlite_version();"
            cursor.execute(sqlite_select_query)
            record = self.cursor.fetchall()
            print("SQLite Database Version is: ", record)
            cursor.close()
        except sqlite3.Error as error:
            print("Error while connecting to sqlite", error)

    def close(self):
        if self.conn:
            self.conn.close()
            print("The SQLite connection is closed")

    def create_mapcore_table(self):
        try:
            sqlite_create_table_query = f"""CREATE TABLE {self.match_table_name}(
                                id TEXT PRIMARY KEY,
                                hub TEXT NOT NULL,
                                map_guid INT NOT NULL,
                                map_name TEXT,
                                class_name TEXT,
                                room_link TEXT,
                                stats TEXT,
                                match_time datetime,
                                image TEXT,
                                demo_url TEXT);"""

            # self.conn.execute(sqlite_create_table_query)
            cursor = self.conn.cursor()
            # sqlite_select_Query = "select sqlite_version();"
            cursor.execute(sqlite_create_table_query)
            record = self.cursor.fetchall()
            print("SQLite Database Version is: ", record)
            cursor.close()
        except sqlite3.Error as error:
            print("make table error", error)

    def insert_match(self, match_dict):

        cursor = self.conn.cursor()

        check_exist_query = f'SELECT EXISTS(SELECT 1 FROM mapcore_dev_matches WHERE id="{match_dict["id"]}" LIMIT 1)'

        cursor.execute(check_exist_query)

        exists_if_1 = cursor.fetchone()[0]
        # print("exists if one", exists_if_1)
        if exists_if_1 == 0:

            cursor.execute(
                "insert into mapcore_dev_matches values(?,?,?,?,?,?,?,?,?,?)",
                (
                    match_dict["id"],
                    match_dict["hub"],
                    match_dict["map_guid"],
                    match_dict["map_name"],
                    match_dict["class_name"],
                    match_dict["room_link"],
                    json.dumps(match_dict["stats"]),
                    match_dict["match_time"],
                    match_dict["image"],
                    match_dict["demo_url"]
                ),
            )

        cursor.execute("select * from mapcore_dev_matches")

        self.conn.commit()
        return exists_if_1 == 1
    
    def check_match(self, match_id):

        cursor = self.conn.cursor()

        check_exist_query = f'SELECT EXISTS(SELECT 1 FROM mapcore_dev_matches WHERE id="{match_id}" LIMIT 1)'

        cursor.execute(check_exist_query)

        exists_if_1 = True if cursor.fetchone()[0] == 1 else False

        return exists_if_1

    def print_all(self, target_map='*'):

        cursor = self.conn.cursor()

        if target_map == '*':
            query = 'SELECT * FROM mapcore_dev_matches ORDER BY match_time DESC'
        else:
            query = f"SELECT * FROM mapcore_dev_matches WHERE (map_name LIKE '{target_map}' OR map_name LIKE 'contest {target_map}') ORDER BY match_time DESC"
        data = cursor.execute(query)
        rows = data.fetchall()
        return_dict = {}
        # print(len(rows))
        for row in rows:

            return_dict[row[0]] = {"room_link": row[5],
                                   "stats": json.loads(row[6]),
                                   "date": row[7],
                                   "demo_url":row[9],
                                   "map_name": row[3]
                                   }
        return return_dict

    def table_dated_map(self, target_map="*", start_days_ago=1, end_days_ago='localtime'):

        cursor = self.conn.cursor()

        query = f'SELECT * FROM mapcore_dev_matches WHERE instr(map_name, "{target_map}") AND match_time BETWEEN datetime("now", "-{start_days_ago} days") AND datetime("now", "{end_days_ago}") ORDER BY match_time DESC'

        data = cursor.execute(query)
        rows = data.fetchall()
        return_dict = {}
        # print(len(rows))
        for row in rows:

            return_dict[row[0]] = {"room_link": row[5],
                                   "stats": json.loads(row[6]),
                                   "date": row[7],
                                   "demo_url":row[9],
                                   "map_name": row[3],
                                   "match_id": row[0]
                                   }
        return return_dict

    def chart_data_fetch(self, start_days_ago, end_days_ago='0'):

        cursor = self.conn.cursor()
        query = f"SELECT * FROM mapcore_dev_matches WHERE julianday('now') - julianday(match_time) BETWEEN {end_days_ago} AND {start_days_ago}"
        # query = f"SELECT * FROM mapcore_dev_matches WHERE (match_time > datetime('now', '-{start_days_ago} days'))"
        # query = f"SELECT * FROM mapcore_dev_matches WHERE match_time BETWEEN datetime('now', '-{start_days_ago} days') AND datetime('now', '{end_days_ago}')"

        data = cursor.execute(query)
        rows = data.fetchall()

        return_data = self.process_chart_rows(rows)

        return return_data

    def chart_data_fetch2(self, start_days_ago, end_days_ago=0):

        cursor = self.conn.cursor()

        # query = f"SELECT * FROM mapcore_dev_matches WHERE (match_time > datetime('now', '-{start_days_ago} days'))"
        query = f"SELECT * FROM mapcore_dev_matches WHERE julianday('now') - julianday(match_time) BETWEEN {end_days_ago} AND {start_days_ago}"

        data = cursor.execute(query)
        rows = data.fetchall()

        return_data = self.process_chart_rows(rows)

        return return_data

    def process_chart_rows(self, rows):

        return_dict = {}
        for row in rows:

            return_dict[row[0]] = {"room_link": row[5],
                                   "stats": json.loads(row[6]),
                                   "date": row[7],
                                   "demo_url":row[9],
                                   "map_name": row[3],
                                   "hub": row[1]
                                   }

        all_maps = [d['map_name'] for d in return_dict.values()]
        all_hubs = [d['hub'] for d in return_dict.values()]
        maps_counter = {}
        hubs_counter = {}
        for faceit_map in all_maps:
            if faceit_map not in maps_counter:
                count_of_map_games = len([i for i in all_maps if i == faceit_map])
                maps_counter[faceit_map] = count_of_map_games

        for hub in all_hubs:
            if hub not in hubs_counter:
                count_of_hub_games = len([i for i in all_hubs if i == hub])

                hubs_counter[hub] = count_of_hub_games
        match_type_counter = {"fiveman":0, "Wingman":0}
        for hub, count in hubs_counter.items():
            if "Wingman" in hub:
                match_type_counter["Wingman"] = match_type_counter["Wingman"] + count
            else:
                match_type_counter["fiveman"] = match_type_counter["fiveman"] + count

        total_games = len(return_dict)

        return {"maps_counter": maps_counter, "match_type_counter":match_type_counter, "total": total_games}

    def last_week_matches(self):
        '''class function to get the games from the last week and prep them '''
        cursor = self.conn.cursor()

        # query = "SELECT * FROM mapcore_dev_matches WHERE match_time BETWEEN datetime('now', '-7 days') AND datetime('now', 'localtime')"
        query = f"SELECT * FROM mapcore_dev_matches WHERE (match_time > datetime('now', '-7 days'))"

        data = cursor.execute(query)
        rows = data.fetchall()
        return_data = self.process_chart_rows(rows)
        print(return_data["maps_counter"].keys())
        try:
            del return_data["maps_counter"]["cache"]
        except:
            print("didnt find cache")
        return return_data

    def to_csv(self, target_map='*'):
        '''class function to get the games from the last week and prep them '''
        cursor = self.conn.cursor()

        if target_map == '*':
            query = 'SELECT * FROM mapcore_dev_matches ORDER BY match_time DESC'
        else:
            query = f"SELECT * FROM mapcore_dev_matches WHERE (map_name LIKE '{target_map}' OR map_name LIKE 'contest {target_map}') ORDER BY match_time DESC"
        data = cursor.execute(query)
        rows = data.fetchall()
        data_dict = {}
        # print(len(rows))
        for row in rows:

            data_dict[row[0]] = {"room_link": row[5],
                                   # "stats": json.loads(row[6]),
                                   "date": row[7],
                                   "demo_url":row[9],
                                   "map_name": row[3]
                                   }
        if target_map == '*':
            csv_file_name = "all_matches.csv"
        else:
            csv_file_name = f"{target_map}_matches_1.csv"
            
        # Get the keys from the first dictionary item to use as headers
        headers = data_dict[next(iter(data_dict))].keys()

        with open(csv_file_name, mode='w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)

            # Write the header
            writer.writeheader()

            # Write the data
            for key, value in data_dict.items():
                writer.writerow(value)

    def fix_dates(self):
        cursor = self.conn.cursor()

        query = "SELECT * FROM mapcore_dev_matches"

        data = cursor.execute(query)
        rows = data.fetchall()
        for row in rows:
            if type(row[7]) ==int:
                new_date = str(datetime.datetime.fromtimestamp(row[7]).strftime('%Y-%m-%dT%H:%M:%SZ'))

                print(row[7], new_date)
                cursor.execute(f"UPDATE mapcore_dev_matches SET match_time = '{new_date}' WHERE id = '{row[0]}'")
                self.conn.commit()

        return "done"

if __name__ == "__main__":
    mcdb = MapCoreDb("MapCore_Dev.db")

    mcdb.test_life()
    mcdb.fix_dates()
    mcdb.to_csv("jura")
    #matches = mcdb.print_all("jura")
    #print(matches)
    #for match in matches.values():
    #    print(match["map_name"])
    # results = mcdb.print_all("thera")
    #print(len(matches))

    mcdb.close()
