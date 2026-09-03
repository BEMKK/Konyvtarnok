# sablon.py

def general_sablon(konyv):
    """Visszaadja a sablon szövegét a könyv adataival kitöltve."""
    return f"""
Bibliográfiai adatok
Cím: {konyv.get('cim', '')}
Alcím: {konyv.get('alcim', '')}
Összeállító: {konyv.get('szerzo', '')}
Egyéb személyek: {konyv.get('egyeb_szemelyek', '')}
Kiadó: {konyv.get('kiado', '')}
Kiadás helye: {konyv.get('hely', '')}
Kiadás éve: {konyv.get('ev', '')}

Példány adatai
Oldalszám: {konyv.get('oldalszam', '')}
Méret (Ma x sz, cm: {konyv.get('meretek', '')}
Kötés típusa: {konyv.get('kotes', '')}
Rövid cím: {konyv.get('rovid_cim', '')}
Bekerülés dátuma: {konyv.get('bekerult', '')}
Példány forrása: {konyv.get('forras', '')}
Példány státusza: {konyv.get('status', '')}
Példány rövid leírása: {konyv.get('rovid_leiras', '')}
""".strip()
