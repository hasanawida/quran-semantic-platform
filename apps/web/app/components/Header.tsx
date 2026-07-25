"use client";

import Link from "next/link";

import { ROLE_LABELS, useAuth } from "../lib/auth";

function BookIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  );
}

const MANAGE_ROLES = [
  "text_officer",
  "tech_admin",
  "quality_manager",
  "linguistic_reviewer",
  "sharia_reviewer",
];

export default function Header() {
  const { user, loading, logout, hasRole } = useAuth();

  return (
    <header className="site-header">
      <nav className="container" aria-label="التنقل الرئيسي">
        <Link href="/" className="brand">
          <BookIcon />
          <span>منصة الاستقراء الدلالي</span>
        </Link>

        <div className="nav-actions">
          <Link href="/" className="nav-link">
            البحث
          </Link>
          <Link href="/mushaf/1" className="nav-link">
            المصحف
          </Link>
          <Link href="/compare" className="nav-link">
            مقارنة الجذور
          </Link>
          <Link href="/morphology" className="nav-link">
            البحث الصرفي
          </Link>
          <Link href="/claims" className="nav-link">
            الادعاءات
          </Link>
          <Link href="/methodology" className="nav-link">
            المنهج والمصادر
          </Link>
          <Link href="/provenance" className="nav-link">
            بيان الأصول
          </Link>
          {user && (
            <Link href="/review" className="nav-link">
              صندوق المراجعة
            </Link>
          )}
          {hasRole(...MANAGE_ROLES) && (
            <Link href="/admin/versions" className="nav-link">
              إصدارات النص
            </Link>
          )}
          {loading ? null : user ? (
            <div className="user-chip">
              <span className="user-name">{user.display_name}</span>
              <span className="user-roles">
                {user.roles.map((r) => ROLE_LABELS[r] ?? r).join("، ")}
              </span>
              <Link href="/account" className="nav-link">
                حسابي
              </Link>
              <button type="button" className="ghost small" onClick={logout}>
                خروج
              </button>
            </div>
          ) : (
            <Link href="/login" className="nav-link primary-link">
              دخول
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
