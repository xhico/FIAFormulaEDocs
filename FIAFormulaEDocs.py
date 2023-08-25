# -*- coding: utf-8 -*-
# !/usr/bin/python3


import datetime
import json
import os
import urllib.request
import urllib.parse
import tweepy
import yagmail
import pdf2image
import shutil
import re
import psutil
import requests
import traceback
import logging
from Misc import get911


def getResults(board):
    """
    Retrieves the most recent timing or notice results for a given Formula E board.

    Args:
        board (str): The name of the board to retrieve results for. Must be either "timings" or "notices".

    Returns:
        dict: A nested dictionary containing the most recent season, race, and relevant documents for the specified board.

    Raises:
        KeyError: If the results dictionary does not contain the expected keys.

    Example usage:
        >>> getResults("timings")
        {
            "2022-23 Season": {
                "Race 1": {
                    "ABB FIA Formula E World Championship": [
                        {"name": "Championship Results", "url": "http://example.com/championship_results.pdf"},
                        {"name": "Driver Standings", "url": "http://example.com/driver_standings.pdf"}
                    ],
                    "Event Information": [
                        {"name": "Schedule", "url": "http://example.com/schedule.pdf"}
                    ]
                }
            }
        }
    """

    # Download JSON Timing Results
    if board == "timings":
        results = json.loads(requests.get(timingsURL).content)
    elif board == "notices":
        results = json.loads(requests.get(noticesURL).content)
    else:
        results = {}

    # Get last season && name
    lastSeason = results["folders"][0]["children"][-1]
    lastSeasonName, championshipDocs, eventDocs = lastSeason["name"], [], []

    # Log the last season name.
    logger.info("lastSeasonName - " + lastSeasonName)

    # Get last race
    lastRace = lastSeason["children"][-1]
    lastRaceName = lastRace["name"]

    # Log the last race name.
    logger.info("lastRaceName - " + lastRaceName)

    # Get Folder
    if "children" not in lastRace.keys():
        logger.error("No children in " + lastRaceName)
        return {}

    for folder in lastRace["children"]:
        if folder["name"] == "ABB FIA Formula E World Championship":
            try:
                if board == "timings":
                    # Retrieve championship documents for timing board.
                    championshipDocs = [{"name": doc["name"], "url": doc["url"]} for subfolder in folder["children"] for doc in subfolder["children"] if doc["extension"] == "pdf"]
                elif board == "notices":
                    # Retrieve championship documents for notice board.
                    championshipDocs = [{"name": doc["name"], "url": doc["url"]} for doc in folder["children"] if doc["extension"] == "pdf"]
            except Exception:
                pass

        elif folder["name"] == "Event Information":
            try:
                # Retrieve event documents.
                eventDocs = [{"name": doc["name"], "url": doc["url"]} for doc in folder["children"] if doc["extension"] == "pdf"]
            except Exception:
                pass

    # Return nested dictionary with most recent season, race, and relevant documents for the specified board.
    documents = {lastSeasonName: {lastRaceName: {"ABB FIA Formula E World Championship": championshipDocs, "Event Information": eventDocs}}}
    return documents


def getLog(board):
    """
    This function takes in a string argument 'board' and returns a Python dictionary representing the log data stored
    in a JSON file associated with that board. If the JSON file doesn't exist, an empty dictionary is returned instead.

    Args:
    - board (str): A string argument representing the board name for which the log data is to be retrieved.

    Returns:
    - log (dict): A Python dictionary containing the log data associated with the specified board. If the JSON file
    doesn't exist, an empty dictionary is returned.
    """
    try:
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + board + ".json")  # constructs the file path for the log file associated with the specified board
        with open(log_file) as inFile:  # opens the log file
            log = json.load(inFile)  # reads the JSON data from the log file and loads it into a Python dictionary
    except Exception:  # if an error occurs (e.g., log file not found), an empty dictionary is returned
        log = {}

    return log  # returns the Python dictionary containing the log data


