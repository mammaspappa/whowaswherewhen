"""Add additional whereabouts for Ernst Jünger extracted from the full Storm of Steel text."""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def get_db():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'wwww.db')
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def main():
    db = get_db()

    # Find Jünger's person_id
    row = db.execute("SELECT id FROM persons WHERE name = 'Ernst Jünger'").fetchone()
    if not row:
        print("Ernst Jünger not found in database!")
        return
    person_id = row['id']

    # Get existing whereabout place_names to avoid duplicates
    existing = {r['place_name'] for r in db.execute(
        "SELECT place_name FROM whereabouts WHERE person_id = ?", (person_id,)
    ).fetchall()}

    gutenberg_url = 'https://www.gutenberg.org/ebooks/34099'

    new_locations = [
        # Early war movements not previously captured
        {'place': 'Le Godat, Champagne, France', 'lat': 49.3500, 'lon': 3.9700,
         'ds': '1914-12-28', 'de': '1915-02-15', 'prec': 'month',
         'dd': 'December 1914 - February 1915', 'desc': 'First front-line trench position in the Champagne chalk region opposite French lines; night watches and constant labor',
         'conf': 'certain'},
        {'place': 'Brussels, Belgium', 'lat': 50.8503, 'lon': 4.3517,
         'ds': '1915-03-10', 'de': '1915-03-15', 'prec': 'day',
         'dd': 'March 1915', 'desc': 'Transit through Brussels area after transfer to 111th Infantry Division',
         'conf': 'probable'},
        {'place': 'Hérinnes, Belgium', 'lat': 50.7400, 'lon': 3.5100,
         'ds': '1915-03-16', 'de': '1915-04-10', 'prec': 'month',
         'dd': 'March - April 1915', 'desc': 'Billeted in Flemish village; celebrated his twentieth birthday on March 29',
         'conf': 'certain'},
        {'place': 'Hal, Belgium', 'lat': 50.7338, 'lon': 4.2348,
         'ds': '1915-04-10', 'de': '1915-04-12', 'prec': 'day',
         'dd': 'April 10, 1915', 'desc': 'Railway loading point for transport to the Lorraine front',
         'conf': 'certain'},
        {'place': 'Tronville, Lorraine, France', 'lat': 49.0800, 'lon': 5.7000,
         'ds': '1915-04-12', 'de': '1915-04-20', 'prec': 'day',
         'dd': 'April 12-20, 1915', 'desc': 'Billeted near the old 1870 battlefields of Mars-la-Tour and Gravelotte',
         'conf': 'certain'},
        {'place': 'Chamblay, France', 'lat': 49.0600, 'lon': 5.7200,
         'ds': '1915-04-20', 'de': '1915-04-21', 'prec': 'day',
         'dd': 'April 20, 1915', 'desc': 'Railway station used for transport toward the Moselle heights',
         'conf': 'certain'},
        {'place': 'Pagny-sur-Moselle, France', 'lat': 48.9839, 'lon': 6.0197,
         'ds': '1915-04-21', 'de': '1915-04-21', 'prec': 'day',
         'dd': 'April 21, 1915', 'desc': 'Transit through the Moselle valley en route to front-line positions',
         'conf': 'probable'},
        {'place': 'Prény, France', 'lat': 48.9800, 'lon': 5.9900,
         'ds': '1915-04-21', 'de': '1915-04-22', 'prec': 'day',
         'dd': 'April 21, 1915', 'desc': 'Mountain village overlooking the Moselle valley with romantic ruins; staging area before Les Éparges',
         'conf': 'certain'},
        {'place': 'Hattonchâtel, France', 'lat': 48.9958, 'lon': 5.7083,
         'ds': '1915-04-22', 'de': '1915-04-23', 'prec': 'day',
         'dd': 'April 22, 1915', 'desc': 'Assembly point in woods near the Grande Tranchée; received combat supplies and grenades before the attack',
         'conf': 'certain'},
        {'place': 'St. Maurice, France', 'lat': 49.0500, 'lon': 5.6300,
         'ds': '1915-04-25', 'de': '1915-04-28', 'prec': 'day',
         'dd': 'April 25-28, 1915', 'desc': 'Church converted to field hospital where he was first treated for his Les Éparges leg wound',
         'conf': 'certain'},
        {'place': 'Döberitz, Germany', 'lat': 52.5300, 'lon': 13.0200,
         'ds': '1915-07-01', 'de': '1915-08-31', 'prec': 'month',
         'dd': 'July - August 1915', 'desc': 'Officers\' training course at the military camp; promoted to Leutnant (lieutenant)',
         'conf': 'probable'},
        {'place': 'St. Léger, France', 'lat': 50.1600, 'lon': 2.7200,
         'ds': '1915-09-01', 'de': '1915-09-10', 'prec': 'day',
         'dd': 'September 1915', 'desc': 'Division headquarters where he rejoined his regiment with replacement troops in Artois',
         'conf': 'certain'},
        {'place': 'Ransart, France', 'lat': 50.1300, 'lon': 2.6300,
         'ds': '1915-12-01', 'de': '1916-01-31', 'prec': 'month',
         'dd': 'December 1915 - January 1916', 'desc': 'Visited the Bellevue ruin, an isolated wartime estaminet overlooking no-man\'s land; witnessed civilian devastation',
         'conf': 'probable'},
        {'place': 'Boyelles, France', 'lat': 50.1200, 'lon': 2.7800,
         'ds': '1916-04-16', 'de': '1916-04-16', 'prec': 'day',
         'dd': 'April 1916', 'desc': 'Visited slaughterhouse, provisions depot, and gun repair facility during officer training course',
         'conf': 'certain'},
        {'place': 'Bourlon Wood, France', 'lat': 50.1700, 'lon': 3.1200,
         'ds': '1916-04-17', 'de': '1916-04-17', 'prec': 'day',
         'dd': 'April 1916', 'desc': 'Inspected sawmill and pioneer park during logistics training; later site of famous 1917 battle',
         'conf': 'certain'},
        {'place': 'Inchy, France', 'lat': 50.1400, 'lon': 3.0800,
         'ds': '1916-04-18', 'de': '1916-04-18', 'prec': 'day',
         'dd': 'April 1916', 'desc': 'Visited dairy, pig breeding facility, and cadaver processing station during training course inspections',
         'conf': 'certain'},
        {'place': 'Quéant, France', 'lat': 50.1500, 'lon': 2.9700,
         'ds': '1916-04-19', 'de': '1916-04-19', 'prec': 'day',
         'dd': 'April 1916', 'desc': 'Visited bakery and airfield during officer training; previously used as rest town with garrison entertainments',
         'conf': 'certain'},
        {'place': 'Douai, France', 'lat': 50.3700, 'lon': 3.0800,
         'ds': '1916-04-20', 'de': '1916-04-20', 'prec': 'day',
         'dd': 'April 1916', 'desc': 'Sunday excursion during officer training course; visited the town for rest and recreation',
         'conf': 'certain'},
        {'place': 'Valenciennes, France', 'lat': 50.3574, 'lon': 3.5236,
         'ds': '1916-04-27', 'de': '1916-04-27', 'prec': 'day',
         'dd': 'April 1916', 'desc': 'Weekend excursion from the Croisilles training course',
         'conf': 'certain'},
    ]

    inserted = 0
    for w in new_locations:
        if w['place'] in existing:
            print(f"  Skipping duplicate: {w['place']}")
            continue

        w_cur = db.execute(
            "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
            "date_start, date_end, date_precision, date_display, description, confidence, "
            "extraction_method, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (person_id, w['place'], w['lat'], w['lon'],
             w['ds'], w['de'], w['prec'], w['dd'], w['desc'], w['conf'],
             'manual', 'system')
        )
        db.execute(
            "INSERT INTO sources (whereabout_id, url, title, source_type) VALUES (?, ?, ?, 'book')",
            (w_cur.lastrowid, 'https://www.gutenberg.org/ebooks/34099',
             'Project Gutenberg: Ernst Jünger - In Stahlgewittern')
        )
        inserted += 1
        print(f"  + {w['place']} ({w['dd']})")

    db.commit()
    db.close()
    print(f"\nDone! Added {inserted} new whereabouts for Ernst Jünger (id={person_id})")


if __name__ == '__main__':
    main()
