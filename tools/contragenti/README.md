# Contragenti — preluarea datelor contragentului din date.gov.md

Utilitar LOCAL (rulează pe calculatorul operatorului) care caută compania în
registrul de stat și întoarce cartela ei în sistemul care a cerut-o —
back-office-ul Biro26, 1C sau orice altă aplicație.

Copie de lucru păstrată în proiect ca operatorul să o poată descărca direct
din back-office: **Clienți → butonul «⤓ Descarcă utilitarul»**.

## Instalare (o singură dată)

```bash
python3 -m venv .venv
./.venv/bin/pip install requests
./.venv/bin/python company_search.py        # sau ./run.sh
```

Serverul local pornește pe `http://127.0.0.1:9393` (schimbare: `--port`).

## Cum îl folosește back-office-ul

1. La deschiderea paginii «Clienți» se face `GET /health`. Dacă utilitarul nu
   rulează, butonul este stins și apare linkul de descărcare.
2. La apăsarea butonului «🏛 Date.gov.md»:
   * întâi se încearcă `GET /pick?...&format=xml` (fetch din pagină) — datele
     intră direct în formular;
   * dacă browserul blochează apelul spre `http://127.0.0.1` dintr-o pagină
     HTTPS, se deschide o fereastră cu
     `GET /pick?...&return_to=<pagina de întoarcere>` — utilitarul face
     **302 înapoi** în sistemul apelant cu datele în query-string
     (`idno`, `denumire`, `adresa`, `inregistrare`, `lichidata`, `state`).

## Regimuri ale endpoint-ului /pick

| Apel | Rezultat |
|---|---|
| `format=xml` (sau `Accept: application/xml`) | XML curat — pentru programe |
| `return_to=<URL>` | **302 înapoi în sistemul apelant** cu datele în query |
| `format=html` | cartela HTML — **regim DEMO**, se oprește în utilitar |
| fără parametri, din browser | demo HTML (compatibilitate) |

Statusuri la `return_to`: `status=ok` (+ câmpuri), `status=cancelled`,
`status=timeout`. Parametrul `state` se întoarce neschimbat (corelare).
