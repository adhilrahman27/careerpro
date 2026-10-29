-- CareerRadar Pro: Postgres/Supabase target schema reference.
-- Not applied to any user project. Deploy only into a NEW, dedicated project.
-- Backend currently uses SQLite; migrating API queries/auth is additional work.
-- Supabase Data API explicit grants are included (October 2026 behavior).
create extension if not exists pgcrypto;

create table if not exists public.profiles (
 user_id uuid primary key references auth.users(id) on delete cascade,
 full_name text not null default '', headline text not null default '',
 country text not null default 'United Arab Emirates',city text not null default 'Dubai',
 desired_titles text not null default '',skills text not null default '',
 years_experience int not null default 0 check(years_experience between 0 and 65),
 salary_min int check(salary_min>=0),salary_currency char(3) not null default 'AED',
 summary text not null default '',updated_at timestamptz not null default now()
);
create table if not exists public.job_providers (
 id text primary key,kind text not null check(kind in ('greenhouse','lever')),
 slug text not null,display_name text not null,enabled boolean not null default true,
 created_at timestamptz not null default now(),unique(kind,slug)
);
create table if not exists public.jobs (
 id uuid primary key default gen_random_uuid(),provider_id text references public.job_providers(id),
 source text not null,external_id text not null,company text not null,title text not null,
 location text not null default '',country text not null default '',work_type text not null default 'Not specified',
 description text not null default '',apply_url text not null,
 posted_at timestamptz,first_seen_at timestamptz not null default now(),
 last_seen_at timestamptz not null default now(),
 status text not null default 'active' check(status in ('active','closed','review')),
 salary_min bigint,salary_max bigint,currency char(3),unique(source,external_id)
);
create index if not exists jobs_status_posted_idx on public.jobs(status,posted_at desc);
create index if not exists jobs_fulltext_idx on public.jobs using gin(to_tsvector('english',title||' '||company||' '||description));
create table if not exists public.saved_jobs(
 user_id uuid not null references auth.users(id) on delete cascade,
 job_id uuid not null references public.jobs(id) on delete cascade,
 created_at timestamptz not null default now(),primary key(user_id,job_id)
);
create table if not exists public.alerts(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 name text not null,query text not null default '',location text not null default '',
 frequency text not null default 'daily' check(frequency in ('immediate','2h','6h','daily','weekly','off')),
 enabled boolean not null default true,created_at timestamptz not null default now()
);
create table if not exists public.alert_deliveries(
 alert_id uuid not null references public.alerts(id) on delete cascade,
 job_id uuid not null references public.jobs(id) on delete cascade,
 delivered_at timestamptz not null default now(),primary key(alert_id,job_id)
);
create table if not exists public.notifications(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 job_id uuid references public.jobs(id) on delete set null,
 title text not null,message text not null,created_at timestamptz not null default now(),read_at timestamptz
);
create table if not exists public.applications(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 job_id uuid references public.jobs(id) on delete set null,
 company text not null,title text not null,status text not null default 'interested'
 check(status in ('interested','applied','assessment','interview','followup','offer','rejected','withdrawn')),
 applied_at date,follow_up_at date,notes text not null default '',created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create table if not exists public.cv_documents(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 filename text not null,storage_key text not null,bytes bigint not null check(bytes>=0),created_at timestamptz not null default now()
);
create table if not exists public.job_reports(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 job_id uuid not null references public.jobs(id) on delete cascade,
 reason text not null,created_at timestamptz not null default now()
);
create table if not exists public.ingestion_runs(
 id uuid primary key default gen_random_uuid(),provider_id text not null references public.job_providers(id),
 started_at timestamptz not null default now(),finished_at timestamptz,
 status text not null,new_count int not null default 0,updated_count int not null default 0,error text not null default ''
);
-- Store privileged data out of user-editable metadata; admin assignment through server-side app_metadata only.
-- Explicitly enable RLS even on service-managed tables.
alter table public.profiles enable row level security;
alter table public.job_providers enable row level security;
alter table public.jobs enable row level security;
alter table public.saved_jobs enable row level security;
alter table public.alerts enable row level security;
alter table public.alert_deliveries enable row level security;
alter table public.notifications enable row level security;
alter table public.applications enable row level security;
alter table public.cv_documents enable row level security;
alter table public.job_reports enable row level security;
alter table public.ingestion_runs enable row level security;

create policy "Profiles owned select" on public.profiles for select to authenticated using ((select auth.uid())=user_id);
create policy "Profiles owned insert" on public.profiles for insert to authenticated with check ((select auth.uid())=user_id);
create policy "Profiles owned update" on public.profiles for update to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
create policy "Jobs publicly readable when active" on public.jobs for select to anon,authenticated using (status='active');
create policy "Saved owned select" on public.saved_jobs for select to authenticated using ((select auth.uid())=user_id);
create policy "Saved owned insert" on public.saved_jobs for insert to authenticated with check ((select auth.uid())=user_id);
create policy "Saved owned delete" on public.saved_jobs for delete to authenticated using ((select auth.uid())=user_id);
create policy "Alert owned select" on public.alerts for select to authenticated using ((select auth.uid())=user_id);
create policy "Alert owned insert" on public.alerts for insert to authenticated with check ((select auth.uid())=user_id);
create policy "Alert owned update" on public.alerts for update to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
create policy "Alert owned delete" on public.alerts for delete to authenticated using ((select auth.uid())=user_id);
create policy "Notification owned select" on public.notifications for select to authenticated using ((select auth.uid())=user_id);
create policy "Notification owned update" on public.notifications for update to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
create policy "Applications owned select" on public.applications for select to authenticated using ((select auth.uid())=user_id);
create policy "Applications owned insert" on public.applications for insert to authenticated with check ((select auth.uid())=user_id);
create policy "Applications owned update" on public.applications for update to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
create policy "Applications owned delete" on public.applications for delete to authenticated using ((select auth.uid())=user_id);
create policy "CV owned metadata select" on public.cv_documents for select to authenticated using ((select auth.uid())=user_id);
create policy "CV owned metadata insert" on public.cv_documents for insert to authenticated with check ((select auth.uid())=user_id);
create policy "CV owned metadata delete" on public.cv_documents for delete to authenticated using ((select auth.uid())=user_id);
create policy "Reports owned select" on public.job_reports for select to authenticated using ((select auth.uid())=user_id);
create policy "Reports owned insert" on public.job_reports for insert to authenticated with check ((select auth.uid())=user_id);
-- Only service role writes provider/jobs/deliveries/runs: no INSERT/UPDATE policies for end users.
-- Direct writes by service role bypass RLS; keep key in trusted services only.
revoke all on public.job_providers,public.ingestion_runs,public.alert_deliveries from anon,authenticated;
grant select on public.jobs to anon,authenticated;
grant select,insert,update on public.profiles to authenticated;
grant select,insert,delete on public.saved_jobs to authenticated;
grant select,insert,update,delete on public.alerts to authenticated;
grant select,update on public.notifications to authenticated;
grant select,insert,update,delete on public.applications to authenticated;
grant select,insert,delete on public.cv_documents to authenticated;
grant select,insert on public.job_reports to authenticated;
-- In actual deployment create a private storage bucket for CVs and bucket-specific ownership policies.
-- Do not create blanket storage.objects policies.
