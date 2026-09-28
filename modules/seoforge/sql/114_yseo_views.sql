-- =====================================================================
-- RO: Vederile conturului SEOForge. Codul aplicatiei citeste doar de aici:
--     agregarea si conversia valutara raman in baza.
-- EN: SEOForge contour views. Application code reads only from here:
--     aggregation and currency conversion stay in the database.
-- =====================================================================

-- ---------------------------------------------------------------------
-- RO: Plan si fapt pe perioada, articol, canal si site.
-- EN: Plan and fact by period, article, channel and site.
--
-- RO: Imbinarea este FULL OUTER dinadins: cheltuiala fara plan trebuie sa
--     apara in grila, altfel depasirea ar disparea tacut din raport.
-- EN: The join is FULL OUTER on purpose: spend without a plan must show up
--     in the grid, otherwise an overrun would silently vanish from the report.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW VSEO_BUDGET_PLANFACT AS
SELECT COALESCE(p.PERIOD, f.PERIOD)                  AS PERIOD,
       COALESCE(p.ARTICLE_COD1, f.ARTICLE_COD1)      AS ARTICLE_COD1,
       COALESCE(p.CHANNEL_COD1, f.CHANNEL_COD1)      AS CHANNEL_COD1,
       COALESCE(p.SITE_COD, f.SITE_COD)              AS SITE_COD,
       NVL(p.PLAN_SUMA, 0)                           AS PLAN_SUMA,
       NVL(f.FACT_SUMA, 0)                           AS FACT_SUMA,
       NVL(p.PLAN_SUMA, 0) - NVL(f.FACT_SUMA, 0)     AS REST_SUMA,
       ROUND(NVL(f.FACT_SUMA, 0) * 100
             / NULLIF(p.PLAN_SUMA, 0), 2)            AS DONE_PCT,
       CASE WHEN NVL(f.FACT_SUMA, 0) > NVL(p.PLAN_SUMA, 0)
            THEN 1 ELSE 0 END                        AS IS_OVERBUDGET
FROM   (SELECT PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD,
               SUM(PK_SEO_UTIL.TO_MDL(PLAN_SUMA, VALUTA, NULL)) AS PLAN_SUMA
        FROM   YSEO_BUDGET_PLAN
        GROUP  BY PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD) p
FULL OUTER JOIN
       (SELECT PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD,
               SUM(SUMA_MDL) AS FACT_SUMA
        FROM   YSEO_SPEND_FACT
        GROUP  BY PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD) f
ON     p.PERIOD = f.PERIOD
   AND p.ARTICLE_COD1 = f.ARTICLE_COD1
   AND NVL(p.CHANNEL_COD1, -1) = NVL(f.CHANNEL_COD1, -1)
   AND NVL(p.SITE_COD, -1) = NVL(f.SITE_COD, -1);

-- ---------------------------------------------------------------------
-- RO: Eficienta pe canal si perioada. NULLIF apara impartirea la zero:
--     o campanie fara clicuri sau fara cheltuiala este normala.
-- EN: Efficiency by channel and period. NULLIF guards division by zero:
--     a campaign with no clicks or no spend is a normal case.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW VSEO_CHANNEL_ROI AS
SELECT s.PERIOD                                       AS PERIOD,
       s.CHANNEL_COD1                                 AS CHANNEL_COD1,
       d.CODE                                         AS CHANNEL_CODE,
       d.NAME_RU                                      AS CHANNEL_NAME_RU,
       d.NAME_RO                                      AS CHANNEL_NAME_RO,
       d.NAME_EN                                      AS CHANNEL_NAME_EN,
       s.SITE_COD                                     AS SITE_COD,
       SUM(s.SUMA_MDL)                                AS SPEND_SUMA,
       SUM(s.CLICKS)                                  AS CLICKS,
       SUM(s.IMPRESSIONS)                             AS IMPRESSIONS,
       SUM(s.CONVERSIONS)                             AS CONVERSIONS,
       SUM(s.REVENUE)                                 AS REVENUE,
       ROUND((SUM(s.REVENUE) - SUM(s.SUMA_MDL))
             / NULLIF(SUM(s.SUMA_MDL), 0), 4)         AS ROI,
       ROUND(SUM(s.SUMA_MDL) / NULLIF(SUM(s.CLICKS), 0), 4)      AS CPC,
       ROUND(SUM(s.SUMA_MDL) / NULLIF(SUM(s.CONVERSIONS), 0), 4) AS CPA,
       ROUND(SUM(s.CLICKS) * 100
             / NULLIF(SUM(s.IMPRESSIONS), 0), 4)      AS CTR_PCT
FROM   YSEO_SPEND_FACT s
JOIN   YSEO_DICT d ON d.COD1 = s.CHANNEL_COD1
GROUP  BY s.PERIOD, s.CHANNEL_COD1, d.CODE,
          d.NAME_RU, d.NAME_RO, d.NAME_EN, s.SITE_COD;

