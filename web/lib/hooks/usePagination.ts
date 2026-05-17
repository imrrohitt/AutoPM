"use client";

import { useEffect, useMemo, useState } from "react";

export function usePagination<T>(items: T[], pageSize = 9) {
  const [page, setPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const paginatedItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  const goToPage = (next: number) => {
    setPage(Math.min(Math.max(1, next), totalPages));
  };

  const resetPage = () => setPage(1);

  return {
    page,
    pageSize,
    totalPages,
    totalItems: items.length,
    paginatedItems,
    goToPage,
    resetPage,
    hasPrev: page > 1,
    hasNext: page < totalPages,
  };
}
