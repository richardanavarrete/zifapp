-- smallCOGS Supabase Database Schema
-- Multi-tenant inventory management system
--
-- Run this migration in the Supabase SQL Editor or via CLI:
-- supabase db push

-- =============================================================================
-- Enable Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Organizations (Tenants)
-- =============================================================================

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    plan TEXT DEFAULT 'free',
    owner_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_owner ON organizations(owner_id);

-- =============================================================================
-- User Profiles (extends Supabase auth.users)
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_profiles_email ON user_profiles(email);

-- =============================================================================
-- Organization Members (many-to-many users <-> organizations)
-- =============================================================================

CREATE TABLE IF NOT EXISTS organization_members (
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    invited_by UUID REFERENCES auth.users(id),
    PRIMARY KEY (org_id, user_id)
);

CREATE INDEX idx_org_members_user ON organization_members(user_id);
CREATE INDEX idx_org_members_org ON organization_members(org_id);

-- =============================================================================
-- Organization Invites
-- =============================================================================

CREATE TABLE IF NOT EXISTS organization_invites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member', 'viewer')),
    code TEXT NOT NULL UNIQUE,
    accepted BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

CREATE INDEX idx_org_invites_code ON organization_invites(code);
CREATE INDEX idx_org_invites_org ON organization_invites(org_id);
CREATE INDEX idx_org_invites_email ON organization_invites(email);

-- =============================================================================
-- Datasets (Inventory data collections)
-- =============================================================================

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT NOT NULL,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    source_files JSONB DEFAULT '[]',
    date_range_start DATE,
    date_range_end DATE,
    items_count INTEGER DEFAULT 0,
    weeks_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY (dataset_id, org_id)
);

CREATE INDEX idx_datasets_org ON datasets(org_id);
CREATE INDEX idx_datasets_created ON datasets(created_at DESC);

-- =============================================================================
-- Items (Individual inventory items)
-- =============================================================================

CREATE TABLE IF NOT EXISTS items (
    item_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    display_name TEXT,
    category TEXT,
    vendor TEXT,
    location TEXT,
    unit_cost DECIMAL(10, 2) DEFAULT 0,
    unit_of_measure TEXT DEFAULT 'unit',
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY (item_id, dataset_id, org_id)
);

CREATE INDEX idx_items_dataset ON items(dataset_id, org_id);
CREATE INDEX idx_items_category ON items(category);
CREATE INDEX idx_items_vendor ON items(vendor);

-- =============================================================================
-- Weekly Records (Time-series inventory data)
-- =============================================================================

CREATE TABLE IF NOT EXISTS weekly_records (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    week_date DATE NOT NULL,
    on_hand DECIMAL(10, 2) NOT NULL,
    usage DECIMAL(10, 2) DEFAULT 0,
    week_name TEXT,
    source_file TEXT
);

CREATE INDEX idx_weekly_records_dataset ON weekly_records(dataset_id, org_id);
CREATE INDEX idx_weekly_records_item ON weekly_records(item_id, dataset_id, org_id);
CREATE INDEX idx_weekly_records_date ON weekly_records(week_date);

-- =============================================================================
-- Agent Runs (Order recommendation runs)
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    targets JSONB NOT NULL,
    constraints JSONB NOT NULL,
    summary JSONB NOT NULL,
    status TEXT DEFAULT 'completed',
    PRIMARY KEY (run_id, org_id)
);

CREATE INDEX idx_agent_runs_dataset ON agent_runs(dataset_id, org_id);
CREATE INDEX idx_agent_runs_created ON agent_runs(created_at DESC);

