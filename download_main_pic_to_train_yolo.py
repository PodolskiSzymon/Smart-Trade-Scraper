import requests;
from bs4 import BeautifulSoup;
import random;
import time;
import json;
import os;
from playwright.sync_api import sync_playwright
import uuid

delay = random.uniform(0.5, 1.5) 

COOKIES_FILE = "cookies.json"

def load_cookies_from_file():
    """Wczytuje ciastka z pliku na samym starcie programu."""
    if not os.path.exists(COOKIES_FILE):
        print(f"[DISK] Brak pliku {COOKIES_FILE}. Program ruszy z pustą sesją.")
        return {}
    
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        print(f"[DISK] Wczytano ciasteczka startowe z pliku {COOKIES_FILE}.")
        return json.load(f)
    
def zdobadz_nowe_ciastka():
    print("[AUTH] Uruchamiam Playwright (Chromium)...")
    with sync_playwright() as p:
        # Launch w trybie headed=False pozwoli Ci ręcznie przeklikać Cloudflare, jeśli zajdzie potrzeba
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("[AUTH] Wchodzę na Vinted...")
        page.goto("https://www.vinted.pl")
        
        # Dajemy czas na załadowanie wszystkiego
        page.wait_for_timeout(3000) 
        
        # Pobieramy ciasteczka w formacie, który 'requests' połknie bez problemu
        cookies_list = context.cookies()
        gotowe_ciastka = {c['name']: c['value'] for c in cookies_list}
        
        browser.close()
        print("[AUTH] Sukces! Zdobyto świeże ciasteczka.")
        return gotowe_ciastka
    
def update_cookies(session):
    """
    Kombajn 3w1 wywoływany, gdy Vinted zwróci 401:
    1. Odpala Playwright i zdobywa świeże ciastka.
    2. Zapisuje je trwale na dysk (nadpisuje stary plik).
    3. Podmienia ciastka w obecnej sesji requests.
    """
    print("\n[WARN] Rozpoczynam procedurę aktualizacji ciasteczek...")
    
    # 1. Pobieranie nowych ciastek Twoją funkcją z Playwrightem
    nowe_ciastka = zdobadz_nowe_ciastka() 
    
    # 2. Zapis do pliku JSON
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(nowe_ciastka, f, indent=4)
    print(f"[DISK] Zapisano świeże ciasteczka do {COOKIES_FILE}.")
    
    # 3. Aktualizacja globalnej sesji
    session.cookies.clear()          # Czyścimy stare, wygasłe ciastka
    session.cookies.update(nowe_ciastka) # Wrzucamy nowe
    print("[AUTH] Sesja requests zaktualizowana pomyślnie. Gotowy do wznowienia pracy.\n")

def get_all_photo_urls(item_id, session, headers, cookies):
    url = f"https://www.vinted.pl/api/v2/items/{item_id}/photos"
    
    try:
        response = session.get(url, headers=headers, cookies=cookies)
        if response.status_code == 200:
            data = response.json()
            # Zazwyczaj API Vinted zwraca listę pod kluczem 'photos'
            photos = data.get('photos', [])
            
            # Tworzymy listę słowników z najważniejszymi danymi
            photo_data = []
            for p in photos:
                photo_data.append({
                    "id": p.get("id"),
                    "url": p.get("url"), # To jest link do zdjęcia w pełnej rozdzielczości
                    "width": p.get("width"),
                    "height": p.get("height"),
                    "is_main": p.get("is_main")
                })
            return photo_data
        else:
            print(f"[ERROR] Endpoint zdjęć zwrócił status {response.status_code}")
            return []
    except Exception as e:
        print(f"[EXCEPTION] Błąd pobierania zdjęć: {e}")
        return []


cookies = load_cookies_from_file()

