import getopt
import json
import logging
import sys
import traceback
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from os import path

from reports import user_weekly_report, team_weekly_report, generate_burnup_chart

# Logger constants

MAIN_LOG_FILE_NAME = 'reports.log'
LOG_FORMAT = '%(asctime)-15s | %(levelname)-8s: %(message)s'  # Format for log
LOG_SIZE = 500000  # In Bytes -> 1,000,000 Bytes = 1 MB
LOG_BACKUPS = 3

# Configuring the logger
logging.basicConfig(
    format=LOG_FORMAT,
    handlers=[RotatingFileHandler(MAIN_LOG_FILE_NAME, maxBytes=LOG_SIZE, backupCount=LOG_BACKUPS),
              logging.StreamHandler()],
    level=logging.DEBUG
)

# Setting log level and logger name
logger = logging.getLogger('__name__')
logger.setLevel(logging.INFO)

help_text = """
--Automated Scrumban Reports Utility--

Downloads and generates the capstone burnup chart, the individual reports, and the team report.

Usage:
    -p : Specifies the file path to store the folders and reports. Defaults to ../docs/weekly reports relative to this
    file.
    -s : Specifies the start date for the reports in the form: YYYY-MM-DD Defaults to 7 days from today
    -u : Specifies the end date for the reports in the form: YYY-MM-DD Defaults to today
    -b : Specifies Trello board name to check for the number of done tasks. Defaults to 'Done'.
    -r : Specifies how many points are included in the linear regression for the burnup chart. Defaults to 4.

    Example usage:

    python run_reports.py -s 2018-10-10 -u 2018-10-16
"""


def main(directory, since, until, board_name, regression_amount):
    try:
        # Checking env variables are present
        if path.isfile(".env"):
            # Loading keys and IDs
            with open('.env') as f:
                env = json.load(f)
        else:
            raise OSError("Environment file could not be found. Please make sure to copy the example and fill it out.")

        # Creating burnup chart
        generate_burnup_chart(env["trello_board_id"], env["trello_app_key"], env["trello_bot_token"], 
                            path.join(directory, "Burnup Charts"), board_name, regression_amount)

        # Personal logs
        user_weekly_report(directory, since, until, env["toggl_api_key"], env["toggl_users"],
                           env["toggl_workspace"])

        # Team report
        team_file = path.join(directory, "team-logs.md")
        team_weekly_report(team_file, since, until, env["toggl_api_key"], env["toggl_workspace"])

    except Exception as e:
        logger.exception("Report Generation Error")


if __name__ == "__main__":

    if __package__ is None:
        import sys
        from os import path

        sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

    # Starting log
    logger.warning("---------------Starting Log---------------")
    opts, args = getopt.getopt(sys.argv[1:], "hd:s:u:")
    now = datetime.now()
    destination_arg = ""
    until_arg = now.strftime("%Y-%m-%d")
    since_arg = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    board_name = "Done"
    regression_amount = 4
    for o, a in opts:
        if o == "-p":
            destination_arg = a
        if o == "-s":
            since_arg = a
        if o == "-u":
            until_arg = a
        if o == "-h":
            print(help_text)
            exit(0)
        if o == "-b":
            board_name = a
        if o == "r":
            regression_amount = int(a)

    if not destination_arg:
        destination_arg = path.realpath(path.join(path.dirname(path.realpath(__file__)), 'Scrumban Reports'))

    main(destination_arg, since_arg, until_arg, board_name, regression_amount)
