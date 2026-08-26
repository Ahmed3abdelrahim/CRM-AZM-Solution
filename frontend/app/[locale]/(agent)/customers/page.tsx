"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  type ContactMethodCreate,
  type ContactMethodKind,
  type CustomerCreate,
  type CustomerType,
  type Locale,
} from "@/lib/api-client";

/** T066 — list + search (F01). Creation is included here too: without it there is no UI path
 * to a customer this list could ever show, and contracts/openapi.yaml's `createCustomer`
 * belongs to the same `/customers` collection this page already renders. */
export default function CustomersPage() {
  const t = useTranslations("Customers");
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);

  const customersQuery = useQuery({
    queryKey: ["customers", q],
    queryFn: () => api.listCustomers(q || undefined),
  });

  const branchesQuery = useQuery({ queryKey: ["branches"], queryFn: api.listBranches });
  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: api.listDepartments });

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("searchLabel")}</span>
          <input
            type="text"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder={t("searchPlaceholder")}
            className="rounded border px-3 py-2"
          />
        </label>
        <button
          type="button"
          onClick={() => setShowCreateForm((prev) => !prev)}
          className="rounded border px-3 py-2"
        >
          {showCreateForm ? t("cancelButton") : t("newCustomerButton")}
        </button>
      </div>

      {showCreateForm && (
        <CreateCustomerForm
          branches={branchesQuery.data ?? []}
          departments={departmentsQuery.data ?? []}
          onCreated={() => {
            setShowCreateForm(false);
            queryClient.invalidateQueries({ queryKey: ["customers"] });
          }}
        />
      )}

      <div className="mt-6">
        {customersQuery.isLoading && <p>{t("loading")}</p>}
        {customersQuery.isError && <p role="alert">{t("error")}</p>}
        {customersQuery.data && customersQuery.data.length === 0 && <p>{t("noResults")}</p>}
        {customersQuery.data && customersQuery.data.length > 0 && (
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b text-start">
                <th className="p-2 text-start">{t("columnName")}</th>
                <th className="p-2 text-start">{t("columnOrganization")}</th>
                <th className="p-2 text-start">{t("columnType")}</th>
                <th className="p-2 text-start">{t("columnStatus")}</th>
                <th className="p-2 text-start" />
              </tr>
            </thead>
            <tbody>
              {customersQuery.data.map((customer) => (
                <tr key={customer.id} className="border-b">
                  <td className="p-2">
                    {customer.full_name_ar}
                    {customer.full_name_en ? ` / ${customer.full_name_en}` : ""}
                  </td>
                  <td className="p-2">{customer.organization_name ?? ""}</td>
                  <td className="p-2">
                    {customer.customer_type === "individual"
                      ? t("customerTypeIndividual")
                      : t("customerTypeOrganization")}
                  </td>
                  <td className="p-2">{customer.is_active ? t("statusActive") : t("statusInactive")}</td>
                  <td className="p-2">
                    <Link href={`customers/${customer.id}`} className="underline">
                      {t("viewLink")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}

function CreateCustomerForm({
  branches,
  departments,
  onCreated,
}: {
  branches: { id: string; label_ar: string; label_en: string }[];
  departments: { id: string; branch_id: string; label_ar: string; label_en: string }[];
  onCreated: () => void;
}) {
  const t = useTranslations("Customers");
  const [branchId, setBranchId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [customerType, setCustomerType] = useState<CustomerType>("individual");
  const [fullNameAr, setFullNameAr] = useState("");
  const [fullNameEn, setFullNameEn] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [preferredLocale, setPreferredLocale] = useState<Locale>("ar");
  const [contactKind, setContactKind] = useState<ContactMethodKind>("phone");
  const [contactValue, setContactValue] = useState("");

  const departmentsForBranch = useMemo(
    () => departments.filter((department) => department.branch_id === branchId),
    [departments, branchId],
  );

  const createMutation = useMutation({
    mutationFn: (data: CustomerCreate) => api.createCustomer(data),
    onSuccess: onCreated,
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const contact_methods: ContactMethodCreate[] = [
      { kind: contactKind, value: contactValue, is_primary: true },
    ];
    createMutation.mutate({
      branch_id: branchId,
      department_id: departmentId,
      customer_type: customerType,
      full_name_ar: fullNameAr,
      full_name_en: fullNameEn || null,
      organization_name: organizationName || null,
      preferred_locale: preferredLocale,
      contact_methods,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3 rounded border p-4">
      <h2 className="font-semibold">{t("createFormTitle")}</h2>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("branch")}</span>
        <select
          required
          value={branchId}
          onChange={(event) => {
            setBranchId(event.target.value);
            setDepartmentId("");
          }}
          className="rounded border px-3 py-2"
        >
          <option value="">{t("selectPlaceholder")}</option>
          {branches.map((branch) => (
            <option key={branch.id} value={branch.id}>
              {branch.label_ar} / {branch.label_en}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("department")}</span>
        <select
          required
          value={departmentId}
          onChange={(event) => setDepartmentId(event.target.value)}
          className="rounded border px-3 py-2"
        >
          <option value="">{t("selectPlaceholder")}</option>
          {departmentsForBranch.map((department) => (
            <option key={department.id} value={department.id}>
              {department.label_ar} / {department.label_en}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("customerType")}</span>
        <select
          value={customerType}
          onChange={(event) => setCustomerType(event.target.value as CustomerType)}
          className="rounded border px-3 py-2"
        >
          <option value="individual">{t("customerTypeIndividual")}</option>
          <option value="organization">{t("customerTypeOrganization")}</option>
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("fullNameAr")}</span>
        <input
          required
          type="text"
          dir="rtl"
          value={fullNameAr}
          onChange={(event) => setFullNameAr(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("fullNameEn")}</span>
        <input
          type="text"
          value={fullNameEn}
          onChange={(event) => setFullNameEn(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      {customerType === "organization" && (
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("organizationName")}</span>
          <input
            type="text"
            value={organizationName}
            onChange={(event) => setOrganizationName(event.target.value)}
            className="rounded border px-3 py-2"
          />
        </label>
      )}

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("preferredLocale")}</span>
        <select
          value={preferredLocale}
          onChange={(event) => setPreferredLocale(event.target.value as Locale)}
          className="rounded border px-3 py-2"
        >
          <option value="ar">{t("localeAr")}</option>
          <option value="en">{t("localeEn")}</option>
        </select>
      </label>

      <fieldset className="flex flex-col gap-2 rounded border p-3">
        <legend className="text-sm text-gray-600">{t("contactMethodsTitle")}</legend>
        <div className="flex flex-wrap gap-2">
          <select
            value={contactKind}
            onChange={(event) => setContactKind(event.target.value as ContactMethodKind)}
            className="rounded border px-3 py-2"
          >
            <option value="phone">{t("contactKindPhone")}</option>
            <option value="email">{t("contactKindEmail")}</option>
            <option value="whatsapp">{t("contactKindWhatsapp")}</option>
            <option value="other">{t("contactKindOther")}</option>
          </select>
          <input
            required
            type="text"
            value={contactValue}
            onChange={(event) => setContactValue(event.target.value)}
            placeholder={t("contactValue")}
            className="rounded border px-3 py-2"
          />
        </div>
      </fieldset>

      {createMutation.isError && <p role="alert">{t("error")}</p>}

      <button type="submit" disabled={createMutation.isPending} className="rounded border px-3 py-2">
        {createMutation.isPending ? t("loading") : t("submitButton")}
      </button>
    </form>
  );
}
