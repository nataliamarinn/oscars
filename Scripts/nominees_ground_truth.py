"""
Ground truth: Oscar Best Picture nominees and winners.

Ceremony year maps to the year the Oscars were held.
  e.g. ceremony_year=2024 → 96th Academy Awards → films from 2023.

Each entry: (ceremony_year, film_title, won)
"""

OSCAR_BEST_PICTURE: list[tuple[int, str, bool]] = [
    # ── 2025 (97th) ───────────────────────────────────────────────────────────
    (2025, "Anora", True),
    (2025, "The Brutalist", False),
    (2025, "A Complete Unknown", False),
    (2025, "Conclave", False),
    (2025, "Dune: Part Two", False),
    (2025, "Emilia Pérez", False),
    (2025, "I'm Still Here", False),
    (2025, "Nickel Boys", False),
    (2025, "The Substance", False),
    (2025, "Wicked", False),

    # ── 2024 (96th) ───────────────────────────────────────────────────────────
    (2024, "Oppenheimer", True),
    (2024, "American Fiction", False),
    (2024, "Anatomy of a Fall", False),
    (2024, "Barbie", False),
    (2024, "The Holdovers", False),
    (2024, "Killers of the Flower Moon", False),
    (2024, "Maestro", False),
    (2024, "Past Lives", False),
    (2024, "Poor Things", False),
    (2024, "Zone of Interest", False),

    # ── 2023 (95th) ───────────────────────────────────────────────────────────
    (2023, "Everything Everywhere All at Once", True),
    (2023, "All Quiet on the Western Front", False),
    (2023, "The Banshees of Inisherin", False),
    (2023, "Elvis", False),
    (2023, "The Fabelmans", False),
    (2023, "Tár", False),
    (2023, "Top Gun: Maverick", False),
    (2023, "Triangle of Sadness", False),
    (2023, "Women Talking", False),

    # ── 2022 (94th) ───────────────────────────────────────────────────────────
    (2022, "CODA", True),
    (2022, "Belfast", False),
    (2022, "Don't Look Up", False),
    (2022, "Drive My Car", False),
    (2022, "Dune", False),
    (2022, "King Richard", False),
    (2022, "Licorice Pizza", False),
    (2022, "Nightmare Alley", False),
    (2022, "The Power of the Dog", False),
    (2022, "West Side Story", False),

    # ── 2021 (93rd) ───────────────────────────────────────────────────────────
    (2021, "Nomadland", True),
    (2021, "The Father", False),
    (2021, "Judas and the Black Messiah", False),
    (2021, "Mank", False),
    (2021, "Minari", False),
    (2021, "Promising Young Woman", False),
    (2021, "Sound of Metal", False),
    (2021, "The Trial of the Chicago 7", False),

    # ── 2020 (92nd) ───────────────────────────────────────────────────────────
    (2020, "Parasite", True),
    (2020, "Ford v Ferrari", False),
    (2020, "The Irishman", False),
    (2020, "Jojo Rabbit", False),
    (2020, "Joker", False),
    (2020, "Little Women", False),
    (2020, "Marriage Story", False),
    (2020, "1917", False),
    (2020, "Once Upon a Time in Hollywood", False),

    # ── 2019 (91st) ───────────────────────────────────────────────────────────
    (2019, "Green Book", True),
    (2019, "Black Panther", False),
    (2019, "BlacKkKlansman", False),
    (2019, "Bohemian Rhapsody", False),
    (2019, "The Favourite", False),
    (2019, "Roma", False),
    (2019, "A Star Is Born", False),
    (2019, "Vice", False),

    # ── 2018 (90th) ───────────────────────────────────────────────────────────
    (2018, "The Shape of Water", True),
    (2018, "Call Me by Your Name", False),
    (2018, "Darkest Hour", False),
    (2018, "Dunkirk", False),
    (2018, "Get Out", False),
    (2018, "Lady Bird", False),
    (2018, "Phantom Thread", False),
    (2018, "The Post", False),
    (2018, "Three Billboards Outside Ebbing, Missouri", False),

    # ── 2017 (89th) ───────────────────────────────────────────────────────────
    (2017, "Moonlight", True),
    (2017, "Arrival", False),
    (2017, "Fences", False),
    (2017, "Hacksaw Ridge", False),
    (2017, "Hell or High Water", False),
    (2017, "Hidden Figures", False),
    (2017, "La La Land", False),
    (2017, "Lion", False),
    (2017, "Manchester by the Sea", False),

    # ── 2016 (88th) ───────────────────────────────────────────────────────────
    (2016, "Spotlight", True),
    (2016, "The Big Short", False),
    (2016, "Bridge of Spies", False),
    (2016, "Brooklyn", False),
    (2016, "Mad Max: Fury Road", False),
    (2016, "The Martian", False),
    (2016, "The Revenant", False),
    (2016, "Room", False),

    # ── 2015 (87th) ───────────────────────────────────────────────────────────
    (2015, "Birdman", True),
    (2015, "American Sniper", False),
    (2015, "Boyhood", False),
    (2015, "The Grand Budapest Hotel", False),
    (2015, "The Imitation Game", False),
    (2015, "Selma", False),
    (2015, "The Theory of Everything", False),
    (2015, "Whiplash", False),

    # ── 2014 (86th) ───────────────────────────────────────────────────────────
    (2014, "12 Years a Slave", True),
    (2014, "American Hustle", False),
    (2014, "Captain Phillips", False),
    (2014, "Dallas Buyers Club", False),
    (2014, "Gravity", False),
    (2014, "Her", False),
    (2014, "Nebraska", False),
    (2014, "Philomena", False),
    (2014, "The Wolf of Wall Street", False),

    # ── 2013 (85th) ───────────────────────────────────────────────────────────
    (2013, "Argo", True),
    (2013, "Amour", False),
    (2013, "Beasts of the Southern Wild", False),
    (2013, "Django Unchained", False),
    (2013, "Les Misérables", False),
    (2013, "Life of Pi", False),
    (2013, "Lincoln", False),
    (2013, "Silver Linings Playbook", False),
    (2013, "Zero Dark Thirty", False),

    # ── 2012 (84th) ───────────────────────────────────────────────────────────
    (2012, "The Artist", True),
    (2012, "The Descendants", False),
    (2012, "Extremely Loud & Incredibly Close", False),
    (2012, "The Help", False),
    (2012, "Hugo", False),
    (2012, "Midnight in Paris", False),
    (2012, "Moneyball", False),
    (2012, "The Tree of Life", False),
    (2012, "War Horse", False),

    # ── 2011 (83rd) ───────────────────────────────────────────────────────────
    (2011, "The King's Speech", True),
    (2011, "Black Swan", False),
    (2011, "The Fighter", False),
    (2011, "Inception", False),
    (2011, "The Kids Are All Right", False),
    (2011, "127 Hours", False),
    (2011, "The Social Network", False),
    (2011, "Toy Story 3", False),
    (2011, "True Grit", False),
    (2011, "Winter's Bone", False),

    # ── 2010 (82nd) ───────────────────────────────────────────────────────────
    (2010, "The Hurt Locker", True),
    (2010, "Avatar", False),
    (2010, "The Blind Side", False),
    (2010, "District 9", False),
    (2010, "An Education", False),
    (2010, "Inglourious Basterds", False),
    (2010, "Precious", False),
    (2010, "A Serious Man", False),
    (2010, "Up", False),
    (2010, "Up in the Air", False),

    # ── 2009 (81st) ───────────────────────────────────────────────────────────
    (2009, "Slumdog Millionaire", True),
    (2009, "The Curious Case of Benjamin Button", False),
    (2009, "Frost/Nixon", False),
    (2009, "Milk", False),
    (2009, "The Reader", False),

    # ── 2008 (80th) ───────────────────────────────────────────────────────────
    (2008, "No Country for Old Men", True),
    (2008, "Atonement", False),
    (2008, "Juno", False),
    (2008, "Michael Clayton", False),
    (2008, "There Will Be Blood", False),

    # ── 2007 (79th) ───────────────────────────────────────────────────────────
    (2007, "The Departed", True),
    (2007, "Babel", False),
    (2007, "Letters from Iwo Jima", False),
    (2007, "Little Miss Sunshine", False),
    (2007, "The Queen", False),

    # ── 2006 (78th) ───────────────────────────────────────────────────────────
    (2006, "Crash", True),
    (2006, "Brokeback Mountain", False),
    (2006, "Capote", False),
    (2006, "Good Night, and Good Luck", False),
    (2006, "Munich", False),

    # ── 2005 (77th) ───────────────────────────────────────────────────────────
    (2005, "Million Dollar Baby", True),
    (2005, "The Aviator", False),
    (2005, "Finding Neverland", False),
    (2005, "Ray", False),
    (2005, "Sideways", False),
]