import json
import openpyxl

# Excel fájl betöltése
wb = openpyxl.load_workbook('Enekeskonyvek_adatai.xlsx', data_only=True)
sheet = wb.active

# Fejlécek (első sor) beolvasása
headers = [cell.value for cell in sheet[1] if cell.value is not None]

# Adatsorok feldolgozása szótárak listájává
data = []
for row in sheet.iter_rows(min_row=2, values_only=True):
    # Csak azokat a sorokat dolgozzuk fel, ahol az első cella nem üres
    if any(row):
        row_dict = {headers[i]: row[i] for i in range(len(headers))}
        data.append(row_dict)

# Mentés JSON-ba (a magyar ékezetek és a szép formázás megtartásával)
with open('referencia_adatbazis.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("A JSON adatbázis sikeresen frissítve!")