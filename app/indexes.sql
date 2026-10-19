CREATE UNIQUE INDEX IF NOT EXISTS uq_user_email
    ON user (email COLLATE NOCASE) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_oauth_identity_user ON oauth_identity (user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_member_user ON workspace_member (user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_creator ON workspace (created_by);
CREATE INDEX IF NOT EXISTS idx_workspace_updater ON workspace (updated_by);
CREATE INDEX IF NOT EXISTS idx_project_workspace ON project (workspace_id);
CREATE INDEX IF NOT EXISTS idx_project_creator ON project (created_by);
CREATE INDEX IF NOT EXISTS idx_project_updater ON project (updated_by);
CREATE INDEX IF NOT EXISTS idx_project_member_workspace_user
    ON project_member (workspace_id, user_id);
CREATE INDEX IF NOT EXISTS idx_project_member_user ON project_member (user_id);
CREATE INDEX IF NOT EXISTS idx_member_invitation_scope
    ON member_invitation (workspace_id, project_id, expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sprint_one_active_per_project
    ON sprint (project_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_sprint_project_status
    ON sprint (project_id, status, start_date);
CREATE INDEX IF NOT EXISTS idx_sprint_task_history_sprint_time
    ON sprint_task_history (sprint_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_sprint_task_history_task_time
    ON sprint_task_history (task_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_task_project_status ON task (project_id, status);
CREATE INDEX IF NOT EXISTS idx_task_project_status_position
    ON task (project_id, status, position, id);
CREATE INDEX IF NOT EXISTS idx_task_project_assignee ON task (project_id, assignee_id);
CREATE INDEX IF NOT EXISTS idx_task_creator ON task (created_by);
CREATE INDEX IF NOT EXISTS idx_task_updater ON task (updated_by);
CREATE INDEX IF NOT EXISTS idx_password_reset_token_user
    ON password_reset_token (user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_password_reset_attempt_email_time
    ON password_reset_attempt (email_hash, requested_at);
CREATE INDEX IF NOT EXISTS idx_password_reset_attempt_ip_time
    ON password_reset_attempt (ip_hash, requested_at);
CREATE INDEX IF NOT EXISTS idx_notification_recipient_created
    ON notification (recipient_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_notification_recipient_unread
    ON notification (recipient_id, id DESC) WHERE read_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_comment_task_created ON comment (task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comment_author ON comment (author_id);
CREATE INDEX IF NOT EXISTS idx_comment_updater ON comment (updated_by);
