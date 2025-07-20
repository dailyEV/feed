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

from supabase import create_client

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

	url = "https://nkdhryqpiulrepmphwmt.supabase.co"
	key = os.environ.get("SUPABASE_KEY")
	if False and not key:
		print("Need SUPABASE_KEY")
		driver.quit()
		exit()

	#psql = create_client(url, key)

	headers = {
		"Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
		"Accept": "application/vnd.github.v3.raw"
	}
	url = "https://api.github.com/repos/dailyev/props/contents/static/mlb/schedule.json"
	response = requests.get(url, headers=headers)
	schedule = response.json()
	inserted = {}

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
		parseFeed(date, data, times, games, totGames, soup, inserted)
		i += 1

		if not loop:
			break

		#upsertFeed(psql, data, inserted)

		time.sleep(1)
		if i >= 5:
			commitChanges()
			i = 0

	driver.quit()

def feedKey(row):
	return f"{row['dt']}-{row['game']}-{row['player']}-{row['pa']}-{row['result']}-{row['dist']}"

async def upsertFeed(psql, data, inserted):
	rows = []
	for game, arr in data.items():
		if game == "all":
			continue
		for row in arr:
			key = feedKey(row)
			if key not in inserted:
				inserted[key] = True
				rows.append(row)

	if rows:
		print(f"Inserting {len(rows)} rows")
		await supabase.table("Feed").upsert(rows).execute()

def parseFeed(date, data, times, games, totGames, soup, inserted):
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
				"created_at": dt,
				"player": player,
				"game": game,
				"hr/park": hrPark,
				"pa": pa,
				"dt": date,
				"team": team,
				"stadium": game.split(" @ ")[-1].replace("-gm2", "")
			}
			i = 3
			for hdr in ["in", "result", "evo", "la", "dist"]:
				j[hdr] = tds[i].text.strip()
				i += 1

			j["is_hh"] = isHH(j)
			j["is_brl"] = isBarrel(j)

			data[game].append(j)

	with open("feed.json", "w") as fh:
		json.dump(data, fh)

	with open("updated") as fh:
		updated = float(fh.read().strip() or 0)
	now = time.time()
	if now - updated >= 5*60:
		with open("feed_free.json", "w") as fh:
			json.dump(data, fh)
		with open("updated", "w") as fh:
			fh.write(str(now))
			
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

	writeFeed(date, args.loop)

	if args.commit:
		commitChanges()
		exit()