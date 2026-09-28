"""RO: denumirile categoriilor de catalog: rusa -> romana.

Pe 22.09.2026 proprietarul a aratat ca la limba ROMANA a site-ului categoriile se
vedeau in rusa. Cauza: numele de BAZA din `BIRO26_GOODS.CATEGORIE` (acelasi care
tine si cheia din URL) era scris in rusa la 540 de categorii / 4402 produse, iar
dictionarul `YBIRO_GRP_I18N` nu avea niciun rind pentru ele — nu exista de unde
lua romana, asa ca vitrina arata numele de baza, adica rusescul.

Aici stau glosarul si regulile, ca sa fie verificabile si refolosibile; migrarea
o face `scripts/biro26_cat_ro_migrate.py` (numele romanesc in BIRO26_GOODS,
rusescul pastrat ca NAME_RU in dictionar).
EN: catalog category names RU -> RO; glossary + rules, applied by the migration script.
"""
import re

GLOSAR = {
 # --- fraze lungi, specifice
 "Автономный контроль доступа и времени посещения": "Control acces si pontaj autonom",
 "Автономный контроль доступа с распознаванием лиц": "Control acces autonom cu recunoastere faciala",
 "Автономный контроль доступа": "Control acces autonom",
 "Автономные контроллеры / Считыватели": "Controlere autonome / Cititoare",
 "СКУД прочее и вспомогательное оборудование": "Control acces - diverse si echipamente auxiliare",
 "Контроллеры СКУД": "Controlere control acces",
 "Контроль доступа": "Control acces",
 "СКУД": "Control acces",
 "Система аварийного оповещения": "Sistem de avertizare de urgenta",
 "Кнопка аварийного выхода": "Buton de iesire de urgenta",
 "Кнопка выхода": "Buton de iesire",
 "Комплекты автоматики для ворот": "Kituri de automatizare pentru porti",
 "Набор парковочного замка": "Set de blocator de parcare",
 "Парковочные устройства": "Dispozitive de parcare",
 "Ручной металлодетектор": "Detector de metale manual",
 "Металлодетекторы": "Detectoare de metale",
 "Металлодетектор": "Detector de metale",
 "Аксессуары для гостиничных замков": "Accesorii pentru broaste hoteliere",
 "Гостиничный замок": "Broasca hoteliera",
 "Аксессуары для жёстких тегов": "Accesorii pentru taguri rigide",
 "Жёсткий RF тег": "Tag RF rigid",
 "Теги для бутылок": "Taguri pentru sticle",
 "Аксессуары для шлагбаумов": "Accesorii pentru bariere",
 "Аксессуары для Турникетов": "Accesorii pentru turnicheti",
 "Электрический замки-болт": "Broaste electrice tip bolt",
 "Электромеханический замок – Болт": "Broasca electromecanica tip bolt",
 "Электромеханические защелки": "Zavoare electromecanice",
 "Электромеханические замки": "Broaste electromecanice",
 "Электромагнитные замки": "Broaste electromagnetice",
 "Электромагнитный замки": "Broaste electromagnetice",
 "Электроригельные замки": "Broaste electrice cu rigla",
 "Кронштейны для электромагнитных замков": "Suporturi pentru broaste electromagnetice",
 "Кронштейны для электромагнитного замка": "Suporturi pentru broasca electromagnetica",
 "Кронштейны для електрический замки-болт": "Suporturi pentru broaste electrice tip bolt",
 "Замок на стеклянную дверь": "Broasca pentru usa de sticla",
 "Навесной замок": "Lacat",
 "Умный замок": "Broasca inteligenta",
 "Биометрические терминалы": "Terminale biometrice",
 "Интеграция терминалов": "Integrare terminale",
 "Вызывные панели IP домофонов": "Panouri de apel pentru interfoane IP",
 "IP Вызывные панели": "Panouri de apel IP",
 "IP Видеодомофон": "Videointerfon IP",
 "Two-Wire Видеодомофоны": "Videointerfoane Two-Wire",
 "IP мониторы": "Monitoare IP",
 "IP SIP-телефоны": "Telefoane IP SIP",
 "SIP телефония": "Telefonie SIP",
 "USB-считыватель": "Cititor USB",
 "Считыватели": "Cititoare", "Счиытватели": "Cititoare",
 "Доводчики": "Amortizoare de usa",
 "Доп. Оборудование": "Echipamente suplimentare",
 "Дополнительное аксессуары": "Accesorii suplimentare",
 "Дополнительное оборудование": "Echipamente suplimentare",
 "Гибкий переход": "Trecere flexibila",
 "Шлагбаумы": "Bariere", "Турникеты": "Turnicheti", "Барьер": "Bariera",
 # --- antiincendiu
 "Адресно–Аналоговые ППКП": "Centrale adresabil-analogice de incendiu",
 "Адресные датчики пожарной сигнализации": "Detectoare adresabile de incendiu",
 "Адресные извещатели и стробоскопы пожарной сигнализации": "Avertizoare si stroboscoape adresabile de incendiu",
 "Адресные панели пожарной сигнализации": "Centrale adresabile de incendiu",
 "Адресные модули": "Module adresabile",
 "Стандартные датчики пожарной тревоги": "Detectoare standard de incendiu",
 "Стандартные кнопки тревоги": "Butoane standard de alarma",
 "Стандартные панели пожарной сигнализации": "Centrale standard de incendiu",
 "Стандартные панели пожаротушения": "Centrale standard de stingere a incendiului",
 "Стандарнтные пожарные сирены/стробоскопы": "Sirene/stroboscoape standard de incendiu",
 "Приборы приемно-контрольные пожарные (ППКП) безадресные": "Centrale de incendiu neadresabile",
 "Линейка безадресных приемо-контрольных приборов управления пожарной сигнализацией": "Gama de centrale neadresabile de incendiu",
 "Линейка безадресных приемо-контрольных приборов управления пожарной сигнализацие": "Gama de centrale neadresabile de incendiu",
 "Плата управления пожаротушением": "Placa de comanda a stingerii incendiului",
 "Малогабаритные модули газового пожаротушения": "Module compacte de stingere cu gaz",
 "ГАЗОВЫЕ ОГНЕТУШАЩИЕ ВЕЩЕСТВА": "Agenti de stingere gazosi",
 "Ручные Пожарные Извещатели (ИПР)": "Butoane manuale de incendiu",
 "Пожарные и Газовые извещатели": "Detectoare de incendiu si gaz",
 "Пожарные Оповещатели": "Avertizoare de incendiu",
 "ОПОВЕЩАТЕЛИ И УКАЗАТЕЛИ": "Avertizoare si indicatoare",
 "Свето-звуковой указатель": "Indicator optic-acustic",
 "Кнопки тревоги": "Butoane de alarma",
 "Ручные кнопки": "Butoane manuale",
 "Искробезопасное оборудование": "Echipamente cu siguranta intrinseca",
 "Периферийное Оборудование": "Echipamente periferice",
 "Модули расширения и дополнительное оборудование": "Module de extensie si echipamente suplimentare",
 "Плата расширения": "Placa de extensie",
 "Модули сети": "Module de retea",
 "РЕЗЕРВНЫЕ ИСТОЧНИКИ ПИТАНИЯ": "Surse de alimentare de rezerva",
 "БЛОКИ ПИТАНИЯ": "Surse de alimentare",
 "УСТРОЙСТВА ВВОДА-ВЫВОДА": "Dispozitive de intrare-iesire",
 "Соответствие Европейским Стандартам": "conform standardelor europene",
 "Соответствует новому нормативу": "conform noii norme",
 "ППКП на 2 кольцевых шлейфа с расширением до 16 колец": "Centrala de incendiu cu 2 bucle, extensibila pina la 16 bucle",
 "ППКП": "Centrala de incendiu",
 "Извещатели": "Avertizoare", "Индикатор": "Indicator", "Детекторы": "Detectoare",
 "Сирены": "Sirene", "Базы": "Socluri",
 # --- supraveghere video / retea
 "Усилитель видеосигнала по по кабелю": "Amplificator de semnal video pe cablu",
 "Усилитель видеосигнала по кабелю": "Amplificator de semnal video pe cablu",
 "(пассивные и активные)": "(pasive si active)",
 "видеорегистраторы": "DVR/NVR", "Видеорегистраторы": "DVR/NVR",
 "канальные": "canale", "каналов": "canale", "канала": "canale", "канал": "canal",
 "камеры": "camere", "Камеры": "Camere", "Камера": "Camera",
 "Объективы": "Obiective", "Кронштейны": "Suporturi", "Кронштейн": "Suport",
 "Блоки питания": "Surse de alimentare", "Блок питания": "Sursa de alimentare",
 "Источники бесперебойного питания": "Surse neintreruptibile (UPS)",
 "Преобразователи напряжения": "Convertoare de tensiune",
 "Зарядные устройства для электромобилей": "Statii de incarcare pentru masini electrice",
 "Зарядные устройства": "Incarcatoare",
 "Аккумуляторы": "Acumulatoare", "АКБ": "Acumulatoare", "ИБП": "UPS", "РИП-ы": "Surse de rezerva",
 "Карты памяти": "Carduri de memorie", "Приемные карты": "Carduri de receptie",
 "Мониторы": "Monitoare", "Рекламные мониторы": "Monitoare publicitare",
 "Мобильный LED экран": "Ecran LED mobil",
 "Прозрачные светодиодные кабинеты": "Cabinete LED transparente",
 "Внутренние светодиодные модули": "Module LED de interior",
 "Уличные светодиодные модули": "Module LED de exterior",
 "Угловые светодиодные модули": "Module LED de colt",
 "Гибкие светодиодные модули": "Module LED flexibile",
 "Светодиодные контроллеры": "Controlere LED",
 "Переносные модуля": "Module portabile",
 "Мини контроллеры": "Mini controlere",
 "Управляющие шлюзы": "Gateway-uri de comanda",
 "(работают через управляющий шлюз)": "(functioneaza prin gateway)",
 "устройства": "dispozitive", "Устройства": "Dispozitive",
 "Умный свет": "Iluminat inteligent",
 "Сетевое оборудование": "Echipamente de retea",
 "Сетевые аксессуары": "Accesorii de retea",
 "Точки доступа": "Puncte de acces",
 "Коммутаторы": "Switch-uri", "свитчи": "switch-uri",
 "управляемые": "administrabile", "WEB управляемые": "administrabile WEB",
 "Серверные шкафы": "Dulapuri server", "Шкафы и стойки": "Dulapuri si rack-uri",
 "Кабинеты": "Cabinete", "Трансформаторы": "Transformatoare",
 "Антенны": "Antene", "Периферийные устройства и аксессуары": "Periferice si accesorii",
 "Датчики к реле серии": "Senzori pentru releele seria",
 "Wi-fi реле": "Relee Wi-Fi", "WiFi Выключатели": "Intrerupatoare WiFi", "WiFi Розетки": "Prize WiFi",
 "Выключатели, розетки и вилки": "Intrerupatoare, prize si stechere",
 "GSM- модуль": "Modul GSM",
 # --- cabluri, tuburi, montaj
 "Аларм кабель": "Cablu de alarma", "Aларм кабель": "Cablu de alarma",
 "Пожарный кабель": "Cablu de incendiu", "Сигнальный кабель": "Cablu de semnal",
 "Кабель питания": "Cablu de alimentare",
 "кабель внутреннего исполнения": "cablu de interior",
 "кабель уличного исполнения": "cablu de exterior",
 "Кабель": "Cablu", "кабель": "cablu", "кабелю": "cablu", "кабелей": "cabluri",
 "Коннекторы для сигнальных кабелей и питания": "Conectori pentru cabluri de semnal si alimentare",
 "Трос для воздушной прокладки кабелей": "Cablu portant pentru pozare aeriana",
 "Гофротруба": "Tub gofrat", "Металлорукав": "Tub metalic flexibil",
 "Поворот гибкий гофрированный": "Cot flexibil gofrat",
 "поворот 90 градусов для труб ПВХ": "cot 90 grade pentru tuburi PVC",
 "соеденитель для труб ПВХ (труба-труба )": "mufa pentru tuburi PVC (tub-tub)",
 "тройник для труб ПВХ": "teu pentru tuburi PVC",
 "держатель трубы(клипса)": "clema de prindere a tubului",
 "Труба ПВХ гладкая (tub plasticПВХ)": "Tub PVC neted",
 "Труба ПЕ (круглая) Teava PE": "Teava PE (rotunda)",
 "Пластиковый канал": "Canal de cablu din plastic",
 "Аксессуары для пластикового канала": "Accesorii pentru canalul de cablu",
 "Крышка на лоток металлический": "Capac pentru jgheab metalic",
 "Неперфорированный": "Neperforat", "Перфорированный": "Perforat",
 # --- generice (la sfirsit)
 "Аксессуары": "Accesorii", "аксессуары": "accesorii",
 "оборудование": "echipamente", "Оборудование": "Echipamente",
 "Питание": "Alimentare", "питания": "alimentare",
 "серия": "seria", "Серия": "Seria", "серии": "seria",
 "Под заказ": "La comanda", "Прочее": "Diverse", "прочее": "diverse",
 "для": "pentru", "и": "si", "с": "cu", "по": "pe", "на": "pentru", "под": "pentru",
}

