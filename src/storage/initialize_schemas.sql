-- Storage Layer Schema Initialization
-- This script sets up the necessary schemas and tables for the MLOps platform storage layer

-- Create schemas for different components
CREATE SCHEMA IF NOT EXISTS feature_store;
CREATE SCHEMA IF NOT EXISTS model_registry;
CREATE SCHEMA IF NOT EXISTS experiment_tracking;
CREATE SCHEMA IF NOT EXISTS operational_data;
CREATE SCHEMA IF NOT EXISTS dim; -- For dimension tables
CREATE SCHEMA IF NOT EXISTS fact; -- For fact tables

-- Create dimension tables
CREATE TABLE IF NOT EXISTS dim.d_user (
    user_key SERIAL PRIMARY KEY,
    user_id VARCHAR(50) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim.d_model (
    model_key SERIAL PRIMARY KEY,
    model_id VARCHAR(50) UNIQUE NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, model_version)
);

CREATE TABLE IF NOT EXISTS dim.d_feature (
    feature_key SERIAL PRIMARY KEY,
    feature_id VARCHAR(50) UNIQUE NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    feature_namespace VARCHAR(50) NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(feature_namespace, feature_name)
);

CREATE TABLE IF NOT EXISTS dim.d_experiment (
    experiment_key SERIAL PRIMARY KEY,
    experiment_id VARCHAR(50) UNIQUE NOT NULL,
    experiment_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create fact tables
CREATE TABLE IF NOT EXISTS fact.f_feature_value (
    feature_value_key SERIAL PRIMARY KEY,
    feature_key INTEGER NOT NULL REFERENCES dim.d_feature(feature_key),
    entity_id VARCHAR(50) NOT NULL,
    value_numeric DOUBLE PRECISION,
    value_text TEXT,
    value_timestamp TIMESTAMP WITH TIME ZONE,
    value_boolean BOOLEAN,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_to TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact.f_model_metric (
    metric_key SERIAL PRIMARY KEY,
    model_key INTEGER NOT NULL REFERENCES dim.d_model(model_key),
    experiment_key INTEGER REFERENCES dim.d_experiment(experiment_key),
    metric_name VARCHAR(50) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    metric_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact.f_prediction (
    prediction_key SERIAL PRIMARY KEY,
    model_key INTEGER NOT NULL REFERENCES dim.d_model(model_key),
    entity_id VARCHAR(50) NOT NULL,
    prediction_value DOUBLE PRECISION,
    prediction_label VARCHAR(100),
    prediction_probability DOUBLE PRECISION,
    prediction_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    latency_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Feature store tables
CREATE TABLE IF NOT EXISTS feature_store.feature_group (
    feature_group_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS feature_store.feature_definition (
    feature_id SERIAL PRIMARY KEY,
    feature_group_id INTEGER NOT NULL REFERENCES feature_store.feature_group(feature_group_id),
    name VARCHAR(100) NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(feature_group_id, name)
);

-- Model registry tables
CREATE TABLE IF NOT EXISTS model_registry.model (
    model_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    s3_uri VARCHAR(255) NOT NULL,
    framework VARCHAR(50) NOT NULL,
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS model_registry.model_deployment (
    deployment_id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES model_registry.model(model_id),
    environment VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    endpoint_url VARCHAR(255),
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deployed_by VARCHAR(50) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_feature_value_entity_id ON fact.f_feature_value(entity_id);
CREATE INDEX IF NOT EXISTS idx_feature_value_feature_key ON fact.f_feature_value(feature_key);
CREATE INDEX IF NOT EXISTS idx_feature_value_valid_from ON fact.f_feature_value(valid_from);
CREATE INDEX IF NOT EXISTS idx_prediction_entity_id ON fact.f_prediction(entity_id);
CREATE INDEX IF NOT EXISTS idx_prediction_timestamp ON fact.f_prediction(prediction_timestamp);
CREATE INDEX IF NOT EXISTS idx_model_metric_model_key ON fact.f_model_metric(model_key);

-- Create retention policy function
CREATE OR REPLACE FUNCTION cleanup_old_feature_values()
RETURNS void AS $$
BEGIN
    -- Delete feature values older than 90 days
    DELETE FROM fact.f_feature_value
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    -- Delete predictions older than 30 days
    DELETE FROM fact.f_prediction
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at columns
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN 
        SELECT table_schema || '.' || table_name 
        FROM information_schema.tables 
        WHERE table_schema IN ('dim', 'feature_store', 'model_registry') 
        AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_updated_at ON %s;
            CREATE TRIGGER update_updated_at
            BEFORE UPDATE ON %s
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        ', t, t);
    END LOOP;
END $$; 