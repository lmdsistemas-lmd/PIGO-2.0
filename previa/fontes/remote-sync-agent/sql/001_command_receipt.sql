/* Install once in a TEST ERP first, using the ERP database administrator.
   The ERP business procedure is implemented separately for the actual schema.
   Do not use autonomous transactions in that procedure. */
CREATE TABLE PIGO_COMMAND_RECEIPT (
    COMMAND_ID VARCHAR(36) NOT NULL PRIMARY KEY,
    PAYLOAD_HASH CHAR(64) NOT NULL,
    RESULT_JSON BLOB SUB_TYPE TEXT CHARACTER SET UTF8,
    APPLIED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
COMMIT;
