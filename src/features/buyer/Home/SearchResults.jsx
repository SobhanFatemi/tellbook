import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Camera, SlidersHorizontal } from "lucide-react";
import { useBookSearch, useSearchFilterOptions } from "../../../hooks/useBooks";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import Card from "../../../components/Card";
import Button, { ButtonLink } from "../../../components/Button";
import { Input, Select } from "../../../components/FormFields";
import { toPersianDigits } from "../../../utils/persianFormat";
import PriceRangeFilter from "../../../components/PriceRangeFilter";
import AdminPagination from "../../../components/AdminPagination";
import BookCard from "../../../components/BookCard";

export default function SearchResults() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [showFilters, setShowFilters] = useState(false);

  const q = searchParams.get("q") || "";
  const params = {
    q,
    page: Math.max(1, Number(searchParams.get("page")) || 1),
    category: searchParams.get("category") || "",
    subcategory: searchParams.get("subcategory") || "",
    publisher_id: searchParams.get("publisher_id") || "",
    min_price: searchParams.get("min_price") || "",
    max_price: searchParams.get("max_price") || "",
    print_year: searchParams.get("print_year") || "",
  };

  const { data, isLoading, isError, refetch } = useBookSearch(params);
  const books = data?.results;
  const { data: filterOptions } = useSearchFilterOptions();

  const updateFilter = (key, value) => {
    const next = new URLSearchParams(searchParams);
    next.delete("page");
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  const activeFilterCount = Object.entries(params).filter(([key, value]) => key !== "q" && key !== "page" && value).length;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="page-title">{q ? `نتایج جستجو برای «${toPersianDigits(q)}»` : "فهرست کتاب‌ها"}</h1>
        <Button variant="ghost" className="flex items-center gap-1.5 text-sm shrink-0" aria-expanded={showFilters} aria-controls="catalog-filters" onClick={() => setShowFilters((v) => !v)}>
          <SlidersHorizontal size={16} /> فیلترها{activeFilterCount > 0 ? ` (${toPersianDigits(activeFilterCount)})` : ""}
        </Button>
      </div>

      {showFilters && (
        <Card id="catalog-filters" className="mb-6 catalog-search-filters">
          <Select label="دسته‌بندی" value={params.category} onChange={(e) => updateFilter("category", e.target.value)}>
            <option value="">همه</option>
            {filterOptions?.categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Select label="زیردسته" value={params.subcategory} onChange={(e) => updateFilter("subcategory", e.target.value)}>
            <option value="">همه</option>
            {filterOptions?.subcategories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Select label="ناشر" value={params.publisher_id} onChange={(e) => updateFilter("publisher_id", e.target.value)}>
            <option value="">همه</option>
            {filterOptions?.publishers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
          <Input
            label="سال چاپ"
            type="number"
            value={params.print_year}
            onChange={(e) => updateFilter("print_year", e.target.value)}
          />
          <PriceRangeFilter
            key={`${filterOptions?.price_bounds?.min_price}:${filterOptions?.price_bounds?.max_price}`}
            bounds={filterOptions?.price_bounds}
            minimum={params.min_price}
            maximum={params.max_price}
            onCommit={(minimum, maximum) => {
              const next = new URLSearchParams(searchParams);
              next.delete("page");
              if (minimum === filterOptions.price_bounds.min_price) next.delete("min_price");
              else next.set("min_price", minimum);
              if (maximum === filterOptions.price_bounds.max_price) next.delete("max_price");
              else next.set("max_price", maximum);
              setSearchParams(next, { replace: true });
            }}
          />

        </Card>
      )}

      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
        {!books?.length ? (
          <EmptyState
            title="چیزی پیدا نشد"
            description={q ? `کتابی با عنوان «${q}» تو تلبوک نیست، ولی می‌تونی ازمون بخوای برات تهیه‌اش کنیم.` : "فیلترهات رو تغییر بده یا یه چیزی جستجو کن."}
            action={
              <ButtonLink to="/request-a-book" state={{ prefillTitle: q }} className="flex items-center gap-2">
                  <Camera size={16} /> درخواست این کتاب
                </ButtonLink>
            }
          />
        ) : (
          <><div className="book-grid">{books.map(book => <BookCard key={book.id} book={book} />)}</div>
          <AdminPagination data={data} page={params.page} onChange={page => { const next = new URLSearchParams(searchParams); next.set("page", page); setSearchParams(next); window.scrollTo({top: 0, behavior: "auto"}); }} /></>
        )}
      </QueryBoundary>
    </div>
  );
}
