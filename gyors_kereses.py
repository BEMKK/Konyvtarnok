import time

import wx


class GyorsListaKereso:
    """Újrafelhasználható 'gépeléssel ugrás a listában' (type-ahead) logika.

    Ez a viselkedés - a beírt karakterek pufferelése, a puffer nullázása,
    ha túl sok idő telt el két leütés között, az egyetlen karakter
    ismételt leütésekor a következő egyező elemre való körkörös lépegetés,
    valamint a szóköz és a Backspace kezelése - korábban három helyen
    (a főablak könyvlistája, a Dezideráta-kezelő és a KönyvTárnok-kereső
    találati táblázata) egymástól függetlenül, szinte szó szerint
    megegyező formában volt megírva. Innentől mindhárom hely ezt a közös
    osztályt használja.

    Az EVT_CHAR eseményből a karakter kinyerése (Backspace felismerése,
    unicode/kódpont alapú kisbetűs karakter előállítása) korábban szintén
    ugyanezen a három helyen, egymástól függetlenül, szó szerint megegyező
    formában volt megírva - lásd a `kezel_char_esemeny` metódust lent.

    Az osztály semmit nem tud a konkrét GUI-elemről (wx.ListCtrl vagy
    virtuális lista), ezért a hívó félnek kell megadnia (a `feldolgoz`
    hívásakor), hogyan kérdezhető le egy adott sor szövege, hány sor van
    összesen, melyik van éppen kijelölve, és hogyan kell egy sort
    kijelölni/fókuszba hozni. Így ugyanaz a logika működik akár egy
    egyszerű `wx.ListCtrl.GetItemText()`-tel elérhető táblázaton, akár egy
    Python-listával feltöltött virtuális listán (ahol nem feltétlenül a
    0. oszlop szövege szerint kell keresni).
    """

    def __init__(self, ido_kuszob=1.2):
        self.ido_kuszob = ido_kuszob
        self.puffer = ""
        self.utolso_leutes_ideje = 0

    def visszaallit(self):
        """Törli a keresési puffert (pl. ha a keresőmezőt kiürítik)."""
        self.puffer = ""
        self.utolso_leutes_ideje = 0

    def torol_egy_karaktert(self):
        """A Backspace billentyű kezeléséhez: törli a puffer utolsó karakterét."""
        if self.puffer:
            self.puffer = self.puffer[:-1]

    def kezel_char_esemeny(self, event, feldolgozo_fv):
        """Egységesen kezeli egy wx.EVT_CHAR esemény kiértékelését.

        Backspace-re törli a puffer utolsó karakterét. Egyébként megpróbálja
        kinyerni a leütött, kisbetűssé alakított karaktert (előbb az unicode
        kódpontból, ha az nem elérhető, a nyers billentyűkódból), és ha ez
        sikerül, átadja a `feldolgozo_fv(karakter)` hívónak megadott
        callback-nek (jellemzően a `feldolgoz` metódusnak egy már
        előkészített lekérő/beállító készlettel). Ha nem nyerhető ki
        használható karakter, `event.Skip()`-et hív, hogy a widget
        alapértelmezett billentyűkezelése lefusson.
        """
        key_code = event.GetKeyCode()

        if key_code == wx.WXK_BACK:
            self.torol_egy_karaktert()
            return

        karakter = ""
        unicode_key = event.GetUnicodeKey()
        if unicode_key != wx.WXK_NONE:
            try:
                karakter = chr(unicode_key).lower()
            except Exception:
                pass

        if not karakter and 32 <= key_code <= 255:
            try:
                karakter = chr(key_code).lower()
            except Exception:
                pass

        if karakter:
            feldolgozo_fv(karakter)
        else:
            event.Skip()

    def feldolgoz(self, karakter, total_lekero, szoveg_lekero, kivalasztott_lekero, kivalasztas_beallito):
        """Feldolgoz egy beütött karaktert, és ha talál egyező sort, kijelöli azt.

        Paraméterek:
          karakter: a beütött (már kisbetűssé alakított) karakter.
          total_lekero: () -> int, az összes sor száma.
          szoveg_lekero: (index) -> str, az adott sor keresendő szövege.
          kivalasztott_lekero: () -> int, a jelenleg kijelölt/fókuszált
              sor indexe, vagy -1, ha nincs ilyen.
          kivalasztas_beallito: (index) -> None, kijelöli és fókuszba
              hozza (és láthatóvá teszi) a megadott indexű sort, a
              korábbi kijelölés törlésével együtt.
        """
        if not karakter:
            return

        aktualis_ido = time.time()
        elozo_buffer = self.puffer

        if aktualis_ido - self.utolso_leutes_ideje > self.ido_kuszob:
            self.puffer = ""
            elozo_buffer = ""

        if karakter == ' ':
            if not self.puffer:
                return
            self.puffer += ' '
        elif karakter.strip():
            # Ismételt egykarakteres leütés detektálása (MIELŐTT a pufferhez adnánk)
            is_single_char_repeat = (
                len(elozo_buffer) == 1 and
                karakter.lower() == elozo_buffer.lower()
            )
            if not is_single_char_repeat:
                self.puffer += karakter
            # Ha ismételt egykarakteres leütés, nem bővítjük a puffert,
            # marad az 1 karakteres állapot.
        else:
            return

        self.utolso_leutes_ideje = aktualis_ido
        keresett = self.puffer.lower()
        total = total_lekero()
        if total == 0:
            return

        # Ciklikus keresés: ha 1 karakteres puffer és ugyanazt nyomták le,
        # a jelenlegi kijelöléstől kezdve keresünk tovább (körkörösen)
        is_single_char_repeat = (
            len(keresett) == 1 and
            len(elozo_buffer) == 1 and
            keresett == elozo_buffer.lower()
        )

        current_idx = kivalasztott_lekero()
        if is_single_char_repeat and current_idx != -1:
            start_idx = (current_idx + 1) % total
        else:
            start_idx = 0

        def keres_elo_tag(tol, korokre=False):
            for i in range(tol, total):
                ertek = str(szoveg_lekero(i)).lower().strip()
                if ertek.startswith(keresett):
                    return i
            if korokre:
                for i in range(0, tol):
                    ertek = str(szoveg_lekero(i)).lower().strip()
                    if ertek.startswith(keresett):
                        return i
            return -1

        # 1. Pontos előtag egyezés keresése
        talalt = keres_elo_tag(start_idx, korokre=is_single_char_repeat)

        # 2. Ha nincs találat és nem körkörösen kerestünk, próbáljuk az elejéről
        if talalt == -1 and not is_single_char_repeat:
            talalt = keres_elo_tag(0)

        if talalt != -1:
            kivalasztas_beallito(talalt)


def osszes_kijelolt_index(list_ctrl):
    """Visszaadja egy wx.ListCtrl (vagy azzal kompatibilis, GetFirstSelected/
    GetNextSelected metódusokkal rendelkező) vezérlőelem összes kijelölt
    sorindexét listaként, a megjelenés sorrendjében.

    Ezt a bejárást (a kijelölés végigolvasása GetFirstSelected/
    GetNextSelected hívásokkal egy while-cikluson keresztül) korábban a
    Dezideráta-kezelő és a KönyvTárnok-kereső több helyen (törlés,
    átemelés az állományba/dezideratába, vágólapra másolás) is, egymástól
    függetlenül, kézzel megismételve valósította meg.
    """
    indexek = []
    idx = list_ctrl.GetFirstSelected()
    while idx != -1:
        indexek.append(idx)
        idx = list_ctrl.GetNextSelected(idx)
    return indexek
