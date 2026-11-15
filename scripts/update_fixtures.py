#!/usr/bin/env python3
"""Fetch verified fixtures for KampKart. Never synthesize dates or opponents."""
import json, datetime, pathlib, urllib.request, urllib.parse, time, re
OUT=pathlib.Path("data/matches.json")
HEAD={"User-Agent":"KampKart/1.0 (public fixture aggregation)","Accept":"application/json"}
CLUBS={"glimt":("nor.1",["Bodø/Glimt","Bodo/Glimt","Bodø Glimt"]),"viking":("nor.1",["Viking FK","Viking"]),"molde":("nor.1",["Molde FK","Molde"]),"united":("eng.1",["Manchester United"]),"arsenal":("eng.1",["Arsenal"])}
HOME={"glimt":"Bodø","viking":"Stavanger","molde":"Molde","united":"Manchester","arsenal":"London","kings":"Los Angeles","sabres":"Buffalo"}
NOR={"Bodø/Glimt":"Bodø","Bodo/Glimt":"Bodø","Viking":"Stavanger","Molde":"Molde","Rosenborg":"Trondheim","Brann":"Bergen","Tromsø":"Tromsø","Vålerenga":"Oslo","KFUM Oslo":"Oslo","Lillestrøm":"Lillestrøm","Fredrikstad":"Fredrikstad","Sarpsborg 08":"Sarpsborg","Sandefjord":"Sandefjord","Kristiansund":"Kristiansund","Aalesund":"Ålesund","HamKam":"Hamar","Haugesund":"Haugesund","Strømsgodset":"Drammen","Odd":"Skien","Bryne":"Bryne","Start":"Kristiansand","Sogndal":"Sogndal"}
ENG={"Arsenal":"London","Manchester United":"Manchester","Manchester City":"Manchester","Liverpool":"Liverpool","Everton":"Liverpool","Chelsea":"London","Tottenham Hotspur":"London","Tottenham":"London","West Ham United":"London","West Ham":"London","Crystal Palace":"London","Fulham":"London","Brentford":"London","Newcastle United":"Newcastle","Newcastle":"Newcastle","Aston Villa":"Birmingham","Birmingham City":"Birmingham","Wolverhampton Wanderers":"Wolverhampton","Wolves":"Wolverhampton","Nottingham Forest":"Nottingham","Leicester City":"Leicester","Leeds United":"Leeds","Leeds":"Leeds","Brighton & Hove Albion":"Brighton","Brighton":"Brighton","AFC Bournemouth":"Bournemouth","Bournemouth":"Bournemouth","Southampton":"Southampton","Sunderland":"Sunderland","Burnley":"Burnley","Ipswich Town":"Ipswich","Sheffield United":"Sheffield"}
NHL={"ANA":"Anaheim","BOS":"Boston","BUF":"Buffalo","CAR":"Raleigh","CBJ":"Columbus","CGY":"Calgary","CHI":"Chicago","COL":"Denver","DAL":"Dallas","DET":"Detroit","EDM":"Edmonton","FLA":"Miami","LAK":"Los Angeles","MIN":"Minneapolis","MTL":"Montreal","NJD":"Newark","NSH":"Nashville","NYI":"New York","NYR":"New York","OTT":"Ottawa","PHI":"Philadelphia","PIT":"Pittsburgh","SEA":"Seattle","SJS":"San Jose","STL":"St Louis","TBL":"Tampa","TOR":"Toronto","UTA":"Salt Lake City","VAN":"Vancouver","VGK":"Las Vegas","WPG":"Winnipeg","WSH":"Washington"}
def get(url):
    req=urllib.request.Request(url,headers=HEAD)
    with urllib.request.urlopen(req,timeout=28) as response:return json.load(response)
def text(v):
    if isinstance(v,dict):return v.get("default") or v.get("en") or v.get("displayName") or ""
    return str(v or "")
