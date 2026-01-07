-- Sample MariaDB Schema for Migration Testing
-- Creates tables for an animal tracking system

-- Animals table
CREATE TABLE IF NOT EXISTS animals (
    animal_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    species VARCHAR(50) NOT NULL,
    age INT,
    weight_kg DECIMAL(10, 2),
    habitat_name VARCHAR(100),
    last_checkup DATE
) ENGINE=InnoDB;

-- Habitats table
CREATE TABLE IF NOT EXISTS habitats (
    habitat_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    climate VARCHAR(50),
    size_acres DECIMAL(10, 2),
    capacity INT,
    built_date DATE
) ENGINE=InnoDB;

-- Feedings table
CREATE TABLE IF NOT EXISTS feedings (
    feeding_id INT PRIMARY KEY,
    animal_name VARCHAR(100) NOT NULL,
    food_type VARCHAR(50),
    quantity_kg DECIMAL(10, 2),
    feeding_time TIMESTAMP,
    fed_by VARCHAR(100)
) ENGINE=InnoDB;

-- Equipment table (tests additional data types)
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id BIGINT PRIMARY KEY,
    name VARCHAR(200),
    equipment_type VARCHAR(50),
    purchase_date DATE,
    last_maintenance TIMESTAMP,
    is_operational BOOLEAN,
    temperature_celsius FLOAT,
    pressure_psi DOUBLE,
    serial_number TEXT,
    calibration_time TIME,
    notes TEXT
) ENGINE=InnoDB;
