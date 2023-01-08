# -*- coding: utf-8 -*-
# !/usr/bin/python3

# python3 -m pip install yagmail tweepy pdf2image psutil --no-cache-dir
# sudo apt install poppler-utils -y

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
    logger.info("lastSeasonName - " + lastSeasonName)

    # Get last race
    lastRace = lastSeason["children"][-1]
    lastRaceName = lastRace["name"]
    logger.info("lastRaceName - " + lastRaceName)

    # Get Folder
    if "children" not in lastRace.keys():
        logger.error("No children in " + lastRaceName)
        return {}
        
    for folder in lastRace["children"]:
        if folder["name"] == "ABB FIA Formula E World Championship":
            try:
                if board == "timings":
                    championshipDocs = [{"name": doc["name"], "url": doc["url"]} for subfolder in folder["children"] for doc in subfolder["children"] if doc["extension"] == "pdf"]
                elif board == "notices":
                    championshipDocs = [{"name": doc["name"], "url": doc["url"]} for doc in folder["children"] if doc["extension"] == "pdf"]
            except Exception:
                pass

        elif folder["name"] == "Event Information":
            try:
                eventDocs = [{"name": doc["name"], "url": doc["url"]} for doc in folder["children"] if doc["extension"] == "pdf"]
            except Exception:
                pass

    documents = {lastSeasonName: {lastRaceName: {"ABB FIA Formula E World Championship": championshipDocs, "Event Information": eventDocs}}}
    return documents


def getLog(board):
    try:
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + board + ".json")
        with open(log_file) as inFile:
            log = json.load(inFile)
    except Exception:
        log = {}

    return log


def parseDocuments(documents, board):
    lastSeasonName, lastRaceName, newDocs = "", "", {}

    # Load board log
    log = getLog(board)

    for lastSeasonName in documents.keys():
        if lastSeasonName not in log.keys():
            log[lastSeasonName] = {}

        for lastRaceName in documents[lastSeasonName].keys():
            if lastRaceName not in log[lastSeasonName].keys():
                log[lastSeasonName][lastRaceName] = {}

            for folderName, docs in documents[lastSeasonName][lastRaceName].items():
                if folderName not in log[lastSeasonName][lastRaceName].keys():
                    log[lastSeasonName][lastRaceName][folderName] = []

                newDocs[folderName] = [doc for doc in docs if doc not in log[lastSeasonName][lastRaceName][folderName]]

    return lastSeasonName, lastRaceName, newDocs, log


def getScreenshots(pdfURL):
    try:
        # Reset tmpFolder
        if os.path.exists(tmpFolder):
            shutil.rmtree(tmpFolder)
        os.mkdir(tmpFolder)

        # Download PDF
        pdfFile = os.path.join(tmpFolder, "tmp.pdf")
        urllib.request.urlretrieve(pdfURL, pdfFile)

        # Check what OS
        if os.name == "nt":
            poppler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poppler-win\Library\bin")
            pages = pdf2image.convert_from_path(poppler_path=poppler_path, pdf_path=pdfFile)
        else:
            pages = pdf2image.convert_from_path(pdf_path=pdfFile)

        # Save the first four pages
        for idx, page in enumerate(pages[0:4]):
            jpgFile = os.path.join(tmpFolder, "tmp_" + str(idx) + ".jpg")
            page.save(jpgFile)
        hasPics = True
    except Exception:
        logger.error("Failed to screenshot")
        hasPics = False

    return hasPics


def tweet(tweetStr):
    try:
        imageFiles = sorted([os.path.join(tmpFolder, file) for file in os.listdir(tmpFolder) if file.split(".")[-1] == "jpg"])
        media_ids = [api.media_upload(os.path.join(tmpFolder, image)).media_id_string for image in imageFiles]
        api.update_status(status=tweetStr, media_ids=media_ids)
        logger.info("Tweeted")
    except Exception as ex:
        logger.error("Failed to Tweet")
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Failed to Tweet - " + os.path.basename(__file__), str(ex) + "\n\n" + tweetStr)


def batchDelete():
    logger.info("Deleting all tweets from the account @" + api.verify_credentials().screen_name)
    for status in tweepy.Cursor(api.user_timeline).items():
        try:
            api.destroy_status(status.id)
        except Exception:
            pass


def postDocs(lastSeason, lastRace, documents, log, board):
    hashtags = "#" + "".join(lastRace.split(" ")[1::]) + " #" + "".join(lastRace.split(" ")[1::]) + "EPrix" + " #FormulaE #ABBFormulaE"

    # Iterate over new docs
    for folder, docs in documents.items():
        for doc in docs:
            log[lastSeason][lastRace][folder].append(doc)

            # Set title
            postTitle = doc["name"]
            postTitle = re.sub("[^a-zA-Z0-9 \n.]", " ", postTitle).replace(".PDF", "").replace(".pdf", "")
            postTitle = re.sub('\\s+', ' ', postTitle)
            logger.info(postTitle)

            # Set date
            postDate = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y/%m/%d %H:%M UTC")

            # Screenshot DPF
            pdfURL = doc["url"].replace(" ", "%20")
            getScreenshots(pdfURL)

            # Tweet!
            tweet(postTitle + "\n\n" + "Published at: " + postDate + "\n\n" + pdfURL + "\n\n" + hashtags)

    # Save Log
    boardLogfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + board + ".json")
    with open(boardLogfile, "w") as outFile:
        json.dump(log, outFile, indent=2)


def main():
    logger.info("getTimingResults")
    timings = getResults("timings")
    logger.info("getNoticesResults")
    notices = getResults("notices")

    logger.info("parseDocuments - timings")
    lastTimingsSeasonName, lastTimingsRaceName, newTimings, timingsLog = parseDocuments(timings, "timings")
    logger.info("parseDocuments - notices")
    lastNoticesSeasonName, lastNoticesName, newNotices, noticesLog = parseDocuments(notices, "notices")

    logger.info("postDocs - timings")
    postDocs(lastTimingsSeasonName, lastTimingsRaceName, newTimings, timingsLog, "timings")
    logger.info("postDocs - notices")
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