def norm(s):return re.sub(r"[^a-z0-9]","",str(s).casefold().replace("ø","o").replace("å","a").replace("æ","ae"))
def soccer():
    games=[]
    # ESPN season-wide scoreboards avoid relying on the team catalog endpoint.
    for league in ("nor.1","eng.1"):
        for season in (2026,2027) if league=="nor.1" else (2025,2026):
            try:
                url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={season}&limit=1000"
                payload=get(url)
                events=payload.get("events",[])
                print("scoreboard",league,season,len(events))
                for event in events:
                    date=str(event.get("date",""))[:10]
                    if not ("2026-01-01"<=date<="2027-12-31"):continue
                    sides=(event.get("competitions") or [{}])[0].get("competitors",[])
                    if len(sides)<2:continue
                    for team,(target_league,names) in CLUBS.items():
                        if target_league!=league:continue
                        ours=next((x for x in sides if norm(x.get("team",{}).get("displayName","")) in {norm(n) for n in names}),None)
                        if ours is None:continue
                        theirs=next((x for x in sides if x is not ours),None)
                        if theirs is None:continue
                        opponent=theirs.get("team",{}).get("displayName","")
                        city=HOME[team] if ours.get("homeAway")=="home" else (NOR if league=="nor.1" else ENG).get(opponent)
                        if city:games.append({"team":team,"date":date,"opponent":opponent,"city":city,"source":"ESPN "+league})
            except Exception as e:print("ERROR scoreboard",league,season,e)
    # Fallback: fetch team schedules directly by ESPN's stable club IDs.
    # ESPN soccer team IDs: Arsenal 359, Manchester United 360.
    ids={"arsenal":"359","united":"360"}
    for team,tid in ids.items():
        for season in (2025,2026):
            try:
                url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/{tid}/schedule?season={season}&limit=500"
                payload=get(url)
                print("team schedule",team,season,len(payload.get("events",[])))
                for event in payload.get("events",[]):
                    date=str(event.get("date",""))[:10]
                    if not ("2026-01-01"<=date<="2027-12-31"):continue
                    sides=(event.get("competitions") or [{}])[0].get("competitors",[])
                    ours=next((x for x in sides if str(x.get("team",{}).get("id",""))==tid),None)
                    theirs=next((x for x in sides if x is not ours),None)
                    if not ours or not theirs:continue
                    opponent=theirs.get("team",{}).get("displayName","")
                    city=HOME[team] if ours.get("homeAway")=="home" else ENG.get(opponent)
                    if city:games.append({"team":team,"date":date,"opponent":opponent,"city":city,"source":"ESPN eng.1"})
            except Exception as e:print("ERROR team schedule",team,season,e)
    # Remove duplicate fixtures returned by multiple ESPN endpoints.
    unique={(g["team"],g["date"],g["opponent"],g["city"]):g for g in games}
    return list(unique.values())
def hockey():
    games=[]
    for team,abbr in [("kings","LAK"),("sabres","BUF")]:
        for season in ("20252026","20262027"):
            try:
                payload=get(f"https://api-web.nhle.com/v1/club-schedule-season/{abbr}/{season}")
                for g in payload.get("games",[]):
                    date=g.get("gameDate","")
                    if not ("2026-01-01"<=date<="2027-12-31"):continue
                    h=g.get("homeTeam",{}).get("abbrev","")
                    a=g.get("awayTeam",{}).get("abbrev","")
                    h=text(h);a=text(a)
                    city=HOME[team] if h==abbr else NHL.get(h)
                    if not city:continue
                    opponent=g.get("awayTeam" if h==abbr else "homeTeam",{})
                    games.append({"team":team,"date":date,"opponent":text(opponent.get("placeName"))+" "+text(opponent.get("commonName")),"city":city,"source":"NHL"})
                print(team,season,"events",len(payload.get("games",[])))
            except Exception as e:print("ERROR NHL",team,season,e)
    return games
def main():
    existing=json.loads(OUT.read_text()) if OUT.exists() else {"matches":[]}
    fresh=soccer()+hockey()
    # Preserve manually sourced hockey fixtures; keep older verified entries if provider temporarily fails.
    merged={(g["team"],g["date"],g["opponent"],g["city"]):g for g in existing.get("matches",[]) if g.get("source") not in ("ESPN nor.1","ESPN eng.1","NHL")}
    for g in fresh:merged[(g["team"],g["date"],g["opponent"],g["city"])]=g
    if not fresh and not merged:raise SystemExit("No fixtures retrieved; refusing to publish empty update")\n    print("Counts by team:", {t:sum(g["team"]==t for g in merged.values()) for t in HOME})
    data={"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),"matches":sorted(merged.values(),key=lambda g:(g["date"],g["team"],g["opponent"]))}
    OUT.parent.mkdir(exist_ok=True,parents=True);OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print("Saved",len(data["matches"]),"matches")
if __name__=="__main__":main()
