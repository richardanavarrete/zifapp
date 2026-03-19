-- Migration 002: Fix RLS policies on organization_members and organizations
-- Problem: "Admins can manage members" policy on organization_members caused
-- infinite recursion because it queries organization_members from within its own policy.
-- Solution: Use a SECURITY DEFINER function to check admin role, bypassing RLS.

-- Create a helper function that checks admin/owner role without triggering RLS
CREATE OR REPLACE FUNCTION public.is_org_admin(check_org_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1 FROM organization_members
        WHERE user_id = auth.uid()
          AND org_id = check_org_id
          AND role IN ('owner', 'admin')
    );
$$;

-- Drop the recursive policy
DROP POLICY IF EXISTS "Admins can manage members" ON organization_members;

-- Re-create with non-recursive check using the SECURITY DEFINER function
CREATE POLICY "Admins can manage members"
    ON organization_members FOR ALL
    USING (
        org_id = get_user_org_id()
        AND is_org_admin(org_id)
    );

-- Members can read their own org's member list
DROP POLICY IF EXISTS "Members can view org members" ON organization_members;
CREATE POLICY "Members can view org members"
    ON organization_members FOR SELECT
    USING (org_id = get_user_org_id());

-- Users can read their own membership
DROP POLICY IF EXISTS "Users can view own membership" ON organization_members;
CREATE POLICY "Users can view own membership"
    ON organization_members FOR SELECT
    USING (user_id = auth.uid());

-- Re-enable RLS on both tables
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- Ensure organizations has basic policies
DROP POLICY IF EXISTS "Members can view their organization" ON organizations;
CREATE POLICY "Members can view their organization"
    ON organizations FOR SELECT
    USING (
        id IN (
            SELECT org_id FROM organization_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Owners can update their organization" ON organizations;
CREATE POLICY "Owners can update their organization"
    ON organizations FOR UPDATE
    USING (
        is_org_admin(id)
    );