def parseDocuments(documents, board):
    """
    Given a dictionary of documents and a board name, updates the board's log with new documents and returns
    the last season and race names, the new documents that were added, and the updated log.

    Parameters:
    documents (dict): A dictionary containing season and race names as keys and a dictionary of folders with their
                      associated documents as values.
    board (str): The name of the board to update.

    Returns:
    tuple: A tuple containing the last season and race names, a dictionary of new documents added, and the updated log.

    """
    # Initialize variables
    lastSeasonName, lastRaceName, newDocs = "", "", {}

    # Load board log
    log = getLog(board)

    # Iterate over seasons in the documents
    for lastSeasonName in documents.keys():
        # If the season is not in the board's log, add it
        if lastSeasonName not in log.keys():
            log[lastSeasonName] = {}

        # Iterate over races in the season
        for lastRaceName in documents[lastSeasonName].keys():
            # If the race is not in the board's log, add it
            if lastRaceName not in log[lastSeasonName].keys():
                log[lastSeasonName][lastRaceName] = {}

            # Iterate over folders in the race
            for folderName, docs in documents[lastSeasonName][lastRaceName].items():
                # If the folder is not in the board's log, add it
                if folderName not in log[lastSeasonName][lastRaceName].keys():
                    log[lastSeasonName][lastRaceName][folderName] = []

                # Add new documents to the folder
                newDocs[folderName] = [doc for doc in docs if doc not in log[lastSeasonName][lastRaceName][folderName]]

    # Return the last season and race names, the new documents added, and the updated log
    return lastSeasonName, lastRaceName, newDocs, log


def getScreenshots(pdfURL):
    """
    Downloads a PDF from a given URL and saves the first four pages as JPGs.

    Args:
        pdfURL (str): The URL of the PDF to download.

    Returns:
        bool: True if screenshots were successfully saved, False otherwise.
    """
    try:
        # Reset tmpFolder
        tmpFolder = "./tmp"
        if os.path.exists(tmpFolder):
            shutil.rmtree(tmpFolder)
        os.mkdir(tmpFolder)

        # Download PDF
        pdfFile = os.path.join(tmpFolder, "tmp.pdf")
        urllib.request.urlretrieve(pdfURL, pdfFile)

        # Check what OS
        if os.name == "nt":
            # Set poppler_path for Windows
            poppler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poppler-win\Library\bin")
            # Convert PDF to images using poppler_path
            pages = pdf2image.convert_from_path(poppler_path=poppler_path, pdf_path=pdfFile)
        else:
            # Convert PDF to images using default settings
            pages = pdf2image.convert_from_path(pdf_path=pdfFile)

        # Save the first four pages as JPGs
        for idx, page in enumerate(pages[0:4]):
            jpgFile = os.path.join(tmpFolder, "tmp_" + str(idx) + ".jpg")
            page.save(jpgFile)

        # Set hasPics to True if screenshots were successfully saved
        hasPics = True
    except Exception:
        # Log an error if screenshots could not be saved
        logger.error("Failed to screenshot")
        # Set hasPics to False if screenshots could not be saved
        hasPics = False

    return hasPics


def tweet(tweetStr):
    """
    Uploads and tweets an image with a given status message.

    Args:
        tweetStr (str): The message to be tweeted.

    Returns:
        None
    """

    try:
        # Get a sorted list of all JPG files in the temporary folder
        imageFiles = sorted([os.path.join(tmpFolder, file) for file in os.listdir(tmpFolder) if file.split(".")[-1] == "jpg"])

        # Upload each image and get its media ID
        media_ids = [api.media_upload(os.path.join(tmpFolder, image)).media_id_string for image in imageFiles]

        # Tweet the message along with the media IDs
        api.update_status(status=tweetStr, media_ids=media_ids)

        # Log a success message
        logger.info("Tweeted")

    except Exception as ex:
        # Log an error message if the tweet fails
        logger.error("Failed to Tweet")

        # Send an email notification with the error message and tweet content
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Failed to Tweet - " + os.path.basename(__file__), str(ex) + "\n\n" + tweetStr)


def batchDelete():
    """
    Deletes all tweets from the authenticated user's Twitter account using Tweepy API.

    Parameters:
        None

    Returns:
        None
    """

    # get the username of the authenticated user
    username = api.verify_credentials().screen_name

    # log a message indicating the start of the tweet deletion process
    logger.info("Deleting all tweets from the account @" + username)

    # iterate over all tweets from the authenticated user's timeline using the Cursor object
    for status in tweepy.Cursor(api.user_timeline).items():

        try:
            # delete the tweet using the destroy_status() method of Tweepy API
            api.destroy_status(status.id)

        except Exception:
            # catch any exceptions raised during tweet deletion and ignore them
            pass


