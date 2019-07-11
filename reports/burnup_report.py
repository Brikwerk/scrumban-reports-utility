import datetime
import json
import logging
import time
from os import path, makedirs

import numpy as np
import pandas as pd
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import requests
from matplotlib import dates as mdates
from matplotlib import pyplot as plt
from matplotlib import ticker as ticker

# Configuring logging
mpl_logger = logging.getLogger("matplotlib")  # Setting matplotlib logging to only log warnings and up
mpl_logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def generate_burnup_chart(board_id, app_key, user_token, save_loc, board_name, regression_amount):
    # Getting data
    logger.info("Getting tasks done/scope")
    curr_cards_done = get_cards_done(board_id, app_key, user_token, board_name)
    curr_cards_total = get_cards_total(board_id, app_key, user_token)
    timestamp = get_timestamp()

    # Saving new data to burnup_data.json
    logger.info("Updating burnup_data.json with fetched data")
    update_burnup_data(curr_cards_done, curr_cards_total, timestamp)

    # Getting chart stats
    logger.info("Calculating burnup stats")
    burnup_stats = get_burnup_stats()

    # Creating/saving chart
    logger.info("Rendering and saving burnup chart at %s" % save_loc)
    render_burnup_chart(burnup_stats, save_loc, regression_amount)


def get_timestamp():
    """Returns the current date as a string formatted YYYY-MM-DD"""

    timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d')
    return timestamp


def get_cards_done(board_id, app_key, user_token, board_name):
    """Fetches and returns the number of cards in the Trello list under the passed name"""

    # Constructing GET request to get all lists on the board
    url = "https://api.trello.com/1/boards/%s/lists?cards=all&key=%s&token=%s" % (board_id, app_key, user_token)

    # Performing GET and parsing to JSON
    response = requests.request("GET", url)
    resp = json.loads(response.text)

    # Searching for list named "Done"
    done_list = None
    for board in resp:
        if board["name"] == board_name:
            done_list = board

    # Returning length of the cards list within the board named "Done"
    return len(done_list["cards"])


def get_cards_total(board_id, app_key, user_token):
    """Fetches and returns the number of total cards within the Trello board"""

    # Constructing GET request to get all cards
    url = "https://api.trello.com/1/boards/%s/cards?key=%s&token=%s" % (board_id, app_key, user_token)

    response = requests.request("GET", url)
    resp = json.loads(response.text)

    return len(resp)


def update_burnup_data(cards_done, cards_total, timestamp):
    """Updates burnup_data.json with new burnup data"""

    # Loading burnup data
    burnup_data = load_burnup_data()

    # Forumlating data json object
    data = {
        "cards_done": cards_done,
        "cards_total": cards_total
    }

    # Inserting into existing data at the timestamp
    burnup_data[timestamp] = data

    # Dumping burnup_data to the json file
    with open("burnup_data.json", "w") as f:
        json.dump(burnup_data, f, indent=2, sort_keys=True)


def get_burnup_stats():
    """
    Retrieves the burnup data and attempts to generate stats for the burnup chart.
    If not enough data is present, an error is thrown. Returns a pandas dataframe.
    """

    # Getting burnup_data
    burnup_data = load_burnup_data()

    # Checking that the burnup data dict isn't empty
    if len(burnup_data) < 1:
        raise ValueError("Burnup Data has length %d. Expected length of at least 1." % len(burnup_data))

    # Collecting lists of stats
    scope_list = []
    done_list = []
    dates_list = []

    # Sorting date keys from the burnup data json object
    sorted_date_keys = sorted(list(burnup_data.keys()))
    for date in sorted_date_keys:
        # Getting data at the date/key location and putting data
        # into the appropriate stat lists
        data = burnup_data[date]
        scope_list.append(data["cards_total"])
        done_list.append(data["cards_done"])
        dates_list.append(datetime.datetime.strptime(date, "%Y-%m-%d"))

    # Populating/creating the stats dataframe
    dataframe = pd.DataFrame({
        "scope": scope_list,
        "done": done_list,
        "dates": dates_list
    })

    return dataframe


def load_burnup_data():
    """Loads burnup_data.json and returns a dict object with the data"""

    # Creating burnup_data.json if it doesn't exist
    if not path.exists("burnup_data.json"):
        with open("burnup_data.json", "w") as f:
            f.write("{}")

    # Loading burnup data from json
    with open("burnup_data.json") as f:
        burnup_data = json.load(f)

    return burnup_data


