import requests;
from bs4 import BeautifulSoup;
import random;
import time;
import json;
import os;
from playwright.sync_api import sync_playwright;

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


def check_item_status(item_id, session):
    url = f"https://www.vinted.pl/api/v2/items/{item_id}"
    
    # Dodajemy nagłówki, które "udają" otwarcie strony w przeglądarce
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Referer": f"https://www.vinted.pl/items/{item_id}",  # TO JEST KLUCZOWE
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest" # Często wymagane przez API
    }
    
    try:
        response = session.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            item = data.get('item', {})
            return {
                "id": item.get("id"),
                "is_closed": item.get("is_closed"),
                "status_id": item.get("status_id")
            }
        else:
            print(f"[ERROR] Status {response.status_code} - być może potrzebna jest nowa sesja.")
            return {"error": response.status_code}
    except Exception as e:
        return {"error": str(e)}
    

cookies = load_cookies_from_file()

headers = {
    'accept': 'application/json,text/plain,*/*,image/webp',
    'accept-language': 'pl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
    'locale': 'pl-PL',
    'priority': 'u=3',
    'referer': 'https://www.vinted.pl/catalog?page=1&time=1782796128&catalog[]=3063&currency=PLN&status_ids[]=6',
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
    # 'cookie': 'v_udt=MGlBYXcxVE1PS0VYYUVtZldVV0UzaHM0UXRDVi0taFZ0NCs1a2hzMnl2M1JoRS0tVWZzYzA2RmdUYlM5Y2JMbU1KTkpHQT09; anonymous-locale=pl-fr; _ga=GA1.1.941820386.1748695155; anon_id=e6f5e540-66d2-4848-ac99-c9e08762733f; domain_selected=true; __ps_fva=1752915039316; last_user_id=1; is_shipping_fees_applied_info_banner_dismissed=false; seller_header_visits=6; OptanonAlertBoxClosed=2026-02-24T19:48:39.140Z; eupubconsent-v2=CQgIJdgQgIJdgAcABBPLCTFsAP_gAEPgAAwILNtR_G__bWlr-Tb3afpkeYxP99hr7sQxBgbJk24FzLvW7JwSx2E5NAzatqIKmRIAu3TBIQNlHIDURUCgKIgFryDMaEyUoTNKJ6BkiBMRA2JYCFxvm4pjWQCY4vr_9lc1mB-N7dr82dzyy4hHn3a5_2S1UJCcIYetDfn8ZBKT-9IEd_x8v4v4_EbpEm-eS1n_pGtp4jd6YlM_dBmxt-TyffzPn_frk_e7X_vc_n3zv84XH77v_4LMgAmGhUQRlkQABAoGAECABQVhABQIAgAASBogIATBgQ5AwAXWEyAEAKAAYIAQAAgwABAAAJAAhEAEABAIAQIBAoAAwAIAgIAGBgADABYiAQAAgOgYpgQQCBYAJEZVBpgSgAJBAS2VCCQBAgrhCEWeAQQIiYKAAAEAAoAAAB4LAQkkBKxIIAuIJoAACAAAKIECBFIWYAgoDNFoKwJOAyNMAwfMEySnQZAEwQkZBkQm_CYeKYogAAAA.f_wACHwAAAAA.ILNtR_G__bXlv-Tb36fpkeYxf99hr7sQxBgbJs24FzLvW7JwS32E7NEzatqYKmRIAu3TBIQNtHIjURUChKIgVrzDsaEyUoTtKJ-BkiDMRY2JYCFxvm4pjWQCZ4vr_91d9mT-N7dr-2dzyy5hnv3a9_-S1UJicKYetHfn8ZBKT-_IU9_x-_4v4_MbpEm-eS1v_tGtt43d64tP_dpuxt-Tyffz___f72_e7X__c__33_-_Xf_7__4A; OTAdditionalConsentString=1~43.55.61.70.83.89.93.108.117.122.124.135.143.144.147.149.159.192.196.211.228.230.239.259.266.286.291.311.320.322.323.327.367.371.385.407.415.424.430.436.445.486.491.494.495.522.523.540.550.560.568.574.576.584.587.591.737.803.820.839.864.899.904.922.938.959.979.981.985.1003.1027.1031.1046.1051.1053.1067.1092.1095.1097.1099.1107.1109.1135.1143.1149.1152.1162.1166.1186.1188.1205.1215.1226.1227.1230.1252.1268.1270.1276.1284.1290.1301.1307.1312.1329.1345.1356.1403.1415.1416.1421.1423.1440.1449.1455.1495.1512.1516.1525.1540.1548.1555.1558.1570.1577.1579.1583.1584.1603.1616.1638.1651.1653.1659.1667.1677.1678.1682.1697.1699.1703.1712.1716.1721.1725.1732.1745.1750.1765.1782.1786.1800.1810.1825.1827.1832.1838.1840.1843.1845.1859.1870.1878.1880.1889.1917.1929.1942.1944.1962.1963.1964.1967.1968.1969.1978.1985.1987.2003.2027.2035.2039.2047.2052.2056.2064.2068.2072.2074.2088.2090.2103.2107.2109.2115.2124.2130.2133.2135.2137.2140.2147.2156.2166.2177.2186.2205.2213.2216.2219.2220.2222.2225.2234.2253.2275.2279.2282.2309.2312.2316.2322.2325.2328.2331.2335.2336.2343.2354.2358.2359.2370.2376.2377.2387.2400.2403.2405.2407.2411.2414.2416.2418.2425.2440.2447.2461.2465.2468.2472.2477.2484.2486.2488.2498.2510.2517.2526.2527.2532.2535.2542.2552.2563.2564.2567.2568.2569.2571.2572.2575.2577.2583.2584.2596.2604.2605.2608.2609.2610.2612.2614.2621.2627.2628.2629.2633.2636.2642.2643.2645.2646.2650.2651.2652.2656.2657.2658.2660.2661.2669.2670.2677.2681.2684.2687.2690.2695.2698.2713.2714.2729.2739.2767.2768.2770.2772.2784.2787.2791.2792.2798.2801.2805.2812.2813.2816.2817.2821.2822.2827.2830.2831.2833.2834.2838.2839.2844.2846.2849.2850.2852.2854.2860.2862.2863.2865.2867.2869.2874.2875.2878.2880.2881.2882.2884.2886.2887.2888.2889.2891.2893.2894.2895.2897.2898.2900.2901.2908.2909.2916.2917.2918.2920.2922.2923.2927.2929.2930.2931.2940.2941.2947.2949.2950.2956.2958.2961.2963.2964.2965.2966.2968.2973.2975.2979.2980.2981.2983.2985.2986.2987.2994.2995.2997.2999.3000.3002.3003.3005.3008.3009.3010.3012.3016.3017.3018.3019.3028.3034.3038.3043.3052.3053.3055.3058.3059.3063.3066.3068.3070.3073.3074.3075.3076.3077.3089.3090.3093.3094.3095.3097.3099.3100.3106.3109.3112.3117.3119.3126.3127.3128.3130.3135.3136.3145.3150.3151.3154.3155.3163.3167.3172.3173.3182.3183.3184.3185.3187.3188.3189.3190.3194.3196.3209.3210.3211.3214.3215.3217.3222.3223.3225.3226.3227.3228.3230.3231.3234.3235.3236.3237.3238.3240.3244.3245.3250.3251.3253.3257.3260.3270.3272.3281.3288.3290.3292.3293.3296.3299.3300.3306.3307.3309.3314.3315.3316.3318.3324.3328.3330.3331.3531.3731.3831.4131.4531.4631.4731.4831.5231.6931.7235.7831.7931.8931.9731.10231.10631.10831.11031.11531.13632.14034.14133.14237.14332.15731.16831.16931.21233.23031.25131.25931.26031.26631.26831.27731.27831.28031.28731.28831.29631.32531.33931.34231.34631.36831.39131.39531.40632.41131.41531.43631.43731.43831.45931.47232.47531.48131.49231.49332.49431.50831.52831; anonymous-iso-locale=pl-PL; _ga_762HZ9XYEN=deleted; __ps_r=_; __ps_lu=https://www.vinted.pl/session-refresh?ref_url=%2F; __ps_did=pscrb_2476757e-f269-4e6d-c2dd-65a38b61db29; non_dot_com_www_domain_cookie_buster=1; consent_version=eu; _gcl_au=1.1.1231803564.1782543267; ad_blocker_detected=true; refresh_token_web=eyJhbGciOiJQUzI1NiIsImtpZCI6IkU1N1lkcnVIcGxBanUyY05vMURvckgzajI3QnU1LXNfT1A1UHdQaWhuNU0ifQ.eyJhcHBfaWQiOjQsImF1ZCI6ImZyLmNvcmUuYXBpLnZpbnRlZC5jb20iLCJjbGllbnRfaWQiOiJ3ZWIiLCJleHAiOjE3ODI4MzkzMTQsImlhdCI6MTc4Mjc5NjExNCwiaXNzIjoidmludGVkLWlhbS1zZXJ2aWNlIiwicHVycG9zZSI6InJlZnJlc2giLCJzY29wZSI6InB1YmxpYyIsInNpZCI6IjIxYjViOTE4LTE3ODI3OTYxMTQifQ.ojxhKkweXjWhaW2-ZODQYOyHZVD_o91VO7bUq_KJ9KrBbxj4aZJBUjTFxZVUOOpNe-Cz87hlPDkgMa7bwoJdC1ZEyLJh0rSF3n_w_eYkinXFxxZE21Tf4_MMCVCcZLdzTIdCDwwfpf59AIV6QF_8i1xR5hhxgXtIgp7wrLWwwcuKr4aqkKFUirzqAJpsUGJjrSTHO17MQfjrQzx3-0uiTnqBhIpMtbVyI8dmYf1N3EpvG_rui90T__hCJTwCXwiyBLcCUXGegpZlcnqJM1jdIR6olY2SdDwjZAQiDIaxN8cgSW82VRtWTFKjLqmzic2PyuVxKuMkZ9BknOhPt_xhaw; access_token_web=eyJhbGciOiJQUzI1NiIsImtpZCI6IkU1N1lkcnVIcGxBanUyY05vMURvckgzajI3QnU1LXNfT1A1UHdQaWhuNU0ifQ.eyJhcHBfaWQiOjQsImF1ZCI6ImZyLmNvcmUuYXBpLnZpbnRlZC5jb20iLCJjbGllbnRfaWQiOiJ3ZWIiLCJleHAiOjE3ODI4MzkzMTQsImlhdCI6MTc4Mjc5NjExNCwiaXNzIjoidmludGVkLWlhbS1zZXJ2aWNlIiwicHVycG9zZSI6ImFjY2VzcyIsInNjb3BlIjoicHVibGljIiwic2lkIjoiMjFiNWI5MTgtMTc4Mjc5NjExNCJ9.wVRNSDRnJt3iPPY4yvry8-BXUEWbmC5ycSCondzluzaXN8cQm_WzPEgn6bHPVD7A3jNYCoexAMGGqJbrR44NdUwPThQKx3znoh6sezPi5Qb7Kmjyve0wGCj5IW46cLszH1JBXxao2KJU8k6LTC4g1IoyKW48c69puM-t5YJEslN6ej9lkjShUmUVlI6oUApNmZ01AfOnTlQsnOQgBNeXhzgj2cAXNWxaDhXiyZKXwGdAS7xO5fNHtf13Cht1vFVIInIhbgPLT1AYaLfyer1mdZQ9H63D7BX8G2OWfIbrYz4yMKWQjZQh-06NXCyLIy8EBFFayaa3CBD-5J9trViSKw; v_sid=9b7f2cca8f63502d98294f6a765fdc92; viewport_size=475; cf_clearance=JTWnDJna3iUn4RcqtU8qqZoUyro5M.yUw0ivCnExXH4-1782799090-1.2.1.1-yHPRuQ_LbNslkDL4JIR57BPjUJ6mSSyk_H..6IaR78VAZVDsAd6ib_FaH30NEYXjzO2oq9V543cjcOxz84hJxf_X7g_OqQM048tgcgj4RSWKJvsfNgMUMXXRQTmQ7Z66TWMN99GANzQnltfI6Ud6gOzcwpqocMccNAB06RhVJUh_P0PHPRdjm01siwAfM6meuv6n5ovEnK09Jnfk.x7e3WIFGu_kKuK5IOqgdAzE9_yuP5tjb3GPmHrXV9.pYfB9X9zbn3iLuvA3_yFvCiBTS0i2vBHKhXXUnuGokNTuJyBtDjiKFf1wdyTcezjSKmG2uFPEVe3E161cKpL8JUs65w; __cf_bm=_bk8n9WFSNJfvhnfYoY8c1PopF76EQMhQBlFO7dJsgs-1782799090.9707654-1.0.1.1-RIV1Eo0WNVKVwuaUIPSxSvCjLiyTkcd3u0vFsF3PfAyMiKGzCSI9DBo2Ezbzp.QxPcSmRXEVVR_u76S8aJVbCGmXLmsU8GlLfMpZTpPUcQe_a8uSCdyqQvy0tEF0ydCxk1W38t_VEIJwh.GitO8kJw; OptanonConsent=isGpcEnabled=0&datestamp=Tue+Jun+30+2026+07%3A58%3A11+GMT%2B0200+(czas+%C5%9Brodkowoeuropejski+letni)&version=202602.1.0&browserGpcFlag=0&isIABGlobal=false&consentId=e6f5e540-66d2-4848-ac99-c9e08762733f&interactionCount=5&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1%2CC0005%3A1%2CV2STACK42%3A1%2CC0035%3A1%2CC0038%3A1&genVendors=V2%3A1%2CV1%3A1%2C&AwaitingReconsent=false&geolocation=PL%3B30&isAnonUser=1&intType=1&identifierType=Cookie+Unique+Id&prevHadToken=0; banners_ui_state=SUCCESS; __ps_sr=_; __ps_slu=https://www.vinted.pl/; _ga_762HZ9XYEN=GS2.1.s1782799088$o18$g1$t1782799094$j54$l0$h0; _ga_ZJHK1N3D75=GS2.1.s1782799088$o123$g1$t1782799094$j54$l0$h0; datadome=JF9BdwPlx6NMucSAl~y6yNsfEuqyHjb03EXxXdr0cDPR2MfabhcbCXwuw_MEzB0bbDAP7h1Z6jSodUUOuRYp_zDNihDJhmnVzxHbedH715Fu1VIEbIUOpZVpHdLE6UKU; _vinted_fr_session=Q2pCeFJ1RGtEYnlEUVFDaFpUcTd6OEhtZC9ITHZuVy84ZWFVaVB3ZGF1NkRZS2FxV3VZZkE4MERVU3YwNzZmSGRncE9leHZGZHpWUmNZUVJGU2VRckFNUjI3VkFQQ0dxOGJ4M0w4V092VjA0dlEyS3dGbVQ5YlBwUXZqd3JuWGxGRnBMVTh2bk8rVXF0QVAxZkNoK1U1TmN3WSthTm5IWTNOUHJEYTU0bWpEOUxMSWw2eUtYWktSclo1Sk5QUWpITUEwRzZMZy9DNE1hZ3ZuVFp6dm5Ld2ptWFJZTHhGZnRQcDhUeFVlSkpucm4wdythMHhzS2xLTGNOUjFqREU4NC0tVGk3dkVLNm5KZm1oc2dsWDZONnVJUT09--9b4f2b7888085837dc18f1917b9a9de99902a3bd',
}

params = {
    'page': '1',
    'per_page': '96', #zmiana nic nie daje
    'search_text': '',
    'price_from': '',
    'currency': 'PLN',
    'order': 'relevance',
    'catalog_ids': '3063', #id katalogu (kategorii)
    'brand_ids': '',
    'status_ids': '',
    'color_ids': '',
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
item_id = "9294313157"
is_available = check_item_status(item_id, session)
print(f"Wynik sprawdzania: {is_available}")