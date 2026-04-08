CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE book
ADD COLUMN IF NOT EXISTS zone_group integer;

UPDATE book b
SET zone_group = z.zone_group
FROM seat s
JOIN zone z ON z.id = s.zid
WHERE b.sid = s.id
  AND b.zone_group IS DISTINCT FROM z.zone_group;

ALTER TABLE book
ALTER COLUMN zone_group SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'book_time_order'
    ) THEN
        ALTER TABLE book
        ADD CONSTRAINT book_time_order
        CHECK (fromts < tots);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION set_book_zone_group()
 RETURNS trigger
 LANGUAGE plpgsql
AS $$
BEGIN
    SELECT z.zone_group
    INTO NEW.zone_group
    FROM seat s
    JOIN zone z ON z.id = s.zid
    WHERE s.id = NEW.sid
    LIMIT 1;

    IF NEW.zone_group IS NULL THEN
        RAISE EXCEPTION 'Unknown seat';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS book_set_zone_group_trig ON book;
CREATE TRIGGER book_set_zone_group_trig
BEFORE INSERT OR UPDATE OF sid ON book
FOR EACH ROW
EXECUTE PROCEDURE set_book_zone_group();

CREATE OR REPLACE FUNCTION sync_book_zone_group_from_zone()
 RETURNS trigger
 LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE book b
    SET zone_group = NEW.zone_group
    FROM seat s
    WHERE b.sid = s.id
      AND s.zid = NEW.id
      AND b.zone_group IS DISTINCT FROM NEW.zone_group;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS zone_update_book_zone_group ON zone;
CREATE TRIGGER zone_update_book_zone_group
AFTER UPDATE OF zone_group ON zone
FOR EACH ROW
WHEN (OLD.zone_group IS DISTINCT FROM NEW.zone_group)
EXECUTE PROCEDURE sync_book_zone_group_from_zone();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'book_no_seat_overlap'
    ) THEN
        ALTER TABLE book
        ADD CONSTRAINT book_no_seat_overlap
        EXCLUDE USING gist (
            sid WITH =,
            int4range(fromts, tots, '[)') WITH &&
        );
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'book_no_user_zone_group_overlap'
    ) THEN
        ALTER TABLE book
        ADD CONSTRAINT book_no_user_zone_group_overlap
        EXCLUDE USING gist (
            login WITH =,
            zone_group WITH =,
            int4range(fromts, tots, '[)') WITH &&
        );
    END IF;
END;
$$;
