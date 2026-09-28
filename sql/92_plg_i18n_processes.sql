-- ============================================================
-- Планограммы: строки интерфейса раздела «Бизнес-процессы» (RU / RO / EN)
-- ============================================================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.processes',  'nav', 'Бизнес-процессы', 'Procese de business', 'Business processes');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.title',       'ui', 'Бизнес-процессы',  'Procese de business', 'Business processes');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.subtitle',    'ui', 'Схемы в нотации BPMN, формат draw.io. Клик по фигуре открывает соответствующий раздел модуля', 'Diagrame BPMN în format draw.io. Clic pe figură deschide secțiunea corespunzătoare', 'BPMN diagrams in draw.io format. Clicking a shape opens the matching module section');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.all',         'ui', 'Все процессы',     'Toate procesele',     'All processes');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.nodes',       'ui', 'Узлов',            'Noduri',              'Nodes');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.import',      'ui', 'Импорт .drawio',   'Import .drawio',      'Import .drawio');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.export',      'ui', 'Скачать .drawio',  'Descarcă .drawio',    'Download .drawio');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.openDrawio',  'ui', 'Открыть в draw.io','Deschide în draw.io', 'Open in draw.io');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.importHint',  'ui', 'Вставьте XML схемы или выберите файл .drawio, выгруженный из diagrams.net', 'Lipiți XML-ul sau alegeți fișierul .drawio exportat din diagrams.net', 'Paste the diagram XML or pick a .drawio file exported from diagrams.net');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.orFile',      'ui', 'или файл',         'sau fișier',          'or file');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.badXml',      'ui', 'Схема не разбирается как XML', 'Diagrama nu poate fi citită ca XML', 'The diagram cannot be parsed as XML');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.goto',        'ui', 'перейти в раздел', 'mergi la secțiune',   'go to section');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.clickHint',   'ui', 'фигуры кликабельны', 'figurile sunt clicabile', 'shapes are clickable');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.event',       'ui', 'событие',          'eveniment',           'event');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.task',        'ui', 'задача',           'sarcină',             'task');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.gateway',     'ui', 'шлюз / решение',   'poartă / decizie',    'gateway / decision');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('bp.end',         'ui', 'завершение',       'finalizare',          'end');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.docs',        'ui', 'Документация',     'Documentație',        'Documentation');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.presentation','ui', 'Презентация',      'Prezentare',          'Presentation');

COMMIT;
