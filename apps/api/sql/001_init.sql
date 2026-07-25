create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

do $$ begin
  create type record_status as enum (
    'draft','imported','machine_generated','under_review',
    'approved','published','disputed','rejected','deprecated'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type confidence_level as enum (
    'verified','high','medium','low','machine_only','disputed'
  );
exception when duplicate_object then null;
end $$;

create table if not exists quran_text_versions (
  id uuid primary key default gen_random_uuid(),
  version_code text not null unique,
  title text not null,
  riwayah text not null,
  script_type text not null,
  counting_system text not null,
  source_name text not null,
  source_reference text,
  sha256_hash text not null,
  status record_status not null default 'imported',
  is_active boolean not null default false,
  approved_by_first uuid,
  approved_by_second uuid,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  check (
    is_active = false
    or (
      status = 'published'
      and approved_by_first is not null
      and approved_by_second is not null
      and approved_by_first <> approved_by_second
    )
  )
);

create unique index if not exists only_one_active_quran_version
on quran_text_versions ((is_active))
where is_active = true;

create table if not exists surahs (
  id smallint primary key,
  number smallint not null unique check (number between 1 and 114),
  arabic_name text not null,
  ayah_count smallint not null
);

create table if not exists ayahs (
  id uuid primary key default gen_random_uuid(),
  text_version_id uuid not null references quran_text_versions(id),
  surah_id smallint not null references surahs(id),
  ayah_number smallint not null check (ayah_number > 0),
  uthmani_text text not null,
  plain_search_text text,
  text_hash text not null,
  unique(text_version_id, surah_id, ayah_number)
);

create table if not exists roots (
  id uuid primary key default gen_random_uuid(),
  display_root text not null,
  normalized_root text not null unique,
  root_length smallint not null check (root_length between 2 and 5),
  status record_status not null default 'imported',
  confidence confidence_level not null default 'machine_only',
  created_at timestamptz not null default now()
);

create table if not exists audit_logs (
  id bigint generated always as identity primary key,
  actor_id uuid,
  action text not null,
  entity_type text not null,
  entity_id uuid,
  old_data jsonb,
  new_data jsonb,
  reason text,
  created_at timestamptz not null default now()
);

-- فهرس البحث النصي التقريبي على النص المطبع للبحث
create index if not exists ayahs_plain_search_trgm
on ayahs using gin (plain_search_text gin_trgm_ops);

-- سجل التدقيق ملحق فقط: يمنع التعديل والحذف على مستوى قاعدة البيانات
create or replace function audit_logs_block_mutation() returns trigger
language plpgsql as $$
begin
  raise exception 'audit_logs append-only: % not allowed', tg_op;
end $$;

create or replace trigger audit_logs_no_mutation
before update or delete on audit_logs
for each statement execute function audit_logs_block_mutation();

-- بيانات السور الثلاث أدناه عينة تطوير فقط (العد الكوفي).
-- القائمة الكاملة للسور الـ114 يجب أن تستورد وتراجع عبر مسار استيراد النص
-- الموثق، لا أن تكتب يدويًا.
insert into surahs (id, number, arabic_name, ayah_count) values
  (1, 1, 'الفاتحة', 7),
  (2, 2, 'البقرة', 286),
  (12, 12, 'يوسف', 111)
on conflict (id) do nothing;

insert into roots (display_root, normalized_root, root_length, status, confidence)
values ('ع ص ر', 'عصر', 3, 'published', 'medium')
on conflict (normalized_root) do nothing;

-- لا يضاف نص قرآني تجريبي هنا؛ يجب استيراده من مصدر موثق.
