OFFICEPLUS CHATBOT – INSTALARE (actualizat 16.09.2026, dupa instalarea reala)

INSTALAT DEJA PE SITE
  Adresa:    https://officeplus.md/OfficePlus_Chatbot/
  Serverul:  92.5.130.1 (server.officeplus.md), nginx + PHP-FPM 8.3
  Folderul:  /var/www/officeplus/OfficePlus_Chatbot
  vendor/    populat cu «composer install» (dompdf 3.1.6 + dependente, 14 MB) — PDF-ul functioneaza

CE MAI TREBUIE COMPLETAT (api/config.php pe server)
  1. OFFICEPLUS_USERNAME / OFFICEPLUS_PASSWORD — un cont pentru API-ul B2B
     (https://officeplus.md/api/v1). Deocamdata in baza exista doar contul de proba
     «apitest@officeplus.test». Fara cont, cautarea produselor intoarce mesajul
     «Nu s-au putut incarca produsele» (restul widgetului merge).
  2. TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID — pentru instiintarea despre oferta noua.
     Fara ele oferta PDF se creeaza oricum, doar ca «telegram_sent» ramine false.

DE STIUT DESPRE ACEST SERVER (lucruri aflate la instalare)
  - PHP ruleaza ca www-data. Scriu doar doua lucruri: api/offers (775) si
    api/.officeplus_tokens.json (600). Restul e 644, root-ul e www-data:www-data.
  - nginx NU citeste .htaccess. Fisierul api/.htaccess nu are efect aici; protectia
    vine din vhost: «location ~ /\.(?!well-known) { deny all; }» acopera tokenul,
    iar listarea folderelor e oprita (api/offers/ raspunde 403, un PDF anume — 200).
  - nginx are «index index.php», deci un folder cu doar index.html raspundea 403.
    De aceea exista index.php care serveste index.html. Nu-l stergeti.
  - «location /api/» din vhost merge spre Flask (back-office), dar NU atinge
    /OfficePlus_Chatbot/api/ — acolo raspund fisierele PHP ale widgetului.
  - README-urile de instalare NU se tin in radacina web (au fost sterse de acolo).

REACTUALIZARE (cind se schimba codul)
  1. local, in folderul proiectului: composer install --no-dev --optimize-autoloader
  2. arhivati si copiati pe server in /var/www/officeplus/OfficePlus_Chatbot
  3. sudo chown -R www-data:www-data <folder>; api/offers ramine 775
  4. verificati: https://officeplus.md/OfficePlus_Chatbot/ (200) si un PDF de proba

INTEGRARE IN PAGINA (WordPress sau site nativ)
  <iframe src="/OfficePlus_Chatbot/" style="width:100%;height:700px;border:0"></iframe>

ALTE NOTE
  - Fluxul foloseste validate_only si NU creeaza inca o comanda reala in UNA.md.
  - Nu puneti credentialele in JavaScript.
  - Ofertele PDF se strung in api/offers/ — merita o curatare periodica.

Date OfficePlus:
GRECU OFFICE GROUP SRL
mun. Bălți, str. Libertății 96, of.1
+373 62 007 211
officeplussrl@gmail.com
https://officeplus.md