GLOSAR2 = {
 # --- fixare / suruburi / dibluri
 "Саморезы для крепления гипсокартонных плит к деревянной обрешётке без предварительного сверления": "Autoforante pentru placi de gips-carton pe structura de lemn, fara pregaurire",
 "Саморезы для крепления гипсокартонных плит к металлическому профилю толщиной до": "Autoforante pentru placi de gips-carton pe profil metalic cu grosimea pina la",
 "Саморезы для оконного профиля, крупная резьба. Оцинкованные": "Autoforante pentru profil de fereastra, filet mare, zincate",
 "Саморезы для оконного профиля, мелкая резьба, наконечник-сверло. Оцинкованные": "Autoforante pentru profil de fereastra, filet fin, virf-burghiu, zincate",
 "Оконные саморезы, наконечник-сверло. Оцинкованные": "Autoforante pentru ferestre, virf-burghiu, zincate",
 "Саморезы для гипсокартона по дереву": "Autoforante pentru gips-carton pe lemn",
 "Саморезы для гипсокартона по металлу": "Autoforante pentru gips-carton pe metal",
 "Саморезы металл-металл со сверлом": "Autoforante metal-metal cu burghiu",
 "Саморезы": "Autoforante",
 "Дюбель полипропиленовый без шурупа, трехстороннего распора": "Diblu din polipropilena fara surub, cu expansiune pe trei parti",
 "Дюбель распорный с шурупом для дерева с шестигранной головкой": "Diblu cu expansiune si surub de lemn cu cap hexagonal",
 "Дюбель распорный с шурупом полукруглый крючек": "Diblu cu expansiune si surub cu cirlig semirotund",
 "Дюбель с шурупом для быстрого монтажа, с бортиком, полипропилен": "Diblu cu surub pentru montaj rapid, cu guler, polipropilena",
 "Дюбель с шурупом для быстрого монтажа, универсальный, полипропилен": "Diblu cu surub pentru montaj rapid, universal, polipropilena",
 "Дюбель с шурупом трехстороннего распора": "Diblu cu surub, expansiune pe trei parti",
 "Дюбеля трехстороннего распора с шурупом с шестигранной головкой": "Dibluri cu expansiune pe trei parti si surub cu cap hexagonal",
 "Дюбеля трехстороннего распора с полукруглым крюком": "Dibluri cu expansiune pe trei parti si cirlig semirotund",
 "Дюбеля с шурупом трехстороннего распора": "Dibluri cu surub, expansiune pe trei parti",
 "Дюбеля трехстороннего распора": "Dibluri cu expansiune pe trei parti",
 "Дюбеля быстрого монтажа с бортиком": "Dibluri pentru montaj rapid, cu guler",
 "Дюбеля быстрого монтажа универсальные": "Dibluri universale pentru montaj rapid",
 'Дюбеля "DRIVA" для гипсокартона, без шурупа, нейлон': 'Dibluri "DRIVA" pentru gips-carton, fara surub, nailon',
 'Дюбеля "DRIVA" металлические': 'Dibluri "DRIVA" metalice',
 "Дюбеля": "Dibluri", "Дюбель": "Diblu",
 "Болт с полной резьбой, оцинкованный DIN 933, класс прочности 8.8 и 6.8": "Surub cu filet complet, zincat DIN 933, clasa de rezistenta 8.8 si 6.8",
 "Болты с полной резьбой, оцинкованные": "Suruburi cu filet complet, zincate",
 "Винт с метрической резьбой и конусной головкой DIN 965": "Surub cu filet metric si cap conic DIN 965",
 "Винты с буром под потай, оцинкованные": "Suruburi autoforante cu cap inecat, zincate",
 "Винты с буром, оцинкованные": "Suruburi autoforante, zincate",
 "Гайка шестигранная, оцинкованная DIN 934": "Piulita hexagonala, zincata DIN 934",
 "Гайки шестигранные, оцинкованные": "Piulite hexagonale, zincate",
 "Шайба увеличенная для деревянных конструкций, оцинкованная DIN 9021": "Saiba largita pentru constructii din lemn, zincata DIN 9021",
 "Шайбы увеличенная оцинкованные": "Saibe largite zincate",
 "Шпилька резьбовая оцинкованная": "Tija filetata zincata",
 "Канатные зажимы оцинкованные": "Cleme de cablu zincate",
 "Канатный зажим оцинкованный DIN 741": "Clema de cablu zincata DIN 741",
 "Талреп кованный крюк-кольцо, оцинкованный": "Intinzator forjat cirlig-inel, zincat",
 "Талрепы крюк-кольцо": "Intinzatoare cirlig-inel",
 "Самоклеящаяся площадка для крепления стяжки (1 уп. - 100 шт)": "Suport autoadeziv pentru coliere (1 pachet - 100 buc.)",
 "Стяжки кабельные из нейлона": "Coliere de cablu din nailon",
 "Стяжка для маркировки кабеля": "Colier pentru marcarea cablului",
 "Стяжной пластиковый хомут, нейлон": "Colier de plastic, nailon",
 "Крепеж для труб полипропиленовый": "Bride pentru tevi, polipropilena",
 "Крепежи для труб полипропиленовые": "Bride pentru tevi din polipropilena",
 "Натяжной зажим для уличного кабеля": "Clema de intindere pentru cablu de exterior",
 "Зажим для кабеля / гофротрубы R типа": "Clema pentru cablu / tub gofrat tip R",
 "Клипса прямоугольная под кабель белая": "Clema dreptunghiulara pentru cablu, alba",
 "Клипсы прямоугольные под кабель": "Cleme dreptunghiulare pentru cablu",
 # --- canal de cablu / tuburi
 "Внешняя заглушка для кабель-канала": "Capac exterior pentru canal de cablu",
 "Т-образный соединитель для кабель-канала": "Conector in T pentru canal de cablu",
 "Угловой соединитель 90° для кабель-канала": "Conector de colt 90° pentru canal de cablu",
 "Соединитель для кабель-канала": "Conector pentru canal de cablu",
 "Уголок внешний для кабель-канала": "Colt exterior pentru canal de cablu",
 "Уголок внутрений для кабель-канала": "Colt interior pentru canal de cablu",
 "Кабельные каналы": "Canale de cablu",
 "Колено 90 градусов для труб ПВХ": "Cot 90 grade pentru tuburi PVC",
 "Муфта для труб ПВХ": "Mufa pentru tuburi PVC",
 "Печатки с точками ПВХ": "Doze PVC cu puncte",
 "Труба ПВХ": "Tub PVC", "Гофрированные трубы": "Tuburi gofrate",
 "Трубка термоусадочная": "Tub termocontractabil",
 "Металлические коробки": "Doze metalice",
 "Распределительные коробки": "Doze de derivatie",
 "Кронштейны и распределительные коробки": "Suporturi si doze de derivatie",
 "Изоленты": "Benzi izolatoare", "Изолента": "Banda izolatoare",
 "Полиуретановая пена": "Spuma poliuretanica", "Силикон": "Silicon", "Клей": "Adeziv",
 # --- scule electrice si gradina
 "Аккумуляторный шуруповерт": "Masina de insurubat cu acumulator",
 "Электрический шуруповерт": "Masina de insurubat electrica",
 "Ударный Дрель": "Bormasina cu percutie",
 "Угловые шлифмашины": "Polizoare unghiulare",
 "Шлифовальные машины": "Masini de slefuit",
 "Полировальные машины": "Masini de polisat",
 "Гравировальные машины": "Masini de gravat",
 "Подметальные машины": "Masini de maturat",
 "Миксеры строительные": "Mixere pentru constructii",
 "Отбойные молотки": "Ciocane demolatoare",
 "Перфораторы": "Ciocane rotopercutoare",
 "Пилы торцовочные": "Ferastraie pentru taieri unghiulare",
 "Сабельные пилы": "Ferastraie sabie",
 "Ручные циркулярки": "Ferastraie circulare manuale",
 "Электропилы": "Ferastraie electrice", "Бензопилы": "Motoferastraie",
 "Плиткорезы": "Masini de taiat gresie", "Лобзик": "Ferastrau pendular",
 "Рубанки": "Rindele", "Реноваторы": "Unelte multifunctionale", "Фрезеры": "Freze",
 "Стационарные Сверлильные Станки": "Masini de gaurit stationare",
 "Деревообрабатывающие станки": "Masini de prelucrat lemnul",
 "Токарные станки": "Strunguri", "Точильные станки": "Masini de ascutit",
 "Сверла по бетону тип SDS plus": "Burghie pentru beton tip SDS plus",
 "Сверла по металлу": "Burghie pentru metal",
 "Конусные сверла": "Burghie conice", "Сверло": "Burghiu", "Сверла": "Burghie",
 "Абразивные диски": "Discuri abrazive", "Алмазные диски": "Discuri diamantate",
 "Диски для камня": "Discuri pentru piatra", "Диски по дереву": "Discuri pentru lemn",
 "Фены индустриальные": "Pistoale cu aer cald", "Паяльники": "Ciocane de lipit",
 "Краскораспылители": "Pistoale de vopsit",
 "Промышленные пылесосы": "Aspiratoare industriale",
 "Мойки высокого давления": "Masini de spalat cu presiune",
 "Аксессуары для мойки высокого давления": "Accesorii pentru masini de spalat cu presiune",
 "Аксессуары для комрпессора": "Accesorii pentru compresor",
 "Аксессуары для мотопомп": "Accesorii pentru motopompe",
 "Компрессоры": "Compresoare", "Генераторы": "Generatoare",
 "Бетономешалки": "Betoniere", "Бетонные вибраторы": "Vibratoare pentru beton",
 "Виброплита бензо": "Placa vibratoare pe benzina",
 "Мотобуры": "Motoburghie", "Мотокультиватор": "Motocultivator",
 "Мотопомпы": "Motopompe", "Мототриммеры": "Motocoase", "Электротриммеры": "Trimere electrice",
 "Газонокосилки": "Masini de tuns iarba", "Кусторезы": "Foarfeci de tuns gard viu",
 "Воздуходувы": "Suflante", "Измельчители веток": "Tocatoare de crengi",
 "Измельчители фруктов и овощей": "Tocatoare de fructe si legume",
 "Измельчители": "Tocatoare", "Грануляторы": "Granulatoare", "Мельницы": "Mori",
 "Молотильщики": "Batoze", "Сеялки": "Semanatori", "Инкубаторы": "Incubatoare",
 "Машинка для стрижки овец": "Masina de tuns oi",
 "ВИНОГРАДНЫЙ ПРЕСС": "Presa de struguri",
 "Газовые грили": "Gratare pe gaz", "Подставки газа": "Suporturi pentru butelie",
 "Тачки": "Roabe", "Колеса для тачки": "Roti pentru roaba",
 "Топоры": "Topoare", "Тиски": "Menghine", "Тросы": "Cabluri de otel",
 "Ручной лебедка": "Troliu manual", "Электрические лебедки": "Trolii electrice",
 "Гидравлические домкраты": "Cricuri hidraulice",
 "Наборы инструментов": "Truse de scule", "Ящик для инструментов": "Cutie de scule",
 "Электроинструменты": "Scule electrice", "Электродвигатели": "Motoare electrice",
 "Двигатели": "Motoare", "Удлинители": "Prelungitoare",
 "Лазерный уровень": "Nivela laser", "Маска защитная": "Masca de protectie",
 "Леска для мотокосы": "Fir pentru motocoasa",
 "Запорные манипуляторы": "Manipulatoare de inchidere",
 "пневматические степлеры, нелеры": "capsatoare si pistoale de cuie pneumatice",
 "Стелажи": "Rafturi", "Стяжки": "Coliere",
 # --- sudura
 "Аргоновые сварочные аппараты": "Aparate de sudura cu argon",
 "Инверторные сварочные аппараты ММА (електродные)": "Aparate de sudura invertor MMA (cu electrod)",
 "Сварочные полуавтоматы": "Aparate de sudura semiautomate",
 "Электроды и сварочная проволока": "Electrozi si sirma de sudura",
 "Вырубные ножницы по металлу": "Foarfece electrice pentru tabla",
 # --- pompe / apa
 "Вибрационные насосы": "Pompe vibratoare", "Дренажные насосы": "Pompe de drenaj",
 "Циркуляционные насосы": "Pompe de circulatie", "Глубинный насос": "Pompa de adincime",
 "Гидрофоры": "Hidrofoare", "Спрай пурификатор": "Spray purificator",
 # --- audio / avertizare
 "Колонки настенные": "Boxe de perete", "Колонки потолочные": "Boxe de tavan",
 "Колонки уличные": "Boxe de exterior", "Динамики": "Difuzoare",
 "Микрофоны": "Microfoane", "Микрофон": "Microfon", "Мегафон": "Megafon", "Рупор": "Portavoce",
 "Микшерные звукоусилители": "Amplificatoare-mixer",
 "Многозонные усилители": "Amplificatoare multizona",
 "Однозонные усилители": "Amplificatoare monozona",
 "Усилитель сетевой": "Amplificator de retea",
 "Усилители": "Amplificatoare", "Регуляторы громкости": "Regulatoare de volum",
 "Аналоговая система оповещения": "Sistem analogic de avertizare",
 "Оповещение": "Avertizare",
 "Панели экстренного вызова": "Panouri de apel de urgenta",
 # --- paza / video
 "Беспроводные охранные системы": "Sisteme de securitate wireless",
 "Гибридные охранные системы": "Sisteme de securitate hibride",
 "Гибридные видеорегистраторы": "DVR/NVR hibride",
 "Охранные системы": "Sisteme de securitate",
 "Охранные панели": "Centrale de efractie", "Охранные пакеты": "Pachete de securitate",
 "Охранные датчики": "Detectoare de efractie", "Охранные извещатели": "Detectoare de efractie",
 "Радиоканальные охранные извещатели для установки на улице": "Detectoare de efractie radio pentru exterior",
 "Радиоканальные охранные извещатели": "Detectoare de efractie radio",
 "Радиоканальные контрольные панели": "Centrale radio",
 "Радиооборудование": "Echipamente radio", "Радиопередатчики": "Radioemitatoare",
 "Беспроводные датчики": "Senzori wireless", "Магнитные датчики": "Contacte magnetice",
 "Датчики охранной сигнализациии - Разбитие стекла": "Detectoare de efractie - spargere de geam",
 "Внутренние сигнализации": "Sirene de interior", "Наружные сигнализации": "Sirene de exterior",
 "Наружные сирены": "Sirene de exterior",
 "Коммуникаторы": "Comunicatoare", "Коммуникационные модули": "Module de comunicatie",
 "Концентраторы": "Concentratoare", "Расширители": "Extensii",
 "Модули и расширители": "Module si extensii",
 "Активные инфракрасные барьеры различной дальности": "Bariere infrarosu active, diverse distante",
 "Контроль вторжения": "Detectie efractie", "Контроль температуры": "Control temperatura",
 "Комплексные решения для контроля доступа и измерения температуры.": "Solutii complete de control acces si masurare a temperaturii",
 "Парковка - Контроль въезда и выезда": "Parcare - control intrare si iesire",
 "Комплекты видеонаблюдения": "Kituri de supraveghere video",
 "Аксессуары для видеонаблюдения и прочее": "Accesorii pentru supraveghere video si diverse",
 "Видео наблюдение": "Supraveghere video", "видеонаблюдения": "supraveghere video",
 "Автомобильные регистраторы": "Camere auto (DVR)",
 "Автономные камеры для установки в дикой среде": "Camere autonome pentru mediul salbatic",
 "Камеры c солнечной панелью": "Camere cu panou solar",
 "Камеры Micro или Pinhole": "Camere Micro sau Pinhole",
 "Камеры профессиональной серии": "Camere din seria profesionala",
 "Аналоговые и HD-TVI камеры": "Camere analogice si HD-TVI",
 "Видеокамеры": "Camere video",
 "Ручные термографические камеры": "Camere termografice portabile",
 "Рекомендуемые аксессуары для термографических камер": "Accesorii recomandate pentru camere termografice",
 "Термальные камеры серии": "Camere termice seria",
 "Кронштейны для купольных камер": "Suporturi pentru camere dome",
 "Кронштейны для цилиндрических камер": "Suporturi pentru camere bullet",
 "Кронштейны для Cube камер": "Suporturi pentru camere Cube",
 "Кронштейны для PTZ Speed Dome камер": "Suporturi pentru camere PTZ Speed Dome",
 "Универсальные кронштейны": "Suporturi universale",
 "Универсальные подставки": "Stative universale",
 "Подставки": "Stative",
 "Сетевые NVR": "NVR de retea",
 "Клавиатуры для панелей": "Tastaturi pentru centrale",
 "Панели": "Centrale", "панели": "centrale",
 "Решения для LCD видео стен": "Solutii pentru videowall LCD",
 "Решения для Retail и HoReCa": "Solutii pentru Retail si HoReCa",
 "Решения с технологией": "Solutii cu tehnologia",
 "Домофония": "Interfonie", "Метаком": "Metakom",
 "Активное оптическое оборудование": "Echipamente optice active",
 "Оптический кабель": "Cablu optic",
 "Мониторинг транспорта": "Monitorizarea transportului",
 "Мобильные устройства": "Dispozitive mobile",
 "Устройства хранения": "Dispozitive de stocare", "Хранение данных": "Stocare de date",
 "Фильтры питания": "Filtre de alimentare",
 "Пускозарядное устройство": "Robot de pornire si incarcare",
 "Ваучеры": "Vouchere", "Тестеры": "Testere", "Коннекторы": "Conectori",
 "В камерах Ezviz рекомендуются к установке только фирменные карты памяти MicroSD":
   "In camerele Ezviz se recomanda doar carduri MicroSD originale",
 "Комплекты Secolink: проводная панель + клавиатура": "Kituri Secolink: centrala cu fir + tastatura",
 "Терминал блок (двусторонний)": "Bloc terminal (bilateral)",
 "Терминал блок 5*1 (односторонний)": "Bloc terminal 5*1 (unilateral)",
 "Кнопки Тревоги, GSM модули": "Butoane de panica, module GSM",
 "IT продукция": "Produse IT", "Проектное": "Pentru proiecte", "Под проекты": "Pentru proiecte",
 "Другие": "Altele", "Другое": "Altele", "ОС": "OS",
 "Hartie втз": "Hartie VTZ",
 "Подарочные сертификаты": "Certificate cadou",
 "Столы,стулья,кресла": "Mese, scaune, fotolii",
 "Столы": "Mese", "стулья": "scaune", "кресла": "fotolii",
 "СКУД и Домофония": "Control acces si interfonie",
 "модули": "module", "Модули": "Module", "системы": "sisteme", "Системы": "Sisteme",
 "датчики": "detectoare", "Датчики": "Detectoare",
 "камер": "camere", "Решения": "Solutii", "решения": "solutii",
 "Гибридные": "Hibride", "гибридные": "hibride",
 "Внутренние": "De interior", "Уличные": "De exterior", "уличные": "de exterior",
 "Наружные": "De exterior", "наружные": "de exterior",
 "оцинкованные": "zincate", "оцинкованный": "zincat", "оцинкованная": "zincata",
 "сигнализации": "alarma", "Сирены": "Sirene",
 "серия": "seria", "Cерия": "seria", "Серия": "Seria", "Cерии": "seria",
 "ерия": "seria",
}

