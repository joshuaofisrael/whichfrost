#!/usr/bin/env python3
"""Vegetable timing transcribed from state cooperative extension pages.

Only states listed here get a planting calendar. A city in any other state
gets a short note and no dates. Offsets are the extension's own words, counted
from that city's NOAA 50% last spring freeze. Nothing here is a national
"zone calendar."
"""
from datetime import date, timedelta

# Colorado State University Extension, GardenNotes #720, reviewed September 2024.
# https://extension.colostate.edu/resource/vegetable-planting-guide/
CO_SOURCE = {
    "state": "CO",
    "title": "Vegetable Planting Guide, CSU Extension GardenNotes #720",
    "url": "https://extension.colostate.edu/resource/vegetable-planting-guide/",
    "reviewed": "September 2024",
    "groups": [
        {
            "name": "Hardy",
            "crops": "broccoli, cabbage, kohlrabi, onions, lettuce, peas, radish, spinach, turnips",
            "start": -28, "end": -14,
            "says": "As early as 2 to 4 weeks before the average last spring frost. Counted here as the span from 28 days before to 14 days before this city's NOAA 50 percent date.",
        },
        {
            "name": "Semi hardy",
            "crops": "beets, carrots, cauliflower, parsley, parsnips, potatoes, Swiss chard",
            "start": -14, "end": 0,
            "says": "As early as 0 to 2 weeks before the average last spring frost. Counted here as the span from 14 days before the NOAA 50 percent date through that date.",
        },
        {
            "name": "Tender, from seed",
            "crops": "beans, celery, corn, cucumbers, New Zealand spinach, summer squash",
            "start": 0, "end": 0,
            "says": "From seed, around the average last spring frost. CSU also says cucumber and summer squash transplants without frost protection should wait until the frost potential is over. No day count is given for that wait, so none is calculated here.",
        },
        {
            "name": "Very tender",
            "crops": "lima beans, cantaloupe, eggplant, pepper, pumpkin, winter squash, tomato, watermelon",
            "start": 14, "end": None,
            "says": "Typically 2 or more weeks after the average last spring frost. The date shown is 14 days after this city's NOAA 50 percent date, the start of that window, not a last planting date.",
        },
    ],
    "extra": "CSU says soil temperature is one of the best ways to time spring planting, measured at 8 a.m. and 4 inches deep (6 inches for beans). This page does not have soil temperature normals, so it does not turn those thresholds into dates. CSU also says cole crops in warmer parts of Colorado are often direct seeded in mid summer, and names early July for the Front Range. That July note is quoted from CSU and is not applied as a calculated date for every Colorado city.",
}

# University of New Hampshire Extension fact sheet, retrieved 16 Nov 2026.
# https://extension.unh.edu/resource/growing-vegetables-when-plant-your-vegetable-garden-fact-sheet
NH_SOURCE = {
    "state": "NH",
    "title": "Growing Vegetables: When to Plant Your Vegetable Garden, UNH Extension",
    "url": "https://extension.unh.edu/resource/growing-vegetables-when-plant-your-vegetable-garden-fact-sheet",
    "reviewed": "retrieved 16 Nov 2026",
    "groups": [
        {"name": "Pea", "crops": "pea", "start": None, "end": None,
         "says": "Plant seed in the garden as soon as the soil thaws. UNH does not give a day offset, so no date is calculated."},
        {"name": "Broccoli and Brussels sprouts", "crops": "broccoli, Brussels sprouts", "start": -28, "end": -14,
         "says": "Set out 2 to 4 weeks before the last frost. Start seed 4 to 6 weeks before transplanting."},
        {"name": "Cabbage, kale, kohlrabi, leek, onion", "crops": "cabbage, kale, kohlrabi, leek, onion", "start": -28, "end": -28,
         "says": "Safe to set out 4 weeks before the last frost."},
        {"name": "Lettuce", "crops": "lettuce", "start": -28, "end": -21,
         "says": "Safe to set out 3 to 4 weeks before the last frost. Start seed 4 to 5 weeks before transplanting."},
        {"name": "Spinach", "crops": "spinach", "start": -42, "end": -21,
         "says": "Safe to set out 3 to 6 weeks before the last frost."},
        {"name": "Cauliflower", "crops": "cauliflower", "start": -14, "end": -14,
         "says": "Safe to set out 2 weeks before the last frost."},
        {"name": "Potato", "crops": "potato", "start": -14, "end": -7,
         "says": "Plant seed potatoes 1 to 2 weeks before the last frost."},
        {"name": "Radish and turnip", "crops": "radish, turnip", "start": -28, "end": -14,
         "says": "Plant seed 2 to 4 weeks before the last frost."},
        {"name": "Swiss chard seed", "crops": "Swiss chard", "start": -28, "end": -28,
         "says": "Plant seed 4 weeks before the last frost. Transplants are safe 2 weeks before the last frost."},
        {"name": "Bean", "crops": "bean", "start": 0, "end": None,
         "says": "Plant seed in the garden after the last frost. The date shown is the NOAA 50 percent date, the first day of that window."},
        {"name": "Tomato", "crops": "tomato", "start": 7, "end": 14,
         "says": "Safe to set out 1 to 2 weeks after the last frost. Start seed 6 to 8 weeks before transplanting."},
        {"name": "Pepper", "crops": "pepper", "start": 14, "end": 14,
         "says": "Safe to set out 2 weeks after the last frost. Start seed 8 to 10 weeks before transplanting."},
        {"name": "Cucumber transplant", "crops": "cucumber", "start": 7, "end": 14,
         "says": "Transplants are safe 1 to 2 weeks after the last frost. UNH also says to direct seed when the soil warms to 70°F. That soil temperature is not calculated here."},
        {"name": "Summer squash and zucchini", "crops": "summer squash, zucchini", "start": 14, "end": 14,
         "says": "Safe to set out 2 weeks after the last frost."},
    ],
    "extra": "UNH says to determine the last frost date for your area before using this chart, and gives Memorial Day as a conservative estimate for central New Hampshire. The dates on a Which Frost city page are counted from that city's NOAA 50 percent last spring freeze, not from Memorial Day. Crops UNH times by soil temperature alone (beet, carrot, corn, and others) are left off this table so a frost date is not turned into a soil date.",
}