-- ---------------------------------------------------------------------
-- RO: Site-ul cu indicatorii perioadei curente - baza pentru placile
--     din ecranul de portofoliu.
-- EN: Site with current-period indicators - the source for the tiles on
--     the portfolio screen.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW VSEO_SITE AS
SELECT s.COD                                          AS COD,
       s.DOMAIN                                       AS DOMAIN,
       s.LOCALES                                      AS LOCALES,
       s.GEO                                          AS GEO,
       s.NICHE                                        AS NICHE,
       s.DIV                                          AS DIV,
       s.TONE_OF_VOICE                                AS TONE_OF_VOICE,
       s.GUARDRAILS                                   AS GUARDRAILS,
       s.KPI_TARGET                                   AS KPI_TARGET,
       s.ISARHIV                                      AS ISARHIV,
       NVL(c.ACTIVE_CAMPAIGNS, 0)                     AS ACTIVE_CAMPAIGNS,
       NVL(f.SPEND_SUMA, 0)                           AS SPEND_CURRENT,
       NVL(p.PLAN_SUMA, 0)                            AS PLAN_CURRENT,
       NVL(p.PLAN_SUMA, 0) - NVL(f.SPEND_SUMA, 0)     AS REST_CURRENT
FROM   YSEO_SITE s
LEFT   JOIN (SELECT SITE_COD, COUNT(*) AS ACTIVE_CAMPAIGNS
             FROM   YSEO_CAMPAIGN
             WHERE  ISARHIV = 0 AND STATUS = 'ACTIVE'
             GROUP  BY SITE_COD) c ON c.SITE_COD = s.COD
LEFT   JOIN (SELECT SITE_COD, SUM(SUMA_MDL) AS SPEND_SUMA
             FROM   YSEO_SPEND_FACT
             WHERE  PERIOD = TO_CHAR(SYSDATE, 'YYYY-MM')
             GROUP  BY SITE_COD) f ON f.SITE_COD = s.COD
LEFT   JOIN (SELECT SITE_COD,
                    SUM(PK_SEO_UTIL.TO_MDL(PLAN_SUMA, VALUTA, NULL)) AS PLAN_SUMA
             FROM   YSEO_BUDGET_PLAN
             WHERE  PERIOD = TO_CHAR(SYSDATE, 'YYYY-MM')
             GROUP  BY SITE_COD) p ON p.SITE_COD = s.COD;

-- ---------------------------------------------------------------------
-- RO: Campania cu plan, fapt si rest. Faptul se aduna dupa CAMP_COD.
-- EN: Campaign with plan, fact and remainder. Fact is summed by CAMP_COD.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW VSEO_CAMPAIGN AS
SELECT c.COD                                          AS COD,
       c.CAMP_CODE                                    AS CAMP_CODE,
       c.SITE_COD                                     AS SITE_COD,
       s.DOMAIN                                       AS SITE_DOMAIN,
       c.NAME_RU                                      AS NAME_RU,
       c.NAME_RO                                      AS NAME_RO,
       c.NAME_EN                                      AS NAME_EN,
       c.PROMO_TYPE_COD1                              AS PROMO_TYPE_COD1,
       d.CODE                                         AS PROMO_TYPE_CODE,
       c.DISCOUNT_VALUE                               AS DISCOUNT_VALUE,
       c.PROMO_CODE                                   AS PROMO_CODE,
       c.SCOPE_KIND                                   AS SCOPE_KIND,
       c.DATE_START                                   AS DATE_START,
       c.DATE_END                                     AS DATE_END,
       c.LIMIT_QTY                                    AS LIMIT_QTY,
       c.LIMIT_SUM                                    AS LIMIT_SUM,
       c.BUDGET_PLAN                                  AS BUDGET_PLAN,
       c.KPI_TARGET                                   AS KPI_TARGET,
       c.LEGAL_TEXT_REF                               AS LEGAL_TEXT_REF,
       c.STATUS                                       AS STATUS,
       c.ISARHIV                                      AS ISARHIV,
       NVL(f.FACT_SUMA, 0)                            AS FACT_SUMA,
       c.BUDGET_PLAN - NVL(f.FACT_SUMA, 0)            AS REST_SUMA,
       NVL(f.CLICKS, 0)                               AS CLICKS,
       NVL(f.CONVERSIONS, 0)                          AS CONVERSIONS,
       NVL(f.REVENUE, 0)                              AS REVENUE
FROM   YSEO_CAMPAIGN c
JOIN   YSEO_SITE s ON s.COD = c.SITE_COD
JOIN   YSEO_DICT d ON d.COD1 = c.PROMO_TYPE_COD1
LEFT   JOIN (SELECT CAMP_COD,
                    SUM(SUMA_MDL)    AS FACT_SUMA,
                    SUM(CLICKS)      AS CLICKS,
                    SUM(CONVERSIONS) AS CONVERSIONS,
                    SUM(REVENUE)     AS REVENUE
             FROM   YSEO_SPEND_FACT
             WHERE  CAMP_COD IS NOT NULL
             GROUP  BY CAMP_COD) f ON f.CAMP_COD = c.COD;
