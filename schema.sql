--
-- PostgreSQL database dump
--

-- Dumped from database version 14.18 (Homebrew)
-- Dumped by pg_dump version 14.18 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: healthkitmetrictype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.healthkitmetrictype AS ENUM (
    'HEART_RATE',
    'BLOOD_PRESSURE_SYSTOLIC',
    'BLOOD_PRESSURE_DIASTOLIC',
    'BLOOD_SUGAR',
    'BODY_TEMPERATURE',
    'BODY_MASS',
    'STEP_COUNT',
    'STAND_TIME',
    'ACTIVE_ENERGY',
    'FLIGHTS_CLIMBED',
    'WORKOUTS',
    'SLEEP',
    'DISTANCE_WALKING'
);


--
-- Name: vitaldatasource; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.vitaldatasource AS ENUM (
    'apple_healthkit',
    'manual_entry',
    'document_extraction',
    'device_sync',
    'api_import'
);


--
-- Name: vitalmetrictype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.vitalmetrictype AS ENUM (
    'Heart Rate',
    'Blood Pressure Systolic',
    'Blood Pressure Diastolic',
    'Blood Sugar',
    'Temperature',
    'Weight',
    'Height',
    'BMI',
    'Steps',
    'Stand Hours',
    'Active Energy',
    'Flights Climbed',
    'Workouts',
    'Sleep'
);


