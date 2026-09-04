-- Mercury QA Platform - Database Schema
-- Auto-exported from production database
-- ============================================================

CREATE TABLE public.ceres_audit_log (
    id bigserial NOT NULL,
    user_email character varying(254) DEFAULT ''::character varying NOT NULL,
    action character varying(20) DEFAULT ''::character varying NOT NULL,
    path character varying(500) DEFAULT ''::character varying NOT NULL,
    body jsonb DEFAULT '{}'::jsonb NOT NULL,
    status_code integer DEFAULT 0 NOT NULL,
    ip_address inet,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.ceres_env (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    project_id bigint NOT NULL,
    name character varying(100) NOT NULL,
    variables jsonb DEFAULT '{}'::jsonb NOT NULL,
    runtime_variables jsonb DEFAULT '{}'::jsonb NOT NULL
);

CREATE TABLE public.ceres_execution_case_result (
    id bigserial NOT NULL,
    execution_id bigint NOT NULL,
    testcase_id bigint,
    case_name character varying(200) NOT NULL,
    status character varying(20) DEFAULT 'passed'::character varying NOT NULL,
    request_method character varying(10) DEFAULT ''::character varying NOT NULL,
    request_url character varying(2000) DEFAULT ''::character varying NOT NULL,
    request_headers jsonb DEFAULT '{}'::jsonb NOT NULL,
    request_body text DEFAULT ''::text NOT NULL,
    response_status integer DEFAULT 0 NOT NULL,
    response_headers jsonb DEFAULT '{}'::jsonb NOT NULL,
    response_body text DEFAULT ''::text NOT NULL,
    duration_ms integer DEFAULT 0 NOT NULL,
    assertion_results jsonb DEFAULT '[]'::jsonb NOT NULL,
    extracted_variables jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.ceres_execution_record (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    project_id bigint NOT NULL,
    task_id character varying(200) NOT NULL,
    testplan_id bigint,
    env_id bigint,
    env_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    trigger_type character varying(20) DEFAULT 'manual'::character varying NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    total_cases integer DEFAULT 0 NOT NULL,
    passed_cases integer DEFAULT 0 NOT NULL,
    failed_cases integer DEFAULT 0 NOT NULL,
    error_cases integer DEFAULT 0 NOT NULL,
    skipped_cases integer DEFAULT 0 NOT NULL,
    pass_rate double precision DEFAULT 0.0 NOT NULL,
    duration_ms integer DEFAULT 0 NOT NULL,
    report_url character varying(500) DEFAULT ''::character varying NOT NULL
);

CREATE TABLE public.ceres_folder (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    project_id bigint NOT NULL,
    name character varying(200) NOT NULL,
    parent_id bigint,
    sort_order integer DEFAULT 0 NOT NULL
);

CREATE TABLE public.ceres_perf_scenario (
    id serial NOT NULL,
    project_id integer NOT NULL,
    name character varying(200) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    testcase_configs jsonb DEFAULT '[]'::jsonb NOT NULL,
    setup_testcase_id integer,
    env_id integer,
    default_users integer DEFAULT 10 NOT NULL,
    default_run_time_secs integer DEFAULT 60 NOT NULL,
    default_hatch_rate integer DEFAULT 1 NOT NULL,
    last_build_status character varying(20) DEFAULT 'none'::character varying NOT NULL,
    last_build_at timestamp with time zone,
    last_build_error text DEFAULT ''::text NOT NULL,
    binary_path character varying(500) DEFAULT ''::character varying NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    data_files jsonb DEFAULT '[]'::jsonb NOT NULL
);

CREATE TABLE public.ceres_project (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    name character varying(200) NOT NULL,
    description text DEFAULT ''::text NOT NULL
);

CREATE TABLE public.ceres_project_permission (
    id bigserial NOT NULL,
    user_id bigint NOT NULL,
    project_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.ceres_report (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    project_id bigint NOT NULL,
    name character varying(100) NOT NULL,
    result text DEFAULT ''::text NOT NULL,
    detail text DEFAULT ''::text NOT NULL,
    store_link character varying(500) DEFAULT ''::character varying NOT NULL
);

CREATE TABLE public.ceres_scheduled_task (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    name character varying(200) NOT NULL,
    testplan_id bigint NOT NULL,
    env_id bigint,
    trigger_type character varying(20) DEFAULT 'interval'::character varying NOT NULL,
    cron_expression character varying(100) DEFAULT ''::character varying NOT NULL,
    interval_seconds integer DEFAULT 900 NOT NULL,
    is_active boolean DEFAULT false NOT NULL
);

CREATE TABLE public.ceres_testcase (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    project_id bigint NOT NULL,
    case_name character varying(200) NOT NULL,
    method character varying(10) DEFAULT 'GET'::character varying NOT NULL,
    url character varying(2000) NOT NULL,
    headers jsonb DEFAULT '[]'::jsonb NOT NULL,
    params jsonb DEFAULT '[]'::jsonb NOT NULL,
    body_type character varying(20) DEFAULT 'none'::character varying NOT NULL,
    body jsonb DEFAULT '{}'::jsonb NOT NULL,
    assertions jsonb DEFAULT '[]'::jsonb NOT NULL,
    pre_request_script text DEFAULT ''::text NOT NULL,
    post_request_script text DEFAULT ''::text NOT NULL,
    script_type character varying(20) DEFAULT 'python'::character varying NOT NULL,
    folder_id bigint,
    sort_order integer DEFAULT 0 NOT NULL,
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    comment text DEFAULT ''::text NOT NULL,
    timeout integer NOT NULL,
    files jsonb DEFAULT '[]'::jsonb NOT NULL,
    ws_steps jsonb
);

CREATE TABLE public.ceres_testplan (
    id bigserial NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    project_id bigint NOT NULL,
    name character varying(200) NOT NULL,
    folder_id bigint,
    env_id bigint,
    is_serial boolean DEFAULT true NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    feishu_webhook character varying(500) DEFAULT ''::character varying NOT NULL,
    notify_on_failure boolean DEFAULT true NOT NULL,
    phone_on_failure boolean DEFAULT false NOT NULL,
    phone_muted boolean DEFAULT false NOT NULL
);

CREATE TABLE public.ceres_testplan_case (
    id bigserial NOT NULL,
    testplan_id bigint NOT NULL,
    testcase_id bigint NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    case_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL
);

CREATE TABLE public.ceres_user (
    id bigint NOT NULL,
    email character varying(254) NOT NULL,
    display_name character varying(200) NOT NULL,
    username character varying(200) NOT NULL,
    last_login timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL,
    is_admin boolean DEFAULT false NOT NULL
);

CREATE TABLE public.ceres_whitelist_email (
    id bigserial NOT NULL,
    email character varying(254) NOT NULL,
    note character varying(200) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.django_content_type (
    id serial NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);

CREATE TABLE public.django_migrations (
    id bigserial NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);

-- ============================================================
-- Primary Keys
-- ============================================================
ALTER TABLE public.ceres_audit_log ADD CONSTRAINT ceres_audit_log_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_env ADD CONSTRAINT ceres_env_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_execution_case_result ADD CONSTRAINT ceres_execution_case_result_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_execution_record ADD CONSTRAINT ceres_execution_record_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_folder ADD CONSTRAINT ceres_folder_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_perf_scenario ADD CONSTRAINT ceres_perf_scenario_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_project ADD CONSTRAINT ceres_project_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_project_permission ADD CONSTRAINT ceres_project_permission_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_report ADD CONSTRAINT ceres_report_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_scheduled_task ADD CONSTRAINT ceres_scheduled_task_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_testcase ADD CONSTRAINT ceres_testcase_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_testplan ADD CONSTRAINT ceres_testplan_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_testplan_case ADD CONSTRAINT ceres_testplan_case_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_user ADD CONSTRAINT ceres_user_pkey PRIMARY KEY (id);
ALTER TABLE public.ceres_whitelist_email ADD CONSTRAINT ceres_whitelist_email_pkey PRIMARY KEY (id);
ALTER TABLE public.django_content_type ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);
ALTER TABLE public.django_migrations ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);
ALTER TABLE public.django_session ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);

-- ============================================================
-- Unique Constraints
-- ============================================================
ALTER TABLE public.ceres_env ADD CONSTRAINT ceres_env_project_id_name_key UNIQUE (project_id, name);
ALTER TABLE public.ceres_execution_record ADD CONSTRAINT ceres_execution_record_task_id_key UNIQUE (task_id);
ALTER TABLE public.ceres_project ADD CONSTRAINT ceres_project_name_key UNIQUE (name);
ALTER TABLE public.ceres_project_permission ADD CONSTRAINT ceres_project_permission_user_id_project_id_key UNIQUE (user_id, project_id);
ALTER TABLE public.ceres_testplan_case ADD CONSTRAINT ceres_testplan_case_testplan_id_testcase_id_key UNIQUE (testplan_id, testcase_id);
ALTER TABLE public.ceres_user ADD CONSTRAINT ceres_user_email_key UNIQUE (email);
ALTER TABLE public.ceres_whitelist_email ADD CONSTRAINT ceres_whitelist_email_email_key UNIQUE (email);
ALTER TABLE public.django_content_type ADD CONSTRAINT django_content_type_app_label_model_key UNIQUE (app_label, model);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_audit_log_created_at ON public.ceres_audit_log USING btree (created_at DESC);
CREATE INDEX idx_audit_log_user_email ON public.ceres_audit_log USING btree (user_email);
CREATE INDEX idx_ceres_env_project_id ON public.ceres_env USING btree (project_id);
CREATE INDEX idx_ceres_exec_case_result_execution_id ON public.ceres_execution_case_result USING btree (execution_id);
CREATE INDEX idx_ceres_exec_case_result_testcase_id ON public.ceres_execution_case_result USING btree (testcase_id);
CREATE INDEX idx_ceres_execution_record_env_id ON public.ceres_execution_record USING btree (env_id);
CREATE INDEX idx_ceres_execution_record_project_id ON public.ceres_execution_record USING btree (project_id);
CREATE INDEX idx_ceres_execution_record_task_id ON public.ceres_execution_record USING btree (task_id);
CREATE INDEX idx_ceres_execution_record_testplan_id ON public.ceres_execution_record USING btree (testplan_id);
CREATE INDEX idx_ceres_folder_parent_id ON public.ceres_folder USING btree (parent_id);
CREATE INDEX idx_ceres_folder_project_id ON public.ceres_folder USING btree (project_id);
CREATE INDEX idx_ceres_report_project_id ON public.ceres_report USING btree (project_id);
CREATE INDEX idx_ceres_scheduled_task_env_id ON public.ceres_scheduled_task USING btree (env_id);
CREATE INDEX idx_ceres_scheduled_task_testplan_id ON public.ceres_scheduled_task USING btree (testplan_id);
CREATE INDEX idx_ceres_testcase_folder_id ON public.ceres_testcase USING btree (folder_id);
CREATE INDEX idx_ceres_testcase_project_id ON public.ceres_testcase USING btree (project_id);
CREATE INDEX idx_ceres_testplan_case_testcase_id ON public.ceres_testplan_case USING btree (testcase_id);
CREATE INDEX idx_ceres_testplan_case_testplan_id ON public.ceres_testplan_case USING btree (testplan_id);
CREATE INDEX idx_ceres_testplan_env_id ON public.ceres_testplan USING btree (env_id);
CREATE INDEX idx_ceres_testplan_folder_id ON public.ceres_testplan USING btree (folder_id);
CREATE INDEX idx_ceres_testplan_project_id ON public.ceres_testplan USING btree (project_id);
CREATE INDEX idx_django_session_expire_date ON public.django_session USING btree (expire_date);
CREATE INDEX idx_perf_scenario_deleted ON public.ceres_perf_scenario USING btree (is_deleted);
CREATE INDEX idx_perf_scenario_project ON public.ceres_perf_scenario USING btree (project_id);

-- ============================================================
-- Foreign Keys
-- ============================================================
ALTER TABLE public.ceres_env ADD CONSTRAINT ceres_env_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_execution_case_result ADD CONSTRAINT ceres_execution_case_result_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.ceres_execution_record(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_execution_case_result ADD CONSTRAINT ceres_execution_case_result_testcase_id_fkey FOREIGN KEY (testcase_id) REFERENCES public.ceres_testcase(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_execution_record ADD CONSTRAINT ceres_execution_record_env_id_fkey FOREIGN KEY (env_id) REFERENCES public.ceres_env(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_execution_record ADD CONSTRAINT ceres_execution_record_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_execution_record ADD CONSTRAINT ceres_execution_record_testplan_id_fkey FOREIGN KEY (testplan_id) REFERENCES public.ceres_testplan(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_folder ADD CONSTRAINT ceres_folder_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.ceres_folder(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_folder ADD CONSTRAINT ceres_folder_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_perf_scenario ADD CONSTRAINT ceres_perf_scenario_env_id_fkey FOREIGN KEY (env_id) REFERENCES public.ceres_env(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_perf_scenario ADD CONSTRAINT ceres_perf_scenario_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id);
ALTER TABLE public.ceres_perf_scenario ADD CONSTRAINT ceres_perf_scenario_setup_testcase_id_fkey FOREIGN KEY (setup_testcase_id) REFERENCES public.ceres_testcase(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_project_permission ADD CONSTRAINT ceres_project_permission_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_project_permission ADD CONSTRAINT ceres_project_permission_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.ceres_user(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_report ADD CONSTRAINT ceres_report_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_scheduled_task ADD CONSTRAINT ceres_scheduled_task_env_id_fkey FOREIGN KEY (env_id) REFERENCES public.ceres_env(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_scheduled_task ADD CONSTRAINT ceres_scheduled_task_testplan_id_fkey FOREIGN KEY (testplan_id) REFERENCES public.ceres_testplan(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_testcase ADD CONSTRAINT ceres_testcase_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.ceres_folder(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_testcase ADD CONSTRAINT ceres_testcase_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_testplan ADD CONSTRAINT ceres_testplan_env_id_fkey FOREIGN KEY (env_id) REFERENCES public.ceres_env(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_testplan ADD CONSTRAINT ceres_testplan_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.ceres_folder(id) ON DELETE SET NULL;
ALTER TABLE public.ceres_testplan ADD CONSTRAINT ceres_testplan_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ceres_project(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_testplan_case ADD CONSTRAINT ceres_testplan_case_testcase_id_fkey FOREIGN KEY (testcase_id) REFERENCES public.ceres_testcase(id) ON DELETE CASCADE;
ALTER TABLE public.ceres_testplan_case ADD CONSTRAINT ceres_testplan_case_testplan_id_fkey FOREIGN KEY (testplan_id) REFERENCES public.ceres_testplan(id) ON DELETE CASCADE;

-- ============================================================
-- Seed: Whitelist & Admin (change to your own email)
-- ============================================================
INSERT INTO public.ceres_whitelist_email (email, note) VALUES ('your-email@example.com', 'admin');
INSERT INTO public.ceres_user (email, display_name, username, is_admin) VALUES ('your-email@example.com', 'Admin User', 'admin', true);
