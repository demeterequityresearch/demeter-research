-- Demeter 회원 다운로드: Supabase 프로젝트(bfhkkaeyvdtmzpxxdlrc)에 한 번 실행 (SQL Editor에 붙여 넣고 Run)
-- 1) 다운로드 기록표: 누가(user_id·email) 무엇을(report) 언제(created_at) 보거나(view) 받았는지(download)
-- 2) 비공개 보관함 'reports': PDF는 여기에만 두고, 공개 저장소에는 올리지 않음
-- 3) 보관함 규칙: 로그인한 회원이 방금(2분 안) 기록을 남긴 리포트만 열 수 있음 → 기록 없이 받아 갈 수 없음
-- 다시 실행해도 괜찮게 작성함

create table if not exists public.downloads (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  email text not null default (auth.jwt() ->> 'email'),
  report text not null,  -- 보관함 안의 파일 이름, 예: 20261018-089890-bo.pdf
  kind text not null default 'download' check (kind in ('view', 'download')),
  created_at timestamptz not null default now()
);
create index if not exists downloads_user_report on public.downloads (user_id, report, created_at desc);

alter table public.downloads enable row level security;

drop policy if exists "회원은 자기 기록만 남김" on public.downloads;
create policy "회원은 자기 기록만 남김" on public.downloads
  for insert to authenticated
  with check (user_id = auth.uid() and email = (auth.jwt() ->> 'email') and created_at > now() - interval '1 minute');

drop policy if exists "회원은 자기 기록만 봄" on public.downloads;
create policy "회원은 자기 기록만 봄" on public.downloads
  for select to authenticated
  using (user_id = auth.uid());

insert into storage.buckets (id, name, public)
values ('reports', 'reports', false)
on conflict (id) do update set public = false;

drop policy if exists "기록을 남긴 회원만 리포트 열람" on storage.objects;
create policy "기록을 남긴 회원만 리포트 열람" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'reports'
    and exists (
      select 1 from public.downloads d
      where d.user_id = auth.uid()
        and d.report = storage.objects.name
        and d.created_at > now() - interval '2 minutes'
    )
  );
