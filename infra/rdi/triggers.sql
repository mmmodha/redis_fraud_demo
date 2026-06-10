-- CDC triggers for the demo RDI processor.
--
-- Each tracked table gets an AFTER INSERT/UPDATE/DELETE row trigger that
-- emits a pg_notify on the 'rdi_changes' channel. The payload is small
-- (only table name, op, primary-key value) because NOTIFY caps payloads
-- at 8000 bytes — the processor re-SELECTs the full row to build the
-- Redis value, which also guarantees post-update consistency.

CREATE OR REPLACE FUNCTION rdi_notify_change() RETURNS TRIGGER AS $$
DECLARE
    pk_col text := TG_ARGV[0];
    pk_val text;
    payload text;
BEGIN
    IF (TG_OP = 'DELETE') THEN
        EXECUTE format('SELECT ($1).%I::text', pk_col) INTO pk_val USING OLD;
    ELSE
        EXECUTE format('SELECT ($1).%I::text', pk_col) INTO pk_val USING NEW;
    END IF;
    payload := json_build_object(
        'table', TG_TABLE_NAME,
        'op',    CASE TG_OP
                   WHEN 'INSERT' THEN 'c'
                   WHEN 'UPDATE' THEN 'u'
                   ELSE 'd'
                 END,
        'pk_col', pk_col,
        'pk_val', pk_val
    )::text;
    PERFORM pg_notify('rdi_changes', payload);
    IF (TG_OP = 'DELETE') THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rdi_t_customers ON customers;
CREATE TRIGGER rdi_t_customers
    AFTER INSERT OR UPDATE OR DELETE ON customers
    FOR EACH ROW EXECUTE FUNCTION rdi_notify_change('customer_id');

DROP TRIGGER IF EXISTS rdi_t_accounts ON accounts;
CREATE TRIGGER rdi_t_accounts
    AFTER INSERT OR UPDATE OR DELETE ON accounts
    FOR EACH ROW EXECUTE FUNCTION rdi_notify_change('account_id');

DROP TRIGGER IF EXISTS rdi_t_cards ON cards;
CREATE TRIGGER rdi_t_cards
    AFTER INSERT OR UPDATE OR DELETE ON cards
    FOR EACH ROW EXECUTE FUNCTION rdi_notify_change('card_id');

DROP TRIGGER IF EXISTS rdi_t_devices ON devices;
CREATE TRIGGER rdi_t_devices
    AFTER INSERT OR UPDATE OR DELETE ON devices
    FOR EACH ROW EXECUTE FUNCTION rdi_notify_change('device_id');

DROP TRIGGER IF EXISTS rdi_t_merchants ON merchants;
CREATE TRIGGER rdi_t_merchants
    AFTER INSERT OR UPDATE OR DELETE ON merchants
    FOR EACH ROW EXECUTE FUNCTION rdi_notify_change('merchant_id');

DROP TRIGGER IF EXISTS rdi_t_merchant_categories ON merchant_categories;
CREATE TRIGGER rdi_t_merchant_categories
    AFTER INSERT OR UPDATE OR DELETE ON merchant_categories
    FOR EACH ROW EXECUTE FUNCTION rdi_notify_change('code');

DROP TRIGGER IF EXISTS rdi_t_transactions ON transactions;
CREATE TRIGGER rdi_t_transactions
    AFTER INSERT OR UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION rdi_notify_change('transaction_id');
