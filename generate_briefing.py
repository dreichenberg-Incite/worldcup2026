#!/usr/bin/env python3
"""
FIFA World Cup 2026 — Daily Morning Briefing Generator (Hebrew Edition)
Runs at 7 AM ET, generates a full RTL Hebrew HTML briefing and opens it.
"""

import os, json, re, sys, webbrowser, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import concurrent.futures
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import anthropic, requests, pytz
except ImportError:
    print("Installing dependencies...")
    os.system(f"{sys.executable} -m pip install anthropic requests pytz")
    import anthropic, requests, pytz

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
FOOTBALL_API_KEY  = os.getenv("WC_FOOTBALL_API_KEY",  "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FOOTBALL_BASE    = "https://api.football-data.org/v4"
# On GitHub Actions (Linux) output as index.html for GitHub Pages
import platform as _platform
_on_actions = os.getenv("GITHUB_ACTIONS") == "true"
OUTPUT_PATH = Path(__file__).parent / ("index.html" if _on_actions else "briefing.html")
ET_TZ            = pytz.timezone("America/New_York")
IL_TZ            = pytz.timezone("Asia/Jerusalem")

# ─────────────────────────────────────────────────────────────────────────────
# TEAM DATA — flags, colors, Hebrew names
# ─────────────────────────────────────────────────────────────────────────────
def flag_img(iso2, size=24):
    """Return an <img> tag using flagcdn.com — works in all browsers."""
    if not iso2:
        return '<span style="opacity:.3;font-size:1rem;">⚑</span>'
    code = iso2.lower()
    return (f'<img src="https://flagcdn.com/w40/{code}.png" '
            f'width="{size}" height="{round(size*0.67)}" '
            f'style="border-radius:2px;object-fit:cover;vertical-align:middle;" '
            f'alt="{iso2}" loading="lazy">')

def T(he, color, color2, iso2):
    return {"iso2": iso2, "color": color, "color2": color2, "he": he}

TEAMS_META = {
    "Argentina":             T("ארגנטינה",    "#74acdf","#ffffff","ar"),
    "Brazil":                T("ברזיל",       "#009c3b","#ffdf00","br"),
    "France":                T("צרפת",        "#002395","#ed2939","fr"),
    "Germany":               T("גרמניה",      "#dd0000","#000000","de"),
    "Spain":                 T("ספרד",        "#aa151b","#f1bf00","es"),
    "England":               T("אנגליה",      "#003399","#ffffff","gb-eng"),
    "Portugal":              T("פורטוגל",     "#006600","#ff0000","pt"),
    "Netherlands":           T("הולנד",       "#ff6400","#003087","nl"),
    "Belgium":               T("בלגיה",       "#ef3340","#000000","be"),
    "Italy":                 T("איטליה",      "#009246","#ce2b37","it"),
    "Croatia":               T("קרואטיה",     "#ff0000","#0030a0","hr"),
    "Uruguay":               T("אורוגוואי",   "#5aadd6","#ffffff","uy"),
    "Colombia":              T("קולומביה",    "#fcd116","#003087","co"),
    "Morocco":               T("מרוקו",       "#c1272d","#006233","ma"),
    "Senegal":               T("סנגל",        "#00853f","#fdef42","sn"),
    "Japan":                 T("יפן",         "#bc002d","#ffffff","jp"),
    "South Korea":           T("קוריאה",      "#003478","#cd2e3a","kr"),
    "Korea Republic":        T("קוריאה",      "#003478","#cd2e3a","kr"),
    "USA":                   T('ארה"ב',       "#3c3b6e","#b22234","us"),
    "United States":         T('ארה"ב',       "#3c3b6e","#b22234","us"),
    "Mexico":                T("מקסיקו",      "#006847","#ce1126","mx"),
    "Canada":                T("קנדה",        "#ff0000","#ffffff","ca"),
    "Ecuador":               T("אקוודור",     "#ffd100","#003087","ec"),
    "Nigeria":               T("ניגריה",      "#008751","#ffffff","ng"),
    "Cameroon":              T("קמרון",       "#007a5e","#ce1126","cm"),
    "Ghana":                 T("גאנה",        "#006b3f","#fcd116","gh"),
    "Ivory Coast":           T("חוף השנהב",   "#f77f00","#009a44","ci"),
    "Egypt":                 T("מצרים",       "#ce1126","#000000","eg"),
    "Tunisia":               T("תוניסיה",     "#e70013","#ffffff","tn"),
    "Algeria":               T("אלגריה",      "#006233","#ffffff","dz"),
    "Saudi Arabia":          T("ערב הסעודית", "#006c35","#ffffff","sa"),
    "Iran":                  T("איראן",       "#239f40","#da0000","ir"),
    "IR Iran":               T("איראן",       "#239f40","#da0000","ir"),
    "Australia":             T("אוסטרליה",    "#00008b","#ffcc00","au"),
    "Serbia":                T("סרביה",       "#c6363c","#0c4076","rs"),
    "Denmark":               T("דנמרק",       "#c60c30","#ffffff","dk"),
    "Poland":                T("פולין",       "#dc143c","#ffffff","pl"),
    "Ukraine":               T("אוקראינה",    "#005bbb","#ffd500","ua"),
    "Turkey":                T("טורקיה",      "#e30a17","#ffffff","tr"),
    "Switzerland":           T("שוויץ",       "#ff0000","#ffffff","ch"),
    "Austria":               T("אוסטריה",     "#ed2939","#ffffff","at"),
    "Qatar":                 T("קטר",         "#8d1b3d","#ffffff","qa"),
    "Costa Rica":            T("קוסטה ריקה",  "#002b7f","#ce1126","cr"),
    "Panama":                T("פנמה",        "#da121a","#003da5","pa"),
    "Honduras":              T("הונדורס",     "#0073cf","#ffffff","hn"),
    "Venezuela":             T("ונצואלה",     "#cf142b","#00247d","ve"),
    "Iraq":                  T("עיראק",       "#ce1126","#007a3d","iq"),
    "Jordan":                T("ירדן",        "#007a3d","#000000","jo"),
    "Paraguay":              T("פרגוואי",     "#d52b1e","#0038a8","py"),
    "New Zealand":           T("ניו זילנד",   "#00247d","#cc142b","nz"),
    "Indonesia":             T("אינדונזיה",   "#ce1126","#ffffff","id"),
    "Wales":                 T("וויילס",      "#00a651","#c8102e","gb-wls"),
    "Scotland":              T("סקוטלנד",     "#003f87","#ffffff","gb-sct"),
    "Czechia":               T("צ'כיה",       "#d7141a","#11457e","cz"),
    "Czech Republic":        T("צ'כיה",       "#d7141a","#11457e","cz"),
    "Bosnia-Herzegovina":    T("בוסניה",      "#002395","#fcdd09","ba"),
    "Bosnia and Herzegovina":T("בוסניה",      "#002395","#fcdd09","ba"),
    "Haiti":                 T("האיטי",       "#00209f","#d21034","ht"),
    "South Africa":          T("דרום אפריקה", "#007a4d","#ffb81c","za"),
    "Guatemala":             T("גואטמלה",     "#4997d0","#ffffff","gt"),
    "Jamaica":               T("ג'מייקה",     "#000000","#fed100","jm"),
    "Trinidad and Tobago":   T("טרינידד",     "#ce1126","#000000","tt"),
    "Cuba":                  T("קובה",        "#002a8f","#cf142b","cu"),
    "Uzbekistan":            T("אוזבקיסטן",   "#1eb53a","#0099b5","uz"),
    "Thailand":              T("תאילנד",      "#a51931","#2d2a4a","th"),
    "Vietnam":               T("וייטנאם",     "#da251d","#ffcd00","vn"),
    "China":                 T("סין",         "#de2910","#ffde00","cn"),
    "Oman":                  T("עומאן",       "#db161b","#ffffff","om"),
    "Bahrain":               T("בחריין",      "#ce1126","#ffffff","bh"),
    "Norway":                T("נורווגיה",    "#ef2b2d","#002868","no"),
    "Sweden":                T("שוודיה",      "#006aa7","#fecc02","se"),
    "Finland":               T("פינלנד",      "#003580","#ffffff","fi"),
    "Greece":                T("יוון",        "#0d5eaf","#ffffff","gr"),
    "Romania":               T("רומניה",      "#002b7f","#fcd116","ro"),
    "Hungary":               T("הונגריה",     "#ce2939","#436f4d","hu"),
    "Slovakia":              T("סלובקיה",     "#0b4ea2","#ee1c25","sk"),
    "Albania":               T("אלבניה",      "#e41e20","#000000","al"),
    "Mali":                  T("מאלי",        "#14b53a","#ce1126","ml"),
    "Zambia":                T("זמביה",       "#198a00","#ef7d00","zm"),
    "TBD":                   T("לא ידוע",     "#333333","#666666",""),
    # ISO 2-letter fallbacks
    "AR":T("ארגנטינה",   "#74acdf","#ffffff","ar"),
    "BR":T("ברזיל",      "#009c3b","#ffdf00","br"),
    "FR":T("צרפת",       "#002395","#ed2939","fr"),
    "DE":T("גרמניה",     "#dd0000","#000000","de"),
    "ES":T("ספרד",       "#aa151b","#f1bf00","es"),
    "PT":T("פורטוגל",    "#006600","#ff0000","pt"),
    "NL":T("הולנד",      "#ff6400","#003087","nl"),
    "BE":T("בלגיה",      "#ef3340","#000000","be"),
    "IT":T("איטליה",     "#009246","#ce2b37","it"),
    "HR":T("קרואטיה",    "#ff0000","#0030a0","hr"),
    "UY":T("אורוגוואי",  "#5aadd6","#ffffff","uy"),
    "CO":T("קולומביה",   "#fcd116","#003087","co"),
    "MA":T("מרוקו",      "#c1272d","#006233","ma"),
    "SN":T("סנגל",       "#00853f","#fdef42","sn"),
    "JP":T("יפן",        "#bc002d","#ffffff","jp"),
    "KR":T("קוריאה",     "#003478","#cd2e3a","kr"),
    "US":T('ארה"ב',      "#3c3b6e","#b22234","us"),
    "MX":T("מקסיקו",     "#006847","#ce1126","mx"),
    "CA":T("קנדה",       "#ff0000","#ffffff","ca"),
    "EC":T("אקוודור",    "#ffd100","#003087","ec"),
    "NG":T("ניגריה",     "#008751","#ffffff","ng"),
    "CM":T("קמרון",      "#007a5e","#ce1126","cm"),
    "GH":T("גאנה",       "#006b3f","#fcd116","gh"),
    "CI":T("חוף השנהב",  "#f77f00","#009a44","ci"),
    "EG":T("מצרים",      "#ce1126","#000000","eg"),
    "TN":T("תוניסיה",    "#e70013","#ffffff","tn"),
    "DZ":T("אלגריה",     "#006233","#ffffff","dz"),
    "SA":T("ערב הסעודית","#006c35","#ffffff","sa"),
    "IR":T("איראן",      "#239f40","#da0000","ir"),
    "AU":T("אוסטרליה",   "#00008b","#ffcc00","au"),
    "RS":T("סרביה",      "#c6363c","#0c4076","rs"),
    "DK":T("דנמרק",      "#c60c30","#ffffff","dk"),
    "PL":T("פולין",      "#dc143c","#ffffff","pl"),
    "UA":T("אוקראינה",   "#005bbb","#ffd500","ua"),
    "TR":T("טורקיה",     "#e30a17","#ffffff","tr"),
    "CH":T("שוויץ",      "#ff0000","#ffffff","ch"),
    "AT":T("אוסטריה",    "#ed2939","#ffffff","at"),
    "QA":T("קטר",        "#8d1b3d","#ffffff","qa"),
    "CR":T("קוסטה ריקה", "#002b7f","#ce1126","cr"),
    "PA":T("פנמה",       "#da121a","#003da5","pa"),
    "HN":T("הונדורס",    "#0073cf","#ffffff","hn"),
    "VE":T("ונצואלה",    "#cf142b","#00247d","ve"),
    "IQ":T("עיראק",      "#ce1126","#007a3d","iq"),
    "JO":T("ירדן",       "#007a3d","#000000","jo"),
    "PY":T("פרגוואי",    "#d52b1e","#0038a8","py"),
    "NZ":T("ניו זילנד",  "#00247d","#cc142b","nz"),
    "ID":T("אינדונזיה",  "#ce1126","#ffffff","id"),
    "ZA":T("דרום אפריקה","#007a4d","#ffb81c","za"),
    "BA":T("בוסניה",     "#002395","#fcdd09","ba"),
    "CZ":T("צ'כיה",      "#d7141a","#11457e","cz"),
    "HT":T("האיטי",      "#00209f","#d21034","ht"),
    "NO":T("נורווגיה",   "#ef2b2d","#002868","no"),
    "UZ":T("אוזבקיסטן",  "#1eb53a","#0099b5","uz"),
    "GB-ENG":T("אנגליה", "#003399","#ffffff","gb-eng"),
    "GB-WLS":T("וויילס", "#00a651","#c8102e","gb-wls"),
    "GB-SCT":T("סקוטלנד","#003f87","#ffffff","gb-sct"),
    "IR":{"flag":"🇮🇷","color":"#239f40","color2":"#da0000","he":"איראן"},
    "AU":{"flag":"🇦🇺","color":"#00008b","color2":"#ffcc00","he":"אוסטרליה"},
    "RS":{"flag":"🇷🇸","color":"#c6363c","color2":"#0c4076","he":"סרביה"},
    "DK":{"flag":"🇩🇰","color":"#c60c30","color2":"#ffffff","he":"דנמרק"},
    "PL":{"flag":"🇵🇱","color":"#dc143c","color2":"#ffffff","he":"פולין"},
    "UA":{"flag":"🇺🇦","color":"#005bbb","color2":"#ffd500","he":"אוקראינה"},
    "TR":{"flag":"🇹🇷","color":"#e30a17","color2":"#ffffff","he":"טורקיה"},
    "CH":{"flag":"🇨🇭","color":"#ff0000","color2":"#ffffff","he":"שוויץ"},
    "AT":{"flag":"🇦🇹","color":"#ed2939","color2":"#ffffff","he":"אוסטריה"},
    "QA":{"flag":"🇶🇦","color":"#8d1b3d","color2":"#ffffff","he":"קטר"},
    "CR":{"flag":"🇨🇷","color":"#002b7f","color2":"#ce1126","he":"קוסטה ריקה"},
    "PA":{"flag":"🇵🇦","color":"#da121a","color2":"#003da5","he":"פנמה"},
    "HN":{"flag":"🇭🇳","color":"#0073cf","color2":"#ffffff","he":"הונדורס"},
    "VE":{"flag":"🇻🇪","color":"#cf142b","color2":"#00247d","he":"ונצואלה"},
    "IQ":{"flag":"🇮🇶","color":"#ce1126","color2":"#007a3d","he":"עיראק"},
    "JO":{"flag":"🇯🇴","color":"#007a3d","color2":"#000000","he":"ירדן"},
    "PY":{"flag":"🇵🇾","color":"#d52b1e","color2":"#0038a8","he":"פרגוואי"},
    "NZ":{"flag":"🇳🇿","color":"#00247d","color2":"#cc142b","he":"ניו זילנד"},
    "ID":{"flag":"🇮🇩","color":"#ce1126","color2":"#ffffff","he":"אינדונזיה"},
    "ZA":{"flag":"🇿🇦","color":"#007a4d","color2":"#ffb81c","he":"דרום אפריקה"},
    "BA":{"flag":"🇧🇦","color":"#002395","color2":"#fcdd09","he":"בוסניה"},
    "CZ":{"flag":"🇨🇿","color":"#d7141a","color2":"#11457e","he":"צ'כיה"},
    "HT":{"flag":"🇭🇹","color":"#00209f","color2":"#d21034","he":"האיטי"},
    "Norway":       {"flag":"🇳🇴","color":"#ef2b2d","color2":"#002868","he":"נורווגיה"},
    "NO":           {"flag":"🇳🇴","color":"#ef2b2d","color2":"#002868","he":"נורווגיה"},
    "Sweden":       {"flag":"🇸🇪","color":"#006aa7","color2":"#fecc02","he":"שוודיה"},
    "SE":           {"flag":"🇸🇪","color":"#006aa7","color2":"#fecc02","he":"שוודיה"},
    "Finland":      {"flag":"🇫🇮","color":"#003580","color2":"#ffffff","he":"פינלנד"},
    "FI":           {"flag":"🇫🇮","color":"#003580","color2":"#ffffff","he":"פינלנד"},
    "Greece":       {"flag":"🇬🇷","color":"#0d5eaf","color2":"#ffffff","he":"יוון"},
    "GR":           {"flag":"🇬🇷","color":"#0d5eaf","color2":"#ffffff","he":"יוון"},
    "Romania":      {"flag":"🇷🇴","color":"#002b7f","color2":"#fcd116","he":"רומניה"},
    "RO":           {"flag":"🇷🇴","color":"#002b7f","color2":"#fcd116","he":"רומניה"},
    "Hungary":      {"flag":"🇭🇺","color":"#ce2939","color2":"#436f4d","he":"הונגריה"},
    "HU":           {"flag":"🇭🇺","color":"#ce2939","color2":"#436f4d","he":"הונגריה"},
    "Slovakia":     {"flag":"🇸🇰","color":"#0b4ea2","color2":"#ee1c25","he":"סלובקיה"},
    "SK":           {"flag":"🇸🇰","color":"#0b4ea2","color2":"#ee1c25","he":"סלובקיה"},
    "Albania":      {"flag":"🇦🇱","color":"#e41e20","color2":"#000000","he":"אלבניה"},
    "AL":           {"flag":"🇦🇱","color":"#e41e20","color2":"#000000","he":"אלבניה"},
    "Mali":         {"flag":"🇲🇱","color":"#14b53a","color2":"#ce1126","he":"מאלי"},
    "ML":           {"flag":"🇲🇱","color":"#14b53a","color2":"#ce1126","he":"מאלי"},
    "Zambia":       {"flag":"🇿🇲","color":"#198a00","color2":"#ef7d00","he":"זמביה"},
    "ZM":           {"flag":"🇿🇲","color":"#198a00","color2":"#ef7d00","he":"זמביה"},
    "England":      {"flag":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","color":"#003399","color2":"#ffffff","he":"אנגליה"},
}

STAGE_HE = {
    "GROUP_STAGE":   "שלב הבתים",
    "ROUND_OF_32":   "שלב 32",
    "LAST_32":       "שלב 32",
    "ROUND_OF_16":   "שמינית גמר",
    "LAST_16":       "שמינית גמר",
    "QUARTER_FINALS":"רבע גמר",
    "SEMI_FINALS":   "חצי גמר",
    "FINAL":         "גמר",
    "3RD_PLACE":     "משחק גמר שלישי",
}

DAYS_HE   = ["שני","שלישי","רביעי","חמישי","שישי","שבת","ראשון"]
MONTHS_HE = ["","ינואר","פברואר","מרץ","אפריל","מאי","יוני",
              "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]

def he_date(dt):
    day_name = DAYS_HE[dt.weekday()]
    return f"{day_name}, {dt.day} ב{MONTHS_HE[dt.month]} {dt.year}"

def team_meta(name):
    clean = re.sub(r'\s+[A-Z]{2,3}$', '', name.strip())
    for search in [clean, name]:
        for k, v in TEAMS_META.items():
            if k.lower() == search.lower():
                return v
        for k, v in TEAMS_META.items():
            if k.lower() in search.lower() or search.lower() in k.lower():
                return v
    return {"iso2":"", "color":"#334455", "color2":"#667788", "he": clean}

def get_flag(name, size=24):
    return flag_img(team_meta(name).get("iso2",""), size)

# ─────────────────────────────────────────────────────────────────────────────
# FOOTBALL API
# ─────────────────────────────────────────────────────────────────────────────
def football_get(endpoint, params=None):
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    try:
        r = requests.get(f"{FOOTBALL_BASE}{endpoint}", params=params,
                         headers=headers, timeout=12)
        if r.status_code == 200:
            return r.json()
        print(f"  [API {r.status_code}] {endpoint}")
    except Exception as e:
        print(f"  [API error] {endpoint}: {e}")
    return {}

def get_todays_matches():
    today = date.today().isoformat()
    data = football_get("/competitions/WC/matches", {"dateFrom": today, "dateTo": today})
    return data.get("matches", [])

def get_standings():
    data = football_get("/competitions/WC/standings")
    return data.get("standings", [])

def get_all_results():
    data = football_get("/competitions/WC/matches", {"status": "FINISHED"})
    return data.get("matches", [])

def get_upcoming_matches(days_ahead=10):
    """Get next scheduled matches within N days."""
    from_date = date.today().isoformat()
    to_date   = (date.today() + timedelta(days=days_ahead)).isoformat()
    data = football_get("/competitions/WC/matches",
                        {"dateFrom": from_date, "dateTo": to_date, "status": "SCHEDULED"})
    return data.get("matches", [])

def get_general_wc_news():
    """Fetch general World Cup 2026 news (used on non-match days)."""
    results = []
    queries = [
        ("מונדיאל 2026 גביע העולם",     "he", "IL", "IL:iw"),
        ("FIFA World Cup 2026",           "en", "US", "US:en"),
        ("גביע העולם 2026 נבחרות",        "he", "IL", "IL:iw"),
        ("World Cup 2026 preview squad",  "en", "US", "US:en"),
    ]
    for q, hl, gl, ceid in queries:
        encoded = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"
        results.extend(fetch_rss(url, "Google News")[:4])
    seen, unique = set(), []
    for item in results:
        key = item["title"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:10]

# ─────────────────────────────────────────────────────────────────────────────
# NEWS — sport5, one.co.il, Google News Hebrew
# ─────────────────────────────────────────────────────────────────────────────
def fetch_rss(url, label=""):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
        tree = ET.fromstring(raw)
        items = tree.findall(".//item")
        news = []
        for item in items[:8]:
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            pub   = item.findtext("pubDate", "").strip()[:16]
            desc  = item.findtext("description", "").strip()
            # strip HTML tags from description
            desc = re.sub(r"<[^>]+>", "", desc)[:120]
            if title:
                news.append({"title": title, "link": link, "pub": pub,
                             "desc": desc, "source": label})
        return news
    except Exception as e:
        print(f"  [RSS {label}] {e}")
        return []

def get_all_news(home, away):
    """Fetch news from Google News in Hebrew and English."""
    results = []
    home_he = team_meta(home).get("he", home)
    away_he = team_meta(away).get("he", away)

    queries = [
        (f"{home_he} {away_he} מונדיאל 2026",       "he", "IL", "IL:iw"),
        (f"{home} {away} FIFA World Cup 2026",        "en", "US", "US:en"),
        (f"גביע העולם 2026 {home_he}",                "he", "IL", "IL:iw"),
    ]
    for q, hl, gl, ceid in queries:
        encoded = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"
        results.extend(fetch_rss(url, "Google News")[:4])

    # Deduplicate
    seen, unique = set(), []
    for item in results:
        key = item["title"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:8]

# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE AI — Hebrew briefing
# ─────────────────────────────────────────────────────────────────────────────
def build_context(home, away, standings, results):
    rows = {}
    for block in standings:
        for e in block.get("table", []):
            n = e.get("team", {}).get("name", "")
            if n in (home, away):
                rows[n] = (f"P{e['playedGames']} W{e['won']} D{e['draw']} L{e['lost']} "
                           f"GF{e['goalsFor']} GA{e['goalsAgainst']} Pts{e['points']}")

    prev = []
    for r in results:
        ht = r.get("homeTeam", {}).get("name", "")
        at = r.get("awayTeam", {}).get("name", "")
        if home in (ht, at) or away in (ht, at):
            sc = r.get("score", {}).get("fullTime", {})
            day = r.get("utcDate","")[:10]
            prev.append(f"{day}  {ht} {sc.get('home','?')}–{sc.get('away','?')} {at}")

    standings_txt = "\n".join(f"{k}: {v}" for k,v in rows.items()) or "טרם החלה אליפות הגביע"
    results_txt   = "\n".join(prev) or "אין תוצאות קודמות בטורניר זה"
    return standings_txt, results_txt

def generate_briefing(match, standings, results):
    home  = match.get("homeTeam", {}).get("name", "TBD")
    away  = match.get("awayTeam", {}).get("name", "TBD")
    home_he = team_meta(home).get("he", home)
    away_he = team_meta(away).get("he", away)
    stage = STAGE_HE.get(match.get("stage",""), match.get("stage",""))
    group = match.get("group", "")
    venue = match.get("venue", "לא ידוע")

    utc_dt = datetime.fromisoformat(match.get("utcDate","2026-06-11T00:00:00Z").replace("Z","+00:00"))
    kick   = utc_dt.astimezone(ET_TZ).strftime("%I:%M %p ET").lstrip("0")

    standings_txt, results_txt = build_context(home, away, standings, results)

    prompt = f"""אתה אנליסט כדורגל מומחה שכותב סיקור בוקר יומי לגביע העולם 2026 בעברית.

המשחק: {home_he} ({home}) נגד {away_he} ({away})
שלב: {stage}{f" | בית {group}" if group else ""}
שעת קיקאוף: {kick}
אצטדיון: {venue}

מצב הטבלה הנוכחי:
{standings_txt}

תוצאות קודמות בטורניר:
{results_txt}

כתוב ניתוח מקיף ומרתק בעברית עם הסעיפים הבאים (השתמש בכותרות ##):

## ⚡ הרקע למשחק
2-3 משפטים: מה על הכף, מצב הבית, המשמעות של המשחק.

## 🔵 {home_he} — פרופיל קבוצה
- **מאמן**: [שם ולאום]
- **מערך**: [סכמה צפויה]
- **שחקנים מרכזיים** (5 שחקנים, כל אחד בשורה נפרדת): שם — קבוצת מועדון — עמדה — למה הוא חשוב
- **סגנון משחק**: 2 משפטים
- **חוזקות / חולשות**: בולט אחד לכל אחד

## 🔴 {away_he} — פרופיל קבוצה
[אותה מבנה]

## 📋 הרכבים צפויים
הצג את ה-11 המרכזי הצפוי של כל קבוצה:
{home_he} (מערך):
שוער — [שם]
הגנה — [שמות]
קישור — [שמות]
התקפה — [שמות]

{away_he} (מערך):
[אותו פורמט]

## ⚔️ קרבות טקטיים מרכזיים
בדיוק 3 עימותים שיכריעו את המשחק. כל אחד: **שחקן א׳ נגד שחקן ב׳** — הסבר.

## 📜 היסטוריה בגביע העולם
פגישות מרכזיות בגביעי עולם קודמים, שיאים, רגעים אייקוניים.

## 🎯 תחזית
**תוצאה: X–Y ({home_he} / תיקו / {away_he})**
3-4 משפטים עם נימוק. ציין את הגורם המכריע ואת השחקן שהכי סביר שיקבע.

כתוב בצורה חדה, ספציפית, מלאת ידע — כמו ניתוח ספורט פרמיום. השתמש בשמות שחקנים אמיתיים."""

    import json as _json, subprocess

    body = _json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 2800,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    # On Linux (GitHub Actions) urllib works fine — no Windows restrictions
    if _platform.system() != "Windows":
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
        except urllib.error.HTTPError as e:
            return f"## ⚠️ שגיאת Claude API ({e.code})\n`{e.read().decode()[:200]}`"
        except Exception as e:
            return f"## ⚠️ ניתוח AI לא זמין\nשגיאה: {str(e)[:300]}"

    # On Windows — use curl via Git Bash (urllib is blocked by Windows sandbox)
    body_file = Path(__file__).parent / "_req_body.json"
    body_file.write_bytes(body)
    curl_cmd = (
        f'curl -s --max-time 90 '
        f'-X POST https://api.anthropic.com/v1/messages '
        f'-H "x-api-key: {ANTHROPIC_API_KEY}" '
        f'-H "anthropic-version: 2023-06-01" '
        f'-H "content-type: application/json" '
        f'-d @"{body_file.as_posix()}"'
    )
    try:
        result = subprocess.run(
            ["C:\\Program Files\\Git\\bin\\bash.exe", "-c", curl_cmd],
            capture_output=True, timeout=95
        )
        body_file.unlink(missing_ok=True)
        if result.returncode != 0:
            return f"## ⚠️ שגיאת curl\n`{result.stderr.decode(errors='replace')[:300]}`"
        data = _json.loads(result.stdout.decode("utf-8", errors="replace"))
        if "error" in data:
            return f"## ⚠️ שגיאת Claude API\n{data['error'].get('message','')}"
        return data["content"][0]["text"]
    except subprocess.TimeoutExpired:
        body_file.unlink(missing_ok=True)
        return "## ⚠️ ניתוח AI לא זמין\nהבקשה לקחה יותר מ-90 שניות."
    except Exception as e:
        body_file.unlink(missing_ok=True)
        return f"## ⚠️ ניתוח AI לא זמין\nשגיאה: {str(e)[:300]}"

# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN → HTML
# ─────────────────────────────────────────────────────────────────────────────
def md_to_html(text):
    lines = text.split("\n")
    html, in_ul = [], False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            html.append("</ul>")
            in_ul = False

    def bold(s):
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", s)
        return s

    for line in lines:
        if line.startswith("## "):
            close_ul()
            html.append(f'<h3 class="sec-title">{bold(line[3:])}</h3>')
        elif line.startswith("### "):
            close_ul()
            html.append(f'<h4>{bold(line[4:])}</h4>')
        elif line.startswith("- ") or line.startswith("• "):
            if not in_ul:
                html.append('<ul class="brief-list">')
                in_ul = True
            html.append(f"<li>{bold(line[2:])}</li>")
        elif line.strip() == "":
            close_ul()
        else:
            close_ul()
            html.append(f"<p>{bold(line)}</p>")

    close_ul()
    return "\n".join(html)

# ─────────────────────────────────────────────────────────────────────────────
# HTML COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────
def standings_table_html(standings):
    if not standings:
        return ""
    html = ""
    for block in standings:
        gname = block.get("group", "")
        table = block.get("table", [])
        if not table:
            continue
        html += f'<div class="s-group"><div class="s-group-name">בית {gname}</div>'
        html += '''<table class="s-table">
<thead><tr>
  <th class="col-rank">#</th>
  <th class="col-team">קבוצה</th>
  <th>מ׳</th><th>נ׳</th><th>ת׳</th><th>ה׳</th><th>גכ</th><th>גנ</th><th>הפ</th><th>נק</th>
</tr></thead><tbody>'''
        for i, e in enumerate(table):
            name    = e.get("team", {}).get("name", "")
            meta    = team_meta(name)
            cls     = "qualify" if i < 2 else ("third" if i == 2 else "")
            he_name = meta.get("he", name)   # always Hebrew
            flag    = flag_img(meta.get("iso2",""), size=20)
            gd      = e["goalDifference"]
            rank_cls = {0:"rank-gold", 1:"rank-silver", 2:"rank-bronze"}.get(i, "")
            html += (
                f'<tr class="{cls}">'
                f'<td class="col-rank"><span class="rank-num {rank_cls}">{i+1}</span></td>'
                f'<td class="col-team">'
                f'<span class="team-cell-inner">'
                f'<span class="t-flag">{flag}</span>'
                f'<span class="t-name">{he_name}</span>'
                f'</span>'
                f'</td>'
                f'<td>{e["playedGames"]}</td><td>{e["won"]}</td>'
                f'<td>{e["draw"]}</td><td>{e["lost"]}</td>'
                f'<td>{e["goalsFor"]}</td><td>{e["goalsAgainst"]}</td>'
                f'<td>{("+" if gd >= 0 else "")}{gd}</td>'
                f'<td><strong>{e["points"]}</strong></td>'
                f'</tr>'
            )
        html += "</tbody></table></div>"
    return html

def results_html(matches, home, away):
    relevant = [r for r in matches if
                home in (r.get("homeTeam",{}).get("name",""), r.get("awayTeam",{}).get("name","")) or
                away in (r.get("homeTeam",{}).get("name",""), r.get("awayTeam",{}).get("name",""))]
    if not relevant:
        return '<p class="muted-he">אין תוצאות עדיין בטורניר זה.</p>'
    html = '<div class="res-grid">'
    for r in relevant:
        ht    = r.get("homeTeam",{}).get("name","")
        at    = r.get("awayTeam",{}).get("name","")
        sc    = r.get("score",{}).get("fullTime",{})
        day   = r.get("utcDate","")[:10]
        stage = STAGE_HE.get(r.get("stage",""), r.get("stage",""))
        hm    = team_meta(ht); am = team_meta(at)
        html += f'''<div class="res-card">
  <div class="res-stage">{stage}</div>
  <div class="res-matchup">
    <span class="res-team">{flag_img(hm.get("iso2",""),20)} {hm.get("he",ht)}</span>
    <span class="res-score">{sc.get("home","?")} – {sc.get("away","?")}</span>
    <span class="res-team">{flag_img(am.get("iso2",""),20)} {am.get("he",at)}</span>
  </div>
  <div class="res-date">{day}</div>
</div>'''
    html += "</div>"
    return html

def news_html(items):
    if not items:
        return '<p class="muted-he">לא נמצאו חדשות.</p>'
    html = '<div class="news-grid">'
    for item in items:
        title  = item.get("title","").split(" - ")[0].strip()
        link   = item.get("link","#")
        source = item.get("source","")
        pub    = item.get("pub","")
        desc   = item.get("desc","")
        src_class = "src-sport5" if "sport5" in source.lower() else ("src-one" if "one" in source.lower() else "src-google")
        html += f'''<a class="news-card" href="{link}" target="_blank" rel="noopener">
  <div class="news-source {src_class}">{source}</div>
  <div class="news-title">{title}</div>
  {f'<div class="news-desc">{desc}</div>' if desc else ''}
  <div class="news-pub">{pub}</div>
</a>'''
    html += "</div>"
    return html

# ─────────────────────────────────────────────────────────────────────────────
# MATCH CARD
# ─────────────────────────────────────────────────────────────────────────────
def match_card_html(match, briefing, news_items, standings, all_results):
    home  = match.get("homeTeam",{}).get("name","TBD")
    away  = match.get("awayTeam",{}).get("name","TBD")
    hm    = team_meta(home)
    am    = team_meta(away)
    stage = STAGE_HE.get(match.get("stage",""), match.get("stage",""))
    group = match.get("group","")
    venue = match.get("venue","")
    status = match.get("status","")

    utc_dt = datetime.fromisoformat(match.get("utcDate","2026-06-11T00:00:00Z").replace("Z","+00:00"))
    et_dt  = utc_dt.astimezone(ET_TZ)
    kick_et = et_dt.strftime("%I:%M %p ET").lstrip("0")
    kick_date = et_dt.strftime("%B %d, %Y")

    sc = match.get("score",{}).get("fullTime",{})
    sh, sa = sc.get("home"), sc.get("away")
    if status == "FINISHED" and sh is not None:
        score_display = f'<div class="score-box finished">{sh}<span class="score-sep">–</span>{sa}</div>'
    elif status in ("IN_PLAY","PAUSED"):
        score_display = '<div class="score-box live">⏱ שידור חי</div>'
    else:
        score_display = f'<div class="score-box upcoming"><span>{kick_et}</span><span class="kick-date">{kick_date}</span></div>'

    stage_label = f'{stage}{f" · בית {group}" if group else ""}'

    # group standings for this match
    grp_standings = ""
    if group:
        for block in standings:
            if block.get("group","") == group:
                grp_standings = standings_table_html([block])
                break
    if not grp_standings:
        grp_standings = standings_table_html(standings) or '<p class="muted-he">הטבלה תעודכן עם תחילת הטורניר</p>'

    card_id = f"m-{home[:3]}-{away[:3]}".replace(" ","-")

    return f'''
<article class="match-card" id="{card_id}">

  <!-- HERO HEADER with team colors -->
  <div class="match-hero" style="--c1:{hm["color"]};--c2:{am["color"]}">
    <div class="hero-bg-left"  style="background:linear-gradient(120deg,{hm["color"]}55,transparent)"></div>
    <div class="hero-bg-right" style="background:linear-gradient(240deg,{am["color"]}55,transparent)"></div>

    <div class="stage-pill">{stage_label}</div>

    <div class="scoreline-row">

      <div class="team-hero home-team">
        <div class="team-flag-giant">{flag_img(hm.get("iso2",""), 72)}</div>
        <div class="team-info-block">
          <div class="team-name-he">{hm.get("he",home)}</div>
          <div class="team-name-en">{home}</div>
        </div>
      </div>

      {score_display}

      <div class="team-hero away-team">
        <div class="team-info-block away-info">
          <div class="team-name-he">{am.get("he",away)}</div>
          <div class="team-name-en">{away}</div>
        </div>
        <div class="team-flag-giant">{flag_img(am.get("iso2",""), 72)}</div>
      </div>

    </div>

    <div class="match-footer-meta">
      <span>📍 {venue}</span>
      <span class="meta-sep">·</span>
      <span>🕐 {kick_et}</span>
    </div>
  </div>

  <!-- TABS -->
  <div class="tab-bar">
    <button class="tab active" onclick="switchTab(this,'{card_id}-brief')">📋 ניתוח המשחק</button>
    <button class="tab" onclick="switchTab(this,'{card_id}-stand')">📊 טבלת הבית</button>
    <button class="tab" onclick="switchTab(this,'{card_id}-res')">🏆 תוצאות הטורניר</button>
    <button class="tab" onclick="switchTab(this,'{card_id}-news')">📰 חדשות</button>
  </div>

  <div id="{card_id}-brief" class="tab-panel active">
    <div class="briefing-body">{md_to_html(briefing)}</div>
  </div>
  <div id="{card_id}-stand" class="tab-panel">
    {grp_standings}
  </div>
  <div id="{card_id}-res" class="tab-panel">
    {results_html(all_results, home, away)}
  </div>
  <div id="{card_id}-news" class="tab-panel">
    {news_html(news_items)}
  </div>

</article>'''

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;700;800;900&display=swap');

:root {
  --bg: #060911;
  --surf: #0d1421;
  --surf2: #131e2f;
  --surf3: #1a2740;
  --border: #1e2e45;
  --gold: #f5c518;
  --gold2: #e8a800;
  --red: #e63946;
  --blue: #3a86ff;
  --green: #06d6a0;
  --text: #e2e8f4;
  --muted: #5a6a82;
  --radius: 16px;
  --font: 'Heebo', 'Arial Hebrew', Arial, sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { direction: rtl; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  min-height: 100vh;
  line-height: 1.65;
}
a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── TOP BAR ──────────────────────────────────────────── */
.top-bar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(6,9,17,.96);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 28px; height: 62px;
}
.logo {
  display: flex; align-items: center; gap: 10px;
  font-size: 1.15rem; font-weight: 900; letter-spacing: -0.3px;
}
.logo-ball { font-size: 1.5rem; }
.logo-title span { color: var(--gold); }
.top-meta {
  display: flex; align-items: center; gap: 14px;
  font-size: .8rem; color: var(--muted);
}
.live-dot {
  width: 7px; height: 7px; background: var(--red);
  border-radius: 50%; animation: blink 1.4s infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.25} }

/* ── PAGE ─────────────────────────────────────────────── */
.page-wrap { max-width: 1080px; margin: 0 auto; padding: 32px 20px 80px; }

/* ── DATE HERO ────────────────────────────────────────── */
.date-hero {
  position: relative; overflow: hidden;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 40px 40px 36px;
  margin-bottom: 28px;
  background: linear-gradient(135deg, #080d1c 0%, #140820 60%, #08101c 100%);
}
.date-hero::before {
  content: '';
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse at 10% 0%, rgba(245,197,24,.18) 0%, transparent 50%),
    radial-gradient(ellipse at 90% 100%, rgba(58,134,255,.12) 0%, transparent 50%);
}
.date-hero-inner { position: relative; }
.date-label { font-size: .75rem; font-weight: 800; text-transform: uppercase;
              letter-spacing: 1.5px; color: var(--gold); margin-bottom: 10px; }
.date-hero h1 { font-size: clamp(1.7rem,3.5vw,2.6rem); font-weight: 900; line-height: 1.1; }
.date-hero h1 .date-colored { color: var(--gold); }
.date-hero p { color: var(--muted); margin-top: 6px; font-size: 1rem; }
.match-pill {
  display: inline-flex; align-items: center; gap: 6px;
  margin-top: 14px;
  background: rgba(245,197,24,.1);
  border: 1px solid rgba(245,197,24,.3);
  color: var(--gold); padding: 7px 16px;
  border-radius: 30px; font-size: .85rem; font-weight: 700;
}

/* ── QUICK NAV ────────────────────────────────────────── */
.quick-nav { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 28px; }
.qn-pill {
  background: var(--surf); border: 1px solid var(--border);
  color: var(--muted); padding: 8px 18px; border-radius: 30px;
  font-size: .83rem; font-weight: 700; cursor: pointer;
  transition: all .2s; white-space: nowrap;
  display: flex; align-items: center; gap: 6px;
}
.qn-pill:hover { border-color: var(--gold); color: var(--text); background: var(--surf2); text-decoration: none; }
.qn-flag { font-size: 1rem; }

/* ── PREVIEW BANNER ───────────────────────────────────── */
.preview-banner {
  background: linear-gradient(135deg, rgba(245,197,24,.08), rgba(58,134,255,.08));
  border: 1px solid rgba(245,197,24,.35);
  border-radius: var(--radius); padding: 20px 28px;
  margin-bottom: 24px;
  display: flex; align-items: center;
  justify-content: space-between; flex-wrap: wrap; gap: 16px;
}
.preview-label { font-size: .8rem; font-weight: 800; color: var(--gold);
                 text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.preview-date  { font-size: 1.1rem; font-weight: 900; }
.countdown-boxes { display: flex; align-items: center; gap: 8px; }
.cd-box { text-align: center; }
.cd-num { display: block; font-size: 1.8rem; font-weight: 900; color: var(--gold);
          line-height: 1; min-width: 2ch; }
.cd-lbl { font-size: .62rem; color: var(--muted); text-transform: uppercase;
          letter-spacing: .8px; }
.cd-sep { font-size: 1.5rem; color: var(--border); line-height: 1;
          margin-bottom: 14px; }

/* ── REFRESH BAR ──────────────────────────────────────── */
.refresh-bar {
  background: rgba(58,134,255,.07);
  border: 1px solid rgba(58,134,255,.2);
  border-radius: 10px; padding: 11px 18px;
  margin-bottom: 24px; font-size: .82rem;
  color: var(--muted); display: flex; align-items: center; gap: 8px;
}

/* ── MATCH CARD ───────────────────────────────────────── */
.match-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 32px;
  overflow: hidden;
  background: var(--surf);
  box-shadow: 0 8px 40px rgba(0,0,0,.5);
}

/* ── MATCH HERO ───────────────────────────────────────── */
.match-hero {
  position: relative; overflow: hidden;
  padding: 32px 32px 24px;
  background: linear-gradient(160deg, #0a1220 0%, #0d1830 100%);
  border-bottom: 1px solid var(--border);
}
.hero-bg-left {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: 50%; pointer-events: none;
}
.hero-bg-right {
  position: absolute; top: 0; left: 0; bottom: 0;
  width: 50%; pointer-events: none;
}
.stage-pill {
  position: relative;
  display: inline-block;
  background: rgba(245,197,24,.12);
  border: 1px solid rgba(245,197,24,.3);
  color: var(--gold);
  font-size: .72rem; font-weight: 800;
  text-transform: uppercase; letter-spacing: 1px;
  padding: 4px 12px; border-radius: 20px;
  margin-bottom: 20px;
}

.scoreline-row {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}

.team-hero { display: flex; align-items: center; gap: 14px; }
.team-hero.away-team { flex-direction: row-reverse; justify-content: flex-start; }

.team-flag-giant img {
  width: 80px; height: 54px;
  object-fit: cover;
  border-radius: 4px;
  filter: drop-shadow(0 4px 16px rgba(0,0,0,.6));
  flex-shrink: 0;
}

.team-info-block {}
.team-info-block.away-info { text-align: right; }
.team-name-he { font-size: 1.5rem; font-weight: 900; line-height: 1.1; }
.team-name-en { font-size: .78rem; color: var(--muted); font-weight: 600; margin-top: 2px; }

/* SCORE BOXES */
.score-box {
  text-align: center; min-width: 110px;
  border-radius: 12px; padding: 14px 18px;
  flex-shrink: 0;
}
.score-box.upcoming {
  background: rgba(255,255,255,.04);
  border: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 2px;
}
.score-box.upcoming span:first-child { font-size: 1.1rem; font-weight: 800; color: var(--gold); }
.kick-date { font-size: .7rem; color: var(--muted); }
.score-box.live {
  background: rgba(230,57,70,.12);
  border: 1px solid rgba(230,57,70,.4);
  color: var(--red); font-size: 1rem; font-weight: 800;
  animation: blink .9s infinite;
}
.score-box.finished {
  background: rgba(255,255,255,.04);
  border: 1px solid var(--border);
  font-size: 2rem; font-weight: 900;
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.score-sep { color: var(--muted); font-weight: 300; }

.match-footer-meta {
  position: relative;
  font-size: .8rem; color: var(--muted);
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.meta-sep { color: var(--border); }

/* ── TABS ─────────────────────────────────────────────── */
.tab-bar {
  display: flex; flex-direction: row-reverse;
  border-bottom: 1px solid var(--border);
  background: var(--surf2);
  overflow-x: auto;
}
.tab {
  background: none; border: none;
  color: var(--muted); padding: 14px 22px;
  cursor: pointer; font-size: .85rem; font-weight: 700;
  white-space: nowrap; font-family: var(--font);
  border-bottom: 2px solid transparent;
  transition: all .18s;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--gold); border-bottom-color: var(--gold); }

.tab-panel { display: none; padding: 28px 32px; }
.tab-panel.active { display: block; }

/* ── BRIEFING CONTENT ─────────────────────────────────── */
.briefing-body h3.sec-title {
  font-size: 1rem; font-weight: 800; color: var(--gold);
  margin: 26px 0 10px;
  padding-bottom: 7px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 6px;
}
.briefing-body h3.sec-title:first-child { margin-top: 0; }
.briefing-body h4 { font-size: .9rem; font-weight: 700; color: #8ab4e8; margin: 14px 0 6px; }
.briefing-body p { font-size: .93rem; margin-bottom: 10px; color: var(--text); }
.briefing-body ul.brief-list {
  padding-right: 20px; padding-left: 0; margin-bottom: 10px;
  list-style: none;
}
.briefing-body ul.brief-list li {
  font-size: .9rem; margin-bottom: 6px; color: var(--text);
  padding-right: 14px; position: relative;
}
.briefing-body ul.brief-list li::before {
  content: '◆'; position: absolute; right: 0;
  color: var(--gold); font-size: .55rem; top: 6px;
}
.briefing-body strong { color: #cde4ff; }
.briefing-body em { color: var(--muted); font-style: normal; }

/* ── STANDINGS ────────────────────────────────────────── */
.s-group { margin-bottom: 24px; }
.s-group-name {
  font-size: .72rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: 1px; color: var(--gold); margin-bottom: 10px;
}
.s-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.s-table th {
  color: var(--muted); font-weight: 700; font-size: .65rem;
  text-transform: uppercase; padding: 7px 5px;
  border-bottom: 1px solid var(--border); text-align: center;
  white-space: nowrap;
}
.s-table th.col-rank { width: 30px; }
.s-table th.col-team { text-align: right; min-width: 110px; }
.s-table td {
  padding: 8px 5px; border-bottom: 1px solid rgba(30,46,69,.5);
  text-align: center; vertical-align: middle;
}
.s-table td.col-rank { width: 30px; text-align: center; }
.s-table td.col-team {
  text-align: right;
  white-space: nowrap;
}
.s-table tr:hover td { background: var(--surf3); }

/* rank badge */
.rank-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%;
  font-size: .75rem; font-weight: 800;
  background: var(--surf2); color: var(--muted);
}
.rank-num.rank-gold   { background: rgba(245,197,24,.2);  color: var(--gold); }
.rank-num.rank-silver { background: rgba(180,180,180,.15); color: #c0c0c0; }
.rank-num.rank-bronze { background: rgba(160,100,50,.2);  color: #cd7f32; }

/* team name cell — flag + name inline, RTL friendly */
.team-cell-inner {
  display: inline-flex; align-items: center; gap: 6px;
  direction: rtl;
}
.t-flag img { border-radius: 2px; vertical-align: middle; flex-shrink: 0; }
.t-name { font-weight: 600; }

/* qualify indicators */
.s-table tr.qualify td.col-team { border-right: 3px solid var(--green); padding-right: 8px; }
.s-table tr.third   td.col-team { border-right: 3px solid var(--blue);  padding-right: 8px; }
.s-legend {
  display: flex; gap: 20px; margin-top: 12px; flex-wrap: wrap;
}
.s-legend-item {
  display: flex; align-items: center; gap: 6px;
  font-size: .73rem; color: var(--muted);
}
.s-legend-dot { width: 10px; height: 10px; border-radius: 2px; }

/* ── RESULTS ──────────────────────────────────────────── */
.res-grid { display: flex; flex-wrap: wrap; gap: 14px; }
.res-card {
  flex: 1; min-width: 175px;
  background: var(--surf2); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px 18px; text-align: center;
}
.res-stage { font-size: .66rem; color: var(--gold); font-weight: 800;
             text-transform: uppercase; letter-spacing: .8px; margin-bottom: 8px; }
.res-matchup { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.res-team { font-size: .82rem; font-weight: 700; }
.res-score { font-size: 1.45rem; font-weight: 900; padding: 0 6px; }
.res-date { font-size: .7rem; color: var(--muted); margin-top: 6px; }

/* ── NEWS ─────────────────────────────────────────────── */
.news-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 640px) { .news-grid { grid-template-columns: 1fr; } }
.news-card {
  background: var(--surf2); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px 18px;
  text-decoration: none; display: block;
  transition: border-color .18s, transform .15s;
}
.news-card:hover { border-color: var(--gold); transform: translateY(-2px); text-decoration: none; }
.news-source {
  font-size: .68rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: .8px; margin-bottom: 6px; padding: 2px 8px;
  border-radius: 4px; display: inline-block;
}
.src-sport5  { background: rgba(255,60,0,.15); color: #ff6a3c; }
.src-one     { background: rgba(0,120,255,.15); color: #4a9eff; }
.src-google  { background: rgba(100,100,100,.15); color: var(--muted); }
.news-title { font-size: .9rem; font-weight: 700; color: var(--text); margin-bottom: 4px; line-height: 1.4; }
.news-desc  { font-size: .78rem; color: var(--muted); margin-bottom: 4px; }
.news-pub   { font-size: .7rem; color: var(--muted); }

/* ── NO MATCHES ───────────────────────────────────────── */
.no-matches { text-align: center; padding: 70px 20px; }
.no-matches-emoji { font-size: 3.5rem; margin-bottom: 16px; }
.no-matches h2 { font-size: 1.4rem; font-weight: 800; margin-bottom: 8px; }
.no-matches p { color: var(--muted); }

/* ── MISC ─────────────────────────────────────────────── */
.muted-he { color: var(--muted); font-size: .9rem; }
code { background: var(--surf2); padding: 2px 6px; border-radius: 4px; font-size: .82rem; }

/* ── RESPONSIVE ───────────────────────────────────────── */
@media (max-width: 640px) {
  .scoreline-row { grid-template-columns: 1fr; gap: 10px; }
  .team-hero, .team-hero.away-team { justify-content: center; }
  .team-flag-giant img { width: 56px; height: 38px; }
  .team-name-he { font-size: 1.2rem; }
  .team-info-block.away-info { text-align: center; }
  .tab-panel { padding: 20px 16px; }
  .match-hero { padding: 24px 16px 18px; }
}

/* ── SCROLLBAR ────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
"""

JS = """
function switchTab(btn, panelId) {
  const card = btn.closest('.match-card') || document.body;
  card.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  card.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  const panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# FULL PAGE
# ─────────────────────────────────────────────────────────────────────────────
def full_page(today_he, today_en, match_cards, standings, all_results,
              matches=None, mode="today", days_until=0, general_news=None):
    now_et = datetime.now(ET_TZ).strftime("%I:%M %p ET").lstrip("0")
    n = match_cards.count('<article class="match-card"')

    # Header text changes by mode
    if mode == "preview":
        if days_until == 1:
            count_str = "⏰ מחר: " + (f"{n} משחקים" if n != 1 else "משחק אחד")
        else:
            count_str = f"⏰ בעוד {days_until} ימים: {n} משחקים"
        hero_subtitle = "תצוגה מקדימה למשחקים הבאים"
    elif mode == "restday":
        count_str = "💤 יום מנוחה — אין משחקים"
        hero_subtitle = "הניתוח המקיף שלך לגביע העולם 2026"
    else:
        count_str = f"⚽ {n} משחקים היום" if n != 1 else "⚽ משחק אחד היום"
        hero_subtitle = "הניתוח המקיף שלך לגביע העולם 2026"

    # Quick nav pills
    quick_nav = ""
    if matches:
        quick_nav = '<nav class="quick-nav">'
        for match in matches:
            home = match.get("homeTeam",{}).get("name","TBD")
            away = match.get("awayTeam",{}).get("name","TBD")
            hm   = team_meta(home); am = team_meta(away)
            card_id = f"m-{home[:3]}-{away[:3]}".replace(" ","-")
            label = f'{hm.get("he",home)} נגד {am.get("he",away)}'
            quick_nav += f'<a class="qn-pill" href="#{card_id}">{label}</a>'
        quick_nav += "</nav>"

    # Pre-tournament / preview banner
    preview_banner = ""
    if mode == "preview" and days_until > 0:
        if matches:
            match_date_et = datetime.fromisoformat(
                matches[0]["utcDate"].replace("Z","+00:00")
            ).astimezone(ET_TZ)
            match_date_str = match_date_et.strftime("%A, %B %d")
        else:
            match_date_str = ""
        preview_banner = f"""
<div class="preview-banner">
  <div class="preview-left">
    <div class="preview-label">{"🏆 גביע העולם מתחיל בקרוב" if days_until > 1 else "🔥 מחר מתחיל הטורניר"}</div>
    <div class="preview-date">{match_date_str}</div>
  </div>
  <div class="countdown-boxes">
    <div class="cd-box"><span class="cd-num" id="cd-d">--</span><span class="cd-lbl">ימים</span></div>
    <div class="cd-sep">:</div>
    <div class="cd-box"><span class="cd-num" id="cd-h">--</span><span class="cd-lbl">שעות</span></div>
    <div class="cd-sep">:</div>
    <div class="cd-box"><span class="cd-num" id="cd-m">--</span><span class="cd-lbl">דקות</span></div>
    <div class="cd-sep">:</div>
    <div class="cd-box"><span class="cd-num" id="cd-s">--</span><span class="cd-lbl">שניות</span></div>
  </div>
</div>"""

    # General news section (shown below matches on preview/restday)
    general_news_html = ""
    if general_news:
        general_news_html = f"""
<section class="match-card" style="padding:0;margin-bottom:28px;">
  <div style="padding:20px 28px 16px;background:var(--surf2);border-bottom:1px solid var(--border);
              font-size:1rem;font-weight:800;">
    📰 חדשות <span style="color:var(--gold)">גביע העולם 2026</span>
  </div>
  <div style="padding:20px 28px;">
    {news_html(general_news)}
  </div>
</section>"""

    # Full standings section
    all_stand_html = ""
    if standings:
        all_stand_html = f"""
<section class="match-card" style="padding:28px 32px;margin-bottom:28px;">
  <div style="font-size:1.05rem;font-weight:800;margin-bottom:20px;">
    📊 טבלאות <span style="color:var(--gold)">כל הבתים</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px;">
    {standings_table_html(standings)}
  </div>
  <div class="s-legend" style="margin-top:16px;">
    <div class="s-legend-item"><div class="s-legend-dot" style="background:var(--green)"></div>עולים לשלב הנוקאאוט</div>
    <div class="s-legend-item"><div class="s-legend-dot" style="background:var(--blue)"></div>עלייה אפשרית (מקום 3)</div>
  </div>
</section>"""

    if not match_cards.strip():
        match_cards = ""   # will show general news instead

    # countdown JS target: first match UTC time
    cd_target = ""
    if matches and (mode == "preview" or mode == "today"):
        cd_target = matches[0]["utcDate"].replace("Z", "+00:00")

    countdown_js = ""
    if cd_target:
        countdown_js = f"""
(function(){{
  var target = new Date("{cd_target}").getTime();
  function tick(){{
    var now = Date.now(), diff = target - now;
    if(diff <= 0){{ return; }}
    var d=Math.floor(diff/86400000),
        h=Math.floor((diff%86400000)/3600000),
        m=Math.floor((diff%3600000)/60000),
        s=Math.floor((diff%60000)/1000);
    var pad=function(n){{return String(n).padStart(2,'0');}};
    var de=document.getElementById('cd-d'),
        he=document.getElementById('cd-h'),
        me=document.getElementById('cd-m'),
        se=document.getElementById('cd-s');
    if(de) de.textContent=d;
    if(he) he.textContent=pad(h);
    if(me) me.textContent=pad(m);
    if(se) se.textContent=pad(s);
  }}
  tick(); setInterval(tick,1000);
}})();"""

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>גביע העולם 2026 · סיכום בוקר · {today_en}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<style>{CSS}</style>
</head>
<body>

<div class="top-bar">
  <div class="logo">
    <span class="logo-ball">⚽</span>
    <div class="logo-title">FIFA <span>2026</span> &nbsp;·&nbsp; סיכום בוקר</div>
  </div>
  <div class="top-meta">
    <div class="live-dot"></div>
    <span>עודכן {now_et}</span>
  </div>
</div>

<div class="page-wrap">

  <div class="date-hero">
    <div class="date-hero-inner">
      <div class="date-label">🌅 סיכום בוקר יומי</div>
      <h1>בוקר טוב ☀️ — <span class="date-colored">{today_he}</span></h1>
      <p>{hero_subtitle}</p>
      <div class="match-pill">{count_str}</div>
    </div>
  </div>

  {preview_banner}

  <div class="refresh-bar">
    🔄 הסיכום נוצר אוטומטית בכל בוקר בשעה 07:00. הרץ <code>generate_briefing.py</code> לרענון ידני.
  </div>

  {quick_nav}
  {match_cards}
  {general_news_html}
  {all_stand_html}

</div>

<script>{JS}</script>
<script>{countdown_js}</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# DEMO DATA — full opening-week schedule (used when no API key)
# ─────────────────────────────────────────────────────────────────────────────
def make_match(home, away, group, venue, date_str, stage="GROUP_STAGE"):
    return {"homeTeam":{"name":home},"awayTeam":{"name":away},
            "stage":stage,"group":group,"venue":venue,
            "utcDate":date_str,"status":"SCHEDULED",
            "score":{"fullTime":{"home":None,"away":None}}}

ALL_DEMO_MATCHES = [
    # June 11
    make_match("Mexico","TBD (Group A)","A","Estadio Azteca, Mexico City","2026-06-11T18:00:00Z"),
    make_match("USA","Brazil","A","MetLife Stadium, East Rutherford, NJ","2026-06-12T00:00:00Z"),
    # June 12
    make_match("Argentina","France","B","Rose Bowl, Pasadena, CA","2026-06-12T21:00:00Z"),
    make_match("Germany","Serbia","B","AT&T Stadium, Arlington, TX","2026-06-13T00:00:00Z"),
    # June 13
    make_match("Spain","Morocco","C","SoFi Stadium, Inglewood, CA","2026-06-13T21:00:00Z"),
    make_match("England","Iran","C","Levi's Stadium, San Jose, CA","2026-06-14T00:00:00Z"),
    # June 14
    make_match("Portugal","Netherlands","D","MetLife Stadium, East Rutherford, NJ","2026-06-14T21:00:00Z"),
    make_match("South Korea","Senegal","D","Arrowhead Stadium, Kansas City, MO","2026-06-15T00:00:00Z"),
    # June 15
    make_match("Belgium","Mexico","E","Estadio Azteca, Mexico City","2026-06-15T21:00:00Z"),
    make_match("Japan","Colombia","G","BC Place, Vancouver","2026-06-16T00:00:00Z"),
]

TOURNAMENT_START = date(2026, 6, 11)
TOURNAMENT_END   = date(2026, 7, 19)

def is_demo():
    return ("YOUR_FOOTBALL_DATA_KEY_HERE" in FOOTBALL_API_KEY or
            "YOUR_ANTHROPIC_API_KEY_HERE" in ANTHROPIC_API_KEY)

def demo_matches_for_today():
    """Return demo matches relevant to today: today's if available, else next upcoming."""
    today = date.today()
    today_str = today.isoformat()
    todays = [m for m in ALL_DEMO_MATCHES
              if m["utcDate"][:10] == today_str]
    if todays:
        return todays, "today"
    # find next match day
    upcoming = sorted(ALL_DEMO_MATCHES, key=lambda m: m["utcDate"])
    future = [m for m in upcoming if m["utcDate"][:10] > today_str]
    if not future:
        return [], "none"
    next_day = future[0]["utcDate"][:10]
    return [m for m in future if m["utcDate"][:10] == next_day], "preview"

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    now_et    = datetime.now(ET_TZ)
    today_he  = he_date(now_et)
    today_en  = now_et.strftime("%Y-%m-%d")
    today     = now_et.date()

    print(f"\n{'='*58}")
    print(f"  גביע העולם FIFA 2026 — סיכום בוקר")
    print(f"  {today_he}")
    print(f"{'='*58}\n")

    demo = is_demo()
    if demo:
        print("  [DEMO] מפתחות API לא מוגדרים — מציג דוגמה.")
        print("  הוסף מפתחות ב-generate_briefing.py או כמשתני סביבה.\n")

    print("  מושך נתוני משחקים...")
    standings = []
    results   = []
    mode      = "today"   # "today" | "preview" | "restday"

    if demo:
        matches, mode = demo_matches_for_today()
    else:
        standings = get_standings()
        results   = get_all_results()
        matches   = get_todays_matches()
        if not matches:
            # Look ahead up to 10 days for next match day
            upcoming = get_upcoming_matches(10)
            if upcoming:
                next_day = upcoming[0]["utcDate"][:10]
                matches  = [m for m in upcoming if m["utcDate"][:10] == next_day]
                mode     = "preview"
                print(f"  אין משחקים היום — מציג תצוגה מקדימה ל-{next_day}")
            else:
                mode = "restday"
                print("  אין משחקים קרובים.")

    print(f"  מצב: {mode} | {len(matches)} משחקים")

    # Days until tournament / match day
    if mode == "preview" and matches:
        preview_date = datetime.fromisoformat(
            matches[0]["utcDate"].replace("Z","+00:00")
        ).astimezone(ET_TZ).date()
        days_until = (preview_date - today).days
    elif today < TOURNAMENT_START:
        days_until = (TOURNAMENT_START - today).days
    else:
        days_until = 0

    # General WC news (always shown, especially useful pre-tournament)
    print("\n  מושך חדשות כלליות על גביע העולם...")
    general_news = get_general_wc_news()
    print(f"  נמצאו {len(general_news)} כתבות כלליות")

    cards = []
    for i, match in enumerate(matches):
        home = match.get("homeTeam",{}).get("name","TBD")
        away = match.get("awayTeam",{}).get("name","TBD")
        hm   = team_meta(home); am = team_meta(away)
        print(f"\n  [{i+1}/{len(matches)}] {hm.get('he',home)}  נגד  {am.get('he',away)}")

        print("     מושך חדשות...")
        news = get_all_news(home, away)
        print(f"     נמצאו {len(news)} כתבות")

        print("     מייצר ניתוח עם Claude AI... (עד 60 שניות)")
        if demo and "YOUR_ANTHROPIC_API_KEY_HERE" in ANTHROPIC_API_KEY:
            briefing = f"""## ⚡ הרקע למשחק
זהו ניתוח לדוגמה. הוסף את מפתח ה-Anthropic API שלך לניתוח AI אמיתי ומפורט.

## 🔵 {hm.get('he',home)} — פרופיל קבוצה
- **מאמן**: דוגמה — הוסף מפתח API
- **שחקנים מרכזיים**: נתוני דוגמה

## 🔴 {am.get('he',away)} — פרופיל קבוצה
- **מאמן**: דוגמה — הוסף מפתח API

## 🎯 תחזית
**תוצאה: 2–1 ({hm.get('he',home)})**
הוסף את מפתח ה-API לקבל תחזית AI אמיתית."""
        else:
            briefing = generate_briefing(match, standings, results)

        cards.append(match_card_html(match, briefing, news, standings, results))
        print("     סיום ✓")

    print("\n  בונה דף HTML...")
    html = full_page(today_he, today_en, "\n".join(cards), standings, results,
                     matches, mode, days_until, general_news)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"  נשמר: {OUTPUT_PATH}")
    webbrowser.open(OUTPUT_PATH.as_uri())
    print("  נפתח בדפדפן ✓\n")

if __name__ == "__main__":
    main()