GA_SOURCE = {
    "state": "GA",
    "title": "Vegetable Garden Calendar, University of Georgia Extension Circular 943",
    "url": "https://extension.uga.edu/publications/detail.html?number=C943",
    "reviewed": "full review 10 March 2026",
}

# University of Georgia Extension Circular 943, full review 10 March 2026.
# Middle Georgia baseline. North and south adjustments are quoted, not applied as new dates.
# https://extension.uga.edu/publications/detail.html?number=C943
GA_MONTHS = {
    1: "Plan the garden, order seed, and take a soil sample. Get plant beds ready so tomatoes, peppers, and eggplant can be seeded in early February.",
    2: "Start seed boxes. UGA says peppers and eggplant take 8 weeks from seed to transplant size, and tomatoes take 6 weeks. Early plantings: carrots, collards, lettuce, mustard, English peas, Irish potatoes, radishes, spinach, and turnips.",
    3: "Second plantings of turnips, mustard, radishes, and spring onions. Have rows ready for warm season crops in the last week of March or the first week or two of April, as the weather allows.",
    4: "Plant frost tender crops: snap, pole, and lima beans, cantaloupe, sweet corn, cucumbers, eggplant, okra, field peas, peppers, squash, tomatoes, and watermelon.",
    5: "A third planting of snap beans, corn, squash, and lima beans. Keep mulch and water in place for the crops already growing.",
    6: "Plant sweet potatoes and a second planting of Southern peas. Harvest beans, peas, squash, cucumbers, and okra often.",
    7: "UGA says to plant tomatoes, okra, corn, pole beans, lima beans, cucumbers, squash, and snap beans no later than July 20 if they are to mature before frost.",
    8: "Snap beans and Irish potatoes no later than August 15. Cucumbers and squash no later than August 31. Start broccoli, cabbage, cauliflower, collards, kale, and onions for setting out in September.",
    9: "Plant or transplant beets, broccoli, cabbage, carrots, collards, lettuce, mustard, onions, radishes, spinach, and turnips. UGA groups September and October together for this list.",
    10: "Same cool season list as September: beets, broccoli, cabbage, carrots, collards, lettuce, mustard, onions, radishes, spinach, and turnips.",
    11: "UGA's November and December notes are about manure, leaves, soil samples, and seed orders. They do not name a planting list.",
    12: "Order next year's seed. UGA does not name a planting list for December.",
}

