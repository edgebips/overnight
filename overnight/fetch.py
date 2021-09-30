"""Fetch lists of earnings from websites."""

__copyright__ = "Copyright (C) 2021  Martin Blais"
__license__ = "GNU GPLv2"

import logging
import csv
import sys
import itertools
import time
import io
from os import path
from typing import Optional

import click
from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.common.by import By


# Time for fixed waits.
WAIT_SECS = 1


def get_tickers(driver):
    # Get the list of tickers.
    tickers = []
    for ticker in driver.find_elements(By.CLASS_NAME, 'ticker'):
        if ticker.text:
            tickers.append(ticker.text)
    return tickers


def fetch_earnings_whispers_list(headless: bool) -> str:
    """Obtain the URL to the latest version."""

    # Create driver.
    opts = options.Options()
    opts.headless = headless
    driver = webdriver.Chrome(executable_path="chromium.chromedriver", options=opts)
    driver.implicitly_wait(3)

    # Open home page.
    driver.get('https://www.earningswhispers.com/calendar')

    # Choose the list view.
    div = driver.find_element(By.ID, 'chooseview')
    label = div.find_element(By.CLASS_NAME, 'switch-label-all')
    label.click()
    time.sleep(WAIT_SECS)

    # Choose AMC.
    div = driver.find_element(By.ID, 'beforaft')
    label = div.find_element(By.CLASS_NAME, 'switch-label-amc')
    label.click()
    time.sleep(WAIT_SECS)

    # Open up the bottom list and wait to ensure it loads.
    # TODO(blais): Find the right element to wait on.
    div = driver.find_element(By.ID, 'showmore')
    div.click()
    time.sleep(WAIT_SECS)

    # Get the list of AMC tickers.
    tickers_amc = get_tickers(driver)

    # Click on the next day.
    nextday = driver.find_element(By.CLASS_NAME, "nottoday")
    nextday.click()
    time.sleep(WAIT_SECS)

    # Choose BMO.
    div = driver.find_element(By.ID, 'beforaft')
    label = div.find_element(By.CLASS_NAME, 'switch-label-bmo')
    label.click()

    # Open up the bottom list and wait to ensure it loads.
    # TODO(blais): Find the right element to wait on.
    div = driver.find_element(By.ID, 'showmore')
    div.click()
    time.sleep(WAIT_SECS)

    # Get the list of BMO tickers.
    tickers_bmo = get_tickers(driver)

    return tickers_amc, tickers_bmo
