"""Insert historical figures from Project Gutenberg diary texts."""

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


def insert_person(db, person, whereabouts, gutenberg_url):
    """Insert a person and their whereabouts. Skip if person already exists."""
    existing = db.execute("SELECT id FROM persons WHERE name = ?", (person['name'],)).fetchone()
    if existing:
        print(f"  '{person['name']}' already exists (id={existing['id']}), skipping.")
        return existing['id']

    cur = db.execute(
        "INSERT INTO persons (name, birth_date_start, birth_date_end, birth_date_display, "
        "death_date_start, death_date_end, death_date_display, description, wikipedia_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (person['name'], person['birth_start'], person['birth_end'], person['birth_display'],
         person['death_start'], person['death_end'], person['death_display'],
         person['description'], person.get('wikipedia_url'))
    )
    person_id = cur.lastrowid
    print(f"  Created '{person['name']}' (id={person_id})")

    for w in whereabouts:
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
            (w_cur.lastrowid, gutenberg_url,
             f"Project Gutenberg: {person['name']}")
        )

    print(f"  Inserted {len(whereabouts)} whereabouts")
    return person_id


def add_pepys(db):
    """Samuel Pepys - from his Diary (Project Gutenberg #4200)."""
    print("\nSamuel Pepys (from Diary, Gutenberg #4200)")

    person = {
        'name': 'Samuel Pepys',
        'birth_start': '1633-02-23', 'birth_end': '1633-02-23', 'birth_display': 'February 23, 1633',
        'death_start': '1703-05-26', 'death_end': '1703-05-26', 'death_display': 'May 26, 1703',
        'description': 'English diarist and naval administrator. His detailed private diary, kept from 1660 to 1669, is among the most important primary sources for the English Restoration period.',
        'wikipedia_url': 'https://en.wikipedia.org/wiki/Samuel_Pepys',
    }

    whereabouts = [
        {'place': 'Brampton, Cambridgeshire, England', 'lat': 52.3280, 'lon': -0.2290,
         'ds': '1633-02-23', 'de': '1644-12-31', 'prec': 'year',
         'dd': '1633 - 1644', 'desc': 'Born and spent early childhood; family home',
         'conf': 'certain'},
        {'place': 'Huntingdon, England', 'lat': 52.3317, 'lon': -0.1860,
         'ds': '1644-01-01', 'de': '1646-12-31', 'prec': 'year',
         'dd': '1644 - 1646', 'desc': 'Attended Huntingdon Grammar School',
         'conf': 'probable'},
        {'place': "St Paul's School, London", 'lat': 51.5138, 'lon': -0.0984,
         'ds': '1646-01-01', 'de': '1650-06-30', 'prec': 'year',
         'dd': '1646 - 1650', 'desc': "Attended St Paul's School in London",
         'conf': 'certain'},
        {'place': 'Magdalene College, Cambridge', 'lat': 52.2086, 'lon': 0.1170,
         'ds': '1651-03-01', 'de': '1654-03-31', 'prec': 'year',
         'dd': '1651 - 1654', 'desc': 'Studied at Magdalene College, Cambridge; received BA',
         'conf': 'certain'},
        {'place': 'Axe Yard, Westminster, London', 'lat': 51.5010, 'lon': -0.1260,
         'ds': '1658-01-01', 'de': '1660-07-03', 'prec': 'year',
         'dd': '1658 - 1660', 'desc': 'Lived with wife Elizabeth in lodgings at Axe Yard; began his famous diary on January 1, 1660',
         'conf': 'certain'},
        {'place': 'HMS Swiftsure, English Channel', 'lat': 50.8000, 'lon': 0.5000,
         'ds': '1660-03-23', 'de': '1660-03-29', 'prec': 'day',
         'dd': 'March 23-29, 1660', 'desc': 'Went aboard the Swiftsure with Edward Montagu to join the fleet',
         'conf': 'certain'},
        {'place': 'HMS Naseby, North Sea', 'lat': 51.5000, 'lon': 1.5000,
         'ds': '1660-03-30', 'de': '1660-05-22', 'prec': 'day',
         'dd': 'March 30 - May 22, 1660', 'desc': 'Transferred to the Naseby; sailed to Holland to bring back King Charles II',
         'conf': 'certain'},
        {'place': 'Scheveningen, Holland', 'lat': 52.1072, 'lon': 4.2703,
         'ds': '1660-05-14', 'de': '1660-05-23', 'prec': 'day',
         'dd': 'May 14-23, 1660', 'desc': 'Arrived in Holland; Charles II boarded the fleet for the Restoration voyage',
         'conf': 'certain'},
        {'place': 'Dover, England', 'lat': 51.1295, 'lon': 1.3089,
         'ds': '1660-05-25', 'de': '1660-05-26', 'prec': 'day',
         'dd': 'May 25-26, 1660', 'desc': 'Charles II landed at Dover; Pepys witnessed the Restoration arrival',
         'conf': 'certain'},
        {'place': 'Navy Office, Seething Lane, London', 'lat': 51.5110, 'lon': -0.0779,
         'ds': '1660-07-04', 'de': '1673-12-31', 'prec': 'year',
         'dd': '1660 - 1673', 'desc': 'Took up residence and office as Clerk of the Acts at the Navy Office; wrote most of his diary here',
         'conf': 'certain'},
        {'place': 'Portsmouth, England', 'lat': 50.8198, 'lon': -1.0880,
         'ds': '1662-04-01', 'de': '1662-04-30', 'prec': 'month',
         'dd': 'April 1662', 'desc': 'Official visit to Portsmouth Dockyard; made a burgess of the town',
         'conf': 'certain'},
        {'place': 'Greenwich, London', 'lat': 51.4769, 'lon': -0.0005,
         'ds': '1665-07-01', 'de': '1666-01-31', 'prec': 'month',
         'dd': 'July 1665 - January 1666', 'desc': 'Moved Navy Office operations to Greenwich during the Great Plague of London',
         'conf': 'certain'},
        {'place': 'City of London', 'lat': 51.5155, 'lon': -0.0922,
         'ds': '1666-09-02', 'de': '1666-09-05', 'prec': 'day',
         'dd': 'September 2-5, 1666', 'desc': 'Witnessed the Great Fire of London; famously buried his wine and Parmesan cheese to save them',
         'conf': 'certain'},
        {'place': 'Derby House, Westminster, London', 'lat': 51.4995, 'lon': -0.1248,
         'ds': '1673-06-01', 'de': '1679-05-31', 'prec': 'year',
         'dd': '1673 - 1679', 'desc': 'Served as Secretary to the Admiralty Commission at Derby House',
         'conf': 'certain'},
        {'place': 'York Buildings, London', 'lat': 51.5088, 'lon': -0.1224,
         'ds': '1679-06-01', 'de': '1703-05-26', 'prec': 'year',
         'dd': '1679 - 1703', 'desc': 'Final residence in retirement; died here on May 26, 1703',
         'conf': 'certain'},
    ]

    insert_person(db, person, whereabouts, 'https://www.gutenberg.org/ebooks/4200')


