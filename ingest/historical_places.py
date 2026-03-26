"""Historical place name → modern coordinates lookup.

Nominatim often maps historical place names to wrong-continent US/Australian
towns with the same name (Athens → Georgia, Damascus → Oregon, Carthage → Texas,
Prussia → Iowa, etc.). This dictionary provides correct coordinates as a
fallback when Nominatim returns a clearly wrong result or can't find the place.

Each key is lowercase. Values are [lat, lon].
"""

HISTORICAL_PLACES = {
    # === ANCIENT GREEK ===
    'athens': [37.98, 23.73],
    'athens in': [37.98, 23.73],
    'pella': [40.76, 22.52],
    'pella, macedon': [40.76, 22.52],
    'macedon': [40.6, 22.3],
    'macedonia': [41.0, 21.8],
    'thessalonica': [40.64, 22.94],
    'megara': [38.0, 23.35],
    'mytilene': [39.1, 26.55],
    'thebes': [38.32, 23.32],
    'corinth': [37.91, 22.88],
    'sparta': [37.08, 22.43],
    'delphi': [38.48, 22.5],
    'olympia': [37.64, 21.63],
    'ephesus': [37.94, 27.34],
    'miletus': [37.53, 27.28],
    'pergamon': [39.13, 27.18],
    'halicarnassus': [37.04, 27.42],
    'troy': [39.96, 26.24],
    'thrace': [41.5, 25.5],
    'lesbos': [39.17, 26.33],
    'samos': [37.75, 26.97],
    'arcadia': [37.5, 22.3],
    'syracuse': [37.07, 15.29],

    # === ANCIENT ROMAN ===
    'actium': [38.95, 20.72],
    'arpinum': [41.65, 13.61],
    'brundisium': [40.64, 17.94],
    'cannae': [41.3, 15.97],
    'carthage': [36.86, 10.32],
    'cilicia': [37.0, 35.0],
    'bithynia': [40.5, 29.5],
    'cappadocia': [38.7, 35.5],
    'pontus': [40.8, 37.5],
    'lydia': [38.5, 28.0],
    'phrygia': [39.0, 30.0],
    'ionia': [38.3, 27.0],
    'caria': [37.2, 28.3],
    'lycia': [36.5, 29.8],
    'pannonia': [47.0, 18.0],
    'dacia': [46.0, 24.0],
    'dalmatia': [43.5, 16.5],
    'noricum': [47.0, 14.0],
    'raetia': [47.0, 10.5],
    'gaul': [46.6, 1.9],
    'lusitania': [39.5, -8.0],
    'numidia': [36.0, 6.0],
    'cyrenaica': [32.0, 21.0],
    'mauretania': [35.0, -2.0],
    'alba longa': [41.75, 12.65],
    'zama': [36.3, 9.4],
    'asia minor': [39.0, 32.0],
    'anatolia': [39.0, 32.0],

    # === ANCIENT NEAR EAST / PERSIA ===
    'babylon': [32.54, 44.42],
    'mesopotamia': [33.0, 44.0],
    'nineveh': [36.36, 43.15],
    'persepolis': [29.93, 52.89],
    'susa': [32.19, 48.26],
    'antioch': [36.2, 36.15],
    'tyre': [33.27, 35.2],
    'sidon': [33.56, 35.37],

    # === BYZANTINE / MEDIEVAL ===
    'byzantium': [41.01, 28.98],
    'constantinople': [41.01, 28.98],
    'nicaea': [40.43, 29.72],
    'edessa': [37.16, 38.79],
    'acre': [32.92, 35.07],
    'outremer': [32.5, 35.5],

    # === MEDIEVAL EUROPE ===
    'aachen': [50.78, 6.08],
    'lotharingia': [49.0, 6.5],
    'aquitaine': [44.25, -0.18],
    'burgundy': [47.3, 4.4],
    'navarre': [42.7, -1.65],
    'aragon': [41.38, -0.76],
    'castile': [39.5, -3.5],
    'granada': [37.17, -3.6],
    'flanders': [51.04, 4.24],
    'brabant': [50.85, 4.35],
    'savoy': [45.49, 6.38],
    'piedmont': [45.06, 7.92],
    'lombardy': [45.57, 9.77],
    'tuscany': [43.4, 11.2],
    'romagna': [44.25, 11.77],

    # === GERMAN HISTORICAL TERRITORIES ===
    'prussia': [52.5, 13.4],
    'kingdom of prussia': [52.5, 13.4],
    'east prussia': [54.7, 20.5],
    'saxony': [51.0, 13.5],
    'silesia': [50.9, 17.0],
    'bohemia': [49.8, 15.5],
    'moravia': [49.2, 16.6],
    'westphalia': [51.8, 8.4],
    'rhineland': [50.9, 6.9],
    'alsace': [48.5, 7.5],
    'lorraine': [48.7, 6.2],
    'franconia': [49.8, 10.5],
    'swabia': [48.15, 10.47],
    'thuringia': [50.9, 11.0],
    'pomerania': [53.77, 15.5],
    'holstein': [54.1, 9.7],
    'german empire': [51.0, 10.0],

    # === RUSSIAN HISTORICAL ===
    'muscovy': [55.75, 37.62],
    'livonia': [57.0, 24.5],
    'courland': [56.8, 22.5],
    'soviet union': [55.75, 37.62],
    'petrograd': [59.96, 30.16],
    'leningrad': [59.96, 30.16],
    'stalingrad': [48.71, 44.52],
    'konigsberg': [54.71, 20.51],

    # === BALKANS / CENTRAL EUROPE ===
    'transylvania': [46.5, 24.5],
    'wallachia': [44.5, 26.0],
    'moldavia': [47.3, 28.8],
    'bessarabia': [47.0, 28.8],
    'yugoslavia': [44.0, 20.5],

    # === MIDDLE EAST / NORTH AFRICA ===
    'palestine': [31.9, 35.2],
    'bethlehem': [31.7, 35.2],
    'damascus': [33.51, 36.31],
    'medina': [24.47, 39.61],
    'kingdom of armenia': [40.0, 44.0],
    'levant': [33.0, 36.0],

    # === CENTRAL ASIAN / MONGOL / TIMURID ===
    'transoxiana': [39.65, 66.96],
    'khwarazm': [41.55, 60.63],
    'khwarazmia': [41.55, 60.63],
    'khorasan': [35.0, 59.0],
    'karakorum': [47.2, 102.8],
    'gurganj': [42.3, 59.15],
    'gurganj, turkmenistan': [42.3, 59.15],
    'wakhsh': [37.8, 69.0],
    'wakhsh, tajikistan': [37.8, 69.0],

    # === SOUTH / SOUTHEAST ASIAN HISTORICAL ===
    'malabar': [10.5, 76.0],
    'bengal': [23.0, 88.0],
    'punjab': [30.9, 75.5],
    'hindustan': [25.0, 82.0],
    'ceylon': [7.0, 80.0],
    'siam': [13.75, 100.5],
    'cochinchina': [11.0, 107.0],

    # === COLONIAL ERA ===
    'batavia': [-6.17, 106.83],
    'amboina': [-3.7, 128.18],
    'amboina, indonesia': [-3.7, 128.18],
    'formosa': [23.7, 121.0],
    'new spain': [19.4, -99.1],
    'edo': [35.68, 139.77],
    'peking': [39.91, 116.39],
    'canton': [23.13, 113.26],
    'madras': [13.08, 80.28],
    'calcutta': [22.57, 88.36],
    'smyrna': [38.42, 27.14],
    'adrianople': [41.68, 26.56],
    'danzig': [54.35, 18.65],
    'breslau': [51.1, 17.04],
    'lemberg': [49.84, 24.03],
    'pressburg': [48.15, 17.11],
    'christiania': [59.91, 10.75],

    # === NOTABLE LANDMARKS / BUILDINGS ===
    'notre-dame': [48.853, 2.349],
    'whitehall palace': [51.504, -0.126],
    'the rhine': [50.47, 7.35],
    'rhine': [50.47, 7.35],

    # === AFRICAN HISTORICAL ===
    'abyssinia': [9.0, 39.0],
    'taghaza': [23.7, -4.0],
    'transvaal': [-25.7, 28.2],

    # === GEORGIA (COUNTRY vs US STATE) ===
    # NOTE: Only used when context clearly indicates the Caucasus country.
    # Handled specially in code, not here, since "Georgia" is ambiguous.
}
