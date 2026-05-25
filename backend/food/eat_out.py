"""Weekend "go out" picks — DFW Indian restaurants + buffets.

Curated list of places within 20-25 min of McKinney/Frisco. Mix of:
  - Hyderabadi biryani specialists (Bawarchi, Paradise, Hyderabad House)
  - South Indian / Andhra (Madras Pavilion, Chennai Cafe)
  - Buffet style (Rangoli, India Palace, Sankalp Gujarati thali)
  - Non-Indian (Brazilian steakhouse, Korean BBQ — for "out of the box")

Each entry has the current address/area + Google Maps + Yelp links so
you always land on current hours, menu, and reviews — no stale data
inside the app.
"""

EAT_OUT: list[dict] = [
    # ─── Hyderabadi biryani specialists ────────────────────────────────────
    {
        "id": "bawarchi_frisco",
        "name": "Bawarchi Biryanis Frisco",
        "cuisine": "Hyderabadi biryani · à la carte",
        "area": "Frisco · ~15 min",
        "tags": ["hyderabadi", "biryani", "weekend"],
        "vibe": "Authentic Hyderabadi dum biryani, family-style",
        "kid_friendly": True,
        "buffet": False,
        "google_maps": "https://www.google.com/maps/search/Bawarchi+Biryanis+Frisco+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Bawarchi+Biryanis&find_loc=Frisco%2C+TX",
        "emoji": "🍛",
    },
    {
        "id": "paradise_biryani_frisco",
        "name": "Paradise Biryani",
        "cuisine": "Hyderabadi biryani · à la carte",
        "area": "Frisco · ~12 min",
        "tags": ["hyderabadi", "biryani", "weekend"],
        "vibe": "Hyderabad chain — closest to the real Paradise dum biryani",
        "kid_friendly": True,
        "buffet": False,
        "google_maps": "https://www.google.com/maps/search/Paradise+Biryani+Pointe+Frisco+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Paradise+Biryani+Pointe&find_loc=Frisco%2C+TX",
        "emoji": "🍛",
    },
    {
        "id": "hyderabad_house_dfw",
        "name": "Hyderabad House",
        "cuisine": "Hyderabadi · biryani + curries",
        "area": "Plano / Frisco · ~15 min",
        "tags": ["hyderabadi", "biryani", "weekend"],
        "vibe": "Solid Hyderabadi spread; biryani + mirchi salan + bagara baingan",
        "kid_friendly": True,
        "buffet": False,
        "google_maps": "https://www.google.com/maps/search/Hyderabad+House+Plano+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Hyderabad+House&find_loc=Plano%2C+TX",
        "emoji": "🍛",
    },

    # ─── Andhra / Telangana / South Indian ─────────────────────────────────
    {
        "id": "chennai_cafe_plano",
        "name": "Chennai Cafe",
        "cuisine": "South Indian · dosa / idly / Chettinad",
        "area": "Plano · ~18 min",
        "tags": ["south_indian", "dosa", "weekend", "kid_friendly"],
        "vibe": "Family go-to for dosa, paniyaram, Chettinad chicken",
        "kid_friendly": True,
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Chennai+Cafe+Plano+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Chennai+Cafe&find_loc=Plano%2C+TX",
        "emoji": "🥞",
    },
    {
        "id": "madras_pavilion_plano",
        "name": "Madras Pavilion",
        "cuisine": "South Indian veg · buffet weekends",
        "area": "Plano · ~20 min",
        "tags": ["south_indian", "buffet", "vegetarian", "weekend", "kid_friendly"],
        "vibe": "Big weekend South Indian veg buffet — ghee dosa, sambar, chutneys, sweets",
        "kid_friendly": True,
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Madras+Pavilion+Plano+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Madras+Pavilion&find_loc=Plano%2C+TX",
        "emoji": "🍽️",
    },
    {
        "id": "godavari_irving",
        "name": "Godavari (Andhra)",
        "cuisine": "Andhra / Telangana · spicy",
        "area": "Irving / Frisco · ~25 min",
        "tags": ["andhra", "telangana", "weekend"],
        "vibe": "Authentic Andhra spice level; gongura mutton, kodi pulusu — proper Vismai-style",
        "kid_friendly": False,  # spice level
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Godavari+Restaurant+Irving+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Godavari&find_loc=Irving%2C+TX",
        "emoji": "🌶️",
    },

    # ─── Buffets (variety) ─────────────────────────────────────────────────
    {
        "id": "rangoli_frisco",
        "name": "Rangoli",
        "cuisine": "North + South Indian buffet",
        "area": "Frisco · ~15 min",
        "tags": ["indian", "buffet", "weekend", "kid_friendly"],
        "vibe": "Wide buffet — kid plays it safe with chana + naan + dal makhani",
        "kid_friendly": True,
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Rangoli+Indian+Frisco+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Rangoli&find_loc=Frisco%2C+TX",
        "emoji": "🍽️",
    },
    {
        "id": "sankalp_frisco",
        "name": "Sankalp Gujarati Thali",
        "cuisine": "Gujarati thali · unlimited",
        "area": "Frisco · ~12 min",
        "tags": ["gujarati", "thali", "vegetarian", "weekend", "out_of_box"],
        "vibe": "Try-something-different — unlimited Gujarati thali, kids love the variety",
        "kid_friendly": True,
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Sankalp+Frisco+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Sankalp&find_loc=Frisco%2C+TX",
        "emoji": "🍱",
    },

    # ─── Out-of-the-box (non-Indian, weekend treat) ────────────────────────
    {
        "id": "texas_de_brazil_plano",
        "name": "Texas de Brazil",
        "cuisine": "Brazilian steakhouse · churrasco",
        "area": "Plano (The Shops at Legacy) · ~20 min",
        "tags": ["brazilian", "meat", "out_of_box", "weekend", "splurge"],
        "vibe": "Out-of-the-box meat night — picanha, salad bar with 50+ items, sides",
        "kid_friendly": True,  # kids under 6 free, salad bar option
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Texas+de+Brazil+Plano+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Texas+de+Brazil&find_loc=Plano%2C+TX",
        "emoji": "🥩",
    },
    {
        "id": "fogo_de_chao_plano",
        "name": "Fogo de Chão",
        "cuisine": "Brazilian churrasco · all-you-can-eat",
        "area": "Plano (Legacy West) · ~22 min",
        "tags": ["brazilian", "meat", "out_of_box", "weekend", "splurge"],
        "vibe": "Higher-end Brazilian churrasco — date-night option",
        "kid_friendly": True,
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Fogo+de+Chao+Plano+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Fogo+de+Chao&find_loc=Plano%2C+TX",
        "emoji": "🥩",
    },
    {
        "id": "korean_bbq_carrollton",
        "name": "Gen Korean BBQ House",
        "cuisine": "Korean BBQ · all-you-can-eat",
        "area": "Carrollton · ~25 min",
        "tags": ["korean", "bbq", "out_of_box", "weekend"],
        "vibe": "Cook-at-table Korean BBQ — kids love watching meat sizzle, kalbi + bulgogi unlimited",
        "kid_friendly": True,
        "buffet": True,
        "google_maps": "https://www.google.com/maps/search/Gen+Korean+BBQ+Carrollton+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Gen+Korean+BBQ&find_loc=Carrollton%2C+TX",
        "emoji": "🥓",
    },
    {
        "id": "hibachi_plano",
        "name": "Sushi & Hibachi (Kabuki / Sushi Sake)",
        "cuisine": "Japanese hibachi + sushi",
        "area": "Plano / Frisco · ~15-20 min",
        "tags": ["japanese", "hibachi", "out_of_box", "weekend"],
        "vibe": "Hibachi tableside show keeps the 3.5y old entertained; sushi for adults",
        "kid_friendly": True,
        "buffet": False,
        "google_maps": "https://www.google.com/maps/search/Hibachi+Plano+TX",
        "yelp": "https://www.yelp.com/search?find_desc=Hibachi&find_loc=Plano%2C+TX",
        "emoji": "🍣",
    },
]


def picks_for_today(*, want_buffet: bool | None = None,
                    out_of_box: bool = False,
                    n: int = 4) -> list[dict]:
    """Return weekend eat-out suggestions.

    `want_buffet=True` → only buffet places.
    `out_of_box=True` → only non-Indian (Brazilian, Korean BBQ, hibachi).
    """
    pool = list(EAT_OUT)
    if want_buffet is True:
        pool = [p for p in pool if p.get("buffet")]
    elif want_buffet is False:
        pool = [p for p in pool if not p.get("buffet")]
    if out_of_box:
        pool = [p for p in pool if "out_of_box" in (p.get("tags") or [])]
    # Rotate randomly so the same restaurant doesn't always show up first
    import random
    random.shuffle(pool)
    return pool[:n]