def postDocs(lastSeason: str, lastRace: str, documents: dict, log: dict, board: str):
    """
    Posts documents on a social media platform along with their title, date, and hashtags.

    Parameters:
    lastSeason (str): The last season of the race.
    lastRace (str): The last race of the season.
    documents (dict): A dictionary of documents, with their names and URLs.
    log (dict): A log of previously posted documents.
    board (str): The name of the social media platform.

    Returns:
    None
    """

    # Generate hashtags based on last race and season
    hashtags = "#" + "".join(lastRace.split(" ")[1::]) + " #" + "".join(lastRace.split(" ")[1::]) + "EPrix" + " #FormulaE #ABBFormulaE"

    # Iterate over new documents
    for folder, docs in documents.items():
        for doc in docs:
            # Add new documents to the log
            log[lastSeason][lastRace][folder].append(doc)

            # Set post title
            postTitle = doc["name"]
            postTitle = re.sub("[^a-zA-Z0-9 \n.]", " ", postTitle).replace(".PDF", "").replace(".pdf", "")
            postTitle = re.sub('\\s+', ' ', postTitle)
            logger.info(postTitle)

            # Set post date
            postDate = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y/%m/%d %H:%M UTC")

            # Screenshot PDF
            pdfURL = doc["url"].replace(" ", "%20")
            getScreenshots(pdfURL)

            # Post tweet with title, date, PDF URL, and hashtags
            tweet(postTitle + "\n\n" + "Published at: " + postDate + "\n\n" + pdfURL + "\n\n" + hashtags)

    # Save log to file
    boardLogfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + board + ".json")
    with open(boardLogfile, "w") as outFile:
        json.dump(log, outFile, indent=2)


def main():
    """
    Main function to run the program. This function fetches timing and notice results,
    parses them and posts the results to a database.

    Returns:
    None
    """
    # Log that we are starting to fetch timing results
    logger.info("getTimingResults")
    # Get timing results
    timings = getResults("timings")
    # Log that we are starting to fetch notice results
    logger.info("getNoticesResults")
    # Get notice results
    notices = getResults("notices")

    # Log that we are starting to parse timing documents
    logger.info("parseDocuments - timings")
    # Parse timing documents and store the results
    lastTimingsSeasonName, lastTimingsRaceName, newTimings, timingsLog = parseDocuments(timings, "timings")
    # Log that we are starting to parse notice documents
    logger.info("parseDocuments - notices")
    # Parse notice documents and store the results
    lastNoticesSeasonName, lastNoticesName, newNotices, noticesLog = parseDocuments(notices, "notices")

    # Log that we are starting to post timing documents to the database
    logger.info("postDocs - timings")
    # Post timing documents to the database
    postDocs(lastTimingsSeasonName, lastTimingsRaceName, newTimings, timingsLog, "timings")
    # Log that we are starting to post notice documents to the database
    logger.info("postDocs - notices")
    # Post notice documents to the database
    postDocs(lastNoticesSeasonName, lastNoticesName, newNotices, noticesLog, "notices")


if __name__ == "__main__":
    # Set Logging
    LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.abspath(__file__).replace(".py", ".log"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
    logger = logging.getLogger()

    CONSUMER_KEY = get911('TWITTER_FORMULAE_CONSUMER_KEY')
    CONSUMER_SECRET = get911('TWITTER_FORMULAE_CONSUMER_SECRET')
    ACCESS_TOKEN = get911('TWITTER_FORMULAE_ACCESS_TOKEN')
    ACCESS_TOKEN_SECRET = get911('TWITTER_FORMULAE_ACCESS_TOKEN_SECRET')
    EMAIL_USER = get911('EMAIL_USER')
    EMAIL_APPPW = get911('EMAIL_APPPW')
    EMAIL_RECEIVER = get911('EMAIL_RECEIVER')

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)

    logger.info("----------------------------------------------------")

    # Set temp folder -> Create logs and tmp folder
    tmpFolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")

    # Set Results URLs
    timingsURL = "https://results.fiaformulae.com/en/s3/feed/v2/results.json"
    noticesURL = "https://results.fiaformulae.com/en/s3/feed/noticeboard/v2/results.json"

    # Check if script is already running
    procs = [proc for proc in psutil.process_iter(attrs=["cmdline"]) if os.path.basename(__file__) in '\t'.join(proc.info["cmdline"])]
    if len(procs) > 2:
        logger.info("isRunning")
    else:
        try:
            main()
        except Exception as ex:
            logger.error(traceback.format_exc())
            yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Error - " + os.path.basename(__file__), str(traceback.format_exc()))
        finally:
            logger.info("End")
