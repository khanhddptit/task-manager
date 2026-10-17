CREATE INDEX IF NOT EXISTS idx_workspace_member_user ON workspace_member (user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_creator ON workspace (created_by);
CREATE INDEX IF NOT EXISTS idx_workspace_updater ON workspace (updated_by);
CREATE INDEX IF NOT EXISTS idx_project_workspace ON project (workspace_id);
CREATE INDEX IF NOT EXISTS idx_project_creator ON project (created_by);
CREATE INDEX IF NOT EXISTS idx_project_updater ON project (updated_by);
CREATE INDEX IF NOT EXISTS idx_project_member_workspace_user
    ON project_member (workspace_id, user_id);
CREATE INDEX IF NOT EXISTS idx_project_member_user ON project_member (user_id);
CREATE INDEX IF NOT EXISTS idx_task_project_status ON task (project_id, status);
CREATE INDEX IF NOT EXISTS idx_task_project_assignee ON task (project_id, assignee_id);
CREATE INDEX IF NOT EXISTS idx_task_creator ON task (created_by);
CREATE INDEX IF NOT EXISTS idx_task_updater ON task (updated_by);
CREATE INDEX IF NOT EXISTS idx_comment_task_created ON comment (task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comment_author ON comment (author_id);
CREATE INDEX IF NOT EXISTS idx_comment_updater ON comment (updated_by);
