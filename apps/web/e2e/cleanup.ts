import type { Page } from "@playwright/test";

type Named = { id: string; name: string };

/**
 * Remove what a spec left on the shared e2e account: saved searches, workflows, and custom fields whose
 * name contains `marker` (the spec's unique stamp). The account has a 100-custom-field limit, so leftovers
 * eventually break other specs. Best effort: cleanup never fails a test.
 */
export async function removeLeftovers(page: Page, marker: string) {
  if (!marker) return;
  try {
    const request = page.request;
    const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "";
    const headers = { "X-CSRFToken": csrf };
    const list = async (url: string, key: string): Promise<Named[]> => {
      const response = await request.get(url);
      return response.ok() ? ((await response.json())[key] ?? []) : [];
    };
    const mine = (item: Named) => item.name.includes(marker);
    for (const view of (await list("/api/saved-views", "views")).filter(mine)) await request.delete(`/api/saved-views/${view.id}`, { headers });
    for (const flow of (await list("/api/workflows", "workflows")).filter(mine)) await request.delete(`/api/workflows/${flow.id}`, { headers });
    for (const field of (await list("/api/custom-fields", "fields")).filter(mine)) {
      // A field can be deleted only once no document holds a value for it.
      const holders = await list(`/api/documents?custom_field_id=${field.id}`, "documents");
      for (const document of holders) await request.delete(`/api/documents/${document.id}/custom-fields/${field.id}`, { headers });
      await request.delete(`/api/custom-fields/${field.id}`, { headers });
    }
  } catch {
    // The page may already be closed or signed out; the next run's cleanup is not affected.
  }
}
