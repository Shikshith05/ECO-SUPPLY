"""
English display names for DataCo's Order_Country values, which are in Spanish
("Estados Unidos", "Alemania", ...). The model and dataset keep the original
values; the UI shows English names and the API accepts either.
"""

SPANISH_TO_ENGLISH = {
    "Afganistán": "Afghanistan", "Albania": "Albania", "Alemania": "Germany", "Angola": "Angola",
    "Arabia Saudí": "Saudi Arabia", "Argelia": "Algeria", "Argentina": "Argentina", "Armenia": "Armenia",
    "Australia": "Australia", "Austria": "Austria", "Azerbaiyán": "Azerbaijan", "Bangladés": "Bangladesh",
    "Barbados": "Barbados", "Baréin": "Bahrain", "Belice": "Belize", "Benín": "Benin",
    "Bielorrusia": "Belarus", "Bolivia": "Bolivia", "Bosnia y Herzegovina": "Bosnia and Herzegovina",
    "Botsuana": "Botswana", "Brasil": "Brazil", "Bulgaria": "Bulgaria", "Burkina Faso": "Burkina Faso",
    "Burundi": "Burundi", "Bután": "Bhutan", "Bélgica": "Belgium", "Camboya": "Cambodia",
    "Camerún": "Cameroon", "Canada": "Canada", "Chad": "Chad", "Chile": "Chile", "China": "China",
    "Chipre": "Cyprus", "Colombia": "Colombia", "Corea del Sur": "South Korea", "Costa Rica": "Costa Rica",
    "Costa de Marfil": "Côte d'Ivoire", "Croacia": "Croatia", "Cuba": "Cuba", "Dinamarca": "Denmark",
    "Ecuador": "Ecuador", "Egipto": "Egypt", "El Salvador": "El Salvador",
    "Emiratos Árabes Unidos": "United Arab Emirates", "Eritrea": "Eritrea", "Eslovaquia": "Slovakia",
    "Eslovenia": "Slovenia", "España": "Spain", "Estados Unidos": "United States", "Estonia": "Estonia",
    "Etiopía": "Ethiopia", "Filipinas": "Philippines", "Finlandia": "Finland", "Francia": "France",
    "Gabón": "Gabon", "Georgia": "Georgia", "Ghana": "Ghana", "Grecia": "Greece",
    "Guadalupe": "Guadeloupe", "Guatemala": "Guatemala", "Guayana Francesa": "French Guiana",
    "Guinea": "Guinea", "Guinea Ecuatorial": "Equatorial Guinea", "Guinea-Bissau": "Guinea-Bissau",
    "Guyana": "Guyana", "Haití": "Haiti", "Honduras": "Honduras", "Hong Kong": "Hong Kong",
    "Hungría": "Hungary", "India": "India", "Indonesia": "Indonesia", "Irak": "Iraq",
    "Irlanda": "Ireland", "Irán": "Iran", "Israel": "Israel", "Italia": "Italy", "Jamaica": "Jamaica",
    "Japón": "Japan", "Jordania": "Jordan", "Kazajistán": "Kazakhstan", "Kenia": "Kenya",
    "Kirguistán": "Kyrgyzstan", "Kuwait": "Kuwait", "Laos": "Laos", "Lesoto": "Lesotho",
    "Liberia": "Liberia", "Libia": "Libya", "Lituania": "Lithuania", "Luxemburgo": "Luxembourg",
    "Líbano": "Lebanon", "Macedonia": "North Macedonia", "Madagascar": "Madagascar",
    "Malasia": "Malaysia", "Mali": "Mali", "Marruecos": "Morocco", "Martinica": "Martinique",
    "Mauritania": "Mauritania", "Moldavia": "Moldova", "Mongolia": "Mongolia", "Montenegro": "Montenegro",
    "Mozambique": "Mozambique", "Myanmar (Birmania)": "Myanmar (Burma)", "México": "Mexico",
    "Namibia": "Namibia", "Nepal": "Nepal", "Nicaragua": "Nicaragua", "Nigeria": "Nigeria",
    "Noruega": "Norway", "Nueva Zelanda": "New Zealand", "Níger": "Niger", "Omán": "Oman",
    "Pakistán": "Pakistan", "Panamá": "Panama", "Papúa Nueva Guinea": "Papua New Guinea",
    "Paraguay": "Paraguay", "Países Bajos": "Netherlands", "Perú": "Peru", "Polonia": "Poland",
    "Portugal": "Portugal", "Qatar": "Qatar", "Reino Unido": "United Kingdom",
    "República Centroafricana": "Central African Republic", "República Checa": "Czech Republic",
    "República Democrática del Congo": "Democratic Republic of the Congo",
    "República Dominicana": "Dominican Republic", "República de Gambia": "The Gambia",
    "República del Congo": "Republic of the Congo", "Ruanda": "Rwanda", "Rumania": "Romania",
    "Rusia": "Russia", "Senegal": "Senegal", "Serbia": "Serbia", "Sierra Leona": "Sierra Leone",
    "Singapur": "Singapore", "Siria": "Syria", "Somalia": "Somalia", "Sri Lanka": "Sri Lanka",
    "Suazilandia": "Eswatini (Swaziland)", "SudAfrica": "South Africa", "Sudán": "Sudan",
    "Sudán del Sur": "South Sudan", "Suecia": "Sweden", "Suiza": "Switzerland", "Surinam": "Suriname",
    "Sáhara Occidental": "Western Sahara", "Tailandia": "Thailand", "Taiwán": "Taiwan",
    "Tanzania": "Tanzania", "Tayikistán": "Tajikistan", "Togo": "Togo",
    "Trinidad y Tobago": "Trinidad and Tobago", "Turkmenistán": "Turkmenistan", "Turquía": "Turkey",
    "Túnez": "Tunisia", "Ucrania": "Ukraine", "Uganda": "Uganda", "Uruguay": "Uruguay",
    "Uzbekistán": "Uzbekistan", "Venezuela": "Venezuela", "Vietnam": "Vietnam", "Yemen": "Yemen",
    "Yibuti": "Djibouti", "Zambia": "Zambia", "Zimbabue": "Zimbabwe",
}

ENGLISH_TO_SPANISH = {en.lower(): es for es, en in SPANISH_TO_ENGLISH.items()}


def to_english(name: str) -> str:
    """English display name; unknown values are returned unchanged."""
    return SPANISH_TO_ENGLISH.get(name, name)


def resolve(name: str, known) -> str:
    """Map a user-supplied country (English or dataset spelling) onto one of the `known` dataset values."""
    name = (name or "").strip()
    if name in known:
        return name
    return to_dataset_name(name)


def to_dataset_name(name: str) -> str:
    """Accept an English or original (Spanish) country name and return the dataset's value."""
    name = (name or "").strip()
    if name in SPANISH_TO_ENGLISH:
        return name
    return ENGLISH_TO_SPANISH.get(name.lower(), name)
