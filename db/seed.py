"""Seed the database with a few well-known historical figures and sample whereabouts."""

from db import get_db


def seed():
    db = get_db()

    # Check if already seeded
    count = db.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    if count > 0:
        print(f"Database already has {count} persons, skipping seed.")
        return

    persons = [
        {
            'name': 'Leonardo da Vinci',
            'birth_date_start': '1452-04-15', 'birth_date_end': '1452-04-15',
            'birth_date_display': 'April 15, 1452',
            'death_date_start': '1519-05-02', 'death_date_end': '1519-05-02',
            'death_date_display': 'May 2, 1519',
            'description': 'Italian polymath of the High Renaissance, painter, sculptor, architect, musician, mathematician, engineer, inventor, anatomist, geologist, and writer.',
            'wikipedia_url': 'https://en.wikipedia.org/wiki/Leonardo_da_Vinci',
            'whereabouts': [
                {'place_name': 'Vinci, Italy', 'lat': 43.7871, 'lon': 10.8725,
                 'ds': '1452-04-15', 'de': '1466-12-31', 'prec': 'year',
                 'dd': '1452 - 1466', 'desc': 'Born and raised in Vinci', 'conf': 'certain'},
                {'place_name': 'Florence, Italy', 'lat': 43.7696, 'lon': 11.2558,
                 'ds': '1466-01-01', 'de': '1482-12-31', 'prec': 'year',
                 'dd': '1466 - 1482', 'desc': 'Apprenticed to Andrea del Verrocchio; early career as painter', 'conf': 'certain'},
                {'place_name': 'Milan, Italy', 'lat': 45.4642, 'lon': 9.1900,
                 'ds': '1482-01-01', 'de': '1499-12-31', 'prec': 'year',
                 'dd': '1482 - 1499', 'desc': 'Worked for Ludovico Sforza; painted The Last Supper', 'conf': 'certain'},
                {'place_name': 'Venice, Italy', 'lat': 45.4408, 'lon': 12.3155,
                 'ds': '1500-03-01', 'de': '1500-04-30', 'prec': 'month',
                 'dd': 'Spring 1500', 'desc': 'Brief stay after fleeing Milan', 'conf': 'probable'},
                {'place_name': 'Florence, Italy', 'lat': 43.7696, 'lon': 11.2558,
                 'ds': '1500-05-01', 'de': '1506-12-31', 'prec': 'year',
                 'dd': '1500 - 1506', 'desc': 'Painted the Mona Lisa', 'conf': 'certain'},
                {'place_name': 'Milan, Italy', 'lat': 45.4642, 'lon': 9.1900,
                 'ds': '1506-01-01', 'de': '1513-12-31', 'prec': 'year',
                 'dd': '1506 - 1513', 'desc': 'Second Milanese period; anatomical studies', 'conf': 'certain'},
                {'place_name': 'Rome, Italy', 'lat': 41.9028, 'lon': 12.4964,
                 'ds': '1513-01-01', 'de': '1516-12-31', 'prec': 'year',
                 'dd': '1513 - 1516', 'desc': 'Lived in the Vatican under Pope Leo X', 'conf': 'certain'},
                {'place_name': 'Amboise, France', 'lat': 47.4133, 'lon': 0.9826,
                 'ds': '1516-01-01', 'de': '1519-05-02', 'prec': 'year',
                 'dd': '1516 - 1519', 'desc': 'Final years at Clos Lucé as guest of King Francis I', 'conf': 'certain'},
            ]
        },
        {
            'name': 'Marco Polo',
            'birth_date_start': '1254-01-01', 'birth_date_end': '1254-12-31',
            'birth_date_display': '1254',
            'death_date_start': '1324-01-08', 'death_date_end': '1324-01-08',
            'death_date_display': 'January 8, 1324',
            'description': 'Venetian merchant, explorer, and writer who travelled through Asia along the Silk Road.',
            'wikipedia_url': 'https://en.wikipedia.org/wiki/Marco_Polo',
            'whereabouts': [
                {'place_name': 'Venice, Italy', 'lat': 45.4408, 'lon': 12.3155,
                 'ds': '1254-01-01', 'de': '1271-12-31', 'prec': 'year',
                 'dd': '1254 - 1271', 'desc': 'Born and raised in Venice', 'conf': 'certain'},
                {'place_name': 'Acre, Israel', 'lat': 32.9226, 'lon': 35.0697,
                 'ds': '1271-11-01', 'de': '1271-12-31', 'prec': 'month',
                 'dd': 'Late 1271', 'desc': 'Departed for Asia with father and uncle', 'conf': 'certain'},
                {'place_name': 'Hormuz, Iran', 'lat': 27.0862, 'lon': 56.4605,
                 'ds': '1272-01-01', 'de': '1272-06-30', 'prec': 'approximate',
                 'dd': 'Around 1272', 'desc': 'Travelled through Persia', 'conf': 'probable'},
                {'place_name': 'Kashgar, China', 'lat': 39.4704, 'lon': 75.9893,
                 'ds': '1273-01-01', 'de': '1273-12-31', 'prec': 'approximate',
                 'dd': 'Around 1273', 'desc': 'Crossed the Pamirs and entered China', 'conf': 'probable'},
                {'place_name': 'Khanbaliq (Beijing), China', 'lat': 39.9042, 'lon': 116.4074,
                 'ds': '1275-01-01', 'de': '1291-12-31', 'prec': 'year',
                 'dd': '1275 - 1291', 'desc': 'Served at the court of Kublai Khan', 'conf': 'certain'},
                {'place_name': 'Venice, Italy', 'lat': 45.4408, 'lon': 12.3155,
                 'ds': '1295-01-01', 'de': '1324-01-08', 'prec': 'year',
                 'dd': '1295 - 1324', 'desc': 'Returned to Venice; wrote Il Milione', 'conf': 'certain'},
            ]
        },
        {
            'name': 'Cleopatra VII',
            'birth_date_start': '-0068-01-01', 'birth_date_end': '-0068-12-31',
            'birth_date_display': '69 BC',
            'death_date_start': '-0029-08-12', 'death_date_end': '-0029-08-12',
            'death_date_display': 'August 12, 30 BC',
            'description': 'Last active ruler of the Ptolemaic Kingdom of Egypt, known for her relationships with Julius Caesar and Mark Antony.',
            'wikipedia_url': 'https://en.wikipedia.org/wiki/Cleopatra',
            'whereabouts': [
                {'place_name': 'Alexandria, Egypt', 'lat': 31.2001, 'lon': 29.9187,
                 'ds': '-0068-01-01', 'de': '-0048-12-31', 'prec': 'year',
                 'dd': '69 BC - 49 BC', 'desc': 'Born and raised in the Ptolemaic court', 'conf': 'certain'},
                {'place_name': 'Rome, Italy', 'lat': 41.9028, 'lon': 12.4964,
                 'ds': '-0045-01-01', 'de': '-0043-03-15', 'prec': 'year',
                 'dd': '46 BC - 44 BC', 'desc': 'Visited Rome as guest of Julius Caesar', 'conf': 'certain'},
                {'place_name': 'Alexandria, Egypt', 'lat': 31.2001, 'lon': 29.9187,
                 'ds': '-0043-03-15', 'de': '-0030-08-12', 'prec': 'year',
                 'dd': '44 BC - 30 BC', 'desc': 'Ruled Egypt; alliance with Mark Antony', 'conf': 'certain'},
            ]
        },
        {
            'name': 'Charles Darwin',
            'birth_date_start': '1809-02-12', 'birth_date_end': '1809-02-12',
            'birth_date_display': 'February 12, 1809',
            'death_date_start': '1882-04-19', 'death_date_end': '1882-04-19',
            'death_date_display': 'April 19, 1882',
            'description': 'English naturalist, geologist, and biologist, known for his contributions to evolutionary biology and the theory of natural selection.',
            'wikipedia_url': 'https://en.wikipedia.org/wiki/Charles_Darwin',
            'whereabouts': [
                {'place_name': 'Shrewsbury, England', 'lat': 52.7077, 'lon': -2.7540,
                 'ds': '1809-02-12', 'de': '1825-10-01', 'prec': 'year',
                 'dd': '1809 - 1825', 'desc': 'Born and raised; early education', 'conf': 'certain'},
                {'place_name': 'Edinburgh, Scotland', 'lat': 55.9533, 'lon': -3.1883,
                 'ds': '1825-10-01', 'de': '1827-04-01', 'prec': 'month',
                 'dd': 'Oct 1825 - Apr 1827', 'desc': 'Studied medicine at University of Edinburgh', 'conf': 'certain'},
                {'place_name': 'Cambridge, England', 'lat': 52.2053, 'lon': 0.1218,
                 'ds': '1828-01-01', 'de': '1831-08-01', 'prec': 'year',
                 'dd': '1828 - 1831', 'desc': 'Studied at Christ\'s College, Cambridge', 'conf': 'certain'},
                {'place_name': 'Plymouth, England', 'lat': 50.3755, 'lon': -4.1427,
                 'ds': '1831-12-27', 'de': '1831-12-27', 'prec': 'day',
                 'dd': 'December 27, 1831', 'desc': 'Departed on HMS Beagle', 'conf': 'certain'},
                {'place_name': 'Galápagos Islands, Ecuador', 'lat': -0.9538, 'lon': -90.9656,
                 'ds': '1835-09-15', 'de': '1835-10-20', 'prec': 'day',
                 'dd': 'Sep 15 - Oct 20, 1835', 'desc': 'Studied unique wildlife that would inform his theory of evolution', 'conf': 'certain'},
                {'place_name': 'Down House, Downe, England', 'lat': 51.3335, 'lon': 0.0530,
                 'ds': '1842-09-14', 'de': '1882-04-19', 'prec': 'day',
                 'dd': '1842 - 1882', 'desc': 'Family home where he wrote On the Origin of Species', 'conf': 'certain'},
            ]
        },
    ]

    for p in persons:
        whereabouts = p.pop('whereabouts')
        cur = db.execute(
            "INSERT INTO persons (name, birth_date_start, birth_date_end, birth_date_display, "
            "death_date_start, death_date_end, death_date_display, description, wikipedia_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p['name'], p['birth_date_start'], p['birth_date_end'], p['birth_date_display'],
             p['death_date_start'], p['death_date_end'], p['death_date_display'],
             p['description'], p['wikipedia_url'])
        )
        person_id = cur.lastrowid

        for w in whereabouts:
            w_cur = db.execute(
                "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
                "date_start, date_end, date_precision, date_display, description, confidence, "
                "extraction_method, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (person_id, w['place_name'], w['lat'], w['lon'],
                 w['ds'], w['de'], w['prec'], w['dd'], w['desc'], w['conf'],
                 'seed', 'system')
            )
            # Add a Wikipedia source for each whereabout
            db.execute(
                "INSERT INTO sources (whereabout_id, url, title, source_type) VALUES (?, ?, ?, 'webpage')",
                (w_cur.lastrowid, p['wikipedia_url'], f"Wikipedia: {p['name']}")
            )

    db.commit()
    print(f"Seeded {len(persons)} persons with whereabouts and sources.")
