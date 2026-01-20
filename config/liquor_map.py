# config/liquor_map.py
# Maps Sales Mix liquor names to inventory items

# Format: "Sales Mix Pattern": "Inventory Item Name"
LIQUOR_MAP = {
    # ============ WHISKEY ============
    "Buffalo Trace": "WHISKEY Buffalo Trace",
    "Trace": "WHISKEY Buffalo Trace",

    "Bulleit Rye": "WHISKEY Bulleit Straight Rye",
    "Bulleit": "WHISKEY Bulleit Straight Rye",
    "Bulliet Rye": "WHISKEY Bulleit Straight Rye",  # Common misspelling
    "Bulliet": "WHISKEY Bulleit Straight Rye",  # Common misspelling

    "Crown Royal": "WHISKEY Crown Royal",
    "Crown": "WHISKEY Crown Royal",

    "Crown Apple": "WHISKEY Crown Royal Regal Apple",
    "Regal Apple": "WHISKEY Crown Royal Regal Apple",

    "Fireball": "WHISKEY Fireball Cinnamon",

    "Jack Daniels": "WHISKEY Jack Daniels Black",
    "Jack Daniel": "WHISKEY Jack Daniels Black",

    "Jack Fire": "WHISKEY Jack Daniels Tennessee Fire",
    "Tennessee Fire": "WHISKEY Jack Daniels Tennessee Fire",

    "Jameson": "WHISKEY Jameson",

    "Jim Beam": "WHISKEY Jim Beam",

    "Makers Mark": "WHISKEY Makers Mark",
    "Maker's Mark": "WHISKEY Makers Mark",

    "Screwball": "WHISKEY Skrewball Peanut Butter",
    "Skrewball": "WHISKEY Skrewball Peanut Butter",

    "Four Roses": "WHISKEY Four Roses",

    "Basil Hayden": "WHISKEY Basil Hayden",

    "Well Whiskey": "WHISKEY Well",

    "Dewars": "WHISKEY Dewars White Label",
    "Dewar's": "WHISKEY Dewars White Label",

    "Glenlivet": "WHISKEY Glenlivet",

    "Well Brandy": "BRANDY Well",

    # ============ VODKA ============
    "Deep Eddy Lime": "VODKA Deep Eddy Lime",
    "Deep Eddy Orange": "VODKA Deep Eddy Orange",
    "Deep Eddy Grapefruit": "VODKA Deep Eddy Ruby Red",
    "Deep Eddy Ruby Red": "VODKA Deep Eddy Ruby Red",

    "Grey Goose": "VODKA Grey Goose",

    "Ketel One": "VODKA Ketel One",
    "Ketel": "VODKA Ketel One",

    "Titos": "VODKA Titos",
    "Tito's": "VODKA Titos",

    "Well Vodka": "VODKA Well",

    "Western Son Blueberry": "VODKA Western Son Blueberry",
    "Western Son Lemon": "VODKA Western Son Lemon",
    "Western Son Raspberry": "VODKA Western Son Raspberry",
    "Western Son Raspberry (FS)": "VODKA Western Son Raspberry",
    "Western Son Prickly Pear": "VODKA Western Son Prickly Pear",
    "Western Son Original": "VODKA Western Son Original",
    "Western Son": "VODKA Western Son Original",
    "Western Son (FS)": "VODKA Western Son Original",

    "Fleischmann's Cherry": "VODKA Fleischmann's Cherry",
    "Fleischmanns Cherry": "VODKA Fleischmann's Cherry",
    "Cherry Vodka": "VODKA Fleischmann's Cherry",

    "Fleischmann's Grape": "VODKA Fleischmann's Grape",
    "Fleischmanns Grape": "VODKA Fleischmann's Grape",
    "Grape Vodka": "VODKA Fleischmann's Grape",

    # Note: Vanilla vodka is 86'd - flag if seen in sales

    # ============ GIN ============
    "Hendricks": "GIN Hendricks",
    "Hendrick's": "GIN Hendricks",

    "Tanqueray": "GIN Tanqueray",

    "Well Gin": "GIN Well",

    # ============ TEQUILA ============
    "Casamigos Silver": "TEQUILA Casamigos Blanco",
    "Casamigos": "TEQUILA Casamigos Blanco",

    "Cazadores Repo": "TEQUILA Cazadores Reposado",
    "Cazadores": "TEQUILA Cazadores Reposado",

    "Corazon Repo": "TEQUILA Corazon Reposado",
    "Corazon": "TEQUILA Corazon Reposado",

    "Don Julio": "TEQUILA Don Julio Blanco",

    "Milagro Anejo": "TEQUILA Milagro Anejo",
    "Milagro Reposado": "TEQUILA Milagro Reposado",
    "Milagro Silver": "TEQUILA Milagro Silver",
    "Milagro": "TEQUILA Milagro Silver",  # Default to silver

    "Patron Silver": "TEQUILA Patron Silver",
    "Patron": "TEQUILA Patron Silver",

    "Well Tequila": "TEQUILA Well",

    # ============ RUM ============
    "Bacardi": "RUM Bacardi Superior White",

    "Captain Morgan": "RUM Captain Morgan Spiced",
    "Captain": "RUM Captain Morgan Spiced",

    "Malibu": "RUM Malibu Coconut",

    "Well Rum": "RUM Well",

    # ============ SCOTCH ============
    "Well Scotch": "SCOTCH Well",

    # ============ LIQUEURS ============
    "Amaretto": "LIQ Amaretto",

    "Baileys": "LIQ Baileys Irish Cream",
    "Bailey's": "LIQ Baileys Irish Cream",

    "Chambord": "LIQ Chambord",

    "Grand Marnier": "LIQ Grand Marnier",
    "Gran Mar": "LIQ Grand Marnier",

    "Jagermeister": "LIQ Jagermeister",
    "Jägermeister": "LIQ Jagermeister",
    "Jaeger": "LIQ Jagermeister",
    "Jager": "LIQ Jagermeister",

    "Kahlua": "LIQ Kahlua",

    "Melon": "LIQ Melon",
    "Midori": "LIQ Melon",

    "Rumplemintz": "LIQ Rumpleminze",
    "Rumpleminze": "LIQ Rumpleminze",

    "Triple Sec": "LIQ Triple Sec",

    "Blue Curacao": "LIQ Blue Curacao",

    "Butterscotch": "LIQ Butterscotch",

    "Peach Schnapps": "LIQ Peach Schnapps",
    "Peach": "LIQ Peach Schnapps",

    "Sour Apple": "LIQ Sour Apple",
    "Apple Schnapps": "LIQ Sour Apple",

    "Watermelon Schnapps": "LIQ Watermelon Schnapps",
    "Watermelon": "LIQ Watermelon Schnapps",

    # ============ VERMOUTH ============
    "Vermouth Dry": "LIQ Vermouth Dry",
    "Dry Vermouth": "LIQ Vermouth Dry",

    "Vermouth Sweet": "LIQ Vermouth Sweet",
    "Sweet Vermouth": "LIQ Vermouth Sweet",
}
