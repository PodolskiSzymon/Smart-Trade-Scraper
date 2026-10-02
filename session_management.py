import os
from cookies_management import update_cookies_and_headers, load_vinted_data_from_file
import requests
import re

# Nowy endpoint katalogu (Vinted przeniósł listę ogłoszeń z www.vinted.pl/api/v2/catalog/items)
CATALOG_URL = 'https://api.vinted.pl/svc-catalogue/items'

categories={
    'karty_pamieci':3063,
    'elektronika':2994,
}

def get_catalog_params(category, order='newest_first', page=1, search_text='', brand_ids='', brand_collection_ids='', status_ids='', price_from=''):
    catalog_ids = categories[category]
    params = {
        'page': page,
        'per_page': 96,
        'search_text': search_text,
        'price_from': price_from,
        'currency': 'PLN',
        'order': order,
        'attribute_ids[catalog]': catalog_ids,
        'attribute_ids[brand]': brand_ids,
        'attribute_ids[brand_collection]': brand_collection_ids,
        'attribute_ids[status]': status_ids,
    }
    # Vinted odrzuca puste price_from= (400 INVALID_REQUEST) - wysyłamy je tylko z wartością,
    # tak jak przeglądarka. Pozostałe puste pola (search_text, attribute_ids[...]) są akceptowane.
    if price_from in ('', None):
        del params['price_from']
    return params

def format_title(title):
    """Zmienia tytuł w format URL-friendly (slug)."""
    title = title.lower()
    title = re.sub(r'[^a-z0-9\s-]', '', title)
    title = re.sub(r'[\s-]+', '-', title)
    return title.strip('-')

def make_main_loop_referer(page=1):
    """Generuje referer dla przeglądania katalogu."""
    if page == 1:
        return "https://www.vinted.pl/catalog"
    else:
        return f"https://www.vinted.pl/catalog?page={page}"

def make_endpoints_referer(item_id, title):
    """Generuje referer udający wejście w szczegóły konkretnego ogłoszenia."""
    clean_title = format_title(title)
    return f"https://www.vinted.pl/items/{item_id}-{clean_title}?referrer=catalog"

def update_sesions_cookies(session):
    """Odświeża zarówno ciastka jak i tokeny w aktywnej sesji."""
    new_cookies, new_headers = update_cookies_and_headers()
    session.cookies.clear()          # stare ciastka (np. wygasły cf_clearance) nie mieszają się z nowymi
    session.cookies.update(new_cookies)
    if new_headers:
        session.headers.update(new_headers)

def make_boot_session():
    """Tworzy i konfiguruje sesję HTTP ładując dynamiczne tokeny."""
    cookies, custom_headers = load_vinted_data_from_file()
    
    # Nagłówki 1:1 z działającego zapytania do api.vinted.pl/svc-catalogue/items (cURL z przeglądarki)
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'pl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'locale': 'pl-PL',
        'origin': 'https://www.vinted.pl',
        'platform': 'web',
        'priority': 'u=1, i',
        'referer': 'https://www.vinted.pl/',
        'sec-ch-ua': '"Chromium";v="154", "Microsoft Edge";v="154", "Not A(Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0',
        'x-next-app': 'marketplace-web',
    }

    session = requests.Session()
    session.headers.update(headers)
    
    # Ładujemy ukradzione tokeny z dysku (x-csrf-token i x-anon-id)
    if custom_headers:
        session.headers.update(custom_headers)
        
    session.cookies.update(cookies)
    main_url = "https://www.vinted.pl/"
    session.headers.update({"Referer": main_url})
    return session

# ==========================================
# KONFIGURACJA OLX
# ==========================================

GRAPHQL_QUERY = """query ListingSearchQuery(
  $searchParameters: [SearchParameter!] = []
) {
  clientCompatibleListings(searchParameters: $searchParameters) {
    __typename
    ... on ListingSuccess {
      __typename
      data {
        id
        title
        url
        photos {
          link
        }
      }
      metadata {
        total_elements
      }
    }
    ... on ListingError {
      __typename
      error {
        code
        detail
        status
        title
      }
    }
  }
}"""

def get_olx_headers(target_category):
    return {
        'accept': 'application/json',
        'accept-language': 'pl',
        'content-type': 'application/json',
        'origin': 'https://www.olx.pl',
        'referer': f'https://www.olx.pl/elektronika/q-{target_category}/?courier=1&search%5Bphotos%5D=1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0',
        'x-client': 'DESKTOP',
    }

def get_olx_payload(current_offset, limit, target_category):
    return {
        'query': GRAPHQL_QUERY,
        'variables': {
            'searchParameters': [
                {'key': 'offset', 'value': str(current_offset)},
                {'key': 'limit', 'value': str(limit)},
                {'key': 'query', 'value': target_category}, 
                {'key': 'category_id', 'value': '2906'}, 
                {'key': 'photos', 'value': 'true'},
                {'key': 'courier', 'value': 'true'},
                {'key': 'sort_by', 'value': 'created_at:desc'},
            ]
        },
    }