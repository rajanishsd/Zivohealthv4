-- Add missing metric anchors for health score calculation
-- Safe to run multiple times - uses ON CONFLICT DO NOTHING

-- Script: 01_add_metric_anchors.sql
-- Purpose: Insert metric anchors for health score calculation
-- Run this FIRST before backfilling sleep data

BEGIN;

-- Biomarkers
INSERT INTO metric_anchor_registry (domain, key, loinc_code, unit, pattern, anchors, half_life_days, group_key, active, introduced_in, created_at, updated_at)
VALUES 
    ('biomarker', 'a1c_pct', '4548-4', '%', 'lower', 
     '[[5.0,100],[5.6,95],[5.7,90],[6.0,75],[6.5,55],[7.0,45],[8.0,30],[9.0,20],[10.0,10]]'::jsonb,
     180, 'glycemic', true, 'v1', NOW(), NOW()),
    
    ('biomarker', 'ldl_mgdl', '13457-7', 'mg/dL', 'lower',
     '[[70,100],[100,90],[130,70],[160,45],[190,25],[220,10]]'::jsonb,
     180, 'lipids', true, 'v1', NOW(), NOW()),
    
    ('biomarker', 'hdl_mgdl_male', '2085-9', 'mg/dL', 'higher',
     '[[25,25],[35,55],[40,70],[50,85],[60,100]]'::jsonb,
     180, 'lipids', true, 'v1', NOW(), NOW()),
    
    ('biomarker', 'triglycerides_mgdl', '2571-8', 'mg/dL', 'lower',
     '[[100,100],[150,85],[200,70],[300,50],[400,35],[500,20],[1000,5]]'::jsonb,
     180, 'lipids', true, 'v1', NOW(), NOW()),
    
    ('biomarker', 'alt_u_l', '1742-6', 'U/L', 'lower',
     '[[25,100],[40,90],[60,75],[80,60],[120,40],[200,20],[300,10]]'::jsonb,
     180, 'hepatic', true, 'v1', NOW(), NOW()),
    
    ('biomarker', 'ast_u_l', '1920-8', 'U/L', 'lower',
     '[[25,100],[40,90],[60,75],[80,60],[120,40],[200,20],[300,10]]'::jsonb,
     180, 'hepatic', true, 'v1', NOW(), NOW()),
    
    ('biomarker', 'hs_crp_mg_l', '30522-7', 'mg/L', 'lower',
     '[[1.0,100],[3.0,75],[5.0,60],[10,40],[20,20],[50,5]]'::jsonb,
     180, 'inflammation', true, 'v1', NOW(), NOW()),
    
    ('biomarker', 'vitd_25oh_ngml', '1989-3', 'ng/mL', 'range',
     '[[10,10],[15,30],[20,50],[25,65],[30,100],[50,100],[60,90],[80,70],[100,50]]'::jsonb,
     180, 'vitamins', true, 'v1', NOW(), NOW())

ON CONFLICT (domain, key) DO NOTHING;

-- Activity
INSERT INTO metric_anchor_registry (domain, key, loinc_code, unit, pattern, anchors, half_life_days, group_key, active, introduced_in, created_at, updated_at)
VALUES 
    ('activity', 'steps_per_day', NULL, 'steps', 'higher',
     '[[0,0],[2000,20],[5000,50],[7000,70],[10000,90],[12000,95],[15000,100]]'::jsonb,
     NULL, 'physical_activity', true, 'v1', NOW(), NOW())

ON CONFLICT (domain, key) DO NOTHING;

-- Sleep
INSERT INTO metric_anchor_registry (domain, key, loinc_code, unit, pattern, anchors, half_life_days, group_key, active, introduced_in, created_at, updated_at)
VALUES 
    ('sleep', 'duration_h', NULL, 'hours', 'range',
     '[[0,0],[4,20],[5,40],[6,60],[7,90],[8,100],[9,90],[10,70],[12,50]]'::jsonb,
     NULL, 'sleep_quality', true, 'v1', NOW(), NOW())

ON CONFLICT (domain, key) DO NOTHING;

-- Vitals
INSERT INTO metric_anchor_registry (domain, key, loinc_code, unit, pattern, anchors, half_life_days, group_key, active, introduced_in, created_at, updated_at)
VALUES 
    ('vitals', 'resting_hr', NULL, 'bpm', 'range',
     '[[40,90],[50,100],[60,100],[70,95],[80,85],[90,70],[100,50],[110,30],[120,10]]'::jsonb,
     NULL, 'cardiovascular', true, 'v1', NOW(), NOW()),
    
    ('vitals', 'bp_systolic', NULL, 'mmHg', 'range',
     '[[90,70],[100,85],[110,95],[120,100],[130,85],[140,70],[160,40],[180,20],[200,5]]'::jsonb,
     NULL, 'cardiovascular', true, 'v1', NOW(), NOW()),
    
    ('vitals', 'bp_diastolic', NULL, 'mmHg', 'range',
     '[[60,80],[70,95],[80,100],[85,95],[90,70],[100,40],[110,20],[120,5]]'::jsonb,
     NULL, 'cardiovascular', true, 'v1', NOW(), NOW()),
    
    ('vitals', 'spo2_pct', NULL, '%', 'higher',
     '[[85,0],[90,30],[92,50],[95,80],[97,95],[98,100],[100,100]]'::jsonb,
     NULL, 'respiratory', true, 'v1', NOW(), NOW()),
    
    ('vitals', 'temperature_c', NULL, '°C', 'range',
     '[[35.0,50],[36.0,80],[36.5,100],[37.0,100],[37.5,90],[38.0,70],[38.5,50],[39.0,30],[40.0,10]]'::jsonb,
     NULL, 'general', true, 'v1', NOW(), NOW())

ON CONFLICT (domain, key) DO NOTHING;

-- Medication
INSERT INTO metric_anchor_registry (domain, key, loinc_code, unit, pattern, anchors, half_life_days, group_key, active, introduced_in, created_at, updated_at)
VALUES 
    ('medication', 'pdc', NULL, 'ratio', 'higher',
     '[[0.0,0],[0.4,30],[0.6,60],[0.8,85],[0.9,95],[1.0,100]]'::jsonb,
     NULL, 'adherence', true, 'v1', NOW(), NOW())

ON CONFLICT (domain, key) DO NOTHING;

-- Nutrition
INSERT INTO metric_anchor_registry (domain, key, loinc_code, unit, pattern, anchors, half_life_days, group_key, active, introduced_in, created_at, updated_at)
VALUES 
    ('nutrition', 'energy_balance_pct_abs', NULL, '%', 'lower',
     '[[0,100],[5,95],[10,90],[15,80],[20,60],[30,40],[50,20]]'::jsonb,
     NULL, 'calorie_balance', true, 'v1', NOW(), NOW())

ON CONFLICT (domain, key) DO NOTHING;

-- Verify insertions
SELECT 
    domain,
    COUNT(*) as anchor_count
FROM metric_anchor_registry
WHERE active = true
GROUP BY domain
ORDER BY domain;

COMMIT;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✓ Metric anchors added successfully';
    RAISE NOTICE 'Total active anchors: %', (SELECT COUNT(*) FROM metric_anchor_registry WHERE active = true);
END $$;

