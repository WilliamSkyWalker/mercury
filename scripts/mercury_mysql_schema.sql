-- Mercury MySQL Schema
-- Generated from Django models (ceres/models.py, ceres/models_perf.py)
-- Django internal tables (auth, contenttypes, migrations) included

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- Django internal tables
-- ============================================================

CREATE TABLE IF NOT EXISTS `django_migrations` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `app` VARCHAR(255) NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    `applied` DATETIME(6) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `django_content_type` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `app_label` VARCHAR(100) NOT NULL,
    `model` VARCHAR(100) NOT NULL,
    UNIQUE KEY `django_content_type_app_label_model` (`app_label`, `model`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `auth_group` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(150) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `auth_user` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `password` VARCHAR(128) NOT NULL,
    `last_login` DATETIME(6) NULL,
    `is_superuser` TINYINT(1) NOT NULL DEFAULT 0,
    `username` VARCHAR(150) NOT NULL UNIQUE,
    `first_name` VARCHAR(150) NOT NULL,
    `last_name` VARCHAR(150) NOT NULL,
    `email` VARCHAR(254) NOT NULL,
    `is_staff` TINYINT(1) NOT NULL DEFAULT 0,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `date_joined` DATETIME(6) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `auth_permission` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `content_type_id` BIGINT NOT NULL,
    `codename` VARCHAR(100) NOT NULL,
    UNIQUE KEY `auth_permission_content_type_id_codename` (`content_type_id`, `codename`),
    CONSTRAINT `auth_permission_content_type_id_fk_django_content_type_id`
        FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `auth_group_permissions` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `group_id` BIGINT NOT NULL,
    `permission_id` BIGINT NOT NULL,
    UNIQUE KEY `auth_group_permissions_group_id_permission_id` (`group_id`, `permission_id`),
    CONSTRAINT `auth_group_permissions_group_id_fk_auth_group_id`
        FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
    CONSTRAINT `auth_group_permissions_permission_id_fk_auth_permission_id`
        FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `auth_user_groups` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `group_id` BIGINT NOT NULL,
    UNIQUE KEY `auth_user_groups_user_id_group_id` (`user_id`, `group_id`),
    CONSTRAINT `auth_user_groups_user_id_fk_auth_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
    CONSTRAINT `auth_user_groups_group_id_fk_auth_group_id`
        FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `auth_user_user_permissions` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `permission_id` BIGINT NOT NULL,
    UNIQUE KEY `auth_user_user_permissions_user_id_permission_id` (`user_id`, `permission_id`),
    CONSTRAINT `auth_user_user_permissions_user_id_fk_auth_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
    CONSTRAINT `auth_user_user_permissions_permission_id_fk_auth_permission_id`
        FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: User
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_user` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `email` VARCHAR(254) NOT NULL UNIQUE,
    `display_name` VARCHAR(200) NOT NULL DEFAULT '',
    `username` VARCHAR(200) NOT NULL DEFAULT '',
    `is_admin` TINYINT(1) NOT NULL DEFAULT 0,
    `last_login` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: Project
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_project` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(200) NOT NULL UNIQUE,
    `description` LONGTEXT NOT NULL,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: Folder
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_folder` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `name` VARCHAR(200) NOT NULL,
    `parent_id` BIGINT NULL,
    `sort_order` INT NOT NULL DEFAULT 0,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `ceres_folder_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`),
    CONSTRAINT `ceres_folder_parent_id_fk_ceres_folder_id`
        FOREIGN KEY (`parent_id`) REFERENCES `ceres_folder` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: Testcase
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_testcase` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `case_name` VARCHAR(200) NOT NULL,
    `method` VARCHAR(10) NOT NULL DEFAULT 'GET',
    `url` VARCHAR(2000) NOT NULL,
    `headers` JSON NOT NULL,
    `params` JSON NOT NULL,
    `body_type` VARCHAR(20) NOT NULL DEFAULT 'none',
    `body` JSON NOT NULL,
    `assertions` JSON NOT NULL,
    `pre_request_script` LONGTEXT NOT NULL,
    `post_request_script` LONGTEXT NOT NULL,
    `script_type` VARCHAR(20) NOT NULL DEFAULT 'python',
    `folder_id` BIGINT NULL,
    `timeout` INT NOT NULL DEFAULT 30,
    `sort_order` INT NOT NULL DEFAULT 0,
    `tags` JSON NOT NULL,
    `comment` LONGTEXT NOT NULL,
    `files` JSON NOT NULL,
    `ws_steps` JSON NULL,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `ceres_testcase_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`),
    CONSTRAINT `ceres_testcase_folder_id_fk_ceres_folder_id`
        FOREIGN KEY (`folder_id`) REFERENCES `ceres_folder` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: Environment
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_env` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `variables` JSON NOT NULL,
    `runtime_variables` JSON NOT NULL,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY `ceres_env_project_id_name` (`project_id`, `name`),
    CONSTRAINT `ceres_env_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: Testplan
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_testplan` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `name` VARCHAR(200) NOT NULL,
    `folder_id` BIGINT NULL,
    `env_id` BIGINT NULL,
    `is_serial` TINYINT(1) NOT NULL DEFAULT 1,
    `retry_count` INT NOT NULL DEFAULT 0,
    `feishu_webhook` VARCHAR(500) NOT NULL DEFAULT '',
    `notify_on_failure` TINYINT(1) NOT NULL DEFAULT 1,
    `phone_on_failure` TINYINT(1) NOT NULL DEFAULT 0,
    `phone_muted` TINYINT(1) NOT NULL DEFAULT 0,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `ceres_testplan_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`),
    CONSTRAINT `ceres_testplan_folder_id_fk_ceres_folder_id`
        FOREIGN KEY (`folder_id`) REFERENCES `ceres_folder` (`id`) ON DELETE SET NULL,
    CONSTRAINT `ceres_testplan_env_id_fk_ceres_env_id`
        FOREIGN KEY (`env_id`) REFERENCES `ceres_env` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: TestplanCase (junction)
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_testplan_case` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `testplan_id` BIGINT NOT NULL,
    `testcase_id` BIGINT NOT NULL,
    `sort_order` INT NOT NULL DEFAULT 0,
    `case_snapshot` JSON NOT NULL,
    UNIQUE KEY `ceres_testplan_case_testplan_id_testcase_id` (`testplan_id`, `testcase_id`),
    CONSTRAINT `ceres_testplan_case_testplan_id_fk_ceres_testplan_id`
        FOREIGN KEY (`testplan_id`) REFERENCES `ceres_testplan` (`id`),
    CONSTRAINT `ceres_testplan_case_testcase_id_fk_ceres_testcase_id`
        FOREIGN KEY (`testcase_id`) REFERENCES `ceres_testcase` (`id`)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: ScheduledTask
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_scheduled_task` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(200) NOT NULL,
    `testplan_id` BIGINT NOT NULL,
    `env_id` BIGINT NULL,
    `trigger_type` VARCHAR(20) NOT NULL DEFAULT 'interval',
    `cron_expression` VARCHAR(100) NOT NULL DEFAULT '',
    `interval_seconds` INT NOT NULL DEFAULT 900,
    `is_active` TINYINT(1) NOT NULL DEFAULT 0,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `ceres_scheduled_task_testplan_id_fk_ceres_testplan_id`
        FOREIGN KEY (`testplan_id`) REFERENCES `ceres_testplan` (`id`),
    CONSTRAINT `ceres_scheduled_task_env_id_fk_ceres_env_id`
        FOREIGN KEY (`env_id`) REFERENCES `ceres_env` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: ExecutionRecord
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_execution_record` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `task_id` VARCHAR(200) NOT NULL UNIQUE,
    `testplan_id` BIGINT NULL,
    `env_id` BIGINT NULL,
    `env_snapshot` JSON NOT NULL,
    `trigger_type` VARCHAR(20) NOT NULL DEFAULT 'manual',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `total_cases` INT NOT NULL DEFAULT 0,
    `passed_cases` INT NOT NULL DEFAULT 0,
    `failed_cases` INT NOT NULL DEFAULT 0,
    `error_cases` INT NOT NULL DEFAULT 0,
    `skipped_cases` INT NOT NULL DEFAULT 0,
    `pass_rate` DOUBLE NOT NULL DEFAULT 0,
    `duration_ms` INT NOT NULL DEFAULT 0,
    `report_url` VARCHAR(500) NOT NULL DEFAULT '',
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `ceres_execution_record_task_id` (`task_id`),
    CONSTRAINT `ceres_execution_record_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`),
    CONSTRAINT `ceres_execution_record_testplan_id_fk_ceres_testplan_id`
        FOREIGN KEY (`testplan_id`) REFERENCES `ceres_testplan` (`id`) ON DELETE SET NULL,
    CONSTRAINT `ceres_execution_record_env_id_fk_ceres_env_id`
        FOREIGN KEY (`env_id`) REFERENCES `ceres_env` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: ExecutionCaseResult
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_execution_case_result` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `execution_id` BIGINT NOT NULL,
    `testcase_id` BIGINT NULL,
    `case_name` VARCHAR(200) NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'passed',
    `request_method` VARCHAR(10) NOT NULL DEFAULT '',
    `request_url` VARCHAR(2000) NOT NULL DEFAULT '',
    `request_headers` JSON NOT NULL,
    `request_body` LONGTEXT NOT NULL,
    `response_status` INT NOT NULL DEFAULT 0,
    `response_headers` JSON NOT NULL,
    `response_body` LONGTEXT NOT NULL,
    `duration_ms` INT NOT NULL DEFAULT 0,
    `assertion_results` JSON NOT NULL,
    `extracted_variables` JSON NOT NULL,
    `error_message` LONGTEXT NOT NULL,
    `stream_metrics` JSON NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT `fk_execution_case_result_execution`
        FOREIGN KEY (`execution_id`) REFERENCES `ceres_execution_record` (`id`),
    CONSTRAINT `fk_execution_case_result_testcase`
        FOREIGN KEY (`testcase_id`) REFERENCES `ceres_testcase` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: WhitelistEmail
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_whitelist_email` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `email` VARCHAR(254) NOT NULL UNIQUE,
    `note` VARCHAR(200) NOT NULL DEFAULT '',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: ProjectPermission
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_project_permission` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `project_id` BIGINT NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY `ceres_project_permission_user_id_project_id` (`user_id`, `project_id`),
    CONSTRAINT `ceres_project_permission_user_id_fk_ceres_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `ceres_user` (`id`),
    CONSTRAINT `ceres_project_permission_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: AuditLog
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_audit_log` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_email` VARCHAR(254) NOT NULL,
    `action` VARCHAR(20) NOT NULL,
    `path` VARCHAR(500) NOT NULL,
    `body` JSON NOT NULL,
    `status_code` INT NOT NULL DEFAULT 0,
    `ip_address` VARCHAR(39) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: Report
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_report` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `result` LONGTEXT NOT NULL,
    `detail` LONGTEXT NOT NULL,
    `store_link` VARCHAR(500) NOT NULL DEFAULT '',
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `ceres_report_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: PerfPlan (load testing)
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_perf_plan` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `env_id` BIGINT NULL,
    `name` VARCHAR(200) NOT NULL,
    `description` LONGTEXT NOT NULL,
    `target_rate` INT NOT NULL DEFAULT 100,
    `duration_secs` INT NOT NULL DEFAULT 60,
    `max_vus` INT NOT NULL DEFAULT 50,
    `transactions` JSON NOT NULL,
    `account_data_file_s3_key` VARCHAR(500) NOT NULL DEFAULT '',
    `notify_feishu_webhook` VARCHAR(500) NOT NULL DEFAULT '',
    `notify_on_completion` TINYINT(1) NOT NULL DEFAULT 0,
    `notify_on_failure` TINYINT(1) NOT NULL DEFAULT 1,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `idx_perf_plan_project` (`project_id`),
    KEY `idx_perf_plan_deleted` (`is_deleted`),
    CONSTRAINT `ceres_perf_plan_project_id_fk_ceres_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `ceres_project` (`id`),
    CONSTRAINT `ceres_perf_plan_env_id_fk_ceres_env_id`
        FOREIGN KEY (`env_id`) REFERENCES `ceres_env` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: PerfPlanCase (load testing junction)
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_perf_plan_case` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `perf_plan_id` BIGINT NOT NULL,
    `testcase_id` BIGINT NOT NULL,
    `role` VARCHAR(20) NOT NULL,
    `transaction_name` VARCHAR(100) NOT NULL DEFAULT '',
    `sort_order` INT NOT NULL DEFAULT 0,
    `data_file_s3_key` VARCHAR(500) NOT NULL DEFAULT '',
    `data_mode` VARCHAR(20) NOT NULL DEFAULT 'round_robin',
    `case_snapshot` JSON NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CHECK (`role` IN ('setup', 'transaction')),
    KEY `idx_perf_plan_case_plan` (`perf_plan_id`),
    KEY `idx_perf_plan_case_case` (`testcase_id`),
    CONSTRAINT `ceres_perf_plan_case_perf_plan_id_fk_ceres_perf_plan_id`
        FOREIGN KEY (`perf_plan_id`) REFERENCES `ceres_perf_plan` (`id`) ON DELETE CASCADE,
    CONSTRAINT `ceres_perf_plan_case_testcase_id_fk_ceres_testcase_id`
        FOREIGN KEY (`testcase_id`) REFERENCES `ceres_testcase` (`id`)
) ENGINE=InnoDB;

-- ============================================================
-- Ceres: PerfRun (load testing execution)
-- ============================================================

CREATE TABLE IF NOT EXISTS `ceres_perf_run` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `perf_plan_id` BIGINT NOT NULL,
    `target_rate` INT NOT NULL,
    `duration_secs` INT NOT NULL,
    `max_vus` INT NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `started_at` DATETIME(6) NULL,
    `finished_at` DATETIME(6) NULL,
    `last_heartbeat_at` DATETIME(6) NULL,
    `summary_json` JSON NOT NULL,
    `error_message` LONGTEXT NOT NULL,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `idx_perf_run_plan` (`perf_plan_id`),
    KEY `idx_perf_run_status` (`status`),
    KEY `idx_perf_run_started` (`started_at` DESC),
    CONSTRAINT `ceres_perf_run_perf_plan_id_fk_ceres_perf_plan_id`
        FOREIGN KEY (`perf_plan_id`) REFERENCES `ceres_perf_plan` (`id`)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;