def add_cook(db):
    """Captain James Cook - from Journal of First Voyage (Project Gutenberg #8106)."""
    print("\nCaptain James Cook (from Journal, Gutenberg #8106)")

    person = {
        'name': 'James Cook',
        'birth_start': '1728-11-07', 'birth_end': '1728-11-07', 'birth_display': 'November 7, 1728',
        'death_start': '1779-02-14', 'death_end': '1779-02-14', 'death_display': 'February 14, 1779',
        'description': 'British explorer, navigator, and cartographer. Made three voyages to the Pacific Ocean, during which he made the first European contact with the eastern coastline of Australia and the Hawaiian Islands.',
        'wikipedia_url': 'https://en.wikipedia.org/wiki/James_Cook',
    }

    whereabouts = [
        {'place': 'Marton, Yorkshire, England', 'lat': 54.5466, 'lon': -1.2100,
         'ds': '1728-11-07', 'de': '1745-12-31', 'prec': 'year',
         'dd': '1728 - 1745', 'desc': 'Born in Marton; grew up in Great Ayton; early education and farm work',
         'conf': 'certain'},
        {'place': 'Whitby, Yorkshire, England', 'lat': 54.4858, 'lon': -0.6206,
         'ds': '1746-01-01', 'de': '1755-06-16', 'prec': 'year',
         'dd': '1746 - 1755', 'desc': 'Apprenticed to ship-owners in Whitby; learned seamanship on coal trade vessels in the North Sea',
         'conf': 'certain'},
        {'place': 'Deptford, London, England', 'lat': 51.4791, 'lon': -0.0276,
         'ds': '1768-05-01', 'de': '1768-07-30', 'prec': 'month',
         'dd': 'May - July 1768', 'desc': 'HMS Endeavour fitted out at Deptford dockyard for the first voyage',
         'conf': 'certain'},
        {'place': 'Plymouth, England', 'lat': 50.3755, 'lon': -4.1427,
         'ds': '1768-08-14', 'de': '1768-08-26', 'prec': 'day',
         'dd': 'August 14-26, 1768', 'desc': 'Final departure point; Joseph Banks and scientific staff boarded',
         'conf': 'certain'},
        {'place': 'Funchal, Madeira', 'lat': 32.6669, 'lon': -16.9241,
         'ds': '1768-09-13', 'de': '1768-09-18', 'prec': 'day',
         'dd': 'September 13-18, 1768', 'desc': 'First port of call; took on fresh provisions and wine',
         'conf': 'certain'},
        {'place': 'Rio de Janeiro, Brazil', 'lat': -22.9068, 'lon': -43.1729,
         'ds': '1768-11-13', 'de': '1768-12-07', 'prec': 'day',
         'dd': 'November 13 - December 7, 1768', 'desc': 'Port call; difficulties with Portuguese authorities who were suspicious of the expedition',
         'conf': 'certain'},
        {'place': 'Bay of Good Success, Tierra del Fuego', 'lat': -54.8000, 'lon': -65.2000,
         'ds': '1769-01-15', 'de': '1769-01-21', 'prec': 'day',
         'dd': 'January 15-21, 1769', 'desc': 'Stopped to gather wood and water before rounding Cape Horn; encountered Fuegian natives',
         'conf': 'certain'},
        {'place': 'Cape Horn', 'lat': -55.9789, 'lon': -67.2743,
         'ds': '1769-01-25', 'de': '1769-01-27', 'prec': 'day',
         'dd': 'January 25-27, 1769', 'desc': 'Successfully rounded Cape Horn into the Pacific Ocean',
         'conf': 'certain'},
        {'place': 'Matavai Bay, Tahiti', 'lat': -17.5000, 'lon': -149.5000,
         'ds': '1769-04-13', 'de': '1769-07-13', 'prec': 'day',
         'dd': 'April 13 - July 13, 1769', 'desc': 'Primary mission: observed the Transit of Venus on June 3, 1769; built Fort Venus; extensive contact with Tahitians',
         'conf': 'certain'},
        {'place': 'Society Islands', 'lat': -16.5000, 'lon': -151.7500,
         'ds': '1769-07-15', 'de': '1769-08-09', 'prec': 'day',
         'dd': 'July 15 - August 9, 1769', 'desc': 'Explored and charted Huahine, Raiatea, and Bora Bora; Cook named them the Society Islands',
         'conf': 'certain'},
        {'place': 'Poverty Bay, New Zealand', 'lat': -38.6840, 'lon': 178.0170,
         'ds': '1769-10-07', 'de': '1769-10-11', 'prec': 'day',
         'dd': 'October 7-11, 1769', 'desc': 'First European landing in New Zealand; named Poverty Bay after failing to obtain supplies; first encounters with Maori',
         'conf': 'certain'},
        {'place': 'Queen Charlotte Sound, New Zealand', 'lat': -41.1000, 'lon': 174.2500,
         'ds': '1770-01-15', 'de': '1770-02-06', 'prec': 'day',
         'dd': 'January 15 - February 6, 1770', 'desc': 'Anchored in Ship Cove; careened and repaired the Endeavour; observed that New Zealand was two islands',
         'conf': 'certain'},
        {'place': 'Botany Bay, Australia', 'lat': -34.0116, 'lon': 151.2313,
         'ds': '1770-04-29', 'de': '1770-05-06', 'prec': 'day',
         'dd': 'April 29 - May 6, 1770', 'desc': 'First landing on the east coast of Australia; Banks collected many plant specimens, inspiring the name Botany Bay',
         'conf': 'certain'},
        {'place': 'Endeavour River, Queensland, Australia', 'lat': -15.4400, 'lon': 145.2500,
         'ds': '1770-06-17', 'de': '1770-08-04', 'prec': 'day',
         'dd': 'June 17 - August 4, 1770', 'desc': 'Beached the Endeavour for repairs after striking the Great Barrier Reef; first European encounter with a kangaroo',
         'conf': 'certain'},
        {'place': 'Possession Island, Torres Strait', 'lat': -10.7300, 'lon': 142.3900,
         'ds': '1770-08-22', 'de': '1770-08-23', 'prec': 'day',
         'dd': 'August 22, 1770', 'desc': 'Cook claimed the entire east coast of Australia for Britain, naming it New South Wales',
         'conf': 'certain'},
        {'place': 'Batavia (Jakarta), Java', 'lat': -6.2088, 'lon': 106.8456,
         'ds': '1770-10-10', 'de': '1770-12-26', 'prec': 'day',
         'dd': 'October 10 - December 26, 1770', 'desc': 'Extended stay for major ship repairs; crew devastated by malaria and dysentery; seven men died',
         'conf': 'certain'},
        {'place': 'Cape of Good Hope, South Africa', 'lat': -34.3568, 'lon': 18.4741,
         'ds': '1771-03-14', 'de': '1771-04-14', 'prec': 'day',
         'dd': 'March 14 - April 14, 1771', 'desc': 'Resupply stop; more crew members died from illness contracted in Batavia',
         'conf': 'certain'},
        {'place': 'Deal, Kent, England', 'lat': 51.2225, 'lon': 1.3955,
         'ds': '1771-07-12', 'de': '1771-07-13', 'prec': 'day',
         'dd': 'July 12, 1771', 'desc': 'Arrived home after nearly three years; completed first circumnavigation voyage',
         'conf': 'certain'},
        {'place': 'Kealakekua Bay, Hawaii', 'lat': 19.4783, 'lon': -155.9319,
         'ds': '1779-01-17', 'de': '1779-02-14', 'prec': 'day',
         'dd': 'January 17 - February 14, 1779', 'desc': 'Third voyage; initially welcomed by Hawaiians. Killed in a violent confrontation on February 14, 1779',
         'conf': 'certain'},
    ]

    insert_person(db, person, whereabouts, 'https://www.gutenberg.org/ebooks/8106')


def main():
    db = get_db()
    add_pepys(db)
    add_cook(db)
    db.commit()
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