GLOSAR = dict(GLOSAR2, **GLOSAR)

CHIR = re.compile(r"[А-Яа-яЁё]")
W = r"[0-9A-Za-zА-Яа-яЁёĂÂÎȘȚăâîșț]"


def _variants(ru: str, ro: str):
    yield ru, ro
    up = ru[:1].upper() + ru[1:]
    if up != ru:
        yield up, ro[:1].upper() + ro[1:]
    low = ru[:1].lower() + ru[1:]
    if low != ru:
        yield low, ro[:1].lower() + ro[1:]


_RULES = []
for _ru, _ro in sorted(GLOSAR.items(), key=lambda kv: -len(kv[0])):
    for a, b in _variants(_ru, _ro):
        _RULES.append((re.compile(r"(?<!%s)%s(?!%s)" % (W, re.escape(a), W)), b))


# RO: omoglife — litere chirilice scapate intr-un cuvint latin («Ciocanе», «Motoсultoare»)
_OMO = str.maketrans({"а":"a","е":"e","о":"o","р":"p","с":"c","у":"y","х":"x","А":"A","В":"B",
                      "Е":"E","К":"K","М":"M","Н":"H","О":"O","Р":"P","С":"C","Т":"T","У":"Y","Х":"X"})


def _fara_omoglife(s: str) -> str:
    """RO: curata litera chirilica izolata dintr-un cuvint altfel latin."""
    def fix(m):
        w = m.group(0)
        lat = sum(1 for c in w if "a" <= c.lower() <= "z")
        chi = sum(1 for c in w if "\u0410" <= c <= "\u044f")
        return w.translate(_OMO) if lat and chi and chi <= 2 else w
    return re.sub(r"[0-9A-Za-z\u0410-\u044f]+", fix, s)


