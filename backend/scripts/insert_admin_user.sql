-- SQL script to insert admin user into the admins table
-- This script inserts the provided admin user data

INSERT INTO admins (
    id,
    email,
    full_name,
    hashed_password,
    is_superadmin,
    is_active,
    created_at,
    updated_at
) VALUES (
    1,
    'rajanish@zivohealth.ai',
    'Super Admin',
    '$2b$12$m.jJW/59uI7TRomJV1sKPOrtYTDGUxD.QIL47Z5w0vqx3MTkYwTsG',
    true,
    true,
    '2025-10-01 13:56:35.192 +0530'::timestamptz,
    '2025-10-01 13:56:35.192 +0530'::timestamptz
);

-- Verify the admin was inserted
SELECT 
    id,
    email,
    full_name,
    is_superadmin,
    is_active,
    created_at,
    updated_at
FROM admins 
WHERE email = 'rajanish@zivohealth.ai';

-- Display success message
\echo 'Admin user inserted successfully!'
\echo 'Email: rajanish@zivohealth.ai'
\echo 'Full Name: Super Admin'
\echo 'Is Superadmin: true'
