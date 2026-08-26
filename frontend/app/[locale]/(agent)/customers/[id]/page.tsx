"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LtrText } from "@/components/ltr-text";
import { api, type ContactMethodCreate, type ContactMethodKind } from "@/lib/api-client";

/** T067 — detail, history, contact methods, attachment upload (F01). */
export default function CustomerDetailPage() {
  const t = useTranslations("CustomerDetail");
  const params = useParams<{ id: string }>();
  const customerId = params.id;
  const queryClient = useQueryClient();
  const [showContactForm, setShowContactForm] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const customerQuery = useQuery({
    queryKey: ["customer", customerId],
    queryFn: () => api.getCustomer(customerId),
  });
  const contactMethodsQuery = useQuery({
    queryKey: ["customer", customerId, "contact-methods"],
    queryFn: () => api.listContactMethods(customerId),
  });
  const historyQuery = useQuery({
    queryKey: ["customer", customerId, "history"],
    queryFn: () => api.getCustomerHistory(customerId),
  });

  const deactivateMutation = useMutation({
    mutationFn: () => api.deactivateCustomer(customerId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["customer", customerId] }),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadCustomerAttachment(customerId, file),
  });

  if (customerQuery.isLoading) {
    return <p className="p-6">{t("loading")}</p>;
  }
  if (customerQuery.isError) {
    return <p className="p-6" role="alert">{t("error")}</p>;
  }
  const customer = customerQuery.data;
  if (!customer) {
    return <p className="p-6">{t("notFound")}</p>;
  }

  return (
    <main className="mx-auto max-w-3xl p-6">
      <Link href="/customers" className="underline">
        {t("backLink")}
      </Link>

      <h1 className="mt-2 text-2xl font-bold">
        {customer.full_name_ar}
        {customer.full_name_en ? ` / ${customer.full_name_en}` : ""}
      </h1>

      <section className="mt-4">
        <h2 className="font-semibold">{t("detailsTitle")}</h2>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <dt className="text-sm text-gray-600">{t("customerTypeIndividual")} / {t("customerTypeOrganization")}</dt>
          <dd>
            {customer.customer_type === "individual" ? t("customerTypeIndividual") : t("customerTypeOrganization")}
          </dd>
          {customer.national_id && (
            <>
              <dt className="text-sm text-gray-600">{t("nationalId")}</dt>
              <dd>
                <LtrText>{customer.national_id}</LtrText>
              </dd>
            </>
          )}
          {customer.notes && (
            <>
              <dt className="text-sm text-gray-600">{t("notes")}</dt>
              <dd>{customer.notes}</dd>
            </>
          )}
        </dl>
        <p className="mt-2">
          {customer.is_active ? t("statusActive") : t("statusInactive")}
          {customer.is_active && (
            <button
              type="button"
              onClick={() => deactivateMutation.mutate()}
              disabled={deactivateMutation.isPending}
              className="ms-2 rounded border px-2 py-1"
            >
              {t("deactivateButton")}
            </button>
          )}
        </p>
      </section>

      <section className="mt-6">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold">{t("contactMethodsTitle")}</h2>
          <button type="button" onClick={() => setShowContactForm((prev) => !prev)} className="rounded border px-2 py-1">
            {showContactForm ? t("cancelButton") : t("addContactMethodButton")}
          </button>
        </div>
        {showContactForm && (
          <AddContactMethodForm
            customerId={customerId}
            onAdded={() => {
              setShowContactForm(false);
              queryClient.invalidateQueries({ queryKey: ["customer", customerId, "contact-methods"] });
            }}
          />
        )}
        <ul className="mt-2 flex flex-col gap-1">
          {(contactMethodsQuery.data ?? []).map((contactMethod) => (
            <li key={contactMethod.id}>
              {contactMethod.kind}: <LtrText>{contactMethod.value}</LtrText>
              {contactMethod.is_primary ? ` (${t("contactPrimary")})` : ""}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">{t("historyTitle")}</h2>

        <h3 className="mt-2 text-sm font-semibold text-gray-600">{t("ticketsTitle")}</h3>
        {(historyQuery.data?.tickets ?? []).length === 0 ? (
          <p>{t("noTickets")}</p>
        ) : (
          <ul className="mt-1 flex flex-col gap-1">
            {historyQuery.data?.tickets.map((ticket) => (
              <li key={ticket.id}>
                <LtrText>{ticket.reference_no}</LtrText> — {ticket.subject}
              </li>
            ))}
          </ul>
        )}

        <h3 className="mt-4 text-sm font-semibold text-gray-600">{t("eventsTitle")}</h3>
        {(historyQuery.data?.events ?? []).length === 0 ? (
          <p>{t("noEvents")}</p>
        ) : (
          <ul className="mt-1 flex flex-col gap-1">
            {historyQuery.data?.events.map((event) => (
              <li key={event.id}>
                {event.event_type} — <LtrText>{new Date(event.created_at).toISOString()}</LtrText>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">{t("attachmentsTitle")}</h2>
        <input
          ref={fileInputRef}
          type="file"
          className="mt-2"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) uploadMutation.mutate(file);
          }}
        />
        {uploadMutation.isPending && <p>{t("uploading")}</p>}
        {uploadMutation.isError && <p role="alert">{t("error")}</p>}
      </section>
    </main>
  );
}

function AddContactMethodForm({ customerId, onAdded }: { customerId: string; onAdded: () => void }) {
  const t = useTranslations("CustomerDetail");
  const [kind, setKind] = useState<ContactMethodKind>("phone");
  const [value, setValue] = useState("");
  const [isPrimary, setIsPrimary] = useState(false);

  const addMutation = useMutation({
    mutationFn: (data: ContactMethodCreate) => api.addContactMethod(customerId, data),
    onSuccess: onAdded,
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    addMutation.mutate({ kind, value, is_primary: isPrimary });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-2 flex flex-wrap items-end gap-2 rounded border p-3">
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("contactKind")}</span>
        <select value={kind} onChange={(event) => setKind(event.target.value as ContactMethodKind)} className="rounded border px-3 py-2">
          <option value="phone">{t("contactKindPhone")}</option>
          <option value="email">{t("contactKindEmail")}</option>
          <option value="whatsapp">{t("contactKindWhatsapp")}</option>
          <option value="other">{t("contactKindOther")}</option>
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("contactValue")}</span>
        <input required type="text" value={value} onChange={(event) => setValue(event.target.value)} className="rounded border px-3 py-2" />
      </label>
      <label className="flex items-center gap-1">
        <input type="checkbox" checked={isPrimary} onChange={(event) => setIsPrimary(event.target.checked)} />
        <span className="text-sm text-gray-600">{t("contactPrimary")}</span>
      </label>
      {addMutation.isError && <p role="alert">{t("error")}</p>}
      <button type="submit" disabled={addMutation.isPending} className="rounded border px-3 py-2">
        {addMutation.isPending ? t("loading") : t("submitButton")}
      </button>
    </form>
  );
}
