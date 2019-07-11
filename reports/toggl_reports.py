import json
from toggl.TogglPy import Toggl
from os import path, makedirs
import getopt
import sys
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

team_report_template = """

---
### Week of {0}

{1}

#### {2}"""


def user_weekly_report(directory, since, until, api_key, users, workspace):
    """
    Downloads each users weekly reports as a summary and details pdf into their own directories.
    :param workspace:
    :param api_key: The toggl api key to use.
    :param users: The dictionary are users with the key as the user id and the values as the full name.
    :param directory: The root destination directory. Each user will have a sub-directory created for their reports
    :param since: The start date in the form yyyy-MM-dd
    :param until: the end data in the form yyyy-MM-dd. Files will be prepended with this date string.
    :return: None
    """
    logging.info("Downloading user weekly reports from {} until {} into {}".format(since, until, directory))
    toggl = Toggl()
    toggl.setAPIKey(api_key)

    for uid, name in users.items():
        logger.info("Downloading reports for {}".format(name))
        name = users[uid]
        data = {
            'workspace_id': workspace,  # see the next example for getting a workspace id
            'since': since,
            'until': until,
            'user_ids': uid
        }

        folder = path.join(directory, name)

        if not path.exists(folder):
            logger.info("Creating the folder {}".format(folder))
            makedirs(folder)

        details = path.join(folder, until + "-details.pdf")
        summary = path.join(folder, until + "-summary.pdf")

        try:
            toggl.getDetailedReportPDF(data, details)
            logger.info("Downloaded {}".format(details))
            toggl.getSummaryReportPDF(data, summary)
            logger.info("Downloaded {}".format(summary))
        except Exception as e:
            logging.error(e)


def team_weekly_report(destination, since, until, api_key, workspace):
    logger.info("Downloading the team weekly report from {} until {} into {}".format(since, until, destination))
    toggl = Toggl()
    toggl.setAPIKey(api_key)

    data = {
        'workspace_id': workspace,  # see the next example for getting a workspace id
        'since': since,
        'until': until
    }
    try:
        result = toggl.getSummaryReport(data)
    except Exception as e:
        logger.error("Unable to download the team weekly data {}".format(e))
        return

    # Calculate hours and minutes
    total_ms = result['total_grand']
    if total_ms:
        hours, minutes = divmod(total_ms / 1000 / 60, 60)
        time_str = "Total team hours: {:.0f}h {:.0f}m".format(hours, minutes)
    else:
        time_str = "Total team hours: No hours recorded"

    # Find all project worked on
    items_worked_on = [item["title"]["time_entry"] for project in result["data"] for item in project["items"]]
    if len(items_worked_on) == 0:
        items_worked_on = ["No tasks worked on for this time period"]

    # Calculate the pretty data for the start of the week
    date = datetime.strptime(since, "%Y-%m-%d")
    formatted_week = date.strftime("%B %d")
    formatted_items = "- " + "\n- ".join(items_worked_on)
    formatted_team_report = team_report_template.format(formatted_week, formatted_items, time_str)

    logger.info("Created team report:")
    logger.info(formatted_team_report)

    logger.info("Adding to team log file %s", destination)

    with open(destination, "a") as report:
        report.write(formatted_team_report)

    logger.info("Done team report")


if __name__ == '__main__':

    logger.setLevel(logging.INFO)
    opts, args = getopt.getopt(sys.argv[1:], "hp:s:u:")
    now = datetime.now()
    f = ""
    u = now.strftime("%Y-%m-%d")
    s = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    for o, a in opts:
        if o == "-p":
            f = a
        if o == "-s":
            s = a
        if o == "-u":
            u = a
        if o == "-h":
            exit(0)

    if not f:
        f = path.realpath(path.join(path.dirname(path.realpath(__file__)), 'team-logs.md'))

    env_file = path.join(path.dirname(path.realpath(__file__)), '.env')

    with open(env_file) as ef:
        env = json.load(ef)

    # user_weekly_report(f, s, u, env["toggl_api_key"], env["toggl_users"], env["toggl_workspace"])
    team_weekly_report(f, s, u, env["toggl_api_key"], env["toggl_workspace"])