headers = {
    'accept': 'application/json,text/plain,*/*,image/webp',
    'accept-language': 'pl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
    'locale': 'pl-PL',
    'priority': 'u=3',
    'referer': 'https://www.vinted.pl/catalog?catalog[]=3063&price_from=199&currency=PLN&page=1',
    'sec-ch-ua': '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    'sec-ch-ua-arch': '"x86"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"149.0.4022.98"',
    'sec-ch-ua-full-version-list': '"Microsoft Edge";v="149.0.4022.98", "Chromium";v="149.0.7827.201", "Not)A;Brand";v="24.0.0.0"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"Windows"',
    'sec-ch-ua-platform-version': '"10.0.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0',
    'x-anon-id': 'e6f5e540-66d2-4848-ac99-c9e08762733f',
    'x-csrf-token': '75f6c9fa-dc8e-4e52-a000-e09dd4084b3e',
    # 'cookie': 'v_udt=MGlBYXcxVE1PS0VYYUVtZldVV0UzaHM0UXRDVi0taFZ0NCs1a2hzMnl2M1JoRS0tVWZzYzA2RmdUYlM5Y2JMbU1KTkpHQT09; anonymous-locale=pl-fr; _ga=GA1.1.941820386.1748695155; anon_id=e6f5e540-66d2-4848-ac99-c9e08762733f; domain_selected=true; __ps_fva=1752915039316; last_user_id=1; is_shipping_fees_applied_info_banner_dismissed=false; seller_header_visits=6; OptanonAlertBoxClosed=2026-02-24T19:48:39.140Z; eupubconsent-v2=CQgIJdgQgIJdgAcABBPLCTFsAP_gAEPgAAwILNtR_G__bWlr-Tb3afpkeYxP99hr7sQxBgbJk24FzLvW7JwSx2E5NAzatqIKmRIAu3TBIQNlHIDURUCgKIgFryDMaEyUoTNKJ6BkiBMRA2JYCFxvm4pjWQCY4vr_9lc1mB-N7dr82dzyy4hHn3a5_2S1UJCcIYetDfn8ZBKT-9IEd_x8v4v4_EbpEm-eS1n_pGtp4jd6YlM_dBmxt-TyffzPn_frk_e7X_vc_n3zv84XH77v_4LMgAmGhUQRlkQABAoGAECABQVhABQIAgAASBogIATBgQ5AwAXWEyAEAKAAYIAQAAgwABAAAJAAhEAEABAIAQIBAoAAwAIAgIAGBgADABYiAQAAgOgYpgQQCBYAJEZVBpgSgAJBAS2VCCQBAgrhCEWeAQQIiYKAAAEAAoAAAB4LAQkkBKxIIAuIJoAACAAAKIECBFIWYAgoDNFoKwJOAyNMAwfMEySnQZAEwQkZBkQm_CYeKYogAAAA.f_wACHwAAAAA.ILNtR_G__bXlv-Tb36fpkeYxf99hr7sQxBgbJs24FzLvW7JwS32E7NEzatqYKmRIAu3TBIQNtHIjURUChKIgVrzDsaEyUoTtKJ-BkiDMRY2JYCFxvm4pjWQCZ4vr_91d9mT-N7dr-2dzyy5hnv3a9_-S1UJicKYetHfn8ZBKT-_IU9_x-_4v4_MbpEm-eS1v_tGtt43d64tP_dpuxt-Tyffz___f72_e7X__c__33_-_Xf_7__4A; OTAdditionalConsentString=1~43.55.61.70.83.89.93.108.117.122.124.135.143.144.147.149.159.192.196.211.228.230.239.259.266.286.291.311.320.322.323.327.367.371.385.407.415.424.430.436.445.486.491.494.495.522.523.540.550.560.568.574.576.584.587.591.737.803.820.839.864.899.904.922.938.959.979.981.985.1003.1027.1031.1046.1051.1053.1067.1092.1095.1097.1099.1107.1109.1135.1143.1149.1152.1162.1166.1186.1188.1205.1215.1226.1227.1230.1252.1268.1270.1276.1284.1290.1301.1307.1312.1329.1345.1356.1403.1415.1416.1421.1423.1440.1449.1455.1495.1512.1516.1525.1540.1548.1555.1558.1570.1577.1579.1583.1584.1603.1616.1638.1651.1653.1659.1667.1677.1678.1682.1697.1699.1703.1712.1716.1721.1725.1732.1745.1750.1765.1782.1786.1800.1810.1825.1827.1832.1838.1840.1843.1845.1859.1870.1878.1880.1889.1917.1929.1942.1944.1962.1963.1964.1967.1968.1969.1978.1985.1987.2003.2027.2035.2039.2047.2052.2056.2064.2068.2072.2074.2088.2090.2103.2107.2109.2115.2124.2130.2133.2135.2137.2140.2147.2156.2166.2177.2186.2205.2213.2216.2219.2220.2222.2225.2234.2253.2275.2279.2282.2309.2312.2316.2322.2325.2328.2331.2335.2336.2343.2354.2358.2359.2370.2376.2377.2387.2400.2403.2405.2407.2411.2414.2416.2418.2425.2440.2447.2461.2465.2468.2472.2477.2484.2486.2488.2498.2510.2517.2526.2527.2532.2535.2542.2552.2563.2564.2567.2568.2569.2571.2572.2575.2577.2583.2584.2596.2604.2605.2608.2609.2610.2612.2614.2621.2627.2628.2629.2633.2636.2642.2643.2645.2646.2650.2651.2652.2656.2657.2658.2660.2661.2669.2670.2677.2681.2684.2687.2690.2695.2698.2713.2714.2729.2739.2767.2768.2770.2772.2784.2787.2791.2792.2798.2801.2805.2812.2813.2816.2817.2821.2822.2827.2830.2831.2833.2834.2838.2839.2844.2846.2849.2850.2852.2854.2860.2862.2863.2865.2867.2869.2874.2875.2878.2880.2881.2882.2884.2886.2887.2888.2889.2891.2893.2894.2895.2897.2898.2900.2901.2908.2909.2916.2917.2918.2920.2922.2923.2927.2929.2930.2931.2940.2941.2947.2949.2950.2956.2958.2961.2963.2964.2965.2966.2968.2973.2975.2979.2980.2981.2983.2985.2986.2987.2994.2995.2997.2999.3000.3002.3003.3005.3008.3009.3010.3012.3016.3017.3018.3019.3028.3034.3038.3043.3052.3053.3055.3058.3059.3063.3066.3068.3070.3073.3074.3075.3076.3077.3089.3090.3093.3094.3095.3097.3099.3100.3106.3109.3112.3117.3119.3126.3127.3128.3130.3135.3136.3145.3150.3151.3154.3155.3163.3167.3172.3173.3182.3183.3184.3185.3187.3188.3189.3190.3194.3196.3209.3210.3211.3214.3215.3217.3222.3223.3225.3226.3227.3228.3230.3231.3234.3235.3236.3237.3238.3240.3244.3245.3250.3251.3253.3257.3260.3270.3272.3281.3288.3290.3292.3293.3296.3299.3300.3306.3307.3309.3314.3315.3316.3318.3324.3328.3330.3331.3531.3731.3831.4131.4531.4631.4731.4831.5231.6931.7235.7831.7931.8931.9731.10231.10631.10831.11031.11531.13632.14034.14133.14237.14332.15731.16831.16931.21233.23031.25131.25931.26031.26631.26831.27731.27831.28031.28731.28831.29631.32531.33931.34231.34631.36831.39131.39531.40632.41131.41531.43631.43731.43831.45931.47232.47531.48131.49231.49332.49431.50831.52831; anonymous-iso-locale=pl-PL; _ga_762HZ9XYEN=deleted; __ps_r=_; __ps_lu=https://www.vinted.pl/session-refresh?ref_url=%2F; __ps_did=pscrb_2476757e-f269-4e6d-c2dd-65a38b61db29; non_dot_com_www_domain_cookie_buster=1; consent_version=eu; v_sid=44fed57b9bba0c2c470ee8ca0f5ca7a5; _gcl_au=1.1.1231803564.1782543267; refresh_token_web=eyJhbGciOiJQUzI1NiIsImtpZCI6IkU1N1lkcnVIcGxBanUyY05vMURvckgzajI3QnU1LXNfT1A1UHdQaWhuNU0ifQ.eyJhcHBfaWQiOjQsImF1ZCI6ImZyLmNvcmUuYXBpLnZpbnRlZC5jb20iLCJjbGllbnRfaWQiOiJ3ZWIiLCJleHAiOjE3ODI3NjA3ODcsImlhdCI6MTc4MjcxNzU4NywiaXNzIjoidmludGVkLWlhbS1zZXJ2aWNlIiwicHVycG9zZSI6InJlZnJlc2giLCJzY29wZSI6InB1YmxpYyIsInNpZCI6ImU5Y2IxMmQyLTE3ODI3MTc1ODcifQ.tJZSoXvgnscV6b8oHcbJ7FgUzng8tDqOXFjXOV0ymPusxH70XzS6-SyxLSGKx9bGvYXBrZraJ4Sa8c6SW5uZQxf2xc2inClZBiv4TafU6aNvWJ1kM5lrgkXjF4qTM802_1R70BYWFLAfslgiUOZW60WPU2qF8XR9hH0NKAgLELG3CKVyxtS-j2MIvETjx1XMof5fgbHjBo3fIVfsxhoNXpkqAPLMqQTAIdaM-DTRhWl7ty3-Fx4Ptvdfil6Y8kSuy3IaauNDB5Pe6myzKBQ7Iw-q8AJifm5YTejq9zJMsu9uEhsLg6AzfZ-q0wF_9KHM0OQmU4kz0MvpEMg6xiJIfA; access_token_web=eyJhbGciOiJQUzI1NiIsImtpZCI6IkU1N1lkcnVIcGxBanUyY05vMURvckgzajI3QnU1LXNfT1A1UHdQaWhuNU0ifQ.eyJhcHBfaWQiOjQsImF1ZCI6ImZyLmNvcmUuYXBpLnZpbnRlZC5jb20iLCJjbGllbnRfaWQiOiJ3ZWIiLCJleHAiOjE3ODI3NjA3ODcsImlhdCI6MTc4MjcxNzU4NywiaXNzIjoidmludGVkLWlhbS1zZXJ2aWNlIiwicHVycG9zZSI6ImFjY2VzcyIsInNjb3BlIjoicHVibGljIiwic2lkIjoiZTljYjEyZDItMTc4MjcxNzU4NyJ9.ADs0Wfzy5yHqXKHy1Cm7BUCVYlJSIHFazjaKYBXQxFU_pP2MHxovWNstj_OHB4UWNIe8QYtjk2Fp26ku4nYV5CeucKd3_7cb6RWuvT_wKnMpV0k12EExcCPc78OTs5WuQctz6qL_NN7IjT1X0P3WUhNn8H7yCkbTb20N-aI7vnaIryRV9_1bEQ4Q22YNJlXlNrtZHreSEJbgQGVqlZPJsVRhiJTUcDSrFQC2phns4KIpDunvWGy0Nmr4Mb7NMzj_g7k0QpxMoupJ8jExiHOY0nuP4YQl6E8h5MiEulMOskl5vpgLkS9a7pqsbKPRaqFFpHrH8WIQnYph-HeUoEXmKg; cf_clearance=EavPjX3nKU5YLTj6qceBpwtX.9MvLvg6rqQWeDD1oGw-1782719887-1.2.1.1-.E4gi2B_1SgVtXZoboOz1Pxn7DhzNwzQ32.rihLSWCBxxixWhPhLw83KVdngXCkuMtBTtXDUdyQBtQlNfWwGB5IzswWF6IfLaGHtMpwADuTCggCWM_mWujDNLsWK8ov2N4rJVAeanIkTYmRLEL5omfuuU4vnMJBuXbphzSO7UlTMD7dD9Kw7JkBzW3soKV4VpNHsoJtT_xgYIB104eMZmyK3u.lh58sGRat.NZpHShRqhHxHw7maYsSBrv3HyzphtR.0dh7yYVOBtU0iN7I_P29c2oZBWj3Li0s2e87DCHGq.YSjpxVvEgRgIm1zvA.JObC76eFel87Z.Ns8Ki3zow; viewport_size=620; ad_blocker_detected=true; banners_ui_state=SUCCESS; __ps_sr=_; __ps_slu=https://www.vinted.pl/; _ga_ZJHK1N3D75=GS2.1.s1782723095$o119$g1$t1782723100$j55$l0$h0; _ga_762HZ9XYEN=GS2.1.s1782723095$o13$g1$t1782723100$j55$l0$h0; OptanonConsent=isGpcEnabled=0&datestamp=Mon+Jun+29+2026+10%3A51%3A42+GMT%2B0200+(czas+%C5%9Brodkowoeuropejski+letni)&version=202602.1.0&browserGpcFlag=0&isIABGlobal=false&consentId=e6f5e540-66d2-4848-ac99-c9e08762733f&interactionCount=5&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1%2CC0005%3A1%2CV2STACK42%3A1%2CC0035%3A1%2CC0038%3A1&genVendors=V2%3A1%2CV1%3A1%2C&AwaitingReconsent=false&geolocation=PL%3B30&isAnonUser=1&intType=1&identifierType=Cookie+Unique+Id&prevHadToken=0; datadome=rVHdowwMttwesmX2gYXh64e4w2CzZtLG4EcwMJ81E6kJa4WxxAKYUT2UCQPIWhOYAI9ODfLFU3Q2OqVXOoxqdJEQ99XU4hhTz34_NbW5JiPQz7nD~4w_D~Hw0fal5JGw; __cf_bm=8RcqYAzH2nnlP_6fwhN5CZGLROTFHWCi1HB8539i3uo-1782723622.1391237-1.0.1.1-FqQYkyT4jVhY5J7DqVa_AX.JnLFSvP6Q.zUWnWs7qnKPfeY8MxixVoWDX7ZnmTDs8Z5KL3NHco2yUy9Du5M0_a707nFloU6KC29dh0JHKL8L_VSC5UJLTXMK8fDSeOi3Kjuujb6NYvITF3dkkhwEkQ; _vinted_fr_session=am13WEN5aUlRSkhQNkgveG9TckV5SHRDb29VRWhLbjIydmtjaGdhTFZCcVIvaXlQd2Q4WjNrUEpZQlhPUkczNVc2cmZhZi8xTzZSVkhOSk92R1MrYnJIZVorbUxManFzUkRFVDJYbU56VTJyVjhPaTZPd1NDZWM0K0pYblNUKzN6eGRhYXE5WkxxemZwU1dBQlZrV2lrRWxIYkVORG9adTNQelpjSlYzZFVFZmlYT1krUlVFRTVGb0ZHVTUrUWNqR2k1OFNLWWtXMDlGK2NYaVVxeDNjWWFnTjNsTXFjLy81MTZxRitTcUJBRWhzQ1RRMzJSNzVTL1dreEhSRGJEVy0tQmdLdk1lUjY3bjdDeVV1V0FNZS9mdz09--61e9791a79f623e01b81254b1ec60354c28fd3c2',
}

