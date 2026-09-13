-- RO: setarile de sistem TMS_SYSS tip XM pe care le cere PKG_EDI_XML (vendor) la
--     importul pachetului 12103, copiate dupa modelul FPROIECT / BMPUBLIC de pe cloudbd.
--     cod 1 = statusurile TMDB_XML_PACKAGE.STATUS_DOC (cod1 6: UM = interval zile pentru
--     data facturii, FPROIECT 364), cod 3 = forma documentului (0 NN, 1 TTN).
--     Idempotent (MERGE), nu atinge rindurile deja existente (cod 4 al OfficePlus).
DECLARE
  PROCEDURE m(p_cod NUMBER, p_cod1 NUMBER, p_den VARCHAR2, p_um VARCHAR2 DEFAULT NULL) IS
  BEGIN
    MERGE INTO TMS_SYSS s USING (SELECT 'XM' tip, p_cod cod, p_cod1 cod1 FROM dual) n
    ON (s.TIP = n.tip AND s.COD = n.cod AND s.COD1 = n.cod1)
    WHEN NOT MATCHED THEN INSERT (TIP, COD, COD1, DENUMIREA, UM) VALUES ('XM', p_cod, p_cod1, p_den, p_um);
  END;
BEGIN
  m(1, 0,  'Statutul facturii incarcate din XML (e-Factura)');
  m(1, 1,  'Factura corecta');
  m(1, 2,  'Factura dublata in baza (1209)');
  m(1, 3,  'Tip de document incorect');
  m(1, 4,  'Seria sau numarul facturii incorect');
  m(1, 5,  'Factura dublata in baza (12102)');
  m(1, 6,  'Data emiterii facturii in afara intervalului (UM = zile)', '364');
  m(1, 7,  'Codul furnizorului negasit');
  m(1, 8,  'Codul subdiviziunii cumparatorului incorect');
  m(1, 9,  'Factura neactuala (era in lista, lipseste din XML)');
  m(1, 10, 'Factura dublata in XML');
  m(1, 11, 'Probleme la completarea 1231');
  m(1, 12, 'Factura dublata in baza (1231)');
  m(1, 13, 'Factura dublata in baza (12103)');
  m(1, 14, 'Factura dublata in baza');
  m(1, 15, 'Seria si data deja completate in F');
  m(3, 0,  'NN');
  m(3, 1,  'TTN');
  COMMIT;
END;
/
