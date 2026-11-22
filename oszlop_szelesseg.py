"""Közös oszlopszélesség-segédek a főlistához (konyv_lista.py) és a
Dezideráta-kezelő listájához (deziderata.py).

A cél: az oszlopok már a létrehozáskor a (közelítőleg) végleges szélességet
kapják, és a natív vezérlőhöz (SetColumnWidth) csak akkor nyúlunk utólag, ha
a kívánt érték tényleg érdemben eltér a jelenlegitől. A SetColumnWidth
hívások drágák, ezért a felesleges hívások elhagyása adja a gyorsulást.
"""
import wx

# Ennél kisebb (pixelben mért) eltérésnél az oszlop szélességét nem állítjuk át.
TURES = 4


def hasznalhato_szelesseg(lista):
    """A lista oszlopai számára rendelkezésre álló szélesség (a függőleges
    görgetősáv levonásával). Ha a lista saját mérete még nem ismert (a
    konstruktor idején jellemzően még nincs elrendezés), a szülőjét használja."""
    szel = lista.GetClientSize().width
    if szel < 100:
        szulo = lista.GetParent()
        if szulo is not None:
            szel = max(szel, szulo.GetClientSize().width)
    return szel - wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)


def szamol_celok(alapok, sulyok, szerel_szelesseg):
    """Az alap szélességekhez hozzáadja a megmaradó helyet a súlyok
    arányában. Ha a hely nem elég, az alap szélességek maradnak."""
    alapok = list(alapok)
    osszes_alap = sum(alapok)
    osszes_suly = sum(sulyok)
    if osszes_alap <= 0 or osszes_suly <= 0 or szerel_szelesseg <= osszes_alap:
        return alapok
    maradek = szerel_szelesseg - osszes_alap
    return [a + int(maradek * s / osszes_suly) for a, s in zip(alapok, sulyok)]


def igazit(lista, celok):
    """A kívánt szélességek beállítása, de csak ott, ahol az eltérés a
    tűrésnél nagyobb; egyetlen Freeze/Thaw közben."""
    valtozasok = [(i, c) for i, c in enumerate(celok)
                  if abs(lista.GetColumnWidth(i) - c) > TURES]
    if not valtozasok:
        return
    lista.Freeze()
    try:
        for i, c in valtozasok:
            lista.SetColumnWidth(i, c)
    finally:
        lista.Thaw()