# RO: in romana determinantul sta DUPA substantiv: «Cablu UTP», nu «UTP Cablu».
_ORDINE = [(re.compile(r"^(UTP|FTP|RG|SFTP|Aларм|IP|Optic)\s+(Cablu|cablu)\b", re.I),
            lambda m: "Cablu " + m.group(1).upper()),
           (re.compile(r"^(IP|Analog|TVI|HD-TVI|Wireless|Termice)\s+(camere|Camere)\b", re.I),
            lambda m: "Camere " + m.group(1).upper()),
           (re.compile(r"^(TVI|HD-TVI|IP|Analog)\s+DVR/NVR\b", re.I),
            lambda m: "DVR/NVR " + m.group(1).upper()),
           (re.compile(r"^(PoE|POE)[- ]?(Switch-uri|switch-uri)\b"),
            lambda m: "Switch-uri PoE")]
# RO: cele doua denumiri TAIATE de coloana bazei, traduse intreg
_INTREGI = {
 "ППКП на 2 кольцевых шлейфа с расширением до 16 колец Соответствие Европейским Ст":
   "Centrala de incendiu cu 2 bucle, extensibila pina la 16 bucle, conform standardelor europene",
 "Саморезы для крепления гипсокартонных плит к деревянной обрешётке без предварите":
   "Autoforante pentru fixarea placilor de gips-carton pe structura de lemn, fara pregaurire",
}