# University of Alaska Fairbanks Cooperative Extension, HGA-00134,
# "16 Easy Steps to Gardening in Alaska". Page checked 20 Nov 2026.
# https://www.uaf.edu/ces/publications/database/gardening/easy-steps-gardening-alaska.php
# Week counts are UAF's. Day offsets below are those weeks times 7, counted
# from the city NOAA 50 percent last spring 32 F date. UAF's own example
# uses 1 June, not the station date.
AK_SOURCE = {
    "state": "AK",
    "title": "16 Easy Steps to Gardening in Alaska, UAF Cooperative Extension HGA-00134",
    "url": "https://www.uaf.edu/ces/publications/database/gardening/easy-steps-gardening-alaska.php",
    "reviewed": "checked 20 Nov 2026",
    "groups": [
        {
            "name": "Celery",
            "crops": "celery",
            "start": -84, "end": -70,
            "says": "Start 10 to 12 weeks before the average last killing frost. Counted here as 84 to 70 days before this city's NOAA 50 percent 32°F date.",
        },
        {
            "name": "Tanana tomato and Brussels sprouts",
            "crops": "Tanana tomato, Brussels sprouts",
            "start": -56, "end": -56,
            "says": "Start 8 weeks before the average last killing frost. UAF names Tanana tomatoes at 8 weeks and other outdoor tomatoes at 6 weeks. Those are not the same row.",
        },
        {
            "name": "Eggplant, pepper, other tomato",
            "crops": "eggplant, pepper, outdoor tomato other than Tanana",
            "start": -42, "end": -42,
            "says": "Start 6 weeks before the average last killing frost. UAF marks eggplant as difficult to transplant: sow several seeds in one pot and move a single plant without disturbing the roots.",
        },
        {
            "name": "Cole crops and early head lettuce",
            "crops": "cabbage, cauliflower, broccoli, head lettuce, kale",
            "start": -42, "end": -28,
            "says": "Start 4 to 6 weeks before the average last killing frost. UAF limits the head lettuce and kale note to an early crop. Cabbage, cauliflower, Brussels sprouts, and broccoli are usually set out as transplants.",
        },
        {
            "name": "Squash, cucumber, pumpkin",
            "crops": "summer squash, cucumber, pumpkin",
            "start": -21, "end": -21,
            "says": "Start 3 weeks before the average last killing frost. UAF marks these as difficult to transplant and says to sow three seeds in a 3 to 4 inch pot, then keep the strongest plant.",
        },
        {
            "name": "Direct seed",
            "crops": "bean, pea, beet, potato, carrot, radish, chard, rutabaga, corn under plastic, parsley, kale, parsnip, kohlrabi, spinach, lettuce, turnip, mustard, zucchini, green onion",
            "start": -14, "end": 0,
            "says": "UAF says these may be seeded in the garden up to two weeks before the last killing frost, with little danger of loss. The same publication says beans freeze easily and that an early bean planting needs cover when the night falls near freezing, and it lists corn only under plastic. The span is 14 days before the NOAA 50 percent date through that date.",
        },
    ],
    "extra": "UAF's worked example counts six weeks back from a 1 June last killing frost and lands on 20 April. This table uses that counting rule with this city's NOAA 50 percent date, not 1 June. HGA-00134 says the Anchorage area, the Kenai Peninsula, and Bristol Bay have low soil temperatures because wind off the water moderates the summer, and it names clear plastic mulch for warm soil crops such as corn, tomatoes, and squash. A garden in a frost pocket, it says, should be planted only with frost resistant vegetables, and a few feet of extra elevation can add days to the season. Outside the Interior, UAF says few sites ripen tomatoes, except favored spots in Anchorage and the Matanuska Valley under plastic mulch. Peat pots are not recommended, because they do not break down in cold Alaska soils. These counted dates are medians plus extension offsets, not a forecast and not agricultural advice.",
}

SOURCES = {
    "CO": CO_SOURCE,
    "NH": NH_SOURCE,
    "AK": AK_SOURCE,
}


def _shift(mmdd, days):
    month, day = int(mmdd[:2]), int(mmdd[3:5])
    # 2024 is a leap year so a Feb 29 normal, if one appears, still resolves.
    d = date(2024, month, day) + timedelta(days=days)
    return d


def _fmt(d):
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    return f"{months[d.month - 1]} {d.day}"


def offset_rows(source, mmdd):
    """Rows of (name, crops, says, when, months) for a frost date MM/DD, or None if no date."""
    rows = []
    for g in source["groups"]:
        when = ""
        months = set()
        if mmdd and g["start"] is not None:
            start = _shift(mmdd, g["start"])
            months.add(start.month)
            if g["end"] is None or g["end"] == g["start"]:
                when = _fmt(start)
                if g["end"] is None and g["start"] != 0:
                    when = when + " onward"
                elif g["end"] is None and g["start"] == 0:
                    when = when + " onward"
            else:
                end = _shift(mmdd, g["end"])
                months.add(end.month)
                # Include months the span crosses.
                d = start
                guard = 0
                while d != end and guard < 40:
                    months.add(d.month)
                    d += timedelta(days=1)
                    guard += 1
                months.add(end.month)
                when = f"{_fmt(start)} to {_fmt(end)}"
        rows.append({
            "name": g["name"],
            "crops": g["crops"],
            "says": g["says"],
            "when": when,
            "months": sorted(months),
        })
    return rows
