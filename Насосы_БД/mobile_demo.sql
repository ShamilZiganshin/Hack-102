INSERT INTO equipment(tag, serial_no, name, data_origin, identity_note)
SELECT 'AMS-PS-00' || i, 'DEMO-00' || i, 'Учебный насос ' || i, 'synthetic', 'Демонстрационная карточка'
FROM generate_series(1,4) AS i ON CONFLICT(tag) DO NOTHING;