def tradu(name: str) -> str:
    if name in _INTREGI:
        return _INTREGI[name]
    out = _fara_omoglife(name)
    for rx, ro in _RULES:
        out = rx.sub(ro.replace("\\", "\\\\"), out)
    # RO: cozile numerice rusesti («16-ти канальные» -> «16 canale») si unitatile
    out = re.sub(r"(\d+)\s*-\s*(ти|х|ми|и)\b", r"\1", out)
    out = re.sub(r"(\d)\s*В\b", r"\1V", out)
    out = out.replace("Импульс", "Impuls")
    # RO: denumirile lungi sint TAIATE de coloana bazei — traducem si cozile rupte
    for ru, ro in ((" Соответст", " conform"), (" Соот", " conform"),
                   ("крепления гипсокартонных плит к деревянной обре",
                    "fixarea placilor de gips-carton pe structura de lemn"),
                   ("крепления гипсокартонных плит к металлическому проф",
                    "fixarea placilor de gips-carton pe profil metalic")):
        out = out.replace(ru, ro)
    out = re.sub(r"\s+", " ", out).strip(" -–—,")
    for rx, f in _ORDINE:
        out = rx.sub(f, out)
    return _substantiv_in_fata(out)


# RO: cuvintele dupa care substantivul NU se muta: acolo forma e deja romaneasca
#     («Canale de cablu», «Cleme pentru cablu»).
_LEGATURI = {"de", "pentru", "cu", "la", "din", "sub", "pe", "si", "fara"}


def _substantiv_in_fata(s: str) -> str:
    """RO: «Dome camere» -> «Camere Dome», «HDMI cablu» -> «Cablu HDMI».
    Din rusa substantivul iese la coada; in romana el sta primul."""
    m = re.match(r"^(.+?)\s+(camere|cablu|switch-uri)$", s, re.I)
    if not m:
        return s.replace("PoE-Switch-uri", "Switch-uri PoE")
    cap, subst = m.group(1).strip(), m.group(2)
    if cap.split()[-1].lower() in _LEGATURI:
        return s
    return subst[:1].upper() + subst[1:] + " " + cap


def ramine_rus(s: str) -> bool:
    return bool(CHIR.search(s))
