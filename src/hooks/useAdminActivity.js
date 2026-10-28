import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export const ACTIVITY_SECTIONS = {
  "/admin/requests": ["requests", "requests"],
  "/admin/orders": ["orders", "orders"],
  "/admin/shipments": ["shipments", "shipment-queue"],
  "/admin/refunds": ["refunds", "refunds"],
  "/admin/books/review": ["reviews", "book-review"],
  "/admin/prices": ["prices", "price-review"],
  "/admin/imports": ["imports", "import-history"],
};

export function useAdminActivity(userId, pathname) {
  const client = useQueryClient();
  const activity = useQuery({
    queryKey: ["admin", "activity", userId],
    queryFn: async () => (await apiClient.get("/admin/activity/")).data,
    enabled: Boolean(userId),
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  });
  useEffect(() => {
    const entry = ACTIVITY_SECTIONS[pathname];
    if (!entry || !userId) return;
    let stopped = false;
    let started = false;
    let unsubscribe = () => {};
    const [section, queryName] = entry;
    // Snapshot first, then load the section: changes arriving during loading
    // remain unread. Failed loads and abandoned navigation never clear badges.
    apiClient.get("/admin/activity/").then(({ data }) => {
      if (stopped) return;
      const check = () => {
        if (stopped || started) return;
        const names = section === "orders" ? [queryName, "payment-queue"] : [queryName];
        const queries = names.map(name => client.getQueryCache().findAll({ queryKey: ["admin", name], type: "active" })[0]);
        if (queries.some(query => !query || query.state.fetchStatus === "fetching")) return;
        started = true;
        Promise.all(queries.map(query => query.fetch())).then(async () => {
          if (stopped) return;
          await apiClient.post("/admin/activity/", { section, snapshot: data.snapshot });
          if (!stopped) client.invalidateQueries({ queryKey: ["admin", "activity", userId] });
        }).catch(() => {});
      };
      unsubscribe = client.getQueryCache().subscribe(check);
      check();
    }).catch(() => {});
    return () => { stopped = true; unsubscribe(); };
  }, [client, pathname, userId]);
  return activity.data?.counts || {};
}