--
-- Name: update_lab_report_categorized_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_lab_report_categorized_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_memory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_memory (
    id integer NOT NULL,
    user_id integer NOT NULL,
    session_id integer,
    agent_name character varying(100) NOT NULL,
    memory_type character varying(50),
    memory_key character varying(255),
    memory_value json,
    relevance_score double precision,
    expiry_date timestamp without time zone,
    last_accessed timestamp without time zone,
    access_count integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: agent_memory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_memory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_memory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_memory_id_seq OWNED BY public.agent_memory.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: appointments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointments (
    id integer NOT NULL,
    patient_id integer NOT NULL,
    doctor_id integer NOT NULL,
    consultation_request_id integer,
    title character varying NOT NULL,
    description text,
    appointment_date timestamp without time zone NOT NULL,
    duration_minutes integer DEFAULT 30,
    status character varying DEFAULT 'scheduled'::character varying,
    appointment_type character varying DEFAULT 'consultation'::character varying,
    patient_notes text,
    doctor_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: appointments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.appointments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: appointments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.appointments_id_seq OWNED BY public.appointments.id;


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_messages (
    id integer NOT NULL,
    session_id integer NOT NULL,
    user_id integer NOT NULL,
    content text NOT NULL,
    role character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    tokens_used integer,
    response_time_ms integer,
    file_path character varying(500),
    file_type character varying(10),
    visualizations json
);


--
-- Name: chat_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_messages_id_seq OWNED BY public.chat_messages.id;


--
-- Name: chat_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_sessions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    last_message_at timestamp with time zone DEFAULT now(),
    message_count integer,
    has_verification boolean,
    has_prescriptions boolean,
    is_active boolean,
    enhanced_mode_enabled boolean DEFAULT true NOT NULL
);


--
-- Name: chat_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_sessions_id_seq OWNED BY public.chat_sessions.id;


--
-- Name: clinical_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clinical_notes (
    id character varying(36) NOT NULL,
    session_id integer NOT NULL,
    user_id integer NOT NULL,
    diagnosis text,
    symptoms_presented text,
    doctor_observations text,
    clinical_findings text,
    treatment_plan text,
    follow_up_recommendations text,
    vital_signs_mentioned text,
    medical_history_noted text,
    visit_date timestamp with time zone,
    clinic_or_hospital character varying(255),
    attending_physician character varying(255),
    specialty character varying(100),
    document_type character varying(100),
    document_image_link character varying(500),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: clinical_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clinical_reports (
    id integer NOT NULL,
    user_id integer NOT NULL,
    chat_session_id integer NOT NULL,
    message_id integer,
    user_question text NOT NULL,
    ai_response text NOT NULL,
    comprehensive_context text NOT NULL,
    data_sources_summary text,
    vitals_data text,
    nutrition_data text,
    prescription_data text,
    lab_data text,
    pharmacy_data text,
    agent_requirements text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: clinical_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clinical_reports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clinical_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clinical_reports_id_seq OWNED BY public.clinical_reports.id;


--
-- Name: consultation_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consultation_requests (
    id integer NOT NULL,
    user_id integer NOT NULL,
    doctor_id integer NOT NULL,
    chat_session_id integer,
    context text NOT NULL,
    user_question text NOT NULL,
    status character varying,
    urgency_level character varying,
    created_at timestamp with time zone DEFAULT now(),
    accepted_at timestamp with time zone,
    completed_at timestamp with time zone,
    doctor_notes text,
    clinical_report_id integer
);


--
-- Name: consultation_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.consultation_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: consultation_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.consultation_requests_id_seq OWNED BY public.consultation_requests.id;


--
-- Name: doctors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.doctors (
    id integer NOT NULL,
    email character varying NOT NULL,
    hashed_password character varying NOT NULL,
    full_name character varying NOT NULL,
    license_number character varying NOT NULL,
    specialization character varying NOT NULL,
    years_experience integer NOT NULL,
    rating double precision,
    total_consultations integer,
    bio text,
    is_available boolean,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    date_of_birth date,
    contact_number character varying
);


--
-- Name: doctors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.doctors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: doctors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.doctors_id_seq OWNED BY public.doctors.id;


--
-- Name: document_processing_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_processing_logs (
    id integer NOT NULL,
    request_id character varying(100) NOT NULL,
    user_id integer NOT NULL,
    session_id integer,
    file_path character varying(500) NOT NULL,
    original_filename character varying(255),
    file_size integer,
    file_type character varying(20),
    mime_type character varying(100),
    document_type character varying(50),
    classification_confidence double precision,
    processing_status character varying(20),
    ocr_text text,
    ocr_confidence double precision,
    ocr_engine character varying(50),
    extracted_data json,
    structured_data json,
    validation_errors json,
    records_created json,
    records_updated json,
    started_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone,
    processing_duration_ms integer,
    error_message text,
    retry_count integer,
    workflow_steps json,
    agent_interactions json,
    created_at timestamp without time zone
);


--
-- Name: document_processing_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.document_processing_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: document_processing_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_processing_logs_id_seq OWNED BY public.document_processing_logs.id;


--
-- Name: health_data_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.health_data_history (
    id integer NOT NULL,
    patient_id integer NOT NULL,
    indicator_id integer NOT NULL,
    current_record_id integer NOT NULL,
    numeric_value double precision,
    text_value text,
    boolean_value boolean,
    file_path character varying,
    recorded_date date NOT NULL,
    recorded_by integer,
    notes text,
    is_abnormal boolean,
    change_type character varying,
    previous_value text,
    created_at timestamp without time zone
);


--
-- Name: health_data_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.health_data_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: health_data_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.health_data_history_id_seq OWNED BY public.health_data_history.id;


--
-- Name: health_indicator_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.health_indicator_categories (
    id integer NOT NULL,
    name character varying NOT NULL,
    description text,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: health_indicator_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.health_indicator_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: health_indicator_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.health_indicator_categories_id_seq OWNED BY public.health_indicator_categories.id;


--
-- Name: health_indicators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.health_indicators (
    id integer NOT NULL,
    category_id integer NOT NULL,
    name character varying NOT NULL,
    unit character varying,
    normal_range_min double precision,
    normal_range_max double precision,
    data_type character varying,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: health_indicators_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.health_indicators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: health_indicators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.health_indicators_id_seq OWNED BY public.health_indicators.id;


--
-- Name: lab_report_categorized; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_report_categorized (
    user_id integer NOT NULL,
    test_name character varying(255) NOT NULL,
    test_value character varying(100) NOT NULL,
    test_date date NOT NULL,
    id integer,
    test_category character varying(100),
    test_unit character varying(50),
    reference_range character varying(500),
    test_status character varying(20),
    lab_name character varying(255),
    lab_address text,
    ordering_physician character varying(255),
    report_date date,
    test_notes text,
    test_methodology character varying(255),
    extracted_from_document_id integer,
    confidence_score double precision,
    raw_text text,
    inferred_test_category character varying(100),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    test_code character varying(50),
    aggregation_status character varying(20) DEFAULT 'pending'::character varying,
    loinc_code character varying(20) NOT NULL
);


--
-- Name: lab_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_reports (
    id integer NOT NULL,
    user_id integer NOT NULL,
    test_name character varying(255) NOT NULL,
    test_category character varying(100),
    test_value character varying(100),
    test_unit character varying(50),
    reference_range character varying(500),
    test_status character varying(20),
    lab_name character varying(255),
    lab_address text,
    ordering_physician character varying(255),
    test_date date NOT NULL,
    report_date date,
    test_notes text,
    test_methodology character varying(255),
    extracted_from_document_id integer,
    confidence_score double precision,
    raw_text text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    categorization_status character varying(20) DEFAULT 'pending'::character varying,
    failure_reason character varying(255)
);


--
-- Name: lab_reports_daily; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_reports_daily (
    id integer NOT NULL,
    user_id integer NOT NULL,
    date date NOT NULL,
    test_name character varying(255) NOT NULL,
    test_category character varying(100) NOT NULL,
    avg_value character varying(100),
    min_value character varying(100),
    max_value character varying(100),
    count integer NOT NULL,
    unit character varying(50),
    normal_range_min double precision,
    normal_range_max double precision,
    status character varying(20),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    test_code character varying(50),
    loinc_code character varying(20)
);


--
-- Name: lab_reports_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lab_reports_daily_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lab_reports_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lab_reports_daily_id_seq OWNED BY public.lab_reports_daily.id;


--
-- Name: lab_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lab_reports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lab_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lab_reports_id_seq OWNED BY public.lab_reports.id;


--
-- Name: lab_reports_monthly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_reports_monthly (
    id integer NOT NULL,
    user_id integer NOT NULL,
    year integer NOT NULL,
    month integer NOT NULL,
    test_name character varying(255) NOT NULL,
    test_category character varying(100) NOT NULL,
    avg_value character varying(100),
    min_value character varying(100),
    max_value character varying(100),
    count integer NOT NULL,
    unit character varying(50),
    normal_range_min double precision,
    normal_range_max double precision,
    status character varying(20),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    test_code character varying(50),
    loinc_code character varying(20)
);


--
-- Name: lab_reports_monthly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lab_reports_monthly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lab_reports_monthly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lab_reports_monthly_id_seq OWNED BY public.lab_reports_monthly.id;


--
-- Name: lab_reports_quarterly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_reports_quarterly (
    id integer NOT NULL,
    user_id integer NOT NULL,
    year integer NOT NULL,
    quarter integer NOT NULL,
    test_name character varying(255) NOT NULL,
    test_category character varying(100) NOT NULL,
    avg_value character varying(100),
    min_value character varying(100),
    max_value character varying(100),
    count integer NOT NULL,
    unit character varying(50),
    normal_range_min double precision,
    normal_range_max double precision,
    status character varying(20),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    test_code character varying(50),
    loinc_code character varying(20)
);


--
-- Name: lab_reports_quarterly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lab_reports_quarterly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lab_reports_quarterly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lab_reports_quarterly_id_seq OWNED BY public.lab_reports_quarterly.id;


--
-- Name: lab_reports_yearly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_reports_yearly (
    id integer NOT NULL,
    user_id integer NOT NULL,
    year integer NOT NULL,
    test_name character varying(255) NOT NULL,
    test_category character varying(100) NOT NULL,
    avg_value character varying(100),
    min_value character varying(100),
    max_value character varying(100),
    count integer NOT NULL,
    unit character varying(50),
    normal_range_min double precision,
    normal_range_max double precision,
    status character varying(20),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    test_code character varying(50),
    loinc_code character varying(20)
);


--
-- Name: lab_reports_yearly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lab_reports_yearly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lab_reports_yearly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lab_reports_yearly_id_seq OWNED BY public.lab_reports_yearly.id;


--
-- Name: lab_test_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lab_test_mappings (
    id integer NOT NULL,
    test_name character varying(255) NOT NULL,
    test_category character varying(100) NOT NULL,
    description text,
    common_units character varying(100),
    normal_range_info text,
    is_active boolean NOT NULL,
    is_standardized boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    gpt_suggested_category character varying(100),
    test_code character varying(50),
    test_name_standardized character varying(255) NOT NULL,
    loinc_code character varying(20),
    loinc_source character varying(50)
);


--
-- Name: COLUMN lab_test_mappings.gpt_suggested_category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lab_test_mappings.gpt_suggested_category IS 'Stores GPT suggested category when test is categorized as Others';


--
-- Name: lab_test_mappings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lab_test_mappings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lab_test_mappings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lab_test_mappings_id_seq OWNED BY public.lab_test_mappings.id;


--
-- Name: langchain_pg_collection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.langchain_pg_collection (
    uuid uuid NOT NULL,
    name character varying,
    cmetadata json
);


--
-- Name: langchain_pg_embedding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.langchain_pg_embedding (
    uuid uuid NOT NULL,
    collection_id uuid,
    embedding public.vector,
    document character varying,
    cmetadata json,
    custom_id character varying
);


--
-- Name: loinc_pg_collection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loinc_pg_collection (
    uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    cmetadata json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: loinc_pg_embedding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loinc_pg_embedding (
    uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    collection_id uuid,
    embedding public.vector(768),
    document text,
    cmetadata json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: medical_images; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.medical_images (
    id integer NOT NULL,
    user_id integer NOT NULL,
    image_type character varying NOT NULL,
    body_part character varying,
    image_path character varying NOT NULL,
    original_filename character varying,
    file_size integer,
    image_format character varying,
    ai_summary text,
    ai_findings text,
    confidence_score double precision,
    exam_date date,
    ordering_physician character varying,
    facility_name character varying,
    exam_reason text,
    processing_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    processed_at timestamp without time zone,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: medical_images_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.medical_images_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: medical_images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.medical_images_id_seq OWNED BY public.medical_images.id;


--
-- Name: nutrition_daily_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nutrition_daily_aggregates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    date date NOT NULL,
    total_calories double precision DEFAULT 0.0,
    total_protein_g double precision DEFAULT 0.0,
    total_fat_g double precision DEFAULT 0.0,
    total_carbs_g double precision DEFAULT 0.0,
    total_fiber_g double precision DEFAULT 0.0,
    total_sugar_g double precision DEFAULT 0.0,
    total_sodium_mg double precision DEFAULT 0.0,
    meal_count integer DEFAULT 0,
    breakfast_count integer DEFAULT 0,
    lunch_count integer DEFAULT 0,
    dinner_count integer DEFAULT 0,
    snack_count integer DEFAULT 0,
    breakfast_calories double precision DEFAULT 0.0,
    lunch_calories double precision DEFAULT 0.0,
    dinner_calories double precision DEFAULT 0.0,
    snack_calories double precision DEFAULT 0.0,
    primary_source character varying,
    sources_included character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    total_vitamin_a_mcg double precision DEFAULT 0.0,
    total_vitamin_c_mg double precision DEFAULT 0.0,
    total_vitamin_d_mcg double precision DEFAULT 0.0,
    total_vitamin_e_mg double precision DEFAULT 0.0,
    total_vitamin_k_mcg double precision DEFAULT 0.0,
    total_vitamin_b1_mg double precision DEFAULT 0.0,
    total_vitamin_b2_mg double precision DEFAULT 0.0,
    total_vitamin_b3_mg double precision DEFAULT 0.0,
    total_vitamin_b6_mg double precision DEFAULT 0.0,
    total_vitamin_b12_mcg double precision DEFAULT 0.0,
    total_folate_mcg double precision DEFAULT 0.0,
    total_calcium_mg double precision DEFAULT 0.0,
    total_iron_mg double precision DEFAULT 0.0,
    total_magnesium_mg double precision DEFAULT 0.0,
    total_phosphorus_mg double precision DEFAULT 0.0,
    total_potassium_mg double precision DEFAULT 0.0,
    total_zinc_mg double precision DEFAULT 0.0,
    total_copper_mg double precision DEFAULT 0.0,
    total_manganese_mg double precision DEFAULT 0.0,
    total_selenium_mcg double precision DEFAULT 0.0
);


--
-- Name: nutrition_daily_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nutrition_daily_aggregates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nutrition_daily_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nutrition_daily_aggregates_id_seq OWNED BY public.nutrition_daily_aggregates.id;


--
-- Name: nutrition_monthly_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nutrition_monthly_aggregates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    year integer NOT NULL,
    month integer NOT NULL,
    avg_daily_calories double precision DEFAULT 0.0,
    avg_daily_protein_g double precision DEFAULT 0.0,
    avg_daily_fat_g double precision DEFAULT 0.0,
    avg_daily_carbs_g double precision DEFAULT 0.0,
    avg_daily_fiber_g double precision DEFAULT 0.0,
    avg_daily_sugar_g double precision DEFAULT 0.0,
    avg_daily_sodium_mg double precision DEFAULT 0.0,
    total_monthly_calories double precision DEFAULT 0.0,
    total_monthly_meals integer DEFAULT 0,
    days_with_data integer DEFAULT 0,
    primary_source character varying,
    sources_included character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    avg_daily_vitamin_a_mcg double precision DEFAULT 0.0,
    avg_daily_vitamin_c_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_d_mcg double precision DEFAULT 0.0,
    avg_daily_vitamin_e_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_k_mcg double precision DEFAULT 0.0,
    avg_daily_vitamin_b1_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b2_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b3_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b6_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b12_mcg double precision DEFAULT 0.0,
    avg_daily_folate_mcg double precision DEFAULT 0.0,
    avg_daily_calcium_mg double precision DEFAULT 0.0,
    avg_daily_iron_mg double precision DEFAULT 0.0,
    avg_daily_magnesium_mg double precision DEFAULT 0.0,
    avg_daily_phosphorus_mg double precision DEFAULT 0.0,
    avg_daily_potassium_mg double precision DEFAULT 0.0,
    avg_daily_zinc_mg double precision DEFAULT 0.0,
    avg_daily_copper_mg double precision DEFAULT 0.0,
    avg_daily_manganese_mg double precision DEFAULT 0.0,
    avg_daily_selenium_mcg double precision DEFAULT 0.0
);


--
-- Name: nutrition_monthly_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nutrition_monthly_aggregates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nutrition_monthly_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nutrition_monthly_aggregates_id_seq OWNED BY public.nutrition_monthly_aggregates.id;


--
-- Name: nutrition_raw_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nutrition_raw_data (
    id integer NOT NULL,
    user_id integer NOT NULL,
    food_item_name character varying NOT NULL,
    meal_type character varying NOT NULL,
    portion_size double precision NOT NULL,
    portion_unit character varying NOT NULL,
    calories double precision NOT NULL,
    protein_g double precision DEFAULT 0.0,
    fat_g double precision DEFAULT 0.0,
    carbs_g double precision DEFAULT 0.0,
    fiber_g double precision DEFAULT 0.0,
    sugar_g double precision DEFAULT 0.0,
    sodium_mg double precision DEFAULT 0.0,
    meal_date date NOT NULL,
    meal_time timestamp without time zone NOT NULL,
    data_source character varying NOT NULL,
    confidence_score double precision,
    image_url character varying,
    notes text,
    aggregation_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    aggregated_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    dish_name character varying,
    dish_type character varying,
    vitamin_a_mcg double precision DEFAULT 0.0,
    vitamin_c_mg double precision DEFAULT 0.0,
    vitamin_d_mcg double precision DEFAULT 0.0,
    vitamin_e_mg double precision DEFAULT 0.0,
    vitamin_k_mcg double precision DEFAULT 0.0,
    vitamin_b1_mg double precision DEFAULT 0.0,
    vitamin_b2_mg double precision DEFAULT 0.0,
    vitamin_b3_mg double precision DEFAULT 0.0,
    vitamin_b6_mg double precision DEFAULT 0.0,
    vitamin_b12_mcg double precision DEFAULT 0.0,
    folate_mcg double precision DEFAULT 0.0,
    calcium_mg double precision DEFAULT 0.0,
    iron_mg double precision DEFAULT 0.0,
    magnesium_mg double precision DEFAULT 0.0,
    phosphorus_mg double precision DEFAULT 0.0,
    potassium_mg double precision DEFAULT 0.0,
    zinc_mg double precision DEFAULT 0.0,
    copper_mg double precision DEFAULT 0.0,
    manganese_mg double precision DEFAULT 0.0,
    selenium_mcg double precision DEFAULT 0.0
);


--
-- Name: nutrition_raw_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nutrition_raw_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nutrition_raw_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nutrition_raw_data_id_seq OWNED BY public.nutrition_raw_data.id;


--
-- Name: nutrition_sync_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nutrition_sync_status (
    id integer NOT NULL,
    user_id integer NOT NULL,
    data_source character varying NOT NULL,
    last_sync_date timestamp without time zone,
    last_successful_sync timestamp without time zone,
    sync_enabled character varying DEFAULT 'true'::character varying,
    last_error text,
    error_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: nutrition_sync_status_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nutrition_sync_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nutrition_sync_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nutrition_sync_status_id_seq OWNED BY public.nutrition_sync_status.id;


--
-- Name: nutrition_weekly_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nutrition_weekly_aggregates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    week_start_date date NOT NULL,
    week_end_date date NOT NULL,
    avg_daily_calories double precision DEFAULT 0.0,
    avg_daily_protein_g double precision DEFAULT 0.0,
    avg_daily_fat_g double precision DEFAULT 0.0,
    avg_daily_carbs_g double precision DEFAULT 0.0,
    avg_daily_fiber_g double precision DEFAULT 0.0,
    avg_daily_sugar_g double precision DEFAULT 0.0,
    avg_daily_sodium_mg double precision DEFAULT 0.0,
    total_weekly_calories double precision DEFAULT 0.0,
    total_weekly_meals integer DEFAULT 0,
    days_with_data integer DEFAULT 0,
    primary_source character varying,
    sources_included character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    avg_daily_vitamin_a_mcg double precision DEFAULT 0.0,
    avg_daily_vitamin_c_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_d_mcg double precision DEFAULT 0.0,
    avg_daily_vitamin_e_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_k_mcg double precision DEFAULT 0.0,
    avg_daily_vitamin_b1_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b2_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b3_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b6_mg double precision DEFAULT 0.0,
    avg_daily_vitamin_b12_mcg double precision DEFAULT 0.0,
    avg_daily_folate_mcg double precision DEFAULT 0.0,
    avg_daily_calcium_mg double precision DEFAULT 0.0,
    avg_daily_iron_mg double precision DEFAULT 0.0,
    avg_daily_magnesium_mg double precision DEFAULT 0.0,
    avg_daily_phosphorus_mg double precision DEFAULT 0.0,
    avg_daily_potassium_mg double precision DEFAULT 0.0,
    avg_daily_zinc_mg double precision DEFAULT 0.0,
    avg_daily_copper_mg double precision DEFAULT 0.0,
    avg_daily_manganese_mg double precision DEFAULT 0.0,
    avg_daily_selenium_mcg double precision DEFAULT 0.0
);


--
-- Name: nutrition_weekly_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nutrition_weekly_aggregates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nutrition_weekly_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nutrition_weekly_aggregates_id_seq OWNED BY public.nutrition_weekly_aggregates.id;


--
-- Name: opentelemetry_traces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.opentelemetry_traces (
    id integer NOT NULL,
    trace_id character varying(32) NOT NULL,
    span_id character varying(16) NOT NULL,
    parent_span_id character varying(16),
    span_name character varying(255) NOT NULL,
    span_kind character varying(20),
    status_code character varying(20),
    status_message text,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone,
    duration_ms double precision,
    service_name character varying(100),
    operation_name character varying(100),
    resource_attributes json,
    span_attributes json,
    span_events json,
    user_id integer,
    session_id integer,
    request_id character varying(100),
    document_id integer,
    agent_name character varying(100),
    agent_type character varying(50),
    workflow_step character varying(100),
    created_at timestamp without time zone
);


--
-- Name: opentelemetry_traces_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.opentelemetry_traces_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: opentelemetry_traces_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.opentelemetry_traces_id_seq OWNED BY public.opentelemetry_traces.id;


--
-- Name: patient_health_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_health_records (
    id integer NOT NULL,
    patient_id integer NOT NULL,
    indicator_id integer NOT NULL,
    numeric_value double precision,
    text_value text,
    boolean_value boolean,
    file_path character varying,
    recorded_date date NOT NULL,
    recorded_by integer,
    notes text,
    is_abnormal boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: patient_health_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.patient_health_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patient_health_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.patient_health_records_id_seq OWNED BY public.patient_health_records.id;


--
-- Name: patient_health_summaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_health_summaries (
    id integer NOT NULL,
    patient_id integer NOT NULL,
    total_indicators_tracked integer,
    abnormal_indicators_count integer,
    last_updated timestamp without time zone,
    health_score double precision,
    high_risk_indicators text,
    medium_risk_indicators text,
    improving_trends text,
    declining_trends text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: patient_health_summaries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.patient_health_summaries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patient_health_summaries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.patient_health_summaries_id_seq OWNED BY public.patient_health_summaries.id;


--
-- Name: pharmacy_bills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pharmacy_bills (
    id integer NOT NULL,
    user_id integer NOT NULL,
    pharmacy_name character varying(255) NOT NULL,
    pharmacy_address text,
    pharmacy_phone character varying(20),
    bill_number character varying(100),
    bill_date date NOT NULL,
    total_amount double precision NOT NULL,
    tax_amount double precision,
    discount_amount double precision,
    prescription_number character varying(100),
    prescribing_doctor character varying(255),
    confidence_score double precision,
    raw_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    pharmacy_gstin character varying(20),
    pharmacy_fssai_license character varying(20),
    pharmacy_dl_numbers json,
    pharmacy_registration_address text,
    pharmacy_premise_address text,
    pos_location character varying(100),
    pharmacist_name character varying(255),
    pharmacist_registration_number character varying(50),
    bill_type character varying(50),
    invoice_number character varying(100),
    order_id character varying(100),
    order_date date,
    invoice_date date,
    gross_amount double precision,
    taxable_amount double precision,
    cgst_rate double precision,
    cgst_amount double precision,
    sgst_rate double precision,
    sgst_amount double precision,
    igst_rate double precision,
    igst_amount double precision,
    total_gst_amount double precision,
    shipping_charges double precision,
    vas_charges double precision,
    credits_applied double precision,
    payable_amount double precision,
    amount_in_words text,
    patient_name character varying(255),
    patient_address text,
    patient_contact character varying(20),
    place_of_supply character varying(100),
    doctor_address text,
    transaction_id character varying(100),
    payment_method character varying(50),
    transaction_timestamp timestamp without time zone,
    transaction_amount double precision,
    support_contact character varying(100),
    compliance_codes json,
    pharmacybill_filepath character varying(500)
);


--
-- Name: pharmacy_bills_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pharmacy_bills_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pharmacy_bills_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pharmacy_bills_id_seq OWNED BY public.pharmacy_bills.id;


--
-- Name: pharmacy_medications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pharmacy_medications (
    id integer NOT NULL,
    bill_id integer NOT NULL,
    medication_name character varying(255) NOT NULL,
    generic_name character varying(255),
    strength character varying(100),
    quantity integer,
    unit_price double precision,
    total_price double precision,
    dosage_instructions text,
    frequency character varying(100),
    duration character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id integer NOT NULL,
    brand_name character varying(255),
    unit_of_measurement character varying(20),
    manufacturer_name character varying(255),
    hsn_code character varying(20),
    batch_number character varying(50),
    expiry_date date,
    ndc_number character varying(20),
    mrp double precision,
    discount_amount double precision,
    taxable_amount double precision,
    gst_rate double precision,
    gst_amount double precision,
    cgst_rate double precision,
    cgst_amount double precision,
    sgst_rate double precision,
    sgst_amount double precision,
    igst_rate double precision,
    igst_amount double precision,
    prescription_validity_date date,
    dispensing_dl_number character varying(50)
);


--
-- Name: pharmacy_medications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pharmacy_medications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pharmacy_medications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pharmacy_medications_id_seq OWNED BY public.pharmacy_medications.id;


--
-- Name: prescriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prescriptions (
    id character varying(36) NOT NULL,
    session_id integer NOT NULL,
    consultation_request_id integer,
    medication_name character varying(255) NOT NULL,
    dosage character varying(100),
    frequency character varying(100),
    instructions text,
    prescribed_by character varying(255) NOT NULL,
    prescribed_at timestamp with time zone DEFAULT now(),
    duration character varying(100),
    prescription_image_link character varying(500),
    user_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rxnorm_pg_collection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rxnorm_pg_collection (
    uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    cmetadata json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: rxnorm_pg_embedding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rxnorm_pg_embedding (
    uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    collection_id uuid,
    embedding public.vector(768),
    document text,
    cmetadata json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: snomed_pg_collection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snomed_pg_collection (
    uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    cmetadata json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: snomed_pg_embedding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snomed_pg_embedding (
    uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    collection_id uuid,
    embedding public.vector(768),
    document text,
    cmetadata json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying NOT NULL,
    hashed_password character varying NOT NULL,
    full_name character varying,
    is_active boolean,
    is_superuser boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vitals_daily_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_daily_aggregates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    metric_type character varying(50) NOT NULL,
    date date NOT NULL,
    average_value double precision,
    min_value double precision,
    max_value double precision,
    total_value double precision,
    count integer DEFAULT 0 NOT NULL,
    unit character varying(20) NOT NULL,
    primary_source character varying(20) NOT NULL,
    confidence_score double precision DEFAULT 1.0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    sources_included text,
    duration_minutes double precision,
    notes text,
    loinc_code character varying(20)
);


--
-- Name: vitals_daily_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vitals_daily_aggregates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vitals_daily_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vitals_daily_aggregates_id_seq OWNED BY public.vitals_daily_aggregates.id;


--
-- Name: vitals_hourly_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_hourly_aggregates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    metric_type character varying(50) NOT NULL,
    hour_start timestamp with time zone NOT NULL,
    average_value double precision,
    min_value double precision,
    max_value double precision,
    total_value double precision,
    count integer DEFAULT 0 NOT NULL,
    unit character varying(20) NOT NULL,
    primary_source character varying(20) NOT NULL,
    confidence_score double precision DEFAULT 1.0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    sources_included text,
    duration_minutes double precision,
    notes text,
    loinc_code character varying(20)
);


--
-- Name: vitals_hourly_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vitals_hourly_aggregates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vitals_hourly_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vitals_hourly_aggregates_id_seq OWNED BY public.vitals_hourly_aggregates.id;


--
-- Name: vitals_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_mappings (
    vital_sign character varying(255) NOT NULL,
    loinc_code character varying(50),
    property character varying(100),
    units character varying(100),
    system character varying(100),
    description text,
    loinc_source character varying(50)
);


--
-- Name: vitals_monthly_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_monthly_aggregates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    metric_type character varying(50) NOT NULL,
    year integer NOT NULL,
    month integer NOT NULL,
    average_value double precision,
    min_value double precision,
    max_value double precision,
    total_value double precision,
    count integer DEFAULT 0 NOT NULL,
    unit character varying(20) NOT NULL,
    primary_source character varying(20) NOT NULL,
    confidence_score double precision DEFAULT 1.0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    sources_included text,
    duration_minutes double precision,
    notes text,
    days_with_data integer DEFAULT 0,
    total_duration_minutes double precision,
    loinc_code character varying(20)
);


--
-- Name: vitals_monthly_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vitals_monthly_aggregates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vitals_monthly_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vitals_monthly_aggregates_id_seq OWNED BY public.vitals_monthly_aggregates.id;


--
-- Name: vitals_raw_categorized; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_raw_categorized (
    id integer NOT NULL,
    user_id integer NOT NULL,
    metric_type character varying NOT NULL,
    value double precision NOT NULL,
    unit character varying NOT NULL,
    start_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone NOT NULL,
    data_source character varying NOT NULL,
    source_device character varying,
    loinc_code character varying(20),
    notes text,
    confidence_score double precision,
    aggregation_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    aggregated_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: vitals_raw_categorized_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vitals_raw_categorized_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vitals_raw_categorized_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vitals_raw_categorized_id_seq OWNED BY public.vitals_raw_categorized.id;


--
-- Name: vitals_raw_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_raw_data (
    id integer NOT NULL,
    user_id integer NOT NULL,
    metric_type character varying(255) NOT NULL,
    value double precision NOT NULL,
    unit character varying(50) NOT NULL,
    start_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone NOT NULL,
    data_source character varying(255) NOT NULL,
    source_device character varying(255),
    notes text,
    confidence_score double precision,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    aggregation_status character varying(20) DEFAULT 'pending'::character varying,
    aggregated_at timestamp without time zone
);


--
-- Name: vitals_raw_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vitals_raw_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vitals_raw_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vitals_raw_data_id_seq OWNED BY public.vitals_raw_data.id;


--
-- Name: vitals_sync_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_sync_status (
    id integer NOT NULL,
    user_id integer NOT NULL,
    sync_enabled character varying(10) DEFAULT 'false'::character varying,
    last_sync_date timestamp without time zone,
    last_successful_sync timestamp without time zone,
    last_error text,
    error_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    data_source character varying(50) DEFAULT 'apple_healthkit'::character varying
);


--
-- Name: vitals_sync_status_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vitals_sync_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vitals_sync_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vitals_sync_status_id_seq OWNED BY public.vitals_sync_status.id;


--
-- Name: vitals_weekly_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vitals_weekly_aggregates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    metric_type character varying(50) NOT NULL,
    week_start_date date NOT NULL,
    average_value double precision,
    min_value double precision,
    max_value double precision,
    total_value double precision,
    count integer DEFAULT 0 NOT NULL,
    unit character varying(20) NOT NULL,
    primary_source character varying(20) NOT NULL,
    confidence_score double precision DEFAULT 1.0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    sources_included text,
    duration_minutes double precision,
    notes text,
    week_end_date date,
    days_with_data integer DEFAULT 0,
    total_duration_minutes double precision,
    loinc_code character varying(20)
);


--
-- Name: vitals_weekly_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vitals_weekly_aggregates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vitals_weekly_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vitals_weekly_aggregates_id_seq OWNED BY public.vitals_weekly_aggregates.id;


--
-- Name: agent_memory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_memory ALTER COLUMN id SET DEFAULT nextval('public.agent_memory_id_seq'::regclass);


--
-- Name: appointments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments ALTER COLUMN id SET DEFAULT nextval('public.appointments_id_seq'::regclass);


--
-- Name: chat_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages ALTER COLUMN id SET DEFAULT nextval('public.chat_messages_id_seq'::regclass);


--
-- Name: chat_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions ALTER COLUMN id SET DEFAULT nextval('public.chat_sessions_id_seq'::regclass);


--
-- Name: clinical_reports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_reports ALTER COLUMN id SET DEFAULT nextval('public.clinical_reports_id_seq'::regclass);


--
-- Name: consultation_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consultation_requests ALTER COLUMN id SET DEFAULT nextval('public.consultation_requests_id_seq'::regclass);


--
-- Name: doctors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors ALTER COLUMN id SET DEFAULT nextval('public.doctors_id_seq'::regclass);


--
-- Name: document_processing_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_logs ALTER COLUMN id SET DEFAULT nextval('public.document_processing_logs_id_seq'::regclass);


--
-- Name: health_data_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_data_history ALTER COLUMN id SET DEFAULT nextval('public.health_data_history_id_seq'::regclass);


--
-- Name: health_indicator_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_indicator_categories ALTER COLUMN id SET DEFAULT nextval('public.health_indicator_categories_id_seq'::regclass);


--
-- Name: health_indicators id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_indicators ALTER COLUMN id SET DEFAULT nextval('public.health_indicators_id_seq'::regclass);


--
-- Name: lab_reports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports ALTER COLUMN id SET DEFAULT nextval('public.lab_reports_id_seq'::regclass);


--
-- Name: lab_reports_daily id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_daily ALTER COLUMN id SET DEFAULT nextval('public.lab_reports_daily_id_seq'::regclass);


--
-- Name: lab_reports_monthly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_monthly ALTER COLUMN id SET DEFAULT nextval('public.lab_reports_monthly_id_seq'::regclass);


--
-- Name: lab_reports_quarterly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_quarterly ALTER COLUMN id SET DEFAULT nextval('public.lab_reports_quarterly_id_seq'::regclass);


--
-- Name: lab_reports_yearly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_yearly ALTER COLUMN id SET DEFAULT nextval('public.lab_reports_yearly_id_seq'::regclass);


--
-- Name: lab_test_mappings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_test_mappings ALTER COLUMN id SET DEFAULT nextval('public.lab_test_mappings_id_seq'::regclass);


--
-- Name: medical_images id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_images ALTER COLUMN id SET DEFAULT nextval('public.medical_images_id_seq'::regclass);


--
-- Name: nutrition_daily_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_daily_aggregates ALTER COLUMN id SET DEFAULT nextval('public.nutrition_daily_aggregates_id_seq'::regclass);


--
-- Name: nutrition_monthly_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_monthly_aggregates ALTER COLUMN id SET DEFAULT nextval('public.nutrition_monthly_aggregates_id_seq'::regclass);


--
-- Name: nutrition_raw_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_raw_data ALTER COLUMN id SET DEFAULT nextval('public.nutrition_raw_data_id_seq'::regclass);


--
-- Name: nutrition_sync_status id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_sync_status ALTER COLUMN id SET DEFAULT nextval('public.nutrition_sync_status_id_seq'::regclass);


--
-- Name: nutrition_weekly_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_weekly_aggregates ALTER COLUMN id SET DEFAULT nextval('public.nutrition_weekly_aggregates_id_seq'::regclass);


--
-- Name: opentelemetry_traces id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opentelemetry_traces ALTER COLUMN id SET DEFAULT nextval('public.opentelemetry_traces_id_seq'::regclass);


--
-- Name: patient_health_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_records ALTER COLUMN id SET DEFAULT nextval('public.patient_health_records_id_seq'::regclass);


--
-- Name: patient_health_summaries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_summaries ALTER COLUMN id SET DEFAULT nextval('public.patient_health_summaries_id_seq'::regclass);


--
-- Name: pharmacy_bills id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_bills ALTER COLUMN id SET DEFAULT nextval('public.pharmacy_bills_id_seq'::regclass);


--
-- Name: pharmacy_medications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_medications ALTER COLUMN id SET DEFAULT nextval('public.pharmacy_medications_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: vitals_daily_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_daily_aggregates ALTER COLUMN id SET DEFAULT nextval('public.vitals_daily_aggregates_id_seq'::regclass);


--
-- Name: vitals_hourly_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_hourly_aggregates ALTER COLUMN id SET DEFAULT nextval('public.vitals_hourly_aggregates_id_seq'::regclass);


--
-- Name: vitals_monthly_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_monthly_aggregates ALTER COLUMN id SET DEFAULT nextval('public.vitals_monthly_aggregates_id_seq'::regclass);


--
-- Name: vitals_raw_categorized id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_categorized ALTER COLUMN id SET DEFAULT nextval('public.vitals_raw_categorized_id_seq'::regclass);


--
-- Name: vitals_raw_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_data ALTER COLUMN id SET DEFAULT nextval('public.vitals_raw_data_id_seq'::regclass);


--
-- Name: vitals_sync_status id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_sync_status ALTER COLUMN id SET DEFAULT nextval('public.vitals_sync_status_id_seq'::regclass);


--
-- Name: vitals_weekly_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_weekly_aggregates ALTER COLUMN id SET DEFAULT nextval('public.vitals_weekly_aggregates_id_seq'::regclass);


--
-- Name: agent_memory agent_memory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_memory
    ADD CONSTRAINT agent_memory_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: appointments appointments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_pkey PRIMARY KEY (id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: chat_sessions chat_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_pkey PRIMARY KEY (id);


--
-- Name: clinical_notes clinical_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_notes
    ADD CONSTRAINT clinical_notes_pkey PRIMARY KEY (id);


--
-- Name: clinical_reports clinical_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_reports
    ADD CONSTRAINT clinical_reports_pkey PRIMARY KEY (id);


--
-- Name: consultation_requests consultation_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consultation_requests
    ADD CONSTRAINT consultation_requests_pkey PRIMARY KEY (id);


--
-- Name: doctors doctors_license_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors
    ADD CONSTRAINT doctors_license_number_key UNIQUE (license_number);


--
-- Name: doctors doctors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors
    ADD CONSTRAINT doctors_pkey PRIMARY KEY (id);


--
-- Name: document_processing_logs document_processing_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_logs
    ADD CONSTRAINT document_processing_logs_pkey PRIMARY KEY (id);


--
-- Name: health_data_history health_data_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_data_history
    ADD CONSTRAINT health_data_history_pkey PRIMARY KEY (id);


--
-- Name: health_indicator_categories health_indicator_categories_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_indicator_categories
    ADD CONSTRAINT health_indicator_categories_name_key UNIQUE (name);


--
-- Name: health_indicator_categories health_indicator_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_indicator_categories
    ADD CONSTRAINT health_indicator_categories_pkey PRIMARY KEY (id);


--
-- Name: health_indicators health_indicators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_indicators
    ADD CONSTRAINT health_indicators_pkey PRIMARY KEY (id);


--
-- Name: lab_report_categorized lab_report_categorized_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_report_categorized
    ADD CONSTRAINT lab_report_categorized_pkey PRIMARY KEY (user_id, loinc_code, test_value, test_date);


--
-- Name: lab_reports_daily lab_reports_daily_loinc_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_daily
    ADD CONSTRAINT lab_reports_daily_loinc_code_unique UNIQUE (user_id, date, test_category, loinc_code);


--
-- Name: lab_reports_daily lab_reports_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_daily
    ADD CONSTRAINT lab_reports_daily_pkey PRIMARY KEY (id);


--
-- Name: lab_reports_monthly lab_reports_monthly_loinc_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_monthly
    ADD CONSTRAINT lab_reports_monthly_loinc_code_unique UNIQUE (user_id, year, month, test_category, loinc_code);


--
-- Name: lab_reports_monthly lab_reports_monthly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_monthly
    ADD CONSTRAINT lab_reports_monthly_pkey PRIMARY KEY (id);


--
-- Name: lab_reports lab_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports
    ADD CONSTRAINT lab_reports_pkey PRIMARY KEY (id);


--
-- Name: lab_reports_quarterly lab_reports_quarterly_loinc_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_quarterly
    ADD CONSTRAINT lab_reports_quarterly_loinc_code_unique UNIQUE (user_id, year, quarter, test_category, loinc_code);


--
-- Name: lab_reports_quarterly lab_reports_quarterly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_quarterly
    ADD CONSTRAINT lab_reports_quarterly_pkey PRIMARY KEY (id);


--
-- Name: lab_reports_yearly lab_reports_yearly_loinc_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_yearly
    ADD CONSTRAINT lab_reports_yearly_loinc_code_unique UNIQUE (user_id, year, test_category, loinc_code);


--
-- Name: lab_reports_yearly lab_reports_yearly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports_yearly
    ADD CONSTRAINT lab_reports_yearly_pkey PRIMARY KEY (id);


--
-- Name: lab_test_mappings lab_test_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_test_mappings
    ADD CONSTRAINT lab_test_mappings_pkey PRIMARY KEY (id);


--
-- Name: langchain_pg_collection langchain_pg_collection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.langchain_pg_collection
    ADD CONSTRAINT langchain_pg_collection_pkey PRIMARY KEY (uuid);


--
-- Name: langchain_pg_embedding langchain_pg_embedding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.langchain_pg_embedding
    ADD CONSTRAINT langchain_pg_embedding_pkey PRIMARY KEY (uuid);


--
-- Name: loinc_pg_collection loinc_pg_collection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loinc_pg_collection
    ADD CONSTRAINT loinc_pg_collection_pkey PRIMARY KEY (uuid);


--
-- Name: loinc_pg_embedding loinc_pg_embedding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loinc_pg_embedding
    ADD CONSTRAINT loinc_pg_embedding_pkey PRIMARY KEY (uuid);


--
-- Name: medical_images medical_images_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_images
    ADD CONSTRAINT medical_images_pkey PRIMARY KEY (id);


--
-- Name: nutrition_daily_aggregates nutrition_daily_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_daily_aggregates
    ADD CONSTRAINT nutrition_daily_aggregates_pkey PRIMARY KEY (id);


--
-- Name: nutrition_monthly_aggregates nutrition_monthly_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_monthly_aggregates
    ADD CONSTRAINT nutrition_monthly_aggregates_pkey PRIMARY KEY (id);


--
-- Name: nutrition_raw_data nutrition_raw_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_raw_data
    ADD CONSTRAINT nutrition_raw_data_pkey PRIMARY KEY (id);


--
-- Name: nutrition_sync_status nutrition_sync_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_sync_status
    ADD CONSTRAINT nutrition_sync_status_pkey PRIMARY KEY (id);


--
-- Name: nutrition_weekly_aggregates nutrition_weekly_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_weekly_aggregates
    ADD CONSTRAINT nutrition_weekly_aggregates_pkey PRIMARY KEY (id);


--
-- Name: opentelemetry_traces opentelemetry_traces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opentelemetry_traces
    ADD CONSTRAINT opentelemetry_traces_pkey PRIMARY KEY (id);


--
-- Name: patient_health_records patient_health_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_records
    ADD CONSTRAINT patient_health_records_pkey PRIMARY KEY (id);


--
-- Name: patient_health_summaries patient_health_summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_summaries
    ADD CONSTRAINT patient_health_summaries_pkey PRIMARY KEY (id);


--
-- Name: pharmacy_bills pharmacy_bills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_bills
    ADD CONSTRAINT pharmacy_bills_pkey PRIMARY KEY (id);


--
-- Name: pharmacy_medications pharmacy_medications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_medications
    ADD CONSTRAINT pharmacy_medications_pkey PRIMARY KEY (id);


--
-- Name: prescriptions prescriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_pkey PRIMARY KEY (id);


--
-- Name: rxnorm_pg_collection rxnorm_pg_collection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rxnorm_pg_collection
    ADD CONSTRAINT rxnorm_pg_collection_pkey PRIMARY KEY (uuid);


--
-- Name: rxnorm_pg_embedding rxnorm_pg_embedding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rxnorm_pg_embedding
    ADD CONSTRAINT rxnorm_pg_embedding_pkey PRIMARY KEY (uuid);


--
-- Name: snomed_pg_collection snomed_pg_collection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snomed_pg_collection
    ADD CONSTRAINT snomed_pg_collection_pkey PRIMARY KEY (uuid);


--
-- Name: snomed_pg_embedding snomed_pg_embedding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snomed_pg_embedding
    ADD CONSTRAINT snomed_pg_embedding_pkey PRIMARY KEY (uuid);


--
-- Name: vitals_raw_categorized uq_vitals_raw_categorized_no_duplicates; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_categorized
    ADD CONSTRAINT uq_vitals_raw_categorized_no_duplicates UNIQUE (user_id, metric_type, unit, start_date, data_source, notes);


--
-- Name: vitals_raw_data uq_vitals_raw_data_no_duplicates; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_data
    ADD CONSTRAINT uq_vitals_raw_data_no_duplicates UNIQUE (user_id, metric_type, unit, start_date, data_source, notes);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: vitals_daily_aggregates vitals_daily_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_daily_aggregates
    ADD CONSTRAINT vitals_daily_aggregates_pkey PRIMARY KEY (id);


--
-- Name: vitals_hourly_aggregates vitals_hourly_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_hourly_aggregates
    ADD CONSTRAINT vitals_hourly_aggregates_pkey PRIMARY KEY (id);


--
-- Name: vitals_mappings vitals_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_mappings
    ADD CONSTRAINT vitals_mappings_pkey PRIMARY KEY (vital_sign);


--
-- Name: vitals_monthly_aggregates vitals_monthly_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_monthly_aggregates
    ADD CONSTRAINT vitals_monthly_aggregates_pkey PRIMARY KEY (id);


--
-- Name: vitals_raw_categorized vitals_raw_categorized_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_categorized
    ADD CONSTRAINT vitals_raw_categorized_pkey PRIMARY KEY (id);


--
-- Name: vitals_raw_data vitals_raw_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_data
    ADD CONSTRAINT vitals_raw_data_pkey PRIMARY KEY (id);


--
-- Name: vitals_sync_status vitals_sync_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_sync_status
    ADD CONSTRAINT vitals_sync_status_pkey PRIMARY KEY (id);


--
-- Name: vitals_weekly_aggregates vitals_weekly_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_weekly_aggregates
    ADD CONSTRAINT vitals_weekly_aggregates_pkey PRIMARY KEY (id);


--
-- Name: idx_aggregation_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aggregation_status ON public.vitals_raw_data USING btree (aggregation_status, user_id, start_date);


--
-- Name: idx_aggregation_status_categorized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aggregation_status_categorized ON public.vitals_raw_categorized USING btree (aggregation_status, user_id, start_date);


--
-- Name: idx_daily_category_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_daily_category_date ON public.lab_reports_daily USING btree (test_category, date);


--
-- Name: idx_daily_user_category_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_daily_user_category_date ON public.lab_reports_daily USING btree (user_id, test_category, date);


--
-- Name: idx_daily_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_daily_user_date ON public.lab_reports_daily USING btree (user_id, date);


--
-- Name: idx_date_loinc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_date_loinc ON public.vitals_daily_aggregates USING btree (date, loinc_code);


--
-- Name: idx_hour_loinc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hour_loinc ON public.vitals_hourly_aggregates USING btree (hour_start, loinc_code);


--
-- Name: idx_lab_categorized_inferred_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_categorized_inferred_category ON public.lab_report_categorized USING btree (inferred_test_category);


--
-- Name: idx_lab_categorized_test_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_categorized_test_category ON public.lab_report_categorized USING btree (test_category);


--
-- Name: idx_lab_categorized_test_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_categorized_test_date ON public.lab_report_categorized USING btree (test_date);


--
-- Name: idx_lab_categorized_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_categorized_user_id ON public.lab_report_categorized USING btree (user_id);


--
-- Name: idx_lab_report_categorized_aggregation_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_report_categorized_aggregation_status ON public.lab_report_categorized USING btree (aggregation_status);


--
-- Name: idx_lab_report_categorized_loinc_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_report_categorized_loinc_code ON public.lab_report_categorized USING btree (loinc_code);


--
-- Name: idx_lab_report_categorized_test_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_report_categorized_test_code ON public.lab_report_categorized USING btree (test_code);


--
-- Name: idx_lab_reports_categorization_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_categorization_status ON public.lab_reports USING btree (categorization_status);


--
-- Name: idx_lab_reports_daily_loinc_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_daily_loinc_code ON public.lab_reports_daily USING btree (loinc_code);


--
-- Name: idx_lab_reports_daily_test_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_daily_test_code ON public.lab_reports_daily USING btree (test_code);


--
-- Name: idx_lab_reports_monthly_loinc_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_monthly_loinc_code ON public.lab_reports_monthly USING btree (loinc_code);


--
-- Name: idx_lab_reports_monthly_test_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_monthly_test_code ON public.lab_reports_monthly USING btree (test_code);


--
-- Name: idx_lab_reports_quarterly_loinc_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_quarterly_loinc_code ON public.lab_reports_quarterly USING btree (loinc_code);


--
-- Name: idx_lab_reports_quarterly_test_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_quarterly_test_code ON public.lab_reports_quarterly USING btree (test_code);


--
-- Name: idx_lab_reports_yearly_loinc_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_yearly_loinc_code ON public.lab_reports_yearly USING btree (loinc_code);


--
-- Name: idx_lab_reports_yearly_test_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_reports_yearly_test_code ON public.lab_reports_yearly USING btree (test_code);


--
-- Name: idx_lab_test_mappings_loinc_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_test_mappings_loinc_code ON public.lab_test_mappings USING btree (loinc_code);


--
-- Name: idx_lab_test_mappings_test_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lab_test_mappings_test_code ON public.lab_test_mappings USING btree (test_code);


--
-- Name: idx_loinc_code_categorized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_loinc_code_categorized ON public.vitals_raw_categorized USING btree (loinc_code);


--
-- Name: idx_loinc_code_daily; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_loinc_code_daily ON public.vitals_daily_aggregates USING btree (loinc_code);


--
-- Name: idx_loinc_code_hourly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_loinc_code_hourly ON public.vitals_hourly_aggregates USING btree (loinc_code);


--
-- Name: idx_loinc_code_monthly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_loinc_code_monthly ON public.vitals_monthly_aggregates USING btree (loinc_code);


--
-- Name: idx_loinc_code_weekly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_loinc_code_weekly ON public.vitals_weekly_aggregates USING btree (loinc_code);


--
-- Name: idx_loinc_pg_embedding_collection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_loinc_pg_embedding_collection ON public.loinc_pg_embedding USING btree (collection_id);


--
-- Name: idx_loinc_pg_embedding_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_loinc_pg_embedding_embedding ON public.loinc_pg_embedding USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_medical_images_body_part; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_medical_images_body_part ON public.medical_images USING btree (body_part, exam_date);


--
-- Name: idx_medical_images_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_medical_images_status ON public.medical_images USING btree (processing_status, user_id);


--
-- Name: idx_medical_images_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_medical_images_type ON public.medical_images USING btree (image_type, exam_date);


--
-- Name: idx_medical_images_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_medical_images_user_date ON public.medical_images USING btree (user_id, exam_date);


--
-- Name: idx_metric_date_range_categorized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metric_date_range_categorized ON public.vitals_raw_categorized USING btree (metric_type, start_date, end_date);


--
-- Name: idx_monthly_category_year_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_monthly_category_year_month ON public.lab_reports_monthly USING btree (test_category, year, month);


--
-- Name: idx_monthly_user_category_year_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_monthly_user_category_year_month ON public.lab_reports_monthly USING btree (user_id, test_category, year, month);


--
-- Name: idx_monthly_user_year_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_monthly_user_year_month ON public.lab_reports_monthly USING btree (user_id, year, month);


--
-- Name: idx_nutrition_aggregation_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_aggregation_status ON public.nutrition_raw_data USING btree (aggregation_status, user_id, meal_date);


--
-- Name: idx_nutrition_date_daily; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_date_daily ON public.nutrition_daily_aggregates USING btree (date);


--
-- Name: idx_nutrition_dish_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_dish_type ON public.nutrition_raw_data USING btree (dish_type, meal_date);


--
-- Name: idx_nutrition_meal_date_range; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_meal_date_range ON public.nutrition_raw_data USING btree (meal_date, meal_time);


--
-- Name: idx_nutrition_meal_type_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_meal_type_date ON public.nutrition_raw_data USING btree (meal_type, meal_date);


--
-- Name: idx_nutrition_user_daily; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_user_daily ON public.nutrition_daily_aggregates USING btree (user_id, date);


--
-- Name: idx_nutrition_user_meal_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_user_meal_date ON public.nutrition_raw_data USING btree (user_id, meal_date);


--
-- Name: idx_nutrition_user_monthly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_user_monthly ON public.nutrition_monthly_aggregates USING btree (user_id, year, month);


--
-- Name: idx_nutrition_user_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_user_source ON public.nutrition_sync_status USING btree (user_id, data_source);


--
-- Name: idx_nutrition_user_source_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_user_source_date ON public.nutrition_raw_data USING btree (user_id, data_source, meal_date);


--
-- Name: idx_nutrition_user_weekly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nutrition_user_weekly ON public.nutrition_weekly_aggregates USING btree (user_id, week_start_date);


--
-- Name: idx_quarterly_category_year_quarter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quarterly_category_year_quarter ON public.lab_reports_quarterly USING btree (test_category, year, quarter);


--
-- Name: idx_quarterly_user_category_year_quarter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quarterly_user_category_year_quarter ON public.lab_reports_quarterly USING btree (user_id, test_category, year, quarter);


--
-- Name: idx_quarterly_user_year_quarter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quarterly_user_year_quarter ON public.lab_reports_quarterly USING btree (user_id, year, quarter);


--
-- Name: idx_rxnorm_pg_embedding_collection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rxnorm_pg_embedding_collection ON public.rxnorm_pg_embedding USING btree (collection_id);


--
-- Name: idx_rxnorm_pg_embedding_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rxnorm_pg_embedding_embedding ON public.rxnorm_pg_embedding USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_snomed_pg_embedding_collection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snomed_pg_embedding_collection ON public.snomed_pg_embedding USING btree (collection_id);


--
-- Name: idx_snomed_pg_embedding_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snomed_pg_embedding_embedding ON public.snomed_pg_embedding USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_test_category_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_test_category_active ON public.lab_test_mappings USING btree (test_category, is_active);


--
-- Name: idx_test_name_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_test_name_category ON public.lab_test_mappings USING btree (test_name, test_category);


--
-- Name: idx_test_name_standardized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_test_name_standardized ON public.lab_test_mappings USING btree (test_name_standardized);


--
-- Name: idx_user_loinc_daily; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_loinc_daily ON public.vitals_daily_aggregates USING btree (user_id, loinc_code, date);


--
-- Name: idx_user_loinc_hourly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_loinc_hourly ON public.vitals_hourly_aggregates USING btree (user_id, loinc_code, hour_start);


--
-- Name: idx_user_loinc_monthly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_loinc_monthly ON public.vitals_monthly_aggregates USING btree (user_id, loinc_code, year, month);


--
-- Name: idx_user_loinc_weekly; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_loinc_weekly ON public.vitals_weekly_aggregates USING btree (user_id, loinc_code, week_start_date);


--
-- Name: idx_user_metric_date_categorized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_metric_date_categorized ON public.vitals_raw_categorized USING btree (user_id, metric_type, start_date);


--
-- Name: idx_user_source_date_categorized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_source_date_categorized ON public.vitals_raw_categorized USING btree (user_id, data_source, start_date);


--
-- Name: idx_vitals_daily_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_daily_date ON public.vitals_daily_aggregates USING btree (date);


--
-- Name: idx_vitals_daily_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_vitals_daily_unique ON public.vitals_daily_aggregates USING btree (user_id, metric_type, date, primary_source);


--
-- Name: idx_vitals_daily_user_metric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_daily_user_metric ON public.vitals_daily_aggregates USING btree (user_id, metric_type);


--
-- Name: idx_vitals_hourly_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_hourly_timestamp ON public.vitals_hourly_aggregates USING btree (hour_start);


--
-- Name: idx_vitals_hourly_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_vitals_hourly_unique ON public.vitals_hourly_aggregates USING btree (user_id, metric_type, hour_start, primary_source);


--
-- Name: idx_vitals_hourly_user_metric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_hourly_user_metric ON public.vitals_hourly_aggregates USING btree (user_id, metric_type);


--
-- Name: idx_vitals_monthly_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_vitals_monthly_unique ON public.vitals_monthly_aggregates USING btree (user_id, metric_type, year, month, primary_source);


--
-- Name: idx_vitals_monthly_user_metric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_monthly_user_metric ON public.vitals_monthly_aggregates USING btree (user_id, metric_type);


--
-- Name: idx_vitals_monthly_year_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_monthly_year_month ON public.vitals_monthly_aggregates USING btree (year, month);


--
-- Name: idx_vitals_weekly_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_weekly_date ON public.vitals_weekly_aggregates USING btree (week_start_date);


--
-- Name: idx_vitals_weekly_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_vitals_weekly_unique ON public.vitals_weekly_aggregates USING btree (user_id, metric_type, week_start_date, primary_source);


--
-- Name: idx_vitals_weekly_user_metric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vitals_weekly_user_metric ON public.vitals_weekly_aggregates USING btree (user_id, metric_type);


--
-- Name: idx_yearly_category_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_yearly_category_year ON public.lab_reports_yearly USING btree (test_category, year);


--
-- Name: idx_yearly_user_category_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_yearly_user_category_year ON public.lab_reports_yearly USING btree (user_id, test_category, year);


--
-- Name: idx_yearly_user_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_yearly_user_year ON public.lab_reports_yearly USING btree (user_id, year);


--
-- Name: ix_agent_memory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_memory_id ON public.agent_memory USING btree (id);


--
-- Name: ix_appointments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_appointments_id ON public.appointments USING btree (id);


--
-- Name: ix_chat_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_id ON public.chat_messages USING btree (id);


--
-- Name: ix_chat_sessions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_sessions_id ON public.chat_sessions USING btree (id);


--
-- Name: ix_clinical_reports_chat_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clinical_reports_chat_session_id ON public.clinical_reports USING btree (chat_session_id);


--
-- Name: ix_clinical_reports_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clinical_reports_created_at ON public.clinical_reports USING btree (created_at);


--
-- Name: ix_clinical_reports_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clinical_reports_id ON public.clinical_reports USING btree (id);


--
-- Name: ix_clinical_reports_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clinical_reports_user_id ON public.clinical_reports USING btree (user_id);


--
-- Name: ix_consultation_requests_clinical_report_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consultation_requests_clinical_report_id ON public.consultation_requests USING btree (clinical_report_id);


--
-- Name: ix_consultation_requests_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consultation_requests_id ON public.consultation_requests USING btree (id);


--
-- Name: ix_doctors_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_doctors_email ON public.doctors USING btree (email);


--
-- Name: ix_doctors_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_doctors_id ON public.doctors USING btree (id);


--
-- Name: ix_document_processing_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_processing_logs_id ON public.document_processing_logs USING btree (id);


--
-- Name: ix_document_processing_logs_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_processing_logs_request_id ON public.document_processing_logs USING btree (request_id);


--
-- Name: ix_health_data_history_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_health_data_history_id ON public.health_data_history USING btree (id);


--
-- Name: ix_health_indicator_categories_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_health_indicator_categories_id ON public.health_indicator_categories USING btree (id);


--
-- Name: ix_health_indicators_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_health_indicators_id ON public.health_indicators USING btree (id);


--
-- Name: ix_lab_reports_daily_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_daily_date ON public.lab_reports_daily USING btree (date);


--
-- Name: ix_lab_reports_daily_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_daily_id ON public.lab_reports_daily USING btree (id);


--
-- Name: ix_lab_reports_daily_test_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_daily_test_category ON public.lab_reports_daily USING btree (test_category);


--
-- Name: ix_lab_reports_daily_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_daily_user_id ON public.lab_reports_daily USING btree (user_id);


--
-- Name: ix_lab_reports_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_id ON public.lab_reports USING btree (id);


--
-- Name: ix_lab_reports_monthly_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_monthly_id ON public.lab_reports_monthly USING btree (id);


--
-- Name: ix_lab_reports_monthly_test_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_monthly_test_category ON public.lab_reports_monthly USING btree (test_category);


--
-- Name: ix_lab_reports_monthly_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_monthly_user_id ON public.lab_reports_monthly USING btree (user_id);


--
-- Name: ix_lab_reports_quarterly_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_quarterly_id ON public.lab_reports_quarterly USING btree (id);


--
-- Name: ix_lab_reports_quarterly_test_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_quarterly_test_category ON public.lab_reports_quarterly USING btree (test_category);


--
-- Name: ix_lab_reports_quarterly_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_quarterly_user_id ON public.lab_reports_quarterly USING btree (user_id);


--
-- Name: ix_lab_reports_yearly_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_yearly_id ON public.lab_reports_yearly USING btree (id);


--
-- Name: ix_lab_reports_yearly_test_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_yearly_test_category ON public.lab_reports_yearly USING btree (test_category);


--
-- Name: ix_lab_reports_yearly_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_reports_yearly_user_id ON public.lab_reports_yearly USING btree (user_id);


--
-- Name: ix_lab_test_mappings_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_test_mappings_id ON public.lab_test_mappings USING btree (id);


--
-- Name: ix_lab_test_mappings_test_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lab_test_mappings_test_category ON public.lab_test_mappings USING btree (test_category);


--
-- Name: ix_lab_test_mappings_test_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_lab_test_mappings_test_name ON public.lab_test_mappings USING btree (test_name);


--
-- Name: ix_opentelemetry_traces_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_opentelemetry_traces_id ON public.opentelemetry_traces USING btree (id);


--
-- Name: ix_opentelemetry_traces_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_opentelemetry_traces_request_id ON public.opentelemetry_traces USING btree (request_id);


--
-- Name: ix_opentelemetry_traces_span_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_opentelemetry_traces_span_id ON public.opentelemetry_traces USING btree (span_id);


--
-- Name: ix_opentelemetry_traces_trace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_opentelemetry_traces_trace_id ON public.opentelemetry_traces USING btree (trace_id);


--
-- Name: ix_patient_health_records_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_health_records_id ON public.patient_health_records USING btree (id);


--
-- Name: ix_patient_health_summaries_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_health_summaries_id ON public.patient_health_summaries USING btree (id);


--
-- Name: ix_pharmacy_bills_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pharmacy_bills_id ON public.pharmacy_bills USING btree (id);


--
-- Name: ix_pharmacy_medications_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pharmacy_medications_id ON public.pharmacy_medications USING btree (id);


--
-- Name: ix_pharmacy_medications_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pharmacy_medications_user_id ON public.pharmacy_medications USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: lab_report_categorized trg_update_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_update_timestamp BEFORE UPDATE ON public.lab_report_categorized FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: lab_reports trg_update_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_update_timestamp BEFORE UPDATE ON public.lab_reports FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: agent_memory agent_memory_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_memory
    ADD CONSTRAINT agent_memory_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);


--
-- Name: agent_memory agent_memory_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_memory
    ADD CONSTRAINT agent_memory_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: appointments appointments_consultation_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_consultation_request_id_fkey FOREIGN KEY (consultation_request_id) REFERENCES public.consultation_requests(id);


--
-- Name: appointments appointments_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id);


--
-- Name: appointments appointments_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.users(id);


--
-- Name: chat_messages chat_messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);


--
-- Name: chat_messages chat_messages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: chat_sessions chat_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: clinical_notes clinical_notes_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_notes
    ADD CONSTRAINT clinical_notes_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);


--
-- Name: clinical_notes clinical_notes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinical_notes
    ADD CONSTRAINT clinical_notes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: document_processing_logs document_processing_logs_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_logs
    ADD CONSTRAINT document_processing_logs_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);


--
-- Name: document_processing_logs document_processing_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_logs
    ADD CONSTRAINT document_processing_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: consultation_requests fk_consultation_requests_clinical_report_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consultation_requests
    ADD CONSTRAINT fk_consultation_requests_clinical_report_id FOREIGN KEY (clinical_report_id) REFERENCES public.clinical_reports(id);


--
-- Name: pharmacy_medications fk_pharmacy_medications_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_medications
    ADD CONSTRAINT fk_pharmacy_medications_user_id FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: health_data_history health_data_history_current_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_data_history
    ADD CONSTRAINT health_data_history_current_record_id_fkey FOREIGN KEY (current_record_id) REFERENCES public.patient_health_records(id);


--
-- Name: health_data_history health_data_history_indicator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_data_history
    ADD CONSTRAINT health_data_history_indicator_id_fkey FOREIGN KEY (indicator_id) REFERENCES public.health_indicators(id);


--
-- Name: health_data_history health_data_history_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_data_history
    ADD CONSTRAINT health_data_history_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.users(id);


--
-- Name: health_data_history health_data_history_recorded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_data_history
    ADD CONSTRAINT health_data_history_recorded_by_fkey FOREIGN KEY (recorded_by) REFERENCES public.users(id);


--
-- Name: health_indicators health_indicators_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_indicators
    ADD CONSTRAINT health_indicators_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.health_indicator_categories(id);


--
-- Name: lab_report_categorized lab_report_categorized_extracted_from_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_report_categorized
    ADD CONSTRAINT lab_report_categorized_extracted_from_document_id_fkey FOREIGN KEY (extracted_from_document_id) REFERENCES public.document_processing_logs(id);


--
-- Name: lab_report_categorized lab_report_categorized_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_report_categorized
    ADD CONSTRAINT lab_report_categorized_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: lab_reports lab_reports_extracted_from_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports
    ADD CONSTRAINT lab_reports_extracted_from_document_id_fkey FOREIGN KEY (extracted_from_document_id) REFERENCES public.document_processing_logs(id);


--
-- Name: lab_reports lab_reports_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lab_reports
    ADD CONSTRAINT lab_reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: langchain_pg_embedding langchain_pg_embedding_collection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.langchain_pg_embedding
    ADD CONSTRAINT langchain_pg_embedding_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.langchain_pg_collection(uuid) ON DELETE CASCADE;


--
-- Name: loinc_pg_embedding loinc_pg_embedding_collection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loinc_pg_embedding
    ADD CONSTRAINT loinc_pg_embedding_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.loinc_pg_collection(uuid);


--
-- Name: medical_images medical_images_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_images
    ADD CONSTRAINT medical_images_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: nutrition_daily_aggregates nutrition_daily_aggregates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_daily_aggregates
    ADD CONSTRAINT nutrition_daily_aggregates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: nutrition_monthly_aggregates nutrition_monthly_aggregates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_monthly_aggregates
    ADD CONSTRAINT nutrition_monthly_aggregates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: nutrition_raw_data nutrition_raw_data_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_raw_data
    ADD CONSTRAINT nutrition_raw_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: nutrition_sync_status nutrition_sync_status_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_sync_status
    ADD CONSTRAINT nutrition_sync_status_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: nutrition_weekly_aggregates nutrition_weekly_aggregates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nutrition_weekly_aggregates
    ADD CONSTRAINT nutrition_weekly_aggregates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: opentelemetry_traces opentelemetry_traces_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opentelemetry_traces
    ADD CONSTRAINT opentelemetry_traces_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document_processing_logs(id);


--
-- Name: opentelemetry_traces opentelemetry_traces_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opentelemetry_traces
    ADD CONSTRAINT opentelemetry_traces_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);


--
-- Name: opentelemetry_traces opentelemetry_traces_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opentelemetry_traces
    ADD CONSTRAINT opentelemetry_traces_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: patient_health_records patient_health_records_indicator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_records
    ADD CONSTRAINT patient_health_records_indicator_id_fkey FOREIGN KEY (indicator_id) REFERENCES public.health_indicators(id);


--
-- Name: patient_health_records patient_health_records_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_records
    ADD CONSTRAINT patient_health_records_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.users(id);


--
-- Name: patient_health_records patient_health_records_recorded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_records
    ADD CONSTRAINT patient_health_records_recorded_by_fkey FOREIGN KEY (recorded_by) REFERENCES public.users(id);


--
-- Name: patient_health_summaries patient_health_summaries_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_summaries
    ADD CONSTRAINT patient_health_summaries_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.users(id);


--
-- Name: pharmacy_bills pharmacy_bills_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_bills
    ADD CONSTRAINT pharmacy_bills_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: pharmacy_medications pharmacy_medications_bill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_medications
    ADD CONSTRAINT pharmacy_medications_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES public.pharmacy_bills(id);


--
-- Name: prescriptions prescriptions_consultation_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_consultation_request_id_fkey FOREIGN KEY (consultation_request_id) REFERENCES public.consultation_requests(id);


--
-- Name: prescriptions prescriptions_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);


--
-- Name: rxnorm_pg_embedding rxnorm_pg_embedding_collection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rxnorm_pg_embedding
    ADD CONSTRAINT rxnorm_pg_embedding_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.rxnorm_pg_collection(uuid);


--
-- Name: snomed_pg_embedding snomed_pg_embedding_collection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snomed_pg_embedding
    ADD CONSTRAINT snomed_pg_embedding_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.snomed_pg_collection(uuid);


--
-- Name: vitals_daily_aggregates vitals_daily_aggregates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_daily_aggregates
    ADD CONSTRAINT vitals_daily_aggregates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: vitals_hourly_aggregates vitals_hourly_aggregates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_hourly_aggregates
    ADD CONSTRAINT vitals_hourly_aggregates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: vitals_monthly_aggregates vitals_monthly_aggregates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_monthly_aggregates
    ADD CONSTRAINT vitals_monthly_aggregates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: vitals_raw_categorized vitals_raw_categorized_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_categorized
    ADD CONSTRAINT vitals_raw_categorized_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: vitals_raw_data vitals_raw_data_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_raw_data
    ADD CONSTRAINT vitals_raw_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: vitals_sync_status vitals_sync_status_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_sync_status
    ADD CONSTRAINT vitals_sync_status_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: vitals_weekly_aggregates vitals_weekly_aggregates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vitals_weekly_aggregates
    ADD CONSTRAINT vitals_weekly_aggregates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

