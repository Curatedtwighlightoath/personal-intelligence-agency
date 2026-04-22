-- Seed defaults. ON CONFLICT DO NOTHING so re-running never clobbers edits.
-- Haiku 4.5 across departments: fast, cheap, and responsive during testing.
-- Swap per-department via the Departments UI or the providers CLI.

INSERT INTO department_config (department, provider, model, api_key_ref, base_url, extra) VALUES
    ('watchdog',  'anthropic', 'claude-haiku-4-5-20251001', 'ANTHROPIC_API_KEY', NULL, '{}'::jsonb),
    ('marketing', 'anthropic', 'claude-haiku-4-5-20251001', 'ANTHROPIC_API_KEY', NULL, '{}'::jsonb),
    ('rd',        'anthropic', 'claude-haiku-4-5-20251001', 'ANTHROPIC_API_KEY', NULL, '{}'::jsonb)
ON CONFLICT (department) DO NOTHING;

-- Default product row so the marketing UI has something to edit on first boot.
INSERT INTO product (id, name, one_liner, audience, tone, key_messages, links) VALUES
    ('default', 'My Product', '', '', '', '[]'::jsonb, '[]'::jsonb)
ON CONFLICT (id) DO NOTHING;
