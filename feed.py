import argparse
import json
import math
import os
import random
import queue
import re
import requests
import time
import nodriver as uc

from bs4 import BeautifulSoup as BS
from shared import *
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def commitChanges():
	repo = git.Repo(".")
	repo.git.add(A=True)
	repo.index.commit("test")

	origin = repo.remote(name="origin")
	origin.push()

def writeFeed(date, loop):
	if not date:
		date = str(datetime.now())[:10]
	url = f"https://baseballsavant.mlb.com/gamefeed?date={date}"
	driver = webdriver.Firefox()
	driver.get(url)
	try:
		element = WebDriverWait(driver, 10).until(
			EC.presence_of_element_located((By.CLASS_NAME, "container-open"))
		)
	except:
		driver.quit()

	with open("feed_times.json") as fh:
		times = json.load(fh)

	headers = {"Accept": "application/vnd.github.v3.raw"}
	url = "https://api.github.com/repos/zhecht/props/contents/static/mlb/schedule.json"
	response = requests.get(url, headers=headers)
	schedule = response.json()

	i = 0
	while True:
		html = driver.page_source
		soup = BS(html, "html.parser")
		#with open(f"feed.html", "w") as fh:
		#	fh.write(html)

		totGames = len(schedule[date])
		games = []
		if date != str(datetime.now())[:10]:
			liveGames = totGames
		else:
			for gameData in schedule[date]:
				try:
					dt = datetime.strptime(gameData["start"], "%I:%M %p")
					dt = int(dt.strftime("%H%M"))
				except:
					dt = 0

				if dt <= int(datetime.now().strftime("%H%M")):
					games.append(gameData)
			liveGames = len(games)
		data = {}
		parseFeed(data, times, games, totGames, soup)
		i += 1

		if not loop:
			break

		time.sleep(1)
		if i >= 5:
			commitChanges()
			i = 0

	driver.quit()

def parseFeed(data, times, games, totGames, soup):
	allTable = soup.find("div", id="allMetrics")
	hdrs = [th.text.lower() for th in allTable.find_all("th")]
	starts = {}
	for game in games:
		starts[game["game"]] = game["start"]
	data = {}
	data["all"] = {k: v.text.strip() for k,v in zip(hdrs,allTable.find_all("td")) if k}
	data["all"]["liveGames"] = len(games)
	data["all"]["totGames"] = totGames
	data["all"]["updated"] = str(datetime.now())
	for div in soup.find_all("div", class_="game-container"):
		away = div.find("div", class_="team-left")
		home = div.find("div", class_="team-right")
		away = convertMLBTeam(away.text.strip())
		home = convertMLBTeam(home.text.strip())
		game = f"{away} @ {home}"
		if game in data:
			game = f"{away}-gm2 @ {home}-gm2"
		data[game] = []
		#table = div.find("div", class_="exit-velocity-table")
		table = div.find("div", class_="mini-ev-table")
		if not table or not table.find("tbody"):
			continue
		for tr in table.find("tbody").find_all("tr"):
			tds = tr.find_all("td")
			player = parsePlayer(tds[1].text.strip())
			#pitcher = parsePlayer(tds[4].text.strip())
			img = tr.find("img").get("src")
			team = convertSavantLogoId(img.split("/")[-1].replace(".svg", ""))
			hrPark = tds[-1].text.strip()

			pa = tds[2].text.strip()
			times.setdefault(game, {}) 
			dt = times[game].get(pa, str(datetime.now()).split(".")[0])
			times[game][pa] = dt
			j = {
				"player": player,
				#"pitcher": pitcher,
				"game": game,
				"hr/park": hrPark,
				"pa": pa,
				"dt": dt,
				"img": img,
				"team": team,
				"start": starts.get(game, "")
			}
			i = 3
			for hdr in ["in", "result", "evo", "la", "dist"]:
				j[hdr] = tds[i].text.strip()
				i += 1

			data[game].append(j)

	with open("feed.json", "w") as fh:
		json.dump(data, fh, indent=4)
	with open("feed_times.json", "w") as fh:
		json.dump(times, fh, indent=4)
	with open("feed_times_historical.json") as fh:
		hist = json.load(fh)
	hist[str(datetime.now())[:10]] = times
	with open("feed_times_historical.json", "w") as fh:
		json.dump(hist, fh)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--sport")
	parser.add_argument("--date", "-d")
	parser.add_argument("--loop", action="store_true")
	parser.add_argument("--clear", action="store_true")
	parser.add_argument("--yest", action="store_true")
	parser.add_argument("--history", action="store_true")
	parser.add_argument("--commit", "-c", action="store_true")

	args = parser.parse_args()

	date = args.date
	if args.yest:
		date = str(datetime.now() - timedelta(days=1))[:10]
	elif not date:
		date = str(datetime.now())[:10]

	if args.history:
		with open("feed_times.json") as fh:
			times = json.load(fh)
		with open("feed_times_historical.json") as fh:
			hist = json.load(fh)
		hist[date] = times
		with open("feed_times_historical.json", "w") as fh:
			json.dump(hist, fh)
		exit()

	if args.clear:
		with open("feed_times.json", "w") as fh:
			json.dump({}, fh)
		exit()

	if args.commit:
		commitChanges()
		exit()

	#time.sleep(7400)
	writeFeed(date, args.loop)