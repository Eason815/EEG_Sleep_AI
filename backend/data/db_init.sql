CREATE DATABASE IF NOT EXISTS sleep_db;
USE sleep_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target_sleep_hours FLOAT DEFAULT 8.0,
    target_deep_ratio FLOAT DEFAULT 0.2,
    target_rem_ratio FLOAT DEFAULT 0.22,
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai'
);

CREATE TABLE IF NOT EXISTS sleep_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    model_family VARCHAR(100) NULL,
    model_name VARCHAR(255) NULL,
    result_json JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
