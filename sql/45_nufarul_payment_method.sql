-- Payment metadata table (companion to blockchain ledger)
-- NUF_ORDERS_LEDGER is a blockchain table and cannot be altered.
-- Payment method and client details are stored separately.
CREATE TABLE NUF_ORDER_PAYMENT (
    ORDER_ID        NUMBER        NOT NULL,
    ORDER_NUMBER    VARCHAR2(50),
    CLIENT_NAME     VARCHAR2(200),
    CLIENT_PHONE    VARCHAR2(50),
    PAYMENT_METHOD  VARCHAR2(50)  DEFAULT 'cash' NOT NULL,
    NOTES           VARCHAR2(1000),
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT PK_NUF_ORDER_PAYMENT PRIMARY KEY (ORDER_ID)
)
/
COMMIT
/
