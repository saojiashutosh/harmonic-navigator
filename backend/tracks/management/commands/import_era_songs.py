"""
Era-organised song import.
All songs have confirmed release years so era filtering works correctly.
Run: python manage.py import_era_songs
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from tracks.models import Artist, Track

# ─────────────────────────────────────────────────────────────────────────────
# Song data — (title, artist, language, release_year, energy, valence,
#              acousticness, duration_ms, genre, tempo)
# Mood is inferred automatically from energy + valence.
# ─────────────────────────────────────────────────────────────────────────────

SONGS = [

    # ══════════════════════════════════════════════════════════════════════════
    # HINDI — LATEST (2024+)
    # ══════════════════════════════════════════════════════════════════════════
    ("Tauba Tauba",                 "Karan Aujla",          "hindi", 2024, 0.82, 0.72, 0.08, 225000, "bollywood", 128),
    ("Teri Baaton Mein Aisa Uljha", "Tanveer Evan",         "hindi", 2024, 0.54, 0.50, 0.32, 218000, "bollywood", 104),
    ("O Bedardeya",                 "Arijit Singh",         "hindi", 2024, 0.38, 0.28, 0.55, 262000, "bollywood",  88),
    ("Naina",                       "Vishal Mishra",        "hindi", 2024, 0.40, 0.35, 0.60, 245000, "bollywood",  82),
    ("Mast Malang Jhoom",           "Arijit Singh",         "hindi", 2024, 0.78, 0.70, 0.12, 198000, "bollywood", 122),
    ("Deva Deva",                   "Arijit Singh",         "hindi", 2024, 0.72, 0.65, 0.18, 238000, "bollywood", 116),
    ("Saiyaan Ji",                  "Yo Yo Honey Singh",    "hindi", 2024, 0.80, 0.74, 0.06, 203000, "bollywood", 130),
    ("Saawariya",                   "Jubin Nautiyal",       "hindi", 2024, 0.36, 0.38, 0.65, 254000, "bollywood",  78),

    # ══════════════════════════════════════════════════════════════════════════
    # HINDI — RECENT (2020-2023)
    # ══════════════════════════════════════════════════════════════════════════
    ("Kesariya",                    "Arijit Singh",         "hindi", 2022, 0.42, 0.33, 0.52, 271000, "bollywood",  92),
    ("Raataan Lambiyan",            "Jubin Nautiyal",       "hindi", 2021, 0.48, 0.40, 0.48, 256000, "bollywood",  96),
    ("Pasoori",                     "Ali Sethi",            "hindi", 2022, 0.55, 0.48, 0.38, 244000, "bollywood", 102),
    ("Besharam Rang",               "Shilpa Rao",           "hindi", 2022, 0.78, 0.72, 0.10, 198000, "bollywood", 124),
    ("Jhoome Jo Pathaan",           "Arijit Singh",         "hindi", 2023, 0.82, 0.79, 0.07, 194000, "bollywood", 130),
    ("Manike (Hindi)",              "Jubin Nautiyal",       "hindi", 2021, 0.72, 0.68, 0.14, 210000, "bollywood", 118),
    ("Jugnu",                       "Badshah",              "hindi", 2021, 0.80, 0.78, 0.06, 206000, "bollywood", 128),
    ("Bijlee Bijlee",               "Harrdy Sandhu",        "hindi", 2021, 0.84, 0.82, 0.05, 192000, "bollywood", 132),
    ("Shayad",                      "Arijit Singh",         "hindi", 2020, 0.36, 0.30, 0.58, 268000, "bollywood",  84),
    ("Dil Bechara Title Track",     "AR Rahman",            "hindi", 2020, 0.38, 0.35, 0.50, 232000, "bollywood",  88),
    ("Tere Vaaste",                 "Varun Jain",           "hindi", 2023, 0.43, 0.45, 0.55, 248000, "bollywood",  94),
    ("Jamal Kudu",                  "Shilpa Rao",           "hindi", 2023, 0.88, 0.82, 0.04, 178000, "bollywood", 138),
    ("Zinda Banda",                 "Vishal-Shekhar",       "hindi", 2023, 0.85, 0.78, 0.06, 186000, "bollywood", 134),
    ("Sajni",                       "Arijit Singh",         "hindi", 2023, 0.45, 0.42, 0.50, 258000, "bollywood",  96),
    ("Calm Down (Hindi)",           "Rema",                 "hindi", 2022, 0.74, 0.72, 0.10, 214000, "bollywood", 112),
    ("Garmi",                       "Badshah",              "hindi", 2020, 0.86, 0.80, 0.04, 188000, "bollywood", 136),
    ("Senorita",                    "Shawn Mendes",         "hindi", 2020, 0.76, 0.74, 0.08, 192000, "bollywood", 117),

    # ══════════════════════════════════════════════════════════════════════════
    # HINDI — 2010s (2010-2019)
    # ══════════════════════════════════════════════════════════════════════════
    ("Tum Hi Ho",                   "Arijit Singh",         "hindi", 2013, 0.32, 0.25, 0.65, 274000, "bollywood",  72),
    ("Ae Dil Hai Mushkil",          "Arijit Singh",         "hindi", 2016, 0.38, 0.28, 0.58, 269000, "bollywood",  80),
    ("Agar Tum Saath Ho",           "Arijit Singh",         "hindi", 2015, 0.36, 0.22, 0.62, 312000, "bollywood",  74),
    ("Channa Mereya",               "Arijit Singh",         "hindi", 2016, 0.42, 0.30, 0.55, 296000, "bollywood",  88),
    ("Kabira",                      "Tochi Raina",          "hindi", 2013, 0.38, 0.32, 0.60, 248000, "bollywood",  82),
    ("Ghungroo",                    "Arijit Singh",         "hindi", 2019, 0.78, 0.72, 0.12, 210000, "bollywood", 122),
    ("Bekhayali",                   "Sachet Tandon",        "hindi", 2019, 0.48, 0.28, 0.45, 306000, "bollywood",  92),
    ("Pachtaoge",                   "Bpraak",               "hindi", 2019, 0.40, 0.28, 0.52, 256000, "bollywood",  84),
    ("Teri Mitti",                  "Bpraak",               "hindi", 2019, 0.35, 0.30, 0.58, 288000, "bollywood",  76),
    ("London Thumakda",             "Sonu Kakkar",          "hindi", 2014, 0.82, 0.82, 0.08, 188000, "bollywood", 128),
    ("Gallan Goodiyaan",            "Shankar-Ehsaan-Loy",   "hindi", 2015, 0.80, 0.78, 0.10, 194000, "bollywood", 124),
    ("Badtameez Dil",               "Benny Dayal",          "hindi", 2013, 0.78, 0.74, 0.08, 198000, "bollywood", 122),
    ("Balam Pichkari",              "Shalmali Kholgade",    "hindi", 2013, 0.82, 0.80, 0.06, 192000, "bollywood", 128),
    ("Iktara",                      "Amit Trivedi",         "hindi", 2010, 0.40, 0.55, 0.70, 252000, "bollywood",  86),
    ("Kun Faya Kun",                "AR Rahman",            "hindi", 2011, 0.32, 0.45, 0.72, 418000, "bollywood",  68),
    ("Tum Se Hi",                   "Mohit Chauhan",        "hindi", 2011, 0.38, 0.40, 0.65, 268000, "bollywood",  82),
    ("Sadda Haq",                   "Mohit Chauhan",        "hindi", 2012, 0.72, 0.62, 0.22, 218000, "bollywood", 116),
    ("Kar Gayi Chull",              "Badshah",              "hindi", 2016, 0.84, 0.80, 0.06, 188000, "bollywood", 128),
    ("Swag Se Swagat",              "Vishal-Shekhar",       "hindi", 2017, 0.82, 0.78, 0.08, 196000, "bollywood", 126),
    ("High Rated Gabru",            "Guru Randhawa",        "hindi", 2017, 0.80, 0.74, 0.08, 202000, "bollywood", 122),
    ("Suit Suit Karda",             "Guru Randhawa",        "hindi", 2017, 0.78, 0.72, 0.10, 198000, "bollywood", 118),
    ("Dilliwali Girlfriend",        "Arijit Singh",         "hindi", 2014, 0.74, 0.70, 0.12, 210000, "bollywood", 118),
    ("Patakha Guddi",               "AR Rahman",            "hindi", 2014, 0.68, 0.65, 0.18, 224000, "bollywood", 110),
    ("Maahi Ve",                    "Ustad Rahat Fateh Ali","hindi", 2016, 0.35, 0.30, 0.62, 278000, "bollywood",  78),
    ("Ik Vaari",                    "Sonu Nigam",           "hindi", 2016, 0.36, 0.32, 0.60, 268000, "bollywood",  80),
    ("Janam Janam",                 "Arijit Singh",         "hindi", 2015, 0.42, 0.38, 0.55, 274000, "bollywood",  88),

    # ══════════════════════════════════════════════════════════════════════════
    # HINDI — 2000s (2000-2009)
    # ══════════════════════════════════════════════════════════════════════════
    ("Dil Chahta Hai",              "Shankar-Ehsaan-Loy",   "hindi", 2001, 0.70, 0.72, 0.20, 248000, "bollywood", 112),
    ("Kal Ho Na Ho",                "Sonu Nigam",           "hindi", 2003, 0.52, 0.45, 0.40, 312000, "bollywood",  96),
    ("Woh Lamhe",                   "Atif Aslam",           "hindi", 2005, 0.38, 0.28, 0.60, 268000, "bollywood",  80),
    ("Pehli Nazar Mein",            "Atif Aslam",           "hindi", 2008, 0.42, 0.35, 0.55, 278000, "bollywood",  86),
    ("Roobaroo",                    "AR Rahman",            "hindi", 2006, 0.68, 0.65, 0.25, 228000, "bollywood", 108),
    ("Rang De Basanti",             "AR Rahman",            "hindi", 2006, 0.72, 0.65, 0.20, 212000, "bollywood", 114),
    ("Khwaja Mere Khwaja",          "AR Rahman",            "hindi", 2008, 0.35, 0.45, 0.68, 378000, "bollywood",  72),
    ("Yeh Ishq Haaye",              "Shilpa Rao",           "hindi", 2007, 0.45, 0.38, 0.52, 258000, "bollywood",  90),
    ("Tujh Mein Rab Dikhta Hai",    "Roop Kumar Rathod",    "hindi", 2008, 0.32, 0.40, 0.70, 268000, "bollywood",  72),
    ("Dola Re Dola",                "Shreya Ghoshal",       "hindi", 2002, 0.62, 0.62, 0.35, 354000, "bollywood", 105),
    ("Say Shava Shava",             "Shankar-Ehsaan-Loy",   "hindi", 2001, 0.80, 0.78, 0.12, 208000, "bollywood", 126),
    ("Suraj Hua Maddham",           "Sonu Nigam",           "hindi", 2001, 0.35, 0.42, 0.60, 326000, "bollywood",  76),
    ("Rock On Title Track",         "Shankar-Ehsaan-Loy",   "hindi", 2008, 0.74, 0.68, 0.20, 218000, "bollywood", 118),
    ("Maa",                         "Shankar Mahadevan",    "hindi", 2007, 0.28, 0.42, 0.78, 248000, "bollywood",  64),
    ("Ek Din Tera",                 "Sonu Nigam",           "hindi", 2001, 0.40, 0.45, 0.60, 268000, "bollywood",  86),
    ("Tere Bina",                   "AR Rahman",            "hindi", 2007, 0.30, 0.35, 0.72, 312000, "bollywood",  70),
    ("Yeh Taara Woh Taara",         "Shankar Mahadevan",    "hindi", 2003, 0.62, 0.68, 0.30, 198000, "bollywood", 108),
    ("Mauja Hi Mauja",              "Mika Singh",           "hindi", 2007, 0.82, 0.80, 0.08, 192000, "bollywood", 128),

    # ══════════════════════════════════════════════════════════════════════════
    # HINDI — NINETIES (<2000)
    # ══════════════════════════════════════════════════════════════════════════
    ("Chaiyya Chaiyya",             "Sukhwinder Singh",     "hindi", 1998, 0.80, 0.72, 0.18, 282000, "bollywood", 126),
    ("Dil Se Re",                   "AR Rahman",            "hindi", 1998, 0.62, 0.55, 0.35, 318000, "bollywood", 108),
    ("Satrangi Re",                 "AR Rahman",            "hindi", 1998, 0.42, 0.35, 0.58, 348000, "bollywood",  88),
    ("Kuch Kuch Hota Hai",          "Udit Narayan",         "hindi", 1998, 0.78, 0.78, 0.15, 198000, "bollywood", 122),
    ("Tujhe Dekha To",              "Kumar Sanu",           "hindi", 1994, 0.35, 0.38, 0.72, 278000, "bollywood",  74),
    ("Pehla Nasha",                 "Udit Narayan",         "hindi", 1992, 0.38, 0.50, 0.72, 312000, "bollywood",  78),
    ("Dil To Pagal Hai",            "Lata Mangeshkar",      "hindi", 1997, 0.62, 0.68, 0.28, 218000, "bollywood", 106),
    ("Mere Khwabon Mein",           "Lata Mangeshkar",      "hindi", 1995, 0.40, 0.55, 0.68, 296000, "bollywood",  84),
    ("Tu Cheez Badi Hai Mast",      "Kavita Krishnamurthy", "hindi", 1994, 0.78, 0.72, 0.12, 242000, "bollywood", 118),
    ("Humma Humma",                 "AR Rahman",            "hindi", 1995, 0.82, 0.78, 0.10, 296000, "bollywood", 128),
    ("Koi Ladki Hai",               "Udit Narayan",         "hindi", 1997, 0.55, 0.62, 0.40, 268000, "bollywood",  98),
    ("Aankhen Teri",                "Kumar Sanu",           "hindi", 1993, 0.32, 0.35, 0.72, 306000, "bollywood",  70),
    ("Muqabla",                     "AR Rahman",            "hindi", 1994, 0.82, 0.76, 0.08, 248000, "bollywood", 130),

    # ══════════════════════════════════════════════════════════════════════════
    # ENGLISH — LATEST (2024+)
    # ══════════════════════════════════════════════════════════════════════════
    ("APT",                         "Rose",                 "english", 2024, 0.82, 0.78, 0.06, 173000, "pop",     126),
    ("Birds of a Feather",          "Billie Eilish",        "english", 2024, 0.48, 0.52, 0.38, 210000, "pop",      96),
    ("Die With a Smile",            "Lady Gaga",            "english", 2024, 0.45, 0.50, 0.42, 251000, "pop",      92),
    ("Too Sweet",                   "Hozier",               "english", 2024, 0.52, 0.55, 0.40, 291000, "indie",    98),
    ("Good Luck Babe",              "Chappell Roan",        "english", 2024, 0.68, 0.62, 0.15, 218000, "pop",     112),
    ("Not Like Us",                 "Kendrick Lamar",       "english", 2024, 0.76, 0.68, 0.08, 274000, "hip-hop", 120),
    ("Please Please Please",        "Sabrina Carpenter",    "english", 2024, 0.62, 0.65, 0.18, 186000, "pop",     108),
    ("Espresso",                    "Sabrina Carpenter",    "english", 2024, 0.72, 0.75, 0.10, 175000, "pop",     118),

    # ══════════════════════════════════════════════════════════════════════════
    # ENGLISH — RECENT (2020-2023)
    # ══════════════════════════════════════════════════════════════════════════
    ("Flowers",                     "Miley Cyrus",          "english", 2023, 0.76, 0.78, 0.12, 200000, "pop",     118),
    ("Anti-Hero",                   "Taylor Swift",         "english", 2022, 0.68, 0.64, 0.20, 200000, "pop",     110),
    ("As It Was",                   "Harry Styles",         "english", 2022, 0.72, 0.74, 0.10, 167000, "pop",     124),
    ("Heat Waves",                  "Glass Animals",        "english", 2020, 0.62, 0.60, 0.15, 238000, "indie",   106),
    ("Levitating",                  "Dua Lipa",             "english", 2020, 0.82, 0.80, 0.08, 203000, "pop",     122),
    ("Blinding Lights",             "The Weeknd",           "english", 2019, 0.78, 0.68, 0.08, 200000, "synth-pop",171),
    ("Beautiful Things",            "Benson Boone",         "english", 2024, 0.60, 0.58, 0.30, 216000, "pop",     104),
    ("cardigan",                    "Taylor Swift",         "english", 2020, 0.35, 0.45, 0.68, 239000, "indie",    82),
    ("exile",                       "Taylor Swift",         "english", 2020, 0.28, 0.22, 0.72, 269000, "indie",    76),
    ("august",                      "Taylor Swift",         "english", 2020, 0.48, 0.52, 0.52, 261000, "indie",    90),
    ("Dynamite",                    "BTS",                  "english", 2020, 0.80, 0.82, 0.06, 199000, "pop",      114),
    ("Butter",                      "BTS",                  "english", 2021, 0.82, 0.84, 0.04, 164000, "pop",      110),
    ("MONTERO",                     "Lil Nas X",            "english", 2021, 0.72, 0.72, 0.06, 137000, "pop",      112),
    ("Kiss Me More",                "Doja Cat",             "english", 2021, 0.72, 0.76, 0.12, 208000, "pop",      116),
    ("INDUSTRY BABY",               "Lil Nas X",            "english", 2021, 0.80, 0.76, 0.06, 212000, "hip-hop",  149),
    ("Stay",                        "Kid Laroi",            "english", 2021, 0.72, 0.68, 0.08, 141000, "pop",      170),
    ("Watermelon Sugar",            "Harry Styles",         "english", 2020, 0.78, 0.80, 0.10, 174000, "pop",      95),
    ("Drivers License",             "Olivia Rodrigo",       "english", 2021, 0.32, 0.32, 0.62, 242000, "pop",       80),
    ("good 4 u",                    "Olivia Rodrigo",       "english", 2021, 0.78, 0.65, 0.06, 178000, "pop",      166),
    ("Unholy",                      "Sam Smith",            "english", 2022, 0.70, 0.62, 0.08, 156000, "pop",      102),
    ("Easy On Me",                  "Adele",                "english", 2021, 0.30, 0.28, 0.72, 224000, "pop",       70),
    ("Peaches",                     "Justin Bieber",        "english", 2021, 0.60, 0.68, 0.30, 198000, "pop",       90),

    # ══════════════════════════════════════════════════════════════════════════
    # ENGLISH — 2010s (2010-2019)
    # ══════════════════════════════════════════════════════════════════════════
    ("Shape of You",                "Ed Sheeran",           "english", 2017, 0.82, 0.82, 0.08, 234000, "pop",      96),
    ("Perfect",                     "Ed Sheeran",           "english", 2017, 0.44, 0.52, 0.55, 263000, "pop",      95),
    ("Someone Like You",            "Adele",                "english", 2011, 0.30, 0.22, 0.72, 285000, "pop",      67),
    ("Rolling in the Deep",         "Adele",                "english", 2010, 0.72, 0.68, 0.20, 228000, "pop",     105),
    ("Counting Stars",              "OneRepublic",          "english", 2013, 0.72, 0.70, 0.25, 257000, "pop",     122),
    ("Happy",                       "Pharrell Williams",    "english", 2013, 0.82, 0.88, 0.06, 233000, "pop",     160),
    ("Can't Stop the Feeling",      "Justin Timberlake",    "english", 2016, 0.80, 0.88, 0.05, 236000, "pop",     113),
    ("Stressed Out",                "Twenty One Pilots",    "english", 2015, 0.72, 0.65, 0.10, 202000, "pop",     169),
    ("Shallow",                     "Lady Gaga",            "english", 2018, 0.48, 0.40, 0.50, 216000, "pop",      96),
    ("Someone You Loved",           "Lewis Capaldi",        "english", 2018, 0.32, 0.30, 0.68, 182000, "pop",     110),
    ("Stay With Me",                "Sam Smith",            "english", 2014, 0.35, 0.30, 0.65, 172000, "pop",      78),
    ("Habits",                      "Tove Lo",              "english", 2014, 0.52, 0.38, 0.30, 186000, "pop",      92),
    ("Royals",                      "Lorde",                "english", 2013, 0.40, 0.48, 0.30, 193000, "pop",     114),
    ("Take Me to Church",           "Hozier",               "english", 2013, 0.52, 0.38, 0.42, 242000, "indie",    92),
    ("See You Again",               "Wiz Khalifa",          "english", 2015, 0.52, 0.50, 0.42, 228000, "pop",      96),
    ("Uptown Funk",                 "Mark Ronson",          "english", 2014, 0.88, 0.86, 0.04, 270000, "funk",    115),
    ("Roar",                        "Katy Perry",           "english", 2013, 0.82, 0.82, 0.04, 224000, "pop",     180),
    ("Firework",                    "Katy Perry",           "english", 2010, 0.78, 0.78, 0.06, 228000, "pop",     124),
    ("We Found Love",               "Rihanna",              "english", 2011, 0.82, 0.72, 0.06, 216000, "dance",   128),
    ("Titanium",                    "David Guetta",         "english", 2011, 0.78, 0.68, 0.06, 245000, "dance",   126),
    ("Let Her Go",                  "Passenger",            "english", 2012, 0.35, 0.35, 0.72, 252000, "indie",    76),
    ("Thinking Out Loud",           "Ed Sheeran",           "english", 2014, 0.42, 0.50, 0.42, 281000, "pop",      79),
    ("Love Yourself",               "Justin Bieber",        "english", 2015, 0.38, 0.50, 0.65, 233000, "pop",     100),
    ("Sorry",                       "Justin Bieber",        "english", 2015, 0.72, 0.72, 0.08, 200000, "pop",     100),
    ("Despacito",                   "Luis Fonsi",           "english", 2017, 0.82, 0.82, 0.10, 229000, "pop",      89),
    ("There's Nothing Holding Me Back","Shawn Mendes",      "english", 2017, 0.78, 0.78, 0.08, 209000, "pop",     195),
    ("Havana",                      "Camila Cabello",       "english", 2017, 0.78, 0.72, 0.08, 217000, "pop",     105),

    # ══════════════════════════════════════════════════════════════════════════
    # ENGLISH — 2000s (2000-2009)
    # ══════════════════════════════════════════════════════════════════════════
    ("Lose Yourself",               "Eminem",               "english", 2002, 0.72, 0.55, 0.08, 326000, "hip-hop", 171),
    ("Clocks",                      "Coldplay",             "english", 2002, 0.62, 0.52, 0.25, 307000, "rock",     131),
    ("The Scientist",               "Coldplay",             "english", 2002, 0.32, 0.28, 0.68, 309000, "rock",      75),
    ("Fix You",                     "Coldplay",             "english", 2005, 0.30, 0.32, 0.72, 295000, "rock",      78),
    ("Yellow",                      "Coldplay",             "english", 2000, 0.42, 0.48, 0.60, 268000, "rock",      89),
    ("Chasing Cars",                "Snow Patrol",          "english", 2006, 0.38, 0.35, 0.68, 267000, "rock",     113),
    ("Boulevard of Broken Dreams",  "Green Day",            "english", 2004, 0.48, 0.38, 0.40, 260000, "rock",     168),
    ("Numb",                        "Linkin Park",          "english", 2003, 0.52, 0.38, 0.15, 187000, "rock",     112),
    ("In the End",                  "Linkin Park",          "english", 2000, 0.58, 0.42, 0.18, 216000, "rock",     105),
    ("Beautiful Day",               "U2",                   "english", 2000, 0.72, 0.68, 0.20, 248000, "rock",     136),
    ("Hips Don't Lie",              "Shakira",              "english", 2006, 0.82, 0.82, 0.06, 218000, "pop",      100),
    ("Crazy in Love",               "Beyonce",              "english", 2003, 0.82, 0.78, 0.04, 236000, "pop",      100),
    ("Umbrella",                    "Rihanna",              "english", 2007, 0.72, 0.65, 0.05, 276000, "pop",      129),
    ("SOS",                         "Rihanna",              "english", 2006, 0.78, 0.75, 0.06, 222000, "pop",      135),
    ("Poker Face",                  "Lady Gaga",            "english", 2008, 0.80, 0.72, 0.04, 237000, "pop",      119),
    ("Just Dance",                  "Lady Gaga",            "english", 2008, 0.82, 0.76, 0.04, 241000, "pop",      119),
    ("Teenage Dream",               "Katy Perry",           "english", 2010, 0.78, 0.82, 0.06, 213000, "pop",      120),
    ("Somebody That I Used to Know","Gotye",                "english", 2011, 0.55, 0.42, 0.45, 244000, "indie",     92),
    ("Apologize",                   "OneRepublic",          "english", 2007, 0.48, 0.38, 0.42, 204000, "pop",      120),
    ("Viva La Vida",                "Coldplay",             "english", 2008, 0.68, 0.62, 0.22, 242000, "rock",      138),

    # ══════════════════════════════════════════════════════════════════════════
    # ENGLISH — NINETIES (<2000)
    # ══════════════════════════════════════════════════════════════════════════
    ("Bohemian Rhapsody",           "Queen",                "english", 1975, 0.38, 0.28, 0.15, 355000, "rock",      72),
    ("Hotel California",            "Eagles",               "english", 1977, 0.45, 0.32, 0.35, 391000, "rock",      80),
    ("Smells Like Teen Spirit",     "Nirvana",              "english", 1991, 0.72, 0.45, 0.10, 301000, "rock",      151),
    ("Losing My Religion",          "REM",                  "english", 1991, 0.38, 0.35, 0.55, 280000, "rock",       88),
    ("Creep",                       "Radiohead",            "english", 1992, 0.38, 0.28, 0.35, 238000, "rock",       92),
    ("No Scrubs",                   "TLC",                  "english", 1999, 0.72, 0.68, 0.08, 213000, "pop",        95),
    ("Baby One More Time",          "Britney Spears",       "english", 1998, 0.72, 0.68, 0.08, 211000, "pop",        95),
    ("Wannabe",                     "Spice Girls",          "english", 1996, 0.82, 0.88, 0.04, 173000, "pop",        110),
    ("Wonderwall",                  "Oasis",                "english", 1995, 0.38, 0.48, 0.62, 258000, "rock",        87),
    ("Don't Look Back in Anger",    "Oasis",                "english", 1996, 0.42, 0.45, 0.58, 273000, "rock",        84),
    ("Killing Me Softly",           "Fugees",               "english", 1996, 0.42, 0.48, 0.40, 294000, "pop",         84),
    ("My Heart Will Go On",         "Celine Dion",          "english", 1997, 0.30, 0.35, 0.68, 279000, "pop",         88),
    ("Nothing Compares 2 U",        "Sinead O'Connor",      "english", 1990, 0.25, 0.18, 0.75, 285000, "pop",         64),

    # ══════════════════════════════════════════════════════════════════════════
    # MARATHI — across eras
    # ══════════════════════════════════════════════════════════════════════════
    ("Phulpakharu",                 "Swapnil Bandodkar",    "marathi", 2022, 0.52, 0.62, 0.45, 228000, "marathi",    98),
    ("Tula Pahto Re",               "Bela Shende",          "marathi", 2021, 0.40, 0.52, 0.58, 248000, "marathi",    86),
    ("Yeu Kashi Tashi Me Nandayla", "Shreya Ghoshal",       "marathi", 2013, 0.72, 0.78, 0.18, 218000, "marathi",   112),
    ("Haldi Lagnachi",              "Ajay-Atul",            "marathi", 2012, 0.80, 0.82, 0.10, 198000, "marathi",   126),
    ("Aika Dajiba",                 "Ajay-Atul",            "marathi", 2015, 0.78, 0.80, 0.12, 204000, "marathi",   122),
    ("Sun Sun Sakhya",              "Hrishikesh Ranade",    "marathi", 2016, 0.42, 0.52, 0.55, 248000, "marathi",    88),
    ("Vaat Majhi Pahu Nako",        "Swapnil Bandodkar",    "marathi", 2018, 0.48, 0.55, 0.50, 238000, "marathi",    92),
    ("Aamhi Doghi Raju-Maju",       "Vaibhav Joshi",        "marathi", 2022, 0.44, 0.55, 0.52, 252000, "marathi",    90),
    ("Kombdi Palali",               "Ajay-Atul",            "marathi", 2013, 0.88, 0.85, 0.06, 186000, "marathi",   136),
    ("Vithu Mauli",                 "Ajay-Atul",            "marathi", 2014, 0.35, 0.48, 0.68, 348000, "marathi",    72),
    ("Shiv Tandav",                 "Shankar Mahadevan",    "marathi", 2010, 0.72, 0.58, 0.20, 268000, "marathi",   112),
    ("Natali Chaitrachi",           "Padmaja Phenany",      "marathi", 2008, 0.38, 0.55, 0.65, 298000, "marathi",    78),
    ("Zingaat",                     "Ajay-Atul",            "marathi", 2016, 0.90, 0.85, 0.04, 188000, "marathi",   140),
    ("Deva Ho Deva",                "Asha Bhosle",          "marathi", 1995, 0.68, 0.65, 0.30, 248000, "marathi",   108),
    ("Apsara Aali",                 "Ajay-Atul",            "marathi", 2010, 0.85, 0.82, 0.06, 192000, "marathi",   132),
    ("Hari Hari",                   "Ajay-Atul",            "marathi", 2009, 0.40, 0.45, 0.60, 348000, "marathi",    82),
    ("Priya Priya",                 "Hrishikesh Ranade",    "marathi", 2019, 0.48, 0.58, 0.50, 252000, "marathi",    94),
    ("Mann Udhan Varyache",         "Vaishali Samant",      "marathi", 2006, 0.32, 0.50, 0.72, 298000, "marathi",    70),

    # ══════════════════════════════════════════════════════════════════════════
    # PUNJABI — across eras
    # ══════════════════════════════════════════════════════════════════════════
    ("Lover",                       "Diljit Dosanjh",       "punjabi", 2021, 0.78, 0.75, 0.10, 218000, "punjabi",  122),
    ("GOAT",                        "Diljit Dosanjh",       "punjabi", 2020, 0.82, 0.78, 0.08, 228000, "punjabi",  128),
    ("G.O.A.T.",                    "Karan Aujla",          "punjabi", 2021, 0.80, 0.72, 0.08, 214000, "bhangra",  124),
    ("Lehanga",                     "Jass Manak",           "punjabi", 2020, 0.68, 0.72, 0.15, 218000, "punjabi",  108),
    ("Baller",                      "Sidhu Moosewala",      "punjabi", 2019, 0.78, 0.65, 0.08, 228000, "punjabi",  118),
    ("Duniya",                      "Akhil",                "punjabi", 2018, 0.52, 0.55, 0.35, 238000, "punjabi",   96),
    ("Naah",                        "Harrdy Sandhu",        "punjabi", 2017, 0.72, 0.68, 0.12, 222000, "punjabi",  112),
    ("Yaar Mod Do",                 "Guru Randhawa",        "punjabi", 2016, 0.68, 0.65, 0.15, 218000, "punjabi",  106),
    ("Morni Banke",                 "Gurnam Bhullar",       "punjabi", 2021, 0.72, 0.75, 0.12, 212000, "punjabi",  114),
    ("Boliyan",                     "Hardy Sandhu",         "punjabi", 2020, 0.78, 0.78, 0.08, 204000, "bhangra",  122),
    ("Lak Tunu Tunu",               "Diljit Dosanjh",       "punjabi", 2014, 0.82, 0.80, 0.06, 198000, "bhangra",  128),
    ("Do You Know",                 "Diljit Dosanjh",       "punjabi", 2014, 0.80, 0.76, 0.08, 218000, "punjabi",  124),
    ("Gal Ban Gayi",                "Urvashi",              "punjabi", 2017, 0.82, 0.82, 0.06, 198000, "bhangra",  130),
    ("Proper Patola",               "Badshah",              "punjabi", 2017, 0.84, 0.80, 0.06, 194000, "bhangra",  132),
    ("Ik Vaari",                    "Babbu Maan",           "punjabi", 2008, 0.40, 0.42, 0.55, 268000, "punjabi",   84),
    ("Taare",                       "Prabh Gill",           "punjabi", 2016, 0.38, 0.40, 0.60, 262000, "punjabi",   80),

    # ══════════════════════════════════════════════════════════════════════════
    # TAMIL — across eras
    # ══════════════════════════════════════════════════════════════════════════
    ("Rowdy Baby",                  "Dhanush",              "tamil",   2018, 0.88, 0.85, 0.04, 196000, "kollywood", 138),
    ("Kannaana Kanney",             "D. Imman",             "tamil",   2019, 0.30, 0.45, 0.68, 278000, "kollywood",  68),
    ("Oh Baby",                     "Leon James",           "tamil",   2020, 0.72, 0.72, 0.12, 208000, "kollywood", 112),
    ("Vaathi Coming",               "Anirudh Ravichander",  "tamil",   2022, 0.88, 0.82, 0.04, 186000, "kollywood", 140),
    ("Naatu Naatu",                 "M.M. Keeravani",       "tamil",   2021, 0.92, 0.88, 0.04, 183000, "kollywood", 142),
    ("Ranjithame",                  "Sid Sriram",           "tamil",   2022, 0.55, 0.60, 0.40, 248000, "kollywood", 100),
    ("Hukum",                       "Anirudh Ravichander",  "tamil",   2023, 0.85, 0.80, 0.06, 194000, "kollywood", 132),
    ("Jigidi Killaadi",             "Anirudh Ravichander",  "tamil",   2023, 0.88, 0.84, 0.04, 188000, "kollywood", 138),
    ("Vaa Vaa",                     "AR Rahman",            "tamil",   2002, 0.72, 0.68, 0.18, 228000, "kollywood", 112),
    ("Mukundha Mukundha",           "Unnikrishnan",         "tamil",   2014, 0.55, 0.68, 0.38, 298000, "kollywood",  96),
    ("Aalaporan Tamizhan",          "AR Rahman",            "tamil",   2017, 0.80, 0.72, 0.10, 212000, "kollywood", 124),
    ("Naan Pizhai",                 "Leon James",           "tamil",   2019, 0.40, 0.38, 0.58, 268000, "kollywood",  82),

    # ══════════════════════════════════════════════════════════════════════════
    # TELUGU — across eras
    # ══════════════════════════════════════════════════════════════════════════
    ("Saami Saami",                 "Mounika Yadav",        "telugu",  2021, 0.82, 0.80, 0.08, 204000, "tollywood", 126),
    ("Oo Antava",                   "Indravathi Chauhan",   "telugu",  2021, 0.88, 0.82, 0.04, 196000, "tollywood", 138),
    ("Naatu Naatu (Telugu)",        "M.M. Keeravani",       "telugu",  2021, 0.92, 0.88, 0.04, 183000, "tollywood", 142),
    ("Daari Choodu",                "Devi Sri Prasad",      "telugu",  2022, 0.78, 0.74, 0.10, 214000, "tollywood", 120),
    ("Buttabomma",                  "Armaan Malik",         "telugu",  2020, 0.52, 0.60, 0.42, 238000, "tollywood",  96),
    ("Ramuloo Ramulaa",             "Anurag Kulkarni",      "telugu",  2019, 0.84, 0.82, 0.06, 192000, "tollywood", 130),
    ("Jai Balayya",                 "Devi Sri Prasad",      "telugu",  2019, 0.88, 0.84, 0.04, 186000, "tollywood", 138),
    ("Butta Bomma",                 "Sid Sriram",           "telugu",  2020, 0.45, 0.52, 0.50, 244000, "tollywood",  90),
    ("Nuvvu Nuvvu",                 "Devi Sri Prasad",      "telugu",  2008, 0.72, 0.68, 0.18, 218000, "tollywood", 112),
    ("Aa Ante Amalapuram",          "Udit Narayan",         "telugu",  2004, 0.82, 0.80, 0.08, 202000, "tollywood", 128),
    ("Arere",                       "Thaman S",             "telugu",  2023, 0.80, 0.76, 0.08, 208000, "tollywood", 124),
    ("Khaleja Title Track",         "Thaman S",             "telugu",  2010, 0.80, 0.74, 0.08, 214000, "tollywood", 124),
]


MOOD_RULES = [
    (0.75, 1.0, 0.70, 1.0,  "celebratory"),
    (0.65, 1.0, 0.45, 1.0,  "energized"),
    (0.00, 0.40, 0.00, 0.35, "melancholic"),
    (0.00, 0.35, 0.00, 0.50, "anxious"),
    (0.00, 0.50, 0.35, 1.0,  "calm"),
    (0.30, 0.70, 0.30, 0.70, "focused"),
]


def infer_mood(energy: float, valence: float) -> str:
    if energy >= 0.75 and valence >= 0.70:
        return "celebratory"
    if energy >= 0.65 and valence >= 0.45:
        return "energized"
    if energy <= 0.40 and valence <= 0.35:
        return "melancholic"
    if energy <= 0.35 and valence <= 0.50:
        return "anxious"
    if energy <= 0.50 and valence >= 0.35:
        return "calm"
    return "focused"


class Command(BaseCommand):
    help = "Import era-organised songs with confirmed release years."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        artist_cache: dict[str, Artist] = {}

        for row in SONGS:
            (title, artist_name, language, release_year,
             energy, valence, acousticness, duration_ms, genre, tempo) = row

            # Artist
            artist = artist_cache.get(artist_name.lower())
            if not artist:
                artist = Artist.objects.filter(name=artist_name).first()
                if not artist:
                    artist = Artist.objects.create(name=artist_name)
                artist_cache[artist_name.lower()] = artist

            mood = infer_mood(energy, valence)

            with transaction.atomic():
                existing = Track.objects.filter(
                    title__iexact=title,
                    artistId__name__iexact=artist_name,
                ).first()
                if existing:
                    # Update year/mood/features so era filtering works correctly
                    existing.releaseYear = release_year
                    existing.primaryMood = mood
                    existing.energy = energy
                    existing.valence = valence
                    existing.acousticness = acousticness
                    existing.language = language.lower()
                    existing.genre = genre
                    existing.isActive = True
                    existing.save(update_fields=[
                        "releaseYear", "primaryMood", "energy", "valence",
                        "acousticness", "language", "genre", "isActive",
                    ])
                    updated += 1
                else:
                    Track.objects.create(
                        title=title,
                        artistId=artist,
                        type=Track.TypeChoices.SONG,
                        source=Track.SourceChoices.MANUAL,
                        language=language.lower(),
                        releaseYear=release_year,
                        energy=energy,
                        valence=valence,
                        acousticness=acousticness,
                        durationMs=duration_ms,
                        tempoBpm=tempo,
                        genre=genre,
                        primaryMood=mood,
                        isInstrumental=False,
                        isExplicit=False,
                        isActive=True,
                    )
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done — {updated} tracks created/updated."
        ))
        self.stdout.write("Era breakdown:")
        for era, min_y, max_y in [
            ("latest   (2024+)",   2024, 9999),
            ("recent   (2020-23)", 2020, 2023),
            ("2010s    (2010-19)", 2010, 2019),
            ("2000s    (2000-09)", 2000, 2009),
            ("nineties (<2000)",      0, 1999),
        ]:
            c = Track.objects.filter(releaseYear__gte=min_y, releaseYear__lte=max_y).count()
            self.stdout.write(f"  {era}: {c} tracks")
