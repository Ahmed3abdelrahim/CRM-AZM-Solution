# Feature Specification: Per-Branch Custom Branding

**Feature Branch**: `007-custom-branding`
**Status**: Roadmap — not implemented in sprint 001
**Source**: PLAN.md §3 Tier D; completes PLAN.md §5 F12
**Depends on**: 001 (branches, portal, storage interface)

## Scope

Sprint 001 built one visual identity. This feature makes the customer-facing surfaces —
portal, emails, survey pages — reflect the owning branch.

**Agent-facing surfaces are deliberately excluded.** Agents work across branches; re-theming
their interface per ticket is disorienting, not helpful.

## New Schema

Additive columns on `branches`:
`logo_storage_key`, `favicon_storage_key`, `primary_color`, `accent_color`,
`email_header_html`, `email_footer_html`, `portal_custom_domain`, `support_email`,
`support_phone`

## Requirements

- **FR-1** An administrator MUST be able to upload a logo and favicon per branch through the
  existing storage interface.
- **FR-2** Primary and accent colours MUST be settable per branch and applied via CSS custom
  properties — not by generating per-branch stylesheets.
- **FR-3** Contrast MUST be validated on save; a combination failing WCAG AA MUST be rejected
  with a localized explanation.
- **FR-4** Portal pages MUST resolve branding from the branch context, with the system default
  as fallback.
- **FR-5** Outbound email MUST use the branch's header, footer, logo, and support contacts.
- **FR-6** Branding MUST apply identically in RTL and LTR — logos and colours are direction-
  neutral, and no layout may assume otherwise.
- **FR-7** An optional custom domain per branch portal MUST be supported.
- **FR-8** Every branding change MUST be audited with before/after values.

## Acceptance Criteria

1. Two branches' portals render distinct logos and colours from the same deployment.
2. Emails from branch A carry branch A's header, footer, and support contacts.
3. A low-contrast colour pair is rejected on save with a reason the administrator can act on.
4. Switching the portal to Arabic preserves branding with no layout breakage.
5. The agent interface is visually unchanged regardless of which branch a ticket belongs to.

## Out of Scope

Per-department branding, agent interface theming, per-branch custom fonts, white-label mobile apps.