params = {
    'page': 1,
    'per_page': 96, #zmiana nic nie daje
    'search_text': '', #np microsd
    'price_from': '',
    'currency': 'PLN',
    'order': 'newest_first',#newest_first -> od najnowszych, relevance->trafność
    'catalog_ids': '3063', #id katalogu (kategorii) #katalog "elektronika"->2994,
    #katalog "nośniki pamięci"->3063
    'brand_ids': '',
    'status_ids': '',
    'color_ids': '',
    'time': str(int(time.time())),
    'global_search_session_id': str(uuid.uuid4())
}


my_referers = {
    "glowna": "https://www.vinted.pl/",
    "karty_pamieci": "https://www.vinted.pl/catalog/3063-memory-cards",
}

session= requests.session()
session.cookies.update(cookies)

session.headers.update({
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
})
session.get(my_referers["glowna"])
session.headers.update({"Referer": my_referers["glowna"]})

for i in range(1, 4):

    params['page']=i
    response = requests.get('https://www.vinted.pl/api/v2/catalog/items', params=params, cookies=cookies, headers=headers)  
    time.sleep(random.uniform(0.5, 1.5))
    if response.status_code == 400:
        print(f"Osiągnięto koniec katalogu (strona {i}). Zamykam scraper.")
        break # To przerywa pętlę for
    elif(response.status_code!=200):
        print(f"blad statusu: ", response.status_code)
    else:
        print("sukces")
        data = response.json()
        items = data.get('items', [])
        print("dlogusc items: ", len(items))
        for licznik, item in enumerate(items):
            id=item.get("id")
            print(f"Przedmiot: {item.get("title")}\n")
            photo_url = f"https://www.vinted.pl/api/v2/items/{id}/photos"
            try:
                photo_response = session.get(photo_url, headers=headers, cookies=cookies)
                if photo_response.status_code==200:
                    print(f"pobieram zdjęcie {licznik} z strony {params['page']}\n")
                    photo_all_data = photo_response.json()
                    all_photos= photo_all_data.get('photos', [])
                    photo_url=all_photos[0].get("url")
                    nazwa_pliku=f"zdj_{licznik}_z_str{params['page']}.png"
                    photo=requests.get(photo_url, stream=True)
                    os.makedirs("zdjecia", exist_ok=True)
                    with open(f"zdjecia/{nazwa_pliku}", 'wb') as f:
                        for chunk in photo.iter_content(8192):
                            f.write(chunk)
                    
                else:
                    print("blad przy  pobieraniu danych")
            except Exception as e:
                print(f"[EXCEPTION] Błąd pobierania zdjęć: {e}")
                
