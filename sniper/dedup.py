"""Anty-Duplikator: pamięć kilkunastu ostatnich ID w RAM (zastępuje PostgreSQL z db_management.py)."""
from collections import deque


class RecentIds:
    """Bufor kołowy ostatnich ID - deque(maxlen) + set dla sprawdzania w O(1).

    Wszystkie operacje są synchroniczne i trwają mikrosekundy, więc nie blokują
    pętli zdarzeń. ID z Vinted rosną monotonicznie, dlatego pamiętamy też
    "próg" (najwyższe ID wypchnięte z bufora) - oferta z ID <= progu jest stara,
    nawet jeśli wypadła już z deque. Chroni to przed ponownymi alertami, gdy
    katalog zwraca więcej pozycji niż mieści bufor.
    """

    def __init__(self, maxlen=20):
        self._order = deque(maxlen=maxlen)
        self._ids = set()
        self._floor = 0

    def __contains__(self, item_id):
        return item_id in self._ids or item_id <= self._floor

    def __len__(self):
        return len(self._order)

    def add(self, item_id):
        """Zapamiętuje ID. Zwraca True, jeśli było nowe."""
        if item_id in self:
            return False
        if len(self._order) == self._order.maxlen:
            evicted = self._order.popleft()
            self._ids.discard(evicted)
            self._floor = max(self._floor, evicted)
        self._order.append(item_id)
        self._ids.add(item_id)
        return True

    def snapshot(self):
        return list(self._order)