-- =============================================================================
-- Agent Recommendations (Per-item order suggestions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_recommendations (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    suggested_order INTEGER,
    reason_code TEXT,
    confidence TEXT,
    data JSONB NOT NULL
);

CREATE INDEX idx_agent_recs_run ON agent_recommendations(run_id);

-- =============================================================================
-- Voice Sessions (Voice counting sessions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS voice_sessions (
    session_id TEXT NOT NULL,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'in_progress',
    location TEXT,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY (session_id, org_id)
);

CREATE INDEX idx_voice_sessions_org ON voice_sessions(org_id);
CREATE INDEX idx_voice_sessions_status ON voice_sessions(status);

-- =============================================================================
-- Voice Count Records (Individual voice counts)
-- =============================================================================

CREATE TABLE IF NOT EXISTS voice_count_records (
    record_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    raw_text TEXT NOT NULL,
    item_id TEXT,
    display_name TEXT,
    match_confidence DECIMAL(3, 2) DEFAULT 0,
    quantity DECIMAL(10, 2) NOT NULL,
    unit TEXT DEFAULT 'bottles',
    confirmed BOOLEAN DEFAULT FALSE,
    rejected BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (record_id, org_id)
);

CREATE INDEX idx_voice_records_session ON voice_count_records(session_id, org_id);

-- =============================================================================
-- Row Level Security (RLS) Policies
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE weekly_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_count_records ENABLE ROW LEVEL SECURITY;

-- Helper function to get user's org_id
CREATE OR REPLACE FUNCTION get_user_org_id()
RETURNS UUID AS $$
    SELECT org_id FROM organization_members WHERE user_id = auth.uid() LIMIT 1;
$$ LANGUAGE SQL SECURITY DEFINER;

-- Organizations: users can view their own org
CREATE POLICY "Users can view their organization"
    ON organizations FOR SELECT
    USING (id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

CREATE POLICY "Users can create organizations"
    ON organizations FOR INSERT
    WITH CHECK (owner_id = auth.uid());

CREATE POLICY "Owners can update their organization"
    ON organizations FOR UPDATE
    USING (owner_id = auth.uid());

-- User Profiles: users can view and update their own profile
CREATE POLICY "Users can view all profiles in their org"
    ON user_profiles FOR SELECT
    USING (TRUE);

CREATE POLICY "Users can update own profile"
    ON user_profiles FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Service role can insert profiles"
    ON user_profiles FOR INSERT
    WITH CHECK (TRUE);

-- Organization Members: scoped to org membership
CREATE POLICY "Users can view members of their org"
    ON organization_members FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Admins can manage members"
    ON organization_members FOR ALL
    USING (
        org_id = get_user_org_id() AND
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE user_id = auth.uid() AND org_id = organization_members.org_id
            AND role IN ('owner', 'admin')
        )
    );

-- Datasets: scoped to org
CREATE POLICY "Users can view datasets in their org"
    ON datasets FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Users can create datasets in their org"
    ON datasets FOR INSERT
    WITH CHECK (org_id = get_user_org_id());

CREATE POLICY "Users can update datasets in their org"
    ON datasets FOR UPDATE
    USING (org_id = get_user_org_id());

CREATE POLICY "Users can delete datasets in their org"
    ON datasets FOR DELETE
    USING (org_id = get_user_org_id());

-- Items: scoped to org
CREATE POLICY "Users can view items in their org"
    ON items FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Users can manage items in their org"
    ON items FOR ALL
    USING (org_id = get_user_org_id());

-- Weekly Records: scoped to org
CREATE POLICY "Users can view records in their org"
    ON weekly_records FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Users can manage records in their org"
    ON weekly_records FOR ALL
    USING (org_id = get_user_org_id());

-- Agent Runs: scoped to org
CREATE POLICY "Users can view agent runs in their org"
    ON agent_runs FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Users can manage agent runs in their org"
    ON agent_runs FOR ALL
    USING (org_id = get_user_org_id());

-- Agent Recommendations: linked to agent_runs
CREATE POLICY "Users can view recommendations"
    ON agent_recommendations FOR SELECT
    USING (
        run_id IN (SELECT run_id FROM agent_runs WHERE org_id = get_user_org_id())
    );

CREATE POLICY "Users can manage recommendations"
    ON agent_recommendations FOR ALL
    USING (
        run_id IN (SELECT run_id FROM agent_runs WHERE org_id = get_user_org_id())
    );

-- Voice Sessions: scoped to org
CREATE POLICY "Users can view voice sessions in their org"
    ON voice_sessions FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Users can manage voice sessions in their org"
    ON voice_sessions FOR ALL
    USING (org_id = get_user_org_id());

-- Voice Count Records: scoped to org
CREATE POLICY "Users can view voice records in their org"
    ON voice_count_records FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Users can manage voice records in their org"
    ON voice_count_records FOR ALL
    USING (org_id = get_user_org_id());

-- Organization Invites: admins can manage
CREATE POLICY "Admins can view invites for their org"
    ON organization_invites FOR SELECT
    USING (org_id = get_user_org_id());

CREATE POLICY "Admins can create invites"
    ON organization_invites FOR INSERT
    WITH CHECK (
        org_id = get_user_org_id() AND
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE user_id = auth.uid() AND org_id = organization_invites.org_id
            AND role IN ('owner', 'admin')
        )
    );

-- =============================================================================
-- Triggers for updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_datasets_updated_at
    BEFORE UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_voice_sessions_updated_at
    BEFORE UPDATE ON voice_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Trigger to create user profile on signup
-- =============================================================================

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (user_id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        NEW.raw_user_meta_data->>'full_name'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Only create trigger if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created'
    ) THEN
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW EXECUTE FUNCTION handle_new_user();
    END IF;
END
$$;
