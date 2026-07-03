aby zaktualizować yolo, należy najpierw pobrać "nowe" zdjecia.
Poprzez plik "download_main_pic_to_train_yolo.py" Pobieramy zdjęcia z sortowaniem od najnowszych z vinted od strony 1 do strony n:
for i in range(1, 4) tutaj wybieramy zakres stron.
Nowo pobrane zdjęcia są przechowywane w folderze "zdjęcia", aby się upenić że nie wystąpią duplikaty z już przetrenowanymi zdjęciami włączamy program:
"usun_duplikaty_zachowujac_yolo.py". Teraz usuną się duplikaty oraz naprawi się numeracja w folderze zdjęcia.
Teraz chcemy odpalić test yolo "test_modelu_yolo.py" który sprawdza nowe, wcześniej nie przetrenowane zdjęcia, są one w folderze "zdjecia".
Teraz w teście szukamy strzałkami <- -> zdjęć które są kartami microsd, a są wykrywane z małą pewnością, oraz błędnie oznaczonych zdjęć jako microsd. kiedy takie zdjęcie widziemy,
naciskamy strzałkę w górę na klawiaturze, w tym momencie nasze zdjęcie zostaje skopiowane do folderu "val_zdjęcia". Kiedy przejdziemy po wszystkich zdjęciach z folderu "zdjęcia",
sprawdzamy czy z "val_zdj" nie ma przypadkowych dupliktów, jesli nie ma, usuwamy zawartość folderu "zdjecia" i dajemy tam zawartosc folderu "val_zdjecia". Teraz jeszcze raz uruchamiamy 
"usun_duplikaty_zachowujac_yolo.py", aby poprawiła się numeracja, teraz zdjęcia z folderu "zdjecia" dajemy do foldery "wytrenowane_zdjecia". Teraz kiedy mamy na pewno nowe i wartościowe
dla naszego yolo zdjęcia, wchodzimy na stronę https://www.makesense.ai/ i załączamy tam wszystkie zdjecia z folderu "wytrenowane_zdjecia", nastepnie wybieramy "object detection", teraz
importujemy już kiedyś utworzone obramówki, klikamy w lewym górnym rogu "Actions"->"Import Annotations"->"pollygon annoations"->najnowszy plik "labels_my-project-name.json". teraz szukamy
nowo wgranych zdjęć, UWAGA: nowo wgrane zdjecia nie muszą byc na samum dole, będą wgrane gdzieś randomowo, ale razem w jednym miejscu. Zaznaczamy microsd, zostawiamy negatywne.
Teraz klikamy "Actions"->"Export Annotations"->"Export polygon annotations"->"COCO json format"->nowy plik "labels_my-project-name_[DATA].json" przenieś do folderu projektu,
Następnie odpalamy "stworz_strukture_yolo.py" bez zmian, nastepnie odpalamy "trenuj_yolo.py" bez zmian
