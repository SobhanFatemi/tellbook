import { useQuery } from "@tanstack/react-query";
import { catalogApi } from "../api/catalog";

export function useBookSearch(params) {
  return useQuery({
    queryKey: ["books", "search", params],
    queryFn: () => catalogApi.search(params),
  });
}

export function useBookDetail(id) {
  return useQuery({
    queryKey: ["books", "detail", id],
    queryFn: () => catalogApi.detail(id),
    enabled: Boolean(id),
  });
}

export function useFeaturedBooks() {
  return useQuery({ queryKey: ["books", "featured"], queryFn: catalogApi.featured });
}

export function useSearchFilterOptions() {
  return useQuery({ queryKey: ["books", "filter-options"], queryFn: catalogApi.searchFilterOptions, staleTime: 5 * 60_000 });
}

/** Debounced-by-the-caller "did you mean...?" suggestions. */
export function useBookSuggestions(query) {
  return useQuery({
    queryKey: ["books", "suggest", query],
    queryFn: () => catalogApi.suggest(query),
    enabled: query.trim().length >= 2,
    staleTime: 30_000,
  });
}

export function useHomepageBooks() {
  return useQuery({queryKey:["books", "homepage"], queryFn:()=>catalogApi.homepage(), staleTime:60000, refetchOnWindowFocus:false});
}
