"""Insert Ernst Jünger from Storm of Steel (Project Gutenberg #34099)."""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ingest.gutenberg_diaries import get_db, insert_person


def add_junger(db):
    """Ernst Jünger - from In Stahlgewittern / Storm of Steel (Gutenberg #34099)."""
    print("\nErnst Jünger (from Storm of Steel, Gutenberg #34099)")

    person = {
        'name': 'Ernst Jünger',
        'birth_start': '1895-03-29', 'birth_end': '1895-03-29', 'birth_display': 'March 29, 1895',
        'death_start': '1998-02-17', 'death_end': '1998-02-17', 'death_display': 'February 17, 1998',
        'description': 'German author, soldier, and entomologist. His WWI diary "In Stahlgewittern" (Storm of Steel) is one of the most detailed first-person accounts of trench warfare. Served as a junior officer on the Western Front from 1914 to 1918, wounded 14 times.',
        'wikipedia_url': 'https://en.wikipedia.org/wiki/Ernst_J%C3%BCnger',
    }

    whereabouts = [
        {'place': 'Heidelberg, Germany', 'lat': 49.3988, 'lon': 8.6724,
         'ds': '1895-03-29', 'de': '1907-12-31', 'prec': 'year',
         'dd': '1895 - 1907', 'desc': 'Born in Heidelberg; early childhood',
         'conf': 'certain'},
        {'place': 'Hannover, Germany', 'lat': 52.3759, 'lon': 9.7320,
         'ds': '1907-01-01', 'de': '1913-12-31', 'prec': 'year',
         'dd': '1907 - 1913', 'desc': 'School years in Hannover; grew restless and yearned for adventure',
         'conf': 'probable'},
        {'place': 'Sidi Bel Abbes, Algeria', 'lat': 34.8400, 'lon': -0.6390,
         'ds': '1913-10-01', 'de': '1913-11-30', 'prec': 'month',
         'dd': 'October - November 1913', 'desc': 'Briefly enlisted in the French Foreign Legion as a teenager; father secured his release',
         'conf': 'certain'},
        {'place': 'Bazancourt, Champagne, France', 'lat': 49.3639, 'lon': 3.9942,
         'ds': '1914-12-27', 'de': '1914-12-31', 'prec': 'day',
         'dd': 'December 27, 1914', 'desc': 'Arrived by train; first deployment to the front with Füsilier Regiment 73',
         'conf': 'certain'},
        {'place': 'Orainville, France', 'lat': 49.3700, 'lon': 3.9600,
         'ds': '1915-01-01', 'de': '1915-02-28', 'prec': 'month',
         'dd': 'January - February 1915', 'desc': 'Reserve position; experienced first artillery strike that killed 13 soldiers; early introduction to trench warfare',
         'conf': 'certain'},
        {'place': 'Recouvrence, France', 'lat': 49.4000, 'lon': 3.8800,
         'ds': '1915-02-15', 'de': '1915-03-15', 'prec': 'month',
         'dd': 'February - March 1915', 'desc': 'Attended officer-aspirant training course; promoted to Fähnrich (officer cadet)',
         'conf': 'certain'},
        {'place': 'Les Éparges, France', 'lat': 49.0700, 'lon': 5.6100,
         'ds': '1915-04-23', 'de': '1915-04-25', 'prec': 'day',
         'dd': 'April 23-25, 1915', 'desc': 'First major battle; received leg wound from shrapnel. Baptism of fire in fierce fighting for the hilltop position',
         'conf': 'certain'},
        {'place': 'Heidelberg, Germany', 'lat': 49.3988, 'lon': 8.6724,
         'ds': '1915-05-01', 'de': '1915-06-30', 'prec': 'month',
         'dd': 'May - June 1915', 'desc': 'Hospital stay recovering from Les Éparges wound',
         'conf': 'certain'},
        {'place': 'Douchy-lès-Ayette, France', 'lat': 50.1200, 'lon': 2.6900,
         'ds': '1915-09-01', 'de': '1915-10-31', 'prec': 'month',
         'dd': 'September - October 1915', 'desc': 'Regimental rest village in Artois; regular rotation point between front and rear areas',
         'conf': 'certain'},
        {'place': 'Monchy-au-Bois, France', 'lat': 50.1400, 'lon': 2.6500,
         'ds': '1915-11-01', 'de': '1916-04-15', 'prec': 'month',
         'dd': 'November 1915 - April 1916', 'desc': 'Commanded Section C of the trench line; constant defensive operations, patrols, and sniping duels',
         'conf': 'certain'},
        {'place': 'Guillemont, Somme, France', 'lat': 49.9900, 'lon': 2.8200,
         'ds': '1916-08-23', 'de': '1916-09-03', 'prec': 'day',
         'dd': 'August 23 - September 3, 1916', 'desc': 'Battle of the Somme; fierce fighting at Guillemont; witnessed devastating British artillery barrages',
         'conf': 'certain'},
        {'place': 'Combles, Somme, France', 'lat': 49.9700, 'lon': 2.8500,
         'ds': '1916-09-03', 'de': '1916-09-15', 'prec': 'day',
         'dd': 'September 3-15, 1916', 'desc': 'Continued Somme fighting near Combles; wounded again',
         'conf': 'probable'},
        {'place': 'Langemarck, Belgium', 'lat': 50.9200, 'lon': 2.9200,
         'ds': '1917-07-31', 'de': '1917-08-15', 'prec': 'day',
         'dd': 'July 31 - August 15, 1917', 'desc': 'Battle of Langemarck during Third Ypres; heavy British offensive; Jünger wounded in the head',
         'conf': 'certain'},
        {'place': 'Cambrai, France', 'lat': 50.1764, 'lon': 3.2365,
         'ds': '1917-11-20', 'de': '1917-12-07', 'prec': 'day',
         'dd': 'November 20 - December 7, 1917', 'desc': 'Battle of Cambrai; first mass tank attack in history; German counter-attack recaptured lost ground',
         'conf': 'probable'},
        {'place': 'Near Vraucourt, France', 'lat': 50.1100, 'lon': 2.9200,
         'ds': '1918-03-21', 'de': '1918-03-28', 'prec': 'day',
         'dd': 'March 21-28, 1918', 'desc': 'German Spring Offensive (Operation Michael); led assault troops; awarded Pour le Mérite for bravery',
         'conf': 'certain'},
        {'place': 'Near Favreuil, France', 'lat': 50.1000, 'lon': 2.8600,
         'ds': '1918-08-25', 'de': '1918-08-25', 'prec': 'day',
         'dd': 'August 25, 1918', 'desc': 'Received his 14th and final wound (shot through the chest); carried from the battlefield; war ended during his recovery',
         'conf': 'certain'},
        {'place': 'Hannover, Germany', 'lat': 52.3759, 'lon': 9.7320,
         'ds': '1918-09-01', 'de': '1918-11-11', 'prec': 'month',
         'dd': 'September - November 1918', 'desc': 'Recuperated from chest wound; the armistice was signed while he was still recovering',
         'conf': 'probable'},
    ]

    insert_person(db, person, whereabouts, 'https://www.gutenberg.org/ebooks/34099')


def main():
    db = get_db()
    add_junger(db)
    db.commit()
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
