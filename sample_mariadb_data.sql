-- Sample MariaDB Data for Migration Testing
-- Generates 1000 rows per table

-- Insert animals (1000 rows)
INSERT INTO animals (animal_id, name, species, age, weight_kg, habitat_name, last_checkup)
SELECT 
    seq AS animal_id,
    CONCAT('Animal_', seq) AS name,
    CASE (seq % 10)
        WHEN 0 THEN 'Lion'
        WHEN 1 THEN 'Tiger'
        WHEN 2 THEN 'Bear'
        WHEN 3 THEN 'Elephant'
        WHEN 4 THEN 'Giraffe'
        WHEN 5 THEN 'Zebra'
        WHEN 6 THEN 'Monkey'
        WHEN 7 THEN 'Penguin'
        WHEN 8 THEN 'Kangaroo'
        ELSE 'Panda'
    END AS species,
    (seq % 20) + 1 AS age,
    50.0 + (seq % 500) AS weight_kg,
    CASE (seq % 5)
        WHEN 0 THEN 'Savanna'
        WHEN 1 THEN 'Forest'
        WHEN 2 THEN 'Arctic'
        WHEN 3 THEN 'Desert'
        ELSE 'Jungle'
    END AS habitat_name,
    DATE_ADD('2024-01-01', INTERVAL (seq % 365) DAY) AS last_checkup
FROM seq_1_to_1000;

-- Insert habitats (1000 rows)
INSERT INTO habitats (habitat_id, name, climate, size_acres, capacity, built_date)
SELECT 
    seq AS habitat_id,
    CONCAT('Habitat_', seq) AS name,
    CASE (seq % 5)
        WHEN 0 THEN 'Tropical'
        WHEN 1 THEN 'Temperate'
        WHEN 2 THEN 'Arctic'
        WHEN 3 THEN 'Desert'
        ELSE 'Jungle'
    END AS climate,
    10.0 + (seq % 200) AS size_acres,
    10 + (seq % 50) AS capacity,
    DATE_ADD('2020-01-01', INTERVAL (seq % 365) DAY) AS built_date
FROM seq_1_to_1000;

-- Insert feedings (1000 rows)
INSERT INTO feedings (feeding_id, animal_name, food_type, quantity_kg, feeding_time, fed_by)
SELECT 
    seq AS feeding_id,
    CONCAT('Animal_', (seq % 1000) + 1) AS animal_name,
    CASE (seq % 6)
        WHEN 0 THEN 'Meat'
        WHEN 1 THEN 'Fish'
        WHEN 2 THEN 'Vegetables'
        WHEN 3 THEN 'Fruits'
        WHEN 4 THEN 'Grains'
        ELSE 'Mixed'
    END AS food_type,
    1.0 + (seq % 20) AS quantity_kg,
    TIMESTAMP(DATE_ADD('2024-01-01', INTERVAL (seq % 365) DAY), 
              TIME(CONCAT((seq % 24), ':00:00'))) AS feeding_time,
    CONCAT('Keeper_', (seq % 20) + 1) AS fed_by
FROM seq_1_to_1000;

-- Insert equipment (1000 rows)
INSERT INTO equipment (equipment_id, name, equipment_type, purchase_date, last_maintenance, 
                       is_operational, temperature_celsius, pressure_psi, serial_number, 
                       calibration_time, notes)
SELECT 
    seq AS equipment_id,
    CONCAT('Equipment_', seq) AS name,
    CASE (seq % 5)
        WHEN 0 THEN 'Cage'
        WHEN 1 THEN 'Feeder'
        WHEN 2 THEN 'Water System'
        WHEN 3 THEN 'Climate Control'
        ELSE 'Monitoring Device'
    END AS equipment_type,
    DATE_ADD('2020-01-01', INTERVAL (seq % 1825) DAY) AS purchase_date,
    TIMESTAMP(DATE_ADD('2024-01-01', INTERVAL (seq % 365) DAY), 
              TIME(CONCAT((seq % 24), ':00:00'))) AS last_maintenance,
    (seq % 2) = 0 AS is_operational,
    20.0 + (seq % 30) AS temperature_celsius,
    14.0 + (seq % 10) AS pressure_psi,
    CONCAT('SN-', LPAD(seq, 8, '0')) AS serial_number,
    TIME(CONCAT((seq % 24), ':', (seq % 60), ':00')) AS calibration_time,
    CONCAT('Equipment notes for item ', seq) AS notes
FROM seq_1_to_1000;