def render_burnup_chart(stats_df, save_loc, regression_amount):
    """Takes in a Pandas dataframe, produces the burnup chart, and saves it in the specified location"""

    fig, ax = plt.subplots()
    timestamp = get_timestamp()

    # Toggles visibility of vertical lines for dates
    ax.xaxis.grid()

    # Predicting best/likely/worst predictions of completion date
    stats_dates = mdates.date2num(list(
        map(lambda x: x.to_pydatetime(), stats_df["dates"])))  # Converting dataframe values to numpy-readable values
    stats_done = list(map(int, stats_df["done"]))

    # Drawing best fit line if more than one point available
    if len(stats_df["dates"]) > 1:
        # Best-case linear prediction on last 4 periods (if available)
        fit_pred = np.polyfit(stats_done[-regression_amount:], stats_dates[-regression_amount:], 1)
        fit_func = np.poly1d(fit_pred)

        # Predicting the time when the "Done" line reaches the current level of the "Scope" line
        curr_scope = stats_df["scope"][len(stats_df["scope"]) - 1]
        curr_done = stats_df["done"][len(stats_df["done"]) - 1]
        curr_date = stats_df["dates"][len(stats_df["dates"]) - 1]
        finish_date = mdates.num2date(fit_func(curr_scope)).replace(
            tzinfo=None)  # Removing timezone info after conversion to python datetime

        # Constructing line plots for best fit line
        fit_line_x = [curr_date, finish_date]
        fit_line_y = [curr_done, curr_scope]

        plt.plot(fit_line_x, fit_line_y, linewidth=3, markersize=10, color="#2ca02c", linestyle='dashed', label="Predicted")

        # Drawing continuation of the scope line
        cont_line_x = [curr_date, finish_date]
        cont_line_y = [curr_scope, curr_scope]
        plt.plot(cont_line_x, cont_line_y, linewidth=3, marker="o", markersize=10, color="#1f77b4", label=None)

        # Annotating the finish date
        plt.text(0.97, 0.05,"Est. Finish Date: %s" % finish_date.strftime("%b %d"),
            horizontalalignment="right",
            verticalalignment="center",
            color="#2ca02c",
            weight="bold",
            size= 16,
            bbox=dict(facecolor='white', alpha=0.5, lw=0),
            transform = ax.transAxes)

    # Turning off x-axis ticks and displaying x-axis title
    ax.get_yaxis().set_ticks([])
    plt.ylabel("Tasks")

    # Drawing the title
    plt.title("Burnup Chart %s" % get_timestamp())

    plt.plot("dates", "scope", data=stats_df, linewidth=3, marker="o", markersize=10, label="Scope")
    plt.plot("dates", "done", data=stats_df, linewidth=3, marker="o", markersize=10, label="Done")
    plt.legend()

    # Increasing y-axis max by 8% and x-axis max by 4% to make room for annotations
    ybottom, ytop = plt.ylim()
    xbottom, xtop = plt.xlim()
    plt.ylim((ybottom, ytop * 1.08))
    plt.xlim((xbottom, xtop))

    # Annotating the points with the value
    # Getting number of points to jump when drawing the number on a point
    jumpNum = 1
    if len(stats_df["dates"]) > 5:
        jumpNum = int(len(stats_df["dates"])/5)
    # Putting done numbers on graph
    for i in range(0, len(stats_df["dates"]), jumpNum):
        date = stats_df["dates"][i]
        done_num = stats_df["done"][i]
        scope_num = stats_df["scope"][i]
        # If we're within a jump to the last point,
        # Make the last point's annotation larger
        if (i+jumpNum) > (len(stats_df["dates"]) - 1):
            date = stats_df["dates"][len(stats_df["dates"]) - 1]
            done_num = stats_df["done"][len(stats_df["done"]) - 1]
            scope_num = stats_df["scope"][len(stats_df["scope"]) - 1]
            ax.annotate(done_num, xy=(date, done_num), xytext=(-5, 9), textcoords='offset points', weight="bold",
                        ha='center', color="#ff7f0e", size=18)
            ax.annotate(scope_num, xy=(date, scope_num), xytext=(-5, 9), textcoords='offset points', weight="bold",
                        ha='center', color="#1f77b4", size=18)
            break
        else:
            ax.annotate(done_num, xy=(date, done_num), xytext=(-5, 9), textcoords='offset points', weight="bold",
                        ha='center', color="#ff7f0e", size=13)
            ax.annotate(scope_num, xy=(date, scope_num), xytext=(-5, 9), textcoords='offset points', weight="bold",
                        ha='center', color="#1f77b4", size=13)

    # Setting x-axis dates to three letter month + date format
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    if len(stats_df["dates"]) > 1:
        days_between = int((stats_df["dates"][len(stats_df["dates"])-1] - stats_df["dates"][0]).days)
        if days_between > 32:
            # Tigther tick rate
            ax.xaxis.set_major_locator(ticker.MultipleLocator(days_between/4))
        else:
            # Looser tick rate
            ax.xaxis.set_major_locator(ticker.MultipleLocator(days_between/2))
    else:
        # If we only have a single point,
        # Set a high tick rate to combat improper formatting
        ax.xaxis.set_major_locator(ticker.MultipleLocator(1200))

    # Packing layout
    plt.tight_layout()

    # Saving plot
    if not save_loc == "" and not path.exists(save_loc):
        makedirs(save_loc)

    burnup_save_loc = path.join(save_loc, 'burnup-%s.png' % timestamp)

    plt.savefig(burnup_save_loc, dpi=150)
    plt.close()
