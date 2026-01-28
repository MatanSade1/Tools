-- SQL script to create staging tables for fraudsters management dev environment
-- Run this in BigQuery console before running main_dev.py

-- Create potential_fraudsters_stage table (copy structure from potential_fraudsters)
CREATE TABLE IF NOT EXISTS `yotam-395120.peerplay.potential_fraudsters_stage` AS
SELECT * FROM `yotam-395120.peerplay.potential_fraudsters` WHERE FALSE;

-- Create fraudsters_stage table (copy structure from fraudsters)
CREATE TABLE IF NOT EXISTS `yotam-395120.peerplay.fraudsters_stage` AS
SELECT * FROM `yotam-395120.peerplay.fraudsters` WHERE FALSE;

-- Create fraudsters_stage_temp table (copy structure from fraudsters_temp)
CREATE TABLE IF NOT EXISTS `yotam-395120.peerplay.fraudsters_stage_temp` AS
SELECT * FROM `yotam-395120.peerplay.fraudsters_temp` WHERE FALSE;

